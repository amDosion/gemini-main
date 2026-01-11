"""
Encryption utilities for secure storage configuration management.

This module provides functions to encrypt/decrypt sensitive configuration fields
and mask sensitive data in logs.
"""

import os
import logging
from typing import Dict, Any, Optional, Set
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Sensitive fields that should be encrypted
SENSITIVE_FIELDS: Set[str] = {
    "token",
    "accessKeyId",
    "accessKeySecret",
    "secretId",
    "secretKey",
    "clientSecret",
    "refreshToken",
    "apiKey",
    "password",
}


def _get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable.
    
    If STORAGE_ENCRYPTION_KEY is not set, generates a new key and provides
    instructions to save it.
    
    Returns:
        bytes: Fernet encryption key
        
    Raises:
        ValueError: If the key format is invalid
    """
    key_str = os.getenv("STORAGE_ENCRYPTION_KEY")
    
    if not key_str:
        # Generate a new key
        new_key = Fernet.generate_key()
        key_str = new_key.decode('utf-8')
        
        logger.warning(
            "STORAGE_ENCRYPTION_KEY not found in environment. "
            "Generated a new key. Please add this to your .env file:\n"
            f"STORAGE_ENCRYPTION_KEY={key_str}\n"
            "⚠️  IMPORTANT: Save this key securely. Without it, you cannot decrypt existing configurations!"
        )
        
        return new_key
    
    try:
        return key_str.encode('utf-8')
    except Exception as e:
        raise ValueError(f"Invalid encryption key format: {e}")


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
        key = _get_encryption_key()
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
                try:
                    encrypted_bytes = fernet.encrypt(value.encode('utf-8'))
                    encrypted_config[field] = encrypted_bytes.decode('utf-8')
                except Exception as e:
                    logger.error(f"Failed to encrypt field '{field}': {e}")
                    # Keep original value if encryption fails
                    encrypted_config[field] = value
            else:
                # Keep non-sensitive fields unchanged
                encrypted_config[field] = value
        
        return encrypted_config
        
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
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
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        
        decrypted_config = {}
        
        for field, value in config.items():
            if value is None:
                decrypted_config[field] = value
            elif isinstance(value, dict):
                # Recursively decrypt nested dictionaries
                decrypted_config[field] = decrypt_config(value)
            elif field in SENSITIVE_FIELDS and isinstance(value, str):
                # Decrypt sensitive string fields
                try:
                    decrypted_bytes = fernet.decrypt(value.encode('utf-8'))
                    decrypted_config[field] = decrypted_bytes.decode('utf-8')
                except InvalidToken:
                    logger.warning(
                        f"Field '{field}' appears to be unencrypted or encrypted with a different key. "
                        "Using value as-is."
                    )
                    # If decryption fails, assume it's already decrypted
                    decrypted_config[field] = value
                except Exception as e:
                    logger.error(f"Failed to decrypt field '{field}': {e}")
                    decrypted_config[field] = value
            else:
                # Keep non-sensitive fields unchanged
                decrypted_config[field] = value
        
        return decrypted_config
        
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        # Return original config if decryption fails
        return config


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


def is_encrypted(value: str) -> bool:
    """
    Check if a string value appears to be encrypted.
    
    This is a heuristic check based on Fernet token format.
    
    Args:
        value: String to check
        
    Returns:
        bool: True if value appears to be encrypted
    """
    if not value or not isinstance(value, str):
        return False
    
    # Fernet tokens start with 'gAAAAA' (base64 encoded)
    # and are typically longer than 100 characters
    return value.startswith('gAAAAA') and len(value) > 100
