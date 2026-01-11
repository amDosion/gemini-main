"""
测试使用真实图片进行编辑（使用 Imagen 编辑 API）
使用图片: D:\\gemini-main\\gemini-main\\testimg\\PhotoshopExtension_Image (1).png
"""
import os
import sys

# 设置环境变量 - 使用 Vertex AI 服务账号
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 Imagen 图片编辑功能")
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
test_image_path = r'D:\gemini-main\gemini-main\testimg\PhotoshopExtension_Image (1).png'

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
    # 目标：压缩到约 2048x2048 或更小
    max_dimension = 2048
    if width > max_dimension or height > max_dimension:
        # 计算缩放比例
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
    
    if len(original_image_bytes) > 27000000:
        print(f"   ⚠️ 警告：图片仍然太大，尝试更高压缩...")
        img_bytes = io.BytesIO()
        original_image.save(img_bytes, format='JPEG', quality=70, optimize=True)
        original_image_bytes = img_bytes.getvalue()
        print(f"   再次压缩后: {len(original_image_bytes)} bytes ({len(original_image_bytes) / 1024 / 1024:.2f} MB)")
    
except Exception as e:
    print(f"❌ 错误：无法读取图片: {e}")
    sys.exit(1)

# 创建 mask（在图片中心区域）
def create_center_mask(width, height):
    """创建中心区域的 mask"""
    mask_img = Image.new('L', (width, height), color=0)  # 黑色背景
    draw = ImageDraw.Draw(mask_img)
    
    # 在中心画一个白色矩形（约占图片的 1/4）
    center_x, center_y = width // 2, height // 2
    rect_width, rect_height = width // 4, height // 4
    
    left = center_x - rect_width // 2
    top = center_y - rect_height // 2
    right = center_x + rect_width // 2
    bottom = center_y + rect_height // 2
    
    draw.rectangle([left, top, right, bottom], fill=255)
    
    # 转换为 bytes
    mask_bytes = io.BytesIO()
    mask_img.save(mask_bytes, format='PNG')
    mask_bytes.seek(0)
    
    # 保存 mask 用于查看
    mask_img.save('test_mask_preview.png')
    print(f"   Mask 预览已保存到: test_mask_preview.png")
    
    return mask_bytes.read()

try:
    mask_image_bytes = create_center_mask(width, height)
    print(f"✅ Mask 创建成功")
    print(f"   Mask 大小: {len(mask_image_bytes)} bytes")
except Exception as e:
    print(f"❌ 错误：无法创建 mask: {e}")
    sys.exit(1)

# 测试 Imagen 编辑模型
test_models = [
    'imagen-3.0-capability-001',
    'imagen-3.0-capability-002',
]

for model_name in test_models:
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
        
        # 配置
        edit_config = types.EditImageConfig(
            edit_mode='EDIT_MODE_INPAINT_INSERTION',
            number_of_images=2,
            aspect_ratio="1:1",
            output_mime_type="image/png",
        )
        
        print(f"\n编辑配置:")
        print(f"  编辑模式: INPAINT_INSERTION")
        print(f"  Mask 模式: FOREGROUND")
        print(f"  生成数量: 2")
        print(f"  提示词: A beautiful red rose with green leaves")
        
        # 调用 edit_image API
        response = client.models.edit_image(
            model=model_name,
            prompt="A beautiful red rose with green leaves",
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
                    print(f"   图片 {i+1}: {len(img.image.image_bytes)} bytes")
                    
                    # 保存图片
                    filename = f"test_imagen_edit_{model_name.replace('/', '_')}_{i+1}.png"
                    with open(filename, 'wb') as f:
                        f.write(img.image.image_bytes)
                    print(f"   已保存到: {filename}")
        else:
            print(f"\n⚠️ 警告：API 调用成功，但没有生成图片")
            
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NOT_FOUND" in error_msg:
            print(f"\n❌ 失败：模型不存在 (404 NOT_FOUND)")
            print(f"   模型 {model_name} 可能不支持编辑功能或不可用")
        elif "403" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"\n❌ 失败：权限不足 (403 PERMISSION_DENIED)")
        elif "400" in error_msg or "INVALID_ARGUMENT" in error_msg:
            print(f"\n❌ 失败：参数错误 (400 INVALID_ARGUMENT)")
            print(f"   详细: {error_msg[:500]}")
        else:
            print(f"\n❌ 失败：{error_msg[:500]}")
        
        # 打印完整错误用于调试
        import traceback
        print("\n完整错误信息:")
        traceback.print_exc()

print("\n" + "="*80)
print("测试完成")
print("="*80)
print("\n生成的文件:")
print("  - test_mask_preview.png (mask 预览)")
print("  - test_imagen_edit_*.png (编辑后的图片)")
