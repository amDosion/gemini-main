"""
JWT 工具类 - 处理 JWT 令牌的生成和验证
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel


# 环境变量配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


class TokenPayload(BaseModel):
    """JWT 令牌载荷"""
    sub: str  # user_id
    exp: int  # 过期时间戳
    type: str  # 'access' | 'refresh'
    iat: Optional[int] = None  # 签发时间戳


class JWTUtils:
    """JWT 工具类"""

    @staticmethod
    def create_access_token(user_id: str) -> str:
        """
        创建访问令牌（15分钟有效期）
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": user_id,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "type": "access"
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """
        创建刷新令牌（7天有效期）
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": user_id,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "type": "refresh"
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> TokenPayload:
        """
        解码并验证 JWT 令牌
        
        Raises:
            JWTError: 令牌无效或已过期
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return TokenPayload(**payload)
        except JWTError as e:
            raise JWTError(f"Invalid token: {str(e)}")

    @staticmethod
    def generate_csrf_token() -> str:
        """
        生成 CSRF 令牌（32字节随机字符串）
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        检查令牌是否已过期
        """
        try:
            payload = JWTUtils.decode_token(token)
            return payload.exp < int(datetime.now(timezone.utc).timestamp())
        except JWTError:
            return True


# 便捷函数
def create_access_token(user_id: str) -> str:
    return JWTUtils.create_access_token(user_id)


def create_refresh_token(user_id: str) -> str:
    return JWTUtils.create_refresh_token(user_id)


def decode_token(token: str) -> TokenPayload:
    return JWTUtils.decode_token(token)


def generate_csrf_token() -> str:
    return JWTUtils.generate_csrf_token()
