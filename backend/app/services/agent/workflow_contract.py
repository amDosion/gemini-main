"""Workflow execution contract constants and normalizers.

This module is the backend source of truth for values that cross the
workflow editor / execute boundary. Keep UI-only labels out of this file.
"""

from __future__ import annotations

from typing import Any, Optional

ALLOWED_WORKFLOW_AGENT_TASK_TYPES = {
    "chat",
    "image-gen",
    "image-edit",
    "video-gen",
    "audio-gen",
    "vision-understand",
    "data-analysis",
}

AGENT_TASK_TYPE_ALIASES = {
    "vision-analyze": "vision-understand",
    "image-analyze": "vision-understand",
    "image-understand": "vision-understand",
    "table-analysis": "data-analysis",
    "video": "video-gen",
    "video-generate": "video-gen",
    "video-generation": "video-gen",
    "audio": "audio-gen",
    "speech": "audio-gen",
    "tts": "audio-gen",
    "speech-gen": "audio-gen",
    "speech-generate": "audio-gen",
    "speech-generation": "audio-gen",
    "audio-generate": "audio-gen",
    "audio-generation": "audio-gen",
}

ALLOWED_WORKFLOW_NODE_TYPES = {
    "start",
    "end",
    "input_text",
    "input_image",
    "input_video",
    "input_audio",
    "input_file",
    "agent",
    "tool",
    "router",
    "parallel",
    "condition",
    "merge",
    "loop",
    "human",
}

ALLOWED_IMAGE_EDIT_MODES = {
    "image-chat-edit",
    "image-mask-edit",
    "image-inpainting",
    "image-background-edit",
    "image-recontext",
    "image-outpainting",
}

IMAGE_EDIT_MODE_ALIASES = {
    "image-chat": "image-chat-edit",
    "chat-edit": "image-chat-edit",
    "mask-edit": "image-mask-edit",
    "inpainting": "image-inpainting",
    "background-edit": "image-background-edit",
    "background": "image-background-edit",
    "recontext": "image-recontext",
    "outpaint": "image-outpainting",
    "image-outpaint": "image-outpainting",
}

ALLOWED_IMAGE_OUTPUT_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_AUDIO_OUTPUT_FORMATS = {"mp3", "wav", "opus", "aac", "flac", "pcm"}
ALLOWED_OUTPUT_FORMATS = {"text", "json", "markdown"}
ALLOWED_VIDEO_ASPECT_RATIOS = {"16:9", "9:16"}
ALLOWED_VIDEO_RESOLUTIONS = {"720p", "1080p", "4k"}
ALLOWED_VIDEO_SUBTITLE_MODES = {"none", "vtt", "srt", "both"}
ALLOWED_VIDEO_INPUT_STRATEGIES = {
    "text_to_video",
    "image_to_video",
    "first_last_frame",
    "video_extension",
    "masked_video_edit",
    "video_mask_edit",
    "first_frame_to_video",
    "first_last_frame_to_video",
    "video_continuation",
    "video_continuation_to_last_frame",
    "reference_to_video",
    "video_edit",
}

VIDEO_RESOLUTION_ALIASES = {
    "1k": "720p",
    "720p": "720p",
    "1280": "720p",
    "1280x720": "720p",
    "720x1280": "720p",
    "2k": "1080p",
    "1080p": "1080p",
    "1920": "1080p",
    "1920x1080": "1080p",
    "1080x1920": "1080p",
    "4k": "4k",
    "2160p": "4k",
    "3840x2160": "4k",
    "2160x3840": "4k",
}

ALLOWED_VIDEO_MASK_MODES = {"INSERT", "REMOVE", "REMOVE_STATIC", "OUTPAINT"}

VIDEO_MASK_MODE_ALIASES = {
    "INSERT": "INSERT",
    "REPLACE": "INSERT",
    "BACKGROUND": "INSERT",
    "BACKGROUND_REPLACE": "INSERT",
    "BACKGROUND-REPLACE": "INSERT",
    "REMOVE": "REMOVE",
    "REMOVE_OBJECT": "REMOVE",
    "REMOVE-OBJECT": "REMOVE",
    "REMOVE_STATIC": "REMOVE_STATIC",
    "REMOVE-STATIC": "REMOVE_STATIC",
    "OUTPAINT": "OUTPAINT",
}

ACTIVE_INLINE_PROVIDER_TOKENS = {
    "__active__",
    "__current__",
    "active",
    "current",
    "active-profile",
    "current-profile",
}

AUTO_INLINE_MODEL_TOKENS = {
    "",
    "__auto__",
    "__active__",
    "auto",
    "active",
    "current",
    "active-profile",
    "current-profile",
}


def normalize_workflow_agent_task_type(value: Any, fallback: str = "chat") -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    normalized = AGENT_TASK_TYPE_ALIASES.get(raw, raw)
    return normalized if normalized in ALLOWED_WORKFLOW_AGENT_TASK_TYPES else fallback


def normalize_workflow_image_edit_mode(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    normalized = IMAGE_EDIT_MODE_ALIASES.get(raw, raw)
    return normalized if normalized in ALLOWED_IMAGE_EDIT_MODES else None


def normalize_workflow_video_resolution(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.lower().replace(" ", "").replace("*", "x").replace("×", "x")
    return VIDEO_RESOLUTION_ALIASES.get(normalized)


def normalize_workflow_video_mask_mode(value: Any) -> Optional[str]:
    raw = str(value or "").strip().upper().replace("-", "_")
    if not raw:
        return None
    return VIDEO_MASK_MODE_ALIASES.get(raw)


def is_active_inline_provider_token(value: Any) -> bool:
    return str(value or "").strip().lower() in ACTIVE_INLINE_PROVIDER_TOKENS


def is_auto_inline_model_token(value: Any) -> bool:
    return str(value or "").strip().lower() in AUTO_INLINE_MODEL_TOKENS
