"""
通义服务模块 - DashScope SDK 实现

架构说明：
- TongyiService: 主协调器，统一入口（通过 ProviderFactory.create("tongyi") 获取）
- 所有子服务由 TongyiService 协调，不应直接调用

子服务（由 TongyiService 委托）：
- QwenNativeProvider: 聊天服务
- ImageGenerationService: 图片生成服务
- ImageEditService: 图片编辑服务
- ImageExpandService: 图片扩展服务
- ModelManager: 模型管理服务

Updated: 2026-01-14 - 移除 TongyiImageService 中间层
"""

from .tongyi_service import TongyiService
from .base import (
    DASHSCOPE_BASE_URL,
    get_endpoint,
    get_pixel_resolution,
    Z_IMAGE_RESOLUTIONS,
    WAN_V2_RESOLUTIONS,
    QWEN_RESOLUTIONS,
)
from .chat import (
    QwenNativeProvider,
    is_vision_model,
    VISION_MODELS,
)
from .image_generation import (
    ImageGenerationService,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from .image_edit import (
    ImageEditService,
    ImageEditResult,
    ImageEditOptions,
)
from .image_expand import (
    ImageExpandService,
    OutPaintingResult,
    image_expand_service,
)
from .file_upload import (
    upload_to_dashscope,
    upload_bytes_to_dashscope,
    DashScopeUploadResult,
)

__all__ = [
    # Main Coordinator
    "TongyiService",
    # Base
    "DASHSCOPE_BASE_URL",
    "get_endpoint",
    "get_pixel_resolution",
    "Z_IMAGE_RESOLUTIONS",
    "WAN_V2_RESOLUTIONS",
    "QWEN_RESOLUTIONS",
    # Chat Service
    "QwenNativeProvider",
    "is_vision_model",
    "VISION_MODELS",
    # Image Generation
    "ImageGenerationService",
    "ImageGenerationRequest",
    "ImageGenerationResult",
    # Image Edit
    "ImageEditService",
    "ImageEditResult",
    "ImageEditOptions",
    # Image Expand
    "ImageExpandService",
    "OutPaintingResult",
    "image_expand_service",
    # File Upload
    "upload_to_dashscope",
    "upload_bytes_to_dashscope",
    "DashScopeUploadResult",
]
