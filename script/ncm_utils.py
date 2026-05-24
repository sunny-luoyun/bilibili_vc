"""
网易云音乐 Node.js 操作封装
============================
JS 脚本位于 script/netease/ 子目录中, npm 依赖自动安装
"""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NCM_DIR = os.path.join(SCRIPT_DIR, "netease")


def ensure_deps():
    """确保 Node.js 依赖已安装"""
    if not os.path.exists(NCM_DIR):
        print(f"netease 目录不存在: {NCM_DIR}")
        return False

    node_modules = os.path.join(NCM_DIR, "node_modules")
    if not os.path.exists(node_modules):
        print("正在安装网易云 Node.js 依赖 (仅首次运行需要)...")
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=NCM_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                print(f"npm install 失败: {result.stderr}")
                return False
            print("依赖安装完成")
        except Exception as e:
            print(f"npm install 异常: {e}")
            return False

    return True


def run_script(script_name, args=None, timeout=900):
    if not ensure_deps():
        return False, ""

    script_path = os.path.join(NCM_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"脚本不存在: {script_path}")
        return False, ""

    cmd = ["node", script_path]
    if args:
        cmd.extend(args)

    is_upload = script_name == "upload_to_cloud.js"
    if is_upload:
        cookie_file = os.path.join(NCM_DIR, ".ncm_cookie")
        if not os.path.exists(cookie_file):
            print("  首次使用需要扫码登录网易云，请在弹出提示后打开生成的 qrcode.png 扫码")

    print(f"  >> {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=NCM_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output_lines = []
        for line in proc.stdout:
            print(f"    {line}", end="")
            output_lines.append(line)
        proc.wait(timeout=timeout)
        return proc.returncode == 0, "".join(output_lines)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("  Node.js 脚本执行超时")
        return False, ""
    except Exception as e:
        print(f"  执行失败: {e}")
        return False, ""


def upload_mp3s(mp3_files):
    if not mp3_files:
        print("没有文件需要上传")
        return False
    print(f"上传 {len(mp3_files)} 个文件到网易云云盘...")
    return run_script("upload_to_cloud.js", mp3_files)[0]


def create_playlist(playlist_name="本周周刊"):
    print(f"创建歌单「{playlist_name}」并添加歌曲...")
    return run_script("sync_to_playlist.js", [playlist_name])[0]


def delete_playlist():
    print("删除歌单...")
    return run_script("delete_playlist.js")[0]


def delete_cloud_songs():
    print("删除云盘歌曲...")
    return run_script("delete_uploaded.js")[0]
