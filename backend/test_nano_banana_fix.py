"""
验证 Nano Banana 模型修复

这个脚本测试修复后的 model_capabilities.py 是否正确处理 Nano Banana 模型。
"""
import sys
sys.path.insert(0, 'D:\\gemini-main\\gemini-main\\backend')

from app.services.model_capabilities import get_google_capabilities, build_model_config

print("="*80)
print("Nano Banana 模型修复验证")
print("="*80)

# 测试所有 Nano Banana 变体
test_models = [
    'nano-banana-pro-preview',
    'nano-banana-pro',
    'nano-banana-preview',
    'nano-banana',
]

print("\n测试 Nano Banana 模型：")
print("-" * 80)

for model_id in test_models:
    config = build_model_config("google", model_id)
    caps = config.capabilities
    
    # 检查是否符合 image-edit 模式要求
    # image-edit 模式要求：vision=True 且不是 veo 模型
    matches_edit_mode = caps.vision and 'veo' not in model_id.lower()
    
    status = "✅ PASS" if matches_edit_mode else "❌ FAIL"
    
    print(f"\n{status} {model_id}")
    print(f"  显示名称: {config.name}")
    print(f"  vision={caps.vision}, search={caps.search}, reasoning={caps.reasoning}")
    print(f"  符合 image-edit 模式: {matches_edit_mode}")

print("\n" + "="*80)
print("测试完成")
print("="*80)

# 额外测试：确保其他图像模型也正常工作
print("\n额外验证：其他图像模型")
print("-" * 80)

other_models = [
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image',
    'imagen-3.0-generate-001',
]

for model_id in other_models:
    config = build_model_config("google", model_id)
    caps = config.capabilities
    matches_edit_mode = caps.vision and 'veo' not in model_id.lower()
    
    status = "✅" if matches_edit_mode else "❌"
    print(f"{status} {model_id}: vision={caps.vision}")
