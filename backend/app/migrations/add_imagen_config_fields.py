"""
数据库迁移脚本：为 imagen_configs 表添加 hidden_models 和 saved_models 字段

使用方法：
    python -m backend.app.migrations.add_imagen_config_fields
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from backend.app.core.database import engine, get_db

def add_imagen_config_fields():
    """为 imagen_configs 表添加 hidden_models 和 saved_models 字段"""
    
    db = next(get_db())
    
    try:
        # 检查字段是否已存在
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'imagen_configs' 
            AND column_name IN ('hidden_models', 'saved_models')
        """)
        
        existing_columns = db.execute(check_query).fetchall()
        existing_column_names = [row[0] for row in existing_columns]
        
        # 添加 hidden_models 字段（如果不存在）
        if 'hidden_models' not in existing_column_names:
            print("添加 hidden_models 字段...")
            db.execute(text("""
                ALTER TABLE imagen_configs 
                ADD COLUMN hidden_models JSON DEFAULT '[]'::json
            """))
            print("✓ hidden_models 字段添加成功")
        else:
            print("⚠ hidden_models 字段已存在，跳过")
        
        # 添加 saved_models 字段（如果不存在）
        if 'saved_models' not in existing_column_names:
            print("添加 saved_models 字段...")
            db.execute(text("""
                ALTER TABLE imagen_configs 
                ADD COLUMN saved_models JSON DEFAULT '[]'::json
            """))
            print("✓ saved_models 字段添加成功")
        else:
            print("⚠ saved_models 字段已存在，跳过")
        
        # 提交更改
        db.commit()
        print("\n✅ 迁移完成！")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ 迁移失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Imagen Config 表字段迁移")
    print("=" * 60)
    print()
    
    try:
        add_imagen_config_fields()
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)
