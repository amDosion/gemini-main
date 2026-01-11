"""
测试图片编辑 - 使用身体区域 mask
使用图片: D:\\gemini-main\\gemini-main\\backend\\1767011393430_edited-1767011390823-1.png
提示词: 穿上白色的袜子，黑色的衣服
"""
import os
import sys

# 设置环境变量 - 使用 Vertex AI 服务账号
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 Imagen 图片编辑功能 - 身体区域 Mask")
print("="*80)

# 导入 Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    print("✅ Google GenAI SDK 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 Google GenAI SDK: {e}")
    sys.exit(1)

# 导入 PIL 用于图片处理
try:
    from PIL import Image, ImageDraw
    import io
    print("✅ PIL 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 PIL: {e}")
    sys.exit(1)

# 初始化客户端
try:
    client = genai.Client()
    print("✅ Vertex AI 客户端初始化成功")
except Exception as e:
    print(f"❌ 错误：客户端初始化失败: {e}")
    sys.exit(1)

# 读取测试图片
test_image_path = r'D:\gemini-main\gemini-main\backend\1767011393430_edited-1767011390823-1.png'

print(f"\n读取测试图片: {test_image_path}")

if not os.path.exists(test_image_path):
    print(f"❌ 错误：图片文件不存在: {test_image_path}")
    sys.exit(1)

try:
    # 读取原始图片
    original_image = Image.open(test_image_path)
    width, height = original_image.size
    
    print(f"✅ 图片读取成功")
    print(f"   原始尺寸: {width}x{height}")
    print(f"   图片格式: {original_image.format}")
    print(f"   图片模式: {original_image.mode}")
    
    # 转换为 RGB 模式（如果需要）
    if original_image.mode != 'RGB':
        original_image = original_image.convert('RGB')
        print(f"   已转换为 RGB 模式")
    
    # 调整图片大小以满足 API 限制（最大 27MB）
    max_dimension = 2048
    if width > max_dimension or height > max_dimension:
        scale = min(max_dimension / width, max_dimension / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        print(f"   调整尺寸: {new_width}x{new_height} (缩放比例: {scale:.2f})")
        original_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        width, height = new_width, new_height
    
    # 保存为 JPEG 以减小文件大小
    img_bytes = io.BytesIO()
    original_image.save(img_bytes, format='JPEG', quality=85, optimize=True)
    original_image_bytes = img_bytes.getvalue()
    
    print(f"   压缩后大小: {len(original_image_bytes)} bytes ({len(original_image_bytes) / 1024 / 1024:.2f} MB)")
    
except Exception as e:
    print(f"❌ 错误：无法读取图片: {e}")
    sys.exit(1)

# 创建身体区域的 mask（覆盖衣服和袜子区域）
def create_body_mask(width, height):
    """
    创建覆盖身体区域的 mask
    假设人物在图片中央，mask 覆盖身体和腿部区域
    """
    mask_img = Image.new('L', (width, height), color=0)  # 黑色背景
    draw = ImageDraw.Draw(mask_img)
    
    # 创建一个覆盖身体中央区域的 mask
    # 假设人物占据图片的中央 60% 宽度，从顶部 20% 到底部 90%
    center_x = width // 2
    
    # 身体区域（上半身）
    body_left = int(width * 0.25)
    body_right = int(width * 0.75)
    body_top = int(height * 0.15)
    body_bottom = int(height * 0.55)
    
    # 腿部区域（下半身）
    legs_left = int(width * 0.30)
    legs_right = int(width * 0.70)
    legs_top = int(height * 0.50)
    legs_bottom = int(height * 0.95)
    
    # 画身体区域（白色 = 要编辑的区域）
    draw.rectangle([body_left, body_top, body_right, body_bottom], fill=255)
    
    # 画腿部区域
    draw.rectangle([legs_left, legs_top, legs_right, legs_bottom], fill=255)
    
    # 转换为 bytes
    mask_bytes = io.BytesIO()
    mask_img.save(mask_bytes, format='PNG')
    mask_bytes.seek(0)
    
    # 保存 mask 用于查看
    mask_img.save('test_body_mask_preview.png')
    print(f"   Mask 预览已保存到: test_body_mask_preview.png")
    
    return mask_bytes.read()

try:
    mask_image_bytes = create_body_mask(width, height)
    print(f"✅ Mask 创建成功")
    print(f"   Mask 大小: {len(mask_image_bytes)} bytes")
except Exception as e:
    print(f"❌ 错误：无法创建 mask: {e}")
    sys.exit(1)

# 测试编辑
model_name = 'imagen-3.0-capability-001'
prompt = "穿上白色的袜子，黑色的衣服"

print("\n" + "="*80)
print(f"测试模型: {model_name}")
print("="*80)

try:
    # 创建参考图片
    raw_image = types.RawReferenceImage(
        reference_id=1,
        reference_image=types.Image(image_bytes=original_image_bytes)
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
    
    # 配置 - 使用最佳质量输出
    edit_config = types.EditImageConfig(
        edit_mode='EDIT_MODE_INPAINT_INSERTION',
        number_of_images=2,
        aspect_ratio="1:1",
        output_mime_type="image/jpeg",
        output_compression_quality=100  # 最佳质量
    )
    
    print(f"\n编辑配置:")
    print(f"  模型: {model_name}")
    print(f"  编辑模式: INPAINT_INSERTION")
    print(f"  Mask 模式: FOREGROUND (编辑白色区域)")
    print(f"  生成数量: 2")
    print(f"  输出格式: JPEG")
    print(f"  输出质量: 100 (最佳)")
    print(f"  提示词: {prompt}")
    
    # 调用 edit_image API
    print(f"\n开始编辑...")
    response = client.models.edit_image(
        model=model_name,
        prompt=prompt,
        reference_images=[raw_image, mask_image],
        config=edit_config
    )
    
    if response.generated_images:
        print(f"\n✅ 成功！生成了 {len(response.generated_images)} 张图片")
        
        for i, img in enumerate(response.generated_images):
            # 检查是否被过滤
            if hasattr(img, 'rai_filtered_reason') and img.rai_filtered_reason:
                print(f"   ⚠️ 图片 {i+1} 被过滤: {img.rai_filtered_reason}")
                continue
            
            if img.image and img.image.image_bytes:
                print(f"   图片 {i+1}: {len(img.image.image_bytes)} bytes ({len(img.image.image_bytes) / 1024 / 1024:.2f} MB)")
                
                # 保存图片（最佳质量）
                filename = f"test_body_edit_result_{i+1}.jpg"
                with open(filename, 'wb') as f:
                    f.write(img.image.image_bytes)
                print(f"   已保存到: {filename}")
    else:
        print(f"\n⚠️ 警告：API 调用成功，但没有生成图片")
        
except Exception as e:
    error_msg = str(e)
    print(f"\n❌ 失败：{error_msg[:500]}")
    
    # 打印完整错误用于调试
    import traceback
    print("\n完整错误信息:")
    traceback.print_exc()

print("\n" + "="*80)
print("测试完成")
print("="*80)
print("\n生成的文件:")
print("  - test_body_mask_preview.png (mask 预览)")
print("  - test_body_edit_result_*.jpg (编辑后的图片)")
