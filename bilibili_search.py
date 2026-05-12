#!/usr/bin/env python3
"""
Bilibili 分区视频搜索脚本
=========================
基于 Bilibili 开放接口文档 (https://github.com/fython/BilibiliAPIDocs) 学习编写。

使用现代 Bilibili 公开 API（无需 appKey/sign），支持：
  1. 按分区(tid)列出最新视频 / 热门视频
  2. 在指定分区内按关键词搜索视频
  3. 多种排序方式
  4. 分页获取
  5. 详细视频信息展示
  6. CSV/JSON 导出

参考文档中的 API.list.md 和 API.search.md 接口设计思路，
改为使用当前有效的 Bilibili Web API 端点。
"""

import csv
import json
import os
import sys
import time
import ssl
import gzip
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

# ============================================================
# Bilibili 分区 ID 对照表（一级分区 + 主要二级分区）
# 来源：Bilibili 官方分区结构
# ============================================================
PARTITION_MAP = {
    # 一级分区
    1: "动画",
    13: "番剧",
    167: "国创",
    3: "音乐",
    129: "舞蹈",
    4: "游戏",
    36: "知识",
    188: "科技",
    234: "运动",
    223: "汽车",
    160: "生活",
    211: "美食",
    217: "动物圈",
    119: "鬼畜",
    155: "时尚",
    5: "娱乐",
    181: "影视",
    177: "纪录片",
    23: "电影",
    11: "电视剧",
    # 二级分区 - 动画
    24: "MAD·AMV",
    25: "MMD·3D",
    47: "短片·手书·配音",
    86: "特摄",
    27: "动画综合",
    # 二级分区 - 音乐
    28: "原创音乐",
    31: "翻唱",
    30: "VOCALOID·UTAU",
    59: "演奏",
    29: "MV",
    130: "音乐现场",
    243: "音乐教学",
    54: "音乐综合",
    # 二级分区 - 游戏
    17: "单机游戏",
    171: "电子竞技",
    172: "手机游戏",
    65: "网络游戏",
    173: "桌游棋牌",
    121: "GMV",
    136: "音游",
    # 二级分区 - 知识
    201: "科学科普",
    124: "社科人文",
    207: "财经",
    208: "校园学习",
    209: "职业职场",
    122: "野生技能协会",
    # 二级分区 - 科技
    95: "数码",
    230: "软件应用",
    231: "计算机技术",
    232: "极客DIY",
    233: "科工机械",
    # 二级分区 - 生活
    138: "搞笑",
    21: "日常",
    76: "美食圈",
    75: "动物圈",
    161: "手工",
    162: "绘画",
    163: "运动",
    174: "生活其他",
    # 二级分区 - 鬼畜
    22: "鬼畜调教",
    26: "音MAD",
    126: "人力VOCALOID",
    216: "鬼畜剧场",
    127: "鬼畜教程演示",
    # 二级分区 - 时尚
    157: "美妆",
    158: "服饰",
    164: "健身",
    159: "时尚资讯",
    252: "时尚潮流",
    # 二级分区 - 娱乐
    71: "综艺",
    241: "娱乐杂谈",
    242: "粉丝创作",
    137: "明星",
    131: "Korea",
    # 二级分区 - 影视
    182: "影视杂谈",
    183: "影视剪辑",
    85: "短片",
    184: "预告·资讯",
    # 二级分区 - 舞蹈
    20: "宅舞",
    198: "街舞",
    199: "明星舞蹈",
    200: "中国舞",
    255: "舞蹈综合",
    256: "舞蹈教程",
    # 二级分区 - 美食
    212: "美食制作",
    213: "美食侦探",
    214: "美食测评",
    215: "田园美食",
    254: "美食搬运",
    # 二级分区 - 动物圈
    218: "喵星人",
    219: "汪星人",
    220: "动物其他",
    221: "野生动物",
    222: "爬宠",
}

# 反向映射：分区名称 → tid
PARTITION_NAME_TO_ID = {v: k for k, v in PARTITION_MAP.items()}


@dataclass
class VideoInfo:
    """视频信息数据结构"""
    aid: int
    bvid: str
    title: str
    author: str
    mid: int
    typename: str
    typeid: int
    play: int
    video_review: int           # 弹幕数
    danmaku: int                # 弹幕数(别名)
    review: int                 # 评论数
    favorites: int              # 收藏数
    coins: int                  # 硬币数
    likes: int                  # 点赞数
    duration: str               # 时长
    create: str                 # 发布日期
    description: str            # 简介
    pic: str                    # 封面图URL
    tag: str = ""               # 标签

    @classmethod
    def from_newlist(cls, item: dict) -> "VideoInfo":
        """从 newlist 接口返回的数据构建"""
        stat = item.get("stat", {})

        # 时长转换：秒 → mm:ss 或 hh:mm:ss
        duration_sec = stat.get("duration", item.get("duration", 0))
        if isinstance(duration_sec, str):
            duration_str = duration_sec
        else:
            if duration_sec >= 3600:
                duration_str = f"{duration_sec // 3600}:{(duration_sec % 3600) // 60:02d}:{duration_sec % 60:02d}"
            else:
                duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"

        return cls(
            aid=item.get("aid", 0),
            bvid=item.get("bvid", ""),
            title=_clean_title(item.get("title", "")),
            author=item.get("owner", {}).get("name", ""),
            mid=item.get("owner", {}).get("mid", 0),
            typename=item.get("tname", ""),
            typeid=item.get("tid", 0),
            play=stat.get("view", 0),
            video_review=stat.get("danmaku", 0),
            danmaku=stat.get("danmaku", 0),
            review=stat.get("reply", 0),
            favorites=stat.get("favorite", 0),
            coins=stat.get("coin", 0),
            likes=stat.get("like", 0),
            duration=duration_str,
            create=datetime.fromtimestamp(item.get("pubdate", 0)).strftime("%Y-%m-%d %H:%M"),
            description=item.get("desc", ""),
            pic=item.get("pic", ""),
        )

    @classmethod
    def from_search(cls, item: dict) -> "VideoInfo":
        """从 search/type 接口返回的数据构建"""
        duration_str = str(item.get("duration", "0:0"))
        # 搜索接口 duration 格式为 "分钟:秒" (如 "23:14")
        # 保持原样

        return cls(
            aid=item.get("aid", 0),
            bvid=item.get("bvid", ""),
            title=_clean_title(item.get("title", "")),
            author=item.get("author", ""),
            mid=item.get("mid", 0),
            typename=item.get("typename", ""),
            typeid=item.get("typeid", 0),
            play=item.get("play", 0),
            video_review=item.get("video_review", 0),
            danmaku=item.get("danmaku", 0),
            review=item.get("review", 0),
            favorites=item.get("favorites", 0),
            coins=item.get("coins", 0),
            likes=item.get("like", 0),
            duration=duration_str,
            create=datetime.fromtimestamp(item.get("pubdate", 0)).strftime("%Y-%m-%d %H:%M"),
            description=item.get("description", ""),
            pic=item.get("pic", ""),
            tag=item.get("tag", ""),
        )


def _clean_title(title: str) -> str:
    """清理标题中的 XML/HTML 标签（搜索接口可能返回带标签的）"""
    import re
    return re.sub(r"<[^>]+>", "", title)


class BilibiliClient:
    """
    Bilibili 分区视频搜索客户端

    基于参考文档中 API.list.md (tid分区+排序+分页) 和 API.search.md (关键词搜索)
    的设计思路，使用当前有效的 Bilibili Web API 端点实现。
    """

    BASE_URL = "https://api.bilibili.com/x/web-interface"

    # 默认请求头（遵循文档要求设置合理的 UserAgent）
    # 请求头：参照文档要求设置合理的 UserAgent，补充反爬所需的 headers
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }

    def __init__(self, timeout: int = 15, delay: float = 0.5, verify_ssl: bool = True):
        """
        Args:
            timeout: 请求超时秒数
            delay: 每次请求间隔（秒），避免触发频率限制（文档警告 -503 调用速度过快）
            verify_ssl: 是否验证 SSL 证书
        """
        self.timeout = timeout
        self.delay = delay
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            self._ssl_ctx = ssl.create_default_context()
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ssl_ctx = None
        self._wbi_keys = None  # (img_key, sub_key) 缓存

    # ----------------------------------------------------------
    # WBI 签名
    # ----------------------------------------------------------

    def _get_wbi_keys(self) -> tuple:
        """获取 WBI 签名所需的 img_key 和 sub_key"""
        if self._wbi_keys is not None:
            return self._wbi_keys

        # nav 接口即使未登录也会返回 wbi_img
        nav_url = "https://api.bilibili.com/x/web-interface/nav"
        nav_data = self._request_raw(nav_url, {})
        if nav_data and "data" in nav_data:
            wbi_img = nav_data["data"].get("wbi_img")
            if wbi_img:
                img_key = wbi_img["img_url"].rsplit("/", 1)[1].split(".")[0]
                sub_key = wbi_img["sub_url"].rsplit("/", 1)[1].split(".")[0]
                self._wbi_keys = (img_key, sub_key)
                return self._wbi_keys

        return ("", "")

    @staticmethod
    def _get_mix_key(img_key: str, sub_key: str) -> str:
        """混合 img_key 和 sub_key：拼接后取偶数位 + 奇数位，再取前32字符"""
        concat = img_key + sub_key
        even = "".join(concat[i] for i in range(0, len(concat), 2))
        odd = "".join(concat[i] for i in range(1, len(concat), 2))
        return (even + odd)[:32]

    def _sign_wbi(self, params: dict) -> dict:
        """对参数进行 WBI 签名，返回添加了 w_rid 和 wts 的新参数字典"""
        img_key, sub_key = self._get_wbi_keys()
        if not img_key:
            return params

        mix_key = self._get_mix_key(img_key, sub_key)

        # 复制参数并添加时间戳
        signed = dict(params)
        signed["wts"] = str(int(time.time()))

        # 按 key 排序，对值做 URL 编码后拼接
        from urllib.parse import quote as _uriquote
        keys = sorted(signed.keys())
        query = "&".join(
            f"{k}={_uriquote(str(signed[k]), safe='')}" for k in keys
        )

        # MD5
        w_rid = hashlib.md5((query + mix_key).encode()).hexdigest()
        signed["w_rid"] = w_rid
        return signed

    def _request_with_wbi(self, url: str, params: dict, data_key: str = "") -> Optional[dict]:
        """带 WBI 签名的请求"""
        signed_params = self._sign_wbi(params)
        return self._request(url, signed_params, data_key=data_key)

    # ----------------------------------------------------------
    # 核心 API
    # ----------------------------------------------------------

    def get_newlist(
        self,
        tid: int,
        page: int = 1,
        page_size: int = 30,
        order: str = "pubdate",
    ) -> dict:
        """
        获取分区最新/热门视频列表（对应文档 API.list.md 的设计）

        使用端点: /x/web-interface/newlist?rid={tid}&type=0&pn={page}&ps={page_size}

        Args:
            tid: 分区ID (参考 PARTITION_MAP)
            page: 页码（从1开始）
            page_size: 每页数量 (1-50)
            order: 排序方式
                - pubdate: 按发布时间 (默认)
                - click: 按播放量
                - stow: 按收藏数
                - coin: 按硬币数
                - dm: 按弹幕数
                - likes: 按点赞数

        Returns:
            {"videos": [...], "total": int, "page": int, "page_size": int}
        """
        params = {
            "rid": tid,
            "type": 0,
            "pn": page,
            "ps": min(page_size, 50),
        }
        url = f"{self.BASE_URL}/newlist"
        data = self._request(url, params, data_key="data")

        videos = []
        if data and "archives" in data:
            for item in data["archives"]:
                try:
                    videos.append(VideoInfo.from_newlist(item))
                except Exception as e:
                    print(f"  [警告] 解析视频项失败: {e}", file=sys.stderr)

        return {
            "videos": videos,
            "total": len(videos),
            "page": page,
            "page_size": page_size,
            "partition_name": PARTITION_MAP.get(tid, str(tid)),
        }

    def get_ranking(
        self,
        tid: int = 0,
        day: int = 3,
    ) -> dict:
        """
        获取分区排行榜（文档 API.list.md 中的 hot/click 排序思路）

        使用端点: /x/web-interface/ranking/v2?rid={tid}&type=all

        Args:
            tid: 分区ID (0=全站)
            day: 时间范围 (1=昨日, 3=三日, 7=周)
                  注: 该参数可能由 type 参数控制，此处保留但仅作参考

        Returns:
            {"videos": [...], "partition_name": str}
        """
        params = {
            "rid": tid,
            "type": "all",
        }
        url = f"{self.BASE_URL}/ranking/v2"
        data = self._request(url, params, data_key="data")

        videos = []
        if data and "list" in data:
            for item in data["list"]:
                try:
                    videos.append(VideoInfo.from_newlist(item))
                except Exception as e:
                    print(f"  [警告] 解析视频项失败: {e}", file=sys.stderr)

        return {
            "videos": videos,
            "total": len(videos),
            "partition_name": PARTITION_MAP.get(tid, "全站" if tid == 0 else str(tid)),
        }

    def search(
        self,
        keyword: str,
        tid: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        order: str = "",
        duration: str = "",
    ) -> dict:
        """
        在指定分区或全站搜索视频（对应文档 API.search.md 的设计）

        使用端点: /x/web-interface/search/type/v2?search_type=video

        Args:
            keyword: 搜索关键词
            tid: 分区ID (None=全站搜索)
            page: 页码
            page_size: 每页数量 (1-50)
            order: 排序方式
                - "" (空字符串): 默认/综合排序
                - "pubdate": 按发布日期倒序
                - "senddate": 按修改日期倒序
                - "click": 按点击量
                - "dm": 按弹幕数
                - "stow": 按收藏数
                - "scores": 按评论数
            duration: 时长筛选 (0=全部, 1=<10min, 2=10-30min, 3=30-60min, 4=>60min)

        Returns:
            {"videos": [...], "total": int, "page": int, "page_size": int, "keywords": [...]}
        """
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": min(page_size, 50),
        }
        if tid is not None:
            params["category_id"] = tid
        if order:
            params["order"] = order
        if duration:
            params["duration"] = duration

        url = f"{self.BASE_URL}/search/type"
        data = self._request_with_wbi(url, params, data_key="data")

        videos = []
        total = 0
        suggest_keywords = []

        if data:
            total = data.get("numResults", 0)
            if "result" in data:
                for item in data["result"]:
                    try:
                        videos.append(VideoInfo.from_search(item))
                    except Exception as e:
                        print(f"  [警告] 解析搜索结果项失败: {e}", file=sys.stderr)

            # 搜索建议关键词
            suggest_keywords = []
            sk = data.get("suggest_keyword", "")
            if isinstance(sk, str) and sk:
                # suggest_keyword 可能直接是推荐词字符串
                suggest_keywords = [sk]
            elif isinstance(sk, list):
                suggest_keywords = sk

        partition_display = (
            PARTITION_MAP.get(tid, f"分区{tid}") if tid else "全站"
        )
        return {
            "videos": videos,
            "total": total,
            "page": page,
            "page_size": page_size,
            "partition_name": partition_display,
            "keyword": keyword,
            "suggest_keywords": suggest_keywords,
        }

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _request(self, url: str, params: dict, data_key: str = "") -> Optional[dict]:
        """
        发送 HTTP GET 请求并解析 JSON 响应

        文档要求:
        - 只支持 GET 方法
        - 必须设置 UserAgent
        - UTF-8 编码
        """
        time.sleep(self.delay)

        full_url = url + "?" + urlencode(params)
        req = Request(full_url, headers=self.HEADERS)

        try:
            ctx = self._ssl_ctx
            resp = urlopen(req, timeout=self.timeout, context=ctx)
            raw_bytes = resp.read()
            # 处理 gzip 压缩：检查 Content-Encoding 或检测魔数
            content_encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" in content_encoding or raw_bytes[:2] == b"\x1f\x8b":
                try:
                    raw_bytes = gzip.decompress(raw_bytes)
                except Exception:
                    pass  # 如果解压失败，使用原始数据
            raw = raw_bytes.decode("utf-8")
            result = json.loads(raw)

            # 检查 API 业务状态码
            code = result.get("code", -1)
            if code != 0:
                msg = result.get("message", "未知错误")
                print(f"  [API错误] code={code}, message={msg}", file=sys.stderr)
                return None

            if data_key:
                return result.get(data_key)
            return result.get("data")

        except HTTPError as e:
            print(f"  [错误] HTTP {e.code}: {full_url[:80]}...", file=sys.stderr)
        except URLError as e:
            print(f"  [错误] URL错误: {e.reason}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"  [错误] 响应不是合法的 JSON", file=sys.stderr)
        except Exception as e:
            print(f"  [错误] {e}", file=sys.stderr)

        return None

    def _request_raw(self, url: str, params: dict) -> Optional[dict]:
        """发送请求并返回原始 JSON 字典，不检查业务 code"""
        time.sleep(self.delay)

        full_url = url + "?" + urlencode(params)
        req = Request(full_url, headers=self.HEADERS)

        try:
            ctx = self._ssl_ctx
            resp = urlopen(req, timeout=self.timeout, context=ctx)
            raw_bytes = resp.read()
            content_encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" in content_encoding or raw_bytes[:2] == b"\x1f\x8b":
                try:
                    raw_bytes = gzip.decompress(raw_bytes)
                except Exception:
                    pass
            raw = raw_bytes.decode("utf-8")
            return json.loads(raw)

        except HTTPError as e:
            print(f"  [错误] HTTP {e.code}: {full_url[:80]}...", file=sys.stderr)
        except URLError as e:
            print(f"  [错误] URL错误: {e.reason}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"  [错误] 响应不是合法的 JSON", file=sys.stderr)
        except Exception as e:
            print(f"  [错误] {e}", file=sys.stderr)

        return None


# ============================================================
# 工具函数
# ============================================================

def print_video_list(videos: list[VideoInfo], show_index: bool = True):
    """格式化打印视频列表"""
    if not videos:
        print("  (无结果)")
        return

    for i, v in enumerate(videos, 1):
        idx = f"{i:3d}." if show_index else ""
        print(
            f"  {idx} [{v.bvid}] {v.title[:50]:50s}"
        )
        print(
            f"      UP主: {v.author:<15s} "
            f"播放: {_fmt_num(v.play):>8s}  "
            f"弹幕: {_fmt_num(v.danmaku):>6s}  "
            f"时长: {v.duration}"
        )
        print(
            f"      分类: {v.typename:<10s}  "
            f"点赞: {_fmt_num(v.likes):>8s}  "
            f"收藏: {_fmt_num(v.favorites):>6s}  "
            f"日期: {v.create}"
        )
        if v.description:
            desc = v.description[:60].replace("\n", " ")
            print(f"      简介: {desc}")
        print()


def _fmt_num(n: int) -> str:
    """格式化数字，万以上显示为 x.x万"""
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


def export_csv(videos: list[VideoInfo], filename: str):
    """导出为 CSV 文件"""
    if not videos:
        print("  [提示] 无数据可导出")
        return

    fieldnames = [
        "aid", "bvid", "title", "author", "typename",
        "play", "danmaku", "review", "favorites", "coins", "likes",
        "duration", "create", "description", "pic", "tag",
    ]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in videos:
            writer.writerow(asdict(v))

    print(f"  [导出] 已保存 {len(videos)} 条记录到 {filename}")


def export_json(videos: list[VideoInfo], filename: str):
    """导出为 JSON 文件"""
    if not videos:
        print("  [提示] 无数据可导出")
        return

    data = [asdict(v) for v in videos]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  [导出] 已保存 {len(videos)} 条记录到 {filename}")


def list_partitions(filter_keyword: str = ""):
    """列出可用分区"""
    print("\nBilibili 分区列表:")
    print("=" * 50)

    # 先列出一级分区
    primary = {
        k: v for k, v in PARTITION_MAP.items()
        if k in [1, 13, 167, 3, 129, 4, 36, 188, 234, 223,
                 160, 211, 217, 119, 155, 5, 181, 177, 23, 11]
    }
    # 二级分区
    sub = {k: v for k, v in PARTITION_MAP.items() if k not in primary}

    if filter_keyword:
        fl = filter_keyword.lower()
        primary = {k: v for k, v in primary.items() if fl in v.lower() or fl in str(k)}
        sub = {k: v for k, v in sub.items() if fl in v.lower() or fl in str(k)}

    print("  【一级分区】")
    for tid in sorted(primary.keys()):
        print(f"    {tid:4d}  {primary[tid]}")

    if not filter_keyword:
        print("\n  【二级分区（部分）】")
        for tid in sorted(sub.keys()):
            print(f"    {tid:4d}  {sub[tid]}")

    print(f"\n  {len(PARTITION_MAP)} 个分区可用")


# ============================================================
# 主入口 & CLI
# ============================================================

SEARCH_ORDER_HELP = """
排序方式 (order):
  留空/空字符串 = 综合排序
  pubdate     = 按发布时间
  click       = 按播放量
  dm          = 按弹幕数
  stow        = 按收藏数
  scores      = 按评论数
  senddate    = 按修改日期
"""

NEWLIST_ORDER_HELP = """
排序方式 (order):
  pubdate     = 按发布时间 (默认)
  click       = 按播放量
  stow        = 按收藏数
  coin        = 按硬币数
  dm          = 按弹幕数
  likes       = 按点赞数
"""


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Bilibili 分区视频搜索工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 列出所有分区
  python bilibili_search.py --list-partitions

  # 搜索分区
  python bilibili_search.py --list-partitions --filter 知识

  # 获取分区最新视频
  python bilibili_search.py --tid 36 --mode newlist --pages 2

  # 获取分区排行榜
  python bilibili_search.py --tid 4 --mode ranking

  # 全站搜索 (默认综合排序)
  python bilibili_search.py --search "机器学习"

  # 在指定分区内搜索并按播放量排序
  python bilibili_search.py --search "教程" --tid 36 --order click

  # 搜索并导出为 CSV
  python bilibili_search.py --search "MAD" --tid 24 --export mad_results.csv

  # 获取多页 (自动遍历)
  python bilibili_search.py --tid 3 --mode newlist --pages 3 --page-size 20

参考文献:
  https://github.com/fython/BilibiliAPIDocs
        """,
    )

    # 模式选择
    parser.add_argument("--tid", type=int, default=None,
                        help="分区ID (使用 --list-partitions 查看)")
    parser.add_argument("--mode", choices=["newlist", "ranking", "search"],
                        default="newlist",
                        help="操作模式 (默认: newlist)")
    parser.add_argument("--search", type=str, default="",
                        help="搜索关键词 (mode=search 时使用)")

    # 分区列表
    parser.add_argument("--list-partitions", action="store_true",
                        help="列出所有可用分区及ID")
    parser.add_argument("--filter", type=str, default="",
                        help="过滤分区列表的关键词")

    # 分页 & 排序
    parser.add_argument("--page", type=int, default=1,
                        help="起始页码 (默认: 1)")
    parser.add_argument("--pages", type=int, default=1,
                        help="获取的页数 (默认: 1)")
    parser.add_argument("--page-size", type=int, default=30,
                        help="每页数量 (默认: 30, 最大: 50)")
    parser.add_argument("--order", type=str, default="",
                        help=f"排序方式 (见下方)")

    # 输出控制
    parser.add_argument("--export", type=str, default="",
                        help="导出为 CSV/JSON 文件路径 (根据扩展名自动判定)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="请求间隔秒数 (默认: 0.5, 文档警告不可滥用)")
    parser.add_argument("--no-ssl-check", action="store_true",
                        help="跳过 SSL 证书验证 (用于某些本地环境)")
    parser.add_argument("--no-print", action="store_true",
                        help="不打印结果到终端")

    args = parser.parse_args()

    # ---- 分区列表模式 ----
    if args.list_partitions:
        list_partitions(args.filter)
        return

    # ---- 获取视频模式 ----
    client = BilibiliClient(delay=args.delay, verify_ssl=not args.no_ssl_check)

    all_videos: list[VideoInfo] = []
    total_found = 0
    partition_name = ""

    for p in range(args.page, args.page + args.pages):
        if args.pages > 1:
            print(f"\n--- 第 {p} 页 ---")

        if args.mode == "search":
            if not args.search:
                print("[错误] search 模式需要 --search 参数")
                return
            result = client.search(
                keyword=args.search,
                tid=args.tid,
                page=p,
                page_size=args.page_size,
                order=args.order,
            )
        elif args.mode == "ranking":
            if p > args.page:
                print("[提示] ranking 接口不支持分页，仅获取第1页")
                break
            result = client.get_ranking(
                tid=args.tid or 0,
                day=3,
            )
        else:  # newlist
            result = client.get_newlist(
                tid=args.tid or 0,
                page=p,
                page_size=args.page_size,
                order=args.order or "pubdate",
            )

        videos = result.get("videos", [])
        all_videos.extend(videos)
        partition_name = result.get("partition_name", "")
        total_found = result.get("total", 0)

        if not videos:
            break

    # ---- 结果展示 ----
    mode_label = {
        "search": f"搜索「{args.search}」",
        "ranking": "排行榜",
        "newlist": "最新视频",
    }.get(args.mode, args.mode)

    print(f"\n{'=' * 60}")
    print(f"  {mode_label} | 分区: {partition_name}")
    if args.mode == "search":
        suggest = result.get("suggest_keywords", [])
        if suggest:
            print(f"  推荐搜索: {' / '.join(suggest[:5])}")
    print(f"  共获取 {len(all_videos)} 条视频")
    if total_found:
        print(f"  总计结果: {total_found}")
    print(f"{'=' * 60}\n")

    if not args.no_print:
        print_video_list(all_videos)

    # ---- 导出 ----
    if args.export:
        ext = os.path.splitext(args.export)[1].lower()
        if ext == ".csv":
            export_csv(all_videos, args.export)
        elif ext == ".json":
            export_json(all_videos, args.export)
        else:
            # 自动判度：有逗号分隔则写入 CSV
            export_csv(all_videos, args.export)


if __name__ == "__main__":
    main()
