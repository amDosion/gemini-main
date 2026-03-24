"""
Grok Provider Service - Main Coordinator

This module implements the Grok provider service as a coordinator that delegates
to specialized sub-services:
- ChatHandler: Chat operations (via AsyncOpenAI, OpenAI-compatible)
- ImageGenerator: Image generation (grok-imagine-1.0)
- ImageEditor: Image editing (grok-imagine-1.0-edit)
- VideoGenerator: Video generation (grok-imagine-1.0-video)
- ModelManager: Model listing

架构说明：
- GrokService 作为协调者，仅负责请求分发，不包含业务逻辑
- 聊天使用 AsyncOpenAI（grok2api 提供 OpenAI 兼容接口）
- 图片/视频使用 httpx（自定义参数和端点）
- 所有子服务延迟加载，避免循环导入和减少初始化开销
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI

from ..common.base_provider import BaseProviderService
from ..common.model_capabilities import ModelConfig

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/v1"


class GrokService(BaseProviderService):
    """
    Grok Provider Service - Main Coordinator

    This service coordinates all Grok operations by delegating to:
    - ChatHandler: Chat operations (streaming and non-streaming)
    - ImageGenerator: Image generation (grok-imagine-1.0)
    - ImageEditor: Image editing (grok-imagine-1.0-edit)
    - VideoGenerator: Video generation (grok-imagine-1.0-video)
    - ModelManager: Model listing

    Uses the coordinator/delegation pattern for consistency with other providers.
    """

    def __init__(self, api_key: str, api_url: Optional[str] = None, **kwargs):
        """
        Initialize Grok service coordinator.

        Args:
            api_key: API key for grok2api authentication
            api_url: Custom API URL (default: http://localhost:8000/v1)
            **kwargs: Additional parameters:
                - timeout (float): Request timeout in seconds (default: 120.0)
                - max_retries (int): Maximum number of retries (default: 3)
        """
        super().__init__(api_key, api_url, **kwargs)

        self.base_url = api_url or DEFAULT_BASE_URL
        self.timeout = kwargs.get("timeout", 120.0)
        self.max_retries = kwargs.get("max_retries", 3)

        # Create shared AsyncOpenAI client (used for chat operations)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

        # 子服务延迟加载
        self._chat_handler = None
        self._image_generator = None
        self._image_editor = None
        self._video_generator = None
        self._model_manager = None

        logger.info(f"[Grok Service] Coordinator initialized with base_url={self.base_url}")

    @property
    def chat_handler(self):
        """Lazy load ChatHandler."""
        if self._chat_handler is None:
            from .chat_handler import ChatHandler
            self._chat_handler = ChatHandler(self.client)
        return self._chat_handler

    @property
    def image_generator(self):
        """Lazy load ImageGenerator."""
        if self._image_generator is None:
            from .image_generator import ImageGenerator
            self._image_generator = ImageGenerator(
                self.api_key,
                self.base_url,
                timeout=self.timeout,
            )
        return self._image_generator

    @property
    def image_editor(self):
        """Lazy load ImageEditor."""
        if self._image_editor is None:
            from .image_editor import ImageEditor
            self._image_editor = ImageEditor(
                self.api_key,
                self.base_url,
                timeout=self.timeout,
            )
        return self._image_editor

    @property
    def video_generator(self):
        """Lazy load VideoGenerator."""
        if self._video_generator is None:
            from .video_generator import VideoGenerator
            self._video_generator = VideoGenerator(
                self.api_key,
                self.base_url,
                timeout=max(self.timeout, 600.0),  # Video gen needs longer timeout
            )
        return self._video_generator

    @property
    def model_manager(self):
        """Lazy load ModelManager."""
        if self._model_manager is None:
            from .model_manager import ModelManager
            self._model_manager = ModelManager(
                self.api_key,
                self.base_url,
            )
        return self._model_manager

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
            'Grok'
        """
        return "Grok"

    # ==================== Image Generation ====================

    async def generate_image(
        self,
        prompt: str,
        model: str = "grok-imagine-1.0",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        生成图片 - 委托给 ImageGenerator

        Args:
            prompt: 图片描述文本
            model: 使用的模型 ('grok-imagine-1.0')
            **kwargs: 额外参数

        Returns:
            图片结果列表（统一格式）
        """
        # Route to image editor if edit model
        if "edit" in str(model or "").lower():
            return await self.image_editor.edit_image(prompt, model, **kwargs)
        return await self.image_generator.generate_image(prompt, model, **kwargs)

    # ==================== Video Generation ====================

    async def generate_video(
        self,
        prompt: str,
        model: str = "grok-imagine-1.0-video",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成视频 - 委托给 VideoGenerator

        Args:
            prompt: 视频描述文本
            model: 使用的模型 ('grok-imagine-1.0-video')
            **kwargs: 额外参数

        Returns:
            包含 url/mime_type/filename 等字段的统一视频结果
        """
        return await self.video_generator.generate_video(prompt, model, **kwargs)
