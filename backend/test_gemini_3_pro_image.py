"""
测试 Gemini 3 Pro Image 模型的图片生成功能
"""
import os
import sys
import asyncio

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试 Gemini 3 Pro Image 模型")
print("="*80)

# 导入服务
try:
    from app.services.gemini.imagen_vertex_ai import VertexAIImageGenerator
    print("✅ VertexAIImageGenerator 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 VertexAIImageGenerator: {e}")
    sys.exit(1)

# 读取凭证
try:
    with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r', encoding='utf-8') as f:
        credentials_json = f.read()
    print("✅ 凭证文件读取成功")
except Exception as e:
    print(f"❌ 错误：无法读取凭证文件: {e}")
    sys.exit(1)

# 初始化生成器
try:
    generator = VertexAIImageGenerator(
        project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
        location=os.environ['GOOGLE_CLOUD_LOCATION'],
        credentials_json=credentials_json
    )
    print("✅ VertexAIImageGenerator 初始化成功")
except Exception as e:
    print(f"❌ 错误：初始化失败: {e}")
    sys.exit(1)

# 测试模型列表
print("\n" + "="*80)
print("获取支持的模型列表:")
print("="*80)

try:
    models = generator.get_supported_models()
    print(f"\n找到 {len(models)} 个图片生成模型:")
    for model in models:
        print(f"  - {model}")
except Exception as e:
    print(f"❌ 错误：无法获取模型列表: {e}")
    sys.exit(1)

# 测试图片生成
print("\n" + "="*80)
print("测试图片生成:")
print("="*80)

async def test_generation():
    # 测试不同的模型
    test_models = [
        'gemini-3-pro-image-preview',
        'imagen-3.0-generate-002'
    ]
    
    prompt = "A beautiful sunset over mountains with a lake in the foreground"
    
    for model in test_models:
        if model not in models:
            print(f"\n⚠️  跳过模型 {model} (不在支持列表中)")
            continue
        
        print(f"\n📷 测试模型: {model}")
        print(f"   提示词: {prompt}")
        
        try:
            results = await generator.generate_image(
                prompt=prompt,
                model=model,
                aspect_ratio='1:1',
                number_of_images=1
            )
            
            print(f"   ✅ 成功生成 {len(results)} 张图片")
            for idx, result in enumerate(results):
                print(f"      图片 {idx + 1}: {result['mimeType']}, 大小: {result['size']} bytes")
        
        except Exception as e:
            print(f"   ❌ 生成失败: {e}")

# 运行测试
try:
    asyncio.run(test_generation())
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("测试完成")
print("="*80)
