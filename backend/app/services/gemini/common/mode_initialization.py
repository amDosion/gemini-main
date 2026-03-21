"""
Google Mode Initialization Module

This module initializes and registers all Google-specific mode handlers
with the global mode registry.

Design:
- Centralized initialization: All handlers registered in one place
- Configuration-driven: Load mode configuration from ProviderConfig
- Lazy initialization: Only initialize when needed
- Idempotent: Safe to call multiple times

Usage:
    >>> from .mode_initialization import initialize_google_modes
    >>> initialize_google_modes()
    >>> # Now handlers are registered and ready to use
"""

from typing import Dict, Any
import logging

from .mode_registry import get_global_registry
from ..handlers import OutpaintingHandler, InpaintingHandler, VirtualTryonHandler
from ...common.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Track initialization state
_initialized = False


def initialize_google_modes() -> None:
    """
    Initialize and register all Google-specific mode handlers.
    
    This function:
    1. Creates handler instances
    2. Registers them with the global registry
    3. Loads mode configuration from ProviderConfig
    
    This function is idempotent - safe to call multiple times.
    
    Example:
        >>> initialize_google_modes()
        >>> registry = get_global_registry()
        >>> handler = registry.get("image-outpainting")
    """
    global _initialized
    
    if _initialized:
        logger.debug("[GoogleModeInit] Already initialized, skipping")
        return
    
    logger.info("[GoogleModeInit] Initializing Google modes...")
    
    # Get global registry
    registry = get_global_registry()
    
    # Create and register handlers
    handlers = {
        "image-outpainting": OutpaintingHandler(),
        "image-inpainting": InpaintingHandler(),
        "virtual-try-on": VirtualTryonHandler(),
    }
    
    for mode_id, handler in handlers.items():
        try:
            # Get mode metadata from handler
            metadata = handler.get_mode_info()
            
            # Register handler with registry
            registry.register(mode_id, handler, metadata)
            
            logger.info(f"[GoogleModeInit] Registered mode: {mode_id}")
        
        except Exception as e:
            logger.error(f"[GoogleModeInit] Failed to register mode {mode_id}: {e}")
            raise
    
    # Load mode configuration from ProviderConfig
    try:
        google_modes = ProviderConfig.get_modes("google")
        if google_modes:
            logger.info(f"[GoogleModeInit] Loaded {len(google_modes)} modes from ProviderConfig: {google_modes}")
        else:
            logger.warning("[GoogleModeInit] No modes found in ProviderConfig for Google provider")
    
    except Exception as e:
        logger.warning(f"[GoogleModeInit] Failed to load modes from ProviderConfig: {e}")
    
    _initialized = True
    logger.info(f"[GoogleModeInit] Initialization complete. Registered {len(handlers)} modes.")


def reset_initialization() -> None:
    """
    Reset initialization state.
    
    This is primarily useful for testing.
    
    Example:
        >>> reset_initialization()
        >>> initialize_google_modes()  # Will re-initialize
    """
    global _initialized
    _initialized = False
    logger.info("[GoogleModeInit] Reset initialization state")


def is_initialized() -> bool:
    """
    Check if Google modes have been initialized.
    
    Returns:
        True if initialized, False otherwise
    
    Example:
        >>> if not is_initialized():
        ...     initialize_google_modes()
    """
    return _initialized


def get_registered_modes() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered mode metadata.
    
    Returns:
        Dictionary mapping mode IDs to metadata
    
    Example:
        >>> modes = get_registered_modes()
        >>> for mode_id, metadata in modes.items():
        ...     print(f"{mode_id}: {metadata['description']}")
    """
    registry = get_global_registry()
    return registry.get_all_metadata()
