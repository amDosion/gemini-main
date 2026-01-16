"""
Encryption utilities for sensitive data storage.

This module provides:
1. Encryption/decryption functions for sensitive data (API keys, credentials)
2. ENCRYPTION_KEY management (generation, storage, retrieval)

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
import json
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

# ==================== ENCRYPTION_KEY 管理 ====================

# 文件路径
_credentials_dir = Path(__file__).resolve().parents[2] / "credentials"
_credentials_dir.mkdir(exist_ok=True)

ENCRYPTION_KEY_FILE = _credentials_dir / ".encryption_key"


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
    def save_key(key: str) -> None:
        """
        保存 ENCRYPTION_KEY 到文件
        
        Args:
            key: ENCRYPTION_KEY（Fernet 格式）
        """
        try:
            # 确保目录存在
            _credentials_dir.mkdir(exist_ok=True)
            
            # 保存到文件（不加密，但用文件权限保护）
            data = {
                'key': key,
                'generated_at': str(Path(__file__).stat().st_mtime)  # 简单的时间戳
            }
            with open(ENCRYPTION_KEY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # 设置文件权限（仅所有者可读）
            os.chmod(ENCRYPTION_KEY_FILE, 0o600)
            logger.info(f"[EncryptionKeyManager] ✅ ENCRYPTION_KEY 已保存到: {ENCRYPTION_KEY_FILE}")
        except Exception as e:
            logger.error(f"[EncryptionKeyManager] ❌ 保存 ENCRYPTION_KEY 失败: {e}")
            raise
    
    @staticmethod
    def load_key_from_file() -> Optional[str]:
        """
        从文件加载 ENCRYPTION_KEY
        
        Returns:
            ENCRYPTION_KEY 或 None（如果文件不存在）
        """
        try:
            if not ENCRYPTION_KEY_FILE.exists():
                return None
            
            with open(ENCRYPTION_KEY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('key')
        except Exception as e:
            logger.warning(f"[EncryptionKeyManager] 从文件加载 ENCRYPTION_KEY 失败: {e}")
            return None
    
    @staticmethod
    def _write_to_env_file(key_name: str, key_value: str) -> None:
        """
        将密钥写入 .env 文件
        
        Args:
            key_name: 密钥名称（如 ENCRYPTION_KEY）
            key_value: 密钥值
        """
        try:
            # 查找 .env 文件（在 backend 目录）
            env_file = Path(__file__).resolve().parents[2] / ".env"
            
            # 读取现有内容
            existing_content = ""
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # 检查是否已存在该密钥
            lines = existing_content.split('\n')
            key_found = False
            new_lines = []
            
            for line in lines:
                # 检查是否是注释行或空行
                stripped = line.strip()
                if stripped.startswith('#') or not stripped:
                    new_lines.append(line)
                    continue
                
                # 检查是否是该密钥
                if stripped.startswith(f'{key_name}='):
                    # 更新现有密钥
                    new_lines.append(f'{key_name}={key_value}')
                    key_found = True
                else:
                    new_lines.append(line)
            
            # 如果未找到，添加到末尾
            if not key_found:
                if new_lines and new_lines[-1] and not new_lines[-1].strip().endswith('\n'):
                    new_lines.append('')
                new_lines.append(f'{key_name}={key_value}')
            
            # 写入文件
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            
            logger.info(f"[EncryptionKeyManager] ✅ 已将 {key_name} 写入 .env 文件: {env_file}")
        except Exception as e:
            logger.error(f"[EncryptionKeyManager] ❌ 写入 .env 文件失败: {e}")
            raise
    
    @staticmethod
    def get_or_create_key() -> str:
        """
        获取或创建 ENCRYPTION_KEY
        
        优先级：
        1. 环境变量 ENCRYPTION_KEY（从 .env 文件加载）
        2. 自动生成新密钥（首次运行，并自动保存到 .env 文件）
        
        Returns:
            ENCRYPTION_KEY
        """
        # 1. 优先从环境变量读取（从 .env 文件加载）
        env_key = os.getenv('ENCRYPTION_KEY')
        if env_key:
            logger.debug("[EncryptionKeyManager] 从环境变量读取 ENCRYPTION_KEY")
            return env_key
        
        # 2. 自动生成新密钥（首次运行）
        logger.warning(
            "[EncryptionKeyManager] ⚠️ ENCRYPTION_KEY 未设置，自动生成新密钥（首次运行）"
        )
        new_key = EncryptionKeyManager.generate_key()
        
        # 自动写入 .env 文件
        try:
            EncryptionKeyManager._write_to_env_file('ENCRYPTION_KEY', new_key)
            logger.info(
                "[EncryptionKeyManager] ✅ 已自动生成并写入 .env 文件 ENCRYPTION_KEY"
            )
        except Exception as e:
            logger.error(
                f"[EncryptionKeyManager] ❌ 自动写入 .env 文件失败: {e}，"
                f"请手动添加 ENCRYPTION_KEY={new_key} 到 .env 文件"
            )
        
        return new_key


def get_encryption_key() -> str:
    """
    获取 ENCRYPTION_KEY（从环境变量读取，即从 .env 文件加载）
    
    优先级：
    1. 环境变量 ENCRYPTION_KEY（从 .env 文件加载）
    2. 自动生成新密钥（首次运行）
    
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
