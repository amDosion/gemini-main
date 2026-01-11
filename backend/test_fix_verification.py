"""验证 model_capabilities.py 修复结果"""
import sys
sys.path.insert(0, 'D:\\gemini-main\\gemini-main\\backend')

from app.services.model_capabilities import get_google_capabilities, build_model_config

# 测试所有相关的 Google 图像模型
test_cases = [
    {
        "model_id": "gemini-3-pro-image-preview",
        "expected": {
            "vision": True,
            "search": True,
            "reasoning": True,
            "coding": False
        },
        "description": "Nano-Banana Pro (Gemini 3)"
    },
    {
        "model_id": "gemini-3.0-pro-image-preview",
        "expected": {
            "vision": True,
            "search": True,
            "reasoning": True,
            "coding": False
        },
        "description": "Nano-Banana Pro (Gemini 3.0)"
    },
    {
        "model_id": "gemini-2.5-flash-image",
        "expected": {
            "vision": True,
            "search": True,
            "reasoning": False,
            "coding": False
        },
        "description": "Nano-Banana (Gemini 2.5)"
    },
    {
        "model_id": "gemini-2.5-flash-image-preview",
        "expected": {
            "vision": True,
            "search": True,
            "reasoning": False,
            "coding": False
        },
        "description": "Nano-Banana Preview (Gemini 2.5)"
    },
    {
        "model_id": "gemini-2.0-flash-exp",
        "expected": {
            "vision": True,
            "search": True,
            "reasoning": False,
            "coding": False
        },
        "description": "Standard Gemini 2.0 model"
    },
]

print("=" * 80)
print("Google Model Capabilities Verification")
print("=" * 80)

all_passed = True

for test in test_cases:
    model_id = test["model_id"]
    expected = test["expected"]
    description = test["description"]

    caps = get_google_capabilities(model_id)

    passed = (
        caps.vision == expected["vision"] and
        caps.search == expected["search"] and
        caps.reasoning == expected["reasoning"] and
        caps.coding == expected["coding"]
    )

    status = "PASS" if passed else "FAIL"
    all_passed = all_passed and passed

    print(f"\n[{status}] {description}")
    print(f"  Model ID: {model_id}")
    print(f"  Expected: vision={expected['vision']}, search={expected['search']}, reasoning={expected['reasoning']}, coding={expected['coding']}")
    print(f"  Actual:   vision={caps.vision}, search={caps.search}, reasoning={caps.reasoning}, coding={caps.coding}")

    # Check if matches image-edit mode requirements
    matches_edit = caps.vision and 'veo' not in model_id.lower()
    print(f"  Image-edit mode: {'YES' if matches_edit else 'NO'}")

print("\n" + "=" * 80)
print(f"Overall Result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
print("=" * 80)

# 测试完整的 ModelConfig 构建
print("\n" + "=" * 80)
print("Complete ModelConfig Build Test")
print("=" * 80)

for model_id in ["gemini-3-pro-image-preview", "gemini-2.5-flash-image"]:
    config = build_model_config("google", model_id)
    print(f"\n{model_id}:")
    print(f"  Name: {config.name}")
    print(f"  Capabilities: {config.capabilities}")
    print(f"  Context Window: {config.context_window}")
