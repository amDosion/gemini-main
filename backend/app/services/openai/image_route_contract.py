"""OpenAI image endpoint routing contract.

Application modes own the endpoint choice:
- image-gen is text-to-image and uses the Images Generate endpoint.
- image-chat-edit and derived image-edit modes are image-to-image and use the
  Images Edit endpoint.
- Responses image editing is only a continuation path when an existing
  `previous_response_id` is present.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Optional


class OpenAIImageRoute(str, Enum):
    IMAGE_GENERATIONS = "images.generations"
    IMAGE_EDITS = "images.edits"
    RESPONSES_IMAGE_GENERATION = "responses.image_generation"
    RESPONSES_IMAGE_EDIT = "responses.image_edit"


def select_image_generation_route(kwargs: Mapping[str, Any]) -> OpenAIImageRoute:
    return OpenAIImageRoute.IMAGE_GENERATIONS


def select_image_edit_route(
    mode: Optional[str],
    kwargs: Mapping[str, Any],
) -> OpenAIImageRoute:
    if wants_responses_image_api(kwargs):
        return OpenAIImageRoute.RESPONSES_IMAGE_EDIT
    return OpenAIImageRoute.IMAGE_EDITS


def wants_responses_image_api(kwargs: Mapping[str, Any]) -> bool:
    return bool(_previous_response_id(kwargs))


def _previous_response_id(kwargs: Mapping[str, Any]) -> Optional[str]:
    value = (
        kwargs.get("openai_previous_response_id")
        or kwargs.get("openaiPreviousResponseId")
        or kwargs.get("previous_response_id")
        or ""
    )
    normalized = str(value).strip()
    return normalized or None
