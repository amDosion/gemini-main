"""测试模型能力推断逻辑"""
from app.services.model_capabilities import get_google_capabilities, build_model_config

# 测试不同的模型ID
test_ids = [
    'gemini-3-pro-image-preview',
    'gemini-3.0-pro-image-preview',
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-image-preview',
    'nano-banana-pro-preview'
]

print("=" * 60)
print("Google 模型能力推断测试")
print("=" * 60)

for model_id in test_ids:
    caps = get_google_capabilities(model_id)
    print(f'\nModel ID: {model_id}')
    print(f'  vision    = {caps.vision}')
    print(f'  search    = {caps.search}')
    print(f'  reasoning = {caps.reasoning}')
    print(f'  coding    = {caps.coding}')

    # 检查是否符合 image-edit 模式要求
    matches_edit_mode = caps.vision and 'veo' not in model_id.lower()
    print(f'  ✅ 符合 image-edit 模式' if matches_edit_mode else '  ❌ 不符合 image-edit 模式')

print("\n" + "=" * 60)
print("完整的 ModelConfig 构建测试")
print("=" * 60)

for model_id in test_ids[:2]:  # 只测试前两个
    config = build_model_config("google", model_id)
    print(f'\n{config.model_dump_json(indent=2)}')
