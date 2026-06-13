from __future__ import annotations

import logging

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers.models import providers


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(providers.router)
    return TestClient(app)


def test_provider_templates_success(monkeypatch) -> None:
    monkeypatch.setattr(
        providers.ProviderConfig,
        "get_provider_templates",
        staticmethod(lambda: [{"id": "google", "name": "Google"}]),
    )

    with _client() as client:
        response = client.get("/api/providers/templates")

    assert response.status_code == 200
    assert response.json() == [{"id": "google", "name": "Google"}]


def test_provider_templates_internal_error_is_generic(monkeypatch, caplog) -> None:
    secret = "provider-template-secret"

    def boom():
        raise RuntimeError(f"template load failed {secret}")

    monkeypatch.setattr(providers.ProviderConfig, "get_provider_templates", staticmethod(boom))

    with _client() as client:
        with caplog.at_level(logging.ERROR, logger=providers.logger.name):
            response = client.get("/api/providers/templates")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to load provider templates"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
