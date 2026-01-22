"""
测试脚本：获取 Vertex AI 模型列表和 Capabilities

使用方法：
1. 设置环境变量或直接修改脚本中的配置
2. 运行: python backend/scripts/test_vertex_ai_models.py
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


def test_vertex_ai_models(
    project_id: str,
    location: str,
    credentials_json: str
):
    """
    测试 Vertex AI 模型列表和 capabilities
    
    Args:
        project_id: Google Cloud 项目 ID
        location: Vertex AI 位置（如 'us-central1'）
        credentials_json: Service account 凭证 JSON 字符串
    """
    print("=" * 80)
    print("Vertex AI 模型测试脚本")
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
        print(f"[SUCCESS] Found {len(list(models_list))} models")
        print()
        
        # 解析模型信息
        all_models = []
        image_models = []
        
        print("=" * 80)
        print("所有模型列表:")
        print("=" * 80)
        
        for model in models_list:
            model_name = model.name if hasattr(model, 'name') else str(model)
            display_name = getattr(model, 'display_name', None) or model_name
            
            # 提取短名称
            short_name = model_name.split('/')[-1] if '/' in model_name else model_name
            
            model_info = {
                'full_name': model_name,
                'short_name': short_name,
                'display_name': display_name,
                'attributes': {}
            }
            
            # 获取模型的所有属性
            if hasattr(model, '__dict__'):
                for attr in dir(model):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(model, attr)
                            if not callable(value):
                                model_info['attributes'][attr] = str(value)
                        except:
                            pass
            
            all_models.append(model_info)
            
            # 过滤图像相关模型
            if any(keyword in short_name.lower() for keyword in ['imagen', 'image', 'veo']):
                image_models.append(model_info)
        
        # 打印所有模型
        print(f"\n[INFO] Total {len(all_models)} models:\n")
        for i, model in enumerate(all_models, 1):
            print(f"{i}. {model['short_name']}")
            print(f"   完整名称: {model['full_name']}")
            if model['display_name'] != model['short_name']:
                print(f"   显示名称: {model['display_name']}")
            print()
        
        # 打印图像模型
        print("=" * 80)
        print(f"图像生成模型 ({len(image_models)} 个):")
        print("=" * 80)
        for i, model in enumerate(image_models, 1):
            print(f"{i}. {model['short_name']}")
            print(f"   完整名称: {model['full_name']}")
            print()
        
        # 测试 VertexAIImageGenerator
        print("=" * 80)
        print("测试 VertexAIImageGenerator:")
        print("=" * 80)
        
        try:
            from backend.app.services.gemini.imagen_vertex_ai import VertexAIImageGenerator
            
            generator = VertexAIImageGenerator(
                project_id=project_id,
                location=location,
                credentials_json=credentials_json
            )
            
            # 获取支持的模型
            print("\n[INFO] Getting supported models...")
            supported_models = generator.get_supported_models()
            print(f"[SUCCESS] Supported models ({len(supported_models)}):")
            for model in supported_models:
                print(f"   - {model}")
            
            # 获取 capabilities
            print("\n[INFO] Getting Capabilities...")
            capabilities = generator.get_capabilities()
            print("[SUCCESS] Capabilities:")
            print(json.dumps(capabilities, indent=2, ensure_ascii=False))
            
            # 检查格式
            print("\n" + "=" * 80)
            print("Capabilities Format Check:")
            print("=" * 80)
            
            expected_fields = [
                'supported_models',
                'max_images',
                'supported_aspect_ratios',
                'person_generation_modes'
            ]
            
            for field in expected_fields:
                if field in capabilities:
                    print(f"[OK] {field}: {capabilities[field]}")
                else:
                    print(f"[MISSING] Field: {field}")
            
            # 检查字段名
            if 'aspect_ratios' in capabilities and 'supported_aspect_ratios' not in capabilities:
                print(f"\n[WARNING] Returns 'aspect_ratios' instead of 'supported_aspect_ratios'")
                print(f"   Value: {capabilities.get('aspect_ratios')}")
            
            if 'supported_models' not in capabilities:
                print(f"\n[WARNING] Missing 'supported_models' field")
                print(f"   But can get via get_supported_models(): {supported_models}")
            
            # ========== 新增：详细分析每个模型的能力 ==========
            print("\n" + "=" * 80)
            print("Detailed Model Capabilities Analysis:")
            print("=" * 80)
            
            try:
                from backend.app.services.common.model_capabilities import get_model_capabilities, get_google_capabilities
                
                print("\n[INFO] Analyzing capabilities for each model...")
                model_capabilities_detail = {}
                
                for model_id in supported_models:
                    # 从 model_capabilities.py 获取能力
                    try:
                        caps = get_google_capabilities(model_id)
                        model_capabilities_detail[model_id] = {
                            'from_model_capabilities': {
                                'vision': caps.vision,
                                'search': caps.search,
                                'reasoning': caps.reasoning,
                                'coding': caps.coding
                            }
                        }
                    except Exception as e:
                        model_capabilities_detail[model_id] = {
                            'from_model_capabilities': {'error': str(e)}
                        }
                
                # 打印详细能力信息
                print(f"\n[INFO] Capabilities for {len(model_capabilities_detail)} models:")
                print()
                
                # 按模型类型分组
                imagen_models = [m for m in supported_models if m.startswith('imagen-')]
                gemini_models = [m for m in supported_models if 'gemini' in m.lower() and 'image' in m.lower()]
                veo_models = [m for m in supported_models if m.startswith('veo-')]
                other_models = [m for m in supported_models if m not in imagen_models + gemini_models + veo_models]
                
                if imagen_models:
                    print(f"[Imagen Models] ({len(imagen_models)} models):")
                    for model in imagen_models[:5]:  # 只显示前5个
                        caps = model_capabilities_detail.get(model, {}).get('from_model_capabilities', {})
                        print(f"  - {model}: vision={caps.get('vision', False)}")
                    if len(imagen_models) > 5:
                        print(f"  ... and {len(imagen_models) - 5} more")
                    print()
                
                if gemini_models:
                    print(f"[Gemini Image Models] ({len(gemini_models)} models):")
                    for model in gemini_models[:5]:
                        caps = model_capabilities_detail.get(model, {}).get('from_model_capabilities', {})
                        print(f"  - {model}: vision={caps.get('vision', False)}, search={caps.get('search', False)}, reasoning={caps.get('reasoning', False)}")
                    if len(gemini_models) > 5:
                        print(f"  ... and {len(gemini_models) - 5} more")
                    print()
                
                if veo_models:
                    print(f"[Veo Models] ({len(veo_models)} models):")
                    for model in veo_models[:5]:
                        caps = model_capabilities_detail.get(model, {}).get('from_model_capabilities', {})
                        print(f"  - {model}: vision={caps.get('vision', False)}")
                    if len(veo_models) > 5:
                        print(f"  ... and {len(veo_models) - 5} more")
                    print()
                
                if other_models:
                    print(f"[Other Models] ({len(other_models)} models):")
                    for model in other_models:
                        caps = model_capabilities_detail.get(model, {}).get('from_model_capabilities', {})
                        print(f"  - {model}: {caps}")
                    print()
                
                # 保存详细能力信息到结果
                capabilities['model_capabilities_detail'] = model_capabilities_detail
                
            except Exception as e:
                print(f"[WARNING] Failed to analyze model capabilities: {e}")
                import traceback
                traceback.print_exc()
            
        except Exception as e:
            print(f"[ERROR] Test VertexAIImageGenerator failed: {e}")
            import traceback
            traceback.print_exc()
        
        # 保存结果到文件
        output_file = project_root / "backend" / "scripts" / "vertex_ai_models_test_result.json"
        result = {
            'total_models': len(all_models),
            'image_models': len(image_models),
            'all_models': all_models,
            'image_models_list': [m['short_name'] for m in image_models],
            'supported_models': supported_models if 'supported_models' in locals() else [],
            'capabilities': capabilities if 'capabilities' in locals() else {},
            'test_summary': {
                'total_vertex_ai_models': len(all_models),
                'image_generation_models_count': len(supported_models) if 'supported_models' in locals() else 0,
                'capabilities_has_supported_models': 'supported_models' in (capabilities if 'capabilities' in locals() else {}),
                'capabilities_has_supported_aspect_ratios': 'supported_aspect_ratios' in (capabilities if 'capabilities' in locals() else {}),
                'capabilities_has_person_generation_modes': 'person_generation_modes' in (capabilities if 'capabilities' in locals() else {})
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n[SUCCESS] Results saved to: {output_file}")
        
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


def get_config_from_db(user_id: str = None):
    """
    从数据库获取 Vertex AI 配置
    
    Args:
        user_id: 用户 ID，如果为 None，则尝试获取第一个用户的配置
    
    Returns:
        Tuple[project_id, location, credentials_json] 或 None
    """
    try:
        # 添加 backend 目录到路径
        backend_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(backend_dir.parent))
        
        from backend.app.core.database import get_db
        from backend.app.models.db_models import VertexAIConfig
        from backend.app.core.encryption import decrypt_data
        
        db = next(get_db())
        
        # 如果没有提供 user_id，尝试获取第一个用户的配置
        if not user_id:
            config = db.query(VertexAIConfig).filter(
                VertexAIConfig.api_mode == 'vertex_ai'
            ).first()
        else:
            config = db.query(VertexAIConfig).filter(
                VertexAIConfig.user_id == user_id,
                VertexAIConfig.api_mode == 'vertex_ai'
            ).first()
        
        if not config:
            return None
        
        if not config.vertex_ai_project_id or not config.vertex_ai_credentials_json:
            return None
        
        # 解密凭证
        credentials_json = decrypt_data(config.vertex_ai_credentials_json)
        
        return (
            config.vertex_ai_project_id,
            config.vertex_ai_location or 'us-central1',
            credentials_json
        )
    except Exception as e:
        print(f"[WARNING] Failed to read config from database: {e}")
        return None


def main():
    """主函数"""
    # 从环境变量或命令行参数获取配置
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('VERTEX_AI_PROJECT_ID')
    location = os.getenv('GOOGLE_CLOUD_LOCATION') or os.getenv('VERTEX_AI_LOCATION', 'us-central1')
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    credentials_json_str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    user_id = os.getenv('TEST_USER_ID')  # 可选：从环境变量获取 user_id
    
    # 如果提供了命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("使用方法:")
            print("  python test_vertex_ai_models.py")
            print("  python test_vertex_ai_models.py <project_id> <location> <credentials_json_file>")
            print("  python test_vertex_ai_models.py --from-db [user_id]")
            print()
            print("环境变量:")
            print("  GOOGLE_CLOUD_PROJECT 或 VERTEX_AI_PROJECT_ID")
            print("  GOOGLE_CLOUD_LOCATION 或 VERTEX_AI_LOCATION (默认: us-central1)")
            print("  GOOGLE_APPLICATION_CREDENTIALS (凭证文件路径)")
            print("  GOOGLE_APPLICATION_CREDENTIALS_JSON (凭证 JSON 字符串)")
            print("  TEST_USER_ID (可选：从数据库读取配置时的用户 ID)")
            sys.exit(0)
        
        if sys.argv[1] == '--from-db':
            # 从数据库读取配置
            db_user_id = sys.argv[2] if len(sys.argv) > 2 else None
            config = get_config_from_db(db_user_id)
            if config:
                project_id, location, credentials_json = config
                print(f"[SUCCESS] Config loaded from database (user_id: {db_user_id or 'auto'})")
            else:
                print("[ERROR] Cannot read Vertex AI config from database")
                print("Please ensure there is a Vertex AI config in database (api_mode='vertex_ai')")
                sys.exit(1)
        elif len(sys.argv) >= 4:
            project_id = sys.argv[1]
            location = sys.argv[2]
            credentials_path = sys.argv[3]
    
    # 如果还没有配置，尝试从数据库读取
    if not project_id or not credentials_json_str:
        print("[INFO] Trying to read config from database...")
        config = get_config_from_db(user_id)
        if config:
            project_id, location, credentials_json = config
            print(f"[SUCCESS] Config loaded from database")
        else:
            print("[WARNING] Cannot read config from database, using environment variables or command line args")
    
    # 读取凭证
    if credentials_json_str:
        credentials_json = credentials_json_str
    elif credentials_path:
        with open(credentials_path, 'r', encoding='utf-8') as f:
            credentials_json = f.read()
    elif 'credentials_json' not in locals():
        print("[ERROR] No credentials provided")
        print("Please set environment variable GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON")
        print("Or use command line: python test_vertex_ai_models.py <project_id> <location> <credentials_file>")
        print("Or use: python test_vertex_ai_models.py --from-db [user_id]")
        sys.exit(1)
    
    if not project_id:
        print("[ERROR] No project ID provided")
        print("Please set environment variable GOOGLE_CLOUD_PROJECT or VERTEX_AI_PROJECT_ID")
        print("Or use: python test_vertex_ai_models.py --from-db [user_id]")
        sys.exit(1)
    
    # 运行测试
    test_vertex_ai_models(project_id, location, credentials_json)


if __name__ == '__main__':
    main()
