#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
B站数据采集 + 腾讯云管理 总控脚本
================================
提供交互式菜单，调用以下子脚本：
1. check_instance.py   - 查询腾讯云CVM实例状态
2. crawl_to_db.py      - B站分区视频增量入库
3. filter.py           - 从数据库筛选符合条件的视频
4. slice_and_merge.py  - 切片/合并BV号文件（用于多机采集）
5. bv_fetcher.py       - BV号批量采集（单机版）
6. score_diff.py       - 计算两个时间点数据增量得分
7. startserver.py      - 创建腾讯云CVM实例
0. 退出
"""

import subprocess
import sys
import os
import shlex

# 脚本所在目录（假设所有脚本都与 manager.py 位于同一目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 子脚本名称映射
SCRIPTS = {
    '1': 'check_instance.py',
    '2': 'crawl_to_db.py',
    '3': 'filter.py',
    '4': 'slice_and_merge.py',
    '5': 'bv_fetcher.py',
    '6': 'score_diff.py',
    '7': 'startserver.py',
}

def run_script(script_name, args=None):
    """在基地目录下运行指定的 Python 脚本，args 为列表形式的参数"""
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"[错误] 脚本不存在：{script_path}")
        return

    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)

    print(f"\n>>> 执行命令：{' '.join(shlex.quote(str(x)) for x in cmd)}\n")
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"\n[警告] 脚本执行结束，返回码：{result.returncode}")
    except KeyboardInterrupt:
        print("\n[中断] 用户终止脚本运行")
    except Exception as e:
        print(f"\n[错误] 运行失败：{e}")
    input("\n按 Enter 返回主菜单...")

def menu_check_instance():
    """1. 查询实例状态"""
    instance_id = input("请输入实例 ID（直接回车使用默认 ins-5b0nyfpg）：").strip()
    if not instance_id:
        instance_id = "ins-5b0nyfpg"
    run_script('check_instance.py', [instance_id])

def menu_crawl_to_db():
    """2. 分区视频增量入库"""
    print("\n---- B站分区视频增量采集入库 ----")
    print("常用选项（直接回车将采用默认值）：")
    tid = input("分区ID (默认 30 – 虚拟歌姬): ").strip()
    max_pages = input("最多爬取页数 (默认 10000): ").strip()
    since = input("手动指定水位线 (格式 'YYYY-MM-DD HH:MM'，默认从数据库最新时间开始): ").strip()
    args = []
    if tid:
        args.extend(['--tid', tid])
    if max_pages:
        args.extend(['--max-pages', max_pages])
    if since:
        args.extend(['--since', since])
    # 默认增量模式（不传 --page 即为增量）
    run_script('crawl_to_db.py', args)

def menu_filter():
    """3. 视频筛选"""
    print("\n---- 视频筛选工具 ----")
    source = input("源数据库文件 (默认 bilibili_videos.db): ").strip()
    target = input("目标数据库文件 (默认 filtered_videos.db): ").strip()
    blacklist = input("黑名单文件 (默认 blacklist.txt，可跳过): ").strip()
    args = []
    if source:
        args.extend(['--source', source])
    if target:
        args.extend(['--target', target])
    if blacklist and blacklist != 'skip':
        args.extend(['--blacklist', blacklist])
    run_script('filter.py', args)

def menu_slice_and_merge():
    """4. 切片/合并工具"""
    print("\n---- 切片 & 合并工具 ----")
    print("请选择模式：")
    print("  1. 切片 (slice) - 将 filtered_videos.db 分成 3 份，生成 txt 输入文件")
    print("  2. 合并 (merge) - 合并三台服务器生成的采集结果")
    print("  3. 自动 (auto)  - 本地切片 + 并行采集 + 合并，可选算分")
    mode = input("请输入数字 (1/2/3): ").strip()
    if mode == '1':
        source = input("源数据库 (默认 filtered_videos.db): ").strip()
        prefix = input("切片文件前缀 (默认 slice_): ").strip()
        args = ['--mode', 'slice']
        if source:
            args.extend(['--source', source])
        if prefix:
            args.extend(['--slice-prefix', prefix])
        run_script('slice_and_merge.py', args)
    elif mode == '2':
        result1 = input("服务器1结果文件路径: ").strip()
        result2 = input("服务器2结果文件路径: ").strip()
        result3 = input("服务器3结果文件路径: ").strip()
        out = input("合并输出文件路径 (默认 merged_result.xlsx): ").strip()
        if not (result1 and result2 and result3):
            print("错误：需要提供三个结果文件。")
            return
        args = ['--mode', 'merge', '--result1', result1, '--result2', result2, '--result3', result3]
        if out:
            args.extend(['--out', out])
        run_script('slice_and_merge.py', args)
    elif mode == '3':
        source = input("源数据库 (默认 filtered_videos.db): ").strip()
        output = input("最终合并输出文件 (默认 merged_data.xlsx): ").strip()
        second = input("用于算分的上一个时间点文件 (可选，若需自动算分请提供): ").strip()
        args = ['--mode', 'auto']
        if source:
            args.extend(['--source', source])
        if output:
            args.extend(['--out', output])
        if second:
            args.extend(['--second-file', second, '--run-score-diff'])
        run_script('slice_and_merge.py', args)
    else:
        print("无效选择")

def menu_bv_fetcher():
    """5. BV号批量采集"""
    print("\n---- BV号批量采集 (单机版) ----")
    input_file = input("输入文件 (txt/csv/xlsx，每行一个BV号或链接): ").strip()
    if not input_file:
        print("错误：必须指定输入文件")
        return
    output = input("输出文件 (默认自动生成时间戳.xlsx): ").strip()
    workers = input("线程数 (默认 10): ").strip()
    size = input("每批数量 (默认 100): ").strip()
    quiet = input("安静模式？(y/n, 默认 n): ").strip().lower()
    args = ['-i', input_file]
    if output:
        args.extend(['-o', output])
    if workers:
        args.extend(['-w', workers])
    if size:
        args.extend(['-s', size])
    if quiet == 'y':
        args.append('--quiet')
    run_script('bv_fetcher.py', args)

def menu_score_diff():
    """6. 增量算分"""
    print("\n---- 增量算分工具 ----")
    file1 = input("第一个时间点文件 (旧): ").strip()
    file2 = input("第二个时间点文件 (新): ").strip()
    if not file1 or not file2:
        print("错误：两个文件都必须提供")
        return
    out = input("输出文件路径 (默认 '旧-新.xlsx'): ").strip()
    args = [file1, file2]
    if out:
        args.extend(['-o', out])
    run_script('score_diff.py', args)

def menu_startserver():
    """7. 创建CVM实例"""
    print("\n---- 创建腾讯云CVM实例 (startserver.py) ----")
    print("注意：该操作将产生费用！确认后将在 ap-nanjing 区创建一台按量计费实例。")
    confirm = input("是否继续？(y/n): ").strip().lower()
    if confirm == 'y':
        run_script('startserver.py', [])
    else:
        print("已取消")

def main():
    while True:
        print("\n" + "=" * 50)
        print("        B站数据采集 + 腾讯云管理 总控菜单")
        print("=" * 50)
        print(" 1. 查询CVM实例状态 (check_instance)")
        print(" 2. B站分区视频增量入库 (crawl_to_db)")
        print(" 3. 筛选视频 (filter)")
        print(" 4. BV切片/多机采集辅助 (slice_and_merge)")
        print(" 5. BV号批量采集 (bv_fetcher)")
        print(" 6. 计算增量得分 (score_diff)")
        print(" 7. 创建CVM实例 (startserver)")
        print(" 0. 退出")
        print("-" * 50)

        choice = input("请输入操作编号: ").strip()

        if choice == '0':
            print("再见！")
            break
        elif choice == '1':
            menu_check_instance()
        elif choice == '2':
            menu_crawl_to_db()
        elif choice == '3':
            menu_filter()
        elif choice == '4':
            menu_slice_and_merge()
        elif choice == '5':
            menu_bv_fetcher()
        elif choice == '6':
            menu_score_diff()
        elif choice == '7':
            menu_startserver()
        else:
            print("无效选项，请重新输入")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，退出。")
        sys.exit(0)