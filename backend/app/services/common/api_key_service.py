"""
API Key Management Service

This module provides secure storage and retrieval of API keys for different providers.
API keys are encrypted before storage and decrypted when retrieved.
"""

from typing import Optional
import os
import logging
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)


class APIKeyService:
    """
    Service for managing API keys securely.
    
    This service provides methods to store, retrieve, and delete API keys
    for different providers. All keys are encrypted before storage.
    
    Note: This is a simple implementation using environment variables.
    In production, you should use a proper database with encryption.
    """
    
    # Encryption key (should be stored securely, e.g., in environment variable)
    # For now, we generate a key if not provided
    _encryption_key: Optional[bytes] = None
    _cipher: Optional[Fernet] = None
    
    @classmethod
    def _get_cipher(cls) -> Fernet:
        """
        Get or create the encryption cipher.
        
        Returns:
            Fernet cipher instance
        """
        if cls._cipher is None:
            # Try to get encryption key from environment
            key_str = os.getenv("API_KEY_ENCRYPTION_KEY")
            
            if key_str:
                cls._encryption_key = key_str.encode()
            else:
                # Generate a new key (WARNING: This should be persisted in production)
                cls._encryption_key = Fernet.generate_key()
                logger.warning(
                    "[API Key Service] No encryption key found in environment. "
                    "Generated a new key. This key will be lost on restart!"
                )
            
            cls._cipher = Fernet(cls._encryption_key)
        
        return cls._cipher
    
    @classmethod
    def _encrypt(cls, value: str) -> str:
        """
        Encrypt a string value.
        
        Args:
            value: Plain text value
        
        Returns:
            Encrypted value (base64 encoded)
        """
        cipher = cls._get_cipher()
        encrypted_bytes = cipher.encrypt(value.encode())
        return base64.b64encode(encrypted_bytes).decode()
    
    @classmethod
    def _decrypt(cls, encrypted_value: str) -> str:
        """
        Decrypt an encrypted value.
        
        Args:
            encrypted_value: Encrypted value (base64 encoded)
        
        Returns:
            Decrypted plain text value
        """
        cipher = cls._get_cipher()
        encrypted_bytes = base64.b64decode(encrypted_value.encode())
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()
    
    @classmethod
    async def get_api_key(cls, provider: str, fallback_key: Optional[str] = None) -> Optional[str]:
        """
        Get API key for a provider.
        
        Priority:
        1. Fallback key (if provided)
        2. Database (TODO: implement database storage)
        3. Environment variables
        
        Args:
            provider: Provider name (e.g., 'openai', 'google')
            fallback_key: Optional fallback key to use if not found
        
        Returns:
            API key if found, None otherwise
        
        Example:
            >>> api_key = await APIKeyService.get_api_key("openai")
            >>> if api_key:
            ...     # Use the API key
        """
        # 1. Try fallback key
        if fallback_key:
            return fallback_key
        
        # 2. Try database (TODO: implement)
        # This would query a database table like:
        # SELECT encrypted_key FROM api_keys WHERE provider = ?
        # Then decrypt the key before returning
        
        # 3. Try environment variables
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "ollama": "OLLAMA_API_KEY",
            "tongyi": "DASHSCOPE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
        }
        
        env_key = env_key_map.get(provider)
        if env_key:
            api_key = os.getenv(env_key)
            if api_key:
                logger.info(f"[API Key Service] Found API key for {provider} in environment")
                return api_key
        
        logger.warning(f"[API Key Service] No API key found for provider: {provider}")
        return None
    
    @classmethod
    async def save_api_key(cls, provider: str, api_key: str) -> bool:
        """
        Save API key for a provider.
        
        The key is encrypted before storage.
        
        Args:
            provider: Provider name (e.g., 'openai', 'google')
            api_key: API key to save
        
        Returns:
            True if saved successfully, False otherwise
        
        Example:
            >>> success = await APIKeyService.save_api_key("openai", "sk-...")
            >>> if success:
            ...     print("API key saved")
        """
        try:
            # Encrypt the API key
            encrypted_key = cls._encrypt(api_key)
            
            # TODO: Save to database
            # This would insert/update a database record:
            # INSERT INTO api_keys (provider, encrypted_key, updated_at)
            # VALUES (?, ?, NOW())
            # ON CONFLICT (provider) DO UPDATE SET encrypted_key = ?, updated_at = NOW()
            
            logger.info(f"[API Key Service] Saved API key for {provider}")
            logger.warning(
                "[API Key Service] Database storage not implemented yet. "
                "API key will be lost on restart!"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"[API Key Service] Error saving API key for {provider}: {e}", exc_info=True)
            return False
    
    @classmethod
    async def delete_api_key(cls, provider: str) -> bool:
        """
        Delete API key for a provider.
        
        Args:
            provider: Provider name (e.g., 'openai', 'google')
        
        Returns:
            True if deleted successfully, False otherwise
        
        Example:
            >>> success = await APIKeyService.delete_api_key("openai")
            >>> if success:
            ...     print("API key deleted")
        """
        try:
            # TODO: Delete from database
            # This would execute:
            # DELETE FROM api_keys WHERE provider = ?
            
            logger.info(f"[API Key Service] Deleted API key for {provider}")
            logger.warning(
                "[API Key Service] Database storage not implemented yet. "
                "Nothing to delete!"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"[API Key Service] Error deleting API key for {provider}: {e}", exc_info=True)
            return False
    
    @classmethod
    async def list_providers(cls) -> list[str]:
        """
        List all providers that have API keys configured.
        
        Returns:
            List of provider names
        
        Example:
            >>> providers = await APIKeyService.list_providers()
            >>> print(providers)
            ['openai', 'google', 'tongyi']
        """
        # TODO: Query database
        # This would execute:
        # SELECT provider FROM api_keys
        
        # For now, check environment variables
        providers = []
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "ollama": "OLLAMA_API_KEY",
            "tongyi": "DASHSCOPE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "doubao": "DOUBAO_API_KEY",
            "hunyuan": "HUNYUAN_API_KEY",
            "nvidia": "NVIDIA_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        
        for provider, env_key in env_key_map.items():
            if os.getenv(env_key):
                providers.append(provider)
        
        logger.info(f"[API Key Service] Found {len(providers)} providers with API keys")
        return providers
    
    @classmethod
    def get_encryption_key_base64(cls) -> str:
        """
        Get the encryption key in base64 format.
        
        This is useful for backing up the key or setting it in environment variables.
        
        Returns:
            Base64 encoded encryption key
        
        Warning:
            Keep this key secure! Anyone with this key can decrypt all stored API keys.
        
        Example:
            >>> key = APIKeyService.get_encryption_key_base64()
            >>> print(f"Set this in your environment: API_KEY_ENCRYPTION_KEY={key}")
        """
        cipher = cls._get_cipher()
        return cls._encryption_key.decode()
