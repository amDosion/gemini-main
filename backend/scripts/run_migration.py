"""
执行数据库迁移脚本

用于为 upload_tasks 表添加新的 source 字段
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

# 尝试多种导入方式
try:
    from app.core.database import SessionLocal, engine
except ImportError:
    try:
        import sys
        sys.path.insert(0, str(project_root))
        from backend.app.core.database import SessionLocal, engine
    except ImportError:
        # 从当前目录导入
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app.core.database import SessionLocal, engine

from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """
    执行数据库迁移
    
    添加字段:
    - source_ai_url: AI返回URL（Base64或HTTP）
    - source_attachment_id: 复用已有附件ID
    """
    logger.info("=" * 80)
    logger.info("开始执行数据库迁移: 添加 upload_tasks 新字段")
    logger.info("=" * 80)
    
    # 读取迁移SQL文件
    migration_file = Path(__file__).parent / "migrations" / "add_upload_task_source_fields.sql"
    
    if not migration_file.exists():
        logger.error(f"迁移文件不存在: {migration_file}")
        return False
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 执行迁移
    db = SessionLocal()
    try:
        logger.info("执行迁移SQL...")
        
        # 分割SQL语句（按分号）
        statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for statement in statements:
            if statement:
                try:
                    logger.info(f"执行: {statement[:50]}...")
                    db.execute(text(statement))
                    db.commit()
                    logger.info("✅ 执行成功")
                except Exception as e:
                    # 如果是"字段已存在"错误，可以忽略
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        logger.warning(f"⚠️ 字段可能已存在，跳过: {e}")
                        db.rollback()
                    else:
                        logger.error(f"❌ 执行失败: {e}")
                        db.rollback()
                        raise
        
        logger.info("=" * 80)
        logger.info("✅ 数据库迁移完成")
        logger.info("=" * 80)
        
        # 验证迁移
        logger.info("验证迁移结果...")
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'upload_tasks' 
            AND column_name IN ('source_ai_url', 'source_attachment_id')
            ORDER BY column_name
        """))
        
        columns = result.fetchall()
        if len(columns) == 2:
            logger.info("✅ 验证成功: 两个新字段都已添加")
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
        else:
            logger.warning(f"⚠️ 验证警告: 期望2个字段，实际找到{len(columns)}个")
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 迁移失败: {e}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
