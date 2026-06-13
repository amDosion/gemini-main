from __future__ import annotations

import logging
import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.models import vertex_ai_config


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.db.config


class FakeDb:
    def __init__(self):
        self.config = None
        self.committed = False
        self.rolled_back = False
        self.query_error = None
        self.commit_error = None

    def query(self, *args, **kwargs):
        if self.query_error:
            raise self.query_error
        return FakeQuery(self)

    def add(self, config):
        self.config = config

    def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def refresh(self, config):
        return None

    def rollback(self):
        self.rolled_back = True


def _client(db: FakeDb, monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(vertex_ai_config.router)
    app.dependency_overrides[vertex_ai_config.require_current_user] = lambda: "user-1"
    app.dependency_overrides[vertex_ai_config.get_db] = lambda: db

    async def no_google_api_key(db, user_id):
        return None

    monkeypatch.setattr(vertex_ai_config, "_get_google_api_key", no_google_api_key)
    return TestClient(app)


def test_update_vertex_ai_config_response_model_for_gemini_mode(monkeypatch):
    db = FakeDb()
    with _client(db, monkeypatch) as client:
        response = client.post(
            "/api/vertex-ai/config",
            json={"api_mode": "gemini_api"},
        )

    assert response.status_code == 200
    assert db.committed is True
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Vertex AI configuration updated to gemini_api mode"
    assert body["config"]["api_mode"] == "gemini_api"
    assert body["config"]["gemini_api_configured"] is True
    assert body["config"]["vertex_ai_configured"] is False
    assert body["config"]["hidden_models"] == []
    assert body["config"]["saved_models"] == []


def test_update_vertex_ai_config_rejects_unbounded_credentials(monkeypatch):
    db = FakeDb()
    with _client(db, monkeypatch) as client:
        response = client.post(
            "/api/vertex-ai/config",
            json={
                "api_mode": "vertex_ai",
                "vertex_ai_project_id": "proj",
                "vertex_ai_credentials_json": "x" * 100_001,
            },
        )

    assert response.status_code == 422
    assert db.committed is False


def test_get_vertex_ai_config_internal_error_is_generic(monkeypatch, caplog):
    secret = "vertex-get-secret"
    db = FakeDb()
    db.query_error = RuntimeError(f"query failed {secret}")

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=vertex_ai_config.logger.name):
            response = client.get("/api/vertex-ai/config")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to get Vertex AI configuration"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_update_vertex_ai_config_encrypt_error_is_generic(monkeypatch, caplog):
    secret = "vertex-encrypt-secret"
    db = FakeDb()

    def boom(_value):
        raise RuntimeError(f"encrypt failed {secret}")

    monkeypatch.setattr(vertex_ai_config, "encrypt_data", boom)

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=vertex_ai_config.logger.name):
            response = client.post(
                "/api/vertex-ai/config",
                json={
                    "api_mode": "vertex_ai",
                    "vertex_ai_project_id": "proj",
                    "vertex_ai_credentials_json": "{\"type\":\"service_account\"}",
                },
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to encrypt credentials"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_update_vertex_ai_config_commit_error_is_generic(monkeypatch, caplog):
    secret = "vertex-commit-secret"
    db = FakeDb()
    db.commit_error = RuntimeError(f"commit failed {secret}")

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=vertex_ai_config.logger.name):
            response = client.post(
                "/api/vertex-ai/config",
                json={"api_mode": "gemini_api"},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to update Vertex AI configuration"
    assert db.rolled_back is True
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_test_connection_internal_error_is_generic(monkeypatch, caplog):
    secret = "vertex-test-connection-secret"
    db = FakeDb()

    class FakeGeminiAPIImageGenerator:
        def __init__(self, **kwargs):
            return None

        def get_supported_models(self):
            raise RuntimeError(f"connection failed {secret}")

    fake_module = types.SimpleNamespace(GeminiAPIImageGenerator=FakeGeminiAPIImageGenerator)
    monkeypatch.setitem(sys.modules, "app.services.gemini.imagen_gemini_api", fake_module)

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=vertex_ai_config.logger.name):
            response = client.post(
                "/api/vertex-ai/test-connection",
                json={"api_mode": "gemini_api", "gemini_api_key": "key"},
            )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "vertex_ai_connection_test_failed"
    assert detail["message"] == "Connection test failed"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_test_connection_configuration_error_is_generic(monkeypatch, caplog):
    secret = "vertex-config-secret"
    db = FakeDb()

    class FakeGeminiAPIImageGenerator:
        def __init__(self, **kwargs):
            return None

        def get_supported_models(self):
            raise vertex_ai_config.ConfigurationError(f"bad credentials {secret}")

    fake_module = types.SimpleNamespace(GeminiAPIImageGenerator=FakeGeminiAPIImageGenerator)
    monkeypatch.setitem(sys.modules, "app.services.gemini.imagen_gemini_api", fake_module)

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.WARNING, logger=vertex_ai_config.logger.name):
            response = client.post(
                "/api/vertex-ai/test-connection",
                json={"api_mode": "gemini_api", "gemini_api_key": "key"},
            )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "vertex_ai_configuration_error"
    assert detail["message"] == "Configuration error"
    assert detail["api_mode"] == "gemini_api"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_verify_vertex_ai_internal_error_is_generic(monkeypatch, caplog):
    secret = "vertex-verify-secret"
    db = FakeDb()

    from google.oauth2 import service_account

    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        staticmethod(lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(f"verify failed {secret}"))),
    )

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.ERROR, logger=vertex_ai_config.logger.name):
            response = client.post(
                "/api/vertex-ai/verify-vertex-ai",
                json={
                    "project_id": "proj",
                    "location": "us-central1",
                    "credentials_json": "{\"type\":\"service_account\"}",
                },
            )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "vertex_ai_verification_failed"
    assert detail["message"] == "Verification failed"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_verify_vertex_ai_invalid_credentials_json_is_generic(monkeypatch, caplog):
    secret = "vertex-json-secret"
    db = FakeDb()

    with _client(db, monkeypatch) as client:
        with caplog.at_level(logging.WARNING, logger=vertex_ai_config.logger.name):
            response = client.post(
                "/api/vertex-ai/verify-vertex-ai",
                json={
                    "project_id": "proj",
                    "location": "us-central1",
                    "credentials_json": f"not-json-{secret}",
                },
            )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid credentials JSON"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
