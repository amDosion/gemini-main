"""
测试 imagen-3.0-capability-001 编辑功能（带 mask）
"""
import os
import sys
import base64

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 imagen-3.0-capability-001 编辑功能（带 mask）")
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

# 创建测试图片
def create_test_images():
    """创建测试图片和 mask"""
    from PIL import Image
    import io
    
    # 创建 512x512 白色图片
    base_img = Image.new('RGB', (512, 512), color='white')
    
    # 创建 mask（中心区域为白色，其他为黑色）
    mask_img = Image.new('L', (512, 512), color=0)  # 黑色背景
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask_img)
    # 在中心画一个白色圆形
    draw.ellipse([156, 156, 356, 356], fill=255)
    
    # 转换为 bytes
    base_bytes = io.BytesIO()
    base_img.save(base_bytes, format='PNG')
    base_bytes.seek(0)
    
    mask_bytes = io.BytesIO()
    mask_img.save(mask_bytes, format='PNG')
    mask_bytes.seek(0)
    
    return base_bytes.read(), mask_bytes.read()

# 测试编辑功能
print("\n" + "="*80)
print("测试: 使用 edit_image 方法（INPAINT_INSERTION 模式）")
print("="*80)

model_id = 'publishers/google/models/imagen-3.0-capability-001'

try:
    # 创建测试图片
    base_image_bytes, mask_image_bytes = create_test_images()
    
    print(f"✅ 创建测试图片成功")
    print(f"   基础图片: {len(base_image_bytes)} bytes")
    print(f"   Mask 图片: {len(mask_image_bytes)} bytes")
    
    # 创建参考图片
    raw_image = types.RawReferenceImage(
        reference_id=1,
        reference_image=types.Image(image_bytes=base_image_bytes)
    )
    
    # 创建 mask 图片
    mask_image = types.MaskReferenceImage(
        reference_id=2,
        config=types.MaskReferenceConfig(
            mask_mode='MASK_MODE_FOREGROUND',
            mask_dilation=0.0
        ),
        reference_image=types.Image(image_bytes=mask_image_bytes)
    )
    
    # 配置
    edit_config = types.EditImageConfig(
        edit_mode='EDIT_MODE_INPAINT_INSERTION',
        number_of_images=1,
        aspect_ratio="1:1",
        output_mime_type="image/png",
    )
    
    print(f"\n测试模型: {model_id}")
    print(f"编辑模式: INPAINT_INSERTION")
    print(f"Mask 模式: FOREGROUND")
    print(f"提示词: A red circle")
    
    # 调用 edit_image
    response = client.models.edit_image(
        model=model_id,
        prompt="A red circle",
        reference_images=[raw_image, mask_image],
        config=edit_config
    )
    
    if response.generated_images:
        print(f"\n✅ 成功！生成了 {len(response.generated_images)} 张图片")
        
        for i, img in enumerate(response.generated_images):
            if img.image and img.image.image_bytes:
                print(f"   图片 {i+1}: {len(img.image.image_bytes)} bytes")
                
                # 保存图片
                filename = f"test_edit_inpaint_{i+1}.png"
                with open(filename, 'wb') as f:
                    f.write(img.image.image_bytes)
                print(f"   已保存到: {filename}")
            
            # 检查是否被过滤
            if hasattr(img, 'rai_filtered_reason') and img.rai_filtered_reason:
                print(f"   ⚠️ 图片 {i+1} 被过滤: {img.rai_filtered_reason}")
    else:
        print(f"\n⚠️ 警告：API 调用成功，但没有生成图片")
        
except Exception as e:
    error_msg = str(e)
    if "404" in error_msg or "NOT_FOUND" in error_msg:
        print(f"\n❌ 失败：模型不存在 (404 NOT_FOUND)")
        print(f"   详细: {error_msg[:300]}")
    elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
        print(f"\n❌ 失败：权限不足 (403 PERMISSION_DENIED)")
        print(f"   详细: {error_msg[:300]}")
    elif "400" in error_msg or "INVALID_ARGUMENT" in error_msg:
        print(f"\n❌ 失败：参数错误 (400 INVALID_ARGUMENT)")
        print(f"   详细: {error_msg[:500]}")
    else:
        print(f"\n❌ 失败：{error_msg[:500]}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
