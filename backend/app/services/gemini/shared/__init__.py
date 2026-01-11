"""
Shared Components for Gemini Service

This module provides shared components used across both the official compatibility layer
and the legacy implementation. It includes adapters, configuration management, and
common utilities.
"""

from .adapters import LegacyToOfficialAdapter, OfficialToLegacyAdapter
from .config import GeminiConfig, get_default_config
from .utils import (
    detect_mime_type,
    validate_api_key,
    format_error_message,
    retry_with_backoff
)

__all__ = [
    # Adapters
    'LegacyToOfficialAdapter',
    'OfficialToLegacyAdapter',
    
    # Configuration
    'GeminiConfig',
    'get_default_config',
    
    # Utilities
    'detect_mime_type',
    'validate_api_key', 
    'format_error_message',
    'retry_with_backoff',
]