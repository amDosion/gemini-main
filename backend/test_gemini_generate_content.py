"""
测试 gemini-3-pro-image-preview 使用 generate_content 方法

根据 Google Cloud Console 的示例，该模型应该使用 generate_content 方法，
而不是 generate_images 方法。
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 gemini-3-pro-image-preview 使用 generate_content 方法")
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
    print("✅ Vertex AI 客户端初始化成功")
except Exception as e:
    print(f"❌ 错误：客户端初始化失败: {e}")
    sys.exit(1)

# 测试模型列表
test_models = [
    'gemini-3-pro-image-preview',
    'nano-banana-pro-preview',
    'gemini-2.0-flash-exp',
]

print("\n" + "="*80)
print("测试: 使用 generate_content 方法生成图片")
print("="*80)

for model_id in test_models:
    print(f"\n测试模型: {model_id}")
    print("-" * 80)
    
    try:
        # 创建内容
        text_part = types.Part.from_text(text="Generate an image of a white cat sitting on a red cushion")
        
        contents = [
            types.Content(
                role="user",
                parts=[text_part]
            )
        ]
        
        # 配置
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],  # 关键：支持图片输出
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ],
            image_config=types.ImageConfig(
                aspect_ratio="1:1",
                image_size="1K",
                output_mime_type="image/png",
            ),
        )
        
        # 调用 generate_content
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=generate_content_config,
        )
        
        # 检查响应
        if response.candidates:
            print(f"✅ 成功！收到 {len(response.candidates)} 个候选结果")
            
            for i, candidate in enumerate(response.candidates):
                if candidate.content and candidate.content.parts:
                    print(f"   候选 {i+1}: {len(candidate.content.parts)} 个部分")
                    
                    for j, part in enumerate(candidate.content.parts):
                        if hasattr(part, 'text') and part.text:
                            print(f"     部分 {j+1}: 文本 ({len(part.text)} 字符)")
                        elif hasattr(part, 'inline_data') and part.inline_data:
                            print(f"     部分 {j+1}: 图片 ({len(part.inline_data.data)} bytes, {part.inline_data.mime_type})")
                        else:
                            print(f"     部分 {j+1}: 其他类型")
        else:
            print(f"⚠️ 警告：API 调用成功，但没有返回候选结果")
            
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NOT_FOUND" in error_msg:
            print(f"❌ 失败：模型不存在 (404 NOT_FOUND)")
            print(f"   详细: {error_msg[:200]}")
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"❌ 失败：权限不足 (403 PERMISSION_DENIED)")
            print(f"   详细: {error_msg[:200]}")
        elif "400" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print(f"❌ 失败：参数错误 (400 INVALID_ARGUMENT)")
            print(f"   详细: {error_msg[:300]}")
        else:
            print(f"❌ 失败：{error_msg[:300]}")

print("\n" + "="*80)
print("测试完成")
print("="*80)

print("\n结论:")
print("- 如果 gemini-3-pro-image-preview 成功，说明它是多模态模型，使用 generate_content 方法")
print("- 如果失败，我们需要检查配置或权限")
print("- 这意味着我们的实现需要区分两种图片生成方式：")
print("  1. generate_images() - 用于 imagen-* 模型")
print("  2. generate_content() - 用于 gemini-*-image-* 模型")
