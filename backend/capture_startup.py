#!/usr/bin/env python3
"""
捕获 uvicorn 启动日志
"""
import subprocess
import sys
import time

# 设置环境变量
import os
os.environ['PYTHONUNBUFFERED'] = '1'

# 启动 uvicorn
cmd = [
    sys.executable, '-m', 'uvicorn',
    'backend.app.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--reload'
]

print(f"[Capture] Running: {' '.join(cmd)}")
print("=" * 80)

# 启动进程并实时输出
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True
)

# 读取前 100 行日志
print("[Capture] Reading startup logs...")
for i, line in enumerate(process.stdout, 1):
    print(line, end='', flush=True)
    if i >= 100:
        break

print("\n" + "=" * 80)
print("[Capture] Captured first 100 lines. Press Ctrl+C to stop server.")

# 保持进程运行
try:
    process.wait()
except KeyboardInterrupt:
    print("\n[Capture] Stopping server...")
    process.terminate()
    process.wait()
