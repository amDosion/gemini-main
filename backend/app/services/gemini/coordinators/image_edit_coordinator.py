"""
Coordinator for selecting between Gemini API and Vertex AI image editing implementations.

This module implements the factory pattern to dynamically select the appropriate
image editor based on configuration.

Also handles mode routing to different edit services:
- ConversationalImageEditService: For chat-based editing
- MaskEditService: For mask/auto-mask editing (Vertex AI Imagen)
- Vertex AI Imagen editors: For inpainting/background/recontext
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from ..base.image_edit_base import BaseImageEditor
from ..base.image_edit_common import NotSupportedError
from ..geminiapi.image_edit_gemini_api import GeminiAPIImageEditor
from ..vertexai.image_edit_vertex_ai import VertexAIImageEditor
from ..vertexai.mask_edit_service import MaskEditService
from ..vertexai.inpainting_service import InpaintingService
from ..vertexai.background_edit_service import BackgroundEditService
from ..vertexai.recontext_service import RecontextService
from ...common.google_model_catalog import get_static_google_vertex_model_ids_for_family
from ._config_cache import get_or_load as _cached_load, clear_config_cache  # noqa: F401
from ....utils.log_sanitization import summarize_text_for_log

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
                from ....models.db_models import VertexAIConfig
                from ....core.encryption import decrypt_api_key

                def _load_vertex() -> Optional[Dict[str, Any]]:
                    row = self._db.query(VertexAIConfig).filter(
                        VertexAIConfig.user_id == self._user_id
                    ).first()
                    if not row:
                        return None
                    return {
                        "api_mode": row.api_mode,
                        "vertex_ai_project_id": row.vertex_ai_project_id,
                        "vertex_ai_location": row.vertex_ai_location,
                        "vertex_ai_credentials_json": row.vertex_ai_credentials_json,
                    }

                user_config = _cached_load(self._user_id, "vertex_ai_config", _load_vertex)

                if user_config:
                    logger.info(f"[ImageEditCoordinator] Using Vertex AI config from database for user={self._user_id}")

                    config['api_mode'] = user_config.get('api_mode')
                    config['vertex_ai_project_id'] = user_config.get('vertex_ai_project_id')
                    config['vertex_ai_location'] = user_config.get('vertex_ai_location') or 'us-central1'

                    # Decrypt credentials JSON if present (fail-closed: an undecryptable
                    # token resolves to '' and is never forwarded to the Vertex AI SDK).
                    raw_credentials = user_config.get('vertex_ai_credentials_json')
                    if raw_credentials:
                        decrypted_credentials = decrypt_api_key(raw_credentials, silent=True)
                        if decrypted_credentials:
                            config['vertex_ai_credentials_json'] = decrypted_credentials
                            logger.debug(f"[ImageEditCoordinator] Successfully decrypted Vertex AI credentials")
                        else:
                            logger.error(f"[ImageEditCoordinator] Failed to decrypt credentials (key mismatch); refusing to forward ciphertext")
                            config['vertex_ai_credentials_json'] = None

                    # For Gemini API mode, get API key from ConfigProfile
                    if user_config.get('api_mode') == 'gemini_api':
                        from ....models.db_models import ConfigProfile

                        def _load_google_profile() -> Optional[Dict[str, Any]]:
                            row = self._db.query(ConfigProfile).filter(
                                ConfigProfile.user_id == self._user_id,
                                ConfigProfile.provider_id == 'google'
                            ).first()
                            if not row:
                                return None
                            return {"api_key": row.api_key}

                        google_profile = _cached_load(
                            self._user_id, "config_profile_first", _load_google_profile, "google"
                        )

                        if google_profile and google_profile.get('api_key'):
                            # ✅ 解密 API Key（fail-closed：密钥不匹配时返回 ''，绝不下发密文）
                            api_key = decrypt_api_key(google_profile.get('api_key'), silent=True)
                            if not api_key:
                                logger.error(f"[ImageEditCoordinator] Failed to decrypt API key from ConfigProfile (key mismatch); refusing to forward ciphertext")

                            if api_key:
                                config['gemini_api_key'] = api_key
                                logger.info(f"[ImageEditCoordinator] Using Gemini API key from ConfigProfile for user={self._user_id}")
                            else:
                                logger.warning(f"[ImageEditCoordinator] Failed to decrypt API key from ConfigProfile for user={self._user_id}, will fall back to environment")
                        else:
                            logger.warning(f"[ImageEditCoordinator] No Google ConfigProfile found for user={self._user_id}, will fall back to environment")

                    # Validate configuration completeness
                    if user_config.get('api_mode') == 'vertex_ai':
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
                    elif user_config.get('api_mode') == 'gemini_api':
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
        # Invalidate shared config cache so DB is re-read on next _load_config
        if self._user_id:
            clear_config_cache(user_id=self._user_id)
        self._config = self._load_config()
        self._editor_cache.clear()
        logger.info(f"[ImageEditCoordinator] Configuration reloaded: api_mode={self._config.get('api_mode')}")
    
    # ==================== 统一的服务获取方法 ====================
    # 所有 Vertex AI 编辑服务遵循相同的创建/缓存模式

    def _require_vertex_ai(self, mode: str) -> None:
        """验证当前 API 模式为 Vertex AI，否则抛出异常"""
        api_mode = self.get_current_api_mode()
        if api_mode != 'vertex_ai':
            raise NotSupportedError(
                f"{mode} mode requires Vertex AI configuration. "
                f"Please set GOOGLE_GENAI_USE_VERTEXAI=true or configure Vertex AI in your settings. "
                f"Current API mode: {api_mode}",
                api_type=api_mode
            )

    def _get_vertex_credentials(self) -> tuple:
        """获取 Vertex AI 凭据三元组 (project_id, location, credentials_json)"""
        project_id = self._config.get('vertex_ai_project_id')
        location = self._config.get('vertex_ai_location', 'us-central1')
        credentials_json = self._config.get('vertex_ai_credentials_json')

        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT is required for Vertex AI mode")
        if not location:
            raise ValueError("GOOGLE_CLOUD_LOCATION is required for Vertex AI mode")
        if not credentials_json:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is required for Vertex AI mode")

        return project_id, location, credentials_json

    def _build_vertex_credentials_object(self):
        """Build google-auth service account credentials for google-genai Vertex clients."""
        _, _, credentials_json = self._get_vertex_credentials()
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError(
                "google-auth is required for Vertex AI service account credentials"
            ) from exc

        if isinstance(credentials_json, str):
            credentials_info = json.loads(credentials_json)
        elif isinstance(credentials_json, dict):
            credentials_info = credentials_json
        else:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON must be a JSON object string")

        return service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    def _build_gemini_image_pool_kwargs(
        self,
        incoming_pool_kwargs: Optional[Dict[str, Any]],
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve pool kwargs for Gemini native image services from the active API mode.

        Chat Edit is a Gemini Developer API feature in this app and must not be
        switched to Vertex merely because Vertex AI is configured for other
        modes. Recontext/Product Recontext can still follow the active Vertex
        configuration because those modes intentionally use Gemini image through
        the user's configured Google Cloud project when available.
        """
        incoming = dict(incoming_pool_kwargs or {})

        if mode == 'image-chat-edit':
            api_key = incoming.get('api_key') or self._config.get('gemini_api_key')
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required for image-chat-edit")
            return {
                'api_key': api_key,
                'use_vertex': False,
                'http_options': incoming.get('http_options'),
            }

        if self.get_current_api_mode() == 'vertex_ai':
            project_id, location, _ = self._get_vertex_credentials()
            return {
                'api_key': incoming.get('api_key') or self._config.get('gemini_api_key'),
                'use_vertex': True,
                'project': project_id,
                'location': location,
                'credentials': self._build_vertex_credentials_object(),
                'http_options': incoming.get('http_options'),
            }

        if incoming:
            incoming['use_vertex'] = bool(incoming.get('use_vertex', False))
            return incoming

        api_key = self._config.get('gemini_api_key')
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini image editing modes")
        return {
            'api_key': api_key,
            'use_vertex': False,
        }

    def _get_cached_service(self, cache_key: str, service_class):
        """获取或创建缓存的 Vertex AI 编辑服务（统一模式）"""
        if cache_key in self._editor_cache:
            logger.debug(f"[ImageEditCoordinator] Using cached {cache_key} editor")
            return self._editor_cache[cache_key]

        project_id, location, credentials_json = self._get_vertex_credentials()
        service = service_class(
            project_id=project_id,
            location=location,
            credentials_json=credentials_json
        )
        self._editor_cache[cache_key] = service
        logger.info(f"[ImageEditCoordinator] Created and cached {cache_key} editor ({service_class.__name__})")
        return service

    def get_mask_editor(self) -> MaskEditService:
        """获取 MaskEditService 实例（缓存）"""
        return self._get_cached_service('mask_edit', MaskEditService)

    def get_inpainting_editor(self) -> InpaintingService:
        """获取 InpaintingService 实例（缓存）"""
        return self._get_cached_service('inpainting', InpaintingService)

    def get_background_editor(self) -> BackgroundEditService:
        """获取 BackgroundEditService 实例（缓存）"""
        return self._get_cached_service('background_edit', BackgroundEditService)

    def get_recontext_editor(self) -> RecontextService:
        """获取 RecontextService 实例（缓存）"""
        return self._get_cached_service('recontext', RecontextService)

    # ==================== 统一模型验证 ====================

    @staticmethod
    def _short_model_id(model: str) -> str:
        return str(model or '').split('/')[-1]

    @classmethod
    def _validate_edit_model(cls, model: str) -> str:
        """Validate and return a model that is compatible with Vertex Imagen edit_image."""
        imagen_edit_models = set(get_static_google_vertex_model_ids_for_family("imagen_edit")) or {'imagen-3.0-capability-001'}
        short_model = cls._short_model_id(model)
        if short_model in imagen_edit_models:
            return short_model
        if not short_model:
            default_model = sorted(imagen_edit_models)[0]
            logger.info(f"[ImageEditCoordinator] No Imagen edit model selected, using default: {default_model}")
            return default_model
        raise ValueError(
            f"Model '{model}' is not compatible with Vertex Imagen edit_image API. "
            f"Select one of: {', '.join(sorted(imagen_edit_models))}"
        )

    @classmethod
    def _is_gemini_image_model(cls, model: str) -> bool:
        short_model = cls._short_model_id(model)
        if short_model in set(get_static_google_vertex_model_ids_for_family("gemini_image")):
            return True
        lower = (model or '').lower()
        return lower.startswith('gemini-') and 'image' in lower

    async def _edit_with_conversational_image_service(
        self,
        *,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        pool_kwargs: Optional[Dict[str, Any]],
        chat_session_manager: Optional[Any],
        file_handler: Optional[Any],
        user_id: Optional[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        if not chat_session_manager:
            raise ValueError("ChatSessionManager is required for Gemini image editing modes")
        if not pool_kwargs:
            raise ValueError("pool_kwargs is required for Gemini image editing modes")
        if not file_handler:
            raise ValueError("FileHandler is required for Gemini image editing modes")

        from ..geminiapi.conversational_image_edit_service import ConversationalImageEditService
        conversational_service = ConversationalImageEditService(
            chat_session_manager=chat_session_manager,
            file_handler=file_handler,
            **pool_kwargs,
        )

        return await conversational_service.edit_image(
            prompt=prompt,
            model=model,
            reference_images=reference_images,
            user_id=user_id,
            **kwargs
        )

    async def _edit_with_gemini_recontext_service(
        self,
        *,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        pool_kwargs: Optional[Dict[str, Any]],
        chat_session_manager: Optional[Any],
        file_handler: Optional[Any],
        user_id: Optional[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        if not chat_session_manager:
            raise ValueError("ChatSessionManager is required for Gemini recontext modes")
        if not pool_kwargs:
            raise ValueError("pool_kwargs is required for Gemini recontext modes")
        if not file_handler:
            raise ValueError("FileHandler is required for Gemini recontext modes")

        from ..geminiapi.recontext_image_service import GeminiRecontextImageService
        recontext_service = GeminiRecontextImageService(
            chat_session_manager=chat_session_manager,
            file_handler=file_handler,
            **pool_kwargs,
        )

        return await recontext_service.edit_image(
            prompt=prompt,
            model=model,
            reference_images=reference_images,
            user_id=user_id,
            **kwargs
        )

    # ==================== 主路由方法 ====================

    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        pool_kwargs: Optional[Dict[str, Any]] = None,
        chat_session_manager: Optional[Any] = None,
        file_handler: Optional[Any] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        智能路由图片编辑请求到对应的子服务

        路由逻辑（按优先级）：
        1. mode='image-background-edit' → BackgroundEditService（Vertex Imagen BGSWAP）
        2. Recontext + Gemini image 模型 → GeminiRecontextImageService（Gemini native recontext）
        3. 其它 Gemini image 模型 → ConversationalImageEditService（官方 generate_content/chat 图片编辑）
        4. mode='image-chat-edit' → ConversationalImageEditService（对话式编辑）
        5. mode='image-mask-edit' → MaskEditService（掩码编辑）
        6. mode='image-inpainting' → InpaintingService（图片修复）
        7. 有 mask → MaskEditService（掩码编辑，自动检测）
        8. 无 mask → MaskEditService（自动掩码）

        Vertex Imagen edit 路径使用统一模式：get_xxx_editor() → editor.edit_image(prompt, reference_images, config)
        """
        logger.info(
            "[ImageEditCoordinator] Image editing request: model=%s, mode=%s, prompt=%s",
            model,
            mode,
            summarize_text_for_log(prompt, label="prompt"),
        )
        logger.info(f"[ImageEditCoordinator] Reference images: {list(reference_images.keys())}, additional parameters: {list(kwargs.keys())}")

        if mode == 'image-background-edit':
            self._require_vertex_ai(mode)
            kwargs['model'] = self._validate_edit_model(model)
            logger.info(f"[ImageEditCoordinator] → BackgroundEditService.edit_image(): model={kwargs['model']}")
            editor = self.get_background_editor()
            return editor.edit_image(prompt=prompt, reference_images=reference_images, config=kwargs)

        # Mask edit is an official Vertex Imagen edit_image flow. It must not
        # fall through to Gemini image conversational editing, because that path
        # cannot preserve MaskReferenceImage semantics.
        if mode == 'image-mask-edit':
            self._require_vertex_ai(mode)
            kwargs['model'] = self._validate_edit_model(model)
            logger.info(f"[ImageEditCoordinator] → MaskEditService.edit_image(): model={kwargs['model']}")
            editor = self.get_mask_editor()
            return editor.edit_image(prompt=prompt, reference_images=reference_images, config=kwargs)

        if mode in {'image-recontext', 'product-recontext'} and self._is_gemini_image_model(model):
            logger.info(f"[ImageEditCoordinator] → GeminiRecontextImageService.edit_image(): model={model}, mode={mode}")
            gemini_pool_kwargs = self._build_gemini_image_pool_kwargs(pool_kwargs, mode=mode)
            return await self._edit_with_gemini_recontext_service(
                prompt=prompt,
                model=model,
                reference_images=reference_images,
                pool_kwargs=gemini_pool_kwargs,
                chat_session_manager=chat_session_manager,
                file_handler=file_handler,
                user_id=user_id,
                **kwargs
            )

        if mode in {'image-recontext', 'product-recontext'}:
            raise ValueError(
                f"{mode} requires a Gemini image model such as gemini-2.5-flash-image. "
                f"Received incompatible model: {model}"
            )

        # Gemini image models use the official Gemini native image editing API
        # (generate_content/chat), independent of the UI edit mode.
        if self._is_gemini_image_model(model):
            logger.info(f"[ImageEditCoordinator] → ConversationalImageEditService.edit_image(): model={model}, mode={mode}")
            gemini_pool_kwargs = self._build_gemini_image_pool_kwargs(pool_kwargs, mode=mode)
            return await self._edit_with_conversational_image_service(
                prompt=prompt,
                model=model,
                reference_images=reference_images,
                pool_kwargs=gemini_pool_kwargs,
                chat_session_manager=chat_session_manager,
                file_handler=file_handler,
                user_id=user_id,
                **kwargs
            )

        # 路由 2: 对话式编辑模式
        if mode == 'image-chat-edit':
            logger.info(f"[ImageEditCoordinator] → ConversationalImageEditService.edit_image(): model={model}, mode={mode}")
            gemini_pool_kwargs = self._build_gemini_image_pool_kwargs(pool_kwargs, mode=mode)
            return await self._edit_with_conversational_image_service(
                prompt=prompt,
                model=model,
                reference_images=reference_images,
                pool_kwargs=gemini_pool_kwargs,
                chat_session_manager=chat_session_manager,
                file_handler=file_handler,
                user_id=user_id,
                **kwargs
            )

        # 路由 3: 图片修复模式 → InpaintingService
        if mode == 'image-inpainting':
            self._require_vertex_ai(mode)
            kwargs['model'] = self._validate_edit_model(model)
            logger.info(f"[ImageEditCoordinator] → InpaintingService.edit_image(): model={kwargs['model']}")
            editor = self.get_inpainting_editor()
            return editor.edit_image(prompt=prompt, reference_images=reference_images, config=kwargs)

        # 路由 6 & 7: 根据是否有 mask 自动选择（未指定模式或向后兼容）
        has_mask = 'mask' in reference_images and reference_images.get('mask')

        self._require_vertex_ai('image-edit')
        kwargs['model'] = self._validate_edit_model(model)
        editor = self.get_mask_editor()

        if has_mask:
            logger.info("[ImageEditCoordinator] → MaskEditService.edit_image(): has mask, auto-detect")
        else:
            logger.info("[ImageEditCoordinator] → MaskEditService.edit_image(): no mask, auto-mask")

        return editor.edit_image(
            prompt=prompt,
            reference_images=reference_images,
            config=kwargs
        )
