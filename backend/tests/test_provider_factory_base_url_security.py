import pytest

from app.services.common import provider_factory as provider_factory_mod
from app.services.common.errors import ClientCreationError
from app.services.common.provider_factory import ProviderFactory
from app.utils.url_security import UnsafeURLError


class _FakeProvider:
    def __init__(self, api_key, api_url=None, **kwargs):
        self.api_key = api_key
        self.api_url = api_url
        self.kwargs = kwargs


@pytest.fixture()
def fake_provider_registry(monkeypatch):
    monkeypatch.setattr(ProviderFactory, "_initialized", True)
    monkeypatch.setattr(ProviderFactory, "_providers", {"openai": _FakeProvider})
    monkeypatch.setattr(ProviderFactory, "_client_cache", {})


def test_provider_factory_validates_custom_openai_base_url(monkeypatch, fake_provider_registry):
    calls = []

    def fake_validate(url):
        calls.append(url)
        return url

    monkeypatch.setattr(provider_factory_mod, "validate_storage_egress_url", fake_validate)

    service = ProviderFactory.create(
        "openai",
        api_key="test-key",
        api_url="https://proxy.example.test/v1",
    )

    assert service.api_url == "https://proxy.example.test/v1"
    assert calls == ["https://proxy.example.test/v1"]


def test_provider_factory_does_not_validate_official_default(monkeypatch, fake_provider_registry):
    def fail_if_called(url):
        raise AssertionError(f"default URL should not be revalidated: {url}")

    monkeypatch.setattr(provider_factory_mod, "validate_storage_egress_url", fail_if_called)

    service = ProviderFactory.create(
        "openai",
        api_key="test-key",
        api_url="https://api.openai.com/v1",
    )

    assert service.api_url == "https://api.openai.com/v1"


def test_provider_factory_preserves_ollama_local_default_variants(monkeypatch):
    def fail_if_called(url):
        raise AssertionError(f"trusted local default should not be revalidated: {url}")

    monkeypatch.setattr(provider_factory_mod, "validate_storage_egress_url", fail_if_called)

    assert (
        ProviderFactory._validate_provider_api_url("ollama", "http://localhost:11434")
        == "http://localhost:11434"
    )
    assert (
        ProviderFactory._validate_provider_api_url("ollama", "http://127.0.0.1:11434/v1")
        == "http://127.0.0.1:11434/v1"
    )


def test_provider_factory_rejects_non_default_loopback_override(fake_provider_registry):
    with pytest.raises(ClientCreationError) as exc_info:
        ProviderFactory.create(
            "openai",
            api_key="test-key",
            api_url="http://127.0.0.1:8000/v1",
    )

    assert isinstance(exc_info.value.original_error, UnsafeURLError)
    assert "path_len=" in exc_info.value.context.additional_context["api_url"]
    assert "/v1" not in exc_info.value.context.additional_context["api_url"]
