"""
Provider Factory Module

This module provides a factory class for creating AI provider service instances.
The factory uses configuration-driven auto-registration to automatically register
providers based on ProviderConfig.

Design:
- Configuration-driven: Providers are registered based on ProviderConfig.CONFIGS
- Auto-registration: Providers are registered automatically on first use
- OpenAI-compatible: Providers with client_type="openai" use OpenAIService
- Extensible: Manual registration still supported for custom providers
"""

from typing import Optional, Dict, Type
import logging
from sqlalchemy.orm import Session
from .base_provider import BaseProviderService
from .provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Factory class for creating AI provider service instances.
    
    This factory uses configuration-driven auto-registration to create provider
    service instances. Providers are automatically registered based on
    ProviderConfig.CONFIGS on first use.
    
    Example:
        >>> service = ProviderFactory.create("openai", api_key="sk-...")
        >>> models = await service.get_available_models()
    """
    
    # Registry of provider names to service classes
    _providers: Dict[str, Type[BaseProviderService]] = {}
    # Initialization flag
    _initialized = False
    
    @classmethod
    def create(
        cls, 
        provider: str, 
        api_key: str, 
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs
    ) -> BaseProviderService:
        """
        Create a provider service instance.
        
        Args:
            provider: Provider name (e.g., 'openai', 'google', 'ollama')
            api_key: API key for authentication
            api_url: Optional custom API URL (overrides config base_url)
            user_id: Optional user ID for user-specific configuration (e.g., Vertex AI)
            db: Optional database session for loading user-specific configuration
            **kwargs: Additional configuration parameters passed to the service
        
        Returns:
            Instance of the appropriate provider service class
        
        Raises:
            ValueError: If provider name is not registered
        
        Example:
            >>> service = ProviderFactory.create(
            ...     "google",
            ...     api_key="...",
            ...     user_id="user123",
            ...     db=db_session
            ... )
        """
        # Ensure providers are registered
        if not cls._initialized:
            cls._auto_register()
        
        if provider not in cls._providers:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Available providers: {', '.join(cls._providers.keys())}"
            )
        
        service_class = cls._providers[provider]
        
        # If no api_url provided, use config base_url
        if api_url is None:
            api_url = ProviderConfig.get_base_url(provider)
        
        # Pass user_id and db to Google providers for Vertex AI support
        # Other providers don't need these parameters yet
        if provider in ['google', 'google-custom']:
            return service_class(api_key, api_url, user_id=user_id, db=db, **kwargs)
        else:
            return service_class(api_key, api_url, **kwargs)
    
    @classmethod
    def _auto_register(cls):
        """
        Automatically register providers based on ProviderConfig.
        
        This method iterates through ProviderConfig.CONFIGS and registers
        providers based on their client_type:
        - client_type="openai": Use OpenAIService (OpenAI-compatible)
        - client_type="google": Use GoogleService
        - client_type="ollama": Use OllamaService (even though OpenAI-compatible)
        
        This method is called automatically on first use of create().
        """
        logger.info("[Provider Factory] Auto-registering providers from config")
        
        # Import service classes
        from .openai_service import OpenAIService
        
        try:
            from .gemini.google_service import GoogleService
        except ImportError:
            GoogleService = None
            logger.warning("[Provider Factory] GoogleService not available")
        
        try:
            from .ollama.ollama import OllamaService
        except ImportError:
            OllamaService = None
            logger.warning("[Provider Factory] OllamaService not available")
        
        try:
            from .qwen_native import QwenNativeProvider
        except ImportError:
            QwenNativeProvider = None
            logger.warning("[Provider Factory] QwenNativeProvider not available (dashscope SDK not installed)")
        
        # Iterate through config and register providers
        for provider_id, config in ProviderConfig.CONFIGS.items():
            client_type = config.get("client_type")
            
            # Register based on client_type
            if client_type == "openai":
                # OpenAI-compatible providers use OpenAIService
                cls._providers[provider_id] = OpenAIService
                logger.info(f"[Provider Factory] Registered {provider_id} (OpenAI-compatible)")
            
            elif client_type == "google" and GoogleService:
                cls._providers[provider_id] = GoogleService
                logger.info(f"[Provider Factory] Registered {provider_id} (Google)")
            
            elif client_type == "ollama" and OllamaService:
                # Ollama uses dedicated service (even though OpenAI-compatible)
                cls._providers[provider_id] = OllamaService
                logger.info(f"[Provider Factory] Registered {provider_id} (Ollama)")
            
            elif client_type == "dashscope" and QwenNativeProvider:
                # DashScope uses native SDK (Qwen/Tongyi)
                cls._providers[provider_id] = QwenNativeProvider
                logger.info(f"[Provider Factory] Registered {provider_id} (DashScope Native SDK)")
            
            else:
                logger.warning(
                    f"[Provider Factory] No service class for {provider_id} "
                    f"(client_type: {client_type})"
                )
        
        cls._initialized = True
        logger.info(f"[Provider Factory] Auto-registration complete. Registered {len(cls._providers)} providers")
    
    @classmethod
    def register(cls, provider: str, service_class: Type[BaseProviderService]) -> None:
        """
        Manually register a provider service class.
        
        This method allows dynamic registration of custom provider implementations
        at runtime. Useful for plugins or extensions.
        
        Args:
            provider: Provider name (e.g., 'custom-provider')
            service_class: Service class that inherits from BaseProviderService
        
        Raises:
            TypeError: If service_class doesn't inherit from BaseProviderService
        
        Example:
            >>> class CustomProvider(BaseProviderService):
            ...     pass
            >>> ProviderFactory.register("custom", CustomProvider)
        """
        if not issubclass(service_class, BaseProviderService):
            raise TypeError(
                f"Service class must inherit from BaseProviderService, "
                f"got {service_class.__name__}"
            )
        
        cls._providers[provider] = service_class
        logger.info(f"[Provider Factory] Manually registered {provider}")
    
    @classmethod
    def unregister(cls, provider: str) -> None:
        """
        Unregister a provider service class.
        
        Args:
            provider: Provider name to unregister
        
        Raises:
            ValueError: If provider name is not registered
        
        Example:
            >>> ProviderFactory.unregister("custom")
        """
        if provider not in cls._providers:
            raise ValueError(f"Provider '{provider}' is not registered")
        
        del cls._providers[provider]
        logger.info(f"[Provider Factory] Unregistered {provider}")
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """
        Get list of all registered provider names.
        
        Returns:
            List of provider names
        
        Example:
            >>> providers = ProviderFactory.list_providers()
            >>> print(providers)
            ['openai', 'google', 'ollama', 'deepseek', 'moonshot', ...]
        """
        if not cls._initialized:
            cls._auto_register()
        return list(cls._providers.keys())
    
    @classmethod
    def is_registered(cls, provider: str) -> bool:
        """
        Check if a provider is registered.
        
        Args:
            provider: Provider name to check
        
        Returns:
            True if provider is registered, False otherwise
        
        Example:
            >>> if ProviderFactory.is_registered("openai"):
            ...     service = ProviderFactory.create("openai", api_key="...")
        """
        if not cls._initialized:
            cls._auto_register()
        return provider in cls._providers
