#!/bin/bash
# Celery Worker 启动脚本 (Linux/Mac)
# 用法：chmod +x start_celery_worker.sh && ./start_celery_worker.sh

echo "========================================"
echo "  Celery Worker 启动中..."
echo "========================================"
echo ""

# 检查是否在 backend 目录
if [ ! -f "app/core/celery_app.py" ]; then
    echo "[错误] 请在 backend 目录下运行此脚本"
    exit 1
fi

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python"
    exit 1
fi

# 检查 Celery 是否安装
if ! python3 -c "import celery" &> /dev/null; then
    echo "[错误] Celery 未安装，正在安装依赖..."
    pip3 install -r requirements.txt
fi

echo "[信息] 启动 Celery Worker..."
echo "[信息] 并发数：3"
echo "[信息] 队列：upload_queue"
echo "[信息] 按 Ctrl+C 停止"
echo ""

# 启动 Celery Worker (Linux/Mac 使用默认 prefork 模式)
celery -A app.core.celery_app worker --loglevel=info --concurrency=3
