"""
列出 Vertex AI 中所有可用的模型
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("列出 Vertex AI 可用模型")
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
    print("✅ Vertex AI 客户端初始化成功")
except Exception as e:
    print(f"❌ 错误：客户端初始化失败: {e}")
    sys.exit(1)

# 列出所有模型
print("\n" + "="*80)
print("可用模型列表:")
print("="*80)

try:
    models = client.models.list()
    
    image_models = []
    text_models = []
    other_models = []
    
    for model in models:
        model_name = model.name if hasattr(model, 'name') else str(model)
        
        if 'image' in model_name.lower() or 'imagen' in model_name.lower():
            image_models.append(model_name)
        elif 'gemini' in model_name.lower() or 'text' in model_name.lower():
            text_models.append(model_name)
        else:
            other_models.append(model_name)
    
    print(f"\n📷 图片相关模型 ({len(image_models)}):")
    for model in sorted(image_models):
        print(f"  - {model}")
    
    print(f"\n📝 文本/Gemini 模型 ({len(text_models)}):")
    for model in sorted(text_models):
        print(f"  - {model}")
    
    print(f"\n🔧 其他模型 ({len(other_models)}):")
    for model in sorted(other_models):
        print(f"  - {model}")
    
    print(f"\n总计: {len(image_models) + len(text_models) + len(other_models)} 个模型")
    
except Exception as e:
    print(f"❌ 错误：无法列出模型: {e}")
    sys.exit(1)

print("\n" + "="*80)
print("完成")
print("="*80)
