from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tools import live_api


class FakeLiveAPIHandler:
    def __init__(self, db):
        self.db = db

    async def query(self, **kwargs):
        assert kwargs == {
            "user_id": "user-1",
            "input_data": "hello",
            "agent_id": "agent-1",
        }
        return {
            "output": "done",
            "status": "completed",
            "runtime": "adapter",
            "model": "google/gemini-2.5-flash",
            "usage": {"input_tokens": 1},
            "extra_payload": {"ok": True},
        }

    async def stream_query(self, **kwargs):
        assert kwargs == {
            "user_id": "user-1",
            "input_data": "hello",
            "agent_id": "agent-1",
        }
        yield {
            "event_type": "chunk",
            "partial_text": "hi",
        }


def _client(monkeypatch, handler=FakeLiveAPIHandler):
    app = FastAPI()
    app.include_router(live_api.router)
    app.dependency_overrides[live_api.require_current_user] = lambda: "user-1"
    app.dependency_overrides[live_api.get_db] = lambda: object()
    monkeypatch.setattr(live_api, "LiveAPIHandler", handler)
    return TestClient(app)


def test_live_query_response_model_filters_extra_json(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/live/query",
            json={"input": "hello", "agent_id": "agent-1"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "output": "done",
        "status": "completed",
        "runtime": "adapter",
        "model": "google/gemini-2.5-flash",
        "agent_id": None,
        "agent_name": None,
        "session_id": None,
        "invocation_id": None,
        "usage": {"input_tokens": 1},
        "event_count": None,
    }


def test_live_stream_query_returns_sse(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/live/stream-query",
            json={"input": "hello", "agent_id": "agent-1"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"eventType": "chunk"' in response.text
    assert '"partialText": "hi"' in response.text


def test_live_query_internal_error_is_generic(monkeypatch, caplog):
    secret = "live-query-secret"

    class BoomLiveAPIHandler(FakeLiveAPIHandler):
        async def query(self, **kwargs):
            raise RuntimeError(f"live query failed {secret}")

    with _client(monkeypatch, handler=BoomLiveAPIHandler) as client:
        with caplog.at_level(logging.ERROR, logger=live_api.logger.name):
            response = client.post(
                "/api/live/query",
                json={"input": "hello", "agent_id": "agent-1"},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Live API query failed"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted query_error; length=" in caplog.text
