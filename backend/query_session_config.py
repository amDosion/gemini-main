"""
查询数据库中实际的会话配置数据
"""
import sys
import json
from pathlib import Path

# 添加项目路径
backend_path = Path(__file__).parent / "app"
sys.path.insert(0, str(backend_path.parent))

from app.core.database import get_db
from app.models.db_models import GoogleChatSession

def query_session_config():
    """查询会话 1a416b1a-8b70-46ae-b240-2babac4861b0 的配置"""
    print("=" * 80)
    print("查询 google_chat_sessions 表实际数据")
    print("=" * 80)

    db = next(get_db())

    try:
        # 查询会话
        session = db.query(GoogleChatSession).filter(
            GoogleChatSession.chat_id == '1a416b1a-8b70-46ae-b240-2babac4861b0'
        ).first()

        if not session:
            print("\n[ERROR] 未找到会话")
            return

        print(f"\n[OK] 找到会话")
        print(f"  - chat_id: {session.chat_id}")
        print(f"  - user_id: {session.user_id}")
        print(f"  - model_name: {session.model_name}")
        print(f"  - frontend_session_id: {session.frontend_session_id}")
        print(f"  - created_at: {session.created_at}")
        print(f"  - last_used_at: {session.last_used_at}")
        print(f"  - is_active: {session.is_active}")

        print(f"\n[config_json] 原始内容:")
        print(f"  {session.config_json}")

        if session.config_json:
            try:
                config_dict = json.loads(session.config_json)
                print(f"\n[config_json] 解析后:")
                print(json.dumps(config_dict, indent=2, ensure_ascii=False))

                # 检查字段格式
                print(f"\n[字段格式检查]:")
                if 'imageAspectRatio' in config_dict:
                    print(f"  [OK] 包含 imageAspectRatio (camelCase): {config_dict['imageAspectRatio']}")
                if 'image_aspect_ratio' in config_dict:
                    print(f"  [OK] 包含 image_aspect_ratio (snake_case): {config_dict['image_aspect_ratio']}")
                if 'imageResolution' in config_dict:
                    print(f"  [OK] 包含 imageResolution (camelCase): {config_dict['imageResolution']}")
                if 'image_resolution' in config_dict:
                    print(f"  [OK] 包含 image_resolution (snake_case): {config_dict['image_resolution']}")
                if 'enableThinking' in config_dict:
                    print(f"  [OK] 包含 enableThinking (camelCase): {config_dict['enableThinking']}")
                if 'enable_thinking' in config_dict:
                    print(f"  [OK] 包含 enable_thinking (snake_case): {config_dict['enable_thinking']}")

                # 检查其他所有字段
                print(f"\n[所有字段列表]:")
                for key, value in config_dict.items():
                    print(f"  - {key}: {value}")

            except json.JSONDecodeError as e:
                print(f"\n[ERROR] config_json 解析失败: {e}")
        else:
            print(f"\n[WARN] config_json 为空")

    finally:
        db.close()

if __name__ == "__main__":
    query_session_config()
