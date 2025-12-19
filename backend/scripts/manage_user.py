#!/usr/bin/env python3
"""
用户管理脚本 - 用于管理员管理用户账号

用法:
    # 列出所有用户
    python -m backend.scripts.manage_user --action list
    
    # 禁用用户
    python -m backend.scripts.manage_user --action disable --email user@example.com
    
    # 启用用户
    python -m backend.scripts.manage_user --action enable --email user@example.com
    
    # 重置密码
    python -m backend.scripts.manage_user --action reset-password --email user@example.com --password "new_password"
    
    # 查看用户详情
    python -m backend.scripts.manage_user --action info --email user@example.com
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.app.core.database import SessionLocal
from backend.app.models.db_models import User
from backend.app.core.password import hash_password


def get_user_by_email(db, email: str) -> User:
    """根据邮箱获取用户"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise ValueError(f"User with email '{email}' not found")
    return user


def list_users() -> list:
    """列出所有用户"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return users
    finally:
        db.close()


def disable_user(email: str) -> User:
    """禁用用户账号"""
    db = SessionLocal()
    try:
        user = get_user_by_email(db, email)
        if user.status == 'disabled':
            raise ValueError(f"User '{email}' is already disabled")
        user.status = 'disabled'
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def enable_user(email: str) -> User:
    """启用用户账号"""
    db = SessionLocal()
    try:
        user = get_user_by_email(db, email)
        if user.status == 'active':
            raise ValueError(f"User '{email}' is already active")
        user.status = 'active'
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def reset_password(email: str, new_password: str) -> User:
    """重置用户密码"""
    db = SessionLocal()
    try:
        user = get_user_by_email(db, email)
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def get_user_info(email: str) -> User:
    """获取用户详情"""
    db = SessionLocal()
    try:
        return get_user_by_email(db, email)
    finally:
        db.close()


def format_user(user: User) -> str:
    """格式化用户信息"""
    status_icon = "✅" if user.status == 'active' else "🚫"
    return f"{status_icon} {user.email} | {user.name} | {user.id} | {user.status}"


def main():
    parser = argparse.ArgumentParser(description="Manage user accounts")
    parser.add_argument(
        "--action",
        required=True,
        choices=["list", "disable", "enable", "reset-password", "info"],
        help="Action to perform"
    )
    parser.add_argument("--email", help="User email address")
    parser.add_argument("--password", help="New password (for reset-password action)")
    
    args = parser.parse_args()
    
    try:
        if args.action == "list":
            users = list_users()
            if not users:
                print("No users found.")
            else:
                print(f"Found {len(users)} user(s):\n")
                print("-" * 80)
                for user in users:
                    print(format_user(user))
                print("-" * 80)
        
        elif args.action == "info":
            if not args.email:
                print("Error: --email is required for info action")
                sys.exit(1)
            user = get_user_info(args.email)
            print(f"User Information:")
            print(f"  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Name: {user.name}")
            print(f"  Status: {user.status}")
            print(f"  Created: {user.created_at}")
            print(f"  Updated: {user.updated_at}")
        
        elif args.action == "disable":
            if not args.email:
                print("Error: --email is required for disable action")
                sys.exit(1)
            user = disable_user(args.email)
            print(f"🚫 User '{user.email}' has been disabled")
        
        elif args.action == "enable":
            if not args.email:
                print("Error: --email is required for enable action")
                sys.exit(1)
            user = enable_user(args.email)
            print(f"✅ User '{user.email}' has been enabled")
        
        elif args.action == "reset-password":
            if not args.email:
                print("Error: --email is required for reset-password action")
                sys.exit(1)
            if not args.password:
                print("Error: --password is required for reset-password action")
                sys.exit(1)
            if len(args.password) < 8:
                print("Error: Password must be at least 8 characters long")
                sys.exit(1)
            user = reset_password(args.email, args.password)
            print(f"🔑 Password reset successfully for '{user.email}'")
    
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
