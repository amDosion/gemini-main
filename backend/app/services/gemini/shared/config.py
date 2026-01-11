"""
Configuration Management for Gemini Service

This module provides configuration management for both the official compatibility layer
and the legacy implementation. It handles API keys, endpoints, retry policies, and
other service-wide settings.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from dataclasses import dataclass
import os
import logging

logger = logging.getLogger(__name__)


class HttpRetryConfig(BaseModel):
    """HTTP retry configuration."""
    
    attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exp_base: float = 2.0
    jitter: bool = True
    http_status_codes: List[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])


class HttpConfig(BaseModel):
    """HTTP client configuration."""
    
    timeout: int = 30000  # milliseconds
    retry: HttpRetryConfig = Field(default_factory=HttpRetryConfig)
    headers: Dict[str, str] = Field(default_factory=dict)
    base_url: Optional[str] = None
    api_version: str = 'v1beta'


class ApiConfig(BaseModel):
    """API-specific configuration."""
    
    # Authentication
    api_key: Optional[str] = None
    
    # Vertex AI settings
    project: Optional[str] = None
    location: str = 'us-central1'
    credentials_path: Optional[str] = None
    
    # API endpoints
    gemini_api_base: str = 'https://generativelanguage.googleapis.com'
    vertex_api_base: str = 'https://us-central1-aiplatform.googleapis.com'
    
    # Default models
    default_chat_model: str = 'gemini-2.5-flash'
    default_image_model: str = 'gemini-2.5-flash-image'
    default_embedding_model: str = 'text-embedding-004'


class PerformanceConfig(BaseModel):
    """Performance and optimization settings."""
    
    # Connection pooling
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: int = 5
    
    # Caching
    enable_response_cache: bool = False
    cache_ttl: int = 300  # seconds
    max_cache_size: int = 1000
    
    # Rate limiting
    requests_per_minute: int = 60
    tokens_per_minute: int = 1000000
    
    # Timeouts
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    enable_request_logging: bool = False
    enable_response_logging: bool = False
    log_sensitive_data: bool = False


class GeminiConfig(BaseModel):
    """Main configuration for Gemini service."""
    
    # Core configurations
    api: ApiConfig = Field(default_factory=ApiConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Feature flags
    enable_official_sdk: bool = True
    enable_legacy_fallback: bool = True
    enable_function_calling: bool = True
    enable_structured_output: bool = True
    enable_file_upload: bool = True
    
    # Safety and compliance
    enable_safety_filters: bool = True
    max_file_size_mb: int = 20
    allowed_file_types: List[str] = Field(default_factory=lambda: [
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf', 'text/plain', 'text/csv',
        'audio/wav', 'audio/mp3', 'video/mp4'
    ])
    
    class Config:
        env_prefix = 'GEMINI_'
        case_sensitive = False


def load_config_from_env() -> GeminiConfig:
    """
    Load configuration from environment variables.
    
    Environment variables:
    - GEMINI_API_KEY: API key for authentication
    - GEMINI_PROJECT: Google Cloud project ID
    - GEMINI_LOCATION: Google Cloud location
    - GEMINI_API_VERSION: API version to use
    - GEMINI_TIMEOUT: Request timeout in milliseconds
    - GEMINI_ENABLE_OFFICIAL_SDK: Enable official SDK compatibility
    - GEMINI_LOG_LEVEL: Logging level
    
    Returns:
        GeminiConfig instance with values from environment
    """
    config = GeminiConfig()
    
    # API configuration
    if api_key := os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'):
        config.api.api_key = api_key
    
    if project := os.getenv('GEMINI_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT'):
        config.api.project = project
    
    if location := os.getenv('GEMINI_LOCATION') or os.getenv('GOOGLE_CLOUD_LOCATION'):
        config.api.location = location
    
    if credentials_path := os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        config.api.credentials_path = credentials_path
    
    # HTTP configuration
    if api_version := os.getenv('GEMINI_API_VERSION'):
        config.http.api_version = api_version
    
    if timeout := os.getenv('GEMINI_TIMEOUT'):
        try:
            config.http.timeout = int(timeout)
        except ValueError:
            logger.warning(f"Invalid timeout value: {timeout}")
    
    if base_url := os.getenv('GEMINI_BASE_URL'):
        config.http.base_url = base_url
    
    # Feature flags
    if enable_official := os.getenv('GEMINI_ENABLE_OFFICIAL_SDK'):
        config.enable_official_sdk = enable_official.lower() in ('true', '1', 'yes')
    
    if enable_legacy := os.getenv('GEMINI_ENABLE_LEGACY_FALLBACK'):
        config.enable_legacy_fallback = enable_legacy.lower() in ('true', '1', 'yes')
    
    # Logging
    if log_level := os.getenv('GEMINI_LOG_LEVEL'):
        config.logging.level = log_level.upper()
    
    if log_requests := os.getenv('GEMINI_LOG_REQUESTS'):
        config.logging.enable_request_logging = log_requests.lower() in ('true', '1', 'yes')
    
    return config


def get_default_config() -> GeminiConfig:
    """
    Get the default configuration with environment overrides.
    
    Returns:
        GeminiConfig with default values and environment overrides
    """
    return load_config_from_env()


def validate_config(config: GeminiConfig) -> List[str]:
    """
    Validate configuration and return list of issues.
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Check API key
    if not config.api.api_key and not config.api.project:
        errors.append("Either api_key or project must be provided")
    
    # Check Vertex AI settings
    if config.api.project and not config.api.location:
        errors.append("location is required when using Vertex AI")
    
    # Check timeout values
    if config.http.timeout <= 0:
        errors.append("timeout must be positive")
    
    if config.performance.connect_timeout <= 0:
        errors.append("connect_timeout must be positive")
    
    # Check file size limits
    if config.max_file_size_mb <= 0:
        errors.append("max_file_size_mb must be positive")
    
    # Check rate limits
    if config.performance.requests_per_minute <= 0:
        errors.append("requests_per_minute must be positive")
    
    return errors


@dataclass
class ConfigContext:
    """Context for configuration management."""
    
    config: GeminiConfig
    is_vertex_ai: bool
    is_official_sdk: bool
    
    @classmethod
    def create(cls, config: Optional[GeminiConfig] = None) -> 'ConfigContext':
        """Create configuration context."""
        if config is None:
            config = get_default_config()
        
        is_vertex_ai = bool(config.api.project)
        is_official_sdk = config.enable_official_sdk
        
        return cls(
            config=config,
            is_vertex_ai=is_vertex_ai,
            is_official_sdk=is_official_sdk
        )
    
    def get_api_base_url(self) -> str:
        """Get the appropriate API base URL."""
        if self.config.http.base_url:
            return self.config.http.base_url
        elif self.is_vertex_ai:
            return self.config.api.vertex_api_base
        else:
            return self.config.api.gemini_api_base
    
    def get_default_model(self, task: str = 'chat') -> str:
        """Get default model for a task."""
        if task == 'chat':
            return self.config.api.default_chat_model
        elif task == 'image':
            return self.config.api.default_image_model
        elif task == 'embedding':
            return self.config.api.default_embedding_model
        else:
            return self.config.api.default_chat_model
    
    def should_use_official_sdk(self) -> bool:
        """Check if official SDK should be used."""
        return self.is_official_sdk
    
    def should_fallback_to_legacy(self) -> bool:
        """Check if legacy fallback is enabled."""
        return self.config.enable_legacy_fallback


# Global configuration instance
_global_config: Optional[GeminiConfig] = None


def get_global_config() -> GeminiConfig:
    """Get the global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = get_default_config()
    return _global_config


def set_global_config(config: GeminiConfig) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config