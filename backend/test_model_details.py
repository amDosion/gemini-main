"""
详细检查 gemini-3-pro-image-preview 模型信息
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("详细检查 gemini-3-pro-image-preview 模型信息")
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

# 获取模型详细信息
print("\n" + "="*80)
print("获取模型详细信息")
print("="*80)

target_models = [
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-image-preview',
]

try:
    models = client.models.list()
    
    for target in target_models:
        print(f"\n查找模型: {target}")
        print("-" * 80)
        
        found = False
        for model in models:
            model_name = model.name if hasattr(model, 'name') else str(model)
            
            if target in model_name:
                found = True
                print(f"✅ 找到: {model_name}")
                
                # 打印所有属性
                print("   属性:")
                for attr in dir(model):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(model, attr)
                            if not callable(value):
                                print(f"     {attr}: {value}")
                        except:
                            pass
                
                # 尝试获取模型详细信息
                try:
                    model_info = client.models.get(name=model_name)
                    print(f"   详细信息: {model_info}")
                except Exception as e:
                    print(f"   无法获取详细信息: {e}")
        
        if not found:
            print(f"❌ 未找到模型")

except Exception as e:
    print(f"❌ 错误：{e}")

print("\n" + "="*80)
print("完成")
print("="*80)
