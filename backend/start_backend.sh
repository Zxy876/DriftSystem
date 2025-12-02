#!/bin/bash

echo "=============================="
echo "🚀 启动 DriftSystem 后端 (FastAPI)"
echo "=============================="

cd "$(dirname "$0")/backend"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python3."
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "⬇️ 未检测到 venv，正在创建 ..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "📦 激活虚拟环境 venv ..."
source venv/bin/activate

# 安装依赖
echo "📦 正在安装依赖 ..."
pip install -r requirements.txt

# 启动 FastAPI
echo "🌐 后端启动中： http://127.0.0.1:8000"
echo "（按 Ctrl+C 关闭）"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
