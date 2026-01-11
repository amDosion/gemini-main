"""
诊断脚本：检查数据库中 Google 配置的 savedModels
查看 gemini-3-pro-image-preview 的 capabilities
"""
import sqlite3
import json
import sys

# 数据库路径（根据你的项目调整）
DB_PATH = "D:/gemini-main/gemini-main/backend/database.db"

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查询所有 Google 配置
    cursor.execute("""
        SELECT id, name, provider_id, saved_models
        FROM config_profiles
        WHERE provider_id = 'google'
    """)

    profiles = cursor.fetchall()

    print("=" * 80)
    print("数据库中的 Google 配置诊断")
    print("=" * 80)

    if not profiles:
        print("\n❌ 未找到 Google 配置！")
        print("请先在 Settings → Profiles 中创建 Google 配置。")
        sys.exit(1)

    for profile_id, name, provider_id, saved_models_json in profiles:
        print(f"\n配置名称: {name}")
        print(f"配置 ID: {profile_id}")

        if not saved_models_json:
            print("  ⚠️ savedModels 为空！请点击 'Verify Connection'")
            continue

        try:
            saved_models = json.loads(saved_models_json)
            print(f"  模型总数: {len(saved_models)}")

            # 查找 gemini-3-pro-image-preview
            target_models = [
                "gemini-3-pro-image-preview",
                "gemini-3.0-pro-image-preview",
                "gemini-2.5-flash-image"
            ]

            for target in target_models:
                model = next((m for m in saved_models if m.get('id') == target), None)

                if model:
                    print(f"\n  ✅ 找到模型: {target}")
                    print(f"     Name: {model.get('name')}")
                    caps = model.get('capabilities', {})
                    print(f"     Capabilities:")
                    print(f"       - vision: {caps.get('vision', False)}")
                    print(f"       - search: {caps.get('search', False)}")
                    print(f"       - reasoning: {caps.get('reasoning', False)}")
                    print(f"       - coding: {caps.get('coding', False)}")

                    # 判断是否符合 EDIT 模式
                    if caps.get('vision') and 'veo' not in target.lower():
                        print(f"     ✅ 符合 image-edit 模式要求")
                    else:
                        print(f"     ❌ 不符合 image-edit 模式要求（vision={caps.get('vision')}）")
                        print(f"     ⚠️ 这是问题所在！需要重新验证配置。")
                else:
                    print(f"\n  ❌ 未找到模型: {target}")
                    print(f"     可能的原因：")
                    print(f"     1. Google API 未返回该模型（需要启用 Billing）")
                    print(f"     2. 需要重新点击 'Verify Connection'")

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON 解析失败: {e}")

    conn.close()

    print("\n" + "=" * 80)
    print("诊断建议")
    print("=" * 80)
    print("""
如果上面显示 capabilities 都是 False，请执行以下操作：

1. 进入 Settings → Profiles
2. 编辑你的 Google 配置
3. 点击 'Verify Connection' 按钮
4. 等待验证完成
5. 确保 Gemini 3 Pro Image Preview 被勾选
6. 点击 'Save' 按钮

这样会用新的后端代码重新获取模型列表，capabilities 会被正确设置。
""")

except sqlite3.Error as e:
    print(f"❌ 数据库错误: {e}")
    print(f"数据库路径: {DB_PATH}")
    print("请确认数据库文件路径是否正确。")
except Exception as e:
    print(f"❌ 未知错误: {e}")
    import traceback
    traceback.print_exc()
