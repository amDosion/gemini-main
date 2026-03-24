"""
Google (Gemini) Provider Service - Main Coordinator

This module coordinates all Gemini-related operations by delegating to specialized handlers.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Union, Type, Tuple, Callable
import logging
from sqlalchemy.orm import Session

from ..common.base_provider import BaseProviderService
from ..common.model_capabilities import ModelConfig, build_model_config
from ..common.errors import (
    ProviderError,
    OperationError,
    ClientCreationError,
    ErrorContext,
    ExecutionTimer,
    RequestIDManager
)
from .common.chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .coordinators.image_edit_coordinator import ImageEditCoordinator
from .coordinators.video_generation_coordinator import VideoGenerationCoordinator
from .coordinators.video_understanding_coordinator import VideoUnderstandingCoordinator
from .common.model_manager import ModelManager
from .common.file_handler import FileHandler
from .common.function_handler import FunctionHandler
from .common.schema_handler import SchemaHandler
from .common.token_handler import TokenHandler
from .client_pool import get_client_pool
from .agent.types import (
    GenerateContentConfig,
    Content,
    Part,
    Tool,
    FunctionDeclaration,
    SafetySetting,
    HttpOptions,
    HttpRetryOptions,
)
from .vertexai.expand_service import ExpandService
from .vertexai.segmentation_service import SegmentationService
from .vertexai.tryon_service import TryOnService
from .common.pdf_extractor import PDFExtractorService

logger = logging.getLogger(__name__)


def _attach_legacy_multi_agent_service_meta(
    result: Any,
    *,
    mode: str,
    model: str,
) -> Dict[str, Any]:
    service_meta = {
        "entrypoint": "GoogleService.multi_agent",
        "legacy": True,
        "status": "compatibility-only",
        "provider_neutral": False,
        "runtime_kind": "google-gemini",
        "provider_scope": "google",
        "supports_provider_switch": False,
        "recommended_entrypoint": "provider-mode",
        "recommended_path_template": "/api/modes/{provider}/multi-agent",
        "mode": mode,
        "model": model,
    }
    if isinstance(result, dict):
        payload = dict(result)
        existing_meta = payload.get("service_meta")
        if isinstance(existing_meta, dict):
            service_meta = {
                **service_meta,
                **existing_meta,
            }
        payload["service_meta"] = service_meta
        return payload
    return {
        "result": result,
        "service_meta": service_meta,
    }


class GoogleService(BaseProviderService):
    """
    Google Gemini Provider Service - Main Coordinator.

    This service coordinates all Gemini operations by delegating to:
    - ChatHandler: Chat operations
    - ImageGenerator: Image generation
    - ModelManager: Model listing
    - FileHandler: File upload/download operations
    - FunctionHandler: Function calling and tool integration
    - SchemaHandler: Structured JSON response handling
    - TokenHandler: Token counting and cost estimation
    - ExpandService: Image expansion/outpainting
    - UpscaleService: Image upscaling
    - SegmentationService: Image segmentation
    - TryOnService: Virtual try-on
    - PDFExtractor: PDF structured data extraction

    Official SDK: https://googleapis.github.io/python-genai/
    
    Dual-Client Support:
    - Vertex AI Client: For advanced features (image editing, try-on, etc.)
    - Developer API Client: For basic chat and generation
    - Client lifecycle: Unified by GeminiClientPool
    """
    
    def __init__(
        self, 
        api_key: str, 
        api_url: Optional[str] = None, 
        use_official_sdk: bool = False,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        request_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Google service coordinator.
        
        Args:
            api_key: Google API key for authentication
            api_url: Optional custom API URL
            use_official_sdk: Whether to use the official Google GenAI SDK compatibility layer
            user_id: Optional user ID for Vertex AI configuration lookup
            db: Optional database session for Vertex AI configuration lookup
            request_id: Optional request ID for tracing (generated if not provided)
            **kwargs: Additional parameters (use_vertex, project, location, etc.)
        """
        super().__init__(api_key, api_url, **kwargs)
        
        self.user_id = user_id
        self.db = db
        self.use_official_sdk = use_official_sdk
        self.request_id = request_id or RequestIDManager.generate()
        
        # 保存 Vertex AI 配置参数（用于 interactions_manager）
        self.use_vertex = kwargs.get('use_vertex', False)
        self.project = kwargs.get('project')
        self.location = kwargs.get('location')
        self.http_options = self._build_http_options_from_kwargs(kwargs)
        
        # Validate credentials before creating clients
        try:
            self._validate_credentials(api_key, kwargs)
        except ValueError as e:
            context = ErrorContext(
                provider_id="google",
                client_type="single",
                operation="initialization",
                request_id=self.request_id,
                user_id=user_id
            )
            raise ClientCreationError(
                message=str(e),
                context=context,
                original_error=e
            )
        
        if use_official_sdk:
            # 直接获取 interactions_manager（不通过 adapter）
            # 根据文档：google_service.py 应该直接协调各个管理器
            # Lazy import to avoid circular dependency
            from ..common.interactions_manager import get_interactions_manager
            self._interactions_manager = get_interactions_manager()
            logger.info(
                "[Google Service] Initialized official SDK mode (adapter inlined)",
                extra={
                    'request_id': self.request_id,
                    'operation': 'initialization',
                }
            )
        else:
            self._interactions_manager = None
            # Store pool params for handler initialization (replaces SDKInitializer)
            self._pool_kwargs = dict(
                api_key=api_key,
                use_vertex=kwargs.get('use_vertex', False),
                project=kwargs.get('project'),
                location=kwargs.get('location') or 'us-central1',
                http_options=self.http_options,
            )
            logger.info(
                "[Google Service] Configured client pool params",
                extra={
                    'request_id': self.request_id,
                    'operation': 'initialization',
                }
            )

            # Initialize handlers (these are lightweight, no need to cache)
            self.chat_handler = ChatHandler(**self._pool_kwargs)
            # 使用 Gemini API 进行图像生成
            self.image_generator = ImageGenerator(
                api_key=api_key,
                user_id=user_id,
                db=db
            )
            # Initialize chat session manager (for conversational image editing)
            if db:
                from .common.chat_session_manager import ChatSessionManager
                self.chat_session_manager = ChatSessionManager(db)
            else:
                self.chat_session_manager = None
            # Initialize image edit coordinator
            self.image_edit_coordinator = ImageEditCoordinator(
                user_id=user_id,
                db=db
            )
            self.model_manager = ModelManager(api_key, api_url)
            
            # Initialize new handlers (P0 features)
            self.file_handler = FileHandler(**self._pool_kwargs)
            self.function_handler = FunctionHandler(**self._pool_kwargs)
            self.schema_handler = SchemaHandler(**self._pool_kwargs)
            self.token_handler = TokenHandler(**self._pool_kwargs)
            self.video_generation_coordinator = VideoGenerationCoordinator(
                user_id=user_id,
                db=db,
                api_key=api_key,
                http_options=self.http_options,
            )
            self.video_understanding_coordinator = VideoUnderstandingCoordinator(
                user_id=user_id,
                db=db,
                api_key=api_key,
                http_options=self.http_options,
            )
            
            # Initialize specialized image services (遵循 GEN 模式，从数据库获取 Vertex AI 配置)
            self.expand_service = ExpandService(user_id=user_id, db=db)
            self.segmentation_service = SegmentationService(user_id=user_id, db=db)

            # Initialize PDF extraction service
            self.pdf_extractor = PDFExtractorService(**self._pool_kwargs)

            # Initialize virtual try-on service
            self.tryon_service = TryOnService()

            logger.info("[Google Service] Using legacy SDK implementation")

    def _ensure_client_factory_for_fallback(self) -> None:
        """Ensure _client_factory is available when official SDK mode needs legacy fallbacks."""
        if hasattr(self, "_client_factory") and self._client_factory:
            return
        _pool = get_client_pool()
        self._client_factory = lambda: _pool.get_client(
            api_key=self.api_key,
            vertexai=self.use_vertex,
            project=self.project,
            location=self.location or 'us-central1',
            http_options=self.http_options,
        )

    def _ensure_legacy_feature_services(self) -> None:
        """
        Lazily initialize legacy feature services so official SDK mode can still execute
        image/pdf/try-on capabilities via existing specialized services.
        """
        if not hasattr(self, "expand_service"):
            self.expand_service = ExpandService(user_id=self.user_id, db=self.db)
        if not hasattr(self, "segmentation_service"):
            self.segmentation_service = SegmentationService(user_id=self.user_id, db=self.db)
        if not hasattr(self, "video_generation_coordinator"):
            self.video_generation_coordinator = VideoGenerationCoordinator(
                user_id=self.user_id,
                db=self.db,
                api_key=self.api_key,
                http_options=self.http_options,
            )
        if not hasattr(self, "video_understanding_coordinator"):
            self.video_understanding_coordinator = VideoUnderstandingCoordinator(
                user_id=self.user_id,
                db=self.db,
                api_key=self.api_key,
                http_options=self.http_options,
            )
        if not hasattr(self, "tryon_service"):
            self.tryon_service = TryOnService()
        if not hasattr(self, "pdf_extractor"):
            self._ensure_client_factory_for_fallback()
            self.pdf_extractor = PDFExtractorService(**self._pool_kwargs)

    @staticmethod
    def _build_http_options_from_kwargs(kwargs: Dict[str, Any]) -> Optional[HttpOptions]:
        timeout_raw = kwargs.get("timeout")
        max_retries_raw = kwargs.get("max_retries")

        timeout_ms: Optional[int] = None
        if timeout_raw is not None:
            try:
                timeout_seconds = float(timeout_raw)
                if timeout_seconds > 0:
                    timeout_ms = int(timeout_seconds * 1000)
            except (TypeError, ValueError):
                timeout_ms = None

        retry_options: Optional[HttpRetryOptions] = None
        if max_retries_raw is not None:
            try:
                attempts = int(max_retries_raw)
                if attempts > 0:
                    retry_options = HttpRetryOptions(attempts=attempts)
            except (TypeError, ValueError):
                retry_options = None

        if timeout_ms is None and retry_options is None:
            return None

        return HttpOptions(
            timeout=timeout_ms,
            retry_options=retry_options,
        )

    def _build_image_chat_http_options(self) -> HttpOptions:
        base_options = self.http_options or HttpOptions()
        return HttpOptions(
            api_version=base_options.api_version,
            base_url=base_options.base_url,
            headers=dict(base_options.headers) if base_options.headers else None,
            timeout=None,
            retry_options=base_options.retry_options,
            use_default_timeout=False,
        )

    def _get_client_factory_for_mode(self, mode: Optional[str]) -> Callable:
        if mode != "image-chat-edit":
            return self._client_factory
        _pool = get_client_pool()
        return lambda: _pool.get_client(
            api_key=self.api_key,
            vertexai=self.use_vertex,
            project=self.project,
            location=self.location or 'us-central1',
            http_options=self._build_image_chat_http_options(),
        )
    
    def _validate_credentials(self, api_key: str, kwargs: Dict[str, Any]) -> None:
        """
        Validate required credentials before creating clients.
        
        Args:
            api_key: Google API key
            kwargs: Additional parameters
        
        Raises:
            ValueError: If required credentials are missing
        """
        use_vertex = kwargs.get('use_vertex', False)
        
        if use_vertex:
            # Vertex AI mode requires project ID
            project = kwargs.get('project')
            if not project and not api_key:
                raise ValueError(
                    "Vertex AI mode requires either 'project' (for ADC) or 'api_key' (for API key auth). "
                    "Please provide one of these credentials."
                )
            
            if project:
                logger.info(
                    f"[Google Service] Validated Vertex AI credentials: project={project}",
                    extra={'request_id': self.request_id, 'operation': 'credential_validation', 'platform': 'vertex_ai'}
                )
            else:
                logger.info(
                    "[Google Service] Validated Vertex AI credentials: using API key",
                    extra={'request_id': self.request_id, 'operation': 'credential_validation', 'platform': 'vertex_ai'}
                )
        else:
            # Gemini API mode requires API key
            if not api_key:
                raise ValueError(
                    "Gemini API mode requires 'api_key'. "
                    "Please provide a valid Google API key."
                )
            
            logger.info(
                "[Google Service] Validated Gemini API credentials",
                extra={'request_id': self.request_id, 'operation': 'credential_validation', 'platform': 'developer_api'}
            )
    
    # ------------------------------------------------------------------
    # Official SDK helpers (inlined from OfficialSDKAdapter)
    # ------------------------------------------------------------------

    def _get_official_client(self):
        """Get a client from the unified pool for official SDK operations."""
        pool = get_client_pool()
        return pool.get_client(
            api_key=self.api_key,
            vertexai=self.use_vertex,
            project=self.project,
            location=self.location or 'us-central1' if self.use_vertex else None,
            http_options=self.http_options,
        )

    def _convert_messages_to_contents(self, messages: List[Dict[str, Any]]) -> List[Content]:
        """Convert existing message format to official SDK Content format."""
        contents = []
        for message in messages:
            role = message.get('role', 'user')
            content_text = message.get('content', '')

            if isinstance(content_text, str):
                parts = [Part.from_text(content_text)]
            elif isinstance(content_text, list):
                parts = []
                for item in content_text:
                    if isinstance(item, dict):
                        if 'text' in item:
                            parts.append(Part.from_text(item['text']))
                        elif 'image_url' in item:
                            parts.append(Part.from_uri(
                                file_uri=item['image_url']['url'],
                                mime_type='image/jpeg'
                            ))
                    else:
                        parts.append(Part.from_text(str(item)))
            else:
                parts = [Part.from_text(str(content_text))]

            contents.append(Content(role=role, parts=parts))
        return contents

    def _build_generation_config(self, **kwargs) -> Optional[GenerateContentConfig]:
        """Build GenerateContentConfig from kwargs."""
        config_params = {}

        if 'temperature' in kwargs:
            config_params['temperature'] = kwargs['temperature']
        if 'top_p' in kwargs:
            config_params['top_p'] = kwargs['top_p']
        if 'top_k' in kwargs:
            config_params['top_k'] = kwargs['top_k']
        if 'max_tokens' in kwargs:
            config_params['max_output_tokens'] = kwargs['max_tokens']
        if 'stop_sequences' in kwargs:
            config_params['stop_sequences'] = kwargs['stop_sequences']
        if 'system_instruction' in kwargs:
            config_params['system_instruction'] = kwargs['system_instruction']

        if 'tools' in kwargs:
            tools = []
            for tool in kwargs['tools']:
                if isinstance(tool, dict) and 'function' in tool:
                    func_def = tool['function']
                    function_declaration = FunctionDeclaration(
                        name=func_def['name'],
                        description=func_def.get('description', ''),
                        parameters=func_def.get('parameters', {})
                    )
                    tools.append(Tool(function_declarations=[function_declaration]))
            if tools:
                config_params['tools'] = tools

        if 'safety_settings' in kwargs:
            safety_settings = []
            for setting in kwargs['safety_settings']:
                safety_settings.append(SafetySetting(
                    category=setting['category'],
                    threshold=setting['threshold']
                ))
            config_params['safety_settings'] = safety_settings

        return GenerateContentConfig(**config_params) if config_params else None

    def _convert_response_to_dict(self, response) -> Dict[str, Any]:
        """Convert official SDK response to existing dictionary format."""
        result: Dict[str, Any] = {
            'choices': [],
            'usage': {}
        }
        for i, candidate in enumerate(response.candidates):
            choice: Dict[str, Any] = {
                'index': i,
                'message': {
                    'role': 'assistant',
                    'content': ''
                },
                'finish_reason': candidate.finish_reason
            }
            if candidate.content and candidate.content.parts:
                content_parts = []
                for part in candidate.content.parts:
                    if part.text:
                        content_parts.append(part.text)
                choice['message']['content'] = ''.join(content_parts)
            result['choices'].append(choice)

        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            result['usage'] = response.usage_metadata
        return result

    async def _official_generate_content(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate content using the official SDK (inlined from adapter)."""
        try:
            client = self._get_official_client()
            contents = self._convert_messages_to_contents(messages)
            config = self._build_generation_config(**kwargs)
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            return self._convert_response_to_dict(response)
        except Exception as e:
            logger.error(f"[Google Service] Error in official generate_content: {e}")
            raise

    async def _official_stream_generate_content(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream generate content using the official SDK (inlined from adapter)."""
        try:
            client = self._get_official_client()
            contents = self._convert_messages_to_contents(messages)
            config = self._build_generation_config(**kwargs)
            stream = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config
            )
            for chunk in stream:
                yield self._convert_response_to_dict(chunk)
        except Exception as e:
            logger.error(f"[Google Service] Error in official stream_generate_content: {e}")
            raise

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Delegate to ChatHandler or inline official SDK generation."""
        if self.use_official_sdk:
            return await self._official_generate_content(messages, model, **kwargs)
        else:
            return await self.chat_handler.chat(messages, model, **kwargs)
    
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        enable_search: bool = False,
        enable_thinking: bool = False,
        enable_code_execution: bool = False,
        enable_grounding: bool = False,
        enable_browser: bool = False,
        user_id: str = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Delegate to ChatHandler or inline official SDK streaming."""
        if self.use_official_sdk:
            async for chunk in self._official_stream_generate_content(messages, model, **kwargs):
                yield chunk
        else:
            async for chunk in self.chat_handler.stream_chat(
                messages, model, enable_search, enable_thinking,
                enable_code_execution, enable_grounding, enable_browser,
                user_id=user_id, **kwargs
            ):
                yield chunk
    
    async def generate_image(
        self,
        prompt: str,
        model: str,  # 移除硬编码默认值，由前端传递
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Delegate to ImageGenerator.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use (must be provided by caller, no default)
            **kwargs: Additional parameters
        """
        import time
        start_time = time.time()
        
        logger.info(f"[GoogleService] ========== 开始图片生成 ==========")
        logger.info(f"[GoogleService] 📥 请求参数:")
        logger.info(f"[GoogleService]     - model: {model}")
        logger.info(f"[GoogleService]     - prompt: {prompt[:100] + '...' if len(prompt) > 100 else prompt}")
        logger.info(f"[GoogleService]     - prompt长度: {len(prompt)}")
        logger.info(f"[GoogleService]     - 额外参数: {list(kwargs.keys())}")
        for key, value in kwargs.items():
            if key in ['number_of_images', 'aspect_ratio', 'image_size', 'output_mime_type', 'image_style']:
                logger.info(f"[GoogleService]     - {key}: {value}")
        
        logger.info(f"[GoogleService] 🔄 委托给 ImageGenerator.generate_image()...")
        result = await self.image_generator.generate_image(prompt, model, **kwargs)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[GoogleService] ✅ 图片生成完成 (耗时: {total_time:.2f}ms)")
        logger.info(f"[GoogleService]     - 返回图片数量: {len(result) if isinstance(result, list) else 'N/A'}")
        logger.info(f"[GoogleService] ========== 图片生成流程结束 ==========")
        
        return result
    
    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        编辑图片 - 统一委托给 ImageEditCoordinator

        路由逻辑（由 ImageEditCoordinator 负责）：
        - image-chat-edit → ConversationalImageEditService (对话式编辑)
        - image-mask-edit → MaskEditService (Vertex AI Imagen 遮罩编辑，独立服务文件)
        - image-inpainting → VertexAIImageEditor (Vertex AI Imagen 图片修复)
        - image-background-edit → VertexAIImageEditor (Vertex AI Imagen 背景编辑)
        - image-recontext → VertexAIImageEditor (Vertex AI Imagen 重上下文)
        - 其他模式 → ImageEditCoordinator (统一处理)
        
        Args:
            prompt: Text description of the desired edit
            model: Model to use for editing
            reference_images: Dictionary mapping reference image types to Base64-encoded images
                Required key: 'raw' (base image)
                Optional keys: 'mask', 'control', 'style', 'subject', 'content'
            mode: 编辑模式（可选）：'image-chat-edit', 'image-mask-edit', 'image-inpainting', 
                 'image-background-edit', 'image-recontext'
            **kwargs: Additional parameters (edit_mode, number_of_images, aspect_ratio, etc.)
        
        Returns:
            List of edited images with metadata
        """
        # ✅ 所有模式统一委托给 ImageEditCoordinator（统一处理）
        # ImageEditCoordinator 负责根据 mode 路由到正确的子服务：
        # - image-chat-edit → ConversationalImageEditService
        # - image-mask-edit → MaskEditService (独立服务文件)
        # - image-inpainting → VertexAIImageEditor (Vertex AI Imagen)
        # - image-background-edit → VertexAIImageEditor (Vertex AI Imagen)
        # - image-recontext → VertexAIImageEditor (Vertex AI Imagen)
        # - 有 mask → MaskEditService (自动检测)
        # - 无 mask → MaskEditService (自动掩码)
        logger.info(f"[Google Service] Delegating image editing to ImageEditCoordinator: model={model}, mode={mode}")
        client_factory = self._get_client_factory_for_mode(mode)
        return await self.image_edit_coordinator.edit_image(
            prompt=prompt,
            model=model,
            reference_images=reference_images,
            mode=mode,
            client_factory=client_factory,
            chat_session_manager=self.chat_session_manager,
            file_handler=self.file_handler,
            user_id=self.user_id,
            **kwargs
        )

    async def layered_design(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分层设计功能（委托给 LayeredDesignService）

        Args:
            prompt: 设计目标描述
            model: 模型名称（用于布局建议时的 LLM）
            reference_images: 参考图片字典 {'raw': image_url, ...}
            mode: 分层设计模式:
                - image-layered-suggest: 布局建议
                - image-layered-decompose: 图层分解
                - image-layered-vectorize: Mask 矢量化
                - image-layered-render: 渲染合成
            **kwargs: 额外参数

        Returns:
            根据 mode 返回不同结构的结果字典
        """
        from ..common.layered_design_service import LayeredDesignService

        logger.info(f"[GoogleService] Delegating layered design to LayeredDesignService: mode={mode}")

        # 获取 LLM client（用于布局建议等需要 LLM 的功能）
        llm_client = None
        if hasattr(self, '_client_factory') and self._client_factory:
            llm_client = self._client_factory()

        # 创建 LayeredDesignService 实例
        service = LayeredDesignService(
            llm_client=llm_client,
            llm_model=model
        )

        return await service.process(
            mode=mode,
            prompt=prompt,
            reference_images=reference_images,
            **kwargs
        )

    async def get_available_models(self) -> List[ModelConfig]:
        """Delegate to ModelManager."""
        return await self.model_manager.get_available_models()
    
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        return "Google"
    
    async def generate_video(
        self, 
        prompt: str,
        model: str = "veo-3.1-generate-preview",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate video through the same GEN-style coordinator split used by Google image generation.

        Routing:
        - Gemini API mode: `geminiapi/video_generation_service.py`
        - Vertex AI mode: `vertexai/video_generation_service.py`

        The selected platform is derived from the user's VertexAIConfig/api_mode
        (or environment fallback), then the provider-mode router bridges the
        returned video into the attachment/preview pipeline.
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        logger.info(
            "[Google Service] Delegating video generation to VideoGenerationCoordinator: model=%s",
            model,
        )
        return await self.video_generation_coordinator.generate_video(
            prompt=prompt,
            model=model,
            **kwargs,
        )

    async def understand_video(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Analyze a source video with a multimodal Gemini model.

        Routing mirrors the coordinator split used by Google GEN services:
        - Gemini API mode: `geminiapi/video_understanding_service.py`
        - Vertex AI mode: `vertexai/video_understanding_service.py`
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        logger.info(
            "[Google Service] Delegating video understanding to VideoUnderstandingCoordinator: model=%s",
            model,
        )
        return await self.video_understanding_coordinator.understand_video(
            prompt=prompt,
            model=model,
            **kwargs,
        )

    async def delete_video(self, **kwargs) -> Dict[str, Any]:
        """
        Delete a generated video asset.

        Supported targets:
        - Gemini Developer API file name (`files/...`)
        - Vertex AI / generated GCS URI (`gs://...`)
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        logger.info("[Google Service] Delegating video deletion to VideoGenerationCoordinator")
        return await self.video_generation_coordinator.delete_video(**kwargs)
    
    # === File Operations (NEW) ===
    
    async def upload_file(
        self,
        file_path: str,
        display_name: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delegate to FileHandler."""
        return await self.file_handler.upload_file(file_path, display_name, mime_type)
    
    async def get_file_info(self, file_name: str) -> Dict[str, Any]:
        """Delegate to FileHandler."""
        return await self.file_handler.get_file_info(file_name)
    
    async def download_file(self, file_name: str, save_path: Optional[str] = None) -> bytes:
        """Delegate to FileHandler."""
        return await self.file_handler.download_file(file_name, save_path)
    
    async def delete_file(self, file_name: str) -> bool:
        """Delegate to FileHandler."""
        return await self.file_handler.delete_file(file_name)
    
    async def list_files(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """Delegate to FileHandler."""
        return await self.file_handler.list_files(page_size)
    
    # === Function Calling (NEW) ===
    
    def register_function(self, func, name: Optional[str] = None) -> str:
        """Delegate to FunctionHandler."""
        return self.function_handler.register_function(func, name)
    
    def create_tool_config(
        self,
        functions: List,
        mode: str = "AUTO",
        allowed_function_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Delegate to FunctionHandler."""
        from .common.function_handler import FunctionCallingMode
        mode_enum = FunctionCallingMode(mode)
        return self.function_handler.create_tool_config(functions, mode_enum, allowed_function_names)
    
    async def execute_function_call(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to FunctionHandler."""
        return await self.function_handler.execute_function_call(function_call)
    
    # === Structured Response (NEW) ===
    
    def create_json_schema_config(
        self,
        schema: Dict[str, Any],
        mime_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """Delegate to SchemaHandler."""
        return self.schema_handler.create_json_schema_config(schema, mime_type)
    
    def create_pydantic_schema_config(
        self,
        model_class,
        mime_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """Delegate to SchemaHandler."""
        return self.schema_handler.create_pydantic_schema_config(model_class, mime_type)
    
    def parse_structured_response(
        self,
        response: Any,
        target_type: Optional[Type] = None
    ):
        """Delegate to SchemaHandler."""
        return self.schema_handler.parse_structured_response(response, target_type)
    
    # === Token Management (NEW) ===
    
    async def count_tokens(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str
    ):
        """Delegate to TokenHandler."""
        return await self.token_handler.count_tokens(content, model)
    
    async def compute_tokens(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ):
        """Delegate to TokenHandler."""
        return await self.token_handler.compute_tokens(content, model, tools, system_instruction)
    
    def estimate_cost(self, token_count, model: str, is_input: bool = True) -> float:
        """Delegate to TokenHandler."""
        return self.token_handler.estimate_cost(token_count, model, is_input)
    
    def get_model_pricing(self, model: str):
        """Delegate to TokenHandler."""
        return self.token_handler.get_model_pricing(model)
    
    def check_token_limit(self, token_count, model: str) -> Dict[str, Any]:
        """Delegate to TokenHandler."""
        if self.use_official_sdk:
            # Official SDK doesn't have token limit checking yet
            return {"within_limit": True, "limit": 1000000, "usage": token_count}
        else:
            return self.token_handler.check_token_limit(token_count, model)
    
    # === Deep Research Agent (NEW - Official SDK Only) ===
    
    async def create_deep_research(
        self,
        query: str,
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_session_id: Optional[str] = None,
        stream: bool = False,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None], None]:
        """
        Create a Deep Research Agent interaction.
        
        直接使用 interactions_manager（管理层），充分利用新架构的完整功能：
        - 客户端池管理（自动复用）
        - 流式模式支持
        - MCP 工具集成
        - Memory Bank 集成（自动加载相关记忆）
        - Code Execution 支持
        - 详细日志记录
        
        Args:
            query: Research query
            agent: Agent name (default: Deep Research Agent)
            background: Whether to run in background mode
            agent_config: Optional agent configuration (e.g., {"type": "deep-research", "thinking_summaries": "auto"})
            system_instruction: Optional system instruction
            tools: Optional list of tools
            mcp_session_id: Optional MCP session ID for tool integration
            stream: Whether to use stream mode (returns AsyncGenerator if True)
            memory_bank_id: Optional Memory Bank ID for memory-enhanced interactions
            session_id: Optional session ID for memory retrieval
            
        Returns:
            Interaction result with ID and status (Dict) or stream generator (if stream=True)
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        # 直接使用 interactions_manager（管理层），使用实例属性
        # 根据文档：应该使用 self._interactions_manager 而不是每次调用 get_interactions_manager()
        if agent_config is None:
            agent_config = {
                "type": "deep-research",
                "thinking_summaries": "auto"
            }
        
        # 集成 Memory Bank（如果提供）
        if memory_bank_id and self.db:
            try:
                from .agent.memory_manager import MemoryManager
                memory_manager = MemoryManager(db=self.db)
                
                # 搜索相关记忆
                memories = await memory_manager.search_memories(
                    user_id=self.user_id or "default",
                    query=query,
                    memory_bank_id=memory_bank_id,
                    session_id=session_id,
                    limit=5
                )
                
                if memories:
                    # 将记忆添加到 system_instruction
                    memory_context = "\n".join([
                        f"- {mem.get('content', '')[:200]}"
                        for mem in memories
                    ])
                    
                    if system_instruction:
                        system_instruction = f"{system_instruction}\n\nRelevant memories:\n{memory_context}"
                    else:
                        system_instruction = f"Relevant memories:\n{memory_context}"
                    
                    logger.info(f"[Google Service] Loaded {len(memories)} memories for Deep Research")
            except Exception as e:
                logger.warning(f"[Google Service] Failed to load memories: {e}")
        
        # Deep Research 强制走 Gemini API Interactions（不走 Vertex AI）
        if not background:
            raise ValueError("Deep Research requires background=True")
        
        # 流式模式：直接返回异步生成器
        if stream:
            # Return the generator directly (not awaited)
            return self._interactions_manager.stream_interaction(
                input=query,
                api_key=self.api_key,
                agent=agent,
                agent_config=agent_config,
                system_instruction=system_instruction,
                tools=tools,
                mcp_session_id=mcp_session_id,
                vertexai=False
            )
        
        # 后台模式 - Use else to ensure only one return path
        else:
            result = await self._interactions_manager.create_interaction_async(
                api_key=self.api_key,
                input=query,
                agent=agent,
                background=background,
                store=True,
                agent_config=agent_config,
                system_instruction=system_instruction,
                tools=tools,
                mcp_session_id=mcp_session_id,
                vertexai=False
            )
            return result
    
    async def get_research_status(self, interaction_id: str) -> Dict[str, Any]:
        """
        Get the status of a Deep Research interaction.
        
        直接使用 interactions_manager（管理层）获取交互状态。
        
        Args:
            interaction_id: Interaction ID
            
        Returns:
            Interaction status and results
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        return await self._interactions_manager.get_interaction_status_async(
            api_key=self.api_key,
            interaction_id=interaction_id,
            vertexai=False
        )
    
    async def stream_deep_research(
        self,
        query: str,
        agent: str = 'deep-research-pro-preview-12-2025',
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a Deep Research Agent interaction.
        
        流式模式可以看到研究过程的实时输出，后端会记录详细日志。
        
        Args:
            query: Research query
            agent: Agent name (default: Deep Research Agent)
            agent_config: Optional agent configuration
            system_instruction: Optional system instruction
            tools: Optional list of tools
            mcp_session_id: Optional MCP session ID for tool integration
            
        Yields:
            Stream events with research progress
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        # 直接使用 interactions_manager（管理层），使用实例属性
        if agent_config is None:
            agent_config = {
                "type": "deep-research",
                "thinking_summaries": "auto"
            }
        
        async for event in self._interactions_manager.stream_interaction(
            input=query,
            api_key=self.api_key,
            agent=agent,
            agent_config=agent_config,
            system_instruction=system_instruction,
            tools=tools,
            mcp_session_id=mcp_session_id,
            vertexai=False
        ):
            yield event
    
    async def cancel_deep_research(self, interaction_id: str) -> Dict[str, Any]:
        """
        Cancel a running Deep Research interaction.
        
        只适用于后台模式中仍在运行的交互。
        
        Args:
            interaction_id: Interaction ID to cancel
            
        Returns:
            Cancelled interaction status
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        return await self._interactions_manager.cancel_interaction(
            api_key=self.api_key,
            interaction_id=interaction_id,
            vertexai=False
        )
    
    async def wait_for_research_completion(
        self,
        interaction_id: str,
        timeout: int = 300,
        poll_interval: int = 2
    ) -> Dict[str, Any]:
        """
        Wait for a Deep Research interaction to complete.
        
        等待研究完成 - 自动轮询直到完成
        
        适用场景：后台模式创建交互后，等待完整结果
        
        Args:
            interaction_id: Interaction ID
            timeout: Timeout in seconds (default: 300)
            poll_interval: Polling interval in seconds (default: 2)
            
        Returns:
            Completed interaction result
            
        Raises:
            TimeoutError: If interaction doesn't complete within timeout
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        return await self._interactions_manager.wait_for_completion(
            api_key=self.api_key,
            interaction_id=interaction_id,
            timeout=timeout,
            poll_interval=poll_interval,
            vertexai=False
        )
    
    async def deep_research(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Deep Research - 委托给 InteractionsManager
        
        Args:
            prompt: Research query
            model: Model identifier (not used, but required by interface)
            **kwargs: Additional parameters:
                - agent: Agent name (default: 'deep-research-pro-preview-12-2025')
                - background: Whether to run in background mode (default: True)
                - agent_config: Optional agent configuration
                - system_instruction: Optional system instruction
                - tools: Optional list of tools
                - mcp_session_id: Optional MCP session ID
                - memory_bank_id: Optional Memory Bank ID
                - session_id: Optional session ID
        
        Returns:
            Interaction result with ID and status
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        logger.info(f"[Google Service] Delegating deep research to InteractionsManager: agent={kwargs.get('agent', 'deep-research-pro-preview-12-2025')}")
        
        # 使用 InteractionsManager 的统一接口
        return await self._interactions_manager.deep_research(
            prompt=prompt,
            model=model,
            api_key=self.api_key,
            user_id=self.user_id,
            **kwargs
        )
    
    async def delete_research(self, interaction_id: str) -> None:
        """
        删除研究交互
        
        Args:
            interaction_id: Interaction ID
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        await self._interactions_manager.delete_interaction(
            api_key=self.api_key,
            interaction_id=interaction_id,
            vertexai=False
        )
    
    # === Image Expansion Service ===
    
    async def expand_image(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Expand image using outpainting - 委托给 ExpandService
        
        Args:
            prompt: Description of what to add in expanded areas
            model: Model identifier (required)
            reference_images: Reference images dict {'raw': image_path or image_url}
            **kwargs: Additional parameters:
                - mode: Expansion mode ('scale', 'offset', 'ratio')
                - image_path: Path to the image (alternative to reference_images)
                - expand_prompt: Alternative prompt parameter
        
        Returns:
            List of expanded images
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()
        
        logger.info(f"[Google Service] Delegating image expansion to ExpandService: model={model}")
        return await self.expand_service.expand_image(
            prompt=prompt,
            model=model,
            reference_images=reference_images,
            **kwargs
        )
    
    # === Image Upscaling Service ===
    
    async def upscale_image(
        self,
        image_path: str,
        upscale_factor: str,  # 移除硬编码默认值，由前端传递
        model: str,  # 移除硬编码默认值，由前端传递
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Upscale image resolution by 2x, 3x or 4x.

        Args:
            image_path: Path to the image to upscale
            upscale_factor: Upscale factor ('x2', 'x3' or 'x4') - must be provided by caller
            model: Model to use for upscaling (must be provided by caller, no default)
            **kwargs: Additional parameters

        Returns:
            List of upscaled images
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        logger.info(f"[Google Service] Delegating image upscaling to ExpandService: factor={upscale_factor}, model={model}")
        logger.info(f"[Google Service] Additional parameters: {list(kwargs.keys())}")

        # 委托给 ExpandService.upscale_image
        return await self.expand_service.upscale_image(
            image_path=image_path,
            upscale_factor=upscale_factor,
            model=model,
            **kwargs
        )
    
    # === Image Segmentation Service ===
    
    async def segment_image(
        self,
        image_path: str,
        model: str,  # 移除硬编码默认值，由前端传递
        prompt: Optional[str] = None,
        mask_mode: str = "MASK_MODE_FOREGROUND",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Segment objects in an image and create masks.
        
        Args:
            image_path: Path to the image to segment
            prompt: Optional text prompt for guided segmentation
            mask_mode: Segmentation mode
            model: Model to use for segmentation (must be provided by caller, no default)
            **kwargs: Additional parameters
        
        Returns:
            List of generated masks
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()
        
        prompt_log = f"prompt='{prompt[:30]}...'" if prompt and len(prompt) > 30 else f"prompt='{prompt}'"
        logger.info(f"[Google Service] Delegating image segmentation to SegmentationService: model={model}, mask_mode={mask_mode}")
        logger.info(f"[Google Service] Segmentation parameters: {prompt_log}, additional_params={list(kwargs.keys())}")

        return await self.segmentation_service.segment_image(image_path, model, prompt, mask_mode, **kwargs)

    # === PDF Extraction Service ===

    async def extract_pdf_data(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract structured data from PDF - 委托给 PDFExtractorService
        
        Args:
            prompt: Extraction instructions (used as additional_instructions)
            model: Model identifier (required)
            reference_images: Reference images dict (should contain 'pdf_bytes' or 'pdf_url')
            **kwargs: Additional parameters:
                - template_type: Template type ('invoice', 'form', 'receipt', 'contract', 'full-text')
                - pdf_bytes: PDF file content as bytes (alternative to reference_images)
                - pdf_url: PDF file URL (alternative to reference_images)
                - additional_instructions: Optional additional extraction instructions
        
        Returns:
            Dictionary containing extracted structured data
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        logger.info(f"[Google Service] Delegating PDF extraction to PDFExtractorService: model={model}")
        return await self.pdf_extractor.extract_pdf_data(
            prompt=prompt,
            model=model,
            reference_images=reference_images,
            **kwargs
        )

    def get_pdf_templates(self) -> List[Dict[str, str]]:
        """Delegate to PDFExtractorService."""
        return self.pdf_extractor.get_available_templates()

    # === Virtual Try-On Service ===

    def _resolve_vertex_config_for_tryon(self) -> Tuple[Optional[str], str, Optional[str]]:
        """
        解析 Vertex AI 配置，与 GEN/Edit 一致：优先用户 VertexAIConfig（解密），否则 env。
        返回 (project_id, location, credentials_json)。
        """
        import os
        project_id = None
        location = "us-central1"
        credentials_json = None
        from_db = False
        user_id = self.user_id
        db = self.db

        if user_id and db:
            try:
                from ...models.db_models import VertexAIConfig
                from ...core.encryption import decrypt_data, is_encrypted
                uc = db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()
                if uc and uc.api_mode == "vertex_ai" and uc.vertex_ai_project_id and uc.vertex_ai_credentials_json:
                    project_id = uc.vertex_ai_project_id
                    location = uc.vertex_ai_location or "us-central1"
                    raw = uc.vertex_ai_credentials_json
                    credentials_json = decrypt_data(raw) if is_encrypted(raw) else raw
                    from_db = True
                    logger.info("[Google Service] Try-on using Vertex config from DB for user=%s", user_id or "")
            except Exception as e:
                logger.warning("[Google Service] Vertex config from DB failed: %s", e)

        if not from_db:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
            credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GCP_LOCATION", "us-central1")

        return project_id, location, credentials_json

    @staticmethod
    def _extract_image_url(obj: Any) -> Optional[str]:
        """从 reference_images 条目提取 data URL 或 base64 字符串。"""
        if obj is None:
            return None
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict) and "url" in obj:
            return obj["url"]
        return None

    async def virtual_tryon(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        虚拟试衣 - 委托给 TryOnService，走统一路由 /api/modes/{provider}/virtual-try-on。

        与 GEN/Edit 统一：
        - 认证、凭证由 modes 路由 + ProviderFactory 处理
        - Vertex 配置由本方法解析（用户 VertexAIConfig 或 env）后传入 TryOnService
        - ✅ 当提供 session_id 和 message_id 时，调用 AttachmentService 处理图片
        - ✅ 返回与 GEN 模式一致的 {"images": [...]} 格式

        reference_images: 来自 modes 的 convert_attachments_to_reference_images。
        - raw: 单图即人物图；多图时为 [人物图, 服装图]，顺序固定。

        kwargs 支持的参数:
        - sessionId / frontend_session_id: 会话 ID
        - message_id: 消息 ID（用于关联附件）
        - numberOfImages / number_of_images: 生成图片数量
        - outputMimeType / output_mime_type: 输出格式
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        ref = reference_images or {}
        raw = ref.get("raw")
        person_url = None
        clothing_url = None
        if isinstance(raw, list) and len(raw) >= 2:
            person_url = self._extract_image_url(raw[0])
            clothing_url = self._extract_image_url(raw[1])
        elif isinstance(raw, (str, dict)):
            person_url = self._extract_image_url(raw)
            clothing_url = self._extract_image_url(ref.get("clothing"))
        if not person_url or not clothing_url:
            raise ValueError("Virtual try-on requires two images: person and garment (attachments[0]=person, attachments[1]=garment)")

        project_id, location, credentials_json = self._resolve_vertex_config_for_tryon()
        if not project_id or not credentials_json:
            raise ValueError(
                "Vertex AI not configured for try-on. Set user Vertex AI settings or "
                "GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS_JSON."
            )

        n = max(1, min(4, kwargs.get("numberOfImages") or kwargs.get("number_of_images") or 1))
        mime = kwargs.get("outputMimeType") or kwargs.get("output_mime_type") or "image/jpeg"
        model_id = model or "virtual-try-on-001"
        
        # 从 kwargs 获取新增的官方支持参数
        base_steps = kwargs.get("baseSteps") or kwargs.get("base_steps")
        compression_quality = kwargs.get("outputCompressionQuality") or kwargs.get("output_compression_quality")
        seed = kwargs.get("seed")

        logger.info(
            "[Google Service] Delegating virtual try-on to TryOnService: model=%s, images=%s, base_steps=%s, quality=%s",
            model_id, n, base_steps, compression_quality
        )
        result = self.tryon_service.virtual_tryon(
            person_image_base64=person_url,
            clothing_image_base64=clothing_url,
            number_of_images=n,
            output_mime_type=mime,
            model=model_id,
            project_id=project_id,
            location=location,
            credentials_json=credentials_json,
            base_steps=base_steps,
            output_compression_quality=compression_quality,
            seed=seed,
        )

        if not result.success:
            raise Exception(result.error or "Virtual try-on failed")

        data_url = result.image
        if data_url and not data_url.startswith("data:"):
            data_url = f"data:{result.mime_type};base64,{data_url}"

        # ✅ 与 GEN 模式保持一致：从 kwargs 中获取 session_id 和 message_id
        session_id = kwargs.get("frontend_session_id") or kwargs.get("sessionId")
        message_id = kwargs.get("message_id")
        
        logger.info(f"[Google Service] Virtual try-on result processing: session_id={session_id}, message_id={message_id}")
        
        # ✅ 如果有 session_id 和 message_id，调用 AttachmentService 处理图片（方案 B）
        # 这样做的原因是 modes.py 禁止修改，所以在服务层自行处理附件
        if session_id and message_id and self.db and self.user_id:
            try:
                from ..common.attachment_service import AttachmentService
                attachment_service = AttachmentService(self.db)
                
                # 调用 process_ai_result 创建数据库附件记录和上传任务
                processed = await attachment_service.process_ai_result(
                    ai_url=data_url,
                    mime_type=mime,
                    session_id=session_id,
                    message_id=message_id,
                    user_id=self.user_id,
                    prefix="tryon"
                )
                
                logger.info(f"[Google Service] Virtual try-on attachment processed: attachment_id={processed['attachment_id']}, status={processed['status']}")
                
                # ✅ 返回与 GEN 模式完全一致的 images 数组格式
                return {
                    "images": [{
                        "url": processed["display_url"],
                        "attachment_id": processed["attachment_id"],
                        "upload_status": processed["status"],
                        "task_id": processed["task_id"],
                        "mime_type": mime,
                        "filename": f"tryon-{processed['attachment_id']}.png"
                    }]
                }
            except Exception as e:
                logger.warning(f"[Google Service] AttachmentService processing failed, returning raw result: {e}")
                # 降级：返回原始结果（不入库）
        
        # ✅ 没有 session_id/message_id 时，也返回 images 数组格式（与 GEN 一致）
        # 这样前端可以统一处理 data.images
        return {
            "images": [{
                "url": data_url,
                "mime_type": mime,
                "filename": f"tryon-{model_id}.png"
            }]
        }
    
    # === Mask Preview Service (委托给 SegmentationService) ===

    async def preview_mask(
        self,
        prompt: str,  # 占位参数，mask 预览不需要 prompt
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Preview auto-generated mask - 委托给 SegmentationService

        Args:
            prompt: Placeholder (not used)
            model: Model identifier (default: image-segmentation-001)
            reference_images: Reference images dict (should contain 'raw' image)
            **kwargs: Additional parameters:
                - mask_mode: MASK_MODE_BACKGROUND, MASK_MODE_FOREGROUND, or MASK_MODE_SEMANTIC
                - mask_dilation: Mask dilation factor (0.0-1.0)

        Returns:
            Dict with mask preview data
        """
        # 从 reference_images 中提取原图
        image_base64 = None
        if reference_images:
            raw_data = reference_images.get("raw")
            if raw_data:
                if isinstance(raw_data, dict):
                    raw_data = raw_data.get("url") or raw_data.get("data")
                if isinstance(raw_data, str):
                    if raw_data.startswith("data:"):
                        image_base64 = raw_data.split(",", 1)[1] if "," in raw_data else raw_data
                    else:
                        image_base64 = raw_data
        if not image_base64:
            image_base64 = kwargs.get("image_base64")

        if not image_base64:
            return {"success": False, "error": "preview_mask requires 'raw' image in reference_images"}

        # 获取 mask 模式并转换为 segmentation 模式
        mask_mode = kwargs.get("mask_mode", kwargs.get("maskMode", "MASK_MODE_FOREGROUND"))
        mode_mapping = {
            "MASK_MODE_FOREGROUND": "FOREGROUND",
            "MASK_MODE_BACKGROUND": "BACKGROUND",
            "MASK_MODE_SEMANTIC": "SEMANTIC",
        }
        segment_mode = mode_mapping.get(mask_mode, "FOREGROUND")

        # 语义分割需要 prompt
        segment_prompt = None
        if segment_mode == "SEMANTIC":
            segment_prompt = kwargs.get("segmentation_prompt", "person")

        logger.info(f"[Google Service] preview_mask: mask_mode={mask_mode} → segment_mode={segment_mode}")

        # 调用 SegmentationService
        try:
            result = self.segmentation_service.segment_image(
                image_base64=image_base64,
                mode=segment_mode,
                prompt=segment_prompt,
                model=model if model != "imagen-3.0-capability-001" else "image-segmentation-001",
                mask_dilation=kwargs.get("mask_dilation", kwargs.get("maskDilation", 0.02)),
            )
        except Exception as e:
            logger.error(f"[Google Service] preview_mask: SegmentationService error: {e}")
            return {"success": False, "error": f"SegmentationService error: {str(e)}"}

        if result.success and result.masks:
            return {
                "success": True,
                "masks": [
                    {
                        "url": f"data:image/png;base64,{m.mask}",
                        "mime_type": "image/png",
                        "labels": [{"label": l.label, "score": l.score} for l in m.labels]
                    }
                    for m in result.masks
                ]
            }
        else:
            return {"success": False, "error": result.error or "No mask generated"}

    # === Clothing Segmentation Service ===

    async def segment_clothing(
        self,
        prompt: str,  # 占位参数，segment-clothing 不需要 prompt
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Segment clothing in an image using Gemini API - 委托给 TryOnService
        
        Args:
            prompt: Placeholder (not used for segmentation)
            model: Gemini model ID (default: "gemini-2.0-flash-exp")
            reference_images: Reference images dict (should contain image data)
            **kwargs: Additional parameters:
                - image_base64: Base64 encoded image (from reference_images or kwargs)
                - target_clothing: Target clothing type (e.g., "upper body clothing")
                - api_key: Gemini API Key (optional, will use self.api_key if not provided)
        
        Returns:
            Dict with segmentation results
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()
        
        # 从 reference_images 或 kwargs 中提取图像
        image_base64 = None
        if reference_images:
            image_base64 = reference_images.get("raw")
        if not image_base64:
            image_base64 = kwargs.get("image_base64")
        
        if not image_base64:
            raise ValueError("segment_clothing requires 'raw' image in reference_images or 'image_base64' in kwargs")
        
        target_clothing = kwargs.get("target_clothing", "upper body clothing")
        
        logger.info(f"[Google Service] Delegating clothing segmentation to TryOnService: target={target_clothing}")
        
        # 传递 api_key（如果未提供，使用 self.api_key）
        if 'api_key' not in kwargs:
            kwargs['api_key'] = self.api_key
        
        result = await self.tryon_service.segment_clothing(
            image_base64=image_base64,
            target_clothing=target_clothing,
            model=model,
            **kwargs
        )
        
        return result
    
    async def multi_agent(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Legacy Google runtime multi-agent compatibility adapter.

        Args:
            prompt: Task description
            model: Model identifier (metadata only, preserved for compatibility)
            **kwargs: Additional parameters:
                - agent_ids: List of agent IDs to use
                - mode: Legacy mode hint. Only ``default`` is supported here.

        Returns:
            Legacy orchestration result with compatibility metadata.

        Notes:
            - This helper is Google runtime specific and is not provider-neutral.
            - The unified entrypoint for new integrations is
              ``POST /api/modes/{provider}/multi-agent``.
            - Explicit legacy orchestration variants should continue to use the
              deprecated ``/api/multi-agent/orchestrate`` compatibility route.
        """
        mode = str(kwargs.get("mode") or "default").strip() or "default"
        if mode != "default":
            raise ValueError(
                "GoogleService.multi_agent only preserves legacy default orchestration. "
                "Use `/api/modes/{provider}/multi-agent` for provider-neutral execution "
                "or the deprecated `/api/multi-agent/orchestrate` compatibility route "
                "for explicit Google runtime modes."
            )

        from .agent.orchestrator import Orchestrator

        orchestrator = Orchestrator(
            db=self.db,
            google_service=self,
            use_smart_decomposition=True
        )

        logger.warning(
            "[Google Service] multi_agent() is a legacy Google runtime compatibility "
            "adapter; prefer POST /api/modes/{provider}/multi-agent"
        )
        result = await orchestrator.orchestrate(
            user_id=self.user_id or "default",
            task=prompt,
            agent_ids=kwargs.get("agent_ids"),
        )
        return _attach_legacy_multi_agent_service_meta(
            result,
            mode=mode,
            model=model,
        )

    def tryon_upscale(
        self,
        image_base64: str,
        upscale_factor: int = 2,
        add_watermark: bool = False
    ):
        """
        Upscale image using Imagen 4 (via TryOnService).

        This is different from upscale_image() which uses UpscaleService with file paths.
        This method accepts base64 encoded images directly.

        Args:
            image_base64: Base64 encoded image
            upscale_factor: Upscale factor (2 or 4)
            add_watermark: Whether to add watermark

        Returns:
            TryOnResult with success status and result image
        """
        if self.use_official_sdk:
            self._ensure_legacy_feature_services()

        logger.info(f"[Google Service] Delegating tryon upscale to TryOnService: factor={upscale_factor}x")
        return self.tryon_service.upscale_image(
            image_base64=image_base64,
            upscale_factor=upscale_factor,
            add_watermark=add_watermark
        )

    # === Imagen Configuration Service ===

    def get_imagen_capabilities(self) -> Dict[str, Any]:
        """
        Get Imagen API capabilities for the current configuration.

        Delegates to ImageGenerator.get_capabilities() which uses ImagenCoordinator
        to determine capabilities based on the user's API mode (Gemini API or Vertex AI).

        Returns:
            Dictionary containing:
            - supported_models: List of supported model IDs (required)
            - max_images: Maximum number of images per request (required)
            - supported_aspect_ratios: List of supported aspect ratios (required)
            - person_generation_modes: Supported person generation modes (required)
            - etc.
        """
        if self.use_official_sdk:
            # Return basic capabilities for official SDK mode
            return {
                "supported_models": ["imagen-3.0-generate-001"],
                "max_images": 8,
                "supported_aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
                "person_generation_modes": ["dont_allow", "allow_adult"]
            }

        logger.info("[Google Service] Getting Imagen capabilities via ImageGenerator")
        capabilities = self.image_generator.get_capabilities()
        
        # Ensure all required fields are present and standardized
        if 'supported_models' not in capabilities:
            # Try to get from image_generator if available
            if hasattr(self.image_generator, 'get_supported_models'):
                try:
                    capabilities['supported_models'] = self.image_generator.get_supported_models()
                except Exception as e:
                    logger.warning(f"[Google Service] Failed to get supported_models: {e}")
                    capabilities['supported_models'] = []
            else:
                capabilities['supported_models'] = []
        
        # Ensure supported_aspect_ratios field exists (standardize from aspect_ratios)
        if 'supported_aspect_ratios' not in capabilities:
            if 'aspect_ratios' in capabilities:
                capabilities['supported_aspect_ratios'] = capabilities['aspect_ratios']
            else:
                capabilities['supported_aspect_ratios'] = ["1:1", "3:4", "4:3", "9:16", "16:9"]
        
        # Ensure person_generation_modes field exists
        if 'person_generation_modes' not in capabilities:
            capabilities['person_generation_modes'] = ['dont_allow', 'allow_adult']
        
        return capabilities

    def get_imagen_api_mode(self) -> str:
        """
        Get the current Imagen API mode (gemini_api or vertex_ai).

        Returns:
            API mode string ('gemini_api' or 'vertex_ai')
        """
        if self.use_official_sdk:
            return "official_sdk"

        return self.image_generator.get_current_api_mode()
