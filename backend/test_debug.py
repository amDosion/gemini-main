"""测试模型能力推断逻辑 - 带调试输出"""
import sys
sys.path.insert(0, 'D:\\gemini-main\\gemini-main\\backend')

from app.services.model_capabilities import Capabilities

def get_google_capabilities_debug(model_id: str) -> Capabilities:
    """调试版本的 get_google_capabilities"""
    lower_id = model_id.lower()
    print(f"\n=== 调试 {model_id} ===")
    print(f"lower_id = '{lower_id}'")

    vision = False
    search = False
    reasoning = False
    coding = False

    # Imagen models: vision only
    if lower_id.startswith("imagen"):
        print("匹配: Imagen models")
        return Capabilities(vision=True)

    # Code models: coding only
    if "-code-" in lower_id or lower_id.endswith("-code"):
        print("匹配: Code models")
        return Capabilities(coding=True)

    # Thinking models: vision + reasoning, no search
    if "-thinking-" in lower_id or lower_id.endswith("-thinking"):
        print("匹配: Thinking models")
        return Capabilities(vision=True, reasoning=True)

    # Gemini 2.5-pro and 3.0-pro: all capabilities except coding
    special_list = ["gemini-2.5-pro", "gemini-3.0-pro", "gemini-2.5-pro-latest", "gemini-3.0-pro-latest"]
    if lower_id in special_list:
        print("匹配: Special Pro models")
        return Capabilities(vision=True, search=True, reasoning=True)
    else:
        print(f"未匹配 Special Pro models (检查列表: {special_list})")

    # Standard Gemini models: vision + search
    gemini_patterns = ["gemini-1.5", "gemini-2.0", "gemini-2.5", "gemini-pro", "gemini-flash"]
    print(f"检查 gemini_patterns: {gemini_patterns}")

    for pattern in gemini_patterns:
        print(f"  测试: '{pattern}' in '{lower_id}' = {pattern in lower_id}")
        if pattern in lower_id:
            vision = True
            search = True
            print(f"  ✓ 匹配! 设置 vision=True, search=True")
            break

    result = Capabilities(vision=vision, search=search, reasoning=reasoning, coding=coding)
    print(f"最终结果: {result}")
    return result

# 测试
test_ids = [
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image',
]

for model_id in test_ids:
    caps = get_google_capabilities_debug(model_id)
    print(f"\n模型 {model_id}:")
    print(f"  vision={caps.vision}, search={caps.search}, reasoning={caps.reasoning}, coding={caps.coding}")
    matches_edit = caps.vision and 'veo' not in model_id.lower()
    print(f"  符合 image-edit 模式: {matches_edit}")
