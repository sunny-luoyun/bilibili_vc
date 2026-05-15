#!/usr/bin/env python3
"""
视频筛选工具：从 bilibili_videos.db 中抽取符合时间与关键词条件的视频，
并支持通过黑名单 BV 号进行过滤。
新增：自动备份旧结果并对比，输出本次新增的 BV 号与标题。
====================================================================
条件：
1. 视频时长大于 2 分钟且小于 10 分钟（开区间）
2. 标题或简介完整包含关键词列表中的至少一个
3. 排除黑名单 txt 文件中列出的 BV 号（每行一个）
4. 结果存入新的 SQLite 数据库（默认 filtered_videos.db，自动覆盖）
5. 与上次自动备份的结果对比，输出新增视频
"""

import os
import sys
import sqlite3
import argparse
import re
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "..", "workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)
DEFAULT_SOURCE_DB = os.path.join(WORKSPACE_DIR, "bilibili_videos.db")
DEFAULT_TARGET_DB = os.path.join(WORKSPACE_DIR, "filtered_videos.db")
DEFAULT_MIN_SEC = 120      # 大于 2 分钟
DEFAULT_MAX_SEC = 420     # 小于 7 分钟
KEYWORDS = [
    "洛天依","天依","乐正绫", "言和", "乐正龙牙", "墨清弦", "徵羽摩柯",
    "心华", "星尘","海伊", "苍穹", "赤羽","诗岸", "牧心", "艾尔法","永夜",
    "初音未来"
]
BLOCK_KEYWORDS = [
    "周刊VOCALOID中文新曲榜","周刊言和新曲排行榜","洛天依新曲排行榜",
    "中文虚拟歌手PickUP周刊","周刊中文虚拟歌手原创传说曲排行榜",
    "中文术力口宝藏日推歌单","中文字幕","周刊Synthesizer","23V吧调音赛","日文原创曲","SNOW MIKU","DECO*27"
]

def match_block_keywords(text: str) -> bool:
    if not text:
        return False
    for bw in BLOCK_KEYWORDS:
        if bw in text:
            return True
    return False

def parse_duration_to_seconds(duration_str: str) -> int:
    if not duration_str:
        return None
    dur = duration_str.strip()
    match = re.match(r"(\d+):(\d+):(\d+)$", dur)
    if match:
        h, m, s = map(int, match.groups())
        return h * 3600 + m * 60 + s
    match = re.match(r"(\d+):(\d+)$", dur)
    if match:
        m, s = map(int, match.groups())
        return m * 60 + s
    if dur.isdigit():
        return int(dur)
    return None

def match_keywords(text: str) -> bool:
    if not text:
        return False
    for kw in KEYWORDS:
        if kw in text:
            return True
    return False

def load_blacklist(filepath: str) -> set:
    blacklist = set()
    if not filepath or not os.path.exists(filepath):
        return blacklist
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            bv = line.strip()
            if bv:
                blacklist.add(bv)
    return blacklist

def filter_videos(
    source_db: str,
    target_db: str,
    min_seconds: int = DEFAULT_MIN_SEC,
    max_seconds: int = DEFAULT_MAX_SEC,
    blacklist_file: str = None,
    previous_db: str = None,
):
    if not os.path.exists(source_db):
        print(f"源数据库不存在: {source_db}", file=sys.stderr)
        sys.exit(1)

    # ----- 自动处理旧结果备份与覆盖 -----
    auto_backup_path = target_db + ".prev"
    if previous_db is None and os.path.exists(target_db):
        shutil.copy2(target_db, auto_backup_path)
        previous_db = auto_backup_path
        print(f"已自动备份旧结果至 {auto_backup_path}")
    elif previous_db and os.path.abspath(target_db) == os.path.abspath(previous_db):
        print("错误：目标数据库不能与上一次结果数据库相同！", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(target_db):
        os.remove(target_db)

    blacklist = load_blacklist(blacklist_file)
    if blacklist:
        print(f"已加载黑名单 {len(blacklist)} 个 BV 号")

    src_conn = sqlite3.connect(source_db)
    src_conn.row_factory = sqlite3.Row

    # 创建目标库（注意：这里新增了 row_factory 设置）
    tgt_conn = sqlite3.connect(target_db)
    tgt_conn.row_factory = sqlite3.Row   # ⚠️ 关键修复
    create_sql = """
        CREATE TABLE IF NOT EXISTS filtered_videos (
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
            "create" TEXT,
            pubdate TEXT,
            description TEXT,
            pic TEXT,
            tag TEXT
        )
    """
    tgt_conn.execute(create_sql)
    tgt_conn.commit()

    cur = src_conn.execute("SELECT * FROM videos")
    rows = cur.fetchall()

    total = len(rows)
    matched = 0
    skipped_duration = 0
    skipped_keyword = 0
    skipped_blacklist = 0
    skipped_blocked = 0

    for row in rows:
        bvid = row["bvid"]
        if bvid in blacklist:
            skipped_blacklist += 1
            continue

        dur_str = row["duration"]
        seconds = parse_duration_to_seconds(dur_str)
        if seconds is None:
            skipped_duration += 1
            continue
        if seconds <= min_seconds or seconds >= max_seconds:
            skipped_duration += 1
            continue

        title = row["title"] or ""
        desc = row["description"] or ""
        if not (match_keywords(title) or match_keywords(desc)):
            skipped_keyword += 1
            continue

        if match_block_keywords(title) or match_block_keywords(desc):
            skipped_blocked += 1
            continue

        data = (
            row["aid"], row["bvid"], row["title"], row["author"], row["mid"],
            row["typename"], row["typeid"], row["play"], row["video_review"],
            row["danmaku"], row["review"], row["favorites"], row["coins"],
            row["likes"], row["duration"], row["create"], row["pubdate"],
            row["description"], row["pic"], row["tag"]
        )
        placeholders = ", ".join("?" for _ in data)
        insert_sql = f'INSERT OR IGNORE INTO filtered_videos (aid, bvid, title, author, mid, typename, typeid, play, video_review, danmaku, review, favorites, coins, likes, duration, "create", pubdate, description, pic, tag) VALUES ({placeholders})'
        tgt_conn.execute(insert_sql, data)
        matched += 1

    tgt_conn.commit()

    print(f"处理完成：总计 {total} 条记录")
    print(f"符合条件：{matched} 条")
    print(f"黑名单过滤：{skipped_blacklist} 条")
    print(f"时长不符合（或无法解析）：{skipped_duration} 条")
    print(f"关键词不匹配：{skipped_keyword} 条")
    print(f"屏蔽词过滤：{skipped_blocked} 条")
    print(f"结果已保存至：{os.path.abspath(target_db)}")

    # ----- 对比新增视频 -----
    if previous_db and os.path.exists(previous_db):
        try:
            prev_conn = sqlite3.connect(previous_db)
            prev_conn.row_factory = sqlite3.Row
            prev_rows = prev_conn.execute("SELECT bvid, title FROM filtered_videos").fetchall()
            prev_bvids = {row["bvid"] for row in prev_rows}
            prev_conn.close()

            # 现在 tgt_conn.row_factory = Row，所以可以使用字符串键
            cur_new = tgt_conn.execute("SELECT bvid, title FROM filtered_videos")
            new_videos = cur_new.fetchall()

            added = [v for v in new_videos if v["bvid"] not in prev_bvids]

            if added:
                print(f"\n相比上一次结果，新增 {len(added)} 个视频：")
                for v in added:
                    print(f"  {v['bvid']}  {v['title']}")
            else:
                print("\n与上一次结果相比，没有新增视频。")
        except Exception as e:
            print(f"对比上一次结果时出错: {e}", file=sys.stderr)
        finally:
            # 清理自动备份
            if previous_db == auto_backup_path and os.path.exists(auto_backup_path):
                os.remove(auto_backup_path)

    tgt_conn.close()
    src_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="从 bilibili_videos.db 中筛选满足时长与关键词的视频，可排除黑名单 BV 号"
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE_DB)
    parser.add_argument("--target", default=DEFAULT_TARGET_DB)
    parser.add_argument("--min", type=int, default=DEFAULT_MIN_SEC)
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_SEC)
    parser.add_argument("--blacklist", default=os.path.join(WORKSPACE_DIR, "blacklist.txt"))
    parser.add_argument("--previous-db", default=None)
    args = parser.parse_args()
    filter_videos(args.source, args.target, args.min, args.max,
                  args.blacklist, args.previous_db)


if __name__ == "__main__":
    main()