"""
测试后端返回的元数据字段

专门用于验证 CaseConversionMiddleware 是否正确转换了 data 字段内部的键名
"""
import requests
import json
import base64
import uuid
import sys

# ==================== 配置 ====================
BASE_URL = "http://localhost:21574"
LOGIN_EMAIL = "121802744@qq.com"
LOGIN_PASSWORD = "chuan*1127"
MODEL_ID = "gemini-3-pro-image-preview"
TEST_IMAGE_URL = "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"


def login() -> str:
    """登录获取 token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        timeout=30
    )
    if response.status_code != 200:
        print(f"❌ 登录失败: {response.text}")
        sys.exit(1)
    return response.json().get("accessToken")


def download_image() -> tuple:
    """下载测试图片"""
    response = requests.get(TEST_IMAGE_URL, timeout=30)
    if response.status_code != 200:
        print(f"❌ 下载图片失败")
        sys.exit(1)
    
    image_bytes = response.content
    content_type = response.headers.get("Content-Type", "image/jpeg")
    base64_str = base64.b64encode(image_bytes).decode('utf-8')
    data_url = f"data:{content_type};base64,{base64_str}"
    return data_url, content_type


def send_request(token: str, image_data_url: str, mime_type: str) -> dict:
    """发送 image-chat-edit 请求"""
    attachment_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    
    request_body = {
        "modelId": MODEL_ID,
        "prompt": "Add a colorful artistic border to this image",
        "attachments": [{
            "id": attachment_id,
            "name": "test-image.jpg",
            "mimeType": mime_type,
            "url": image_data_url,
        }],
        "options": {
            "enableSearch": False,
            "enableThinking": False,
            "imageAspectRatio": "1:1",
            "imageResolution": "1K",
            "numberOfImages": 1,
            "outputMimeType": "image/png",
            "frontendSessionId": session_id,
            "sessionId": session_id,
            "messageId": message_id,
        },
    }
    
    print(f"\n📤 发送请求...")
    print(f"   sessionId: {session_id}")
    print(f"   messageId: {message_id}")
    print(f"   attachmentId: {attachment_id}")
    
    response = requests.post(
        f"{BASE_URL}/api/modes/google/image-chat-edit",
        json=request_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        timeout=180
    )
    
    return response


def analyze_response(response):
    """分析响应，打印所有字段名"""
    print(f"\n📥 响应状态码: {response.status_code}")
    
    try:
        data = response.json()
    except:
        print(f"❌ 无法解析 JSON: {response.text[:500]}")
        return
    
    print(f"\n========== 原始响应结构 ==========")
    print(f"顶层字段: {list(data.keys())}")
    
    if "data" in data:
        inner_data = data["data"]
        print(f"\ndata 字段类型: {type(inner_data).__name__}")
        
        if isinstance(inner_data, dict):
            print(f"data 内部字段: {list(inner_data.keys())}")
            
            if "images" in inner_data:
                images = inner_data["images"]
                print(f"\nimages 数量: {len(images)}")
                
                if images:
                    img = images[0]
                    print(f"\n========== 第一张图片的所有字段 ==========")
                    print(f"字段名列表: {list(img.keys())}")
                    
                    print(f"\n========== 关键元数据字段检查 ==========")
                    
                    # 检查 camelCase 格式
                    camel_fields = ['attachmentId', 'messageId', 'sessionId', 'userId', 'uploadStatus', 'taskId', 'cloudUrl', 'mimeType', 'createdAt']
                    print(f"\ncamelCase 格式字段:")
                    for field in camel_fields:
                        value = img.get(field)
                        if value is not None:
                            if isinstance(value, str) and len(value) > 50:
                                print(f"  ✅ {field}: {value[:50]}...")
                            else:
                                print(f"  ✅ {field}: {value}")
                        else:
                            print(f"  ❌ {field}: 不存在")
                    
                    # 检查 snake_case 格式
                    snake_fields = ['attachment_id', 'message_id', 'session_id', 'user_id', 'upload_status', 'task_id', 'cloud_url', 'mime_type', 'created_at']
                    print(f"\nsnake_case 格式字段:")
                    for field in snake_fields:
                        value = img.get(field)
                        if value is not None:
                            if isinstance(value, str) and len(value) > 50:
                                print(f"  ✅ {field}: {value[:50]}...")
                            else:
                                print(f"  ✅ {field}: {value}")
                        else:
                            print(f"  ❌ {field}: 不存在")
                    
                    # 打印完整的图片对象（不包含 url）
                    print(f"\n========== 完整图片对象（不含 url）==========")
                    img_copy = {k: v for k, v in img.items() if k != 'url'}
                    for k, v in img_copy.items():
                        if isinstance(v, str) and len(v) > 100:
                            print(f"  {k}: {v[:100]}...")
                        elif isinstance(v, list):
                            print(f"  {k}: [列表, {len(v)} 项]")
                        else:
                            print(f"  {k}: {v}")
    
    print(f"\n========== 结论 ==========")
    if response.status_code == 200 and "data" in data and "images" in data.get("data", {}):
        images = data["data"]["images"]
        if images:
            img = images[0]
            # 检查是 camelCase 还是 snake_case
            has_camel = 'attachmentId' in img
            has_snake = 'attachment_id' in img
            
            if has_camel and not has_snake:
                print("✅ 后端返回 camelCase 格式（CaseConversionMiddleware 正常工作）")
            elif has_snake and not has_camel:
                print("⚠️ 后端返回 snake_case 格式（CaseConversionMiddleware 未转换 data 内部字段）")
                print("   原因: 'data' 在 SKIP_VALUE_CONVERSION_FIELDS 中")
            elif has_camel and has_snake:
                print("⚠️ 后端同时返回两种格式（异常情况）")
            else:
                print("❌ 后端未返回 attachmentId 或 attachment_id 字段")
    else:
        print("❌ 请求失败或响应格式异常")


def main():
    print("=" * 60)
    print("  测试后端返回的元数据字段格式")
    print("=" * 60)
    
    # 1. 登录
    print("\n📝 Step 1: 登录...")
    token = login()
    print(f"   ✅ 登录成功")
    
    # 2. 下载图片
    print("\n📝 Step 2: 下载测试图片...")
    image_data_url, mime_type = download_image()
    print(f"   ✅ 下载成功")
    
    # 3. 发送请求
    print("\n📝 Step 3: 发送 image-chat-edit 请求...")
    response = send_request(token, image_data_url, mime_type)
    
    # 4. 分析响应
    print("\n📝 Step 4: 分析响应...")
    analyze_response(response)
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
