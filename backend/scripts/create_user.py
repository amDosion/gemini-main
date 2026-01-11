#!/usr/bin/env python3
"""
创建用户脚本 - 用于管理员创建预置账号

用法:
    python -m backend.scripts.create_user --email admin@example.com --password "secure_password" --name "Admin"
    
    或者从 backend 目录运行:
    python scripts/create_user.py --email admin@example.com --password "secure_password"
"""
import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.app.core.database import SessionLocal
from backend.app.models.db_models import User, generate_user_id
from backend.app.core.password import hash_password


def create_user(email: str, password: str, name: str = None) -> User:
    """创建新用户"""
    db = SessionLocal()
    try:
        # 检查邮箱是否已存在
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError(f"User with email '{email}' already exists")
        
        # 创建用户
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
        return user
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create a new user account")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User password (min 8 characters)")
    parser.add_argument("--name", help="User display name (optional)")
    
    args = parser.parse_args()
    
    # 验证密码长度
    if len(args.password) < 8:
        print("Error: Password must be at least 8 characters long")
        sys.exit(1)
    
    try:
        user = create_user(args.email, args.password, args.name)
        print(f"✅ User created successfully!")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Status: {user.status}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating user: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
