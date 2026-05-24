#!/usr/bin/env python3
"""
删除网易云歌单及云盘音乐（功能13）
====================================
删除先前通过功能12创建的网易云歌单和上传的云盘音乐。
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from ncm_utils import delete_playlist, delete_cloud_songs


def main():
    print("网易云音乐清理工具")
    print("=" * 50)

    print("将要执行以下操作：")
    print("  1. 删除通过同步创建的歌单")
    print("  2. 删除已上传的云盘音乐")

    confirm = input("\n⚠️  此操作不可逆！是否继续？(yes/no): ").strip().lower()
    if confirm != "yes":
        print("已取消")
        return

    print("\n--- 删除歌单 ---")
    ok_playlist = delete_playlist()

    print("\n--- 删除云盘音乐 ---")
    ok_cloud = delete_cloud_songs()

    print(f"\n{'=' * 50}")
    if ok_playlist:
        print("  ✅ 歌单已删除")
    else:
        print("  ❌ 歌单删除失败（可能不存在或网络问题）")
    if ok_cloud:
        print("  ✅ 云盘音乐已删除")
    else:
        print("  ❌ 云盘音乐删除失败")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
