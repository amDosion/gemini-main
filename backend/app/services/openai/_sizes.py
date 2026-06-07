"""
OpenAI 图像尺寸/宽高比查表与模型识别辅助。

从 ``_shared`` 拆分而来。保持纯函数与常量,供 ``_shared`` 重新导出,
以维持既有调用方的导入契约不变。
"""
from __future__ import annotations

from typing import Any, Optional, Set

IMAGE_ALLOWED_OPTION_KEYS: Set[str] = {
    "size",
    "quality",
    "style",
    "n",
    "response_format",
    "user",
    "background",
    "moderation",
    "output_format",
    "output_compression",
    "partial_images",
}

IMAGE_EDIT_ALLOWED_OPTION_KEYS: Set[str] = {
    "size",
    "quality",
    "n",
    "response_format",
    "user",
    "background",
    "moderation",
    "output_format",
    "output_compression",
    "input_fidelity",
    "mask",
    "partial_images",
}

SPEECH_ALLOWED_OPTION_KEYS: Set[str] = {
    "model",
    "response_format",
    "speed",
    "instructions",
}

IMAGE_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "16:9": "1792x1024",
}

GPT_IMAGE_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "4:3": "1152x864",
    "3:4": "864x1152",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
}

GPT_IMAGE_2_MAX_SIZE_BY_ASPECT_RATIO = {
    "1:1": "2880x2880",
    "4:3": "2880x2160",
    "3:4": "2160x2880",
    "16:9": "3840x2160",
    "9:16": "2160x3840",
    "3:2": "3456x2304",
    "2:3": "2304x3456",
}

GPT_IMAGE_2_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO = {
    "1K": {
        "1:1": "1024x1024",
        "4:3": "1152x864",
        "3:4": "864x1152",
        "16:9": "1280x720",
        "9:16": "720x1280",
        "3:2": "1536x1024",
        "2:3": "1024x1536",
    },
    "2K": {
        "1:1": "2048x2048",
        "4:3": "2048x1536",
        "3:4": "1536x2048",
        "16:9": "2048x1152",
        "9:16": "1152x2048",
        "3:2": "2304x1536",
        "2:3": "1536x2304",
    },
    "MAX": GPT_IMAGE_2_MAX_SIZE_BY_ASPECT_RATIO,
    "4K": GPT_IMAGE_2_MAX_SIZE_BY_ASPECT_RATIO,
}

GPT_IMAGE_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO = {
    "1K": {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "3:2": "1536x1024",
    },
}

GPT_IMAGE_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}
GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3840
GPT_IMAGE_2_MAX_ASPECT_RATIO = 3.0
DALL_E_2_SIZES = {"256x256", "512x512", "1024x1024"}
DALL_E_3_SIZES = {"1024x1024", "1024x1792", "1792x1024"}

AUDIO_MIME_TYPE_BY_FORMAT = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/pcm",
}


def is_gpt_image_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    return normalized.startswith("gpt-image") or normalized.startswith("chatgpt-image")


def is_gpt_image_2_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    return normalized.startswith("gpt-image-2")


def is_valid_gpt_image_2_size(size: str) -> bool:
    value = str(size or "").strip().lower()
    if value == "auto":
        return True
    if "x" not in value:
        return False
    width_raw, height_raw = value.split("x", 1)
    try:
        width = int(width_raw)
        height = int(height_raw)
    except ValueError:
        return False
    if width <= 0 or height <= 0:
        return False
    if width > GPT_IMAGE_2_MAX_EDGE or height > GPT_IMAGE_2_MAX_EDGE:
        return False
    if width % 16 != 0 or height % 16 != 0:
        return False
    pixels = width * height
    if pixels < GPT_IMAGE_2_MIN_PIXELS or pixels > GPT_IMAGE_2_MAX_PIXELS:
        return False
    long_edge = max(width, height)
    short_edge = min(width, height)
    return long_edge / short_edge <= GPT_IMAGE_2_MAX_ASPECT_RATIO


def normalize_image_size(model: str, size: Optional[Any]) -> Optional[str]:
    value = str(size or "").strip()
    if not value:
        return None

    lower_model = str(model or "").strip().lower()
    lowered_value = value.lower()
    normalized_tier = value.upper()
    if is_gpt_image_2_model(lower_model) and normalized_tier in GPT_IMAGE_2_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO:
        return None
    if is_gpt_image_2_model(lower_model):
        return lowered_value if is_valid_gpt_image_2_size(lowered_value) else None
    if is_gpt_image_model(lower_model):
        return lowered_value if lowered_value in GPT_IMAGE_SIZES else None
    if lower_model.startswith("dall-e-2"):
        return lowered_value if lowered_value in DALL_E_2_SIZES else None
    if lower_model.startswith("dall-e-3"):
        return lowered_value if lowered_value in DALL_E_3_SIZES else None
    if "x" in lowered_value or lowered_value == "auto":
        return lowered_value
    return None


def map_image_resolution_to_size(
    model: str,
    resolution: Optional[Any],
    aspect_ratio: Optional[str],
) -> Optional[str]:
    value = str(resolution or "").strip()
    if not value:
        return None

    if value.lower() == "auto" and is_gpt_image_model(model):
        return "auto"

    if is_gpt_image_2_model(model):
        tier_map = GPT_IMAGE_2_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO.get(value.upper())
        if tier_map:
            aspect = str(aspect_ratio or "").strip() or "1:1"
            return tier_map.get(aspect) or tier_map.get("1:1")

    return normalize_image_size(model, value)


def map_image_aspect_ratio_to_size(model: str, aspect_ratio: Optional[str]) -> Optional[str]:
    value = str(aspect_ratio or "").strip()
    if not value:
        return None

    mapped = (
        GPT_IMAGE_SIZE_BY_ASPECT_RATIO.get(value)
        if is_gpt_image_model(model)
        else IMAGE_SIZE_BY_ASPECT_RATIO.get(value)
    )
    if not mapped:
        return None

    if str(model or "").strip().lower().startswith("dall-e-2") and mapped != "1024x1024":
        return "1024x1024"

    return mapped


def read_field(item: Any, *field_names: str) -> Any:
    if isinstance(item, dict):
        for field_name in field_names:
            if field_name in item:
                return item[field_name]
        return None

    for field_name in field_names:
        value = getattr(item, field_name, None)
        if value is not None:
            return value
    return None


def audio_format_to_mime_type(audio_format: str) -> str:
    normalized = str(audio_format or "").strip().lower()
    return AUDIO_MIME_TYPE_BY_FORMAT.get(normalized, "audio/mpeg")


def image_output_format_to_mime_type(output_format: Optional[str]) -> str:
    normalized = str(output_format or "").strip().lower()
    if normalized == "jpeg":
        return "image/jpeg"
    if normalized == "webp":
        return "image/webp"
    return "image/png"
