"""
Google Platform Routing Module

This module implements logic to route between Vertex AI and Developer API
based on mode requirements and user preferences.

Design:
- Configuration-driven: Load platform support from ProviderConfig
- Deterministic routing: Same inputs always produce same output
- User preference override: Allow users to choose platform when supported
- Mode-based routing: Some modes only work on specific platforms

Usage:
    >>> platform, routing_info = resolve_platform(
    ...     mode_id="image-outpainting",
    ...     user_preference="vertex_ai"
    ... )
    >>> print(platform)  # "vertex_ai" or "developer_api"
"""

from typing import Literal, Optional, Tuple, Dict, Any
import logging

from ...common.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Type definitions
Platform = Literal["vertex_ai", "developer_api"]
PlatformSupport = Literal["either", "vertex_ai_only", "developer_api_only", "vertex_ai_preferred"]


def resolve_platform(
    mode_id: str,
    user_preference: Optional[Platform] = None,
    provider_id: str = "google",
    request_id: Optional[str] = None
) -> Tuple[Platform, Dict[str, Any]]:
    """
    Resolve which platform to use for a given mode.
    
    This function implements deterministic routing logic:
    1. Check mode's platform support
    2. If mode is platform-specific, use that platform
    3. If mode supports either platform:
       a. Use user preference if provided and allowed
       b. Otherwise use default platform
    
    Args:
        mode_id: Mode identifier (e.g., "image-outpainting")
        user_preference: Optional user-selected platform
        provider_id: Provider identifier (default: "google")
        request_id: Optional request ID for tracing
    
    Returns:
        Tuple of (resolved_platform, routing_info)
        - resolved_platform: The platform to use
        - routing_info: Dictionary with routing details
    
    Raises:
        ValueError: If user preference is not allowed for this mode
    
    Example:
        >>> platform, info = resolve_platform("image-outpainting")
        >>> print(platform)
        'vertex_ai'
        >>> print(info['support'])
        'either'
    """
    log_extra = {
        'request_id': request_id,
        'mode_id': mode_id,
        'provider_id': provider_id,
        'user_preference': user_preference
    }
    
    # Get platform routing configuration from ProviderConfig
    platform_routing = ProviderConfig.get_platform_routing(provider_id)
    
    if not platform_routing:
        logger.warning(
            f"[PlatformRouting] No platform routing config found for provider={provider_id}, using defaults",
            extra=log_extra
        )
        platform_routing = {
            "default_platform": "developer_api",
            "modes": {}
        }
    
    # Get mode-specific configuration
    mode_config = platform_routing.get("modes", {}).get(mode_id, {})
    default_platform = platform_routing.get("default_platform", "developer_api")
    
    # Get platform support for this mode
    support: PlatformSupport = mode_config.get("support", "either")
    
    logger.debug(
        f"[PlatformRouting] Resolving platform for mode={mode_id}, support={support}, user_preference={user_preference}",
        extra={**log_extra, 'support': support, 'default_platform': default_platform}
    )
    
    # Handle vertex_ai_only modes
    if support == "vertex_ai_only":
        routing_info = {
            "support": "vertex_ai_only",
            "can_choose_platform": False,
            "allowed_platforms": ["vertex_ai"],
            "default_platform": "vertex_ai",
            "resolved_platform": "vertex_ai",
            "reason": "Mode only supported on Vertex AI"
        }
        logger.info(
            f"[PlatformRouting] Mode {mode_id} requires Vertex AI (vertex_ai_only)",
            extra={**log_extra, 'resolved_platform': 'vertex_ai', 'reason': 'vertex_ai_only'}
        )
        return "vertex_ai", routing_info
    
    # Handle developer_api_only modes
    if support == "developer_api_only":
        routing_info = {
            "support": "developer_api_only",
            "can_choose_platform": False,
            "allowed_platforms": ["developer_api"],
            "default_platform": "developer_api",
            "resolved_platform": "developer_api",
            "reason": "Mode only supported on Developer API"
        }
        logger.info(
            f"[PlatformRouting] Mode {mode_id} requires Developer API (developer_api_only)",
            extra={**log_extra, 'resolved_platform': 'developer_api', 'reason': 'developer_api_only'}
        )
        return "developer_api", routing_info
    
    # Handle vertex_ai_preferred modes
    if support == "vertex_ai_preferred":
        # Prefer Vertex AI but allow user override
        can_choose = mode_config.get("can_choose_platform", True)
        allowed_platforms = mode_config.get("allowed_platforms", ["vertex_ai", "developer_api"])
        
        if user_preference and can_choose:
            if user_preference not in allowed_platforms:
                raise ValueError(
                    f"Platform '{user_preference}' not allowed for mode '{mode_id}'. "
                    f"Allowed platforms: {allowed_platforms}"
                )
            
            routing_info = {
                "support": "vertex_ai_preferred",
                "can_choose_platform": True,
                "allowed_platforms": allowed_platforms,
                "default_platform": "vertex_ai",
                "resolved_platform": user_preference,
                "reason": f"User selected {user_preference}"
            }
            logger.info(
                f"[PlatformRouting] Mode {mode_id} using user preference: {user_preference}",
                extra={**log_extra, 'resolved_platform': user_preference, 'reason': 'user_preference'}
            )
            return user_preference, routing_info
        
        routing_info = {
            "support": "vertex_ai_preferred",
            "can_choose_platform": can_choose,
            "allowed_platforms": allowed_platforms,
            "default_platform": "vertex_ai",
            "resolved_platform": "vertex_ai",
            "reason": "Vertex AI preferred for this mode"
        }
        logger.info(
            f"[PlatformRouting] Mode {mode_id} using preferred platform: vertex_ai",
            extra={**log_extra, 'resolved_platform': 'vertex_ai', 'reason': 'vertex_ai_preferred'}
        )
        return "vertex_ai", routing_info
    
    # Handle "either" modes (both platforms supported equally)
    can_choose = mode_config.get("can_choose_platform", True)
    allowed_platforms = mode_config.get("allowed_platforms", ["vertex_ai", "developer_api"])
    mode_default = mode_config.get("default_platform", default_platform)
    
    # User preference override
    if user_preference:
        if not can_choose:
            raise ValueError(
                f"Platform selection is disabled for mode '{mode_id}'. "
                f"Using default platform: {mode_default}"
            )
        
        if user_preference not in allowed_platforms:
            raise ValueError(
                f"Platform '{user_preference}' not allowed for mode '{mode_id}'. "
                f"Allowed platforms: {allowed_platforms}"
            )
        
        routing_info = {
            "support": "either",
            "can_choose_platform": True,
            "allowed_platforms": allowed_platforms,
            "default_platform": mode_default,
            "resolved_platform": user_preference,
            "reason": f"User selected {user_preference}"
        }
        logger.info(
            f"[PlatformRouting] Mode {mode_id} using user preference: {user_preference}",
            extra={**log_extra, 'resolved_platform': user_preference, 'reason': 'user_preference'}
        )
        return user_preference, routing_info
    
    # Use default platform
    routing_info = {
        "support": "either",
        "can_choose_platform": can_choose,
        "allowed_platforms": allowed_platforms,
        "default_platform": mode_default,
        "resolved_platform": mode_default,
        "reason": f"Using default platform: {mode_default}"
    }
    logger.info(
        f"[PlatformRouting] Mode {mode_id} using default platform: {mode_default}",
        extra={**log_extra, 'resolved_platform': mode_default, 'reason': 'default_platform'}
    )
    return mode_default, routing_info


def get_mode_platform_support(mode_id: str, provider_id: str = "google") -> PlatformSupport:
    """
    Get platform support for a specific mode.
    
    Args:
        mode_id: Mode identifier
        provider_id: Provider identifier (default: "google")
    
    Returns:
        Platform support type
    
    Example:
        >>> support = get_mode_platform_support("virtual-try-on")
        >>> print(support)
        'vertex_ai_preferred'
    """
    platform_routing = ProviderConfig.get_platform_routing(provider_id)
    
    if not platform_routing:
        return "either"
    
    mode_config = platform_routing.get("modes", {}).get(mode_id, {})
    return mode_config.get("support", "either")


def get_allowed_platforms(mode_id: str, provider_id: str = "google") -> list[Platform]:
    """
    Get allowed platforms for a specific mode.
    
    Args:
        mode_id: Mode identifier
        provider_id: Provider identifier (default: "google")
    
    Returns:
        List of allowed platforms
    
    Example:
        >>> platforms = get_allowed_platforms("image-outpainting")
        >>> print(platforms)
        ['vertex_ai', 'developer_api']
    """
    platform_routing = ProviderConfig.get_platform_routing(provider_id)
    
    if not platform_routing:
        return ["vertex_ai", "developer_api"]
    
    mode_config = platform_routing.get("modes", {}).get(mode_id, {})
    support = mode_config.get("support", "either")
    
    if support == "vertex_ai_only":
        return ["vertex_ai"]
    elif support == "developer_api_only":
        return ["developer_api"]
    else:
        return mode_config.get("allowed_platforms", ["vertex_ai", "developer_api"])


def can_user_choose_platform(mode_id: str, provider_id: str = "google") -> bool:
    """
    Check if user can choose platform for a specific mode.
    
    Args:
        mode_id: Mode identifier
        provider_id: Provider identifier (default: "google")
    
    Returns:
        True if user can choose, False otherwise
    
    Example:
        >>> can_choose = can_user_choose_platform("image-outpainting")
        >>> print(can_choose)
        True
    """
    platform_routing = ProviderConfig.get_platform_routing(provider_id)
    
    if not platform_routing:
        return True
    
    mode_config = platform_routing.get("modes", {}).get(mode_id, {})
    support = mode_config.get("support", "either")
    
    # Platform-specific modes don't allow choice
    if support in ["vertex_ai_only", "developer_api_only"]:
        return False
    
    return mode_config.get("can_choose_platform", True)
