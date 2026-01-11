"""
测试 nano-banana-pro-preview 模型在 Vertex AI 中的可用性

使用环境变量配置 Vertex AI 客户端
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 nano-banana-pro-preview 模型在 Vertex AI 中的可用性")
print("="*80)

print("\n环境变量配置:")
print(f"  GOOGLE_GENAI_USE_VERTEXAI: {os.environ['GOOGLE_GENAI_USE_VERTEXAI']}")
print(f"  GOOGLE_CLOUD_PROJECT: {os.environ['GOOGLE_CLOUD_PROJECT']}")
print(f"  GOOGLE_CLOUD_LOCATION: {os.environ['GOOGLE_CLOUD_LOCATION']}")
print(f"  GOOGLE_APPLICATION_CREDENTIALS: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")

# 检查 credentials 文件是否存在
if not os.path.exists(os.environ['GOOGLE_APPLICATION_CREDENTIALS']):
    print(f"\n❌ 错误：Credentials 文件不存在")
    print(f"   路径: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
    sys.exit(1)

print(f"\n✅ Credentials 文件存在")

# 导入 Google GenAI SDK
try:
    from google import genai
    print("✅ Google GenAI SDK 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 Google GenAI SDK: {e}")
    sys.exit(1)

# 初始化客户端（使用环境变量）
try:
    client = genai.Client()
    print("✅ Vertex AI 客户端初始化成功")
except Exception as e:
    print(f"❌ 错误：客户端初始化失败: {e}")
    sys.exit(1)

# 测试模型列表
test_models = [
    'nano-banana-pro-preview',
    'nano-banana-pro',
    'gemini-3-pro-image-preview',
    'imagen-3.0-generate-001',
    'imagen-3.0-capability-001',
]

print("\n" + "="*80)
print("测试 1: 图片生成 (generate_images)")
print("="*80)

for model_id in test_models:
    print(f"\n测试模型: {model_id}")
    print("-" * 80)
    
    try:
        # 尝试生成图片
        response = client.models.generate_images(
            model=model_id,
            prompt="A white cat",
            config=genai.types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio='1:1',
                output_mime_type='image/png',
                include_rai_reason=True,
            )
        )
        
        if response.generated_images:
            print(f"✅ 成功！生成了 {len(response.generated_images)} 张图片")
            print(f"   图片大小: {len(response.generated_images[0].image.image_bytes)} bytes")
            
            # 检查是否有 RAI 信息
            if hasattr(response.generated_images[0], 'rai_filtered_reason'):
                print(f"   RAI 过滤原因: {response.generated_images[0].rai_filtered_reason}")
        else:
            print(f"⚠️ 警告：API 调用成功，但没有返回图片")
            
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NOT_FOUND" in error_msg:
            print(f"❌ 失败：模型不存在 (404 NOT_FOUND)")
            print(f"   详细错误: {error_msg[:200]}")
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"❌ 失败：权限不足 (403 PERMISSION_DENIED)")
            print(f"   详细错误: {error_msg[:200]}")
        elif "400" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print(f"❌ 失败：参数错误 (400 INVALID_ARGUMENT)")
            print(f"   详细错误: {error_msg[:200]}")
        else:
            print(f"❌ 失败：{error_msg[:200]}")

print("\n" + "="*80)
print("测试 2: 图片编辑 (edit_image)")
print("="*80)

# 创建测试图片（简单的 1x1 像素图片）
import base64
# 1x1 白色 PNG 图片
test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
test_image_bytes = base64.b64decode(test_image_base64)

# 只测试支持编辑的模型
edit_test_models = [
    'nano-banana-pro-preview',
    'imagen-3.0-capability-001',
]

for model_id in edit_test_models:
    print(f"\n测试模型: {model_id}")
    print("-" * 80)
    
    try:
        # 创建参考图片
        raw_ref_image = genai.types.RawReferenceImage(
            reference_id=1,
            reference_image=genai.types.Image(image_bytes=test_image_bytes),
        )
        
        mask_ref_image = genai.types.MaskReferenceImage(
            reference_id=2,
            config=genai.types.MaskReferenceConfig(
                mask_mode='MASK_MODE_BACKGROUND',
                mask_dilation=0.06,
            ),
        )
        
        # 尝试编辑图片
        response = client.models.edit_image(
            model=model_id,
            prompt="Change to a black cat",
            reference_images=[raw_ref_image, mask_ref_image],
            config=genai.types.EditImageConfig(
                edit_mode=genai.types.EditMode.EDIT_MODE_INPAINT_INSERTION,
                number_of_images=1,
                include_rai_reason=True,
            )
        )
        
        if response.generated_images:
            print(f"✅ 成功！编辑了 {len(response.generated_images)} 张图片")
            print(f"   图片大小: {len(response.generated_images[0].image.image_bytes)} bytes")
        else:
            print(f"⚠️ 警告：API 调用成功，但没有返回图片")
            
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NOT_FOUND" in error_msg:
            print(f"❌ 失败：模型不存在 (404 NOT_FOUND)")
            print(f"   详细错误: {error_msg[:200]}")
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"❌ 失败：权限不足 (403 PERMISSION_DENIED)")
            print(f"   详细错误: {error_msg[:200]}")
        elif "400" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print(f"❌ 失败：参数错误 (400 INVALID_ARGUMENT)")
            print(f"   详细错误: {error_msg[:200]}")
        else:
            print(f"❌ 失败：{error_msg[:200]}")

print("\n" + "="*80)
print("测试完成")
print("="*80)

print("\n结论:")
print("- 如果 nano-banana-pro-preview 返回 404，说明 Vertex AI 不支持该模型，需要模型映射")
print("- 如果 nano-banana-pro-preview 成功，说明 Vertex AI 支持该模型，可以直接使用")
print("- 如果返回其他错误（如 400），可能是参数问题，需要进一步调试")
