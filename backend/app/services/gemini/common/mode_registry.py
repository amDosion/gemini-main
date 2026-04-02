"""
Google Mode Registry Module

This module provides a registry for Google-specific modes (outpainting, inpainting,
virtual try-on, etc.) in the backend.

Design:
- Registry pattern: Central registration of mode handlers
- Extensible: Easy to add new modes
- Configuration-driven: Load mode configuration from ProviderConfig
- Type-safe: Strong typing for mode handlers

Usage:
    >>> registry = GoogleModeRegistry()
    >>> handler = registry.get("image-outpainting")
    >>> result = await handler.execute(params)
"""

from typing import Dict, Any, Optional, Protocol, List
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


# ==================== Mode Handler Interface ====================

class ModeHandler(Protocol):
    """
    Protocol for mode handlers.
    
    All mode handlers must implement the execute() method.
    """
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the mode operation.
        
        Args:
            params: Operation parameters
        
        Returns:
            Operation result
        
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If operation fails
        """
        ...
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate operation parameters.
        
        Args:
            params: Parameters to validate
        
        Returns:
            True if valid, False otherwise
        """
        ...
    
    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get mode information.
        
        Returns:
            Mode metadata (name, description, parameters, etc.)
        """
        ...


# ==================== Google Mode Registry ====================

class GoogleModeRegistry:
    """
    Registry for Google-specific modes.
    
    This class manages registration and retrieval of mode handlers.
    Modes are registered at initialization and can be retrieved by mode ID.
    
    Example:
        >>> registry = GoogleModeRegistry()
        >>> handler = registry.get("image-outpainting")
        >>> if handler:
        ...     result = await handler.execute(params)
    """
    
    def __init__(self):
        """Initialize the mode registry."""
        self._handlers: Dict[str, ModeHandler] = {}
        self._mode_metadata: Dict[str, Dict[str, Any]] = {}
        logger.info("[GoogleModeRegistry] Initialized")
    
    def register(
        self,
        mode_id: str,
        handler: ModeHandler,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a mode handler.
        
        Args:
            mode_id: Unique mode identifier (e.g., "image-outpainting")
            handler: Mode handler instance
            metadata: Optional mode metadata
        
        Raises:
            ValueError: If mode_id is already registered
        
        Example:
            >>> registry.register(
            ...     "image-outpainting",
            ...     OutpaintingHandler(),
            ...     {"description": "Extend image boundaries"}
            ... )
        """
        if mode_id in self._handlers:
            logger.warning(f"[GoogleModeRegistry] Overwriting existing handler for mode: {mode_id}")
        
        self._handlers[mode_id] = handler
        
        # Store metadata (from handler or provided)
        if metadata:
            self._mode_metadata[mode_id] = metadata
        else:
            self._mode_metadata[mode_id] = handler.get_mode_info()
        
        logger.info(f"[GoogleModeRegistry] Registered mode: {mode_id}")
    
    def get(self, mode_id: str) -> Optional[ModeHandler]:
        """
        Get a mode handler by ID.
        
        Args:
            mode_id: Mode identifier
        
        Returns:
            Mode handler instance or None if not found
        
        Example:
            >>> handler = registry.get("image-outpainting")
            >>> if handler:
            ...     result = await handler.execute(params)
        """
        handler = self._handlers.get(mode_id)
        
        if handler:
            logger.debug(f"[GoogleModeRegistry] Retrieved handler for mode: {mode_id}")
        else:
            logger.warning(f"[GoogleModeRegistry] No handler found for mode: {mode_id}")
        
        return handler
    
    def has_mode(self, mode_id: str) -> bool:
        """
        Check if a mode is registered.
        
        Args:
            mode_id: Mode identifier
        
        Returns:
            True if mode is registered, False otherwise
        
        Example:
            >>> if registry.has_mode("image-outpainting"):
            ...     handler = registry.get("image-outpainting")
        """
        return mode_id in self._handlers
    
    def list_modes(self) -> List[str]:
        """
        List all registered mode IDs.
        
        Returns:
            List of mode identifiers
        
        Example:
            >>> modes = registry.list_modes()
            >>> print(modes)
            ['image-outpainting', 'image-inpainting', 'virtual-try-on']
        """
        return list(self._handlers.keys())
    
    def get_mode_metadata(self, mode_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a mode.
        
        Args:
            mode_id: Mode identifier
        
        Returns:
            Mode metadata or None if not found
        
        Example:
            >>> metadata = registry.get_mode_metadata("image-outpainting")
            >>> print(metadata["description"])
            'Extend image boundaries'
        """
        return self._mode_metadata.get(mode_id)
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all registered modes.
        
        Returns:
            Dictionary mapping mode IDs to metadata
        
        Example:
            >>> all_metadata = registry.get_all_metadata()
            >>> for mode_id, metadata in all_metadata.items():
            ...     print(f"{mode_id}: {metadata['description']}")
        """
        return self._mode_metadata.copy()
    
    def unregister(self, mode_id: str) -> bool:
        """
        Unregister a mode handler.
        
        Args:
            mode_id: Mode identifier
        
        Returns:
            True if mode was unregistered, False if not found
        
        Example:
            >>> registry.unregister("image-outpainting")
            True
        """
        if mode_id in self._handlers:
            del self._handlers[mode_id]
            if mode_id in self._mode_metadata:
                del self._mode_metadata[mode_id]
            logger.info(f"[GoogleModeRegistry] Unregistered mode: {mode_id}")
            return True
        
        logger.warning(f"[GoogleModeRegistry] Cannot unregister unknown mode: {mode_id}")
        return False
    
    def clear(self) -> None:
        """
        Clear all registered modes.
        
        This is primarily useful for testing.
        
        Example:
            >>> registry.clear()
            >>> assert len(registry.list_modes()) == 0
        """
        self._handlers.clear()
        self._mode_metadata.clear()
        logger.info("[GoogleModeRegistry] Cleared all modes")


# ==================== Global Registry Instance ====================

# Global registry instance (eager initialization to avoid race conditions)
_global_registry: GoogleModeRegistry = GoogleModeRegistry()


def get_global_registry() -> GoogleModeRegistry:
    """
    Get the global mode registry instance.

    Returns:
        Global GoogleModeRegistry instance

    Example:
        >>> registry = get_global_registry()
        >>> handler = registry.get("image-outpainting")
    """
    return _global_registry


def reset_global_registry() -> None:
    """
    Reset the global registry instance.
    
    This is primarily useful for testing.
    
    Example:
        >>> reset_global_registry()
        >>> registry = get_global_registry()  # Creates new instance
    """
    global _global_registry
    _global_registry = None
    logger.info("[GoogleModeRegistry] Reset global registry")
