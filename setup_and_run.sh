#!/bin/bash
set -e

echo "=== 安装 Python3 及依赖 ==="
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

echo "激活虚拟环境..."
source "$VENV_DIR/bin/activate"

echo "安装 openpyxl..."
pip install openpyxl

echo "=== 开始采集 ==="
if [ -z "$2" ]; then
    # 未指定输出文件 → 让 Python 自动生成时间戳文件名
    python3 bv_fetcher.py -i "$1"
else
    # 指定了输出文件
    python3 bv_fetcher.py -i "$1" -o "$2"
fi

echo "完成！"