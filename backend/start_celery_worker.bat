@echo off
REM Celery Worker 启动脚本 (Windows)
REM 用法：双击运行或在 backend 目录下执行 start_celery_worker.bat

echo ========================================
echo   Celery Worker 启动中...
echo ========================================
echo.

REM 检查是否在 backend 目录
if not exist "app\core\celery_app.py" (
    echo [错误] 请在 backend 目录下运行此脚本
    pause
    exit /b 1
)

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

REM 检查 Celery 是否安装
python -c "import celery" >nul 2>&1
if errorlevel 1 (
    echo [错误] Celery 未安装，正在安装依赖...
    pip install -r requirements.txt
)

echo [信息] 启动 Celery Worker...
echo [信息] 并发数：3
echo [信息] 队列：upload_queue
echo [信息] 按 Ctrl+C 停止
echo.

REM 启动 Celery Worker (Windows 使用 solo 模式)
celery -A app.core.celery_app worker --loglevel=info --pool=solo

pause
