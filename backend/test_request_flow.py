"""
测试完整的请求流程和日志输出

模拟前端请求到后端，验证所有日志都能在终端显示
"""

import sys
import os
import asyncio
import requests
import json

# 设置 Windows 控制台编码为 UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 后端地址
BACKEND_URL = "http://localhost:21574"

def get_user_token(email: str, password: str) -> str:
    """获取用户 token"""
    print(f"\n{'='*80}")
    print(f"[测试] 步骤1: 获取用户 Token")
    print(f"{'='*80}")
    print(f"  邮箱: {email}")
    print(f"  密码: {'*' * len(password)}")
    
    # 尝试登录获取 token
    login_url = f"{BACKEND_URL}/api/auth/login"
    response = requests.post(
        login_url,
        json={"email": email, "password": password},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        if token:
            print(f"  [OK] Token 获取成功: {token[:20]}...")
            return token
        else:
            print(f"  [ERROR] 响应中没有 access_token")
            print(f"  响应: {data}")
            return None
    else:
        print(f"  [ERROR] 登录失败: {response.status_code}")
        print(f"  响应: {response.text}")
        return None

def test_image_gen_request(token: str):
    """测试图片生成请求"""
    print(f"\n{'='*80}")
    print(f"[测试] 步骤2: 发送图片生成请求")
    print(f"{'='*80}")
    print(f"  URL: {BACKEND_URL}/api/modes/google/image-gen")
    print(f"  Token: {token[:20]}...")
    
    # 构建请求
    url = f"{BACKEND_URL}/api/modes/google/image-gen"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # 请求体
    request_body = {
        "modelId": "imagen-4.0-generate-preview-06-06",
        "prompt": "欧洲女子",
        "attachments": [],
        "options": {
            "numberOfImages": 1,
            "aspectRatio": "1:1",
            "imageResolution": "1K"
        },
        "extra": {}
    }
    
    print(f"\n  请求参数:")
    print(f"    - modelId: {request_body['modelId']}")
    print(f"    - prompt: {request_body['prompt']}")
    print(f"    - numberOfImages: {request_body['options']['numberOfImages']}")
    print(f"    - aspectRatio: {request_body['options']['aspectRatio']}")
    
    print(f"\n  [SEND] 发送请求...")
    print(f"  {'='*80}")
    print(f"  [INFO] 请观察后端终端输出，应该能看到完整的日志链：")
    print(f"      [Request] -> [Auth] -> [Modes] -> [CredentialManager] ->")
    print(f"      [ProviderFactory] -> [GoogleService] -> [ImageGenerator] ->")
    print(f"      [ImagenCoordinator] -> [GeminiAPIImageGenerator]")
    print(f"  {'='*80}\n")
    
    try:
        response = requests.post(
            url,
            json=request_body,
            headers=headers,
            timeout=120  # 图片生成可能需要较长时间
        )
        
        print(f"\n  [OK] 请求完成")
        print(f"  状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  [OK] 请求成功")
            if isinstance(data, dict) and "data" in data:
                images = data["data"]
                if isinstance(images, list):
                    print(f"  [OK] 返回图片数量: {len(images)}")
                    for idx, img in enumerate(images):
                        if isinstance(img, dict):
                            print(f"    图片 {idx+1}:")
                            print(f"      - attachmentId: {img.get('attachmentId', 'N/A')[:20]}...")
                            print(f"      - uploadStatus: {img.get('uploadStatus', 'N/A')}")
                            print(f"      - url: {img.get('url', 'N/A')[:60]}...")
                else:
                    print(f"  响应数据: {data}")
            else:
                print(f"  响应数据: {data}")
        else:
            print(f"  [ERROR] 请求失败")
            print(f"  响应: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"  [WARN] 请求超时（图片生成可能需要更长时间）")
    except Exception as e:
        print(f"  [ERROR] 请求异常: {e}")

def main():
    """主函数"""
    print("="*80)
    print("测试完整的请求流程和日志输出")
    print("="*80)
    
    # 用户信息
    email = "user1@example.com"
    password = "user1pass123"
    
    # 步骤1: 获取 token
    token = get_user_token(email, password)
    if not token:
        print("\n[ERROR] 无法获取 token，请检查：")
        print("  1. 用户是否存在（使用 create_user.py 创建）")
        print("  2. 后端服务是否运行")
        print("  3. 密码是否正确")
        return
    
    # 步骤2: 测试图片生成请求
    test_image_gen_request(token)
    
    print(f"\n{'='*80}")
    print("测试完成")
    print("="*80)
    print("\n请检查后端终端输出，确认所有日志都已显示：")
    print("  [OK] [Request] 中间件日志")
    print("  [OK] [Auth] 认证日志")
    print("  [OK] [Modes] 路由处理日志")
    print("  [OK] [CredentialManager] 凭证获取日志")
    print("  [OK] [ProviderFactory] 服务创建日志")
    print("  [OK] [GoogleService] 服务层日志")
    print("  [OK] [ImageGenerator] 生成器日志")
    print("  [OK] [ImagenCoordinator] 协调器日志")
    print("  [OK] [GeminiAPIImageGenerator] 实际生成器日志")

if __name__ == "__main__":
    main()
