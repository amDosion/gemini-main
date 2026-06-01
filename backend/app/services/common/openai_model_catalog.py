"""Static OpenAI media model catalog.

The normal models endpoint is DB-first. Sora video models need to remain
visible for video-gen even when the saved profile only contains chat/image
models or when the provider model listing omits preview media models.
"""

from __future__ import annotations

from typing import Dict, List


OPENAI_STATIC_MEDIA_MODELS: List[Dict[str, str]] = [
    {
        "id": "sora-2",
        "name": "Sora 2",
        "description": "OpenAI text/image-to-video generation model with synced audio output",
    },
    {
        "id": "sora-2-pro",
        "name": "Sora 2 Pro",
        "description": "OpenAI higher-quality Sora video generation and editing model",
    },
]


def get_static_openai_media_model_entries() -> List[Dict[str, str]]:
    return [dict(entry) for entry in OPENAI_STATIC_MEDIA_MODELS]


def get_static_openai_media_model_ids() -> List[str]:
    return [entry["id"] for entry in OPENAI_STATIC_MEDIA_MODELS]
