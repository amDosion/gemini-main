from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.core import attachments


class FakeAttachment:
    upload_status = "completed"


class FakeQuery:
    def filter_by(self, **kwargs):
        return self

    def first(self):
        return FakeAttachment()


class FakeDb:
    def query(self, *args, **kwargs):
        return FakeQuery()


class FakeAttachmentService:
    def __init__(self, db):
        self.db = db

    async def resolve_continuity_attachment(self, **kwargs):
        assert kwargs["active_image_url"] == "blob:http://localhost/image"
        assert kwargs["session_id"] == "session-1"
        assert kwargs["user_id"] == "user-1"
        return {
            "attachment_id": "attachment-1",
            "url": "https://storage.example.test/a.png",
            "status": "completed",
            "task_id": None,
            "message_id": "message-1",
            "session_id": "session-1",
            "user_id": "user-1",
            "filename": "a.png",
            "mime_type": "image/png",
            "size": 123,
            "cloud_url": "https://storage.example.test/a.png",
            "created_at": None,
        }

    async def get_cloud_url(self, **kwargs):
        assert kwargs == {"attachment_id": "attachment-1", "user_id": "user-1"}
        return "https://storage.example.test/a.png"


def _client(monkeypatch, service_cls=FakeAttachmentService):
    app = FastAPI()
    app.include_router(attachments.router)
    app.dependency_overrides[attachments.require_current_user] = lambda: "user-1"
    app.dependency_overrides[attachments.get_db] = lambda: FakeDb()
    monkeypatch.setattr(attachments, "AttachmentService", service_cls)
    return TestClient(app)


def test_resolve_continuity_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/attachments/resolve-continuity",
            json={
                "active_image_url": "blob:http://localhost/image",
                "session_id": "session-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "attachment_id": "attachment-1",
        "url": "https://storage.example.test/a.png",
        "status": "completed",
        "task_id": None,
        "message_id": "message-1",
        "session_id": "session-1",
        "user_id": "user-1",
        "filename": "a.png",
        "mime_type": "image/png",
        "size": 123,
        "cloud_url": "https://storage.example.test/a.png",
        "created_at": None,
    }


def test_cloud_url_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/attachments/attachment-1/cloud-url")

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://storage.example.test/a.png",
        "upload_status": "completed",
    }


def test_resolve_continuity_internal_error_is_generic(monkeypatch, caplog):
    secret = "attachment-secret-token"

    class FailingAttachmentService(FakeAttachmentService):
        async def resolve_continuity_attachment(self, **kwargs):
            raise RuntimeError(f"resolve failed {secret}")

    with _client(monkeypatch, FailingAttachmentService) as client:
        with caplog.at_level(logging.ERROR, logger=attachments.logger.name):
            response = client.post(
                "/api/attachments/resolve-continuity",
                json={
                    "active_image_url": "blob:http://localhost/image",
                    "session_id": "session-1",
                },
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_cloud_url_internal_error_is_generic(monkeypatch, caplog):
    secret = "cloud-url-secret-token"

    class FailingAttachmentService(FakeAttachmentService):
        async def get_cloud_url(self, **kwargs):
            raise RuntimeError(f"cloud failed {secret}")

    with _client(monkeypatch, FailingAttachmentService) as client:
        with caplog.at_level(logging.ERROR, logger=attachments.logger.name):
            response = client.get("/api/attachments/attachment-1/cloud-url")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
