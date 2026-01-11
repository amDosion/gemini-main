"""
测试 Gemini 3 Pro Image Preview 在不同区域的可用性
"""
import os
import sys

# 基础配置
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 Gemini 3 Pro Image Preview 在不同区域")
print("="*80)

# 导入 Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    from google.oauth2 import service_account
    print("✅ Google GenAI SDK 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 Google GenAI SDK: {e}")
    sys.exit(1)

# 测试的区域
locations = [
    'us-central1',
    'us-east4',
    'us-west1',
    'europe-west1',
    'europe-west4',
    'asia-northeast1',
]

# 测试的模型名称格式
model_formats = [
    'gemini-3-pro-image-preview',
    'publishers/google/models/gemini-3-pro-image-preview',
]

prompt = "A red apple on a white table"

# 加载凭证
import json
with open(r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json', 'r') as f:
    credentials_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)

# 测试每个区域
for location in locations:
    print(f"\n{'='*80}")
    print(f"测试区域: {location}")
    print(f"{'='*80}")
    
    try:
        # 为每个区域创建新客户端
        client = genai.Client(
            vertexai=True,
            project='gen-lang-client-0639481221',
            location=location,
            credentials=credentials
        )
        print(f"✅ 客户端初始化成功")
        
        # 测试每种模型名称格式
        for model in model_formats:
            print(f"\n  测试模型格式: {model}")
            
            try:
                text_part = types.Part.from_text(text=prompt)
                contents = [types.Content(role="user", parts=[text_part])]
                
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        response_modalities=["TEXT", "IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio="1:1",
                            image_size="1K",
                            output_mime_type="image/png",
                        )
                    )
                )
                
                # 检查是否有图片
                has_image = False
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    has_image = True
                                    image_size = len(part.inline_data.data)
                                    break
                
                if has_image:
                    print(f"  ✅✅✅ 成功！")
                    print(f"    区域: {location}")
                    print(f"    模型: {model}")
                    print(f"    图片大小: {image_size} bytes")
                    print(f"    方法: generate_content()")
                    
                    # 保存图片
                    filename = f"test_gemini3_{location.replace('-', '_')}.png"
                    with open(filename, 'wb') as f:
                        f.write(part.inline_data.data)
                    print(f"    已保存: {filename}")
                else:
                    print(f"  ⚠️ API 调用成功但没有生成图片")
                    
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "NOT_FOUND" in error_msg:
                    print(f"  ❌ 404 - 模型在此区域不可用")
                elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                    print(f"  ❌ 403 - 权限不足")
                else:
                    print(f"  ❌ {type(e).__name__}: {error_msg[:100]}")
                    
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
