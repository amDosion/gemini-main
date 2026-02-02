"""
Vertex AI 专用服务模块

这些服务需要 GCP 凭证，使用专用的图像处理 API。
所有编辑服务继承 VertexAIEditBase，遵循统一的有状态接口模式：
- 构造函数: __init__(project_id, location, credentials_json)
- 接口: edit_image(prompt, reference_images, config) -> List[Dict[str, Any]]

服务列表:
- vertex_edit_base: 编辑服务共享基类
- inpainting_service: 图像修复 (edit_image API - inpaint)
- background_edit_service: 背景编辑 (edit_image API - bgswap)
- recontext_service: 重新上下文 (edit_image API - inpaint)
- mask_edit_service: 掩码编辑 (edit_image API - 带掩码)
- tryon_service: 虚拟试穿 (recontext_image API)
- segmentation_service: 图片分割 (segment_image API)
- expand_service: 图像扩展/放大 (edit_image API - outpaint, upscale_image API)
- imagen_vertex_ai: Vertex AI 图像生成
- image_edit_vertex_ai: Vertex AI 图像编辑 (向后兼容别名)

注意: upscale_service 已整合到 expand_service 中
"""

from .tryon_service import TryOnService, TryOnResult, tryon_service
from .segmentation_service import SegmentationService, SegmentResult, segmentation_service
from .mask_edit_service import MaskEditService, EditResult
from .vertex_edit_base import VertexAIEditBase
from .inpainting_service import InpaintingService
from .background_edit_service import BackgroundEditService
from .recontext_service import RecontextService
from .expand_service import ExpandService

__all__ = [
    # 编辑服务基类
    "VertexAIEditBase",
    # 图像修复
    "InpaintingService",
    # 背景编辑
    "BackgroundEditService",
    # 重新上下文
    "RecontextService",
    # 掩码编辑
    "MaskEditService",
    "EditResult",
    # 虚拟试穿
    "TryOnService",
    "TryOnResult",
    "tryon_service",
    # 图片分割
    "SegmentationService",
    "SegmentResult",
    "segmentation_service",
    # 图像扩展/放大
    "ExpandService",
]
