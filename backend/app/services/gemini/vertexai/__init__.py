"""
Vertex AI 专用服务模块

这些服务需要 GCP 凭证，使用专用的图像处理 API。
所有服务通过 client_pool.get_client(vertexai=True) 获取客户端。

服务列表:
- tryon_service: 虚拟试穿 (recontext_image API)
- upscale_service: 图片放大 (upscale_image API)
- segmentation_service: 图片分割 (segment_image API)
- mask_edit_service: 掩码编辑 (edit_image API)
- expand_service: 图像扩展 (edit_image API - outpaint)
- imagen_vertex_ai: Vertex AI 图像生成
- image_edit_vertex_ai: Vertex AI 图像编辑
"""

from .tryon_service import TryOnService, TryOnResult, tryon_service
from .upscale_service import UpscaleService, UpscaleResult, upscale_service
from .segmentation_service import SegmentationService, SegmentResult, segmentation_service
from .mask_edit_service import MaskEditService, EditResult, mask_edit_service

__all__ = [
    # 虚拟试穿
    "TryOnService",
    "TryOnResult",
    "tryon_service",
    # 图片放大
    "UpscaleService",
    "UpscaleResult",
    "upscale_service",
    # 图片分割
    "SegmentationService",
    "SegmentResult",
    "segmentation_service",
    # 掩码编辑
    "MaskEditService",
    "EditResult",
    "mask_edit_service",
]
