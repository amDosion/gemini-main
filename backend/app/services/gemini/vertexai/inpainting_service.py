"""
Inpainting Service (图像修复服务)

使用 Vertex AI edit_image API 进行图像修复（插入/移除内容）。
默认编辑模式: EDIT_MODE_INPAINT_INSERTION

路由: image-inpainting → ImageEditCoordinator → InpaintingService.edit_image()
"""

import logging
from typing import Dict, Any, List, Optional

from .vertex_edit_base import VertexAIEditBase

logger = logging.getLogger(__name__)


class InpaintingService(VertexAIEditBase):
    """
    图像修复服务

    继承 VertexAIEditBase，预设 edit_mode 为 'inpainting'（EDIT_MODE_INPAINT_INSERTION）。
    支持通过 config 中的 edit_mode 覆盖默认值（如 'inpainting-remove'）。

    构造函数: __init__(project_id, location, credentials_json)
    接口: edit_image(prompt, reference_images, config) -> List[Dict[str, Any]]
    """

    DEFAULT_EDIT_MODE = 'inpainting'
