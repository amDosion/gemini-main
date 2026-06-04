"""Regression: browse-progress SSE frames must be camelCase.

The browse-progress SSE endpoint emitted the raw ProgressTracker dict with
snake_case `operation_id` (SSE is middleware-passthrough), but the frontend
type-guard isBrowseProgressUpdate requires camelCase `operationId`, so every
update was silently dropped. The fix routes the frame through
encode_sse_data(camel_case=True) so the wire is camelCase and the frontend never
converts.
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tools import browse


class _FakeTracker:
    def __init__(self, messages):
        self._messages = messages

    async def subscribe(self, operation_id):
        q: "asyncio.Queue" = asyncio.Queue()
        for m in self._messages:
            q.put_nowait(m)
        return q

    async def unsubscribe(self, operation_id, queue):
        return None


def _client(monkeypatch, messages):
    monkeypatch.setattr(browse, "_progress_tracker", _FakeTracker(messages))
    app = FastAPI()
    app.include_router(browse.router)
    app.dependency_overrides[browse.require_current_user] = lambda: "u1"
    return TestClient(app)


def test_browse_progress_frame_is_camelcase(monkeypatch):
    snake_msg = {
        "operation_id": "op1",
        "step": "fetch",
        "status": "completed",
        "details": "done",
        "progress": 100,
        "timestamp": 1234,
    }
    client = _client(monkeypatch, [snake_msg])

    resp = client.get("/api/browse/progress/op1")

    assert resp.status_code == 200
    body = resp.text
    # The frontend guard requires camelCase operationId.
    assert "operationId" in body
    # snake_case must not reach the wire.
    assert "operation_id" not in body
