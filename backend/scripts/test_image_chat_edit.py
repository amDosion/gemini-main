"""
测试 image-chat-edit 模式 - 多轮对话式图片编辑
"""
import requests
import json
import base64
import uuid
import os

BASE_URL = "http://localhost:21574"

# 1. 登录获取 token
print("1. 登录...")
login_resp = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "121802744@qq.com", "password": "chuan*1127"}
)
print(f"   状态码: {login_resp.status_code}")
if login_resp.status_code != 200:
    print(f"   错误: {login_resp.text}")
    exit(1)

login_data = login_resp.json()
token = login_data.get("accessToken")
print(f"   Token: {token[:50]}...")

headers = {"Authorization": f"Bearer {token}"}

# 2. 下载一张测试图片并转为 base64
print("\n2. 准备测试图片...")
# 使用一个公开的测试图片
test_image_url = "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"
try:
    img_resp = requests.get(test_image_url, timeout=10)
    if img_resp.status_code == 200:
        image_base64 = base64.b64encode(img_resp.content).decode('utf-8')
        print(f"   ✅ 下载成功，大小: {len(img_resp.content)} bytes")
    else:
        print(f"   ❌ 下载失败: {img_resp.status_code}")
        exit(1)
except Exception as e:
    print(f"   ❌ 下载异常: {e}")
    exit(1)

# 3. 使用一个已有的会话
frontend_session_id = str(uuid.uuid4())  # 新建一个会话
print(f"   Session ID: {frontend_session_id}")

# 4. 测试 image-chat-edit 模式
print("\n3. 测试 image-chat-edit 模式...")

payload = {
    "modelId": "gemini-3-pro-image-preview",
    "prompt": "Add a red border around this image",
    "attachments": [
        {
            "attachmentId": str(uuid.uuid4()),
            "url": f"data:image/png;base64,{image_base64}",
            "mimeType": "image/png"
        }
    ],
    "options": {
        "frontendSessionId": frontend_session_id,
        "sessionId": frontend_session_id,
        "enableThinking": False
    }
}

print(f"   请求: modelId={payload['modelId']}, prompt={payload['prompt']}")
print(f"   图片: base64 格式，长度={len(image_base64)}")

try:
    print("   发送请求中...")
    resp = requests.post(
        f"{BASE_URL}/api/modes/google/image-chat-edit",
        headers=headers,
        json=payload,
        timeout=120  # 图片编辑可能需要较长时间
    )
    print(f"   状态码: {resp.status_code}")
    
    if resp.status_code == 200:
        result = resp.json()
        print(f"   ✅ 成功! 返回数据类型: {type(result)}")
        if isinstance(result, list) and len(result) > 0:
            first_img = result[0]
            if 'url' in first_img:
                print(f"   图片 URL 前缀: {first_img['url'][:80]}...")
        elif isinstance(result, dict):
            print(f"   返回字段: {list(result.keys())}")
    else:
        print(f"   ❌ 错误: {resp.text[:500]}")
except requests.exceptions.Timeout:
    print("   ⏰ 请求超时（120秒）")
except Exception as e:
    print(f"   ❌ 异常: {e}")

print("\n测试完成!")
