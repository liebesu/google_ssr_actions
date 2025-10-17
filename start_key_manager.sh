#!/bin/bash
# SerpAPI 密钥管理服务启动脚本

# 设置工作目录
cd "$(dirname "$0")"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查Flask是否安装
if ! python3 -c "import flask" &> /dev/null; then
    echo "安装 Flask..."
    pip3 install flask requests
fi

# 创建必要的目录
mkdir -p data

# 启动API服务
echo "启动 SerpAPI 密钥管理服务..."
echo "访问地址: http://localhost:5000"
echo "密钥管理页面: http://localhost:5000/static/key_manager.html"
echo "按 Ctrl+C 停止服务"

python3 key_manager_api.py













