"""
Mode to backend service mapping and mode catalog metadata.

Single source of truth:
- Execution method routing (`mode -> service_method`)
- Frontend navigation metadata (group/label/description/filter mode)
"""

from typing import Dict, Optional, List, TypedDict


class ModeCatalogItem(TypedDict):
    id: str
    label: str
    description: str
    group: str
    service_method: str
    filter_mode: str
    visible_in_navigation: bool
    streaming: bool
    image_edit: bool
    layered_design: bool


# Unified mode catalog (ordered)
MODE_CATALOG: List[ModeCatalogItem] = [
    # Core
    {
        "id": "chat",
        "label": "Chat",
        "description": "对话聊天",
        "group": "基础",
        "service_method": "stream_chat",
        "filter_mode": "chat",
        "visible_in_navigation": True,
        "streaming": True,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "multi-agent",
        "label": "Multi-Agent",
        "description": "多智能体",
        "group": "基础",
        "service_method": "multi_agent",
        "filter_mode": "multi-agent",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    # Image generation/editing
    {
        "id": "image-gen",
        "label": "Gen",
        "description": "图片生成",
        "group": "图片生成",
        "service_method": "generate_image",
        "filter_mode": "image-gen",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "image-chat-edit",
        "label": "Chat Edit",
        "description": "对话编辑",
        "group": "图片编辑",
        "service_method": "edit_image",
        "filter_mode": "image-chat-edit",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": True,
        "layered_design": False,
    },
    {
        "id": "image-mask-edit",
        "label": "Mask",
        "description": "蒙版编辑",
        "group": "图片编辑",
        "service_method": "edit_image",
        "filter_mode": "image-mask-edit",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": True,
        "layered_design": False,
    },
    {
        "id": "image-inpainting",
        "label": "Inpaint",
        "description": "局部重绘",
        "group": "图片编辑",
        "service_method": "edit_image",
        "filter_mode": "image-inpainting",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": True,
        "layered_design": False,
    },
    {
        "id": "image-background-edit",
        "label": "Background",
        "description": "背景编辑",
        "group": "图片编辑",
        "service_method": "edit_image",
        "filter_mode": "image-background-edit",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": True,
        "layered_design": False,
    },
    {
        "id": "image-recontext",
        "label": "Recontext",
        "description": "场景重构",
        "group": "图片编辑",
        "service_method": "edit_image",
        "filter_mode": "image-recontext",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": True,
        "layered_design": False,
    },
    {
        "id": "virtual-try-on",
        "label": "Try-On",
        "description": "虚拟试衣",
        "group": "图片编辑",
        "service_method": "virtual_tryon",
        "filter_mode": "virtual-try-on",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "image-outpainting",
        "label": "Expand",
        "description": "图片扩展",
        "group": "图片编辑",
        "service_method": "expand_image",
        "filter_mode": "image-outpainting",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    # Media
    {
        "id": "video-gen",
        "label": "Video",
        "description": "视频生成",
        "group": "媒体",
        "service_method": "generate_video",
        "filter_mode": "video-gen",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "video-understand",
        "label": "Video Understand",
        "description": "视频理解",
        "group": "内部",
        "service_method": "understand_video",
        "filter_mode": "video-understand",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "video-delete",
        "label": "Video Delete",
        "description": "删除提供商视频资产",
        "group": "内部",
        "service_method": "delete_video",
        "filter_mode": "video-delete",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "audio-gen",
        "label": "Audio",
        "description": "音频生成",
        "group": "媒体",
        "service_method": "generate_speech",
        "filter_mode": "audio-gen",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "pdf-extract",
        "label": "PDF",
        "description": "PDF 提取",
        "group": "媒体",
        "service_method": "extract_pdf_data",
        "filter_mode": "pdf-extract",
        "visible_in_navigation": True,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    # Internal/non-navigation
    {
        "id": "image-edit",
        "label": "Image Edit",
        "description": "通用图片编辑",
        "group": "内部",
        "service_method": "edit_image",
        "filter_mode": "image-edit",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": True,
        "layered_design": False,
    },
    {
        "id": "image-mask-preview",
        "label": "Mask Preview",
        "description": "自动掩码预览",
        "group": "内部",
        "service_method": "preview_mask",
        "filter_mode": "image-mask-edit",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "image-upscale",
        "label": "Upscale",
        "description": "图片放大",
        "group": "内部",
        "service_method": "upscale_image",
        "filter_mode": "image-upscale",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "image-segmentation",
        "label": "Segmentation",
        "description": "图像分割",
        "group": "内部",
        "service_method": "segment_image",
        "filter_mode": "image-segmentation",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "product-recontext",
        "label": "Product Recontext",
        "description": "产品重构",
        "group": "内部",
        "service_method": "edit_image",
        "filter_mode": "product-recontext",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "segment-clothing",
        "label": "Segment Clothing",
        "description": "服装分割",
        "group": "内部",
        "service_method": "segment_clothing",
        "filter_mode": "image-segmentation",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": False,
    },
    {
        "id": "image-layered-suggest",
        "label": "Layered Suggest",
        "description": "布局建议",
        "group": "内部",
        "service_method": "layered_design",
        "filter_mode": "image-chat-edit",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": True,
    },
    {
        "id": "image-layered-decompose",
        "label": "Layered Decompose",
        "description": "图层分解",
        "group": "内部",
        "service_method": "layered_design",
        "filter_mode": "image-chat-edit",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": True,
    },
    {
        "id": "image-layered-vectorize",
        "label": "Layered Vectorize",
        "description": "Mask 矢量化",
        "group": "内部",
        "service_method": "layered_design",
        "filter_mode": "image-chat-edit",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": True,
    },
    {
        "id": "image-layered-render",
        "label": "Layered Render",
        "description": "渲染合成",
        "group": "内部",
        "service_method": "layered_design",
        "filter_mode": "image-chat-edit",
        "visible_in_navigation": False,
        "streaming": False,
        "image_edit": False,
        "layered_design": True,
    },
]


MODE_METHOD_MAP: Dict[str, str] = {
    item["id"]: item["service_method"] for item in MODE_CATALOG
}
_STREAMING_MODES = {item["id"] for item in MODE_CATALOG if item["streaming"]}
_IMAGE_EDIT_MODES = {item["id"] for item in MODE_CATALOG if item["image_edit"]}
_LAYERED_DESIGN_MODES = {item["id"] for item in MODE_CATALOG if item["layered_design"]}


def get_mode_catalog(include_internal: bool = False) -> List[ModeCatalogItem]:
    if include_internal:
        return [dict(item) for item in MODE_CATALOG]
    return [dict(item) for item in MODE_CATALOG if item["visible_in_navigation"]]


def get_service_method(mode: str) -> Optional[str]:
    return MODE_METHOD_MAP.get(mode)


def is_streaming_mode(mode: str) -> bool:
    return mode in _STREAMING_MODES


def is_image_edit_mode(mode: str) -> bool:
    return mode in _IMAGE_EDIT_MODES


def is_layered_design_mode(mode: str) -> bool:
    return mode in _LAYERED_DESIGN_MODES
