"""
测试图片编辑 - 无 mask 模式
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
print("测试 Imagen 图片编辑功能 - 无 Mask 模式")
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
    from PIL import Image
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
    # 读取原始图片（不压缩）
    with open(test_image_path, 'rb') as f:
        original_image_bytes = f.read()
    
    # 使用 PIL 打开图片获取信息
    original_image = Image.open(test_image_path)
    width, height = original_image.size
    
    print(f"✅ 图片读取成功")
    print(f"   文件大小: {len(original_image_bytes)} bytes ({len(original_image_bytes) / 1024 / 1024:.2f} MB)")
    print(f"   图片尺寸: {width}x{height}")
    print(f"   图片格式: {original_image.format}")
    print(f"   图片模式: {original_image.mode}")
    
    # 检查文件大小
    if len(original_image_bytes) > 27000000:
        print(f"   ⚠️ 警告：图片大小超过 27MB 限制，可能会失败")
    
except Exception as e:
    print(f"❌ 错误：无法读取图片: {e}")
    sys.exit(1)

# 测试不同的编辑模式（无 mask）
print("\n" + "="*80)
print("测试: 图片编辑 - EDIT_MODE_INPAINT_REMOVAL (无 mask)")
print("="*80)

model_name = 'imagen-3.0-capability-001'
prompt = "穿上白色的袜子，黑色的衣服"

try:
    # 创建参考图片（只有原图，没有 mask）
    raw_image = types.RawReferenceImage(
        reference_id=1,
        reference_image=types.Image(image_bytes=original_image_bytes)
    )
    
    # 配置 - 使用 INPAINT_REMOVAL 模式（不需要 mask）
    edit_config = types.EditImageConfig(
        edit_mode='EDIT_MODE_INPAINT_REMOVAL',
        number_of_images=2,
        aspect_ratio="1:1",
        output_mime_type="image/jpeg",
        output_compression_quality=100  # 最佳质量（仅 JPEG 支持）
    )
    
    print(f"\n编辑配置:")
    print(f"  模型: {model_name}")
    print(f"  编辑模式: INPAINT_REMOVAL (无 mask)")
    print(f"  生成数量: 2")
    print(f"  输出格式: JPEG")
    print(f"  输出质量: 100 (最佳)")
    print(f"  提示词: {prompt}")
    
    # 调用 edit_image API
    print(f"\n开始编辑...")
    response = client.models.edit_image(
        model=model_name,
        prompt=prompt,
        reference_images=[raw_image],  # 只传入原图
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
                filename = f"test_no_mask_edit_result_{i+1}.jpg"
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

# 尝试其他编辑模式 - OUTPAINT
print("\n" + "="*80)
print("测试: 图片编辑 - EDIT_MODE_OUTPAINT (扩展图片)")
print("="*80)

try:
    # 创建参考图片
    raw_image = types.RawReferenceImage(
        reference_id=1,
        reference_image=types.Image(image_bytes=original_image_bytes)
    )
    
    # 配置 - 使用 OUTPAINT 模式
    edit_config = types.EditImageConfig(
        edit_mode='EDIT_MODE_OUTPAINT',
        number_of_images=2,
        aspect_ratio="1:1",
        output_mime_type="image/jpeg",
        output_compression_quality=100  # 最佳质量
    )
    
    print(f"\n编辑配置:")
    print(f"  模型: {model_name}")
    print(f"  编辑模式: OUTPAINT")
    print(f"  生成数量: 2")
    print(f"  输出格式: JPEG")
    print(f"  输出质量: 100 (最佳)")
    print(f"  提示词: {prompt}")
    
    # 调用 edit_image API
    print(f"\n开始编辑...")
    response = client.models.edit_image(
        model=model_name,
        prompt=prompt,
        reference_images=[raw_image],
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
                filename = f"test_outpaint_edit_result_{i+1}.jpg"
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
print("  - test_no_mask_edit_result_*.png (无 mask 编辑结果)")
print("  - test_product_mode_edit_result_*.png (产品模式编辑结果)")
