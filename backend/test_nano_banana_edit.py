"""
测试 nano-banana-pro-preview 通过 MODEL_MAPPING 编辑功能
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 nano-banana-pro-preview 编辑功能（应该映射到 imagen-3.0-capability-001）")
print("="*80)

# 导入后端服务
sys.path.insert(0, r'D:\gemini-main\gemini-main\backend')

from app.services.gemini.image_edit_vertex_ai import VertexAIImageEditor
from PIL import Image
import io
import base64

# 创建测试图片
def create_test_images():
    """创建测试图片和 mask"""
    # 创建 512x512 白色图片
    base_img = Image.new('RGB', (512, 512), color='white')
    
    # 创建 mask（中心区域为白色，其他为黑色）
    mask_img = Image.new('L', (512, 512), color=0)  # 黑色背景
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask_img)
    # 在中心画一个白色圆形
    draw.ellipse([156, 156, 356, 356], fill=255)
    
    # 转换为 Base64
    base_bytes = io.BytesIO()
    base_img.save(base_bytes, format='PNG')
    base_bytes.seek(0)
    base_b64 = base64.b64encode(base_bytes.read()).decode('utf-8')
    
    mask_bytes = io.BytesIO()
    mask_img.save(mask_bytes, format='PNG')
    mask_bytes.seek(0)
    mask_b64 = base64.b64encode(mask_bytes.read()).decode('utf-8')
    
    return base_b64, mask_b64

print("\n创建测试图片...")
base_image_b64, mask_image_b64 = create_test_images()
print(f"✅ 基础图片: {len(base_image_b64)} chars")
print(f"✅ Mask 图片: {len(mask_image_b64)} chars")

# 读取凭证
print("\n读取 Vertex AI 凭证...")
with open(r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json', 'r') as f:
    credentials_json = f.read()
print("✅ 凭证读取成功")

# 创建编辑器
print("\n初始化 VertexAIImageEditor...")
editor = VertexAIImageEditor(
    project_id='gen-lang-client-0639481221',
    location='us-central1',
    credentials_json=credentials_json
)
print("✅ 编辑器初始化成功")

# 测试编辑
print("\n" + "="*80)
print("测试: nano-banana-pro-preview 编辑功能")
print("="*80)

try:
    reference_images = {
        'raw': base_image_b64,
        'mask': mask_image_b64
    }
    
    config = {
        'model': 'nano-banana-pro-preview',  # 用户提供的模型ID
        'edit_mode': 'inpainting-insert',
        'number_of_images': 1,
        'aspect_ratio': '1:1',
        'output_mime_type': 'image/png'
    }
    
    print(f"用户模型: nano-banana-pro-preview")
    print(f"编辑模式: inpainting-insert")
    print(f"提示词: A red circle")
    print(f"\n调用 edit_image()...")
    
    results = editor.edit_image(
        prompt="A red circle",
        reference_images=reference_images,
        config=config
    )
    
    print(f"\n✅ 成功！生成了 {len(results)} 张图片")
    
    for i, result in enumerate(results):
        print(f"   图片 {i+1}:")
        print(f"     - URL: {result['url'][:100]}...")
        print(f"     - MIME: {result['mimeType']}")
        print(f"     - Size: {result['size']} bytes")
        
        # 保存图片
        import base64
        img_data = result['url'].split(',')[1]
        img_bytes = base64.b64decode(img_data)
        filename = f"test_nano_banana_edit_{i+1}.png"
        with open(filename, 'wb') as f:
            f.write(img_bytes)
        print(f"     - 已保存到: {filename}")
    
except Exception as e:
    print(f"\n❌ 失败：{str(e)[:500]}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("测试完成")
print("="*80)
print("\n结论:")
print("- 如果成功，说明 MODEL_MAPPING 正常工作")
print("- nano-banana-pro-preview 被正确映射到 imagen-3.0-capability-001")
