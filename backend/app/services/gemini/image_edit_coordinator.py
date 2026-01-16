"""
Coordinator for selecting between Gemini API and Vertex AI image editing implementations.

This module implements the factory pattern to dynamically select the appropriate
image editor based on configuration.

Also handles mode routing to different edit services:
- ConversationalImageEditService: For chat-based editing
- SimpleImageEditService: For simple editing without mask
- Vertex AI Imagen editors: For advanced editing with mask
"""

import logging
import os
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from .image_edit_base import BaseImageEditor
from .image_edit_gemini_api import GeminiAPIImageEditor
from .image_edit_vertex_ai import VertexAIImageEditor

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


class ImageEditCoordinator:
    """
    Coordinates between Gemini API and Vertex AI image editing implementations.
    
    This class implements the factory pattern to select the appropriate
    image editor based on configuration. It caches editor instances
    for performance.
    """

    
    def __init__(self, user_id: Optional[str] = None, db: Optional[Session] = None):
        """
        Initialize coordinator with configuration.
        
        Args:
            user_id: User ID for loading user-specific configuration
            db: Database session for loading user configuration
        """
        self._user_id = user_id
        self._db = db
        self._config = self._load_config()
        self._editor_cache: Dict[str, BaseImageEditor] = {}
        
        logger.info(f"[ImageEditCoordinator] Initialized with API mode: {self._config.get('api_mode', 'gemini_api')}, user_id: {user_id}")
    
    def get_editor(self) -> BaseImageEditor:
        """
        Get the appropriate image editor based on configuration.
        
        Returns:
            BaseImageEditor instance (Gemini API or Vertex AI)
        
        Raises:
            ValueError: If configuration is invalid
        """
        global _vertex_ai_usage_count, _gemini_api_usage_count, _fallback_count
        
        api_mode = self._config.get('api_mode', 'gemini_api')
        
        # Return cached editor if available
        if api_mode in self._editor_cache:
            logger.debug(f"[ImageEditCoordinator] Using cached {api_mode} editor")
            
            # Increment usage counter
            if api_mode == 'vertex_ai':
                _vertex_ai_usage_count += 1
            else:
                _gemini_api_usage_count += 1
            
            return self._editor_cache[api_mode]
        
        # Create new editor
        try:
            if api_mode == 'vertex_ai':
                editor = self._create_vertex_ai_editor()
                _vertex_ai_usage_count += 1
            else:
                editor = self._create_gemini_api_editor()
                _gemini_api_usage_count += 1
            
            # Cache the editor
            self._editor_cache[api_mode] = editor
            logger.info(f"[ImageEditCoordinator] Created and cached {api_mode} editor")
            
            return editor
            
        except Exception as e:
            logger.error(f"[ImageEditCoordinator] Failed to create {api_mode} editor: {e}")
            
            # Fallback to Gemini API if Vertex AI fails
            if api_mode == 'vertex_ai':
                logger.warning("[ImageEditCoordinator] Falling back to Gemini API due to Vertex AI failure")
                _fallback_count += 1
                _gemini_api_usage_count += 1
                return self._create_gemini_api_editor()
            
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
                    logger.info(f"[ImageEditCoordinator] Using Vertex AI config from database for user={self._user_id}")
                    
                    config['api_mode'] = user_config.api_mode
                    config['vertex_ai_project_id'] = user_config.vertex_ai_project_id
                    config['vertex_ai_location'] = user_config.vertex_ai_location or 'us-central1'
                    
                    # Decrypt credentials JSON if present
                    if user_config.vertex_ai_credentials_json:
                        try:
                            config['vertex_ai_credentials_json'] = decrypt_data(
                                user_config.vertex_ai_credentials_json
                            )
                            logger.debug(f"[ImageEditCoordinator] Successfully decrypted Vertex AI credentials")
                        except Exception as e:
                            logger.error(f"[ImageEditCoordinator] Failed to decrypt credentials: {e}")
                            config['vertex_ai_credentials_json'] = None
                    
                    # For Gemini API mode, get API key from ConfigProfile
                    if user_config.api_mode == 'gemini_api':
                        from ...models.db_models import ConfigProfile
                        
                        # Find Google provider config for this user
                        google_profile = self._db.query(ConfigProfile).filter(
                            ConfigProfile.user_id == self._user_id,
                            ConfigProfile.provider_id == 'google'
                        ).first()
                        
                        if google_profile:
                            config['gemini_api_key'] = google_profile.api_key
                            logger.info(f"[ImageEditCoordinator] Using Gemini API key from ConfigProfile for user={self._user_id}")
                        else:
                            logger.warning(f"[ImageEditCoordinator] No Google ConfigProfile found for user={self._user_id}, will fall back to environment")
                    
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
                                f"[ImageEditCoordinator] Incomplete Vertex AI config from database for user={self._user_id}: "
                                f"missing {', '.join(missing_fields)}. Will fall back to environment variables or Gemini API."
                            )
                    elif user_config.api_mode == 'gemini_api':
                        if not config.get('gemini_api_key'):
                            logger.warning(
                                f"[ImageEditCoordinator] Incomplete Gemini API config from database for user={self._user_id}: "
                                f"missing API key. Will fall back to environment variables."
                            )
                    
                    logger.debug(f"[ImageEditCoordinator] Loaded config from database: api_mode={config['api_mode']}")
                    return config
                else:
                    logger.info(f"[ImageEditCoordinator] No database config found for user={self._user_id}, falling back to environment variables")
            except Exception as e:
                logger.error(f"[ImageEditCoordinator] Failed to load config from database: {e}, falling back to environment variables")
        
        # Fallback to environment variables (for testing and backward compatibility)
        logger.info(f"[ImageEditCoordinator] Using Vertex AI config from environment variables")
        
        use_vertex_ai = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'false').lower() == 'true'
        config['api_mode'] = 'vertex_ai' if use_vertex_ai else 'gemini_api'
        
        # Gemini API configuration
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
                    f"[ImageEditCoordinator] Incomplete Vertex AI config from environment: "
                    f"missing {', '.join(missing_env_fields)}. Will fall back to Gemini API."
                )
        elif config['api_mode'] == 'gemini_api':
            if not config.get('gemini_api_key'):
                logger.warning(
                    f"[ImageEditCoordinator] Incomplete Gemini API config from environment: "
                    f"missing GEMINI_API_KEY."
                )
        
        logger.debug(f"[ImageEditCoordinator] Loaded config from environment: api_mode={config['api_mode']}")
        
        return config

    
    def _create_gemini_api_editor(self) -> GeminiAPIImageEditor:
        """
        Create Gemini API editor instance.
        
        Returns:
            GeminiAPIImageEditor instance
        
        Raises:
            ValueError: If API key is missing
        """
        api_key = self._config.get('gemini_api_key')
        
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for Gemini API mode"
            )
        
        logger.info("[ImageEditCoordinator] Creating Gemini API editor")
        return GeminiAPIImageEditor(api_key=api_key)
    
    def _create_vertex_ai_editor(self) -> VertexAIImageEditor:
        """
        Create Vertex AI editor instance.
        
        Returns:
            VertexAIImageEditor instance
        
        Raises:
            ValueError: If required configuration is missing
        """
        project_id = self._config.get('vertex_ai_project_id')
        location = self._config.get('vertex_ai_location')
        credentials_json = self._config.get('vertex_ai_credentials_json')
        
        # Validate required configuration
        if not project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT environment variable is required for Vertex AI mode"
            )
        
        if not location:
            raise ValueError(
                "GOOGLE_CLOUD_LOCATION environment variable is required for Vertex AI mode"
            )
        
        if not credentials_json:
            raise ValueError(
                "GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable is required for Vertex AI mode"
            )
        
        logger.info(f"[ImageEditCoordinator] Creating Vertex AI editor: project={project_id}, location={location}")
        return VertexAIImageEditor(
            project_id=project_id,
            location=location,
            credentials_json=credentials_json
        )
    
    def get_current_api_mode(self) -> str:
        """
        Get the current API mode.
        
        Returns:
            'vertex_ai' or 'gemini_api'
        """
        return self._config.get('api_mode', 'gemini_api')
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get capabilities of the current editor.
        
        Returns:
            Dictionary with capability information
        """
        try:
            editor = self.get_editor()
            return editor.get_capabilities()
        except Exception as e:
            logger.error(f"[ImageEditCoordinator] Failed to get capabilities: {e}")
            return {
                'api_type': 'unknown',
                'supports_editing': False,
                'error': str(e)
            }
    
    def reload_config(self) -> None:
        """
        Reload configuration and clear editor cache.
        
        This is useful when configuration changes at runtime.
        """
        logger.info("[ImageEditCoordinator] Reloading configuration")
        self._config = self._load_config()
        self._editor_cache.clear()
        logger.info(f"[ImageEditCoordinator] Configuration reloaded: api_mode={self._config.get('api_mode')}")
    
    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        sdk_initializer: Optional[Any] = None,
        chat_session_manager: Optional[Any] = None,
        file_handler: Optional[Any] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        智能路由图片编辑请求到对应的子服务
        
        路由逻辑（按优先级）：
        1. 如果 mode='image-chat-edit' → 使用 ConversationalImageEditService（对话式编辑）
        2. 如果 mode='image-mask-edit' → 使用 Vertex AI Imagen（精确编辑，必须有 mask）
        3. 如果 mode='image-inpainting' → 使用 Vertex AI Imagen（图片修复）
        4. 如果 mode='image-background-edit' → 使用 Vertex AI Imagen（背景编辑）
        5. 如果 mode='image-recontext' → 使用 Vertex AI Imagen（重新上下文）
        6. 如果有 mask → 使用 Vertex AI Imagen（精确编辑，自动检测）
        7. 如果没有 mask → 使用 SimpleImageEditService（generateContent 方式，简单编辑）
        
        Args:
            prompt: Text description of the desired edit
            model: Model to use for editing
            reference_images: Dictionary mapping reference image types to Base64-encoded images
                Required key: 'raw' (base image)
                Optional keys: 'mask', 'control', 'style', 'subject', 'content'
            mode: 编辑模式（可选）：'image-chat-edit', 'image-mask-edit', 'image-inpainting', 
                 'image-background-edit', 'image-recontext'
            sdk_initializer: SDK 初始化器（用于 ConversationalImageEditService 和 SimpleImageEditService）
            chat_session_manager: Chat 会话管理器（用于 ConversationalImageEditService）
            file_handler: 文件处理器（用于 ConversationalImageEditService 和 SimpleImageEditService）
            user_id: 用户 ID（用于会话管理）
            **kwargs: Additional parameters (edit_mode, number_of_images, aspect_ratio, etc.)
        
        Returns:
            List of edited images with metadata
        """
        logger.info(f"[ImageEditCoordinator] Image editing request: model={model}, mode={mode}, prompt='{prompt[:50]}...'")
        logger.info(f"[ImageEditCoordinator] Reference images: {list(reference_images.keys())}, additional parameters: {list(kwargs.keys())}")
        
        # 路由 1: 对话式编辑模式
        if mode == 'image-chat-edit':
            if not chat_session_manager:
                raise ValueError("ChatSessionManager is required for image-chat-edit mode")
            if not sdk_initializer:
                raise ValueError("SDKInitializer is required for image-chat-edit mode")
            if not file_handler:
                raise ValueError("FileHandler is required for image-chat-edit mode")
            
            from .conversational_image_edit_service import ConversationalImageEditService
            conversational_service = ConversationalImageEditService(
                sdk_initializer=sdk_initializer,
                chat_session_manager=chat_session_manager,
                file_handler=file_handler
            )
            
            return await conversational_service.edit_image(
                prompt=prompt,
                model=model,
                reference_images=reference_images,
                user_id=user_id,
                **kwargs
            )
        
        # 路由 2-5: Vertex AI Imagen 模式（mask-edit, inpainting, background-edit, recontext）
        vertex_ai_modes = ['image-mask-edit', 'image-inpainting', 'image-background-edit', 'image-recontext']
        if mode in vertex_ai_modes:
            has_mask = 'mask' in reference_images and reference_images.get('mask')
            
            if mode == 'image-mask-edit' and not has_mask:
                raise ValueError("image-mask-edit mode requires a mask in reference_images")
            
            if mode == 'image-inpainting' and not has_mask:
                logger.warning("[ImageEditCoordinator] image-inpainting mode typically requires a mask, proceeding without mask")
            
            # 设置编辑模式
            edit_mode_map = {
                'image-mask-edit': 'mask_edit',
                'image-inpainting': 'inpainting',
                'image-background-edit': 'background_edit',
                'image-recontext': 'recontext'
            }
            kwargs['edit_mode'] = edit_mode_map.get(mode, 'inpainting')
            
            logger.info(f"[ImageEditCoordinator] Using Vertex AI Imagen for {mode}")
            editor = self.get_editor()
            return await editor.edit_image(
                prompt=prompt,
                reference_images=reference_images,
                config=kwargs
            )
        
        # 路由 6 & 7: 根据是否有 mask 自动选择（未指定模式或向后兼容）
        has_mask = 'mask' in reference_images and reference_images.get('mask')
        
        if has_mask:
            # 使用 Vertex AI Imagen（精确编辑）
            logger.info("[ImageEditCoordinator] Using Vertex AI Imagen for precise editing (has mask, auto-detect)")
            editor = self.get_editor()
            return await editor.edit_image(
                prompt=prompt,
                reference_images=reference_images,
                config=kwargs
            )
        else:
            # 使用 SimpleImageEditService（generateContent 方式，简单编辑）
            if not sdk_initializer:
                raise ValueError("SDKInitializer is required for simple image editing")
            if not file_handler:
                raise ValueError("FileHandler is required for simple image editing")
            
            logger.info("[ImageEditCoordinator] Using SimpleImageEditService for simple editing (no mask, auto-detect)")
            from .simple_image_edit_service import SimpleImageEditService
            
            simple_edit_service = SimpleImageEditService(
                sdk_initializer=sdk_initializer,
                file_handler=file_handler
            )
            
            return await simple_edit_service.edit_image(
                prompt=prompt,
                model=model,
                reference_images=reference_images,
                **kwargs
            )
