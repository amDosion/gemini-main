"""
Recontext Service (重新上下文服务)

使用 Vertex AI edit_image API 进行图像重新上下文化。
默认编辑模式: EDIT_MODE_INPAINT_INSERTION (recontext 使用 inpaint insertion 模式)

路由: image-recontext → ImageEditCoordinator → RecontextService.edit_image()
"""

import logging
from typing import Dict, Any, List, Optional

from .vertex_edit_base import VertexAIEditBase

logger = logging.getLogger(__name__)


class RecontextService(VertexAIEditBase):
    """
    重新上下文服务

    继承 VertexAIEditBase，预设 edit_mode 为 'recontext'（EDIT_MODE_INPAINT_INSERTION）。

    构造函数: __init__(project_id, location, credentials_json)
    接口: edit_image(prompt, reference_images, config) -> List[Dict[str, Any]]
    """

    DEFAULT_EDIT_MODE = 'recontext'
