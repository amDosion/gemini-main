"""
测试 Nano Banana Pro Preview 的三种可能方式
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 Nano Banana Pro Preview 的三种方式")
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

# 测试的模型名称变体
model_variants = [
    "nano-banana-pro-preview",
    "nano-banana-pro",
    "publishers/google/models/nano-banana-pro-preview",
    "publishers/google/models/nano-banana-pro",
]

prompt = "A red apple on a white table"

# 方式 1: generate_images()
print("\n" + "="*80)
print("方式 1: 测试 generate_images() 方法")
print("="*80)

for model in model_variants:
    print(f"\n测试模型: {model}")
    try:
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            )
        )
        
        if response.generated_images:
            print(f"✅ 成功！生成了 {len(response.generated_images)} 张图片")
            print(f"   方法: generate_images()")
            print(f"   模型: {model}")
            break
        else:
            print(f"❌ 失败：没有生成图片")
            
    except Exception as e:
        print(f"❌ 失败：{type(e).__name__}: {str(e)[:100]}")

# 方式 2: generate_content()
print("\n" + "="*80)
print("方式 2: 测试 generate_content() 方法")
print("="*80)

for model in model_variants:
    print(f"\n测试模型: {model}")
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
                            break
        
        if has_image:
            print(f"✅ 成功！生成了图片")
            print(f"   方法: generate_content()")
            print(f"   模型: {model}")
            break
        else:
            print(f"❌ 失败：没有生成图片")
            
    except Exception as e:
        print(f"❌ 失败：{type(e).__name__}: {str(e)[:100]}")

# 方式 3: edit_image()
print("\n" + "="*80)
print("方式 3: 测试 edit_image() 方法（需要基础图片）")
print("="*80)

# 创建测试图片
from PIL import Image
import io

base_img = Image.new('RGB', (512, 512), color='white')
base_bytes = io.BytesIO()
base_img.save(base_bytes, format='PNG')
base_bytes.seek(0)

for model in model_variants:
    print(f"\n测试模型: {model}")
    try:
        raw_image = types.RawReferenceImage(
            reference_id=1,
            reference_image=types.Image(image_bytes=base_bytes.read())
        )
        
        response = client.models.edit_image(
            model=model,
            prompt=prompt,
            reference_images=[raw_image],
            config=types.EditImageConfig(
                edit_mode="EDIT_MODE_INPAINT_INSERTION",
                number_of_images=1,
            )
        )
        
        if response.generated_images:
            print(f"✅ 成功！生成了 {len(response.generated_images)} 张图片")
            print(f"   方法: edit_image()")
            print(f"   模型: {model}")
            break
        else:
            print(f"❌ 失败：没有生成图片")
            
    except Exception as e:
        print(f"❌ 失败：{type(e).__name__}: {str(e)[:100]}")
    
    # 重置 bytes
    base_bytes.seek(0)

print("\n" + "="*80)
print("测试完成")
print("="*80)
