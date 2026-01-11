"""
获取 Gemini 3 Pro Image Preview 的详细信息
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("获取 Gemini 3 Pro Image Preview 的详细信息")
print("="*80)

# 导入 Google GenAI SDK
try:
    from google import genai
    print("✅ Google GenAI SDK 导入成功")
except ImportError as e:
    print(f"❌ 错误：无法导入 Google GenAI SDK: {e}")
    sys.exit(1)

# 初始化客户端
try:
    client = genai.Client()
    print("✅ Vertex AI 客户端初始化成功\n")
except Exception as e:
    print(f"❌ 错误：客户端初始化失败: {e}")
    sys.exit(1)

# 获取模型详细信息
model_name = "publishers/google/models/gemini-3-pro-image-preview"

try:
    print(f"正在获取模型信息: {model_name}\n")
    model = client.models.get(model=model_name)
    
    print("="*80)
    print("模型详细信息")
    print("="*80)
    print(f"名称: {model.name}")
    print(f"显示名称: {model.display_name if hasattr(model, 'display_name') else 'N/A'}")
    print(f"描述: {model.description if hasattr(model, 'description') else 'N/A'}")
    
    # 支持的方法
    if hasattr(model, 'supported_generation_methods'):
        print(f"\n支持的生成方法:")
        for method in model.supported_generation_methods:
            print(f"  - {method}")
    
    # 输入/输出模态
    if hasattr(model, 'input_modalities'):
        print(f"\n输入模态:")
        for modality in model.input_modalities:
            print(f"  - {modality}")
    
    if hasattr(model, 'output_modalities'):
        print(f"\n输出模态:")
        for modality in model.output_modalities:
            print(f"  - {modality}")
    
    # 其他属性
    print(f"\n其他属性:")
    for attr in dir(model):
        if not attr.startswith('_') and attr not in ['name', 'display_name', 'description', 'supported_generation_methods', 'input_modalities', 'output_modalities']:
            try:
                value = getattr(model, attr)
                if not callable(value):
                    print(f"  {attr}: {value}")
            except:
                pass
    
except Exception as e:
    print(f"❌ 错误：获取模型信息失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("完成")
print("="*80)
