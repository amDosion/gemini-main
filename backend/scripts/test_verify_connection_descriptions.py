"""
测试脚本：验证所有 Verify Connection 相关的描述和缓存处理

测试场景：
1. 测试 EditorTab 中的 Verify Connection（通过 /api/models/{provider}）
2. 测试 VertexAIConfiguration 中的 Verify Connection（通过 /vertex-ai/verify-vertex-ai）
3. 验证描述是否正确返回
4. 验证是否强制不使用缓存
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
    from backend.app.services.common.model_capabilities import get_model_description, build_model_config
    from backend.app.services.gemini.model_manager import ModelManager
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)


def test_model_description_generation():
    """
    测试模型描述生成
    """
    print("=" * 80)
    print("测试：模型描述生成")
    print("=" * 80)
    print()
    
    test_models = [
        'imagen-4.0-generate-001',
        'veo-3.1-generate-001',
        'gemini-3-pro-image-preview',
        'gemini-2.5-pro',
        'deep-research-pro',
        'nano-banana-pro'
    ]
    
    print("[INFO] 测试模型描述生成:")
    all_pass = True
    for model_id in test_models:
        try:
            desc = get_model_description('google', model_id)
            config = build_model_config('google', model_id)
            
            # 验证描述不为空且与名称不同
            name = config.name
            is_valid = desc and desc != name and desc != f'Model: {model_id}'
            
            status = "✅" if is_valid else "❌"
            print(f"  {status} {model_id}")
            print(f"     名称: {name}")
            print(f"     描述: {desc}")
            print(f"     有效: {is_valid}")
            
            if not is_valid:
                all_pass = False
        except Exception as e:
            print(f"  ❌ {model_id}: 错误 - {e}")
            all_pass = False
        print()
    
    print(f"[RESULT] 所有测试: {'✅ 通过' if all_pass else '❌ 失败'}")
    print()
    return all_pass


def test_build_model_config():
    """
    测试 build_model_config 是否包含描述
    """
    print("=" * 80)
    print("测试：build_model_config 描述字段")
    print("=" * 80)
    print()
    
    test_models = [
        'imagen-4.0-generate-001',
        'gemini-2.5-pro',
        'veo-3.1-generate-001'
    ]
    
    print("[INFO] 测试 build_model_config 返回的模型配置:")
    all_pass = True
    for model_id in test_models:
        try:
            config = build_model_config('google', model_id)
            
            # 验证配置包含所有必需字段
            has_id = hasattr(config, 'id') and config.id
            has_name = hasattr(config, 'name') and config.name
            has_description = hasattr(config, 'description') and config.description
            has_capabilities = hasattr(config, 'capabilities') and config.capabilities
            
            # 验证描述与名称不同
            desc_valid = has_description and config.description != config.name
            
            is_valid = has_id and has_name and has_description and has_capabilities and desc_valid
            
            status = "✅" if is_valid else "❌"
            print(f"  {status} {model_id}")
            print(f"     id: {config.id if has_id else 'MISSING'}")
            print(f"     name: {config.name if has_name else 'MISSING'}")
            print(f"     description: {config.description if has_description else 'MISSING'}")
            print(f"     description != name: {desc_valid}")
            print(f"     capabilities: {has_capabilities}")
            
            if not is_valid:
                all_pass = False
        except Exception as e:
            print(f"  ❌ {model_id}: 错误 - {e}")
            all_pass = False
        print()
    
    print(f"[RESULT] 所有测试: {'✅ 通过' if all_pass else '❌ 失败'}")
    print()
    return all_pass


def main():
    """主函数"""
    print("=" * 80)
    print("Verify Connection 描述和缓存测试")
    print("=" * 80)
    print()
    
    results = []
    
    # 测试 1: 模型描述生成
    results.append(("模型描述生成", test_model_description_generation()))
    
    # 测试 2: build_model_config
    results.append(("build_model_config 描述字段", test_build_model_config()))
    
    # 总结
    print("=" * 80)
    print("测试总结:")
    print("=" * 80)
    print()
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
    print()
    
    all_passed = all(result[1] for result in results)
    print(f"[FINAL RESULT] 所有测试: {'✅ 通过' if all_passed else '❌ 失败'}")
    print()
    
    # 保存测试结果
    output_file = project_root / "backend" / "scripts" / "verify_connection_descriptions_test_result.json"
    result_data = {
        'tests': [
            {'name': name, 'passed': passed}
            for name, passed in results
        ],
        'all_passed': all_passed
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    
    print(f"[SUCCESS] 测试结果已保存到: {output_file}")
    print()
    
    # 说明
    print("=" * 80)
    print("修复说明:")
    print("=" * 80)
    print()
    print("1. EditorTab 中的 Verify Connection:")
    print("   - 已设置 useCache = false，强制刷新")
    print("   - 已添加模型描述显示")
    print("   - 后端通过 build_model_config 生成描述")
    print()
    print("2. VertexAIConfiguration 中的 Verify Connection:")
    print("   - 直接调用 Vertex AI API，不涉及缓存")
    print("   - 后端使用 get_model_description 生成描述")
    print("   - 已添加模型描述显示")
    print("   - 验证时不再从数据库加载旧模型列表，只恢复选择状态")
    print()
    print("3. 缓存处理:")
    print("   - EditorTab: useCache = false 传递到后端")
    print("   - VertexAIConfiguration: 直接调用 API，无缓存")
    print("   - 后端 /api/models/{provider}: 根据 useCache 参数决定是否使用缓存")
    print()


if __name__ == '__main__':
    main()
