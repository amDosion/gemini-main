"""测试 /upload-async API，验证参数传递和数据库写入"""
import requests
import os
import io

API_BASE = "http://localhost:8000/api/storage"

# 1. 检查后端是否运行
print("=" * 60)
print("1. 检查后端状态")
print("=" * 60)
try:
    resp = requests.get(f"{API_BASE}/debug", timeout=5)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"TEMP_DIR: {data.get('temp_dir')}")
        print(f"CWD: {data.get('cwd')}")
    else:
        print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")
    print("后端可能未启动！")
    exit(1)

# 2. 创建测试文件
print("\n" + "=" * 60)
print("2. 创建测试上传任务")
print("=" * 60)

# 创建一个小的测试图片（1x1 PNG）
test_png = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
    0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
    0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
    0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
    0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
    0x44, 0xAE, 0x42, 0x60, 0x82
])

# 测试参数
test_params = {
    "session_id": "test-session-12345678",
    "message_id": "test-message-87654321",
    "attachment_id": "test-attachment-abcdef",
    "priority": "normal"
}

files = {
    "file": ("test-image.png", io.BytesIO(test_png), "image/png")
}

print(f"测试参数: {test_params}")

try:
    resp = requests.post(
        f"{API_BASE}/upload-async",
        params=test_params,
        files=files,
        timeout=10
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"任务ID: {result.get('task_id')}")
        print(f"状态: {result.get('status')}")
        print(f"入队: {result.get('enqueued')}")
        task_id = result.get('task_id')
    else:
        print(f"错误: {resp.text}")
        exit(1)
except Exception as e:
    print(f"请求失败: {e}")
    exit(1)

# 3. 查询数据库验证写入
print("\n" + "=" * 60)
print("3. 验证数据库写入")
print("=" * 60)

import psycopg2
conn = psycopg2.connect(
    host='192.168.50.115',
    port=5432,
    database='gemini-ai',
    user='ai',
    password='Z6LwNUH481dnjAmp2kMRPmg8xj8CtE'
)
cur = conn.cursor()

cur.execute("""
    SELECT id, session_id, message_id, attachment_id, 
           source_file_path, storage_id, priority, status
    FROM upload_tasks 
    WHERE id = %s
""", (task_id,))

row = cur.fetchone()
if row:
    print(f"任务ID: {row[0]}")
    print(f"session_id: {row[1]}")
    print(f"message_id: {row[2]}")
    print(f"attachment_id: {row[3]}")
    print(f"source_file_path: {row[4]}")
    print(f"storage_id: {row[5]}")
    print(f"priority: {row[6]}")
    print(f"status: {row[7]}")
    
    # 检查路径类型
    path = row[4]
    if path:
        if path.startswith('C:') or path.startswith('D:') or path.startswith('/'):
            print(f"\n⚠️ 路径是绝对路径！代码可能未更新")
        elif path.startswith('backend/temp/'):
            print(f"\n✅ 路径是相对路径，代码已正确更新")
        else:
            print(f"\n❓ 路径格式未知: {path}")
else:
    print(f"未找到任务: {task_id}")

conn.close()
print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
