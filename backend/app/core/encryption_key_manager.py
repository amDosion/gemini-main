"""
Encryption Key Manager - 管理 ENCRYPTION_KEY（主密钥）

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
import json
import secrets
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

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
        from cryptography.fernet import Fernet
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
    def get_or_create_key() -> str:
        """
        获取或创建 ENCRYPTION_KEY
        
        优先级：
        1. 环境变量 ENCRYPTION_KEY（生产环境推荐）
        2. 文件 backend/credentials/.encryption_key（开发环境）
        3. 自动生成新密钥（首次运行）
        
        Returns:
            ENCRYPTION_KEY
        """
        # 1. 优先从环境变量读取（生产环境推荐）
        env_key = os.getenv('ENCRYPTION_KEY')
        if env_key:
            logger.debug("[EncryptionKeyManager] 从环境变量读取 ENCRYPTION_KEY")
            return env_key
        
        # 2. 从文件读取（开发环境）
        file_key = EncryptionKeyManager.load_key_from_file()
        if file_key:
            logger.debug("[EncryptionKeyManager] 从文件读取 ENCRYPTION_KEY")
            return file_key
        
        # 3. 自动生成新密钥（首次运行）
        logger.warning(
            "[EncryptionKeyManager] ⚠️ ENCRYPTION_KEY 未设置，自动生成新密钥（首次运行）"
        )
        new_key = EncryptionKeyManager.generate_key()
        EncryptionKeyManager.save_key(new_key)
        logger.info(
            "[EncryptionKeyManager] ✅ 已自动生成并保存 ENCRYPTION_KEY 到文件"
        )
        logger.warning(
            "[EncryptionKeyManager] ⚠️ 生产环境建议设置 ENCRYPTION_KEY 环境变量，而不是使用文件存储"
        )
        return new_key


# 全局函数：获取 ENCRYPTION_KEY（用于 encryption.py）
def get_encryption_key() -> str:
    """
    获取 ENCRYPTION_KEY（优先从 Key Service 获取，否则从环境变量/文件读取）
    
    优先级：
    1. Key Service（如果可用，方案 D）
    2. 环境变量 ENCRYPTION_KEY（生产环境推荐）
    3. 文件 backend/credentials/.encryption_key（开发环境）
    4. 自动生成新密钥（首次运行）
    
    此函数用于 encryption.py，确保密钥安全管理。
    
    Returns:
        ENCRYPTION_KEY
    """
    # 优先从 Key Service 获取（方案 D）
    try:
        from .key_service_client import get_encryption_key as get_key_from_service
        return get_key_from_service()
    except (ImportError, RuntimeError) as e:
        # Key Service 不可用，回退到文件存储
        logger.debug(f"[EncryptionKeyManager] Key Service 不可用，使用文件存储: {e}")
        return EncryptionKeyManager.get_or_create_key()
