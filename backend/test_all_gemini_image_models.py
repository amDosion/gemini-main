"""
测试所有 Gemini 图片模型，找到可用的方式
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试所有 Gemini 图片模型")
print("="*80)

# 导入 Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    print("✅ Google GenAI SDK 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 Google GenAI SDK: {e}")
    sys.exit(1)

# 初始化客户端
try:
    client = genai.Client()
    print("✅ Vertex AI 客户端初始化成功\n")
except Exception as e:
    print(f"❌ 错误：客户端初始化失败: {e}")
    sys.exit(1)

# 所有 Gemini 图片模型
gemini_image_models = [
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-3-pro-image-preview",
]

prompt = "A red apple on a white table"

# 测试 generate_content() 方法
print("="*80)
print("测试 generate_content() 方法")
print("="*80)

for model in gemini_image_models:
    print(f"\n{'='*80}")
    print(f"测试模型: {model}")
    print(f"{'='*80}")
    
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
        
        # 检查响应
        print(f"✅ API 调用成功")
        
        if response.candidates:
            print(f"   Candidates: {len(response.candidates)}")
            
            for i, candidate in enumerate(response.candidates):
                print(f"\n   Candidate {i+1}:")
                if candidate.content and candidate.content.parts:
                    print(f"     Parts: {len(candidate.content.parts)}")
                    
                    for j, part in enumerate(candidate.content.parts):
                        print(f"     Part {j+1}:")
                        
                        # 检查文本
                        if hasattr(part, 'text') and part.text:
                            print(f"       - 文本: {part.text[:100]}...")
                        
                        # 检查图片
                        if hasattr(part, 'inline_data') and part.inline_data:
                            print(f"       - 图片: {len(part.inline_data.data)} bytes")
                            print(f"       - MIME: {part.inline_data.mime_type}")
                            print(f"\n✅✅✅ 成功生成图片！")
                            print(f"   模型: {model}")
                            print(f"   方法: generate_content()")
                        
                        # 检查其他属性
                        if hasattr(part, 'file_data') and part.file_data:
                            print(f"       - 文件数据: {part.file_data}")
        else:
            print(f"   ⚠️ 没有 candidates")
            
    except Exception as e:
        print(f"❌ 失败：{type(e).__name__}")
        print(f"   错误: {str(e)[:200]}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
