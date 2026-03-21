"""
Ollama 本地模型服务模块

提供 Ollama 本地模型的聊天、向量化、模型管理等功能
"""

from .ollama import (
    OllamaService,
)
from ..common.errors import (
    APIKeyError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError,
    OperationError,
)
from .ollama_types import (
    OllamaAPIMode,
    OllamaModelCapabilities,
    OllamaModelInfo,
    OllamaToolCallState,
)

__all__ = [
    # 服务类
    "OllamaService",
    # 异常类
    "OperationError",
    "APIKeyError",
    "RateLimitError",
    "ModelNotFoundError",
    "InvalidRequestError",
    # 类型定义
    "OllamaAPIMode",
    "OllamaModelCapabilities",
    "OllamaModelInfo",
    "OllamaToolCallState",
]
