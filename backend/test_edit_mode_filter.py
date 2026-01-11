"""
测试 EDIT 模式的模型过滤逻辑
验证哪些模型应该显示，哪些不应该显示
"""
import sys
sys.path.insert(0, 'D:\\gemini-main\\gemini-main\\backend')

from app.services.model_capabilities import get_google_capabilities, get_qwen_capabilities

def test_edit_mode_filter(model_id: str, provider: str):
    """
    模拟前端 EDIT 模式的过滤逻辑
    """
    # 获取能力
    if provider == "google":
        caps = get_google_capabilities(model_id)
    elif provider == "tongyi":
        caps = get_qwen_capabilities(model_id)
    else:
        return False, "Unknown provider"

    lower_id = model_id.lower()

    # Header.tsx:106-118 的逻辑
    if not caps.vision or lower_id.__contains__('veo'):
        return False, "No vision or is veo model"

    # 排除纯文生图模型
    is_text_to_image_only = (
        lower_id.__contains__('wanx') or
        lower_id.__contains__('-t2i') or
        lower_id.__contains__('z-image-turbo') or
        lower_id.__contains__('dall') or
        lower_id.__contains__('flux') or
        lower_id.__contains__('midjourney') or
        (lower_id.startswith('imagen-') and 'edit' not in lower_id)
    )

    if is_text_to_image_only:
        return False, "Text-to-image only model (should not show in EDIT mode)"

    return True, "Should show in EDIT mode"

# 测试用例
test_cases = [
    # Google 模型
    ("gemini-3-pro-image-preview", "google", True, "Nano-Banana Pro - 支持图像编辑"),
    ("gemini-2.5-flash-image", "google", True, "Nano-Banana - 支持图像编辑"),
    ("gemini-2.0-flash-exp", "google", True, "标准多模态模型"),
    ("gemini-1.5-pro", "google", True, "标准多模态模型"),

    # 通义模型 - 应该显示
    ("wan2.6-image", "tongyi", True, "万相图像编辑模型"),
    ("qwen-image-edit-plus", "tongyi", True, "图像编辑专用模型"),
    ("qwen-vl-max", "tongyi", True, "多模态对话模型"),

    # 通义模型 - 不应该显示（纯文生图）
    ("wanx-t2i", "tongyi", False, "纯文生图模型"),
    ("wan2.6-t2i", "tongyi", False, "纯文生图模型"),
    ("wanx2.0-t2i", "tongyi", False, "纯文生图模型"),
    ("z-image-turbo", "tongyi", False, "纯文生图模型"),

    # 其他提供商
    ("dall-e-3", "google", False, "DALL-E 纯生成模型"),
    ("imagen-3.0-generate", "google", False, "Imagen 纯生成模型"),
]

print("=" * 100)
print("EDIT 模式模型过滤测试")
print("=" * 100)

passed = 0
failed = 0

for model_id, provider, expected_show, description in test_cases:
    should_show, reason = test_edit_mode_filter(model_id, provider)

    test_passed = (should_show == expected_show)
    status = "PASS" if test_passed else "FAIL"

    if test_passed:
        passed += 1
    else:
        failed += 1

    print(f"\n[{status}] {model_id} ({provider})")
    print(f"  描述: {description}")
    print(f"  期望: {'显示' if expected_show else '隐藏'}")
    print(f"  实际: {'显示' if should_show else '隐藏'}")
    print(f"  原因: {reason}")

print("\n" + "=" * 100)
print(f"测试结果: {passed} 通过, {failed} 失败")
print("=" * 100)

if failed == 0:
    print("\n✅ 所有测试通过！EDIT 模式过滤逻辑正确。")
else:
    print(f"\n❌ {failed} 个测试失败！请检查过滤逻辑。")
