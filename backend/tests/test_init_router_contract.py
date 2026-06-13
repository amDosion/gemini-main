from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.user import init as init_router


def _client():
    app = FastAPI()
    app.include_router(init_router.router)
    app.dependency_overrides[init_router.require_current_user] = lambda: "user-1"
    app.dependency_overrides[init_router.get_db] = lambda: object()
    return TestClient(app)


def test_init_critical_response_model(monkeypatch):
    from app.services.common import init_service

    async def fake_profiles(user_id, db):
        assert user_id == "user-1"
        return {
            "profiles": [{"id": "profile-1", "provider_id": "google"}],
            "active_profile_id": None,
            "active_profile": None,
            "dashscope_key": "",
        }

    monkeypatch.setattr(init_service, "_query_profiles", fake_profiles)

    with _client() as client:
        response = client.get("/api/init/critical")

    assert response.status_code == 200
    body = response.json()
    assert body["profiles"][0]["id"] == "profile-1"
    assert body["cached_mode_catalog"] == []


def test_init_critical_internal_error_logs_summary(monkeypatch, caplog):
    secret = "init-critical-secret"
    from app.services.common import init_service

    async def boom_profiles(user_id, db):
        raise RuntimeError(f"critical failed {secret}")

    monkeypatch.setattr(init_service, "_query_profiles", boom_profiles)

    with _client() as client:
        with caplog.at_level(logging.ERROR, logger=init_router.logger.name):
            response = client.get("/api/init/critical")

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Failed to load critical initialization data. Please try again later."
    )
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
    assert "<redacted user_id; length=" in caplog.text


def test_init_more_sessions_response_model(monkeypatch):
    from app.services.common import init_service

    async def fake_sessions(user_id, db, limit=20, offset=0, cursor=None, mode=None):
        assert (user_id, limit, offset, cursor, mode) == ("user-1", 5, 0, None, "chat")
        return {
            "sessions": [{"id": "session-1", "messages": []}],
            "total": 10,
            "has_more": True,
            "next_cursor": "1000:session-1",
        }

    monkeypatch.setattr(init_service, "_query_sessions_metadata_only", fake_sessions)

    with _client() as client:
        response = client.get("/api/init/sessions/more?limit=5&mode=chat")

    assert response.status_code == 200
    assert response.json()["hasMore"] is True
    assert response.json()["nextCursor"] == "1000:session-1"


def test_init_more_sessions_internal_error_logs_summary(monkeypatch, caplog):
    secret = "init-more-sessions-secret"
    from app.services.common import init_service

    async def boom_sessions(user_id, db, limit=20, offset=0, cursor=None, mode=None):
        raise RuntimeError(f"more sessions failed {secret}")

    monkeypatch.setattr(init_service, "_query_sessions_metadata_only", boom_sessions)

    with _client() as client:
        with caplog.at_level(logging.ERROR, logger=init_router.logger.name):
            response = client.get("/api/init/sessions/more?limit=5&mode=chat")

    assert response.status_code == 503
    assert response.json()["detail"] == "Failed to load more sessions"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
    assert "<redacted user_id; length=" in caplog.text


def test_init_non_critical_response_model(monkeypatch):
    from app.services.common import init_service

    async def fake_sessions(user_id, db, limit=20, mode=None):
        assert (user_id, limit, mode) == ("user-1", 20, "chat")
        return {"sessions": [{"id": "session-1"}], "total": 1, "has_more": False}

    async def fake_personas(user_id, db):
        return {"personas": [{"id": "persona-1"}]}

    async def fake_storage(user_id, db):
        return {"storage_configs": [{"id": "storage-1"}], "active_storage_id": "storage-1"}

    async def fake_vertex(user_id, db):
        return {"imagen_config": {"api_mode": "gemini_api"}}

    monkeypatch.setattr(init_service, "_query_sessions_with_first_messages", fake_sessions)
    monkeypatch.setattr(init_service, "_query_personas", fake_personas)
    monkeypatch.setattr(init_service, "_query_storage_configs", fake_storage)
    monkeypatch.setattr(init_service, "_query_vertex_ai_config", fake_vertex)

    with _client() as client:
        response = client.get("/api/init/non-critical?mode=chat")

    assert response.status_code == 200
    body = response.json()
    assert body["sessionsTotal"] == 1
    assert body["activeStorageId"] == "storage-1"
    assert body["imagenConfig"] == {"api_mode": "gemini_api"}


def test_init_non_critical_partial_error_logs_summary(monkeypatch, caplog):
    secret = "init-non-critical-secret"
    from app.services.common import init_service

    async def boom_sessions(user_id, db, limit=20, mode=None):
        raise RuntimeError(f"sessions failed {secret}")

    async def fake_personas(user_id, db):
        return {"personas": []}

    async def fake_storage(user_id, db):
        return {"storage_configs": [], "active_storage_id": None}

    async def fake_vertex(user_id, db):
        return {"imagen_config": None}

    monkeypatch.setattr(init_service, "_query_sessions_with_first_messages", boom_sessions)
    monkeypatch.setattr(init_service, "_query_personas", fake_personas)
    monkeypatch.setattr(init_service, "_query_storage_configs", fake_storage)
    monkeypatch.setattr(init_service, "_query_vertex_ai_config", fake_vertex)

    with _client() as client:
        with caplog.at_level(logging.WARNING, logger=init_router.logger.name):
            response = client.get("/api/init/non-critical?mode=chat")

    assert response.status_code == 200
    assert response.json()["sessions"] == []
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_init_legacy_response_model(monkeypatch):
    async def fake_init_data(user_id, db):
        assert user_id == "user-1"
        return {
            "profiles": [],
            "active_profile_id": None,
            "active_profile": None,
            "dashscope_key": "",
            "storage_configs": [],
            "active_storage_id": None,
            "sessions": [],
            "personas": [],
            "imagen_config": None,
            "vertex_ai_config": {"api_mode": "gemini_api"},
            "cached_models": None,
            "_metadata": {
                "timestamp": 1_765_497_600_000,
                "partial_failures": [],
            },
        }

    monkeypatch.setattr(init_router, "get_init_data", fake_init_data)

    with _client() as client:
        response = client.get("/api/init")

    assert response.status_code == 200
    body = response.json()
    assert body["_metadata"]["partial_failures"] == []
    assert body["vertex_ai_config"] == {"api_mode": "gemini_api"}


def test_init_legacy_internal_error_logs_summary(monkeypatch, caplog):
    secret = "init-legacy-secret"

    async def boom_init_data(user_id, db):
        raise RuntimeError(f"legacy init failed {secret}")

    monkeypatch.setattr(init_router, "get_init_data", boom_init_data)

    with _client() as client:
        with caplog.at_level(logging.ERROR, logger=init_router.logger.name):
            response = client.get("/api/init")

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Failed to load initialization data. Please try again later."
    )
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
    assert "<redacted user_id; length=" in caplog.text
