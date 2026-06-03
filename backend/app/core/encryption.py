"""
Encryption utilities for sensitive data storage.

This module provides:
1. Encryption/decryption functions for sensitive data (API keys, credentials)
2. ENCRYPTION_KEY management (generation, storage, retrieval)
3. Configuration dictionary encryption/decryption (for storage configs)

ENCRYPTION_KEY 用于加密 JWT Secret Key 和其他敏感数据（如 API keys）。
作为"主密钥"，它比 JWT Secret Key 更重要，需要安全的管理机制。

存储策略（混合方案）：
1. 优先从环境变量读取（生产环境推荐）
2. 如果环境变量不存在，从文件读取（开发环境）
3. 文件存储到 backend/credentials/.encryption_key（不加密，但用文件权限保护）

注意：ENCRYPTION_KEY 是"主密钥"，不能再用另一个密钥加密（否则会有无限递归）。
所以文件存储时不加密，但使用文件权限保护（0o600）。
"""

import os
import base64
from typing import Optional, Dict, Any, Set
from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)


class ConfigDecryptionError(ValueError):
    """Raised when a stored sensitive config value cannot be decrypted."""

    code = "storage_config_credentials_not_decrypted"

    def __init__(self, field: str):
        self.field = field
        super().__init__(
            f"{self.code}: failed to decrypt sensitive config field '{field}'"
        )


def looks_like_fernet_token(data: str) -> bool:
    """Return True when a string has the shape of a stored Fernet token."""
    if not data:
        return False

    value = data.strip()
    if value.startswith("gAAAAA"):
        return True

    try:
        padded = value + ("=" * (-len(value) % 4))
        decoded = base64.b64decode(padded.encode("utf-8"))
        return decoded.decode("utf-8").strip().startswith("gAAAAA")
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return False


def _decrypt_fernet_config_value(fernet: Fernet, value: str) -> str:
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as direct_error:
        try:
            padded = value + ("=" * (-len(value) % 4))
            encrypted_bytes = base64.b64decode(padded.encode("utf-8"))
            return fernet.decrypt(encrypted_bytes).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeDecodeError, base64.binascii.Error):
            raise direct_error

# ==================== ENCRYPTION_KEY 管理 ====================


class EncryptionKeyManager:
    """ENCRYPTION_KEY 管理器"""
    
    @staticmethod
    def generate_key() -> str:
        """
        生成新的 ENCRYPTION_KEY（Fernet 密钥）
        
        Returns:
            32 字节的 base64 编码密钥（Fernet 格式）
        """
        key = Fernet.generate_key()
        return key.decode()
    
    @staticmethod
    def get_or_create_key() -> str:
        """
        获取 ENCRYPTION_KEY（必需）
        
        仅从环境变量读取，不在运行时自动写入 `.env` 或自动生成。
        
        Returns:
            ENCRYPTION_KEY

        Raises:
            RuntimeError: ENCRYPTION_KEY 未设置
        """
        env_key = os.getenv('ENCRYPTION_KEY')
        if env_key:
            logger.debug("[EncryptionKeyManager] 从环境变量读取 ENCRYPTION_KEY")
            return env_key

        message = (
            "ENCRYPTION_KEY 未设置。已禁用运行时自动写入 .env；"
            "请通过环境变量或密钥管理器显式提供 ENCRYPTION_KEY。"
        )
        logger.error(f"[EncryptionKeyManager] ❌ {message}")
        raise RuntimeError(message)


def get_encryption_key() -> str:
    """
    获取 ENCRYPTION_KEY（仅从环境变量读取）
    
    不在运行时自动生成，也不写入 .env 文件。
    
    此函数用于其他模块，确保密钥安全管理。
    
    Returns:
        ENCRYPTION_KEY
    """
    return EncryptionKeyManager.get_or_create_key()


# ==================== 加密/解密功能 ====================

def _get_encryption_key_bytes() -> bytes:
    """
    Get encryption key bytes for Fernet encryption.
    
    Returns:
        Encryption key bytes
    
    Raises:
        ValueError: If ENCRYPTION_KEY cannot be obtained
    """
    key_str = get_encryption_key()
    
    if not key_str:
        raise ValueError("ENCRYPTION_KEY cannot be obtained")
    
    return key_str.encode()


def encrypt_data(data: str) -> str:
    """
    Encrypt sensitive data.
    
    Args:
        data: Plain text data to encrypt
    
    Returns:
        Base64-encoded encrypted data
    
    Raises:
        ValueError: If encryption key is not configured
    """
    if not data:
        return data
    
    try:
        key = _get_encryption_key_bytes()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"[Encryption] Failed to encrypt data: {e}")
        raise


def decrypt_data(encrypted_data: str, silent: bool = False) -> str:
    """
    Decrypt sensitive data.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        silent: If True, don't log errors (for compatibility checks)
    
    Returns:
        Decrypted plain text data
    
    Raises:
        ValueError: If encryption key is not configured or data is invalid
    """
    if not encrypted_data:
        return encrypted_data
    
    try:
        key = _get_encryption_key_bytes()
        fernet = Fernet(key)
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except ValueError as e:
        # ENCRYPTION_KEY 未设置，这是配置问题
        if not silent:
            logger.error(f"[Encryption] ENCRYPTION_KEY not configured: {e}")
        raise
    except Exception as e:
        # 其他解密失败（可能是密钥不匹配、数据格式错误等）
        # 在兼容性检查场景中，不记录 ERROR，只记录 DEBUG
        if silent:
            logger.debug(f"[Encryption] Decryption failed (silent mode): {type(e).__name__}")
        else:
            logger.warning(f"[Encryption] Failed to decrypt data: {type(e).__name__}: {e}")
        raise


def is_encrypted(data: str) -> bool:
    """
    Check if data appears to be encrypted.
    
    通过尝试实际解密来判断数据是否加密，而不是仅检查 base64 格式。
    这样可以避免将明文 API key（可能是 base64 格式）误判为加密数据。
    
    支持两种加密格式：
    1. Fernet token（直接 Fernet 加密，以 'gAAAAA' 开头）- 用于 encrypt_config()
    2. Base64 编码的 Fernet token（双重编码）- 用于 encrypt_data()
    
    Args:
        data: Data to check
    
    Returns:
        True if data can be successfully decrypted
    """
    if not data:
        return False
    
    # 快速检查：如果看起来像 JSON，肯定不是加密的
    if data.strip().startswith('{') or data.strip().startswith('['):
        return False
    
    # 快速检查：如果包含常见 API key 前缀，可能是明文
    common_prefixes = ['sk-', 'pk-', 'AIza', 'Bearer ', 'Basic ']
    if any(data.startswith(prefix) for prefix in common_prefixes):
        return False
    
    # 尝试实际解密：如果能成功解密，则认为是加密的
    try:
        key = _get_encryption_key_bytes()
        fernet = Fernet(key)
        
        # 尝试两种格式：
        # 1. 直接 Fernet token（encrypt_config 使用）
        try:
            fernet.decrypt(data.encode('utf-8'))
            return True
        except Exception:
            pass
        
        # 2. Base64 编码的 Fernet token（encrypt_data 使用）
        try:
            encrypted_bytes = base64.b64decode(data.encode())
            fernet.decrypt(encrypted_bytes)
            return True
        except (ValueError, base64.binascii.Error):
            pass
        
        return False
    except (ValueError, base64.binascii.Error):
        # ENCRYPTION_KEY 未设置或 base64 解码失败，不是加密数据
        return False
    except Exception:
        # 解密失败（密钥不匹配、数据格式错误等），不是加密数据
        return False


# ==================== 配置字典加密/解密功能 ====================

# Sensitive fields that should be encrypted in configuration dictionaries
# 注意：只使用 snake_case 格式（中间件会自动转换前端的 camelCase）
SENSITIVE_FIELDS: Set[str] = {
    # 通用字段
    "token",
    "password",

    # Access Key
    "access_key_id",
    "access_key_secret",

    # Secret Key
    "secret_id",
    "secret_key",

    # Client Secret
    "client_secret",

    # Refresh Token
    "refresh_token",

    # API Key
    "api_key",

    # Google 凭证
    "credentials_json",
}


def encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in a configuration dictionary.
    
    Only encrypts fields listed in SENSITIVE_FIELDS. Other fields are left unchanged.
    Handles nested dictionaries recursively.
    
    Args:
        config: Configuration dictionary to encrypt
        
    Returns:
        Dict with sensitive fields encrypted
        
    Example:
        >>> config = {"token": "secret123", "domain": "example.com"}
        >>> encrypted = encrypt_config(config)
        >>> encrypted["domain"]
        'example.com'
        >>> encrypted["token"]  # Will be encrypted string
        'gAAAAAB...'
    """
    if not config:
        return config
    
    try:
        key = _get_encryption_key_bytes()
        fernet = Fernet(key)
        
        encrypted_config = {}
        
        for field, value in config.items():
            if value is None:
                encrypted_config[field] = value
            elif isinstance(value, dict):
                # Recursively encrypt nested dictionaries
                encrypted_config[field] = encrypt_config(value)
            elif field in SENSITIVE_FIELDS and isinstance(value, str):
                # Encrypt sensitive string fields
                # ✅ 检查是否已经加密，避免重复加密
                if is_encrypted(value):
                    # 已经加密，直接使用
                    encrypted_config[field] = value
                else:
                    # 未加密，进行加密
                    try:
                        encrypted_bytes = fernet.encrypt(value.encode('utf-8'))
                        encrypted_config[field] = encrypted_bytes.decode('utf-8')
                    except Exception as e:
                        logger.error(f"[Encryption] Failed to encrypt field '{field}': {e}")
                        # Keep original value if encryption fails
                        encrypted_config[field] = value
            else:
                # Keep non-sensitive fields unchanged
                encrypted_config[field] = value
        
        return encrypted_config
        
    except Exception as e:
        logger.error(f"[Encryption] Encryption failed: {e}")
        # Return original config if encryption fails
        return config


def decrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in a configuration dictionary.
    
    Only decrypts fields listed in SENSITIVE_FIELDS. Other fields are left unchanged.
    Handles nested dictionaries recursively.
    
    Args:
        config: Configuration dictionary to decrypt
        
    Returns:
        Dict with sensitive fields decrypted
        
    Raises:
        ValueError: If decryption fails due to invalid key or corrupted data
    """
    if not config:
        return config

    fernet: Optional[Fernet] = None
    decrypted_config = {}

    for field, value in config.items():
        if value is None:
            decrypted_config[field] = value
        elif isinstance(value, dict):
            # Recursively decrypt nested dictionaries
            decrypted_config[field] = decrypt_config(value)
        elif field in SENSITIVE_FIELDS and isinstance(value, str):
            if looks_like_fernet_token(value):
                if fernet is None:
                    try:
                        fernet = Fernet(_get_encryption_key_bytes())
                    except ValueError as e:
                        logger.error(
                            "[Encryption] Failed to initialize config decryption for field '%s': %s",
                            field,
                            type(e).__name__,
                        )
                        raise ConfigDecryptionError(field) from e

                try:
                    decrypted_config[field] = _decrypt_fernet_config_value(
                        fernet,
                        value,
                    )
                except InvalidToken as e:
                    logger.warning(
                        "[Encryption] Failed to decrypt sensitive config field '%s': %s",
                        field,
                        type(e).__name__,
                    )
                    raise ConfigDecryptionError(field) from e
            else:
                # 未加密（可能是历史数据），直接使用
                logger.debug(
                    f"[Encryption] Field '{field}' is not encrypted (likely historical data). Using value as-is."
                )
                decrypted_config[field] = value
        else:
            # Keep non-sensitive fields unchanged
            decrypted_config[field] = value

    return decrypted_config


def decrypt_api_key(api_key: str, silent: bool = False) -> str:
    """
    解密 API Key（如果已加密），否则原样返回。

    Args:
        api_key: API Key（可能是明文或已加密）
        silent: 如果为 True，解密失败时 fail-closed 返回空串（绝不返回密文），
            而不是抛异常；如果为 False，解密失败时抛 ConfigDecryptionError。

    Returns:
        解密后的 API Key；当 silent=True 且对一个 Fernet 密文解密失败时返回 ""。

    Raises:
        ConfigDecryptionError: 当 silent=False 且对 Fernet 密文解密失败时
    """
    if not api_key:
        return api_key

    # 仅依据"形状"判断是否为加密令牌（与 ENCRYPTION_KEY 是否匹配无关）。
    # 不能用 is_encrypted()：它在密钥不匹配时吞掉 InvalidToken 并返回 False，
    # 会导致密钥不匹配的 Fernet 密文被当作明文 API key 原样下发给 Provider SDK
    # （fail-open，验证发现项 V-S2）。looks_like_fernet_token 只看形状，因此
    # 密钥不匹配的密文仍会进入下方解密分支并 fail-closed。
    if not looks_like_fernet_token(api_key):
        return api_key

    try:
        return decrypt_data(api_key, silent=silent)
    except Exception as exc:
        # fail-closed：绝不把 Fernet 密文当作明文 API key 返回给调用方。
        if silent:
            # silent 调用方容忍失败，但必须返回空串而非密文，避免把 gAAAA... 发给 Provider。
            logger.error(
                "[decrypt_api_key] 解密失败（ENCRYPTION_KEY 不匹配或数据损坏），"
                "拒绝下发密文，返回空值: %s",
                type(exc).__name__,
            )
            return ""
        raise ConfigDecryptionError("api_key") from exc


def mask_sensitive_fields(config: Dict[str, Any], mask: str = "***") -> Dict[str, Any]:
    """
    Mask sensitive fields in a configuration dictionary for safe logging.
    
    Replaces sensitive field values with a mask string. Handles nested dictionaries.
    
    Args:
        config: Configuration dictionary to mask
        mask: String to use for masking (default: "***")
        
    Returns:
        Dict with sensitive fields masked
        
    Example:
        >>> config = {"token": "secret123", "domain": "example.com"}
        >>> masked = mask_sensitive_fields(config)
        >>> masked
        {'token': '***', 'domain': 'example.com'}
    """
    if not config:
        return config
    
    masked_config = {}
    
    for field, value in config.items():
        if value is None:
            masked_config[field] = value
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            masked_config[field] = mask_sensitive_fields(value, mask)
        elif field in SENSITIVE_FIELDS:
            # Mask sensitive fields
            if isinstance(value, str) and len(value) > 0:
                # Show first 3 characters for debugging, mask the rest
                if len(value) <= 3:
                    masked_config[field] = mask
                else:
                    masked_config[field] = value[:3] + mask
            else:
                masked_config[field] = mask
        else:
            # Keep non-sensitive fields unchanged
            masked_config[field] = value
    
    return masked_config
