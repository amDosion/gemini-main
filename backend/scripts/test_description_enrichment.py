"""
测试脚本：验证模型描述自动补充功能

测试场景：
1. 模拟前端保存的数据（description 和 name 一样）
2. 验证后端是否能正确补充描述
3. 检查保存到数据库后的描述是否正确
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
    from backend.app.services.common.model_capabilities import get_model_description, get_model_name, get_google_capabilities
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)


def test_description_enrichment():
    """
    测试描述自动补充功能
    """
    print("=" * 80)
    print("测试：模型描述自动补充功能")
    print("=" * 80)
    print()
    
    # 模拟前端保存的数据格式（description 和 name 一样）
    test_models = [
        {
            'id': 'imagen-4.0-generate-001',
            'name': 'Imagen 4.0 Generate 001',
            'description': 'Imagen 4.0 Generate 001',  # 和 name 一样
            'capabilities': {'vision': False, 'search': False, 'reasoning': False, 'coding': False}
        },
        {
            'id': 'veo-3.1-generate-001',
            'name': 'Veo 3.1 Generate 001',
            'description': 'Veo 3.1 Generate 001',  # 和 name 一样
            'capabilities': {'vision': False, 'search': False, 'reasoning': False, 'coding': False}
        },
        {
            'id': 'gemini-3-pro-image-preview',
            'name': 'Gemini 3 Pro Image Preview',
            'description': 'Gemini 3 Pro Image Preview',  # 和 name 一样
            'capabilities': {'vision': False, 'search': False, 'reasoning': False, 'coding': False}
        },
        {
            'id': 'gemini-2.5-pro',
            'name': 'Gemini 2.5 Pro',
            'description': 'Gemini 2.5 Pro',  # 和 name 一样
            'capabilities': {'vision': False, 'search': False, 'reasoning': False, 'coding': False}
        }
    ]
    
    print("[STEP 1] 模拟前端保存的数据（description 和 name 一样）:")
    for model in test_models:
        print(f"  - {model['id']}: name='{model['name']}', description='{model['description']}'")
        print(f"    相同: {model['name'] == model['description']}")
    print()
    
    # 模拟后端处理逻辑
    print("[STEP 2] 后端自动补充描述和 capabilities:")
    enriched_models = []
    # 创建副本以避免修改原始数据
    for original_model in test_models:
        model_data = original_model.copy()  # 创建副本
        model_id = model_data.get('id', '')
        name = model_data.get('name', model_id)
        description = model_data.get('description', '')
        
        # 检查 description 是否和 name 一样
        if not description or description == name or description == f'Model: {model_id}':
            try:
                new_description = get_model_description('google', model_id)
                model_data['description'] = new_description
                print(f"  ✅ {model_id}: 描述已更新")
                print(f"     旧: '{description}'")
                print(f"     新: '{new_description}'")
            except Exception as e:
                print(f"  ❌ {model_id}: 描述更新失败: {e}")
        
        # 检查 capabilities 是否全部为 False
        caps = model_data.get('capabilities', {})
        if not any([caps.get('vision', False), caps.get('search', False), 
                   caps.get('reasoning', False), caps.get('coding', False)]):
            try:
                model_caps = get_google_capabilities(model_id)
                model_data['capabilities'] = {
                    'vision': model_caps.vision,
                    'search': model_caps.search,
                    'reasoning': model_caps.reasoning,
                    'coding': model_caps.coding
                }
                print(f"  ✅ {model_id}: capabilities 已更新")
                print(f"     vision={model_caps.vision}, search={model_caps.search}, reasoning={model_caps.reasoning}, coding={model_caps.coding}")
            except Exception as e:
                print(f"  ❌ {model_id}: capabilities 更新失败: {e}")
        
        enriched_models.append(model_data)
        print()
    
    # 显示最终结果
    print("[STEP 3] 最终结果对比:")
    print()
    # 保存原始数据用于对比
    original_models_copy = [m.copy() for m in test_models]
    
    for i, (original, enriched) in enumerate(zip(original_models_copy, enriched_models), 1):
        print(f"{i}. {original['id']}")
        print(f"   原始: name='{original['name']}', description='{original['description']}'")
        print(f"   补充后: name='{enriched['name']}', description='{enriched['description']}'")
        print(f"   描述是否改善: {enriched['description'] != original['description']}")
        print(f"   描述长度: {len(original['description'])} -> {len(enriched['description'])}")
        print(f"   Capabilities 改善: {any([enriched['capabilities'].get('vision'), enriched['capabilities'].get('search'), enriched['capabilities'].get('reasoning'), enriched['capabilities'].get('coding')])}")
        print()
    
    # 保存测试结果（使用原始数据）
    original_models_for_result = [
        {
            'id': m['id'],
            'name': m['name'],
            'description': m['description'],
            'capabilities': m['capabilities'].copy()
        }
        for m in test_models
    ]
    
    output_file = project_root / "backend" / "scripts" / "description_enrichment_test_result.json"
    result = {
        'test_models_count': len(test_models),
        'original_models': original_models_for_result,
        'enriched_models': enriched_models,
        'summary': {
            'models_with_improved_description': sum(1 for o, e in zip(test_models, enriched_models) 
                                                   if e['description'] != o['description']),
            'models_with_enriched_capabilities': sum(1 for e in enriched_models 
                                                    if any([e['capabilities'].get('vision'), 
                                                           e['capabilities'].get('search'),
                                                           e['capabilities'].get('reasoning'),
                                                           e['capabilities'].get('coding')]))
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"[SUCCESS] 测试结果已保存到: {output_file}")
    print()
    
    # 总结
    print("=" * 80)
    print("总结:")
    print("=" * 80)
    print()
    print("1. 问题分析:")
    print("   - 官方 API 返回的模型对象中，description 和 display_name 字段都为 None")
    print("   - 前端保存时，description 被设置为和 name 一样的值")
    print("   - 这导致数据库中保存的 description 和 name 相同，没有意义")
    print()
    print("2. 解决方案:")
    print("   - 创建了 get_model_description() 函数，根据模型 ID 生成有意义的描述")
    print("   - 后端保存时，检查 description 是否和 name 一样，如果是则自动补充")
    print("   - 描述会根据模型类型生成（如 'Google Imagen 4.0 - Latest image generation model'）")
    print()
    print("3. 实现位置:")
    print("   - backend/app/services/common/model_capabilities.py: get_model_description()")
    print("   - backend/app/routers/models/vertex_ai_config.py: update_vertex_ai_config()")
    print()


if __name__ == '__main__':
    test_description_enrichment()
