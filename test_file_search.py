"""
测试 File Search 上传功能
"""
import requests
import os

# 配置
API_KEY = os.getenv("GEMINI_API_KEY")  # 从环境变量读取
BASE_URL = "http://localhost:8000"

if not API_KEY:
    print("ERROR: Please set GEMINI_API_KEY environment variable")
    exit(1)

# 创建测试文件
test_content = """
# Test Document

This is a test file for Deep Research document analysis.

## Key Information

1. Project Name: Gemini Chat Application
2. Tech Stack: React + FastAPI + Google GenAI
3. Main Features:
   - Multi-modal conversation
   - Image generation and editing
   - Deep research analysis

## Architecture

Frontend: React 18 + TypeScript
Backend: FastAPI + SQLAlchemy
"""

# 保存测试文件
test_file_path = "test_document.md"
with open(test_file_path, 'w', encoding='utf-8') as f:
    f.write(test_content)

print(f"[OK] Test file created: {test_file_path}")

# 上传文件到 File Search Store
print("\n[UPLOAD] Uploading to Google File Search Store...")

with open(test_file_path, 'rb') as f:
    files = {'file': (test_file_path, f, 'text/markdown')}
    headers = {'Authorization': f'Bearer {API_KEY}'}

    response = requests.post(
        f"{BASE_URL}/api/file-search/upload",
        files=files,
        headers=headers,
        timeout=120
    )

if response.status_code == 200:
    result = response.json()
    print("[SUCCESS] Upload completed!")
    print(f"  Store Name: {result['file_search_store_name']}")
    print(f"  File Name: {result['file_name']}")
    print(f"  Status: {result['status']}")
    print(f"\n[INFO] Use this store_name for Deep Research:")
    print(f"  {result['file_search_store_name']}")
else:
    print(f"[ERROR] Upload failed: {response.status_code}")
    print(f"  {response.text}")

# 清理测试文件
os.remove(test_file_path)
print(f"\n[CLEAN] Test file deleted: {test_file_path}")
