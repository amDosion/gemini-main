#!/usr/bin/env python3
"""
为用户生成 access_token 和 refresh_token

用法:
    python scripts/generate_user_token.py --email xcgrmini@example.com
"""
import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from backend.app.core.database import SessionLocal
from backend.app.models.db_models import User, RefreshToken
from backend.app.services.common.auth_service import AuthService
from backend.app.core.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_token_for_user(email: str):
    """为用户生成 token"""
    logger.info("=" * 60)
    logger.info("开始为用户生成 token")
    logger.info("=" * 60)
    
    db = SessionLocal()
    try:
        # 查找用户
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.error(f"❌ 用户 '{email}' 不存在")
            sys.exit(1)
        
        logger.info(f"  - 找到用户: {user.email}")
        logger.info(f"    ID: {user.id}")
        logger.info(f"    Name: {user.name}")
        logger.info(f"    Status: {user.status}")
        
        # 使用 AuthService 生成 token
        auth_service = AuthService(db)
        tokens = auth_service._create_tokens(user.id)
        
        # 更新用户的 access_token 和 token_expires_at
        user.access_token = tokens.access_token
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        db.commit()
        db.refresh(user)
        
        logger.info("")
        logger.info("  ✅ Token 生成成功！")
        logger.info("")
        logger.info("  Token 信息:")
        logger.info(f"    Access Token: {tokens.access_token[:50]}...")
        logger.info(f"    Refresh Token: {tokens.refresh_token[:50]}...")
        logger.info(f"    Token Type: {tokens.token_type}")
        logger.info(f"    Expires In: {tokens.expires_in} 秒 ({tokens.expires_in // 60} 分钟)")
        logger.info(f"    Token Expires At: {user.token_expires_at}")
        logger.info("")
        logger.info("  ⚠️  请妥善保管这些 token，不要泄露！")
        logger.info("")
        logger.info("  前端使用方式:")
        logger.info(f"    localStorage.setItem('access_token', '{tokens.access_token}')")
        logger.info(f"    localStorage.setItem('refresh_token', '{tokens.refresh_token}')")
        
        return tokens
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 生成 token 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="为用户生成 access_token 和 refresh_token")
    parser.add_argument("--email", required=True, help="用户邮箱")
    
    args = parser.parse_args()
    
    try:
        tokens = generate_token_for_user(args.email)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ 操作完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

