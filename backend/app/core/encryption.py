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
    Get or generate encryption key from environment variable.
    
    Returns:
        Encryption key bytes
    
    Raises:
        ValueError: If ENCRYPTION_KEY is not set
    """
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


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt sensitive data.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
    
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
    except Exception as e:
        logger.error(f"[Encryption] Failed to decrypt data: {e}")
        raise


def is_encrypted(data: str) -> bool:
    """
    Check if data appears to be encrypted.
    
    Args:
        data: Data to check
    
    Returns:
        True if data appears to be encrypted (base64 format)
    """
    if not data:
        return False
    
    try:
        # Try to decode as base64
        base64.b64decode(data.encode())
        # If successful and doesn't look like JSON, probably encrypted
        return not (data.strip().startswith('{') or data.strip().startswith('['))
    except Exception:
        return False
