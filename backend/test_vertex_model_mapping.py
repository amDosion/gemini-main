"""
测试 Vertex AI 图片编辑模型映射

验证用户选择的模型 ID 是否正确映射到 Vertex AI 支持的模型 ID。
"""
import sys
sys.path.insert(0, 'D:\\gemini-main\\gemini-main\\backend')

from app.services.gemini.image_edit_vertex_ai import MODEL_MAPPING, DEFAULT_EDIT_MODEL

print("="*80)
print("Vertex AI 图片编辑模型映射测试")
print("="*80)

# 测试所有映射
print("\n模型映射表：")
print("-" * 80)

for user_model, vertex_model in MODEL_MAPPING.items():
    status = "✅" if vertex_model == DEFAULT_EDIT_MODEL else "⚠️"
    print(f"{status} {user_model:40} → {vertex_model}")

print("\n" + "="*80)
print(f"默认模型: {DEFAULT_EDIT_MODEL}")
print("="*80)

# 测试特定模型
test_models = [
    'nano-banana-pro-preview',
    'gemini-3-pro-image-preview',
    'imagen-3.0-capability-001',
    'unknown-model',  # 测试未知模型
]

print("\n特定模型映射测试：")
print("-" * 80)

for model in test_models:
    mapped = MODEL_MAPPING.get(model, DEFAULT_EDIT_MODEL)
    is_mapped = model in MODEL_MAPPING
    status = "✅ 已映射" if is_mapped else "⚠️ 使用默认"
    print(f"{status} {model:40} → {mapped}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
