"""
OpenAI Provider Service - Main Coordinator

This module implements the OpenAI provider service as a coordinator that delegates
to specialized sub-services:
- ChatHandler: Chat operations
- ImageGenerator: Image generation (DALL-E)
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

logger = logging.getLogger(__name__)


class OpenAIService(BaseProviderService):
    """
    OpenAI Provider Service - Main Coordinator

    This service coordinates all OpenAI operations by delegating to:
    - ChatHandler: Chat operations (streaming and non-streaming)
    - ImageGenerator: Image generation (DALL-E)
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

        # Create shared AsyncOpenAI client (used by all sub-services)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_url or "https://api.openai.com/v1",
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3)
        )

        # 子服务延迟加载（避免循环导入和减少初始化开销）
        self._chat_handler = None
        self._image_generator = None
        self._speech_generator = None
        self._model_manager = None

        logger.info(f"[OpenAI Service] Coordinator initialized with base_url={api_url or 'default'}")

    @property
    def chat_handler(self):
        """Lazy load ChatHandler."""
        if self._chat_handler is None:
            from .chat_handler import ChatHandler
            self._chat_handler = ChatHandler(self.api_key, self.api_url)
        return self._chat_handler

    @property
    def image_generator(self):
        """Lazy load ImageGenerator."""
        if self._image_generator is None:
            from .image_generator import ImageGenerator
            self._image_generator = ImageGenerator(self.api_key, self.api_url)
        return self._image_generator

    @property
    def speech_generator(self):
        """Lazy load SpeechGenerator."""
        if self._speech_generator is None:
            from .speech_generator import SpeechGenerator
            self._speech_generator = SpeechGenerator(self.api_key, self.api_url)
        return self._speech_generator

    @property
    def model_manager(self):
        """Lazy load ModelManager."""
        if self._model_manager is None:
            from .model_manager import ModelManager
            self._model_manager = ModelManager(self.client)
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
            'OpenAI'
        """
        return "OpenAI"

    # ==================== Image Generation ====================

    async def generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        生成图片 - 委托给 ImageGenerator

        Args:
            prompt: 图片描述文本
            model: 使用的模型 ('dall-e-2' 或 'dall-e-3')
            **kwargs: 额外参数

        Returns:
            图片结果列表（统一格式）
        """
        return await self.image_generator.generate_image(prompt, model, **kwargs)

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
            包含 audio 和 format 的字典
        """
        return await self.speech_generator.generate_speech(text, voice, **kwargs)
