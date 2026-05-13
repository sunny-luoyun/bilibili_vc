#!/usr/bin/env python3
import paramiko
import os
import argparse
import sys

def upload_file(local_path, remote_path, host, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname=host, username=username, password=password)
        sftp = ssh.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        print(f"✅ 文件上传成功: {local_path} -> {remote_path}")
        return True
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        return False
    finally:
        ssh.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="上传文件到远程服务器")
    parser.add_argument("--local", required=True, help="本地文件路径")
    parser.add_argument("--remote", required=True, help="远程保存路径（含文件名）")
    parser.add_argument("--host", required=True, help="服务器IP")
    parser.add_argument("--user", required=True, help="SSH用户名")
    parser.add_argument("--password", required=True, help="SSH密码")
    args = parser.parse_args()

    if not os.path.isfile(args.local):
        print(f"❌ 文件不存在: {args.local}")
        sys.exit(1)

    success = upload_file(args.local, args.remote, args.host, args.user, args.password)
    sys.exit(0 if success else 1)