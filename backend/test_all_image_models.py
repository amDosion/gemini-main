"""
测试所有图片生成模型：imagen vs gemini-image
"""
import os
import sys

# 设置环境变量
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
os.environ['GOOGLE_CLOUD_PROJECT'] = 'gen-lang-client-0639481221'
os.environ['GOOGLE_CLOUD_LOCATION'] = 'us-central1'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\gemini-main\gemini-main\backend\credentials\vertex-ai-service-account.json'

print("="*80)
print("测试图片生成模型：imagen vs gemini-image")
print("="*80)

# 导入 Google GenAI SDK
try:
    from google import genai
    from google.genai import types
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

# 测试 Imagen 模型（使用 generate_images 方法）
print("\n" + "="*80)
print("测试 1: Imagen 模型 - 使用 generate_images() 方法")
print("="*80)

imagen_models = [
    'publishers/google/models/imagen-3.0-generate-002',
    'publishers/google/models/imagen-4.0-generate-001',
    'publishers/google/models/imagen-4.0-fast-generate-001',
]

for model_id in imagen_models:
