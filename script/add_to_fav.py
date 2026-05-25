#!/usr/bin/env python3
"""
将算分结果文件中的前 N 个视频添加到 B站收藏夹
=================================================
用法:
  python add_to_fav.py <算分文件.xlsx> --top N [--folder 收藏夹名]

流程:
  1. 读取算分 Excel 文件（按最终得分降序排列）
  2. 取前 N 个视频的 bvid
  3. 将 bvid 转换为 aid
  4. 创建目标收藏夹
  5. 逐个添加视频到收藏夹
"""

import argparse
import json
import os
import sys
import time
import ssl
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "..", "workspace")
SCORE_DIR = os.path.join(SCRIPT_DIR, "..", "score")
COOKIE_FILE = os.path.join(WORKSPACE_DIR, "bilibili_cookies.json")

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def load_cookies(path=None):
    path = path or COOKIE_FILE
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if cookies.get("SESSDATA") and cookies.get("bili_jct"):
            print(f"已加载 Cookie: {path}")
            return cookies

    print("\n请提供 B站登录 Cookie 信息（用于身份认证）")
    print("获取方法: 浏览器登录 bilibili.com → F12 → Application → Cookies → 复制以下值\n")
    sessdata = input("SESSDATA: ").strip()
    bili_jct = input("bili_jct (即 csrf): ").strip()
    dedeuserid = input("DedeUserID (可选，直接回车跳过): ").strip()

    if not sessdata or not bili_jct:
        print("SESSDATA 和 bili_jct 为必填项")
        sys.exit(1)

    cookies = {
        "SESSDATA": sessdata,
        "bili_jct": bili_jct,
        "DedeUserID": dedeuserid or "",
    }

    save = input(f"\n是否保存到 {path} 以便下次使用? (y/n): ").strip().lower()
    if save == "y":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"已保存至: {path}")

    return cookies


def make_cookie_header(cookies):
    parts = []
    for key in ("SESSDATA", "bili_jct", "DedeUserID"):
        if cookies.get(key):
            parts.append(f"{key}={cookies[key]}")
    return "; ".join(parts)


def build_headers(cookies, content_type=None):
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = make_cookie_header(cookies)
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _request(url, data=None, headers=None, method="GET", timeout=15):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"  [HTTP {e.code}] {body}")
    except urllib.error.URLError as e:
        print(f"  [网络错误] {e.reason}")
    except json.JSONDecodeError:
        print("  [错误] 响应不是合法 JSON")
    except Exception as e:
        print(f"  [错误] {e}")
    return None


def bvid_to_aid(bvid, cookies, delay=1.0):
    time.sleep(delay)
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = build_headers(cookies)
    result = _request(url, headers=headers)
    if result and result.get("code") == 0:
        return result["data"]["aid"]
    msg = result.get("message", "未知错误") if result else "无响应"
    print(f"(aid转换失败: {msg})")
    return None


def get_created_folders(cookies, delay=1.0):
    time.sleep(delay)
    url = "https://api.bilibili.com/x/v3/fav/folder/created/list-all"
    params = {}
    if cookies.get("DedeUserID"):
        params["up_mid"] = cookies["DedeUserID"]
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = build_headers(cookies)
    result = _request(url, headers=headers)
    if result and result.get("code") == 0:
        return result.get("data", {}).get("list", [])
    return []


def create_folder(folder_name, cookies, delay=1.0):
    time.sleep(delay)
    url = "https://api.bilibili.com/x/v3/fav/folder/add"
    params = {
        "title": folder_name,
        "privacy": 0,
        "csrf": cookies["bili_jct"],
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    headers = build_headers(cookies, content_type="application/x-www-form-urlencoded")
    result = _request(url, data=data, headers=headers, method="POST")
    if result and result.get("code") == 0:
        return result["data"].get("id") or result["data"].get("media_id")
    msg = result.get("message", "") if result else ""
    print(f"  (创建失败: {msg})")
    return None


def add_to_folder(aid, folder_id, cookies, delay=1.5):
    time.sleep(delay)
    url = "https://api.bilibili.com/x/v3/fav/resource/deal"
    params = {
        "rid": aid,
        "type": 2,
        "add_media_ids": folder_id,
        "csrf": cookies["bili_jct"],
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    headers = build_headers(cookies, content_type="application/x-www-form-urlencoded")
    result = _request(url, data=data, headers=headers, method="POST")
    if result and result.get("code") == 0:
        return True
    msg = result.get("message", "未知错误") if result else "无响应"
    print(f"(收藏失败: {msg})")
    return False


def read_scored_excel(filepath):
    try:
        import openpyxl
    except ImportError:
        print("需要 openpyxl: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        print("Excel 文件没有数据行")
        sys.exit(1)

    headers = [str(h) for h in rows[0]]

    col_bvid = col_score = col_title = None
    for i, h in enumerate(headers):
        if h == "bvid":
            col_bvid = i
        elif h in ("最终得分", "final_score"):
            col_score = i
        elif h == "title":
            col_title = i

    if col_bvid is None:
        print("Excel 中找不到 bvid 列")
        sys.exit(1)

    entries = []
    for row in rows[1:]:
        bvid = row[col_bvid] if col_bvid < len(row) else None
        if not bvid or str(bvid).strip() == "":
            continue
        score = float(row[col_score]) if col_score is not None and row[col_score] is not None else 0.0
        title = str(row[col_title]) if col_title is not None and row[col_title] is not None else ""
        entries.append((str(bvid).strip(), score, title))

    entries.sort(key=lambda x: x[1], reverse=True)
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="将算分结果前 N 个视频加入 B站收藏夹"
    )
    parser.add_argument("score_file", nargs="?", help="算分 Excel 文件路径")
    parser.add_argument("--top", "-n", type=int, default=None, help="取前 N 个视频")
    parser.add_argument("--folder", "-f", default=None, help="收藏夹名称（将新建）")
    parser.add_argument("--cookies", default=None, help="Cookie 配置文件路径")
    args = parser.parse_args()

    score_file = args.score_file
    if not score_file:
        score_files = [f for f in os.listdir(SCORE_DIR) if f.endswith(".xlsx")]
        if not score_files:
            print(f"{SCORE_DIR} 下没有算分文件，请先运行算分或直接指定文件路径")
            sys.exit(1)
        print("\n可用算分文件:")
        for i, f in enumerate(score_files, 1):
            size = os.path.getsize(os.path.join(SCORE_DIR, f))
            print(f"  {i}. {f} ({size / 1024:.1f} KB)")
        sel = input("请选择 (输入序号): ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(score_files):
            score_file = os.path.join(SCORE_DIR, score_files[int(sel) - 1])
        else:
            print("无效选择")
            sys.exit(1)

    if not os.path.exists(score_file):
        print(f"文件不存在: {score_file}")
        sys.exit(1)

    print(f"\n读取算分文件: {score_file}")
    entries = read_scored_excel(score_file)
    print(f"  共 {len(entries)} 条视频记录")

    top_n = args.top
    if top_n is None:
        inp = input(f"要收藏前几个视频? (默认 10): ").strip()
        top_n = int(inp) if inp.isdigit() else 10
    top_n = min(top_n, len(entries))
    selected = entries[:top_n]

    print(f"\n将收藏前 {top_n} 个视频:")
    for i, (bvid, score, title) in enumerate(selected, 1):
        title_short = title[:50] if title else "(无标题)"
        print(f"  {i:2d}. [{bvid}] {title_short} (得分: {score:.2f})")

    confirm = input("\n确认继续? (y/n): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    cookies = load_cookies(args.cookies)

    folder_name = args.folder
    if not folder_name:
        default_name = f"周刊TOP{top_n}"
        inp = input(f"收藏夹名称 (新建，默认: {default_name}): ").strip()
        folder_name = inp if inp else default_name

    print(f"\n创建收藏夹: {folder_name}")
    folder_id = create_folder(folder_name, cookies)
    if folder_id is None:
        print("  尝试查找现有同名收藏夹...")
        folders = get_created_folders(cookies)
        for f in folders:
            if f.get("title") == folder_name:
                folder_id = f.get("id") or f.get("media_id")
                print(f"  找到现有收藏夹: {folder_name} (id={folder_id})")
                break
        if folder_id is None:
            print("创建/获取收藏夹失败")
            sys.exit(1)
    else:
        print(f"  创建成功 (media_id={folder_id})")

    print(f"\n开始添加 {top_n} 个视频到收藏夹「{folder_name}」")
    success = []
    failed = []

    for i, (bvid, score, title) in enumerate(reversed(selected), 1):
        title_short = title[:40] if title else ""
        print(f"  [{i}/{top_n}] {bvid} {title_short}", end=" ")
        sys.stdout.flush()

        aid = bvid_to_aid(bvid, cookies)
        if aid is None:
            failed.append((bvid, "aid转换失败"))
            continue

        if add_to_folder(aid, folder_id, cookies):
            print(" OK")
            success.append(bvid)
        else:
            failed.append((bvid, "收藏失败"))

    print(f"\n{'=' * 50}")
    print(f"操作完成!")
    print(f"  成功: {len(success)} 个")
    print(f"  失败: {len(failed)} 个")
    if failed:
        print(f"\n失败列表:")
        for bvid, reason in failed:
            print(f"    - [{bvid}] {reason}")
    if success:
        print(f"\n收藏夹: {folder_name}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
