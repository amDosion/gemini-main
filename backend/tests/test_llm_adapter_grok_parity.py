"""Regression tests guarding LLM adapter / provider registry parity.

Finding A1 (HIGH): ``grok`` is declared in both ``ProviderConfig`` and
``ProviderFactory`` but was missing from ``LLMAdapterFactory``'s family
resolver, so resolving a grok adapter raised ``ValueError`` at runtime and
crashed any agent workflow that selected grok.

Finding T5 (drift guard): every provider declared in ``ProviderConfig`` /
registered in ``ProviderFactory`` must also resolve to a concrete adapter in
``LLMAdapterFactory``. This parity test fails loudly if a future provider is
added to one registry but forgotten in the other.
"""

from typing import Any

import pytest

from app.services.common.provider_config import ProviderConfig
from app.services.common.provider_factory import ProviderFactory
from app.services.llm.adapter_factory import LLMAdapterFactory
from app.services.llm.adapters.openai_adapter import OpenAILLMAdapter


class _StubService:
    """Minimal stand-in for a provider service (adapter only stores it)."""

    async def chat(self, *args: Any, **kwargs: Any) -> dict:  # pragma: no cover
        return {"content": "", "raw": None}


def _config_provider_ids() -> list[str]:
    return list(ProviderConfig.CONFIGS.keys())


# --- (b) grok specifically resolves to an OpenAI-compatible adapter ---------


def test_grok_resolves_to_openai_family_without_value_error():
    """grok must resolve to the OpenAI family (it uses an OpenAI-compatible API)."""
    family = LLMAdapterFactory.provider_family("grok")
    assert family == "openai", (
        f"Expected grok -> 'openai' family, got {family!r}. "
        "Grok uses an OpenAI-compatible API and must map to OpenAILLMAdapter."
    )


def test_grok_create_returns_openai_adapter_without_value_error():
    """LLMAdapterFactory.create('grok', ...) must not raise ValueError."""
    adapter = LLMAdapterFactory.create("grok", _StubService())
    assert isinstance(adapter, OpenAILLMAdapter)


def test_grok_client_type_is_resolvable():
    """Sanity: grok's declared client_type must map to a known adapter family."""
    client_type = ProviderConfig.get_client_type("grok")
    assert client_type == "grok"
    # The family resolver must understand the declared client_type.
    assert LLMAdapterFactory.provider_family("grok") != ""


# --- (a) registry parity: every declared provider resolves to an adapter ----


@pytest.mark.parametrize("provider_id", _config_provider_ids())
def test_every_config_provider_resolves_to_an_adapter_family(provider_id: str):
    """Every provider in ProviderConfig.CONFIGS must resolve to a non-empty family.

    The custom/empty-id placeholder ``custom`` is OpenAI-compatible and resolves
    via its declared client_type, so no provider should fall through to ``""``.
    """
    family = LLMAdapterFactory.provider_family(provider_id)
    assert family in LLMAdapterFactory._ADAPTERS, (
        f"Provider {provider_id!r} resolves to family {family!r}, which has no "
        f"adapter. Known adapter families: {sorted(LLMAdapterFactory._ADAPTERS)}"
    )


@pytest.mark.parametrize("provider_id", _config_provider_ids())
def test_every_config_provider_create_does_not_raise(provider_id: str):
    """LLMAdapterFactory.create must succeed for every declared provider."""
    adapter = LLMAdapterFactory.create(provider_id, _StubService())
    assert adapter is not None


def test_registered_providers_all_have_adapters():
    """Every provider ProviderFactory actually registers must have an adapter.

    This is the strongest drift guard: it walks the live registry (subject to
    optional SDK availability) rather than only the static config.
    """
    registered = ProviderFactory.list_providers()
    assert registered, "ProviderFactory registered no providers"
    missing = [
        provider_id
        for provider_id in registered
        if LLMAdapterFactory.provider_family(provider_id) not in LLMAdapterFactory._ADAPTERS
    ]
    assert not missing, (
        f"Providers registered in ProviderFactory but missing an LLM adapter: {missing}"
    )
