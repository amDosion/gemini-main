"""
测试使用真实图片进行编辑（基于官方 Gemini 3 Pro Image 示例）
使用图片: D:\\gemini-main\\gemini-main\\testimg\\PhotoshopExtension_Image (1).png
"""
import os
import sys
import base64
from pathlib import Path

# 设置环境变量 - 使用 Vertex AI 服务账号
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 Gemini 3 Pro Image 编辑功能（基于官方示例）")
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

# 初始化客户端（使用 Vertex AI 服务账号）
try:
    client = genai.Client()
    print("✅ Vertex AI 客户端初始化成功（服务账号模式）")
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
    print(f"   图片尺寸: {width}x{height}")
    print(f"   图片格式: {original_image.format}")
    print(f"   图片模式: {original_image.mode}")
    
    # 转换为 RGB 模式（如果需要）
    if original_image.mode != 'RGB':
        original_image = original_image.convert('RGB')
        print(f"   已转换为 RGB 模式")
    
    # 保存为临时文件以便上传
    temp_image_path = 'temp_test_image.jpg'
    original_image.save(temp_image_path, 'JPEG', quality=95)
    print(f"   临时文件已保存: {temp_image_path}")
    
except Exception as e:
    print(f"❌ 错误：无法读取图片: {e}")
    sys.exit(1)

# 创建 mask（在图片中心区域）
def create_center_mask(width, height):
    """创建中心区域的 mask"""
    mask_img = Image.new('L', (width, height), color=0)  # 黑色背景
    draw = ImageDraw.Draw(mask_img)
    
    # 在中心画一个白色矩形（约占图片的 1/3）
    center_x, center_y = width // 2, height // 2
    rect_width, rect_height = width // 3, height // 3
    
    left = center_x - rect_width // 2
    top = center_y - rect_height // 2
    right = center_x + rect_width // 2
    bottom = center_y + rect_height // 2
    
    draw.rectangle([left, top, right, bottom], fill=255)
    
    # 保存 mask 用于查看
    mask_preview_path = 'test_mask_preview.png'
    mask_img.save(mask_preview_path)
    print(f"   Mask 预览已保存到: {mask_preview_path}")
    
    return mask_img

try:
    mask_image = create_center_mask(width, height)
    
    # 保存 mask 为临时文件
    temp_mask_path = 'temp_test_mask.png'
    mask_image.save(temp_mask_path)
    print(f"✅ Mask 创建成功")
    print(f"   Mask 临时文件: {temp_mask_path}")
except Exception as e:
    print(f"❌ 错误：无法创建 mask: {e}")
    sys.exit(1)

# 测试图片编辑（基于官方示例风格）
print("\n" + "="*80)
print("测试: Gemini 3 Pro Image 编辑功能")
print("="*80)

try:
    # 使用 from_uri 方式加载图片（本地文件）
    # 注意：实际使用时可能需要上传到 GCS，这里先尝试本地路径
    
    # 方法1：尝试使用本地文件路径
    print("\n尝试方法1: 使用本地文件路径...")
    try:
        image1 = types.Part.from_uri(
            file_uri=f"file://{os.path.abspath(temp_image_path)}",
            mime_type="image/jpeg"
        )
        
        mask1 = types.Part.from_uri(
            file_uri=f"file://{os.path.abspath(temp_mask_path)}",
            mime_type="image/png"
        )
        
        print("✅ 本地文件路径加载成功")
    except Exception as e:
        print(f"⚠️  本地文件路径失败: {e}")
        print("\n尝试方法2: 使用 base64 编码...")
        
        # 方法2：使用 base64 编码
        with open(temp_image_path, 'rb') as f:
            image_bytes = f.read()
        with open(temp_mask_path, 'rb') as f:
            mask_bytes = f.read()
        
        image1 = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )
        
        mask1 = types.Part.from_bytes(
            data=mask_bytes,
            mime_type="image/png"
        )
        
        print("✅ Base64 编码加载成功")
    
    # 创建文本提示
    text1 = types.Part.from_text(
        text="Replace the center area with a beautiful red rose with green leaves"
    )
    
    # 模型名称 - 使用可用的 Gemini 图片模型
    model = "gemini-2.5-flash-image-preview"
    
    # 创建内容
    contents = [
        types.Content(
            role="user",
            parts=[image1, mask1, text1]
        )
    ]
    
    # 生成配置（基于官方示例）
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=32768,
        response_modalities=["TEXT", "IMAGE"],
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            )
        ],
        image_config=types.ImageConfig(
            aspect_ratio="1:1",
            image_size="1K",
            output_mime_type="image/png"
        )
    )
    
    print(f"\n配置:")
    print(f"  模型: {model}")
    print(f"  温度: 1.0")
    print(f"  Top P: 0.95")
    print(f"  图片尺寸: 1K")
    print(f"  输出格式: PNG")
    print(f"  提示词: Replace the center area with a beautiful red rose with green leaves")
    
    print(f"\n开始生成...")
    
    # 使用流式生成
    result_text = ""
    result_images = []
    
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config
    ):
        if chunk.text:
            result_text += chunk.text
            print(chunk.text, end="")
        
        # 检查是否有图片
        if hasattr(chunk, 'candidates') and chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            result_images.append(part.inline_data.data)
    
    print("\n")
    
    if result_text:
        print(f"✅ 生成的文本: {result_text}")
    
    if result_images:
        print(f"✅ 成功生成 {len(result_images)} 张图片")
        
        for i, image_data in enumerate(result_images):
            filename = f"test_gemini_edit_result_{i+1}.png"
            with open(filename, 'wb') as f:
                f.write(image_data)
            print(f"   图片 {i+1} 已保存到: {filename}")
    else:
        print("⚠️  没有生成图片")
    
except Exception as e:
    print(f"\n❌ 失败：{str(e)}")
    import traceback
    print("\n完整错误信息:")
    traceback.print_exc()

# 清理临时文件
try:
    if os.path.exists(temp_image_path):
        os.remove(temp_image_path)
    if os.path.exists(temp_mask_path):
        os.remove(temp_mask_path)
    print("\n✅ 临时文件已清理")
except:
    pass

print("\n" + "="*80)
print("测试完成")
print("="*80)
print("\n生成的文件:")
print("  - test_mask_preview.png (mask 预览)")
print("  - test_gemini_edit_result_*.png (编辑后的图片)")
