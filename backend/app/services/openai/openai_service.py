"""
OpenAI Provider Service - Main Coordinator

This module implements the OpenAI provider service as a coordinator that delegates
to specialized sub-services:
- ChatHandler: Chat operations
- ImageGenerator: Image generation (GPT Image)
- ImageEditor: Image editing / image-to-image (GPT Image)
- VideoGenerator: Video generation (Sora)
- SpeechGenerator: Speech synthesis (TTS)
- ModelManager: Model listing

架构说明：
- OpenAIService 作为协调者，仅负责请求分发，不包含业务逻辑
- 所有子服务延迟加载，避免循环导入和减少初始化开销
- 遵循"路由与逻辑分离"架构原则

Updated: 2026-01-14 - 移动到 openai/ 目录，统一架构
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI

from ..common.base_provider import BaseProviderService
from ..common.model_capabilities import ModelConfig
from ._shared import coerce_openai_image_max_retries, coerce_openai_image_timeout
from .image_route_contract import (
    OpenAIImageRoute,
    select_image_edit_route,
    select_image_generation_route,
)

logger = logging.getLogger(__name__)


class OpenAIService(BaseProviderService):
    """
    OpenAI Provider Service - Main Coordinator

    This service coordinates all OpenAI operations by delegating to:
    - ChatHandler: Chat operations (streaming and non-streaming)
    - ImageGenerator: Image generation (GPT Image)
    - SpeechGenerator: Speech synthesis (TTS)
    - ModelManager: Model listing

    Uses the coordinator/delegation pattern for consistency with other providers.
    """

    def __init__(self, api_key: str, api_url: Optional[str] = None, **kwargs):
        """
        Initialize OpenAI service coordinator.

        Args:
            api_key: OpenAI API key
            api_url: Optional custom API URL (for OpenAI-compatible APIs)
            **kwargs: Additional parameters:
                - timeout (float): Request timeout in seconds (default: 120.0)
                - max_retries (int): Maximum number of retries (default: 3)
        """
        super().__init__(api_key, api_url, **kwargs)

        self.user_id = kwargs.get("user_id")
        self.db = kwargs.get("db")
        self.timeout = kwargs.get("timeout", 120.0)
        self.max_retries = kwargs.get("max_retries", 3)
        self.image_timeout = coerce_openai_image_timeout(kwargs.get("image_timeout"))
        self.image_max_retries = coerce_openai_image_max_retries(kwargs.get("image_max_retries"))

        # Create shared AsyncOpenAI client (used by all sub-services)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_url or "https://api.openai.com/v1",
            timeout=self.timeout,
            max_retries=self.max_retries
        )

        # 子服务延迟加载（避免循环导入和减少初始化开销）
        self._chat_handler = None
        self._image_generator = None
        self._image_editor = None
        self._responses_image = None
        self._video_generator = None
        self._speech_generator = None
        self._model_manager = None
        self._pdf_extractor = None

        logger.info(f"[OpenAI Service] Coordinator initialized with base_url={api_url or 'default'}")

    @property
    def chat_handler(self):
        """Lazy load ChatHandler."""
        if self._chat_handler is None:
            from .chat_handler import ChatHandler
            self._chat_handler = ChatHandler(
                self.api_key,
                self.api_url,
                client=self.client,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._chat_handler

    @property
    def image_generator(self):
        """Lazy load ImageGenerator."""
        if self._image_generator is None:
            from .image_generator import ImageGenerator
            self._image_generator = ImageGenerator(
                self.api_key,
                self.api_url,
                client=self.client,
                timeout=self.timeout,
                max_retries=self.max_retries,
                image_timeout=self.image_timeout,
                image_max_retries=self.image_max_retries,
            )
        return self._image_generator

    @property
    def image_editor(self):
        """Lazy load ImageEditor."""
        if self._image_editor is None:
            from .image_editor import ImageEditor
            self._image_editor = ImageEditor(
                self.api_key,
                self.api_url,
                client=self.client,
                timeout=self.timeout,
                max_retries=self.max_retries,
                image_timeout=self.image_timeout,
                image_max_retries=self.image_max_retries,
            )
        return self._image_editor

    @property
    def responses_image(self):
        """Lazy load ResponsesImageService."""
        if self._responses_image is None:
            from .responses_image import ResponsesImageService
            self._responses_image = ResponsesImageService(
                self.api_key,
                self.api_url,
                client=self.client,
                timeout=self.timeout,
                max_retries=self.max_retries,
                image_editor=self.image_editor,
            )
        return self._responses_image

    @property
    def speech_generator(self):
        """Lazy load SpeechGenerator."""
        if self._speech_generator is None:
            from .speech_generator import SpeechGenerator
            self._speech_generator = SpeechGenerator(
                self.api_key,
                self.api_url,
                client=self.client,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._speech_generator

    @property
    def video_generator(self):
        """Lazy load VideoGenerator."""
        if self._video_generator is None:
            from .video_generator import VideoGenerator
            self._video_generator = VideoGenerator(
                self.api_key,
                self.api_url,
                user_id=self.user_id,
                db=self.db,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._video_generator

    @property
    def model_manager(self):
        """Lazy load ModelManager."""
        if self._model_manager is None:
            from .model_manager import ModelManager
            self._model_manager = ModelManager(self.client)
        return self._model_manager

    @property
    def pdf_extractor(self):
        """Lazy load OpenAI PDF extractor."""
        if self._pdf_extractor is None:
            from .pdf_extractor import OpenAIPDFExtractor
            self._pdf_extractor = OpenAIPDFExtractor(
                self.api_key,
                self.api_url,
                client=self.client,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._pdf_extractor

    # ==================== Chat Operations ====================

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送聊天请求并获取完整响应（非流式）- 委托给 ChatHandler

        Args:
            messages: 消息列表
            model: 模型标识符
            **kwargs: 额外参数

        Returns:
            聊天响应字典
        """
        return await self.chat_handler.chat(messages, model, **kwargs)

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        发送聊天请求并流式返回响应 - 委托给 ChatHandler

        Args:
            messages: 消息列表
            model: 模型标识符
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        async for chunk in self.chat_handler.stream_chat(messages, model, **kwargs):
            yield chunk

    # ==================== Model Management ====================

    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表 - 委托给 ModelManager

        Returns:
            ModelConfig 对象列表
        """
        return await self.model_manager.get_available_models()

    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            'OpenAI'
        """
        return "OpenAI"

    # ==================== Image Generation ====================

    async def generate_image(
        self,
        prompt: str,
        model: str = "gpt-image-2",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        生成图片 - 委托给 ImageGenerator

        Args:
            prompt: 图片描述文本
            model: 使用的模型，默认使用 GPT Image 2
            **kwargs: 额外参数

        Returns:
            图片结果列表（统一格式）
        """
        route = select_image_generation_route(kwargs)
        if route == OpenAIImageRoute.RESPONSES_IMAGE_GENERATION:
            return await self.responses_image.generate_image(
                prompt,
                image_model=model,
                **kwargs,
            )
        return await self.image_generator.generate_image(prompt, model, **kwargs)

    async def edit_image(
        self,
        prompt: str,
        model: str = "gpt-image-2",
        reference_images: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        编辑图片 - 委托给 ImageEditor

        与 GoogleService 保持同一层级的 provider 分发契约：
        core/modes.py 只根据 mode 调用 provider.edit_image()；
        OpenAIService 再把 GPT Image 的图生图请求委托给 ImageEditor。
        """
        route = select_image_edit_route(mode, kwargs)
        if route == OpenAIImageRoute.RESPONSES_IMAGE_EDIT:
            return await self.responses_image.edit_image(
                prompt=prompt,
                image_model=model,
                reference_images=reference_images or {},
                mode=mode,
                **kwargs,
            )
        return await self.image_editor.edit_image(
            prompt=prompt,
            model=model,
            reference_images=reference_images or {},
            mode=mode,
            **kwargs,
        )

    async def expand_image(
        self,
        prompt: str = "",
        model: str = "gpt-image-2",
        reference_images: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        OpenAI prompt-driven image extension.

        The global mode catalog routes `image-outpainting` to `expand_image`.
        OpenAI does not expose the Vertex-style ratio/offset/upscale contract,
        so the provider implementation maps this mode to GPT Image edit with a
        clear extension prompt and the existing reference image.
        """
        effective_prompt = (prompt or "").strip() or self._default_expand_prompt(mode, kwargs)
        route = select_image_edit_route("image-outpainting", kwargs)
        if route == OpenAIImageRoute.RESPONSES_IMAGE_EDIT:
            return await self.responses_image.edit_image(
                prompt=effective_prompt,
                image_model=model,
                reference_images=reference_images or {},
                mode="image-outpainting",
                **kwargs,
            )
        return await self.image_editor.edit_image(
            prompt=effective_prompt,
            model=model,
            reference_images=reference_images or {},
            mode="image-outpainting",
            **kwargs,
        )

    async def virtual_tryon(
        self,
        prompt: str = "",
        model: str = "gpt-image-2",
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        OpenAI virtual try-on as a multi-reference GPT Image edit.

        Attachment order follows the existing app contract:
        reference_images.raw[0] = person image, reference_images.raw[1] = garment image.
        """
        effective_prompt = (prompt or "").strip() or (
            "Edit the first image to make the person wear the garment from the second image. "
            "Preserve the person's identity, pose, body shape, lighting direction, and the "
            "garment's color, texture, logo placement, seams, and proportions. Return a "
            "realistic product try-on image with no added text or watermark."
        )
        route = select_image_edit_route("virtual-try-on", kwargs)
        if route == OpenAIImageRoute.RESPONSES_IMAGE_EDIT:
            return await self.responses_image.edit_image(
                prompt=effective_prompt,
                image_model=model,
                reference_images=reference_images or {},
                mode="virtual-try-on",
                **kwargs,
            )
        return await self.image_editor.edit_image(
            prompt=effective_prompt,
            model=model,
            reference_images=reference_images or {},
            mode="virtual-try-on",
            **kwargs,
        )

    async def extract_pdf_data(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Extract structured data from PDFs through OpenAI Responses file input."""
        return await self.pdf_extractor.extract_pdf_data(
            prompt=prompt,
            model=model,
            reference_images=reference_images or {},
            **kwargs,
        )

    def _default_expand_prompt(self, mode: Optional[str], params: Dict[str, Any]) -> str:
        normalized_mode = str(mode or params.get("outpaint_mode") or "").strip().lower()
        if normalized_mode == "upscale":
            factor = str(params.get("upscale_factor") or "").strip() or "the requested factor"
            return (
                f"Improve and enlarge the input image to {factor} resolution while preserving "
                "the subject, composition, edges, material details, and lighting. Do not add text or watermark."
            )
        if normalized_mode == "offset":
            return (
                "Extend the canvas naturally in the requested directions. Preserve the original image "
                "content exactly and synthesize only coherent surrounding context with matching perspective and lighting."
            )
        if normalized_mode == "scale":
            return (
                "Expand the canvas naturally around the original image while preserving the subject and "
                "composition. Fill the new areas with coherent scene context matching perspective, lighting, and style."
            )
        target_ratio = params.get("output_ratio") or params.get("aspect_ratio") or params.get("image_aspect_ratio")
        if target_ratio:
            return (
                f"Extend the image naturally to a {target_ratio} composition. Preserve the original subject and "
                "details, and fill the new canvas areas with coherent background matching perspective and lighting."
            )
        return (
            "Extend the image naturally while preserving the original subject, details, perspective, and lighting. "
            "Fill only the surrounding canvas with coherent context and do not add text or watermark."
        )

    # ==================== Video Generation ====================

    async def generate_video(
        self,
        prompt: str,
        model: str = "sora-2",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成视频 - 委托给 VideoGenerator

        Args:
            prompt: 视频描述文本
            model: 使用的模型 ('sora-2' 或 'sora-2-pro')
            **kwargs: 额外参数

        Returns:
            包含 url/mime_type/filename 等字段的统一视频结果
        """
        return await self.video_generator.generate_video(prompt, model, **kwargs)

    # ==================== Speech Generation ====================

    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成语音 - 委托给 SpeechGenerator

        Args:
            text: 要转换的文本
            voice: 使用的语音
            **kwargs: 额外参数

        Returns:
            包含 url/mime_type/format 的字典
        """
        return await self.speech_generator.generate_speech(text, voice, **kwargs)
