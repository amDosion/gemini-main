"""
测试后端模型过滤 API
验证 /api/models/{provider}?mode=image-edit 是否正确过滤
"""
import requests
import json

# 配置
BASE_URL = "http://localhost:8000"
PROVIDER = "google"
API_KEY = "YOUR_GOOGLE_API_KEY"  # 替换为你的 API Key

def test_backend_filter(mode: str):
    """测试指定模式的后端过滤"""
    url = f"{BASE_URL}/api/models/{PROVIDER}"
    params = {
        "apiKey": API_KEY,
        "useCache": False,
        "mode": mode
    }

    print(f"\n{'='*80}")
    print(f"测试模式: {mode}")
    print(f"{'='*80}")

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        models = data.get("models", [])
        filtered_by = data.get("filtered_by_mode")

        print(f"✅ 请求成功")
        print(f"   过滤模式: {filtered_by}")
        print(f"   返回模型数: {len(models)}")
        print(f"\n模型列表:")

        for i, model in enumerate(models, 1):
            model_id = model.get("id")
            name = model.get("name")
            caps = model.get("capabilities", {})

            print(f"   {i}. {name}")
            print(f"      ID: {model_id}")
            print(f"      Capabilities: vision={caps.get('vision')}, "
                  f"search={caps.get('search')}, reasoning={caps.get('reasoning')}")

        return models

    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return []

# 测试不同模式
print("="*80)
print("后端模型过滤 API 测试")
print("="*80)

# 测试 image-edit 模式
edit_models = test_backend_filter("image-edit")

# 测试 image-gen 模式
gen_models = test_backend_filter("image-gen")

# 对比结果
print(f"\n{'='*80}")
print("对比分析")
print(f"{'='*80}")
print(f"image-edit 模式: {len(edit_models)} 个模型")
print(f"image-gen 模式: {len(gen_models)} 个模型")

# 检查 gemini-3-pro-image-preview 是否在 edit 模式中
target = "gemini-3-pro-image-preview"
found_in_edit = any(m.get("id") == target for m in edit_models)
print(f"\n{target}:")
print(f"  在 image-edit 模式: {'✅ 是' if found_in_edit else '❌ 否'}")
