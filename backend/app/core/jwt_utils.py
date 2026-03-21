"""
JWT 工具类 - 处理 JWT 令牌的生成和验证

This module provides:
1. JWT token generation and validation functions
2. JWT Secret Key management (storage, retrieval, rotation)

安全地管理 JWT Secret Key：
- 从环境变量/密钥管理器显式读取运行时密钥
- 支持加密存储到安全文件（管理员显式操作）
- 提供 CLI 命令查看和管理
- 确保不会泄露到代码或配置文件中
"""
import os
import secrets
import json
import base64
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel
from cryptography.fernet import Fernet
import logging

# 导入统一的环境变量加载模块（确保 .env 文件已加载）
from .env_loader import _ENV_LOADED  # noqa: F401

logger = logging.getLogger(__name__)

# ==================== JWT Secret Key 管理 ====================

# JWT Secret Key 存储文件路径（存储在 backend/credentials 目录）
# 注意：此文件应添加到 .gitignore，确保不会提交到版本控制
# backend/credentials 目录已在 .gitignore 中忽略
_credentials_dir = Path(__file__).resolve().parents[2] / "credentials"
_credentials_dir.mkdir(exist_ok=True)  # 确保目录存在
JWT_SECRET_FILE = _credentials_dir / ".jwt_secret"
JWT_SECRET_ENCRYPTED_FILE = _credentials_dir / ".jwt_secret.enc"


class JWTSecretManager:
    """
    JWT Secret Key 管理器
    
    功能：
    1. 生成强随机密钥（64字节，URL-safe base64编码）
    2. 加密存储到安全文件（使用 Fernet 对称加密，管理员显式调用）
    3. 提供安全的读取接口（运行时仅从环境变量读取）
    4. 支持密钥轮换
    """
    
    @staticmethod
    def _get_master_key() -> bytes:
        """
        获取主加密密钥（用于加密 JWT Secret Key）

        Returns:
            加密密钥（bytes）
        """
        from .encryption import get_encryption_key

        master_key = get_encryption_key()
        if not master_key:
            raise RuntimeError("ENCRYPTION_KEY 未设置")
        return master_key.encode()
    
    @staticmethod
    def generate_secret_key() -> str:
        """
        生成新的 JWT Secret Key
        
        Returns:
            64字节的 URL-safe base64 编码密钥（适合 HS256 算法）
        """
        # 生成 64 字节的随机密钥（512 位）
        # 使用 secrets.token_urlsafe() 生成 URL-safe base64 编码
        secret_key = secrets.token_urlsafe(64)
        logger.info("[JWTSecretManager] ✅ 已生成新的 JWT Secret Key")
        return secret_key
    
    @staticmethod
    def _encrypt_secret(secret: str) -> str:
        """
        加密 JWT Secret Key
        
        Args:
            secret: 原始密钥
        
        Returns:
            加密后的密钥（base64 编码）
        """
        try:
            master_key = JWTSecretManager._get_master_key()
            fernet = Fernet(master_key)
            encrypted = fernet.encrypt(secret.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"[JWTSecretManager] 加密失败: {e}")
            raise
    
    @staticmethod
    def _decrypt_secret(encrypted_secret: str) -> str:
        """
        解密 JWT Secret Key
        
        Args:
            encrypted_secret: 加密后的密钥（base64 编码）
        
        Returns:
            原始密钥
        """
        try:
            master_key = JWTSecretManager._get_master_key()
            fernet = Fernet(master_key)
            encrypted_bytes = base64.b64decode(encrypted_secret.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"[JWTSecretManager] 解密失败: {e}")
            raise
    
    @staticmethod
    def get_or_create_secret() -> str:
        """
        获取 JWT Secret Key（必需）

        仅从环境变量读取，不在运行时自动写入 `.env` 或自动生成。
        
        Returns:
            JWT Secret Key

        Raises:
            RuntimeError: JWT_SECRET_KEY 未设置
        """
        env_secret = os.getenv('JWT_SECRET_KEY')
        if env_secret:
            logger.debug("[JWTSecretManager] 从环境变量读取 JWT Secret Key")
            return env_secret

        message = (
            "JWT_SECRET_KEY 未设置。已禁用运行时自动写入 .env；"
            "请通过环境变量或密钥管理器显式提供 JWT_SECRET_KEY。"
        )
        logger.error(f"[JWTSecretManager] ❌ {message}")
        raise RuntimeError(message)
    
    @staticmethod
    def save_secret(secret: str, encrypt: bool = True) -> None:
        """
        保存 JWT Secret Key 到文件
        
        Args:
            secret: JWT Secret Key
            encrypt: 是否加密存储（默认 True）
        """
        try:
            if encrypt:
                # 加密存储
                encrypted_secret = JWTSecretManager._encrypt_secret(secret)
                data = {
                    'secret': encrypted_secret,
                    'encrypted': True,
                    'created_at': str(Path(__file__).stat().st_mtime)  # 使用文件修改时间作为参考
                }
                with open(JWT_SECRET_ENCRYPTED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                # 设置文件权限（仅所有者可读）
                os.chmod(JWT_SECRET_ENCRYPTED_FILE, 0o600)
                logger.info(f"[JWTSecretManager] ✅ JWT Secret Key 已加密保存到: {JWT_SECRET_ENCRYPTED_FILE}")
            else:
                # 未加密存储（不推荐，仅用于向后兼容）
                data = {
                    'secret': secret,
                    'encrypted': False
                }
                with open(JWT_SECRET_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                os.chmod(JWT_SECRET_FILE, 0o600)
                logger.warning("[JWTSecretManager] ⚠️ JWT Secret Key 以未加密方式保存（不推荐）")
        except Exception as e:
            logger.error(f"[JWTSecretManager] ❌ 保存 JWT Secret Key 失败: {e}")
            raise
    
    @staticmethod
    def _revoke_all_refresh_tokens() -> int:
        """
        撤销数据库中的所有 refresh tokens（用于密钥轮换）
        
        Returns:
            被撤销的 token 数量
        """
        try:
            from ..core.database import SessionLocal
            from ..models.db_models import RefreshToken
            from datetime import datetime, timezone
            
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)
                # 撤销所有未过期的 refresh tokens
                revoked_count = db.query(RefreshToken).filter(
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now
                ).update({"revoked_at": now})
                db.commit()
                
                if revoked_count > 0:
                    logger.info(f"[JWTSecretManager] ✅ 已撤销 {revoked_count} 个 refresh tokens")
                return revoked_count
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[JWTSecretManager] ❌ 撤销 refresh tokens 失败: {e}")
            return 0
    
    @staticmethod
    def rotate_secret(revoke_tokens: bool = False) -> str:
        """
        轮换 JWT Secret Key（生成新密钥）
        
        注意：
        - 轮换后，所有用旧密钥签名的 JWT Token 将无法验证（签名验证会失败）
        - 默认不清理数据库中的 refresh tokens，让它们自然过期
        - 用户下次尝试刷新 token 时会失败，然后需要重新登录
        - 这样用户体验更好，不会立即被强制退出
        
        Args:
            revoke_tokens: 是否撤销数据库中的所有 refresh tokens（默认 False）
                          - False: 正常轮换，不清理数据库记录（推荐）
                          - True: 强制轮换，清理数据库记录（仅在安全事件时使用）
        
        Returns:
            新的 JWT Secret Key
        """
        if revoke_tokens:
            logger.warning("[JWTSecretManager] ⚠️ 正在强制轮换 JWT Secret Key，将清理所有 refresh tokens")
        else:
            logger.warning("[JWTSecretManager] ⚠️ 正在轮换 JWT Secret Key，旧的 Token 将自然失效")
        
        new_secret = JWTSecretManager.generate_secret_key()
        JWTSecretManager.save_secret(new_secret, encrypt=True)
        
        # 仅在强制轮换时撤销所有 refresh tokens（安全事件场景）
        if revoke_tokens:
            revoked_count = JWTSecretManager._revoke_all_refresh_tokens()
            if revoked_count > 0:
                logger.info(f"[JWTSecretManager] ✅ 已撤销 {revoked_count} 个 refresh tokens")
        else:
            logger.info("[JWTSecretManager] ℹ️ 未清理数据库中的 refresh tokens，它们将自然过期")
        
        logger.info("[JWTSecretManager] ✅ JWT Secret Key 已轮换")
        return new_secret
    
    @staticmethod
    def get_secret_for_display() -> Optional[str]:
        """
        获取 JWT Secret Key 用于显示（仅用于 CLI 命令）
        
        注意：此方法仅用于管理命令，不应在生产代码中使用。
        
        Returns:
            JWT Secret Key（如果存在）
        """
        try:
            return JWTSecretManager.get_or_create_secret()
        except Exception as e:
            logger.error(f"[JWTSecretManager] 获取密钥失败: {e}")
            return None


def get_jwt_secret_key() -> str:
    """
    获取 JWT Secret Key（仅从环境变量读取）

    不在运行时自动生成，也不写入 .env 文件。
    
    此函数用于 jwt_utils.py，确保密钥安全管理。
    
    Returns:
        JWT Secret Key
    """
    return JWTSecretManager.get_or_create_secret()


# ==================== JWT Token 功能 ====================

# JWT 配置
JWT_SECRET_KEY = get_jwt_secret_key()  # ✅ 从安全文件或环境变量获取
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
