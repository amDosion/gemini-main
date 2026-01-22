"""
Coordinator for selecting between Gemini API and Vertex AI implementations.

This module implements the factory pattern to dynamically select the appropriate
image generator based on configuration.
"""

import logging
import os
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .imagen_base import BaseImageGenerator
from .imagen_gemini_api import GeminiAPIImageGenerator
from .imagen_vertex_ai import VertexAIImageGenerator
from .imagen_common import ConfigurationError

logger = logging.getLogger(__name__)

# ==================== Monitoring Metrics ====================
# These counters track usage statistics for monitoring
_vertex_ai_usage_count = 0
_gemini_api_usage_count = 0
_fallback_count = 0


def get_usage_stats() -> Dict[str, int]:
    """
    Get usage statistics for monitoring.
    
    Returns:
        Dictionary with usage counts:
        - vertex_ai_usage: Number of times Vertex AI was used
        - gemini_api_usage: Number of times Gemini API was used
        - fallback_count: Number of times fallback occurred
    """
    return {
        "vertex_ai_usage": _vertex_ai_usage_count,
        "gemini_api_usage": _gemini_api_usage_count,
        "fallback_count": _fallback_count
    }


def reset_usage_stats() -> None:
    """Reset usage statistics (for testing)."""
    global _vertex_ai_usage_count, _gemini_api_usage_count, _fallback_count
    _vertex_ai_usage_count = 0
    _gemini_api_usage_count = 0
    _fallback_count = 0


class ImagenCoordinator:
    """
    Coordinates between Gemini API and Vertex AI implementations.
    
    This class implements the factory pattern to select the appropriate
    image generator based on configuration. It caches generator instances
    for performance.
    """
    
    def __init__(self, user_id: Optional[str] = None, db: Optional[Session] = None, api_key: Optional[str] = None):
        """
        Initialize coordinator with configuration.
        
        Args:
            user_id: User ID for loading user-specific configuration
            db: Database session for loading user configuration
            api_key: Optional pre-decrypted API key (if provided, will be used instead of loading from database)
        """
        self._user_id = user_id
        self._db = db
        self._provided_api_key = api_key  # ✅ 保存传入的已解密 API Key
        self._config = self._load_config()
        self._generator_cache: Dict[str, BaseImageGenerator] = {}
        
        logger.info(f"[ImagenCoordinator] Initialized with API mode: {self._config.get('api_mode', 'gemini_api')}, user_id: {user_id}")
    
    def get_generator(self) -> BaseImageGenerator:
        """
        Get the appropriate image generator based on configuration.
        
        Returns:
            BaseImageGenerator instance (Gemini API or Vertex AI)
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        import time
        start_time = time.time()
        
        global _vertex_ai_usage_count, _gemini_api_usage_count, _fallback_count
        
        api_mode = self._config.get('api_mode', 'gemini_api')
        logger.info(f"[ImagenCoordinator] 🔄 获取生成器...")
        logger.info(f"[ImagenCoordinator]     - api_mode: {api_mode}")
        logger.info(f"[ImagenCoordinator]     - user_id: {self._user_id[:8] + '...' if self._user_id else 'None'}")
        
        # Return cached generator if available
        if api_mode in self._generator_cache:
            logger.info(f"[ImagenCoordinator] ✅ 使用缓存的 {api_mode} 生成器")
            
            # Increment usage counter
            if api_mode == 'vertex_ai':
                _vertex_ai_usage_count += 1
            else:
                _gemini_api_usage_count += 1
            
            generator = self._generator_cache[api_mode]
            generator_type = type(generator).__name__
            logger.info(f"[ImagenCoordinator]     - 生成器类型: {generator_type}")
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[ImagenCoordinator] ✅ 获取生成器完成 (耗时: {elapsed:.2f}ms)")
            return generator
        
        # Create new generator
        logger.info(f"[ImagenCoordinator] 🔄 创建新的 {api_mode} 生成器...")
        try:
            if api_mode == 'vertex_ai':
                logger.info(f"[ImagenCoordinator]     - 使用 Vertex AI 模式")
                generator = self._create_vertex_ai_generator()
                _vertex_ai_usage_count += 1
            else:
                logger.info(f"[ImagenCoordinator]     - 使用 Gemini API 模式")
                generator = self._create_gemini_api_generator()
                _gemini_api_usage_count += 1
            
            generator_type = type(generator).__name__
            logger.info(f"[ImagenCoordinator] ✅ 生成器创建完成: {generator_type}")
            
            # Cache the generator
            self._generator_cache[api_mode] = generator
            logger.info(f"[ImagenCoordinator] ✅ 生成器已缓存")
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[ImagenCoordinator] ✅ 获取生成器完成 (耗时: {elapsed:.2f}ms)")
            return generator
            
        except Exception as e:
            logger.error(f"[ImagenCoordinator] ❌ 创建 {api_mode} 生成器失败: {e}", exc_info=True)
            
            # Fallback to Gemini API if Vertex AI fails
            if api_mode == 'vertex_ai':
                logger.warning("[ImagenCoordinator] ⚠️ Vertex AI 失败，降级到 Gemini API")
                _fallback_count += 1
                _gemini_api_usage_count += 1
                fallback_generator = self._create_gemini_api_generator()
                fallback_type = type(fallback_generator).__name__
                logger.info(f"[ImagenCoordinator] ✅ 降级生成器创建完成: {fallback_type}")
                return fallback_generator
            
            raise
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from database (user-specific) or environment variables (fallback).
        
        Returns:
            Configuration dictionary
        """
        config = {}
        
        # Try to load from database if user_id and db session are provided
        if self._user_id and self._db:
            try:
                from ...models.db_models import VertexAIConfig
                from ...core.encryption import decrypt_data
                
                user_config = self._db.query(VertexAIConfig).filter(
                    VertexAIConfig.user_id == self._user_id
                ).first()
                
                if user_config:
                    logger.info(f"[ImagenCoordinator] Using Vertex AI config from database for user={self._user_id}")
                    
                    config['api_mode'] = user_config.api_mode
                    config['vertex_ai_project_id'] = user_config.vertex_ai_project_id
                    config['vertex_ai_location'] = user_config.vertex_ai_location or 'us-central1'
                    
                    # Decrypt credentials JSON if present
                    if user_config.vertex_ai_credentials_json:
                        try:
                            config['vertex_ai_credentials_json'] = decrypt_data(
                                user_config.vertex_ai_credentials_json
                            )
                            logger.debug(f"[ImagenCoordinator] Successfully decrypted Vertex AI credentials")
                        except Exception as e:
                            logger.error(f"[ImagenCoordinator] Failed to decrypt credentials: {e}")
                            config['vertex_ai_credentials_json'] = None
                    
                    # For Gemini API mode, get API key from ConfigProfile
                    if user_config.api_mode == 'gemini_api':
                        # ✅ 优先使用传入的已解密 API Key（来自 credential_manager）
                        if self._provided_api_key:
                            config['gemini_api_key'] = self._provided_api_key
                            logger.info(f"[ImagenCoordinator] Using provided pre-decrypted API key for user={self._user_id}")
                        else:
                            # 回退：从数据库加载并解密
                            from ...models.db_models import ConfigProfile
                            from ...core.encryption import decrypt_data, is_encrypted
                            
                            # Find Google provider config for this user
                            google_profile = self._db.query(ConfigProfile).filter(
                                ConfigProfile.user_id == self._user_id,
                                ConfigProfile.provider_id == 'google'
                            ).first()
                            
                            if google_profile and google_profile.api_key:
                                # ✅ 解密 API Key（如果已加密）
                                api_key = google_profile.api_key
                                if is_encrypted(api_key):
                                    try:
                                        api_key = decrypt_data(api_key, silent=True)
                                        logger.debug(f"[ImagenCoordinator] Successfully decrypted Gemini API key from ConfigProfile")
                                    except Exception as e:
                                        logger.error(f"[ImagenCoordinator] Failed to decrypt API key from ConfigProfile: {e}")
                                        # 解密失败时，不设置 gemini_api_key，让系统回退到环境变量
                                        api_key = None
                                
                                if api_key:
                                    config['gemini_api_key'] = api_key
                                    logger.info(f"[ImagenCoordinator] Using Gemini API key from ConfigProfile for user={self._user_id}")
                                else:
                                    logger.warning(f"[ImagenCoordinator] Failed to decrypt API key from ConfigProfile for user={self._user_id}, will fall back to environment")
                            else:
                                logger.warning(f"[ImagenCoordinator] No Google ConfigProfile found for user={self._user_id}, will fall back to environment")
                    
                    # Validate configuration completeness
                    if user_config.api_mode == 'vertex_ai':
                        missing_fields = []
                        if not config.get('vertex_ai_project_id'):
                            missing_fields.append('vertex_ai_project_id')
                        if not config.get('vertex_ai_location'):
                            missing_fields.append('vertex_ai_location')
                        if not config.get('vertex_ai_credentials_json'):
                            missing_fields.append('vertex_ai_credentials_json')
                        
                        if missing_fields:
                            logger.warning(
                                f"[ImagenCoordinator] Incomplete Vertex AI config from database for user={self._user_id}: "
                                f"missing {', '.join(missing_fields)}. Will fall back to environment variables or Gemini API."
                            )
                    elif user_config.api_mode == 'gemini_api':
                        if not config.get('gemini_api_key'):
                            logger.warning(
                                f"[ImagenCoordinator] Incomplete Gemini API config from database for user={self._user_id}: "
                                f"missing API key. Will fall back to environment variables."
                            )
                    
                    logger.debug(f"[ImagenCoordinator] Loaded config from database: api_mode={config['api_mode']}")
                    return config
                else:
                    logger.info(f"[ImagenCoordinator] No database config found for user={self._user_id}, falling back to environment variables")
            except Exception as e:
                logger.error(f"[ImagenCoordinator] Failed to load config from database: {e}, falling back to environment variables")
        
        # Fallback to environment variables (for testing and backward compatibility)
        logger.info(f"[ImagenCoordinator] Using Vertex AI config from environment variables")
        
        use_vertex_ai = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'false').lower() == 'true'
        config['api_mode'] = 'vertex_ai' if use_vertex_ai else 'gemini_api'
        
        # Gemini API configuration
        # ✅ 优先使用传入的已解密 API Key（来自 credential_manager）
        if self._provided_api_key:
            config['gemini_api_key'] = self._provided_api_key
            logger.info(f"[ImagenCoordinator] Using provided pre-decrypted API key (fallback to env)")
        else:
            config['gemini_api_key'] = os.getenv('GEMINI_API_KEY')
        
        # Vertex AI configuration
        config['vertex_ai_project_id'] = os.getenv('GOOGLE_CLOUD_PROJECT')
        config['vertex_ai_location'] = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
        config['vertex_ai_credentials_json'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        
        # Validate environment configuration completeness
        if config['api_mode'] == 'vertex_ai':
            missing_env_fields = []
            if not config.get('vertex_ai_project_id'):
                missing_env_fields.append('GOOGLE_CLOUD_PROJECT')
            if not config.get('vertex_ai_credentials_json'):
                missing_env_fields.append('GOOGLE_APPLICATION_CREDENTIALS_JSON')
            
            if missing_env_fields:
                logger.warning(
                    f"[ImagenCoordinator] Incomplete Vertex AI config from environment: "
                    f"missing {', '.join(missing_env_fields)}. Will fall back to Gemini API."
                )
        elif config['api_mode'] == 'gemini_api':
            if not config.get('gemini_api_key'):
                logger.warning(
                    f"[ImagenCoordinator] Incomplete Gemini API config from environment: "
                    f"missing GEMINI_API_KEY."
                )
        
        logger.debug(f"[ImagenCoordinator] Loaded config from environment: api_mode={config['api_mode']}")
        
        return config
    
    def _create_gemini_api_generator(self) -> GeminiAPIImageGenerator:
        """
        Create Gemini API generator instance.
        
        Returns:
            GeminiAPIImageGenerator instance
        
        Raises:
            ConfigurationError: If API key is missing
        """
        api_key = self._config.get('gemini_api_key')
        
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY environment variable is required for Gemini API mode"
            )
        
        logger.info("[ImagenCoordinator] Creating Gemini API generator")
        return GeminiAPIImageGenerator(api_key=api_key)
    
    def _create_vertex_ai_generator(self) -> VertexAIImageGenerator:
        """
        Create Vertex AI generator instance.
        
        Returns:
            VertexAIImageGenerator instance
        
        Raises:
            ConfigurationError: If required configuration is missing
        """
        project_id = self._config.get('vertex_ai_project_id')
        location = self._config.get('vertex_ai_location')
        credentials_json = self._config.get('vertex_ai_credentials_json')
        
        # Validate required configuration
        if not project_id:
            raise ConfigurationError(
                "GOOGLE_CLOUD_PROJECT environment variable is required for Vertex AI mode"
            )
        
        if not location:
            raise ConfigurationError(
                "GOOGLE_CLOUD_LOCATION environment variable is required for Vertex AI mode"
            )
        
        if not credentials_json:
            raise ConfigurationError(
                "GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable is required for Vertex AI mode"
            )
        
        logger.info(f"[ImagenCoordinator] Creating Vertex AI generator: project={project_id}, location={location}")
        return VertexAIImageGenerator(
            project_id=project_id,
            location=location,
            credentials_json=credentials_json
        )
    
    def get_current_api_mode(self) -> str:
        """
        Get the current API mode.
        
        Returns:
            'gemini_api' or 'vertex_ai'
        """
        return self._config.get('api_mode', 'gemini_api')
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get capabilities of the current API mode.
        
        Returns:
            Capabilities dictionary with standardized format:
            - supported_models: List of supported model IDs
            - max_images: Maximum number of images per request
            - supported_aspect_ratios: List of supported aspect ratios
            - person_generation_modes: List of supported person generation modes
        """
        generator = self.get_generator()
        capabilities = generator.get_capabilities()
        
        # Ensure all required fields are present
        if 'supported_models' not in capabilities:
            # Try to get from generator if available
            if hasattr(generator, 'get_supported_models'):
                try:
                    capabilities['supported_models'] = generator.get_supported_models()
                except Exception as e:
                    logger.warning(f"[ImagenCoordinator] Failed to get supported_models: {e}")
                    capabilities['supported_models'] = []
        
        # Ensure supported_aspect_ratios field exists (standardize from aspect_ratios)
        if 'supported_aspect_ratios' not in capabilities and 'aspect_ratios' in capabilities:
            capabilities['supported_aspect_ratios'] = capabilities['aspect_ratios']
        
        # Ensure person_generation_modes field exists
        if 'person_generation_modes' not in capabilities:
            capabilities['person_generation_modes'] = ['dont_allow', 'allow_adult']
        
        return capabilities
    
    def reload_config(self) -> None:
        """
        Reload configuration and clear generator cache.
        
        Use this when configuration changes (e.g., API mode switch).
        """
        logger.info(f"[ImagenCoordinator] Reloading configuration for user={self._user_id}")
        self._config = self._load_config()
        self._generator_cache.clear()
        logger.info(f"[ImagenCoordinator] Configuration reloaded: api_mode={self._config.get('api_mode')}")
