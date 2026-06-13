from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.user import personas


class FakePersona:
    def __init__(self, persona_id: str, created_at: int):
        self.id = persona_id
        self.created_at = created_at


class FakePersonaQuery:
    def __init__(self):
        self.deleted = False

    def delete(self):
        self.deleted = True


class FakeUserScopedQuery:
    last_query = None

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        self.query_obj = FakePersonaQuery()
        FakeUserScopedQuery.last_query = self

    def get_all(self, model):
        return [FakePersona("persona-1", 123)]

    def query(self, model):
        return self.query_obj


class FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, persona):
        self.added.append(persona)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _client(db: FakeDb, monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(personas.router)
    app.dependency_overrides[personas.require_current_user] = lambda: "user-1"
    app.dependency_overrides[personas.get_db] = lambda: db
    monkeypatch.setattr(personas, "UserScopedQuery", FakeUserScopedQuery)
    return TestClient(app)


def test_save_personas_response_model_and_body_limit(monkeypatch):
    db = FakeDb()
    with _client(db, monkeypatch) as client:
        response = client.post(
            "/api/personas",
            json=[
                {
                    "id": "persona-1",
                    "name": "Analyst",
                    "description": "Reads data",
                    "systemPrompt": "Be precise",
                    "icon": "chart",
                    "category": "work",
                }
            ],
        )

    assert response.status_code == 200
    assert response.json() == {"success": True, "count": 1}
    assert db.committed is True
    assert FakeUserScopedQuery.last_query.query_obj.deleted is True
    assert db.added[0].user_id == "user-1"
    assert db.added[0].system_prompt == "Be precise"


def test_save_personas_rejects_over_large_batch(monkeypatch):
    db = FakeDb()
    with _client(db, monkeypatch) as client:
        response = client.post("/api/personas", json=[{}] * 10_001)

    assert response.status_code == 422
    assert db.committed is False


def test_save_personas_internal_error_is_generic(monkeypatch, caplog):
    secret = "persona-save-secret"
    db = FakeDb()

    def _boom():
        raise RuntimeError(f"commit failed {secret}")

    monkeypatch.setattr(db, "commit", _boom)
    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=personas.logger.name):
            response = client.post(
                "/api/personas",
                json=[
                    {
                        "id": "persona-1",
                        "name": "Analyst",
                        "description": "Reads data",
                        "systemPrompt": "Be precise",
                        "icon": "chart",
                        "category": "work",
                    }
                ],
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to save personas"
    assert db.rolled_back is True
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_reset_personas_internal_error_is_generic(monkeypatch, caplog):
    secret = "persona-reset-secret"
    db = FakeDb()

    def _boom(user_id, db):
        raise RuntimeError(f"reset failed {secret}")

    monkeypatch.setattr(personas, "create_default_personas", _boom)
    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=personas.logger.name):
            response = client.post("/api/personas/reset")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to reset personas"
    assert db.rolled_back is True
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
