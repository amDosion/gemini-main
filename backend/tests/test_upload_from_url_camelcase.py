"""Regression: POST /storage/upload-from-url must honour the camelCase contract.

The frontend (storageUpload.uploadFromUrlViaBackend) already sends camelCase
sessionId/messageId/attachmentId/storageId, but the endpoint was decorated
@case_conversion_options(skip_request_body=True) while the handler reads
data.get("session_id") (snake) — so the IDs arrived camelCase, were never read,
and the UploadTask was created with session_id/message_id/attachment_id = None
(url-uploads silently lost their session/message/attachment linkage).

Removing the skip lets the middleware convert camel->snake so the handler reads
the IDs. (to_snake_case is idempotent, so legacy snake callers still work.)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.storage import storage as storage_mod
from app.middleware.case_conversion_middleware import CaseConversionMiddleware
from app.core.dependencies import require_current_user
from app.core.database import get_db


class _FakeQuery:
    def filter(self, *a, **k):
        return self

    def first(self):
        return None  # no ChatSession owner row -> skip the 404 ownership check


class _FakeDB:
    def __init__(self):
        self.added = []

    def query(self, *a, **k):
        return _FakeQuery()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        return None

    def rollback(self):
        return None


class _FakeRedisQueue:
    _redis = object()  # non-None -> skip connect()

    async def enqueue(self, task_id, priority):
        return 0

    async def append_task_log(self, *a, **k):
        return None


@pytest.fixture
def client(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(storage_mod, "redis_queue", _FakeRedisQueue())
    monkeypatch.setattr(storage_mod, "_validate_outbound_http_url", lambda u: u)
    monkeypatch.setattr(
        storage_mod, "_resolve_enabled_storage_config", lambda **k: ("storage-1", None)
    )

    app = FastAPI()
    app.add_middleware(CaseConversionMiddleware)
    app.include_router(storage_mod.router)
    app.dependency_overrides[require_current_user] = lambda: "user-1"
    app.dependency_overrides[get_db] = lambda: fake_db
    return TestClient(app), fake_db


def test_camelcase_body_ids_reach_the_handler(client):
    test_client, fake_db = client

    resp = test_client.post(
        "/api/storage/upload-from-url",
        json={
            "url": "https://cdn.example.com/x.png",
            "filename": "x.png",
            "sessionId": "sess-1",
            "messageId": "msg-1",
            "attachmentId": "att-1",
            "storageId": "storage-1",
        },
    )

    assert resp.status_code == 200
    assert len(fake_db.added) == 1
    task = fake_db.added[0]
    # The middleware converted camelCase -> snake_case, so the handler read them.
    assert task.session_id == "sess-1"
    assert task.message_id == "msg-1"
    assert task.attachment_id == "att-1"
