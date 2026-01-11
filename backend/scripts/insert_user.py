#!/usr/bin/env python3
"""
直接在 users 表中插入用户

用法:
    python scripts/insert_user.py --email xcgrmini@example.com --password "password123" --name "Admin"
"""
import argparse
import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.app.core.database import SessionLocal
from backend.app.models.db_models import User, generate_user_id
from backend.app.core.password import hash_password

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def insert_user(email: str, password: str, name: str = None):
    """插入用户到 users 表"""
    logger.info("=" * 60)
    logger.info("开始插入用户")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        # 检查邮箱是否已存在
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.warning(f"⚠️  用户 '{email}' 已存在")
            logger.info(f"    ID: {existing.id}")
            logger.info(f"    Email: {existing.email}")
            logger.info(f"    Name: {existing.name}")
            logger.info(f"    Status: {existing.status}")
            
            # 自动更新密码和名称
            logger.info("  - 更新用户密码和名称...")
            existing.password_hash = hash_password(password)
            if name:
                existing.name = name
            db.commit()
            db.refresh(existing)
            logger.info("  ✅ 用户密码和名称已更新")
            return existing
        
        # 创建新用户
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
        logger.error(f"❌ 插入用户失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="在 users 表中插入用户")
    parser.add_argument("--email", required=True, help="用户邮箱")
    parser.add_argument("--password", required=True, help="用户密码（至少8个字符）")
    parser.add_argument("--name", help="用户显示名称（可选）")
    
    args = parser.parse_args()
    
    # 验证密码长度
    if len(args.password) < 8:
        logger.error("❌ 密码长度至少需要8个字符")
        sys.exit(1)
    
    try:
        user = insert_user(args.email, args.password, args.name)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ 操作完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

