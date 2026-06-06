#!/usr/bin/env python3
"""
下载算分结果前 N 个视频的音频（MP3），上传网易云云盘并创建歌单
===============================================================
用法:
  python download_mp3.py <算分文件.xlsx> --top N [--ncm-playlist 歌单名]

流程:
  1. 读取算分 Excel（按最终得分降序）
  2. 取前 N 个视频
  3. 使用 yt-dlp 逐个下载音频并转为 MP3
  4. 记录到 workspace/downloaded_mp3/manifest.json
  5. 调用网易云 Node.js 脚本上传云盘 + 创建歌单
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from ncm_utils import upload_mp3s, create_playlist as ncm_create_playlist
from extract_song_name import extract_song_name, detect_artist

WORKSPACE_DIR = os.path.join(SCRIPT_DIR, "..", "workspace")
SCORE_DIR = os.path.join(SCRIPT_DIR, "..", "score")
MP3_DIR = os.path.join(WORKSPACE_DIR, "downloaded_mp3")
MANIFEST_FILE = os.path.join(MP3_DIR, "manifest.json")

COOKIE_FILE = os.path.join(WORKSPACE_DIR, "bilibili_cookies.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://www.bilibili.com",
}


def load_bilibili_cookies():
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def ensure_cookie_file(cookies):
    if not cookies:
        return None
    path = os.path.join(MP3_DIR, ".cookies.txt")
    lines = [
        "# Netscape HTTP Cookie File",
        ".bilibili.com\tTRUE\t/\tTRUE\t2147483647\tSESSDATA\t" + cookies.get("SESSDATA", ""),
        ".bilibili.com\tTRUE\t/\tTRUE\t2147483647\tbili_jct\t" + cookies.get("bili_jct", ""),
        ".bilibili.com\tTRUE\t/\tTRUE\t2147483647\tDedeUserID\t" + cookies.get("DedeUserID", ""),
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def sanitize_filename(name: str, max_len: int = 40) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"[\x00-\x1F\x7F]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"_+", "_", name).strip("_")
    if len(name) > max_len:
        name = name[:max_len].rstrip("_")
    return name or "no_title"


def write_id3_tags(mp3_path, title, artist=""):
    tmp_path = mp3_path + ".tmp_id3.mp3"
    cmd = [
        "ffmpeg", "-y", "-i", mp3_path, "-c", "copy",
        "-map_metadata", "-1",
        "-metadata", f"title={title}",
    ]
    if artist:
        cmd += ["-metadata", f"artist={artist}"]
    cmd.append(tmp_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and os.path.exists(tmp_path):
            os.replace(tmp_path, mp3_path)
        else:
            print(f"  ffmpeg 写入标签失败: {proc.stderr.strip()}")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        print(f"  写入 ID3 标签失败: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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


def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"version": 1, "entries": data}
        return data
    return {"version": 1, "entries": []}


def save_manifest(manifest):
    os.makedirs(MP3_DIR, exist_ok=True)
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def check_ytdlp():
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        print("需要 yt-dlp: pip install yt-dlp")
        sys.exit(1)


def get_video_title_direct(bvid, delay=1.5):
    """通过 B 站 API 获取视频标题（用于确认）"""
    time.sleep(delay)
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        ctx = __import__("ssl").create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = __import__("ssl").CERT_NONE
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == 0:
            return data["data"].get("title", "")
    except Exception:
        pass
    return ""


def validate_mp3(filepath: str) -> bool:
    """用 ffprobe 检测 MP3 是否为有效音频"""
    if not os.path.exists(filepath):
        return False
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", filepath],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return False
        return "audio" in proc.stdout
    except Exception:
        return False


def download_mp3(bvid, title, rank, mp3_dir, artist="", delay=3.0):
    yt_dlp = check_ytdlp()

    safe_title = sanitize_filename(title)
    filename = f"{rank:02d}_{safe_title}.mp3"
    output_path = os.path.join(mp3_dir, filename)
    temp_pattern = os.path.join(mp3_dir, f"{rank:02d}_{safe_title}.%(ext)s")

    if os.path.exists(output_path):
        print(f"  已存在，跳过: {filename}")
        if validate_mp3(output_path):
            write_id3_tags(output_path, title, artist)
            return True, output_path
        else:
            print(f"  文件损坏，重新下载")
            os.unlink(output_path)

    url = f"https://www.bilibili.com/video/{bvid}"

    cookies = load_bilibili_cookies()
    cookie_file = ensure_cookie_file(cookies)

    http_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Referer": HEADERS["Referer"],
        "Accept": HEADERS["Accept"],
        "Accept-Language": HEADERS["Accept-Language"],
        "Origin": HEADERS["Origin"],
    }

    # 按优先级尝试不同的 format，直到一个通过验证
    format_tries = ["bestaudio/best", "bestaudio", "140"]

    for attempt, fmt in enumerate(format_tries):
        if attempt > 0:
            print(f"  重试 format={fmt!r} ...")
            time.sleep(delay)

        ydl_opts = {
            "format": fmt,
            "outtmpl": temp_pattern,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "sleep_interval_requests": 1.0,
            "sleep_interval": delay,
            "http_headers": http_headers,
            "user_agent": HEADERS["User-Agent"],
            "referer": "https://www.bilibili.com",
            "extractor_args": {"bilibili": ["no_webproxy=True"]},
            "cookiefile": cookie_file,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"  下载失败 (format={fmt}): {e}")
            # 清理可能产生的残余文件
            for p in (output_path, output_path.replace(".mp3", ".m4a"), output_path.replace(".mp3", ".webm")):
                if os.path.exists(p):
                    os.unlink(p)
            continue

        # 检查是否生成文件（yt-dlp 可能输出 .m4a 或 .webm 后转 .mp3）
        if os.path.exists(output_path):
            if validate_mp3(output_path):
                write_id3_tags(output_path, title, artist)
                return True, output_path
            else:
                print(f"  文件验证失败 (format={fmt})")
                for p in (output_path, output_path.replace(".mp3", ".m4a"), output_path.replace(".mp3", ".webm")):
                    if os.path.exists(p):
                        os.unlink(p)
        else:
            print(f"  下载完成但未找到输出文件 (format={fmt})")

    print(f"  {filename} 所有 format 尝试均失败")
    return False, None


def _collect_mp3_files(manifest):
    entries = manifest.get("entries", [])
    files = []
    for entry in entries:
        fp = entry.get("filepath", "")
        if fp and os.path.exists(fp):
            files.append(fp)
    return files


def main():
    parser = argparse.ArgumentParser(
        description="下载算分结果前 N 个视频的 MP3，上传网易云并创建歌单"
    )
    parser.add_argument("score_file", nargs="?", help="算分 Excel 文件路径")
    parser.add_argument("--top", "-n", type=int, default=None, help="取前 N 个视频")
    parser.add_argument("--ncm-playlist", default=None, help="网易云歌单名称")
    parser.add_argument("--download-only", action="store_true", help="仅下载，不执行网易云操作")
    parser.add_argument("--ncm-only", action="store_true", help="仅执行网易云操作（跳过下载）")
    parser.add_argument("--cookies", default=None, help="B站 Cookie 文件路径（当前下载不需要）")
    parser.add_argument("--retag", action="store_true", help="读取 manifest 重新写入 ID3 标签（歌名+歌手）")
    args = parser.parse_args()

    if args.retag:
        manifest = load_manifest()
        entries = manifest.get("entries", [])
        count = 0
        for entry in entries:
            fp = entry.get("filepath", "")
            if fp and os.path.exists(fp):
                title = entry.get("song_name", entry.get("title", ""))
                artist = detect_artist(entry.get("title", ""))
                write_id3_tags(fp, title, artist)
                count += 1
                print(f"  {count:>3}. {os.path.basename(fp)} → title={title!r}, artist={artist!r}")
        print(f"\n已更新 {count} 个文件的 ID3 标签")
        return

    if args.ncm_only:
        manifest = load_manifest()
        mp3_files = _collect_mp3_files(manifest)
        playlist_name = args.ncm_playlist or f"周刊TOP{len(mp3_files)}"
        step = input("要执行的操作: 1=仅上传云盘  2=仅创建歌单  3=上传+创建歌单: ").strip()
        if step == "1":
            upload_mp3s(mp3_files)
        elif step == "2":
            ncm_create_playlist(playlist_name)
        elif step == "3":
            print("\n--- 上传到云盘 ---")
            upload_mp3s(mp3_files)
            print("\n--- 创建歌单 ---")
            ncm_create_playlist(playlist_name)
        else:
            print("无效选择")
        return

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
        inp = input(f"要下载前几个视频? (默认 10): ").strip()
        top_n = int(inp) if inp.isdigit() else 10
    top_n = min(top_n, len(entries))
    selected = entries[:top_n]

    print(f"\n将下载前 {top_n} 个视频的音频:")
    for i, (bvid, score, title) in enumerate(selected, 1):
        song_name = extract_song_name(title) if title else "(无标题)"
        print(f"  {i:2d}. [{bvid}] {song_name} (得分: {score:.2f})")

    confirm = input("\n确认开始下载? (y/n): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    # ---- 下载阶段 ----
    os.makedirs(MP3_DIR, exist_ok=True)
    manifest = load_manifest()

    existing_bvids = {e["bvid"] for e in manifest.get("entries", [])}

    success_count = 0
    fail_count = 0
    new_entries = []

    print(f"\n开始下载 {top_n} 个视频...")
    for i, (bvid, score, title) in enumerate(selected, 1):
        song_name = extract_song_name(title)
        print(f"\n  [{i}/{top_n}] {bvid} {song_name}")

        if bvid in existing_bvids:
            print(f"    已在 manifest 中，跳过")
            existing_entry = [e for e in manifest["entries"] if e["bvid"] == bvid][0]
            fp = existing_entry.get("filepath", "")
            if fp and os.path.exists(fp):
                write_id3_tags(fp, existing_entry.get("song_name", existing_entry["title"]), detect_artist(existing_entry["title"]))
            new_entries.append(existing_entry)
            success_count += 1
            continue

        artist = detect_artist(title)
        ok, filepath = download_mp3(bvid, song_name, i, MP3_DIR, artist=artist, delay=3.0)
        if ok:
            print(f"    OK -> {os.path.basename(filepath)}")
            success_count += 1
            entry = {
                "bvid": bvid,
                "title": title,
                "song_name": song_name,
                "score": round(score, 2),
                "rank": i,
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            new_entries.append(entry)
            existing_bvids.add(bvid)
        else:
            fail_count += 1
            print("    FAIL")

    manifest["entries"] = new_entries
    save_manifest(manifest)

    print(f"\n{'=' * 50}")
    print(f"下载完成!")
    print(f"  成功: {success_count} 个")
    print(f"  失败: {fail_count} 个")
    print(f"  Manifest: {MANIFEST_FILE}")

    if args.download_only:
        return

    # ---- 网易云操作 ----
    if success_count == 0:
        print("没有新下载的文件，跳过网易云操作")
        return

    print(f"\n{'=' * 50}")
    print("开始网易云云盘上传和歌单创建...")
    print(f"{'=' * 50}")

    playlist_name = args.ncm_playlist
    if not playlist_name:
        default_name = f"周刊TOP{top_n}"
        inp = input(f"网易云歌单名称 (默认: {default_name}): ").strip()
        playlist_name = inp if inp else default_name

    mp3_files = _collect_mp3_files(manifest)

    do_upload = input("\n是否上传到网易云云盘? (y/n, 默认 y): ").strip().lower()
    if do_upload != "n":
        print("\n--- 上传到云盘 ---")
        upload_mp3s(mp3_files)

    do_playlist = input("\n是否创建歌单并添加歌曲? (y/n, 默认 y): ").strip().lower()
    if do_playlist != "n":
        print("\n--- 创建歌单 ---")
        ncm_create_playlist(playlist_name)

    print(f"\n{'=' * 50}")
    print("全部完成!")


if __name__ == "__main__":
    main()
