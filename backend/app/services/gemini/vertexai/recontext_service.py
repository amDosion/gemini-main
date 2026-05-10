"""
Recontext Service (重新上下文服务)

Legacy Vertex Imagen edit_image recontext wrapper.

当前 UI 的 image-recontext / product-recontext 已按官方迁移方向使用
gemini-2.5-flash-image 原生图片编辑。这个类仅保留给旧调用方或显式
Imagen edit 实验路径，不代表当前 Recontext 模式的主路由。
"""

import logging
from typing import Dict, Any, List, Optional

from .vertex_edit_base import VertexAIEditBase

logger = logging.getLogger(__name__)


class RecontextService(VertexAIEditBase):
    """
    旧 Imagen 重新上下文服务

    继承 VertexAIEditBase，预设 edit_mode 为 'recontext'（EDIT_MODE_INPAINT_INSERTION）。
    当前 Background 模式使用 BackgroundEditService；当前 Recontext 模式使用
    GeminiRecontextImageService。

    构造函数: __init__(project_id, location, credentials_json)
    接口: edit_image(prompt, reference_images, config) -> List[Dict[str, Any]]
    """

    DEFAULT_EDIT_MODE = 'recontext'
