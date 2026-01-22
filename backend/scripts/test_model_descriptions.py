"""
测试脚本：检查 Vertex AI 和 Google API 返回的模型描述信息

目的：
1. 检查 Vertex AI API 返回的模型对象是否有 description 字段
2. 检查 Google API 返回的模型对象是否有 description 字段
3. 查看官方 API 响应中是否有更详细的描述信息
4. 分析如何获取更好的模型描述
"""

import os
import sys
import json
import tempfile
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
    from google import genai
    from google.oauth2 import service_account
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("Please install: pip install google-genai google-auth")
    sys.exit(1)


def inspect_model_object(model, model_name: str):
    """
    详细检查模型对象的所有属性和方法
    
    Args:
        model: 模型对象
        model_name: 模型名称（用于显示）
    """
    print(f"\n{'=' * 80}")
    print(f"检查模型: {model_name}")
    print(f"{'=' * 80}")
    
    # 1. 检查基本属性
    print("\n[INFO] 基本属性:")
    basic_attrs = ['name', 'display_name', 'description', 'supported_generation_methods', 
                   'version', 'input_token_limit', 'output_token_limit', 'base_model_id']
    for attr in basic_attrs:
        if hasattr(model, attr):
            try:
                value = getattr(model, attr)
                if not callable(value):
                    print(f"  {attr}: {value}")
            except Exception as e:
                print(f"  {attr}: <无法访问: {e}>")
    
    # 2. 检查所有非私有属性
    print("\n[INFO] 所有非私有属性:")
    all_attrs = []
    for attr in dir(model):
        if not attr.startswith('_'):
            try:
                value = getattr(model, attr)
                if not callable(value):
                    # 只保存可序列化的值
                    try:
                        json.dumps(value)  # 测试是否可序列化
                        all_attrs.append((attr, value))
                    except (TypeError, ValueError):
                        all_attrs.append((attr, str(value)))  # 转换为字符串
                    print(f"  {attr}: {value}")
            except Exception as e:
                print(f"  {attr}: <无法访问: {e}>")
    
    # 3. 尝试转换为字典
    print("\n[INFO] 尝试转换为字典:")
    try:
        if hasattr(model, '__dict__'):
            print(f"  __dict__: {model.__dict__}")
        if hasattr(model, 'to_dict'):
            print(f"  to_dict(): {model.to_dict()}")
        if hasattr(model, 'dict'):
            print(f"  dict(): {model.dict()}")
    except Exception as e:
        print(f"  转换失败: {e}")
    
    # 4. 检查是否有 metadata 或 additional_properties
    print("\n[INFO] 检查元数据:")
    metadata_attrs = ['metadata', 'additional_properties', 'extra', 'info', 'details']
    for attr in metadata_attrs:
        if hasattr(model, attr):
            try:
                value = getattr(model, attr)
                print(f"  {attr}: {value}")
            except Exception as e:
                print(f"  {attr}: <无法访问: {e}>")
    
    return {
        'name': getattr(model, 'name', None) if hasattr(model, 'name') else None,
        'display_name': getattr(model, 'display_name', None) if hasattr(model, 'display_name') else None,
        'description': getattr(model, 'description', None) if hasattr(model, 'description') else None,
        'all_attrs': all_attrs
    }


def test_vertex_ai_model_descriptions(
    project_id: str,
    location: str,
    credentials_json: str
):
    """
    测试 Vertex AI API 返回的模型描述信息
    """
    print("=" * 80)
    print("测试 Vertex AI 模型描述信息")
    print("=" * 80)
    print(f"项目 ID: {project_id}")
    print(f"位置: {location}")
    print()
    
    # 创建临时凭证文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        temp_file.write(credentials_json)
        temp_credentials_path = temp_file.name
    
    try:
        # 设置环境变量
        os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
        os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
        os.environ['GOOGLE_CLOUD_LOCATION'] = location
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
        
        # 初始化客户端
        print("[INFO] Initializing Vertex AI client...")
        client = genai.Client()
        print("[SUCCESS] Client initialized successfully")
        print()
        
        # 列出所有模型
        print("[INFO] Fetching model list...")
        models_list = client.models.list()
        models = list(models_list)
        print(f"[SUCCESS] Found {len(models)} models")
        print()
        
        # 选择几个代表性的模型进行详细检查
        # 1. Imagen 模型
        # 2. Gemini 模型
        # 3. Veo 模型
        test_models = []
        for model in models:
            model_name = model.name if hasattr(model, 'name') else str(model)
            short_name = model_name.split('/')[-1] if '/' in model_name else model_name
            
            # 选择不同类型的模型
            if 'imagen' in short_name.lower() and len([m for m in test_models if 'imagen' in m[1].lower()]) < 2:
                test_models.append((model, short_name))
            elif 'gemini' in short_name.lower() and len([m for m in test_models if 'gemini' in m[1].lower()]) < 2:
                test_models.append((model, short_name))
            elif 'veo' in short_name.lower() and len([m for m in test_models if 'veo' in m[1].lower()]) < 2:
                test_models.append((model, short_name))
            
            if len(test_models) >= 6:
                break
        
        print(f"[INFO] 选择 {len(test_models)} 个代表性模型进行详细检查:")
        for i, (_, name) in enumerate(test_models, 1):
            print(f"  {i}. {name}")
        print()
        
        # 详细检查每个模型
        model_info_list = []
        for model, short_name in test_models:
            info = inspect_model_object(model, short_name)
            model_info_list.append({
                'short_name': short_name,
                'full_name': model.name if hasattr(model, 'name') else str(model),
                'info': info
            })
        
        # 保存结果
        output_file = project_root / "backend" / "scripts" / "model_descriptions_test_result.json"
        result = {
            'total_models': len(models),
            'tested_models': len(test_models),
            'model_details': model_info_list,
            'sample_models': [
                {
                    'name': m.name if hasattr(m, 'name') else str(m),
                    'display_name': getattr(m, 'display_name', None),
                    'description': getattr(m, 'description', None),
                    'has_description': hasattr(m, 'description'),
            'all_attributes': {attr: str(getattr(m, attr)) for attr in dir(m) 
                              if not attr.startswith('_') and not callable(getattr(m, attr, None))
                              and attr not in ['model_computed_fields', 'model_fields', 'model_config', 'model_extra', 'model_fields_set']}
                }
                for m in models[:10]  # 保存前 10 个模型的详细信息
            ]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n[SUCCESS] 测试结果已保存到: {output_file}")
        
        # 总结
        print("\n" + "=" * 80)
        print("总结:")
        print("=" * 80)
        
        models_with_description = sum(1 for m in models if hasattr(m, 'description') and getattr(m, 'description'))
        models_with_display_name = sum(1 for m in models if hasattr(m, 'display_name') and getattr(m, 'display_name'))
        
        print(f"\n[INFO] 统计:")
        print(f"  总模型数: {len(models)}")
        print(f"  有 description 的模型: {models_with_description}")
        print(f"  有 display_name 的模型: {models_with_display_name}")
        print()
        
        # 检查是否有其他描述字段
        print("[INFO] 检查其他可能的描述字段:")
        description_fields = set()
        for model in models[:20]:  # 检查前 20 个模型
            for attr in dir(model):
                if not attr.startswith('_') and not callable(getattr(model, attr, None)):
                    attr_lower = attr.lower()
                    if any(keyword in attr_lower for keyword in ['desc', 'info', 'detail', 'summary', 'about']):
                        description_fields.add(attr)
        
        if description_fields:
            print(f"  找到可能的描述字段: {', '.join(description_fields)}")
        else:
            print("  未找到其他描述字段")
        print()
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_credentials_path)
        except:
            pass


def test_google_api_model_descriptions(api_key: str):
    """
    测试 Google API (Gemini API) 返回的模型描述信息
    """
    print("=" * 80)
    print("测试 Google API (Gemini API) 模型描述信息")
    print("=" * 80)
    print()
    
    try:
        # 初始化客户端
        print("[INFO] Initializing Google API client...")
        client = genai.Client(api_key=api_key)
        print("[SUCCESS] Client initialized successfully")
        print()
        
        # 列出所有模型
        print("[INFO] Fetching model list...")
        models_list = client.models.list()
        models = list(models_list)
        print(f"[SUCCESS] Found {len(models)} models")
        print()
        
        # 检查前 10 个模型
        print("[INFO] 检查前 10 个模型的描述信息:")
        for i, model in enumerate(models[:10], 1):
            model_name = model.name if hasattr(model, 'name') else str(model)
            short_name = model_name.split('/')[-1] if '/' in model_name else model_name
            
            print(f"\n  {i}. {short_name}")
            print(f"     完整名称: {model_name}")
            
            if hasattr(model, 'display_name'):
                print(f"     display_name: {getattr(model, 'display_name', None)}")
            if hasattr(model, 'description'):
                desc = getattr(model, 'description', None)
                print(f"     description: {desc if desc else '<无>'}")
            
            # 检查所有属性
            attrs = []
            for attr in dir(model):
                if not attr.startswith('_') and not callable(getattr(model, attr, None)):
                    try:
                        value = getattr(model, attr)
                        if 'desc' in attr.lower() or 'info' in attr.lower() or 'detail' in attr.lower():
                            attrs.append((attr, value))
                    except:
                        pass
            
            if attrs:
                print(f"     相关属性:")
                for attr, value in attrs:
                    print(f"       {attr}: {value}")
        
        print()
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


def get_config_from_db(user_id: str = None):
    """
    从数据库获取配置
    """
    try:
        backend_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(backend_dir.parent))
        
        from backend.app.core.database import get_db
        from backend.app.models.db_models import VertexAIConfig, ConfigProfile
        from backend.app.core.encryption import decrypt_data
        
        db = next(get_db())
        
        # 获取 Vertex AI 配置
        if not user_id:
            vertex_config = db.query(VertexAIConfig).filter(
                VertexAIConfig.api_mode == 'vertex_ai'
            ).first()
            if vertex_config:
                user_id = vertex_config.user_id
        else:
            vertex_config = db.query(VertexAIConfig).filter(
                VertexAIConfig.user_id == user_id,
                VertexAIConfig.api_mode == 'vertex_ai'
            ).first()
        
        if not vertex_config:
            return None, None
        
        if not vertex_config.vertex_ai_project_id or not vertex_config.vertex_ai_credentials_json:
            return None, None
        
        # 获取 Google API Key
        google_profile = db.query(ConfigProfile).filter(
            ConfigProfile.user_id == user_id,
            ConfigProfile.provider_id == 'google'
        ).first()
        
        google_api_key = None
        if google_profile and google_profile.api_key:
            google_api_key = decrypt_data(google_profile.api_key)
        
        # 解密凭证
        credentials_json = decrypt_data(vertex_config.vertex_ai_credentials_json)
        
        return (
            vertex_config.vertex_ai_project_id,
            vertex_config.vertex_ai_location or 'us-central1',
            credentials_json
        ), google_api_key
        
    except Exception as e:
        print(f"[WARNING] Failed to read config from database: {e}")
        return None, None


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试模型描述信息')
    parser.add_argument('--user-id', type=str, help='用户 ID（可选）')
    parser.add_argument('--vertex-ai-only', action='store_true', help='只测试 Vertex AI')
    parser.add_argument('--google-api-only', action='store_true', help='只测试 Google API')
    
    args = parser.parse_args()
    
    # 从数据库获取配置
    vertex_config, google_api_key = get_config_from_db(args.user_id)
    
    if not args.google_api_only:
        if vertex_config:
            project_id, location, credentials_json = vertex_config
            test_vertex_ai_model_descriptions(project_id, location, credentials_json)
        else:
            print("[WARNING] 未找到 Vertex AI 配置，跳过 Vertex AI 测试")
            print("请使用环境变量或命令行参数提供配置")
    
    if not args.vertex_ai_only:
        if google_api_key:
            test_google_api_model_descriptions(google_api_key)
        else:
            print("[WARNING] 未找到 Google API Key，跳过 Google API 测试")
            print("请使用环境变量提供 GOOGLE_API_KEY")


if __name__ == '__main__':
    main()
