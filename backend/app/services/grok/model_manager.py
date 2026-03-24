"""
Grok 模型管理器

处理 Grok 的模型列表获取。
通过 httpx 调用 grok2api 的 /models 端点。
"""
from __future__ import annotations
from typing import List, Optional
import logging

import httpx

from ..common.model_capabilities import (
    Capabilities,
    ModelConfig,
    ModelTraits,
    build_model_config,
    get_model_traits,
)

logger = logging.getLogger(__name__)

# Model IDs that are chat models (not image/video)
CHAT_MODEL_PREFIXES = ("grok-3", "grok-4")
IMAGE_MODEL_IDS = {"grok-imagine-1.0", "grok-imagine-1.0-fast"}
IMAGE_EDIT_MODEL_IDS = {"grok-imagine-1.0-edit"}
VIDEO_MODEL_IDS = {"grok-imagine-1.0-video"}

# Display name mapping
DISPLAY_NAMES = {
    "grok-3": "Grok 3",
    "grok-3-mini": "Grok 3 Mini",
    "grok-3-thinking": "Grok 3 Thinking",
    "grok-4": "Grok 4",
    "grok-4-thinking": "Grok 4 Thinking",
    "grok-4-heavy": "Grok 4 Heavy",
    "grok-4.1-mini": "Grok 4.1 Mini",
    "grok-4.1-fast": "Grok 4.1 Fast",
    "grok-4.1-expert": "Grok 4.1 Expert",
    "grok-4.1-thinking": "Grok 4.1 Thinking",
    "grok-4.20-beta": "Grok 4.20 Beta",
    "grok-imagine-1.0": "Grok Image",
    "grok-imagine-1.0-fast": "Grok Image Fast",
    "grok-imagine-1.0-edit": "Grok Image Edit",
    "grok-imagine-1.0-video": "Grok Video",
}

DESCRIPTIONS = {
    "grok-3": "Grok 3 chat model by xAI.",
    "grok-3-mini": "Grok 3 Mini with thinking capabilities.",
    "grok-3-thinking": "Grok 3 with extended thinking.",
    "grok-4": "Grok 4 flagship chat model by xAI.",
    "grok-4-thinking": "Grok 4 with extended thinking.",
    "grok-4-heavy": "Grok 4 Heavy - premium tier model.",
    "grok-4.1-mini": "Grok 4.1 Mini - compact thinking model.",
    "grok-4.1-fast": "Grok 4.1 Fast - optimized for speed.",
    "grok-4.1-expert": "Grok 4.1 Expert - high quality reasoning.",
    "grok-4.1-thinking": "Grok 4.1 with extended thinking.",
    "grok-4.20-beta": "Grok 4.20 Beta preview model.",
    "grok-imagine-1.0": "Image generation model.",
    "grok-imagine-1.0-fast": "Fast image generation model.",
    "grok-imagine-1.0-edit": "Image editing model with reference images.",
    "grok-imagine-1.0-video": "Video generation model (6-30 seconds).",
}

# Unsupported model tokens (skip these)
UNSUPPORTED_MODEL_TOKENS = (
    "embedding",
    "moderation",
    "tts",
    "whisper",
    "transcribe",
)


class ModelManager:
    """
    Grok 模型管理器

    负责获取和管理可用模型列表。
    """

    def __init__(self, api_key: str, base_url: str, timeout: float = 30.0):
        """
        初始化模型管理器

        Args:
            api_key: API key for Bearer auth
            base_url: grok2api base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.info("[Grok ModelManager] Initialized")

    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表

        Returns:
            ModelConfig 对象列表
        """
        try:
            logger.info("[Grok ModelManager] Fetching available models")

            url = f"{self.base_url}/models"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            result = []
            seen_model_ids = set()
            for model_data in data.get("data", []):
                model_id = str(model_data.get("id", "")).strip()
                if not model_id or model_id in seen_model_ids:
                    continue
                if not self._is_supported_model(model_id):
                    continue
                seen_model_ids.add(model_id)

                config = build_model_config("grok", model_id)
                config.name = DISPLAY_NAMES.get(model_id, config.name)
                config.description = DESCRIPTIONS.get(model_id, config.description)
                config.capabilities = self._get_capabilities(model_id)
                config.traits = get_model_traits(
                    provider="grok",
                    model_id=model_id,
                    capabilities=config.capabilities,
                    model_name=config.name,
                )
                result.append(config)

            result.sort(key=lambda item: (str(item.name or "").lower(), str(item.id or "").lower()))
            logger.info(f"[Grok ModelManager] Found {len(result)} models")

            return result

        except Exception as e:
            logger.error(f"[Grok ModelManager] Error fetching models: {e}", exc_info=True)
            raise

    def _is_supported_model(self, model_id: str) -> bool:
        """Check if model is supported (skip embedding, tts, etc.)."""
        lower_id = model_id.lower()
        return not any(token in lower_id for token in UNSUPPORTED_MODEL_TOKENS)

    def _get_capabilities(self, model_id: str) -> Capabilities:
        """Get capabilities for a Grok model."""
        lower_id = model_id.lower()

        # Image models
        if lower_id in IMAGE_MODEL_IDS or lower_id in IMAGE_EDIT_MODEL_IDS:
            return Capabilities(vision=True)

        # Video models
        if lower_id in VIDEO_MODEL_IDS:
            return Capabilities(vision=True)

        # Chat models with thinking
        if "thinking" in lower_id or "expert" in lower_id or "heavy" in lower_id:
            return Capabilities(vision=True, reasoning=True)

        # Mini thinking models
        if "mini" in lower_id:
            return Capabilities(vision=True, reasoning=True)

        # Standard chat models (grok-3, grok-4, etc.)
        if any(lower_id.startswith(prefix) for prefix in CHAT_MODEL_PREFIXES):
            return Capabilities(vision=True)

        return Capabilities()
