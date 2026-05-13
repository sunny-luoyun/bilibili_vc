#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
B站工作流总控脚本
=================
整合采集、筛选、切片、云服务器创建、上传下载、合并、算分、删除实例等步骤。
支持自定义切片份数、服务器数量。
"""

import os
import sys
import subprocess
import sqlite3
import time
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional

# ---------- 全局配置 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 脚本路径（确保与 main.py 同目录）
SCRIPTS = {
    "crawl_db": "crawl_to_db.py",
    "filter": "filter.py",
    "slice_merge": "slice_and_merge.py",
    "start_server": "startserver.py",
    "check_instance": "check_instance.py",
    "upload": "upload.py",
    "download": "download.py",
    "score_diff": "score_diff.py",
    "bv_fetcher": "bv_fetcher.py",
}

# 默认文件名
DEFAULT_SOURCE_DB = "bilibili_videos.db"
DEFAULT_FILTERED_DB = "filtered_videos.db"
DEFAULT_SLICE_PREFIX = "slice_"

# ---------- 辅助函数 ----------
def run_cmd(cmd: List[str], cwd=None) -> bool:
    """执行外部命令，返回是否成功"""
    print(f"\n>>> 执行命令: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, cwd=cwd or SCRIPT_DIR, check=False)
        if proc.returncode != 0:
            print(f"命令执行失败，返回码 {proc.returncode}")
            return False
        return True
    except Exception as e:
        print(f"执行异常: {e}")
        return False

def get_bv_list_from_db(db_path: str) -> List[str]:
    """从 SQLite 数据库的 filtered_videos 或 videos 表中读取 BV 号列表"""
    if not os.path.exists(db_path):
        print(f"数据库不存在: {db_path}")
        return []
    conn = sqlite3.connect(db_path)
    # 尝试 filtered_videos 表，若无则回退到 videos
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('filtered_videos', 'videos')"
    ).fetchall()
    table_name = None
    for (tbl,) in tables:
        if tbl == "filtered_videos":
            table_name = tbl
            break
    if not table_name and tables:
        table_name = tables[0][0]
    if not table_name:
        conn.close()
        print("数据库中没有有效的视频表")
        return []
    cur = conn.execute(f"SELECT bvid FROM {table_name}")
    bvids = [row[0] for row in cur.fetchall()]
    conn.close()
    return bvids

def slice_bvids(bvids: List[str], num_slices: int, output_prefix: str) -> List[str]:
    """将 BV 号列表平分为 num_slices 份，生成 txt 文件，返回文件路径列表"""
    total = len(bvids)
    if total == 0:
        print("没有 BV 号可切片")
        return []
    slice_size = total // num_slices
    remainder = total % num_slices
    files = []
    start = 0
    for i in range(num_slices):
        end = start + slice_size + (1 if i < remainder else 0)
        slice_bv = bvids[start:end]
        fname = f"{output_prefix}{i+1}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(slice_bv))
        files.append(fname)
        print(f"生成切片 {fname}: {len(slice_bv)} 个 BV")
        start = end
    return files

def merge_result_files(result_files: List[str], output_path: str):
    """合并多个 bv_fetcher 生成的 Excel/CSV/JSON 文件，去重保留最新"""
    if not result_files:
        print("没有结果文件可合并")
        return
    # 复用 slice_and_merge.py 中的 merge_results 函数
    # 但需要导入该模块（需要确保该模块可导入且函数可用）
    # 直接 subprocess 调用 slice_and_merge.py --mode merge 更简单，但需要传递多个文件
    # 这里实现一个简单版合并（仅支持 Excel 和 CSV）
    import openpyxl
    import csv

    merged = {}
    for fpath in result_files:
        ext = Path(fpath).suffix.lower()
        records = []
        if ext == ".csv":
            with open(fpath, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                records = list(reader)
        elif ext in (".xlsx", ".xls"):
            wb = openpyxl.load_workbook(fpath, read_only=True)
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
            for row in ws.iter_rows(min_row=2, values_only=True):
                rec = {headers[i]: val for i, val in enumerate(row) if i < len(headers)}
                records.append(rec)
            wb.close()
        else:
            print(f"跳过不支持的文件格式 {ext}: {fpath}")
            continue

        for rec in records:
            bvid = rec.get("bvid")
            if bvid:
                merged[bvid] = rec

    records_out = list(merged.values())
    if not records_out:
        print("无有效数据")
        return

    # 保存为 Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(records_out[0].keys())
    ws.append(headers)
    for rec in records_out:
        ws.append([rec.get(h, "") for h in headers])
    wb.save(output_path)
    print(f"合并完成，共 {len(records_out)} 条记录 -> {output_path}")

def upload_files_to_servers(server_ips: List[str], username: str, password: str, local_files: List[str], remote_dir: str = "/home/ubuntu/"):
    """使用 upload.py 将文件上传到多台服务器（串行）"""
    # 要求 upload.py 支持参数: python upload.py <local_path> <host> <user> <pass> [remote_path]
    # 但现有 upload.py 硬编码，需要修改。这里调用一个增强版 upload.py
    # 为了不修改原文件，我们在此实现一个简单的上传函数（使用 paramiko）
    import paramiko
    for ip in server_ips:
        print(f"\n上传到 {ip} ...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(hostname=ip, username=username, password=password)
            sftp = ssh.open_sftp()
            for local_file in local_files:
                remote_path = os.path.join(remote_dir, os.path.basename(local_file))
                sftp.put(local_file, remote_path)
                print(f"  ✅ {local_file} -> {remote_path}")
            sftp.close()
        except Exception as e:
            print(f"  ❌ 上传失败: {e}")
        finally:
            ssh.close()

def download_from_server(server_ip: str, username: str, password: str, remote_path: str, local_dir: str = "."):
    """从单台服务器下载文件，使用 download.py 或直接实现"""
    # 调用 download.py，需要确保该脚本支持参数
    cmd = [
        sys.executable, SCRIPTS["download"],
        "--host", server_ip,
        "--user", username,
        "--password", password,
        "--remote", remote_path,
        "--local", local_dir
    ]
    return run_cmd(cmd)

# ---------- 菜单功能实现 ----------
def menu_crawl_to_db():
    """1. 采集B站视频（crawl_to_db.py）"""
    print("\n▶ 开始采集B站视频（分区增量模式）")
    # 可询问额外参数，例如 --tid, --max-pages, --since
    tid = input("请输入分区ID (默认30): ").strip()
    tid = tid if tid else "30"
    max_pages = input("最多爬取页数 (默认10000): ").strip()
    max_pages = max_pages if max_pages else "10000"
    since = input("手动指定水位线时间 (格式 YYYY-MM-DD HH:MM，直接回车则自动): ").strip()
    cmd = [sys.executable, SCRIPTS["crawl_db"], "--tid", tid, "--max-pages", max_pages]
    if since:
        cmd.extend(["--since", since])
    run_cmd(cmd)

def menu_filter():
    """2. 筛选视频（filter.py）"""
    print("\n▶ 开始筛选视频（时长、关键词、黑名单）")
    min_sec = input("最小时长(秒，默认120): ").strip()
    min_sec = min_sec if min_sec else "120"
    max_sec = input("最大时长(秒，默认420): ").strip()
    max_sec = max_sec if max_sec else "420"
    blacklist = input("黑名单文件 (默认blacklist.txt): ").strip()
    blacklist = blacklist if blacklist else "blacklist.txt"
    cmd = [sys.executable, SCRIPTS["filter"], "--min", min_sec, "--max", max_sec, "--blacklist", blacklist]
    run_cmd(cmd)

def menu_slice():
    """3. 切片BV号（支持自定义份数）"""
    print("\n▶ 切片BV号")
    db_path = input(f"源数据库路径 (默认{DEFAULT_FILTERED_DB}): ").strip()
    if not db_path:
        db_path = DEFAULT_FILTERED_DB
    bvids = get_bv_list_from_db(db_path)
    if not bvids:
        print("未获取到BV号")
        return
    print(f"共 {len(bvids)} 个BV号")
    slices = input("请输入切割份数 (默认3): ").strip()
    slices = int(slices) if slices.isdigit() else 3
    prefix = input(f"输出文件前缀 (默认{DEFAULT_SLICE_PREFIX}): ").strip()
    prefix = prefix if prefix else DEFAULT_SLICE_PREFIX
    files = slice_bvids(bvids, slices, prefix)
    print(f"\n已生成 {len(files)} 个切片文件:")
    for f in files:
        print(f"  {f}")

def menu_create_servers():
    """4. 创建云服务器（支持自定义数量）"""
    print("\n▶ 创建腾讯云CVM实例")
    count = input("请输入要创建的实例数量 (默认3): ").strip()
    count = int(count) if count.isdigit() else 3
    # 由于原 startserver.py 硬编码 InstanceCount=1，需要修改脚本支持 --count 参数
    # 我们调用一个修改后的版本: 确保 startserver.py 已增加 --count 参数
    cmd = [sys.executable, SCRIPTS["start_server"], "--count", str(count)]
    if not run_cmd(cmd):
        print("创建实例失败，请检查 startserver.py 是否支持 --count 参数。")
        print("提示：可以手动修改 startserver.py，在 RunInstancesRequest 中设置 InstanceCount = count")
    else:
        print("实例创建请求已提交，请稍后检查 instances_info.json")

def menu_upload():
    """5. 上传数据到服务器（每个服务器上传对应的切片文件 + bv_fetcher.py + setup_and_run.sh）"""
    print("\n▶ 上传文件到云服务器")
    info_file = "instances_info.json"
    if not os.path.exists(info_file):
        print(f"未找到 {info_file}，请先创建服务器")
        return
    with open(info_file, "r") as f:
        data = json.load(f)
    instances = data.get("instances", [])
    if not instances:
        print("没有实例信息")
        return

    ips = [inst["PublicIp"] for inst in instances if inst.get("PublicIp")]
    if not ips:
        print("没有公网IP")
        return

    username = input("SSH用户名 (默认ubuntu): ").strip() or "ubuntu"
    password = input("SSH密码 (默认Sunny1318860595.): ").strip() or "Sunny1318860595."
    remote_dir = input("远程目录 (默认 /home/ubuntu/): ").strip() or "/home/ubuntu/"

    # 自动检测切片文件（按顺序 slice_1.txt, slice_2.txt, slice_3.txt）
    slice_files = []
    for i in range(1, len(ips)+1):
        candidate = f"slice_{i}.txt"
        if os.path.exists(candidate):
            slice_files.append(candidate)
        else:
            print(f"警告：未找到切片文件 {candidate}，请先执行菜单3生成切片")
            return

    if len(slice_files) != len(ips):
        print(f"切片文件数量({len(slice_files)})与服务器数量({len(ips)})不匹配")
        return

    # 需要上传的脚本文件（必须存在）
    bv_fetcher_script = "bv_fetcher.py"
    setup_script = "setup_and_run.sh"
    if not os.path.exists(bv_fetcher_script):
        print(f"错误：{bv_fetcher_script} 不存在，请确保该脚本在当前目录")
        return
    if not os.path.exists(setup_script):
        print(f"错误：{setup_script} 不存在，请确保该脚本在当前目录")
        return

    print("\n开始上传...")
    for idx, (ip, slice_file) in enumerate(zip(ips, slice_files), start=1):
        print(f"\n>>> 上传到服务器 {idx} ({ip})")
        # 上传切片文件
        remote_slice = os.path.join(remote_dir, slice_file)
        cmd_upload_slice = [
            sys.executable, "upload.py",
            "--local", slice_file,
            "--remote", remote_slice,
            "--host", ip,
            "--user", username,
            "--password", password
        ]
        if not run_cmd(cmd_upload_slice):
            print(f"上传 {slice_file} 失败，跳过该服务器")
            continue

        # 上传 bv_fetcher.py
        remote_script = os.path.join(remote_dir, bv_fetcher_script)
        cmd_upload_script = [
            sys.executable, "upload.py",
            "--local", bv_fetcher_script,
            "--remote", remote_script,
            "--host", ip,
            "--user", username,
            "--password", password
        ]
        if not run_cmd(cmd_upload_script):
            print(f"上传 {bv_fetcher_script} 失败，可能影响远程执行")

        # 上传 setup_and_run.sh
        remote_setup = os.path.join(remote_dir, setup_script)
        cmd_upload_setup = [
            sys.executable, "upload.py",
            "--local", setup_script,
            "--remote", remote_setup,
            "--host", ip,
            "--user", username,
            "--password", password
        ]
        if not run_cmd(cmd_upload_setup):
            print(f"上传 {setup_script} 失败，可能影响远程执行")

    print("\n✅ 所有上传任务完成")

def menu_remote_run():
    """6. 在服务器上执行采集命令（输出命令，手动执行）"""
    print("\n▶ 远程采集命令生成")
    info_file = "instances_info.json"
    if not os.path.exists(info_file):
        print("未找到 instances_info.json")
        return
    with open(info_file, "r") as f:
        data = json.load(f)
    instances = data.get("instances", [])
    ips = [inst["PublicIp"] for inst in instances if inst.get("PublicIp")]
    if not ips:
        print("无公网IP")
        return
    print("请登录各服务器手动执行以下命令（假设已上传切片文件和 bv_fetcher.py）：")
    for idx, ip in enumerate(ips, 1):
        print(f"\n服务器 {idx} (IP {ip}):")
        print(f"  ssh {username}@{ip}")
        print(f"  cd /home/ubuntu")
        print(f"  python3 bv_fetcher.py -i slice_{idx}.txt -o result_{idx}.xlsx --quiet")

def menu_download():
    """7. 从服务器下载结果文件（识别 .xlsx 和 _failed.txt，不依赖 result 前缀）"""
    print("\n▶ 从服务器下载结果文件")
    info_file = "instances_info.json"
    if not os.path.exists(info_file):
        print(f"未找到 {info_file}，请先创建服务器")
        return
    with open(info_file, "r") as f:
        data = json.load(f)
    instances = data.get("instances", [])
    if not instances:
        print("没有实例信息")
        return

    ips = [inst["PublicIp"] for inst in instances if inst.get("PublicIp")]
    if not ips:
        print("没有公网IP")
        return

    username = input("SSH用户名 (默认ubuntu): ").strip() or "ubuntu"
    password = input("SSH密码 (默认Sunny1318860595.): ").strip() or "Sunny1318860595."
    remote_dir = input("远程目录 (默认 /home/ubuntu/): ").strip() or "/home/ubuntu/"
    local_dir = input("本地保存目录 (默认当前目录): ").strip() or "."

    # 需要匹配的文件模式
    patterns = ["*.xlsx", "*_failed.txt"]

    print("\n开始下载...")
    for idx, ip in enumerate(ips, start=1):
        print(f"\n>>> 从服务器 {idx} ({ip}) 扫描文件")
        # 通过 SSH 列出远程目录下匹配模式的文件
        remote_files = []
        try:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=ip, username=username, password=password)

            # 使用 find 命令匹配多个模式
            find_cmd = f'find "{remote_dir}" -maxdepth 1 -type f \\( '
            for i, pat in enumerate(patterns):
                if i > 0:
                    find_cmd += " -o "
                find_cmd += f'-name "{pat}"'
            find_cmd += " \\)"
            stdin, stdout, stderr = ssh.exec_command(find_cmd)
            remote_files = [line.strip() for line in stdout.readlines()]
            ssh.close()
        except Exception as e:
            print(f"  ❌ 连接或扫描失败: {e}")
            continue

        if not remote_files:
            print(f"  ⚠️ 未找到匹配的文件（模式：{patterns}）")
            continue

        print(f"  发现 {len(remote_files)} 个文件")
        for remote_path in remote_files:
            # 调用 download.py 下载每个文件
            cmd_download = [
                sys.executable, "download.py",
                "--host", ip,
                "--user", username,
                "--password", password,
                "--remote", remote_path,
                "--local", local_dir
            ]
            print(f"  下载: {os.path.basename(remote_path)}")
            run_cmd(cmd_download)

    print("\n✅ 下载完成，请检查本地目录")

def menu_merge():
    """8. 合并结果文件（只合并当前目录下的 .xlsx 文件）"""
    print("\n▶ 合并多个Excel文件")
    # 列出当前目录下所有 .xlsx 文件
    xlsx_files = [f for f in os.listdir("..") if f.endswith(".xlsx")]
    if not xlsx_files:
        print("未找到任何 .xlsx 文件")
        return
    print("找到以下Excel文件:")
    for i, f in enumerate(xlsx_files, 1):
        print(f"  {i}. {f}")
    selected = input("请输入要合并的文件索引（用空格分隔，默认全部）: ").strip()
    if selected:
        idxs = [int(x)-1 for x in selected.split() if x.isdigit()]
        files_to_merge = [xlsx_files[i] for i in idxs if i < len(xlsx_files)]
    else:
        files_to_merge = xlsx_files
    if not files_to_merge:
        print("未选择任何文件")
        return
    out_name = input("输出文件名 (默认merged_result.xlsx): ").strip()
    out_name = out_name if out_name else "merged_result.xlsx"
    merge_result_files(files_to_merge, out_name)

def menu_score():
    """9. 计算得分（score_diff.py）"""
    print("\n▶ 计算增量得分")
    file1 = input("第一个时间点文件 (旧): ").strip()
    if not os.path.exists(file1):
        print("文件不存在")
        return
    file2 = input("第二个时间点文件 (新): ").strip()
    if not os.path.exists(file2):
        print("文件不存在")
        return
    out = input("输出文件 (默认自动生成): ").strip()
    cmd = [sys.executable, SCRIPTS["score_diff"], file1, file2]
    if out:
        cmd.extend(["-o", out])
    run_cmd(cmd)

def menu_delete_instances():
    """10. 删除实例"""
    print("\n▶ 删除腾讯云实例")
    confirm = input("⚠️ 此操作将销毁所有实例，不可逆！是否继续？(yes/no): ").strip().lower()
    if confirm != "yes":
        print("取消删除")
        return
    run_cmd([sys.executable, SCRIPTS["check_instance"]])

def menu_exit():
    print("退出程序")
    sys.exit(0)

# ---------- 主菜单 ----------
def main():
    while True:
        print("\n" + "=" * 50)
        print("周刊工作流管理程序")
        print("=" * 50)
        print("1. 采集视频 ")
        print("2. 筛选视频 ")
        print("3. 切片BV号 ")
        print("4. 创建云服务器 ")
        print("5. 上传数据到服务器")
        print("6. 生成远程采集命令")
        print("7. 下载服务器结果")
        print("8. 合并结果文件")
        print("9. 计算得分")
        print("10. 删除所有服务器")
        print("0. 退出")
        choice = input("请选择操作: ").strip()
        if choice == "1":
            menu_crawl_to_db()
        elif choice == "2":
            menu_filter()
        elif choice == "3":
            menu_slice()
        elif choice == "4":
            menu_create_servers()
        elif choice == "5":
            menu_upload()
        elif choice == "6":
            menu_remote_run()
        elif choice == "7":
            menu_download()
        elif choice == "8":
            menu_merge()
        elif choice == "9":
            menu_score()
        elif choice == "10":
            menu_delete_instances()
        elif choice == "0":
            menu_exit()
        else:
            print("无效选项，请重新输入")
        input("\n按回车键继续...")

if __name__ == "__main__":
    main()