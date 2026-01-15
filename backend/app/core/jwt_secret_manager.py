"""
JWT Secret Key 管理器

安全地管理 JWT Secret Key：
- 自动生成强随机密钥
- 加密存储到安全文件
- 提供 CLI 命令查看和管理
- 确保不会泄露到代码或配置文件中
"""
import os
import secrets
import json
import base64
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

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
    1. 自动生成强随机密钥（64字节，URL-safe base64编码）
    2. 加密存储到安全文件（使用 Fernet 对称加密）
    3. 提供安全的读取接口
    4. 支持密钥轮换
    """
    
    @staticmethod
    def _get_master_key() -> bytes:
        """
        获取主加密密钥（用于加密 JWT Secret Key）
        
        优先级：
        1. ENCRYPTION_KEY 环境变量（与 encryption.py 使用相同的密钥）
        2. 如果不存在，使用基于系统信息的派生密钥（仅用于开发环境）
        
        Returns:
            加密密钥（bytes）
        """
        # 优先使用 EncryptionKeyManager（与 encryption.py 保持一致）
        try:
            from .encryption_key_manager import get_encryption_key
            master_key = get_encryption_key()
            if master_key:
                return master_key.encode()
        except ImportError:
            # 向后兼容：如果 EncryptionKeyManager 不可用，回退到环境变量
            master_key = os.getenv('ENCRYPTION_KEY')
            if master_key:
                return master_key.encode()
        
        # 开发环境回退：使用基于项目路径的派生密钥（不安全，仅用于开发）
        # 生产环境必须设置 ENCRYPTION_KEY
        logger.warning(
            "[JWTSecretManager] ⚠️ ENCRYPTION_KEY 未设置，使用开发环境回退密钥。"
            "生产环境必须设置 ENCRYPTION_KEY 环境变量！"
        )
        
        # 使用项目根目录路径生成一个固定的密钥（仅用于开发）
        project_root = Path(__file__).resolve().parents[3]
        key_material = str(project_root).encode()
        # 使用 SHA256 派生一个 32 字节的密钥
        import hashlib
        derived_key = hashlib.sha256(key_material).digest()
        # 转换为 Fernet 格式（base64url 编码）
        return base64.urlsafe_b64encode(derived_key)
    
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
        获取或创建 JWT Secret Key
        
        如果密钥文件不存在，自动生成并保存。
        如果密钥文件存在，读取并返回。
        
        Returns:
            JWT Secret Key
        """
        # 优先尝试读取加密文件
        if JWT_SECRET_ENCRYPTED_FILE.exists():
            try:
                with open(JWT_SECRET_ENCRYPTED_FILE, 'r', encoding='utf-8') as f:
                    encrypted_data = json.load(f)
                    encrypted_secret = encrypted_data.get('secret')
                    if encrypted_secret:
                        secret = JWTSecretManager._decrypt_secret(encrypted_secret)
                        logger.debug("[JWTSecretManager] ✅ 从加密文件读取 JWT Secret Key")
                        return secret
            except Exception as e:
                logger.warning(f"[JWTSecretManager] 读取加密文件失败: {e}，尝试读取未加密文件")
        
        # 回退：读取未加密文件（向后兼容）
        if JWT_SECRET_FILE.exists():
            try:
                with open(JWT_SECRET_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    secret = data.get('secret')
                    if secret:
                        logger.debug("[JWTSecretManager] ✅ 从文件读取 JWT Secret Key")
                        # 自动升级：将未加密的密钥加密保存
                        JWTSecretManager.save_secret(secret, encrypt=True)
                        # 删除未加密文件
                        try:
                            JWT_SECRET_FILE.unlink()
                            logger.info("[JWTSecretManager] ✅ 已升级为加密存储，删除未加密文件")
                        except Exception:
                            pass
                        return secret
            except Exception as e:
                logger.warning(f"[JWTSecretManager] 读取文件失败: {e}")
        
        # 如果文件不存在，生成新密钥
        logger.info("[JWTSecretManager] JWT Secret Key 文件不存在，生成新密钥...")
        secret = JWTSecretManager.generate_secret_key()
        JWTSecretManager.save_secret(secret, encrypt=True)
        logger.info("[JWTSecretManager] ✅ 已生成并保存新的 JWT Secret Key")
        return secret
    
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


# 全局函数：获取 JWT Secret Key（用于 jwt_utils.py）
def get_jwt_secret_key() -> str:
    """
    获取 JWT Secret Key（优先从 Key Service 获取，否则从安全文件读取）
    
    优先级：
    1. Key Service（如果可用，方案 D）
    2. 从安全文件读取（加密存储）
    3. 从环境变量读取（向后兼容，但不推荐）
    4. 自动生成新密钥（首次运行）
    
    此函数用于 jwt_utils.py，确保密钥安全管理。
    
    Returns:
        JWT Secret Key
    """
    # 优先从 Key Service 获取（方案 D）
    # 注意：需要检查 Key Service 是否已初始化，避免循环依赖
    try:
        from .key_service_client import is_key_service_available, _key_service_client
        if is_key_service_available() and _key_service_client:
            return _key_service_client.get_jwt_secret_key()
    except (ImportError, RuntimeError, AttributeError) as e:
        # Key Service 不可用，回退到文件存储
        logger.debug(f"[JWTSecretManager] Key Service 不可用，使用文件存储: {e}")
    
    # 优先级：
    # 1. 从安全文件读取（加密存储）
    # 2. 从环境变量读取（向后兼容，但不推荐）
    # 3. 自动生成新密钥（首次运行）
    
    # 优先从安全文件读取
    try:
        secret = JWTSecretManager.get_or_create_secret()
        if secret and secret != "your-super-secret-key-change-in-production":
            return secret
    except Exception as e:
        logger.warning(f"[JWTSecretManager] 从安全文件读取失败: {e}")
    
    # 回退：从环境变量读取（向后兼容，但不推荐）
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret and env_secret != "your-super-secret-key-change-in-production":
        logger.warning(
            "[JWTSecretManager] ⚠️ 从环境变量读取 JWT Secret Key（不推荐）。"
            "建议使用安全文件存储。运行 'python -m backend.scripts.manage_jwt_secret' 查看密钥。"
        )
        return env_secret
    
    # 最后回退：使用默认值（仅用于开发环境）
    logger.error(
        "[JWTSecretManager] ❌ 无法获取 JWT Secret Key，使用默认值（不安全）。"
        "请运行 'python -m backend.scripts.manage_jwt_secret generate' 生成密钥。"
    )
    return "your-super-secret-key-change-in-production"
