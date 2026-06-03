"""Factory for provider-specific LLM adapters."""

from typing import Any, Dict, Type

from ..common.provider_config import ProviderConfig
from .adapters.base import LLMAdapter
from .adapters.google_adapter import GoogleLLMAdapter
from .adapters.openai_adapter import OpenAILLMAdapter
from .adapters.tongyi_adapter import TongyiLLMAdapter
from .adapters.ollama_adapter import OllamaLLMAdapter


class LLMAdapterFactory:
    """Create adapters by provider family."""

    _ADAPTERS: Dict[str, Type[LLMAdapter]] = {
        "google": GoogleLLMAdapter,
        "openai": OpenAILLMAdapter,
        "tongyi": TongyiLLMAdapter,
        "ollama": OllamaLLMAdapter,
    }

    @classmethod
    def provider_family(cls, provider_id: str) -> str:
        lowered = str(provider_id or "").strip().lower()
        configured_client_type = ""
        try:
            configured_client_type = str(ProviderConfig.get_client_type(lowered) or "").strip().lower()
        except Exception:
            configured_client_type = ""

        if configured_client_type == "google":
            return "google"
        # grok exposes an OpenAI-compatible API (grok2api), so its dedicated
        # client_type maps onto the OpenAI adapter family.
        if configured_client_type in ("openai", "grok"):
            return "openai"
        if configured_client_type == "ollama":
            return "ollama"
        if configured_client_type == "dashscope":
            return "tongyi"

        if lowered.startswith("google"):
            return "google"
        if lowered.startswith("openai") or lowered.startswith("grok"):
            return "openai"
        if lowered.startswith("ollama"):
            return "ollama"
        if lowered in ("tongyi", "dashscope") or lowered.startswith("tongyi") or lowered.startswith("dashscope"):
            return "tongyi"
        return ""

    @classmethod
    def create(cls, provider_id: str, provider_service: Any) -> LLMAdapter:
        family = cls.provider_family(provider_id)
        adapter_cls = cls._ADAPTERS.get(family)
        if adapter_cls is None:
            raise ValueError(
                f"不支持的 LLM 提供商: {provider_id}。"
                "支持: google, openai (含 grok 等 OpenAI 兼容提供商), tongyi, ollama。"
            )
        return adapter_cls(provider_service)
