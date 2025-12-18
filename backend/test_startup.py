#!/usr/bin/env python3
"""
测试后端启动并捕获日志
"""
import subprocess
import sys
import time
import os

# 设置环境变量
os.environ['PYTHONUNBUFFERED'] = '1'

print("[Test] Starting uvicorn with backend.app.main:app")
print("=" * 80)

# 启动 uvicorn
cmd = [
    sys.executable, '-m', 'uvicorn',
    'backend.app.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--reload'
]

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# 读取前 60 行或等待 10 秒
print("[Test] Capturing startup logs...")
start_time = time.time()
line_count = 0

try:
    for line in process.stdout:
        print(line, end='', flush=True)
        line_count += 1

        # 检查是否看到 "Application startup complete"
        if "Application startup complete" in line:
            print("\n" + "=" * 80)
            print(f"[Test] ✅ Server started successfully! ({line_count} lines)")
            print("=" * 80)
            break

        # 检查是否超过 60 行
        if line_count >= 60:
            print("\n" + "=" * 80)
            print(f"[Test] Captured {line_count} lines")
            print("=" * 80)
            break

        # 检查是否超过 10 秒
        if time.time() - start_time > 10:
            print("\n" + "=" * 80)
            print(f"[Test] Timeout after 10 seconds ({line_count} lines)")
            print("=" * 80)
            break

    # 等待 2 秒让服务完全启动
    time.sleep(2)

finally:
    # 停止服务
    print("\n[Test] Stopping server...")
    process.terminate()
    try:
        process.wait(timeout=5)
        print("[Test] Server stopped gracefully")
    except subprocess.TimeoutExpired:
        process.kill()
        print("[Test] Server killed")
