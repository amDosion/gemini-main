"""
检查 Google API 返回的所有图像相关模型
"""
import sys
sys.path.insert(0, 'D:\\gemini-main\\gemini-main\\backend')

from app.services.model_capabilities import get_google_capabilities, build_model_config

# 模拟 Google API 可能返回的图像相关模型
possible_models = [
    # Gemini 3.x 图像模型
    'gemini-3-pro-image-preview',
    'gemini-3.0-pro-image-preview',
    'gemini-3-pro-image',
    'gemini-3.0-pro-image',

    # Gemini 2.5 图像模型
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-image-preview',
    'gemini-2.5-pro-image',
    'gemini-2.5-pro-image-preview',

    # Nano Banana 相关
    'nano-banana-pro-preview',
    'nano-banana-pro',
    'nano-banana-preview',
    'nano-banana',
]

print("="*80)
print("Google 图像模型能力测试")
print("="*80)

for model_id in possible_models:
    config = build_model_config("google", model_id)
    caps = config.capabilities

    # 检查是否符合 image-edit 模式
    matches_edit = caps.vision and 'veo' not in model_id.lower()

    status = "✓" if matches_edit else "✗"

    print(f"\n[{status}] {model_id}")
    print(f"    显示名称: {config.name}")
    print(f"    vision={caps.vision}, search={caps.search}, reasoning={caps.reasoning}")
    print(f"    符合 image-edit: {matches_edit}")
