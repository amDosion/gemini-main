"""
通义图像服务 - 基础配置
包含端点映射、分辨率配置等共享常量和工具函数
"""
from typing import Dict

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"

# API 端点映射
ENDPOINTS = {
    "image-generation": "/api/v1/services/aigc/multimodal-generation/generation",
    "out-painting": "/api/v1/services/aigc/image2image/out-painting",
    "file": "/api/v1/files",
    "task": "/api/v1/tasks",
}

# ============================================
# Z-Image 分辨率映射
# ============================================
# 官方文档: https://help.aliyun.com/zh/model-studio/text-to-image-v2
# 总像素范围: [512*512, 2048*2048]
# 推荐范围: [1024*1024, 1536*1536]
# 特有比例: 7:9, 9:7, 9:21

Z_IMAGE_1K_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1024*1024",
    "2:3": "832*1248",
    "3:2": "1248*832",
    "3:4": "864*1152",
    "4:3": "1152*864",
    "7:9": "896*1152",
    "9:7": "1152*896",
    "9:16": "720*1280",
    "9:21": "576*1344",
    "16:9": "1280*720",
    "21:9": "1344*576",
}

Z_IMAGE_1280_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1280*1280",
    "2:3": "1024*1536",
    "3:2": "1536*1024",
    "3:4": "1104*1472",
    "4:3": "1472*1104",
    "7:9": "1120*1440",
    "9:7": "1440*1120",
    "9:16": "864*1536",
    "9:21": "720*1680",
    "16:9": "1536*864",
    "21:9": "1680*720",
}

Z_IMAGE_1536_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1536*1536",
    "2:3": "1248*1872",
    "3:2": "1872*1248",
    "3:4": "1296*1728",
    "4:3": "1728*1296",
    "7:9": "1344*1728",
    "9:7": "1728*1344",
    "9:16": "1152*2048",
    "9:21": "864*2016",
    "16:9": "2048*1152",
    "21:9": "2016*864",
}

Z_IMAGE_2K_RESOLUTIONS: Dict[str, str] = {
    "1:1": "2048*2048",
    "2:3": "1664*2496",
    "3:2": "2496*1664",
    "3:4": "1728*2304",
    "4:3": "2304*1728",
    "7:9": "1792*2304",
    "9:7": "2304*1792",
    "9:16": "1536*2730",
    "9:21": "1152*2688",
    "16:9": "2730*1536",
    "21:9": "2688*1152",
}

Z_IMAGE_RESOLUTIONS: Dict[str, Dict[str, str]] = {
    "1K": Z_IMAGE_1K_RESOLUTIONS,
    "1.25K": Z_IMAGE_1280_RESOLUTIONS,
    "1.5K": Z_IMAGE_1536_RESOLUTIONS,
    "2K": Z_IMAGE_2K_RESOLUTIONS,
}

# ============================================
# WanV2 文生图分辨率映射 (wan2.x-t2i / wanx2.x-t2i)
# ============================================
# 官方文档: https://help.aliyun.com/zh/model-studio/text-to-image-v2
# 总像素范围: [512*512, 2048*2048]
# 推荐范围: [1024*1024, 1536*1536]

WAN_T2I_1K_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1280*1280",
    "2:3": "800*1200",
    "3:2": "1200*800",
    "3:4": "960*1280",
    "4:3": "1280*960",
    "9:16": "720*1280",
    "16:9": "1280*720",
    "21:9": "1344*576",
}

WAN_T2I_1280_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1440*1440",
    "2:3": "900*1350",
    "3:2": "1350*900",
    "3:4": "1080*1440",
    "4:3": "1440*1080",
    "9:16": "810*1440",
    "16:9": "1440*810",
    "21:9": "1512*648",
}

WAN_T2I_1536_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1536*1536",
    "2:3": "960*1440",
    "3:2": "1440*960",
    "3:4": "1152*1536",
    "4:3": "1536*1152",
    "9:16": "864*1536",
    "16:9": "1536*864",
    "21:9": "1680*720",
}

WAN_V2_RESOLUTIONS: Dict[str, Dict[str, str]] = {
    "1K": WAN_T2I_1K_RESOLUTIONS,
    "1.25K": WAN_T2I_1280_RESOLUTIONS,
    "1.5K": WAN_T2I_1536_RESOLUTIONS,
}

# ============================================
# Qwen-Image-Plus 分辨率（固定的5种）
# ============================================

QWEN_RESOLUTIONS: Dict[str, str] = {
    "1:1": "1328*1328",
    "16:9": "1664*928",
    "9:16": "928*1664",
    "4:3": "1472*1140",
    "3:4": "1140*1472",
}


def get_endpoint(endpoint_type: str) -> str:
    """获取完整的 API 端点 URL"""
    return f"{DASHSCOPE_BASE_URL}{ENDPOINTS[endpoint_type]}"


def get_pixel_resolution(
    aspect_ratio: str,
    resolution_tier: str,
    model_id: str
) -> str:
    """
    根据模型和参数获取像素分辨率

    Args:
        aspect_ratio: 宽高比，如 "1:1", "16:9"
        resolution_tier: 分辨率档位，如 "1K", "1.25K", "1.5K", "2K"
        model_id: 模型 ID

    Returns:
        像素分辨率，如 "1280*1280"
    """
    model_lower = model_id.lower()

    # Z-Image 系列
    if "z-image" in model_lower:
        tier_map = Z_IMAGE_RESOLUTIONS.get(resolution_tier, Z_IMAGE_1280_RESOLUTIONS)
        return tier_map.get(aspect_ratio, tier_map.get("1:1", "1280*1280"))

    # WanV2 系列 (-t2i 后缀的文生图模型)
    if "-t2i" in model_lower or "wan" in model_lower or "wanx" in model_lower:
        tier_map = WAN_V2_RESOLUTIONS.get(resolution_tier, WAN_T2I_1280_RESOLUTIONS)
        return tier_map.get(aspect_ratio, tier_map.get("1:1", "1280*1280"))

    # Qwen-Image-Plus
    if "qwen" in model_lower:
        return QWEN_RESOLUTIONS.get(aspect_ratio, QWEN_RESOLUTIONS.get("1:1", "1328*1328"))

    # 默认
    return "1024*1024"
