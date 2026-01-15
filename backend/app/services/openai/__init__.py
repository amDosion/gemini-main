"""
OpenAI 服务模块

架构说明：
- OpenAIService: 主协调器，统一入口（通过 ProviderFactory.create("openai") 获取）
- 所有子服务由 OpenAIService 协调，不应直接调用

子服务（由 OpenAIService 委托）：
- ChatHandler: 聊天服务
- ImageGenerator: 图像生成服务 (DALL-E)
- SpeechGenerator: 语音合成服务 (TTS)
- ModelManager: 模型管理服务

Updated: 2026-01-14 - 创建模块结构，统一架构
"""

from .openai_service import OpenAIService
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .speech_generator import SpeechGenerator
from .model_manager import ModelManager

__all__ = [
    # Main Coordinator
    "OpenAIService",
    # Sub-services (for direct access if needed)
    "ChatHandler",
    "ImageGenerator",
    "SpeechGenerator",
    "ModelManager",
]
