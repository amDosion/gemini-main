import os
import shutil
import subprocess

npx_path = shutil.which('npx')
print(f"npx from which: {npx_path}")

fallback = r'C:\Program Files\nodejs\npx.cmd'
print(f"fallback exists: {os.path.exists(fallback)}")

if os.path.exists(fallback):
    result = subprocess.run([fallback, '-y', '@openai/codex', '--version'], capture_output=True, text=True)
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")
    print(f"returncode: {result.returncode}")
