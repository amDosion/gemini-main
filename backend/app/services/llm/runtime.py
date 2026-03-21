"""Provider-agnostic LLM runtime for agent workflows."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..common.provider_factory import ProviderFactory
from .adapter_factory import LLMAdapterFactory
from .adapters.base import LLMAdapter
from .credentials_resolver import ProviderCredentialsResolver


class LLMRuntime:
    """Shared runtime that resolves credentials, provider service, and adapter."""

    def __init__(
        self,
        user_id: str,
        db: Session,
        credentials_resolver: ProviderCredentialsResolver | None = None,
    ):
        self.user_id = user_id
        self.db = db
        self.credentials_resolver = credentials_resolver or ProviderCredentialsResolver()
        self._adapter_cache: Dict[str, LLMAdapter] = {}

    async def get_adapter(self, provider_id: str, profile_id: Optional[str] = None) -> LLMAdapter:
        normalized_provider = str(provider_id or "").strip()
        normalized_profile = str(profile_id or "").strip()
        cache_key = f"{normalized_provider}::{normalized_profile or '__active__'}"
        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        api_key, base_url = await self.credentials_resolver.resolve(
            provider_id=normalized_provider,
            db=self.db,
            user_id=self.user_id,
            profile_id=normalized_profile or None,
        )

        provider_service = ProviderFactory.create(
            provider=normalized_provider,
            api_key=api_key,
            api_url=base_url,
            user_id=self.user_id,
            db=self.db,
        )
        adapter = LLMAdapterFactory.create(normalized_provider, provider_service)
        self._adapter_cache[cache_key] = adapter
        return adapter

    async def chat(
        self,
        provider_id: str,
        model_id: str,
        messages: List[Dict[str, Any]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        adapter = await self.get_adapter(provider_id, profile_id=profile_id)
        return await adapter.chat(
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
