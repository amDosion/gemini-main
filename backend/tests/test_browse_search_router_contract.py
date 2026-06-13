from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tools import browse


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(browse.router)
    app.dependency_overrides[browse.require_current_user] = lambda: "user-1"
    monkeypatch.setattr(
        browse,
        "_web_search",
        lambda query: [{"title": "Result", "url": f"https://example.test/?q={query}"}],
    )
    return TestClient(app)


def test_web_search_response_model_and_query_bounds(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post("/api/search", params={"query": "gemini"})

    assert response.status_code == 200
    assert response.json() == {
        "results": [{"title": "Result", "url": "https://example.test/?q=gemini"}]
    }


def test_web_search_rejects_empty_query(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post("/api/search", params={"query": ""})

    assert response.status_code == 422


def test_web_search_internal_error_is_generic(monkeypatch, caplog):
    secret = "browse-search-secret"

    def _boom(query):
        raise RuntimeError(f"search failed {secret}")

    with _client(monkeypatch) as client:
        monkeypatch.setattr(browse, "_web_search", _boom)
        with caplog.at_level(logging.ERROR, logger=browse.logger.name):
            response = client.post("/api/search", params={"query": "gemini"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Web search failed"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
