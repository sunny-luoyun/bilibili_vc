#!/usr/bin/env python3
"""
Bilibili 分区视频增量采集入库工具
==================================
基于 bilibili_search.py 提供的 BilibiliClient，
自动采集指定分区（默认 tid=30）的最新视频，存储到 SQLite 数据库。

【采集策略】
- 默认“增量模式”：每次都从第 1 页开始，直到遇到一页中所有视频都已入库，自动停止。
- 若手动指定 --page，则切换到“固定页码模式”，从指定页开始按页数爬取。
"""

import os
import sys
import time
import json
import sqlite3
import argparse
from typing import Optional
from dataclasses import asdict

# 导入现有模块（请确保 bilibili_search.py 在同一目录）
from bilibili_search import BilibiliClient, VideoInfo, PARTITION_MAP

DB_FILE = "bilibili_videos.db"
PROGRESS_FILE = "crawl_progress.json"
DEFAULT_TID = 30
MIN_INTERVAL = 3.5          # 每秒约 0.28 次，即每分钟约 17 次，远低于 20 次限制
MAX_RETRY_412 = 3           # 412 错误最大重试次数
RETRY_SLEEP_412 = 65        # 412 后等待秒数
RETRY_SLEEP_NET = 10        # 网络错误后等待秒数
MAX_RETRY_NET = 5           # 普通网络错误最大重试次数


def init_db(db_path: str):
    """初始化 SQLite 数据库，确保视频表存在且字段齐全"""
    create_sql = """
        CREATE TABLE IF NOT EXISTS videos (
            aid INTEGER,
            bvid TEXT PRIMARY KEY,
            title TEXT,
            author TEXT,
            mid INTEGER,
            typename TEXT,
            typeid INTEGER,
            play INTEGER,
            video_review INTEGER,
            danmaku INTEGER,
            review INTEGER,
            favorites INTEGER,
            coins INTEGER,
            likes INTEGER,
            duration TEXT,
            "create" TEXT,           -- 保留字需要双引号
            pubdate TEXT,
            description TEXT,        -- 修复：新增 description 字段
            pic TEXT,
            tag TEXT,
            crawled_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute(create_sql)
        # 兼容旧表：若缺失 description 列，自动添加
        for col in [("description", "TEXT")]:
            try:
                conn.execute(f'ALTER TABLE videos ADD COLUMN "{col[0]}" {col[1]}')
            except sqlite3.OperationalError:
                pass   # 列已存在，跳过


def video_exists(conn: sqlite3.Connection, bvid: str) -> bool:
    """检查 BV 号是否已存在"""
    cur = conn.execute("SELECT 1 FROM videos WHERE bvid = ?", (bvid,))
    return cur.fetchone() is not None

def get_watermark(conn: sqlite3.Connection) -> str:
    """获取数据库中最新视频的发布时间，作为增量采集的水位线"""
    cur = conn.execute("SELECT MAX(pubdate) FROM videos")
    row = cur.fetchone()
    return row[0] if row and row[0] else "1970-01-01 00:00"

def insert_video(conn: sqlite3.Connection, video: VideoInfo):
    """将 VideoInfo 对象插入数据库，保留 create 列并同时填充 pubdate"""
    data = asdict(video)
    data['pubdate'] = data.get('create', '')
    data.pop('crawled_at', None)
    # 👇 关键修改：用双引号包裹每个列名，避免保留字报错
    columns = ", ".join(f'"{k}"' for k in data.keys())
    placeholders = ", ".join("?" for _ in data)
    sql = f"INSERT OR IGNORE INTO videos ({columns}) VALUES ({placeholders})"
    conn.execute(sql, list(data.values()))


class ProgressTracker:
    """进度跟踪器，仅在“指定页码”模式下用于断点续爬"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.state = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_page": 0, "last_bvid": "", "last_pubdate": ""}

    def save(self, page: int, last_video: Optional[VideoInfo] = None):
        """保存当前进度"""
        self.state["last_page"] = page
        if last_video:
            self.state["last_bvid"] = last_video.bvid
            self.state["last_pubdate"] = last_video.create
        with open(self.filepath, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_start_page(self) -> int:
        """返回应该从第几页开始爬（进度页+1）"""
        return self.state["last_page"] + 1

    def __str__(self):
        return f"last_page={self.state['last_page']}, bvid={self.state.get('last_bvid')}"


def crawl_partition(
    tid: int = DEFAULT_TID,
    start_page: int = 1,
    max_pages: int = 20,
    db_path: str = DB_FILE,
    progress_path: str = PROGRESS_FILE,
    order: str = "pubdate",
    page_size: int = 30,
    incremental: bool = True,
    use_progress: bool = False,
    watermark: Optional[str] = None,       # 新增：外部指定水位线，格式 "YYYY-MM-DD HH:MM"
):
    """
    采集分区视频并入库

    增量模式 (incremental=True): 从第 1 页开始，遇视频 pubdate <= watermark 即停止。
    固定页码模式 (incremental=False): 按指定页码和页数爬取，支持进度续爬。
    """
    init_db(db_path)

    # 确定水位线：优先使用外部传入，否则从数据库获取最新视频时间
    if watermark is None:
        with sqlite3.connect(db_path) as tmp_conn:
            watermark = get_watermark(tmp_conn)
    print(f"watermark: {watermark}")

    # 模式选择
    if incremental:
        start_page = 1
        max_pages = max_pages  # 最多检查这些页，防止死循环
        print(f"[增量模式] 从第 1 页开始，至多检查 {max_pages} 页，水位线={watermark}")
    else:
        # 固定页码模式
        tracker = ProgressTracker(progress_path)
        if use_progress and start_page == 1 and tracker.get_start_page() > 1:
            start_page = tracker.get_start_page()
            print(f"[续爬] 从上次中断的第 {start_page} 页继续")
        else:
            print(f"[固定页码] 从第 {start_page} 页开始，共爬取 {max_pages} 页")
        max_pages = max_pages  # 原样保留

    client = BilibiliClient(delay=MIN_INTERVAL, verify_ssl=False)
    conn = sqlite3.connect(db_path)
    total_new = 0
    consecutive_zero_pages = 0

    try:
        for page in range(start_page, start_page + max_pages):
            print(f"\n--- 第 {page} 页 ---", flush=True)

            result = None
            retry_412 = 0
            retry_net = 0

            while result is None:
                try:
                    result = client.get_newlist(
                        tid=tid, page=page, page_size=page_size, order=order
                    )
                except Exception as e:
                    err_str = str(e).lower()
                    if "412" in err_str or "too many requests" in err_str:
                        retry_412 += 1
                        if retry_412 > MAX_RETRY_412:
                            print("  [严重] 412 错误次数过多，保存进度后退出", file=sys.stderr)
                            if not incremental:
                                tracker.save(page - 1)
                            conn.commit()
                            return
                        print(f"  [风控] 412 错误，休眠 {RETRY_SLEEP_412} 秒后重试...")
                        time.sleep(RETRY_SLEEP_412)
                    else:
                        retry_net += 1
                        if retry_net > MAX_RETRY_NET:
                            print(f"  [放弃] 网络错误次数过多，跳过第 {page} 页", file=sys.stderr)
                            break
                        print(f"  [错误] {e}，休眠 {RETRY_SLEEP_NET} 秒后重试 ({retry_net}/{MAX_RETRY_NET})...")
                        time.sleep(RETRY_SLEEP_NET)

            if result is None:
                print(f"  [跳过] 第 {page} 页未能获取数据，保存进度并继续")
                if not incremental:
                    tracker.save(page - 1)
                continue

            videos = result.get("videos", [])
            print(f"  获取到 {len(videos)} 个视频")

            if not videos:
                print("  本页无数据，已达到最后，爬取结束")
                if not incremental:
                    tracker.save(page)
                break

            # 插入新视频，同时检测是否抵达水位线
            page_new = 0
            reached_watermark = False
            for v in videos:
                # 检测水位线：若视频的发布时间 <= 水位线，则标记到达
                if v.create <= watermark:
                    reached_watermark = True
                    # 注意：即使到达水位线，仍然要尝试插入该视频（可能水位线边缘的视频之前未入库）
                if not video_exists(conn, v.bvid):
                    insert_video(conn, v)
                    page_new += 1
                    print(f"    + [{v.bvid}] {v.author}: {v.title[:40]}")

            conn.commit()
            total_new += page_new
            print(f"  本页新增 {page_new} 条，累计新增 {total_new} 条")

            # 停止判断
            if incremental:
                # 增量模式：一旦本页出现发布时间 <= 水位线的视频，处理后立即停止
                if reached_watermark:
                    print("  >>> 已到达水位线，增量采集完成。")
                    break
            else:
                # 固定页码模式：保留原来的连续多页无新视频停止，同时也可用水位线辅助
                last_video = videos[-1] if videos else None
                tracker.save(page, last_video)

                if page_new == 0:
                    consecutive_zero_pages += 1
                    if consecutive_zero_pages >= 3:
                        print("  连续 3 页无新视频，认为已追上最新进度，停止爬取")
                        break
                else:
                    consecutive_zero_pages = 0

                # (可选) 也可利用水位线提前终止固定页码模式
                if reached_watermark:
                    print("  已到达水位线，停止后续页码")
                    break

    except KeyboardInterrupt:
        print("\n[中断] 用户手动终止")
        if not incremental:
            saved_page = start_page - 1
            if 'page' in locals() and page > start_page:
                saved_page = page - 1
            tracker.save(saved_page)
            print(f"进度已保存至第 {saved_page} 页，下次可继续")
    finally:
        conn.close()

    print(f"\n{'='*50}")
    print(f"本次运行：新增 {total_new} 条视频记录")
    if not incremental:
        print(f"当前进度：{tracker}")
    print(f"数据库位置：{os.path.abspath(db_path)}")


def main():
    parser = argparse.ArgumentParser(
        description="Bilibili 分区视频增量采集入库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 增量采集（默认，推荐日常使用）
  python crawl_to_db.py

  # 增量采集，限制最多检查 50 页
  python crawl_to_db.py --max-pages 50

  # 强制从第 10 页开始，爬取 5 页（旧模式，用于回溯）
  python crawl_to_db.py --page 10 --max-pages 5

  # 指定分区
  python crawl_to_db.py --tid 33
        """
    )

    parser.add_argument("--tid", type=int, default=DEFAULT_TID,
                        help=f"分区 ID（默认 {DEFAULT_TID}：{PARTITION_MAP.get(DEFAULT_TID)}）")
    parser.add_argument("--page", type=int, default=None,
                        help="强制指定起始页码（提供此参数时将关闭增量模式，采用固定页码模式）")
    parser.add_argument("--max-pages", type=int, default=20,
                        help="本次最多爬取页数（默认 20）")
    parser.add_argument("--page-size", type=int, default=30,
                        help="每页视频数（默认 30，最大 50）")
    parser.add_argument("--order", type=str, default="pubdate",
                        choices=["pubdate", "click", "stow", "coin", "dm", "likes"],
                        help="排序方式（默认 pubdate）")
    parser.add_argument("--db", type=str, default=DB_FILE,
                        help="SQLite 数据库文件路径")
    parser.add_argument("--progress", type=str, default=PROGRESS_FILE,
                        help="进度文件路径（仅在固定页码模式下使用）")
    parser.add_argument("--no-resume", action="store_true", default=False,
                        help="忽略历史进度（仅在固定页码模式下有效）")
    parser.add_argument("--since", type=str, default=None,
                        help="手动指定水位线时间，格式 'YYYY-MM-DD HH:MM'，从该时间开始向前采集")
    args = parser.parse_args()

    # 判断模式：若用户未指定 --page，则为增量模式
    if args.page is None:
        incremental_mode = True
        start_page = 1
        use_progress = False
    else:
        incremental_mode = False
        start_page = max(args.page, 1)
        use_progress = not args.no_resume

    crawl_partition(
        tid=args.tid,
        start_page=start_page,
        max_pages=args.max_pages,
        db_path=args.db,
        progress_path=args.progress,
        order=args.order,
        page_size=args.page_size,
        incremental=incremental_mode,
        use_progress=use_progress,
        watermark=args.since,
    )


if __name__ == "__main__":
    main()