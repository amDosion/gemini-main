"""
Encryption utilities for sensitive data storage.

This module provides simple encryption/decryption for sensitive data like
API keys and service account credentials.
"""

import os
import base64
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


def _get_encryption_key() -> bytes:
    """
    Get encryption key from EncryptionKeyManager (environment variable or file).
    
    Returns:
        Encryption key bytes
    
    Raises:
        ValueError: If ENCRYPTION_KEY cannot be obtained
    """
    try:
        # 使用 EncryptionKeyManager 获取密钥（优先环境变量，然后文件，最后自动生成）
        from .encryption_key_manager import get_encryption_key
        key_str = get_encryption_key()
        
        if not key_str:
            raise ValueError("ENCRYPTION_KEY cannot be obtained")
        
        return key_str.encode()
    except ImportError:
        # 向后兼容：如果 EncryptionKeyManager 不可用，回退到环境变量
        key_str = os.getenv('ENCRYPTION_KEY')
        if not key_str:
            raise ValueError(
                "ENCRYPTION_KEY environment variable is required for data encryption. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
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
        key = _get_encryption_key()
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
        key = _get_encryption_key()
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
        key = _get_encryption_key()
        fernet = Fernet(key)
        encrypted_bytes = base64.b64decode(data.encode())
        # 尝试解密（不抛出异常，只检查是否成功）
        fernet.decrypt(encrypted_bytes)
        return True
    except (ValueError, base64.binascii.Error):
        # ENCRYPTION_KEY 未设置或 base64 解码失败，不是加密数据
        return False
    except Exception:
        # 解密失败（密钥不匹配、数据格式错误等），不是加密数据
        return False
