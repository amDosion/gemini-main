"""
Gemini Service Module (重构版)

统一的 Google Gemini/Vertex AI 服务模块。

说明：
- 本包提供 Google/Gemini provider 实现及其相关子服务导出。
- provider-neutral 的 Multi-Agent 主入口不在这里，而是
  `POST /api/modes/{provider}/multi-agent`。
- `GoogleService.multi_agent()` 仅保留为 legacy Google runtime 兼容 helper。

目录结构:
├── client_pool.py          # 统一客户端池
├── google_service.py       # 主服务入口
│
├── vertexai/               # Vertex AI 专用服务 (需要 GCP 凭证)
│   ├── vertex_edit_base.py       # 编辑服务共享基类
│   ├── inpainting_service.py     # 图像修复
│   ├── background_edit_service.py # 背景编辑
│   ├── recontext_service.py      # 重新上下文
│   ├── mask_edit_service.py      # 掩码编辑
│   ├── tryon_service.py          # 虚拟试穿
│   ├── segmentation_service.py   # 图片分割
│   └── expand_service.py         # 图像扩展/放大 (包含 outpaint 和 upscale)
│
├── geminiapi/              # Gemini API 专用服务 (只需 API Key)
│   ├── imagen_gemini_api.py
│   └── conversational_image_edit_service.py
│
├── common/                 # 公共模块
├── base/                   # 基类
├── coordinators/           # 协调器
└── docs/                   # 文档

使用方式:
    # Vertex AI 服务
    from .vertexai import tryon_service, segmentation_service, ExpandService

    # Gemini API 服务
    from .geminiapi import imagen_gemini_api

    # 统一客户端池
    from .client_pool import get_client_pool

注意: upscale_service 已整合到 expand_service 中
"""

PROVIDER_NEUTRAL_MULTI_AGENT_ENTRYPOINT = "/api/modes/{provider}/multi-agent"
LEGACY_GOOGLE_RUNTIME_HELPERS = (
    "GoogleService.multi_agent",
)

# ==================== 主服务 ====================
from .google_service import GoogleService
from .client_pool import GeminiClientPool, get_client_pool

# ==================== 公共模块 ====================
from .common.file_handler import FileHandler
from .common.function_handler import FunctionHandler, FunctionCallingMode
from .common.schema_handler import SchemaHandler, CommonSchemas
from .common.token_handler import TokenHandler, TokenCount, ModelPricing, ModelLimits
from .common.mode_registry import GoogleModeRegistry, get_global_registry, ModeHandler
from .common.mode_initialization import initialize_google_modes, get_registered_modes

# ==================== Vertex AI 服务 ====================
from .vertexai import (
    VertexAIEditBase,
    InpaintingService,
    BackgroundEditService,
    RecontextService,
    MaskEditService,
    EditResult,
    TryOnService,
    TryOnResult,
    tryon_service,
    SegmentationService,
    SegmentResult,
    segmentation_service,
    ExpandService,
)

__all__ = [
    # Multi-Agent entrypoint contract
    'PROVIDER_NEUTRAL_MULTI_AGENT_ENTRYPOINT',
    'LEGACY_GOOGLE_RUNTIME_HELPERS',

    # 主服务
    'GoogleService',
    'GeminiClientPool',
    'get_client_pool',

    # 公共模块
    'FileHandler',
    'FunctionHandler',
    'FunctionCallingMode',
    'SchemaHandler',
    'CommonSchemas',
    'TokenHandler',
    'TokenCount',
    'ModelPricing',
    'ModelLimits',
    'GoogleModeRegistry',
    'get_global_registry',
    'ModeHandler',
    'initialize_google_modes',
    'get_registered_modes',

    # Vertex AI 编辑服务
    'VertexAIEditBase',
    'InpaintingService',
    'BackgroundEditService',
    'RecontextService',
    'MaskEditService',
    'EditResult',

    # Vertex AI 其他服务
    'TryOnService',
    'TryOnResult',
    'tryon_service',
    'SegmentationService',
    'SegmentResult',
    'segmentation_service',
    'ExpandService',
]
