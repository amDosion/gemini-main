"""
列出所有可用的模型，找到正确的模型名称
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("列出所有可用的 Vertex AI 模型")
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

# 列出所有模型
try:
    print("正在获取模型列表...\n")
    models = client.models.list()
    
    # 分类存储
    gemini_models = []
    imagen_models = []
    nano_models = []
    other_models = []
    
    for model in models:
        model_name = model.name
        
        if 'gemini' in model_name.lower():
            gemini_models.append(model_name)
        elif 'imagen' in model_name.lower():
            imagen_models.append(model_name)
        elif 'nano' in model_name.lower() or 'banana' in model_name.lower():
            nano_models.append(model_name)
        else:
            other_models.append(model_name)
    
    # 打印 Gemini 模型
    print("="*80)
    print(f"Gemini 模型 ({len(gemini_models)} 个)")
    print("="*80)
    for model in sorted(gemini_models):
        print(f"  - {model}")
    
    # 打印 Imagen 模型
    print("\n" + "="*80)
    print(f"Imagen 模型 ({len(imagen_models)} 个)")
    print("="*80)
    for model in sorted(imagen_models):
        print(f"  - {model}")
    
    # 打印 Nano/Banana 模型
    print("\n" + "="*80)
    print(f"Nano/Banana 模型 ({len(nano_models)} 个)")
    print("="*80)
    if nano_models:
        for model in sorted(nano_models):
            print(f"  - {model}")
    else:
        print("  ⚠️ 未找到 Nano/Banana 模型")
    
    # 打印其他模型
    print("\n" + "="*80)
    print(f"其他模型 ({len(other_models)} 个)")
    print("="*80)
    for model in sorted(other_models):
        print(f"  - {model}")
    
    # 搜索特定关键词
    print("\n" + "="*80)
    print("搜索特定关键词")
    print("="*80)
    
    keywords = ['gemini-3', 'nano', 'banana', 'preview', 'image']
    all_models = gemini_models + imagen_models + nano_models + other_models
    
    for keyword in keywords:
        matching = [m for m in all_models if keyword.lower() in m.lower()]
        if matching:
            print(f"\n包含 '{keyword}' 的模型 ({len(matching)} 个):")
            for model in sorted(matching):
                print(f"  - {model}")
    
except Exception as e:
    print(f"❌ 错误：获取模型列表失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("完成")
print("="*80)
