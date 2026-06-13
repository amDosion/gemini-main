from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ai import interactions


class FakeInteractionsManager:
    def __init__(self):
        self.deleted = []

    async def delete_interaction(self, **kwargs):
        self.deleted.append(kwargs)

    async def stream_existing_interaction(self, **kwargs):
        assert kwargs["interaction_id"] == "interaction-1"
        assert kwargs["last_event_id"] == "event-0"
        assert kwargs["include_input"] is True
        yield {
            "event_id": "event-1",
            "event_type": "interaction.complete",
            "final_text": "done",
        }


def _client(monkeypatch, manager):
    app = FastAPI()
    app.include_router(interactions.router)
    app.dependency_overrides[interactions.require_current_user] = lambda: "user-1"
    app.dependency_overrides[interactions.get_db] = lambda: object()

    async def fake_resolve(**kwargs):
        assert kwargs["provider_id"] == "google"
        assert kwargs["user_id"] == "user-1"
        return "google-key", {}

    monkeypatch.setattr(interactions.credentials_resolver, "resolve", fake_resolve)
    monkeypatch.setattr(interactions, "get_interactions_manager", lambda **kwargs: manager)
    return TestClient(app)


def test_delete_interaction_response_model(monkeypatch):
    manager = FakeInteractionsManager()
    with _client(monkeypatch, manager) as client:
        response = client.delete("/api/interactions/interaction-1")

    assert response.status_code == 200
    assert response.json() == {"message": "Interaction deleted successfully"}
    assert manager.deleted == [
        {
            "api_key": "google-key",
            "interaction_id": "interaction-1",
            "vertexai": True,
        }
    ]


def test_stream_interaction_returns_sse(monkeypatch):
    manager = FakeInteractionsManager()
    with _client(monkeypatch, manager) as client:
        response = client.get(
            "/api/interactions/interaction-1/stream?last_event_id=event-0&include_input=true"
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: event-1" in response.text
    assert '"eventType": "interaction.complete"' in response.text
    assert '"finalText": "done"' in response.text
