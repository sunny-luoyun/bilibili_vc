#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
从远程服务器下载文件
用法:
    python download.py --host <IP> --user <用户名> --password <密码> --remote <远程路径> [--local <本地目录>]
"""
import paramiko
import os
import argparse
import sys

def download_file(host, username, password, remote_path, local_dir="."):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname=host, username=username, password=password)
        sftp = ssh.open_sftp()
        local_filename = os.path.basename(remote_path)
        local_full = os.path.join(local_dir, local_filename)
        sftp.get(remote_path, local_full)
        print(f"✅ 下载成功: {remote_path} -> {local_full}")
        sftp.close()
    except Exception as e:
        print(f"❌ 下载失败: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从远程服务器下载文件")
    parser.add_argument("--host", required=True, help="服务器IP")
    parser.add_argument("--user", required=True, help="SSH用户名")
    parser.add_argument("--password", required=True, help="SSH密码")
    parser.add_argument("--remote", required=True, help="远程文件路径")
    parser.add_argument("--local", default=".", help="本地保存目录，默认当前目录")
    args = parser.parse_args()
    download_file(args.host, args.user, args.password, args.remote, args.local)