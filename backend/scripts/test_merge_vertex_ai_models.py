"""
测试脚本：分析如何将 Vertex AI Configuration 中的模型合并到 Google 提供商的模型列表中

测试场景：
1. 从 ConfigProfile 获取 Google 提供商的模型列表（通过 API）
2. 从 VertexAIConfig 获取 saved_models（用户保存的 Vertex AI 模型）
3. 合并两个列表，去重，并确保 capabilities 正确
"""

import os
import sys
import json
from pathlib import Path

# 设置 UTF-8 编码输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.app.core.database import get_db
    from backend.app.models.db_models import ConfigProfile, VertexAIConfig, UserSettings
    from backend.app.core.encryption import decrypt_data, is_encrypted
    from backend.app.services.common.model_capabilities import get_google_capabilities, build_model_config
    from backend.app.services.common.provider_factory import ProviderFactory
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("Please ensure you're running from the project root")
    sys.exit(1)


async def test_merge_vertex_ai_models(user_id: str = None):
    """
    测试合并 Vertex AI 模型到 Google 提供商模型列表
    
    Args:
        user_id: 用户 ID，如果为 None，则尝试获取第一个用户的配置
    """
    print("=" * 80)
    print("测试：合并 Vertex AI 模型到 Google 提供商模型列表")
    print("=" * 80)
    print()
    
    db = next(get_db())
    
    try:
        # 1. 获取用户的 Google ConfigProfile
        print("[STEP 1] 获取用户的 Google ConfigProfile...")
        if not user_id:
            # 尝试获取第一个有 Google 配置的用户
            google_profile = db.query(ConfigProfile).filter(
                ConfigProfile.provider_id == 'google'
            ).first()
            if google_profile:
                user_id = google_profile.user_id
                print(f"[INFO] 使用用户 ID: {user_id}")
            else:
                print("[ERROR] 未找到 Google 配置")
                return
        else:
            google_profile = db.query(ConfigProfile).filter(
                ConfigProfile.user_id == user_id,
                ConfigProfile.provider_id == 'google'
            ).first()
        
        if not google_profile:
            print(f"[ERROR] 用户 {user_id} 没有 Google 配置")
            return
        
        print(f"[SUCCESS] 找到 Google 配置: {google_profile.name} (ID: {google_profile.id})")
        print()
        
        # 2. 获取 Google 提供商的模型列表（通过 API）
        print("[STEP 2] 通过 ProviderFactory 获取 Google 模型列表...")
        try:
            # 解密 API Key
            api_key = google_profile.api_key
            if is_encrypted(api_key):
                api_key = decrypt_data(api_key)
            
            # 创建 GoogleService
            service = ProviderFactory.create(
                provider="google",
                api_key=api_key,
                api_url=google_profile.base_url,
                user_id=user_id,
                db=db
            )
            
            # 获取可用模型（异步方法）
            import asyncio
            google_models = await service.get_available_models()
            print(f"[SUCCESS] 从 Google API 获取到 {len(google_models)} 个模型")
            
            # 显示前 5 个模型
            print("\n[INFO] Google API 模型示例（前 5 个）:")
            for i, model in enumerate(google_models[:5], 1):
                print(f"  {i}. {model.id}")
                print(f"     名称: {model.name}")
                print(f"     能力: vision={model.capabilities.vision}, search={model.capabilities.search}, reasoning={model.capabilities.reasoning}, coding={model.capabilities.coding}")
            if len(google_models) > 5:
                print(f"  ... 还有 {len(google_models) - 5} 个模型")
            print()
            
        except Exception as e:
            print(f"[ERROR] 获取 Google 模型失败: {e}")
            import traceback
            traceback.print_exc()
            google_models = []
            print()
        
        # 3. 获取 Vertex AI 配置中的 saved_models
        print("[STEP 3] 获取 Vertex AI 配置中的 saved_models...")
        vertex_ai_config = db.query(VertexAIConfig).filter(
            VertexAIConfig.user_id == user_id
        ).first()
        
        if not vertex_ai_config:
            print("[WARNING] 用户没有 Vertex AI 配置")
            vertex_ai_models = []
        else:
            saved_models = vertex_ai_config.saved_models or []
            print(f"[SUCCESS] 找到 {len(saved_models)} 个保存的 Vertex AI 模型")
            
            # 显示保存的模型
            if saved_models:
                print("\n[INFO] Vertex AI 保存的模型:")
                for i, model_data in enumerate(saved_models[:10], 1):
                    model_id = model_data.get('id') if isinstance(model_data, dict) else str(model_data)
                    model_name = model_data.get('name', model_id) if isinstance(model_data, dict) else model_id
                    caps = model_data.get('capabilities', {}) if isinstance(model_data, dict) else {}
                    print(f"  {i}. {model_id}")
                    print(f"     名称: {model_name}")
                    print(f"     能力: vision={caps.get('vision', False)}, search={caps.get('search', False)}, reasoning={caps.get('reasoning', False)}, coding={caps.get('coding', False)}")
                if len(saved_models) > 10:
                    print(f"  ... 还有 {len(saved_models) - 10} 个模型")
            print()
            
            # 转换为 ModelConfig 格式
            vertex_ai_models = []
            for model_data in saved_models:
                if isinstance(model_data, dict):
                    model_id = model_data.get('id', '')
                    model_name = model_data.get('name', model_id)
                    description = model_data.get('description', f'Model: {model_id}')
                    caps = model_data.get('capabilities', {})
                    context_window = model_data.get('contextWindow', 0)
                    
                    # 创建 ModelConfig 对象（简化版，使用字典）
                    vertex_ai_models.append({
                        'id': model_id,
                        'name': model_name,
                        'description': description,
                        'capabilities': {
                            'vision': caps.get('vision', False),
                            'search': caps.get('search', False),
                            'reasoning': caps.get('reasoning', False),
                            'coding': caps.get('coding', False)
                        },
                        'contextWindow': context_window
                    })
        
        # 4. 合并模型列表
        print("[STEP 4] 合并模型列表...")
        print(f"[INFO] Google API 模型数: {len(google_models)}")
        print(f"[INFO] Vertex AI 保存模型数: {len(vertex_ai_models)}")
        
        # 创建模型映射（以 ID 为键）
        merged_models_map = {}
        
        # 首先添加 Google API 模型
        for model in google_models:
            merged_models_map[model.id] = {
                'id': model.id,
                'name': model.name,
                'description': model.description if hasattr(model, 'description') else f'Model: {model.id}',
                'capabilities': {
                    'vision': model.capabilities.vision,
                    'search': model.capabilities.search,
                    'reasoning': model.capabilities.reasoning,
                    'coding': model.capabilities.coding
                },
                'contextWindow': model.context_window if hasattr(model, 'context_window') else None,
                'source': 'google_api'
            }
        
        # 然后添加 Vertex AI 模型（如果 ID 不存在，或覆盖 capabilities）
        duplicates = []
        new_models = []
        for vertex_model in vertex_ai_models:
            model_id = vertex_model['id']
            if model_id in merged_models_map:
                # 模型已存在，检查是否需要更新 capabilities
                existing = merged_models_map[model_id]
                existing_caps = existing['capabilities']
                vertex_caps = vertex_model['capabilities']
                
                # 如果 Vertex AI 模型有更完整的能力信息，更新它
                if any([vertex_caps.get('vision'), vertex_caps.get('search'), 
                       vertex_caps.get('reasoning'), vertex_caps.get('coding')]):
                    # 合并 capabilities（Vertex AI 的优先级更高）
                    merged_models_map[model_id]['capabilities'] = {
                        'vision': vertex_caps.get('vision', existing_caps.get('vision', False)),
                        'search': vertex_caps.get('search', existing_caps.get('search', False)),
                        'reasoning': vertex_caps.get('reasoning', existing_caps.get('reasoning', False)),
                        'coding': vertex_caps.get('coding', existing_caps.get('coding', False))
                    }
                    merged_models_map[model_id]['source'] = 'both'
                duplicates.append(model_id)
            else:
                # 新模型，添加它
                vertex_model['source'] = 'vertex_ai_only'
                merged_models_map[model_id] = vertex_model
                new_models.append(model_id)
        
        merged_models = list(merged_models_map.values())
        
        print(f"[SUCCESS] 合并后共有 {len(merged_models)} 个模型")
        print(f"[INFO] 重复模型数: {len(duplicates)}")
        print(f"[INFO] 仅 Vertex AI 模型数: {len(new_models)}")
        print()
        
        # 5. 显示合并结果
        print("[STEP 5] 合并结果分析:")
        print()
        
        # 按来源分组
        google_only = [m for m in merged_models if m.get('source') == 'google_api']
        vertex_only = [m for m in merged_models if m.get('source') == 'vertex_ai_only']
        both = [m for m in merged_models if m.get('source') == 'both']
        
        print(f"[INFO] 仅 Google API: {len(google_only)} 个")
        print(f"[INFO] 仅 Vertex AI: {len(vertex_only)} 个")
        print(f"[INFO] 两者都有（已合并）: {len(both)} 个")
        print()
        
        # 显示 Vertex AI 独有的模型
        if vertex_only:
            print("[INFO] Vertex AI 独有的模型（这些模型不在 Google API 列表中）:")
            for i, model in enumerate(vertex_only[:10], 1):
                print(f"  {i}. {model['id']}")
                print(f"     名称: {model['name']}")
                print(f"     能力: vision={model['capabilities']['vision']}, search={model['capabilities']['search']}, reasoning={model['capabilities']['reasoning']}, coding={model['capabilities']['coding']}")
            if len(vertex_only) > 10:
                print(f"  ... 还有 {len(vertex_only) - 10} 个模型")
            print()
        
        # 显示合并的模型（有更新的 capabilities）
        if both:
            print("[INFO] 合并的模型（capabilities 已更新）:")
            for i, model in enumerate(both[:5], 1):
                print(f"  {i}. {model['id']}")
                print(f"     名称: {model['name']}")
                print(f"     能力: vision={model['capabilities']['vision']}, search={model['capabilities']['search']}, reasoning={model['capabilities']['reasoning']}, coding={model['capabilities']['coding']}")
            if len(both) > 5:
                print(f"  ... 还有 {len(both) - 5} 个模型")
            print()
        
        # 6. 保存测试结果
        output_file = project_root / "backend" / "scripts" / "merge_vertex_ai_models_test_result.json"
        result = {
            'user_id': user_id,
            'google_profile_id': google_profile.id,
            'google_profile_name': google_profile.name,
            'google_models_count': len(google_models),
            'vertex_ai_models_count': len(vertex_ai_models),
            'merged_models_count': len(merged_models),
            'duplicates_count': len(duplicates),
            'new_models_count': len(new_models),
            'google_only_count': len(google_only),
            'vertex_only_count': len(vertex_only),
            'both_count': len(both),
            'google_models': [
                {
                    'id': m.id,
                    'name': m.name,
                    'capabilities': {
                        'vision': m.capabilities.vision,
                        'search': m.capabilities.search,
                        'reasoning': m.capabilities.reasoning,
                        'coding': m.capabilities.coding
                    }
                }
                for m in google_models[:20]  # 只保存前 20 个
            ],
            'vertex_ai_models': vertex_ai_models[:20],  # 只保存前 20 个
            'merged_models': merged_models[:30],  # 只保存前 30 个
            'vertex_only_models': [m['id'] for m in vertex_only],
            'duplicate_model_ids': duplicates
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"[SUCCESS] 测试结果已保存到: {output_file}")
        print()
        
        # 7. 总结和建议
        print("=" * 80)
        print("合并策略建议:")
        print("=" * 80)
        print()
        print("1. 合并逻辑:")
        print("   - 首先添加所有 Google API 返回的模型")
        print("   - 然后添加 Vertex AI 保存的模型")
        print("   - 如果模型 ID 重复，使用 Vertex AI 的 capabilities（更准确）")
        print()
        print("2. 前端实现:")
        print("   - 在 useModels hook 中，当 provider_id === 'google' 时")
        print("   - 调用 /vertex-ai/config 获取 saved_models")
        print("   - 将 saved_models 合并到从 API 获取的模型列表中")
        print("   - 确保去重（以 model.id 为键）")
        print()
        print("3. 注意事项:")
        print("   - Vertex AI 模型可能包含一些特殊的模型（如 imagen-*, veo-*）")
        print("   - 这些模型可能不在标准的 Google API 模型列表中")
        print("   - 需要确保这些模型也能正确显示在模型选择器中")
        print()
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        db.close()


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试合并 Vertex AI 模型到 Google 提供商模型列表')
    parser.add_argument('--user-id', type=str, help='用户 ID（可选）')
    
    args = parser.parse_args()
    
    await test_merge_vertex_ai_models(args.user_id)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
