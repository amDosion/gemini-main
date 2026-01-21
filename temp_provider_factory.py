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
from .client_selector import ClientSelectorFactory
from .errors import (
    ClientCreationError,
    ConfigurationError,
    ErrorContext,
    RequestIDManager
)

logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Factory class for creating AI provider service instances.
    
    This factory uses configuration-driven auto-registration to create provider
    service instances. Providers are automatically registered based on
    ProviderConfig.CONFIGS on first use.
    
    Caching Strategy:
    - Cache key: f"{provider}:{api_key}"
    - Scope: Per (provider, api_key) tuple
    - Lifetime: Application lifetime (until clear_cache() called)
    - Thread-safe: Uses class-level dict (GIL-protected in CPython)
    
    Example:
        >>> service = ProviderFactory.create("openai", api_key="sk-...")
        >>> models = await service.get_available_models()
    """
    
    # Registry of provider names to service classes
    _providers: Dict[str, Type[BaseProviderService]] = {}
    # Client instance cache
    _client_cache: Dict[str, BaseProviderService] = {}
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
        request_id: Optional[str] = None,
        **kwargs
    ) -> BaseProviderService:
        """
        Create or retrieve cached provider service instance.
        
        Caching Logic:
        1. Check if (provider, api_key) exists in cache
        2. If yes: Return cached instance
        3. If no: Create new instance, cache it, return it
        
        Dual-Client Support:
        - For providers with dual-client configuration (Qwen, Ollama),
          a ClientSelector is instantiated and passed to the service
        - The service can use the selector to choose between primary/secondary clients
        
        Args:
            provider: Provider name (e.g., 'openai', 'google', 'ollama')
            api_key: API key for authentication
            api_url: Optional custom API URL (overrides config base_url)
            user_id: Optional user ID for user-specific configuration (e.g., Vertex AI)
            db: Optional database session for loading user-specific configuration
            request_id: Optional request ID for tracing
            **kwargs: Additional configuration parameters passed to the service
        
        Returns:
            Cached or newly created provider service instance
        
        Raises:
            ConfigurationError: If provider name is not registered
            ClientCreationError: If client creation fails
        
        Example:
            >>> service = ProviderFactory.create(
            ...     "google",
            ...     api_key="...",
            ...     user_id="user123",
            ...     db=db_session
            ... )
        """
        import time
        import sys
        start_time = time.time()
        
        logger.info(f"[ProviderFactory] 🔄 开始创建服务: provider={provider}, user_id={user_id[:8] + '...' if user_id else 'None'}")
        print(f"[ProviderFactory] 🔄 开始创建服务: provider={provider}, user_id={user_id[:8] + '...' if user_id else 'None'}", file=sys.stderr, flush=True)
        
        # Generate request ID if not provided
        if not request_id:
            request_id = RequestIDManager.generate()
        
        # Ensure providers are registered
        if not cls._initialized:
            logger.info(f"[ProviderFactory] 🔄 自动注册提供商...")
            print(f"[ProviderFactory] 🔄 自动注册提供商...", file=sys.stderr, flush=True)
            cls._auto_register()
            logger.info(f"[ProviderFactory] ✅ 提供商注册完成")
            print(f"[ProviderFactory] ✅ 提供商注册完成", file=sys.stderr, flush=True)
        
        # Check cache first
        cache_key = f"{provider}:{api_key}"
        if cache_key in cls._client_cache:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[ProviderFactory] ✅ 使用缓存服务 (耗时: {elapsed:.2f}ms)")
            print(f"[ProviderFactory] ✅ 使用缓存服务 (耗时: {elapsed:.2f}ms)", file=sys.stderr, flush=True)
            return cls._client_cache[cache_key]
        
        # Validate provider exists
        if provider not in cls._providers:
            context = ErrorContext(
                provider_id=provider,
                client_type='single',
                operation='create_client',
                request_id=request_id,
                user_id=user_id
            )
            raise ConfigurationError(
                message=f"Unknown provider: {provider}. Available providers: {', '.join(cls._providers.keys())}",
                context=context
            )
        
        service_class = cls._providers[provider]
        
        # If no api_url provided, use config base_url
        if api_url is None:
            api_url = ProviderConfig.get_base_url(provider)
        
        # Check if provider supports dual-client mode
        has_dual_client = ProviderConfig.has_dual_client_support(provider)
        
        # If dual-client supported, get ClientSelector for this provider
        if has_dual_client:
            client_selector = ClientSelectorFactory.get_selector(provider)
            kwargs['client_selector'] = client_selector
            logger.info(
                f"[Provider Factory] Dual-client provider {provider}, using {client_selector.__class__.__name__}",
                extra={'request_id': request_id, 'provider': provider, 'client_selector': client_selector.__class__.__name__}
            )
        
        try:
            # Pass user_id and db to providers that need them
            # Google: for Vertex AI support
            # Tongyi: for future features (currently optional)
            if provider in ['google', 'google-custom', 'tongyi']:
                service = service_class(api_key, api_url, user_id=user_id, db=db, **kwargs)
            else:
                service = service_class(api_key, api_url, **kwargs)
            
            # Cache before returning
            cls._client_cache[cache_key] = service
            elapsed = (time.time() - start_time) * 1000
            service_type = type(service).__name__
            logger.info(f"[ProviderFactory] ✅ 服务创建完成 (耗时: {elapsed:.2f}ms)")
            print(f"[ProviderFactory] ✅ 服务创建完成 (耗时: {elapsed:.2f}ms)", file=sys.stderr, flush=True)
            logger.info(f"[ProviderFactory]     - service类型: {service_type}")
            print(f"[ProviderFactory]     - service类型: {service_type}", file=sys.stderr, flush=True)
            logger.info(f"[ProviderFactory]     - 已缓存: {cache_key}")
            print(f"[ProviderFactory]     - 已缓存: {cache_key}", file=sys.stderr, flush=True)
            return service
            
        except Exception as e:
            # Wrap any exception in ClientCreationError
            context = ErrorContext(
                provider_id=provider,
                client_type='primary' if has_dual_client else 'single',
                operation='create_client',
                request_id=request_id,
                user_id=user_id,
                additional_context={'api_url': api_url}
            )
            raise ClientCreationError(
                message=f"Failed to create {provider} client: {str(e)}",
                context=context,
                original_error=e
            )
    
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
        from ..openai import OpenAIService
        
        try:
            from ..gemini.google_service import GoogleService
        except ImportError:
            try:
                from .gemini.google_service import GoogleService
            except ImportError:
                GoogleService = None
                logger.warning("[Provider Factory] GoogleService not available")
        
        try:
            from .ollama.ollama import OllamaService
        except ImportError:
            OllamaService = None
            logger.debug("[Provider Factory] OllamaService not available (optional dependency)")
        
        try:
            from .tongyi.chat import QwenNativeProvider
        except ImportError:
            QwenNativeProvider = None
            logger.debug("[Provider Factory] QwenNativeProvider not available (dashscope SDK not installed, optional)")
        
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
            
            elif client_type == "dashscope":
                # DashScope uses TongyiService coordinator (统一协调者模式)
                try:
                    from ..tongyi.tongyi_service import TongyiService
                    cls._providers[provider_id] = TongyiService
                    logger.info(f"[Provider Factory] Registered {provider_id} (TongyiService Coordinator)")
                except ImportError as e:
                    logger.debug(f"[Provider Factory] Failed to import TongyiService: {e}")
                    # 回退到 QwenNativeProvider（向后兼容）
                    if QwenNativeProvider:
                        cls._providers[provider_id] = QwenNativeProvider
                        logger.info(f"[Provider Factory] Registered {provider_id} (DashScope Native SDK - fallback)")
                    else:
                        logger.debug(f"[Provider Factory] No service class for {provider_id} (DashScope, optional dependency)")
            
            else:
                # 对于可选依赖（ollama, tongyi），使用 debug 级别
                if client_type in ["ollama", "dashscope"]:
                    logger.debug(
                        f"[Provider Factory] No service class for {provider_id} "
                        f"(client_type: {client_type}, optional dependency)"
                    )
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

    @classmethod
    def get_cached(
        cls,
        provider: str,
        api_key: str
    ) -> Optional[BaseProviderService]:
        """
        Get cached client instance without creating new one.
        
        Args:
            provider: Provider name
            api_key: API key
        
        Returns:
            Cached service instance or None if not cached
        
        Example:
            >>> service = ProviderFactory.get_cached("google", "key123")
            >>> if service is None:
            ...     service = ProviderFactory.create("google", "key123")
        """
        cache_key = f"{provider}:{api_key}"
        return cls._client_cache.get(cache_key)
    
    @classmethod
    def clear_cache(cls, provider: Optional[str] = None) -> None:
        """
        Clear cache for specific provider or all providers.
        
        Args:
            provider: Provider name to clear, or None to clear all
        
        Example:
            >>> ProviderFactory.clear_cache("google")  # Clear Google cache
            >>> ProviderFactory.clear_cache()  # Clear all cache
        """
        if provider is None:
            cls._client_cache.clear()
            logger.info("[Provider Factory] Cleared all cache")
        else:
            # Clear all entries for this provider
            keys_to_delete = [k for k in cls._client_cache.keys() if k.startswith(f"{provider}:")]
            for key in keys_to_delete:
                del cls._client_cache[key]
            logger.info(f"[Provider Factory] Cleared cache for {provider} ({len(keys_to_delete)} entries)")
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dict with cache size and entries per provider
        
        Example:
            >>> stats = ProviderFactory.get_cache_stats()
            >>> print(stats)
            {'total': 5, 'google': 2, 'qwen': 2, 'ollama': 1}
        """
        stats = {'total': len(cls._client_cache)}
        for key in cls._client_cache.keys():
            provider = key.split(':')[0]
            stats[provider] = stats.get(provider, 0) + 1
        return stats
