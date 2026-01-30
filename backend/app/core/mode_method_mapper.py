"""
Mode 到服务方法映射

将前端 mode 映射到提供商服务的对应方法。
路由层使用此映射来调用正确的服务方法。
"""
from typing import Dict, Optional

# Mode 到服务方法的映射表
MODE_METHOD_MAP: Dict[str, str] = {
    # 聊天
    "chat": "stream_chat",

    # 图片相关
    "image-gen": "generate_image",

    # 图片编辑模式（都映射到 edit_image，但需要传递 mode 参数）
    "image-chat-edit": "edit_image",      # 对话式图片编辑 → ConversationalImageEditService
    "image-mask-edit": "edit_image",      # 遮罩编辑 → ImageEditCoordinator → MaskEditService
    "image-inpainting": "edit_image",     # 图片修复 → ImageEditCoordinator (Vertex AI Imagen)
    "image-background-edit": "edit_image", # 背景编辑 → ImageEditCoordinator (Vertex AI Imagen)
    "image-recontext": "edit_image",      # 图片重上下文 → ImageEditCoordinator (Vertex AI Imagen)
    "image-edit": "edit_image",           # 图片编辑（通用，自动检测） → ImageEditCoordinator 或 SimpleImageEditService

    "image-mask-preview": "preview_mask", # 自动 mask 预览 → SegmentationService
    "image-outpainting": "expand_image",  # 图片扩展 → ExpandService
    
    # 视频和音频
    "video-gen": "generate_video",
    "audio-gen": "generate_speech",
    
    # 其他
    "pdf-extract": "extract_pdf_data",
    "virtual-try-on": "virtual_tryon",
    "segment-clothing": "segment_clothing",  # 服装分割
    "deep-research": "deep_research",
    "multi-agent": "multi_agent",

    # 分层设计模式（都映射到 layered_design，内部根据 mode 参数分发）
    "image-layered-suggest": "layered_design",     # 布局建议 → LayeredDesignService.suggest_layout()
    "image-layered-decompose": "layered_design",   # 图层分解 → LayeredDesignService.decompose_layers()
    "image-layered-vectorize": "layered_design",   # Mask 矢量化 → LayeredDesignService.vectorize_mask()
    "image-layered-render": "layered_design",      # 渲染合成 → LayeredDesignService.render_layerdoc()
}


def get_service_method(mode: str) -> Optional[str]:
    """
    根据 mode 获取对应的服务方法名
    
    Args:
        mode: 前端模式名称
        
    Returns:
        服务方法名，如果不存在则返回 None
    """
    return MODE_METHOD_MAP.get(mode)


def is_streaming_mode(mode: str) -> bool:
    """
    判断是否为流式模式
    
    Args:
        mode: 前端模式名称
        
    Returns:
        是否为流式模式
    """
    streaming_modes = {"chat"}
    return mode in streaming_modes


def is_image_edit_mode(mode: str) -> bool:
    """
    判断是否为图片编辑相关的 mode

    Args:
        mode: 前端模式名称

    Returns:
        是否为图片编辑模式
    """
    image_edit_modes = {
        "image-chat-edit",
        "image-mask-edit",
        "image-inpainting",
        "image-background-edit",
        "image-recontext",
        "image-edit"
    }
    return mode in image_edit_modes


def is_layered_design_mode(mode: str) -> bool:
    """
    判断是否为分层设计相关的 mode

    Args:
        mode: 前端模式名称

    Returns:
        是否为分层设计模式
    """
    layered_modes = {
        "image-layered-suggest",
        "image-layered-decompose",
        "image-layered-vectorize",
        "image-layered-render"
    }
    return mode in layered_modes
