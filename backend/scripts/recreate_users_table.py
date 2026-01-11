#!/usr/bin/env python3
"""
删除并重新创建 users 表，然后创建初始用户

用法:
    python scripts/recreate_users_table.py --email admin@example.com --password "password123" --name "Admin"
"""
import argparse
import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.database import engine, Base, SessionLocal
from backend.app.models.db_models import User, generate_user_id
from backend.app.core.password import hash_password

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def drop_users_table():
    """删除 users 表"""
    logger.info("=" * 60)
    logger.info("开始删除 users 表")
    logger.info("=" * 60)
    
    try:
        with engine.connect() as connection:
            trans = connection.begin()
            
            # 检查表是否存在
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if 'users' not in tables:
                logger.warning("⚠️  users 表不存在，跳过删除")
                trans.rollback()
                return
            
            # 删除表（CASCADE 会自动删除依赖的索引和外键）
            logger.info("  - 删除 users 表...")
            connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            
            trans.commit()
            logger.info("  ✅ users 表删除成功")
            
    except Exception as e:
        logger.error(f"❌ 删除 users 表失败: {str(e)}")
        raise


def create_users_table():
    """重新创建 users 表"""
    logger.info("=" * 60)
    logger.info("开始创建 users 表")
    logger.info("=" * 60)
    
    try:
        # 使用 SQLAlchemy 的 create_all 创建表
        logger.info("  - 创建 users 表结构...")
        User.__table__.create(engine, checkfirst=True)
        logger.info("  ✅ users 表创建成功")
        
        # 验证表结构
        inspector = inspect(engine)
        cols = inspector.get_columns('users')
        logger.info("\n  Users 表结构:")
        for col in cols:
            nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
            logger.info(f"    - {col['name']}: {col['type']} ({nullable})")
        
    except Exception as e:
        logger.error(f"❌ 创建 users 表失败: {str(e)}")
        raise


def create_initial_user(email: str, password: str, name: str = None):
    """创建初始用户"""
    logger.info("=" * 60)
    logger.info("开始创建初始用户")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        # 检查邮箱是否已存在
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.warning(f"⚠️  用户 '{email}' 已存在，跳过创建")
            return existing
        
        # 创建用户
        logger.info(f"  - 创建用户: {email}")
        user = User(
            id=generate_user_id(),
            email=email,
            password_hash=hash_password(password),
            name=name or email.split('@')[0],
            status='active'
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info("  ✅ 用户创建成功")
        logger.info(f"    ID: {user.id}")
        logger.info(f"    Email: {user.email}")
        logger.info(f"    Name: {user.name}")
        logger.info(f"    Status: {user.status}")
        
        return user
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 创建用户失败: {str(e)}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="删除并重新创建 users 表，然后创建初始用户")
    parser.add_argument("--email", required=True, help="初始用户邮箱")
    parser.add_argument("--password", required=True, help="初始用户密码（至少8个字符）")
    parser.add_argument("--name", help="初始用户显示名称（可选）")
    parser.add_argument("--skip-drop", action="store_true", help="跳过删除表步骤（仅创建表）")
    
    args = parser.parse_args()
    
    # 验证密码长度
    if len(args.password) < 8:
        logger.error("❌ 密码长度至少需要8个字符")
        sys.exit(1)
    
    try:
        # 1. 删除表（除非跳过）
        if not args.skip_drop:
            drop_users_table()
            logger.info("")
        
        # 2. 创建表
        create_users_table()
        logger.info("")
        
        # 3. 创建初始用户
        create_initial_user(args.email, args.password, args.name)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ 所有操作完成！")
        logger.info("=" * 60)
        
    except SQLAlchemyError as e:
        logger.error(f"❌ 数据库错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 未知错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


