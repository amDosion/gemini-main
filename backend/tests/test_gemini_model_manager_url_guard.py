import logging

import pytest

from app.services.gemini.common import model_manager as model_manager_mod
from app.services.gemini.common.model_manager import ModelManager
from app.utils.url_security import UnsafeURLError


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_gemini_model_manager_uses_guard_for_custom_api_url(monkeypatch, caplog):
    calls = []

    def fake_guard(url, *, headers, timeout, max_redirects):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "max_redirects": max_redirects,
            }
        )
        return _FakeResponse(
            '{"models":[{"name":"models/gemini-2.5-flash","displayName":"Flash"}]}'
        )

    monkeypatch.setattr(model_manager_mod, "sync_get_with_redirect_guard", fake_guard)

    manager = ModelManager(
        api_key="secret-key",
        api_url="https://proxy.example.com/custom/v1beta",
    )

    with caplog.at_level(logging.INFO, logger=model_manager_mod.logger.name):
        models = await manager.get_available_models()

    assert [model.id for model in models] == ["gemini-2.5-flash"]
    assert calls == [
        {
            "url": "https://proxy.example.com/custom/v1beta/models",
            "headers": {
                "x-goog-api-key": "secret-key",
                "Accept": "application/json",
            },
            "timeout": 10.0,
            "max_redirects": 5,
        }
    ]
    assert "custom/v1beta" not in caplog.text
    assert "https://proxy.example.com path_len=" in caplog.text


@pytest.mark.asyncio
async def test_gemini_model_manager_blocks_unsafe_custom_api_url(monkeypatch):
    def fake_guard(url, *, headers, timeout, max_redirects):
        raise UnsafeURLError("URL 指向受限地址")

    monkeypatch.setattr(model_manager_mod, "sync_get_with_redirect_guard", fake_guard)

    manager = ModelManager(
        api_key="secret-key",
        api_url="http://127.0.0.1/v1beta",
    )

    with pytest.raises(RuntimeError, match="blocked by outbound URL policy"):
        await manager.get_available_models()
