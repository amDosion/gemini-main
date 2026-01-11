#!/usr/bin/env python3
"""
数据库 Schema 验证脚本

用途：验证数据库 Schema 与 SQLAlchemy 模型定义一致
使用：python scripts/verify_schema.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import db_models


def verify_schema():
    """验证数据库 Schema"""

    print("🔍 正在验证数据库 Schema...")

    # 创建引擎
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)

    # 获取所有表名
    existing_tables = set(inspector.get_table_names())

    # 期望的表名（从模型定义中提取）
    expected_tables = {
        'users',
        'config_profiles',
        'user_settings',
        'chat_sessions',
        'message_index',
        'message_chat',
        'message_imagegen',
        'message_videogen',
        'message_audiogen',
        'message_attachments',
        'personas',
        'storage_uploads',
        'research_tasks',
    }

    # 检查缺失的表
    missing_tables = expected_tables - existing_tables
    if missing_tables:
        print(f"❌ 缺失的表: {', '.join(missing_tables)}")
        return False

    # 检查多余的表（可能是旧迁移遗留）
    extra_tables = existing_tables - expected_tables
    if extra_tables:
        print(f"⚠️  多余的表: {', '.join(extra_tables)}")

    # 验证关键表的列
    critical_tables = {
        'users': ['id', 'username', 'email', 'hashed_password', 'created_at'],
        'config_profiles': ['id', 'user_id', 'name', 'provider_id', 'api_key_encrypted'],
        'chat_sessions': ['id', 'user_id', 'name', 'mode', 'created_at'],
        'message_index': ['id', 'session_id', 'mode', 'message_table', 'message_id'],
    }

    for table_name, expected_columns in critical_tables.items():
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        missing_columns = set(expected_columns) - set(columns)

        if missing_columns:
            print(f"❌ 表 '{table_name}' 缺失列: {', '.join(missing_columns)}")
            return False

    print("✅ 数据库 Schema 验证通过")
    return True


if __name__ == "__main__":
    try:
        success = verify_schema()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Schema 验证失败: {e}")
        sys.exit(1)
