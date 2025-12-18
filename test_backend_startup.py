#!/usr/bin/env python3
"""
测试后端启动并捕获日志（从项目根目录运行）
"""
import subprocess
import sys
import time
import os

# 设置环境变量
os.environ['PYTHONUNBUFFERED'] = '1'

print("[Test] Starting uvicorn from project root")
print("[Test] Command: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload")
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

# 读取启动日志
print("[Test] Capturing startup logs...")
start_time = time.time()
line_count = 0
startup_complete = False
has_warnings = False
warning_lines = []

try:
    for line in process.stdout:
        print(line, end='', flush=True)
        line_count += 1

        # 检查警告
        if "[WARN]" in line or "WARNING" in line:
            has_warnings = True
            warning_lines.append(line.strip())

        # 检查是否看到 "Application startup complete"
        if "Application startup complete" in line:
            startup_complete = True
            print("\n" + "=" * 80)
            print(f"[Test] ✅ Server started successfully! ({line_count} lines)")
            if has_warnings:
                print(f"[Test] ⚠️  Found {len(warning_lines)} warnings:")
                for warning in warning_lines:
                    print(f"       {warning}")
            else:
                print("[Test] ✅ No warnings found!")
            print("=" * 80)
            break

        # 检查是否超过 80 行
        if line_count >= 80:
            print("\n" + "=" * 80)
            print(f"[Test] Captured {line_count} lines, stopping...")
            print("=" * 80)
            break

        # 检查是否超过 15 秒
        if time.time() - start_time > 15:
            print("\n" + "=" * 80)
            print(f"[Test] Timeout after 15 seconds ({line_count} lines)")
            print("=" * 80)
            break

    # 等待 2 秒让服务完全启动
    if startup_complete:
        time.sleep(2)
        print("[Test] Server is running. Press Ctrl+C to stop...")

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
