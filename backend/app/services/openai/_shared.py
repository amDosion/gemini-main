"""
OpenAI 服务共享辅助函数。
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Iterable, Mapping, Optional, Set

from openai import AsyncOpenAI

DEFAULT_BASE_URL = "https://api.openai.com/v1"

INTERNAL_OPTION_KEYS: Set[str] = {
    "base_url",
    "frontend_session_id",
    "session_id",
    "message_id",
    "active_image_url",
    "enable_search",
    "enable_thinking",
    "enable_code_execution",
    "enable_browser",
    "enable_grounding",
    "reference_images",
}

CHAT_ALLOWED_OPTION_KEYS: Set[str] = {
    "temperature",
    "max_tokens",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "seed",
    "stop",
    "response_format",
    "logit_bias",
    "n",
    "user",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "stream_options",
}

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

AUDIO_MIME_TYPE_BY_FORMAT = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/pcm",
}


def build_async_client(
    api_key: str,
    base_url: Optional[str] = None,
    *,
    timeout: float = 120.0,
    max_retries: int = 3,
    client: Optional[AsyncOpenAI] = None,
) -> AsyncOpenAI:
    if client is not None:
        return client

    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url or DEFAULT_BASE_URL,
        timeout=timeout,
        max_retries=max_retries,
    )


def filter_allowed_kwargs(
    kwargs: Mapping[str, Any],
    *,
    allowed_keys: Iterable[str],
    aliases: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    alias_map = aliases or {}
    allowed = set(allowed_keys)
    filtered: Dict[str, Any] = {}

    for key, value in kwargs.items():
        if value is None:
            continue
        normalized_key = alias_map.get(key, key)
        if normalized_key in INTERNAL_OPTION_KEYS:
            continue
        if normalized_key not in allowed:
            continue
        filtered[normalized_key] = value

    return filtered


def map_image_aspect_ratio_to_size(model: str, aspect_ratio: Optional[str]) -> Optional[str]:
    value = str(aspect_ratio or "").strip()
    if not value:
        return None

    mapped = IMAGE_SIZE_BY_ASPECT_RATIO.get(value)
    if not mapped:
        return None

    if str(model or "").strip().lower().startswith("dall-e-2") and mapped != "1024x1024":
        return "1024x1024"

    return mapped


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


def to_data_url(content: bytes, mime_type: str) -> str:
    import base64

    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def read_binary_response_content(response: Any) -> bytes:
    if hasattr(response, "read"):
        content = response.read()
        if inspect.isawaitable(content):
            content = await content
        return _coerce_binary_content(content)

    if hasattr(response, "content"):
        return _coerce_binary_content(response.content)

    return _coerce_binary_content(response)


def _coerce_binary_content(content: Any) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    raise RuntimeError(f"Unsupported binary response type: {type(content).__name__}")
