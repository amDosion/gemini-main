"""
Client Selection Strategy Module

This module provides strategies for selecting between primary and secondary clients
in dual-client provider architectures.

Design:
- Priority-based selection: User preference > Operation requirements > Capability check > Performance
- Extensible: Support custom strategies per provider
- Logging: All selection decisions are logged for debugging with structured context

Usage:
    >>> selector = DefaultClientSelector()
    >>> client_type = selector.select(operation, capabilities, preferences)
    >>> print(client_type)  # 'primary' or 'secondary'
"""

from typing import Dict, Any, Literal, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

@dataclass
class ProviderCapabilities:
    """
    Provider capability information.
    
    Attributes:
        streaming: Supports streaming responses
        function_call: Supports function/tool calling
        vision: Supports vision/image inputs
        thinking: Supports thinking/reasoning mode
        web_search: Supports web search
        code_execution: Supports code execution
        secondary_client_supported: Has secondary client available
    """
    streaming: bool = False
    function_call: bool = False
    vision: bool = False
    thinking: bool = False
    web_search: bool = False
    code_execution: bool = False
    secondary_client_supported: bool = False


@dataclass
class UserPreferences:
    """
    User preferences for client selection.
    
    Attributes:
        preferred_client: User's preferred client ('primary' or 'secondary')
    """
    preferred_client: Optional[Literal['primary', 'secondary']] = None


# ==================== Client Selector Interface ====================

class ClientSelector:
    """
    Base class for client selection strategies.
    
    Subclasses should implement the select() method to define
    custom selection logic.
    """
    
    def select(
        self,
        operation: Dict[str, Any],
        capabilities: ProviderCapabilities,
        preferences: UserPreferences,
        request_id: Optional[str] = None
    ) -> Literal['primary', 'secondary']:
        """
        Select which client to use for an operation.
        
        Args:
            operation: Operation details (type, parameters, required features)
            capabilities: Provider capabilities
            preferences: User preferences
            request_id: Optional request ID for tracing
        
        Returns:
            'primary' or 'secondary'
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement select()")
    
    def select_with_fallback(
        self,
        operation: Dict[str, Any],
        capabilities: ProviderCapabilities,
        preferences: UserPreferences
    ) -> Literal['primary', 'secondary']:
        """
        Select client with automatic fallback to primary on error.
        
        This method wraps select() with error handling to ensure
        a valid client is always returned.
        
        Args:
            operation: Operation details
            capabilities: Provider capabilities
            preferences: User preferences
        
        Returns:
            'primary' or 'secondary' (defaults to 'primary' on error)
        """
        try:
            return self.select(operation, capabilities, preferences)
        except Exception as e:
            logger.warning(
                f"[ClientSelector] Selection failed: {e}, falling back to primary client"
            )
            return 'primary'


# ==================== Default Client Selector ====================

class DefaultClientSelector(ClientSelector):
    """
    Default client selection strategy with 4-priority logic.
    
    Priority Order:
    1. User preference (if specified)
    2. Operation requirements (advanced features → primary)
    3. Capability check (secondary not available → primary)
    4. Performance optimization (basic chat → secondary if available)
    
    Default: Primary client
    """
    
    def select(
        self,
        operation: Dict[str, Any],
        capabilities: ProviderCapabilities,
        preferences: UserPreferences,
        request_id: Optional[str] = None
    ) -> Literal['primary', 'secondary']:
        """
        Select client based on 4-priority logic.
        
        Args:
            operation: Operation details
            capabilities: Provider capabilities
            preferences: User preferences
            request_id: Optional request ID for tracing
        
        Returns:
            'primary' or 'secondary'
        """
        # Extract operation context for logging
        operation_type = operation.get('type', 'unknown')
        provider_id = operation.get('provider_id', 'unknown')
        
        log_extra = {
            'request_id': request_id,
            'operation_type': operation_type,
            'provider_id': provider_id
        }
        
        # Priority 1: User preference
        if preferences.preferred_client:
            logger.info(
                f"[ClientSelector] User preference: {preferences.preferred_client}",
                extra={**log_extra, 'selection_reason': 'user_preference', 'selected_client': preferences.preferred_client}
            )
            return preferences.preferred_client
        
        # Priority 2: Operation requirements (advanced features)
        if self._requires_advanced_features(operation):
            logger.info(
                f"[ClientSelector] Advanced features required, using primary client",
                extra={**log_extra, 'selection_reason': 'advanced_features', 'selected_client': 'primary'}
            )
            return 'primary'
        
        # Priority 3: Capability check
        if not capabilities.secondary_client_supported:
            logger.debug(
                f"[ClientSelector] Secondary client not available, using primary",
                extra={**log_extra, 'selection_reason': 'no_secondary', 'selected_client': 'primary'}
            )
            return 'primary'
        
        # Priority 4: Performance optimization
        if self._is_basic_operation(operation):
            logger.debug(
                f"[ClientSelector] Basic operation, using secondary client for performance",
                extra={**log_extra, 'selection_reason': 'performance_optimization', 'selected_client': 'secondary'}
            )
            return 'secondary'
        
        # Default: Primary client
        logger.debug(
            f"[ClientSelector] No specific criteria matched, using primary client (default)",
            extra={**log_extra, 'selection_reason': 'default', 'selected_client': 'primary'}
        )
        return 'primary'
    
    def _requires_advanced_features(self, operation: Dict[str, Any]) -> bool:
        """
        Check if operation requires advanced features.
        
        Advanced features include:
        - Web search (enable_search)
        - Code interpreter (plugins)
        - PDF parsing (plugins)
        - Thinking mode (enable_thinking)
        - Vision models (multimodal)
        - Image editing modes (outpainting, inpainting, etc.)
        
        Args:
            operation: Operation details
        
        Returns:
            True if advanced features required
        """
        # Explicit advanced feature flags
        if operation.get('enable_search'):
            return True
        if operation.get('enable_thinking'):
            return True
        if operation.get('plugins'):
            return True
        
        # Operation type checks
        operation_type = operation.get('type', '')
        if operation_type in ['multimodal', 'vision', 'image_edit']:
            return True
        
        # Model-based checks
        model = operation.get('model', '')
        if 'vl' in model.lower():  # Vision models (e.g., qwen-vl)
            return True
        
        # Mode-based checks (Google image editing)
        mode = operation.get('mode', '')
        if mode in ['outpainting', 'inpainting', 'virtual-try-on']:
            return True
        
        return False
    
    def _is_basic_operation(self, operation: Dict[str, Any]) -> bool:
        """
        Check if operation is a basic operation.
        
        Basic operations include:
        - Simple chat
        - Text generation
        - Standard completion
        
        Args:
            operation: Operation details
        
        Returns:
            True if basic operation
        """
        operation_type = operation.get('type', 'chat')
        return operation_type in ['chat', 'completion', 'text']


# ==================== Provider-Specific Selectors ====================

class QwenClientSelector(ClientSelector):
    """
    Qwen-specific client selection strategy.
    
    Primary Client (DashScope Native SDK):
    - Web search (enable_search)
    - Code interpreter plugin
    - PDF parser plugin
    - Thinking models
    - Vision models (qwen-vl-*)
    
    Secondary Client (OpenAI-Compatible):
    - Basic chat operations
    - Standard text generation
    """
    
    def select(
        self,
        operation: Dict[str, Any],
        capabilities: ProviderCapabilities,
        preferences: UserPreferences
    ) -> Literal['primary', 'secondary']:
        """Select client for Qwen operations."""
        # User preference overrides
        if preferences.preferred_client:
            return preferences.preferred_client
        
        # Advanced features require primary
        if (operation.get('enable_search') or 
            operation.get('plugins') or 
            operation.get('enable_thinking')):
            logger.info("[QwenSelector] Advanced features detected, using primary (DashScope SDK)")
            return 'primary'
        
        # Vision models require primary
        model = operation.get('model', '')
        if 'vl' in model.lower():
            logger.info(f"[QwenSelector] Vision model {model}, using primary (MultiModalConversation API)")
            return 'primary'
        
        # Basic chat uses secondary if available
        if capabilities.secondary_client_supported:
            logger.debug("[QwenSelector] Basic chat, using secondary (OpenAI-compatible)")
            return 'secondary'
        
        return 'primary'


class OllamaClientSelector(ClientSelector):
    """
    Ollama-specific client selection strategy.
    
    Primary Client (OpenAI-Compatible API /v1/*):
    - Chat operations
    - Streaming responses
    
    Secondary Client (Native Ollama API /api/*):
    - Model management (/api/tags, /api/ps)
    - Model info (/api/show)
    - Embedding (/api/embed)
    - Capability detection
    """
    
    def select(
        self,
        operation: Dict[str, Any],
        capabilities: ProviderCapabilities,
        preferences: UserPreferences
    ) -> Literal['primary', 'secondary']:
        """Select client for Ollama operations."""
        # User preference overrides
        if preferences.preferred_client:
            return preferences.preferred_client
        
        # Model management and embedding use secondary (native API)
        operation_type = operation.get('type', 'chat')
        if operation_type in ['modelList', 'modelInfo', 'embedding', 'capabilities', 'modelPull', 'modelDelete']:
            logger.info(f"[OllamaSelector] {operation_type} operation, using secondary (native /api/*)")
            return 'secondary'
        
        # Chat uses primary (OpenAI-compatible)
        logger.debug("[OllamaSelector] Chat operation, using primary (OpenAI /v1/*)")
        return 'primary'


# ==================== Selector Factory ====================

class ClientSelectorFactory:
    """
    Factory for creating client selectors.
    
    Supports provider-specific selectors and default selector.
    """
    
    _selectors: Dict[str, ClientSelector] = {}
    
    @classmethod
    def get_selector(cls, provider: str) -> ClientSelector:
        """
        Get client selector for provider.
        
        Args:
            provider: Provider ID (e.g., 'qwen', 'ollama', 'google')
        
        Returns:
            ClientSelector instance
        """
        # Check if custom selector registered
        if provider in cls._selectors:
            return cls._selectors[provider]
        
        # Use provider-specific selector if available
        if provider == 'tongyi' or provider == 'qwen':
            return QwenClientSelector()
        elif provider == 'ollama':
            return OllamaClientSelector()
        
        # Default selector
        return DefaultClientSelector()
    
    @classmethod
    def register_selector(cls, provider: str, selector: ClientSelector) -> None:
        """
        Register custom selector for provider.
        
        Args:
            provider: Provider ID
            selector: ClientSelector instance
        """
        cls._selectors[provider] = selector
        logger.info(f"[ClientSelectorFactory] Registered custom selector for {provider}")
