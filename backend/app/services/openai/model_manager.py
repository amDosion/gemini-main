"""
OpenAI 模型管理器

处理 OpenAI 的模型列表获取。
"""
from __future__ import annotations

from typing import List, Optional
import logging
from openai import AsyncOpenAI

from ..common.model_capabilities import (
    Capabilities,
    ModelConfig,
    build_model_config,
    get_model_traits,
)

logger = logging.getLogger(__name__)

UNSUPPORTED_MODEL_TOKENS = (
    "embedding",
    "moderation",
    "realtime",
    "transcribe",
    "transcription",
)
UNSUPPORTED_MODEL_PREFIXES = (
    "whisper",
)


class ModelManager:
    """
    OpenAI 模型管理器
    
    负责获取和管理可用模型列表。
    """
    
    def __init__(self, client: AsyncOpenAI):
        """
        初始化模型管理器
        
        Args:
            client: AsyncOpenAI 客户端实例
        """
        self.client = client
        logger.info("[OpenAI ModelManager] Initialized")
    
    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表
        
        Returns:
            ModelConfig 对象列表
        """
        try:
            logger.info("[OpenAI ModelManager] Fetching available models")
            
            # Get models from OpenAI API
            models = await self.client.models.list()

            result = []
            seen_model_ids = set()
            for model in models.data:
                model_id = str(getattr(model, "id", "") or "").strip()
                if not model_id or model_id in seen_model_ids:
                    continue
                if not self._is_supported_model(model_id):
                    logger.debug("[OpenAI ModelManager] Skipping unsupported model id=%s", model_id)
                    continue
                seen_model_ids.add(model_id)

                config = build_model_config("openai", model_id)
                config.name = self._build_display_name(model_id, fallback=config.name)
                config.description = self._build_description(model_id, fallback=config.description)
                config.capabilities = self._merge_capabilities(model_id, config.capabilities)
                config.context_window = self._resolve_context_window(model_id, config.context_window)
                config.traits = get_model_traits(
                    provider="openai",
                    model_id=model_id,
                    capabilities=config.capabilities,
                    model_name=config.name,
                )
                result.append(config)

            result.sort(key=lambda item: (str(item.name or "").lower(), str(item.id or "").lower()))
            logger.info(f"[OpenAI ModelManager] Found {len(result)} models")
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI ModelManager] Error fetching models: {e}", exc_info=True)
            raise

    def _build_display_name(self, model_id: str, fallback: str) -> str:
        lower_id = str(model_id or "").strip().lower()

        exact_names = {
            "gpt-4o": "GPT-4o",
            "gpt-4o-mini": "GPT-4o Mini",
            "gpt-4o-tts": "GPT-4o TTS",
            "gpt-4o-mini-tts": "GPT-4o Mini TTS",
            "gpt-4.1": "GPT-4.1",
            "gpt-4.1-mini": "GPT-4.1 Mini",
            "gpt-4.1-nano": "GPT-4.1 Nano",
            "gpt-4.5-preview": "GPT-4.5 Preview",
            "gpt-5": "GPT-5",
            "gpt-5-chat-latest": "GPT-5 Chat Latest",
            "gpt-5-mini": "GPT-5 Mini",
            "gpt-5-nano": "GPT-5 Nano",
            "gpt-5.1": "GPT-5.1",
            "gpt-image-1": "GPT Image 1",
            "gpt-image-1-mini": "GPT Image 1 Mini",
            "gpt-image-1.5": "GPT Image 1.5",
            "gpt-image-1.5-mini": "GPT Image 1.5 Mini",
            "dall-e-2": "DALL-E 2",
            "dall-e-3": "DALL-E 3",
            "tts-1": "TTS 1",
            "tts-1-hd": "TTS 1 HD",
            "whisper-1": "Whisper 1",
            "sora-2": "Sora 2",
            "sora-2-pro": "Sora 2 Pro",
            "sora-2-preview": "Sora 2 Preview",
            "sora-2-pro-preview": "Sora 2 Pro Preview",
            "codex-mini-latest": "Codex Mini Latest",
            "o1": "o1",
            "o1-mini": "o1 Mini",
            "o1-pro": "o1 Pro",
            "o3": "o3",
            "o3-mini": "o3 Mini",
            "o3-pro": "o3 Pro",
            "o3-deep-research": "o3 Deep Research",
            "o4-mini": "o4 Mini",
            "o4-mini-deep-research": "o4 Mini Deep Research",
        }
        if lower_id in exact_names:
            return exact_names[lower_id]

        if "codex" in lower_id:
            return self._title_tokens(model_id, token_map={"codex": "Codex", "mini": "Mini", "max": "Max", "latest": "Latest"})
        if lower_id.startswith("tts-"):
            return self._title_tokens(model_id, token_map={"tts": "TTS", "hd": "HD"})
        if lower_id.startswith("sora-"):
            return self._title_tokens(model_id, token_map={"sora": "Sora", "pro": "Pro", "preview": "Preview"})
        if lower_id.startswith("whisper-"):
            return self._title_tokens(model_id, token_map={"whisper": "Whisper"})

        return fallback

    def _build_description(self, model_id: str, fallback: str) -> str:
        lower_id = str(model_id or "").strip().lower()

        if lower_id.startswith("sora"):
            if "pro" in lower_id:
                return "Advanced video generation model with synced audio."
            return "Video generation model with synced audio."

        if lower_id.startswith("gpt-image"):
            return "State-of-the-art image generation model."

        if lower_id.startswith("dall-e") or lower_id.startswith("dalle"):
            return "Image generation model for creating images from text prompts."

        if lower_id.endswith("-tts") or "-tts-" in lower_id:
            return "Text-to-speech model powered by GPT voice synthesis."

        if lower_id.startswith("tts-1-hd"):
            return "Text-to-speech model optimized for quality."

        if lower_id.startswith("tts"):
            return "Text-to-speech model optimized for speed."

        if "whisper" in lower_id or "transcribe" in lower_id:
            return "Speech-to-text transcription model."

        if "codex" in lower_id or "-code" in lower_id:
            return "Coding model optimized for software engineering and agentic code tasks."

        if lower_id.startswith("gpt-5"):
            return "Flagship reasoning model with image input support."

        if lower_id.startswith("gpt-4.1"):
            return "Multimodal chat model with image input support."

        if lower_id.startswith("gpt-4o") or lower_id.startswith("chatgpt-4o"):
            return "Fast multimodal chat model with image input support."

        return fallback

    def _merge_capabilities(self, model_id: str, capabilities: Capabilities) -> Capabilities:
        lower_id = str(model_id or "").strip().lower()
        merged = capabilities.model_copy(deep=True)

        is_audio_variant = any(token in lower_id for token in ("audio", "transcribe", "tts", "realtime"))

        if lower_id.startswith("gpt-image") or lower_id.startswith("dall-e") or lower_id.startswith("dalle"):
            merged.vision = True

        if lower_id.startswith("gpt-4.1") or lower_id.startswith("gpt-4.5"):
            merged.vision = True

        if (lower_id.startswith("gpt-4o") or lower_id.startswith("chatgpt-4o")) and not is_audio_variant:
            merged.vision = True

        if lower_id.startswith("gpt-5"):
            merged.reasoning = True
            if not is_audio_variant:
                merged.vision = True

        if lower_id.startswith(("o1", "o3", "o4")):
            merged.reasoning = True
            if lower_id.startswith("o4-mini"):
                merged.vision = False

        if "codex" in lower_id or "-code" in lower_id:
            merged.coding = True

        return merged

    def _resolve_context_window(self, model_id: str, fallback: Optional[int]) -> Optional[int]:
        lower_id = str(model_id or "").strip().lower()
        if lower_id.startswith("gpt-4.1"):
            return 1_047_576
        if lower_id.startswith("gpt-5"):
            return 400_000
        return fallback

    def _is_supported_model(self, model_id: str) -> bool:
        lower_id = str(model_id or "").strip().lower()
        if not lower_id:
            return False
        if lower_id.startswith(UNSUPPORTED_MODEL_PREFIXES):
            return False
        return not any(token in lower_id for token in UNSUPPORTED_MODEL_TOKENS)

    def _title_tokens(self, model_id: str, token_map: Optional[dict] = None) -> str:
        replacements = token_map or {}
        parts = []
        for token in str(model_id or "").replace("_", "-").split("-"):
            if not token:
                continue
            lowered = token.lower()
            if lowered in replacements:
                parts.append(replacements[lowered])
            else:
                parts.append(token.capitalize())
        return " ".join(parts)
