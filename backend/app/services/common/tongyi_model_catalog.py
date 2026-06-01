"""Static Tongyi/DashScope media model catalog.

DashScope's OpenAI-compatible model listing does not reliably include Wan
image/video models. Keep provider-owned media models here and merge them with
profile/API-discovered models before app-mode filtering.
"""

from __future__ import annotations

from typing import Dict, List


TONGYI_STATIC_MEDIA_MODELS: List[Dict[str, str]] = [
    {
        "id": "qwen-tts",
        "name": "Qwen TTS",
        "description": "Qwen non-realtime text-to-speech model",
    },
    {
        "id": "image-out-painting",
        "name": "Image Out Painting",
        "description": "DashScope image outpainting model",
    },
    {
        "id": "aitryon-plus",
        "name": "OutfitAnyone Plus",
        "description": "DashScope virtual try-on model",
    },
    {
        "id": "wan2.7-image-pro",
        "name": "Wan 2.7 Image Pro",
        "description": "Wan 2.7 image generation and editing model with 4K text-to-image support",
    },
    {
        "id": "wan2.7-image",
        "name": "Wan 2.7 Image",
        "description": "Wan 2.7 image generation and editing model",
    },
    {
        "id": "wan2.7-t2v",
        "name": "Wan 2.7 Text to Video",
        "description": "Wan 2.7 text-to-video model",
    },
    {
        "id": "wan2.7-i2v",
        "name": "Wan 2.7 Image to Video",
        "description": "Wan 2.7 image-to-video and video-continuation model",
    },
    {
        "id": "wan2.7-r2v",
        "name": "Wan 2.7 Reference to Video",
        "description": "Wan 2.7 reference-to-video model",
    },
    {
        "id": "wan2.7-videoedit",
        "name": "Wan 2.7 Video Edit",
        "description": "Wan 2.7 instruction-based video editing model",
    },
    {
        "id": "happyhorse-1.0-t2v",
        "name": "HappyHorse 1.0 Text to Video",
        "description": "HappyHorse 1.0 text-to-video model",
    },
    {
        "id": "happyhorse-1.0-i2v",
        "name": "HappyHorse 1.0 Image to Video",
        "description": "HappyHorse 1.0 image-to-video model",
    },
    {
        "id": "happyhorse-1.0-r2v",
        "name": "HappyHorse 1.0 Reference to Video",
        "description": "HappyHorse 1.0 reference-to-video model",
    },
    {
        "id": "happyhorse-1.0-video-edit",
        "name": "HappyHorse 1.0 Video Edit",
        "description": "HappyHorse 1.0 video editing model",
    },
]


def get_static_tongyi_media_model_entries() -> List[Dict[str, str]]:
    return [dict(entry) for entry in TONGYI_STATIC_MEDIA_MODELS]


def get_static_tongyi_media_model_ids() -> List[str]:
    return [entry["id"] for entry in TONGYI_STATIC_MEDIA_MODELS]
