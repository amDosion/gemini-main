"""V-S28: clear source_ai_url after a successful upload.

source_ai_url (Text) stores the full AI-returned image payload (often a plaintext
base64 data URL). After a successful cloud upload it is no longer needed, but it
lingered in the DB column, so a DB dump exposed the raw payloads. The success
path must clear it in the same commit that marks the task completed.
"""

import pytest
import logging

from app.services.common.upload_worker_pool import UploadWorkerPool


async def _async_noop(*args, **kwargs):
    return None


class _FakeQueue:
    async def append_task_log(self, *args, **kwargs):
        return None

    async def update_stats(self, *args, **kwargs):
        return None


class _FakeTask:
    def __init__(self):
        self.id = "t-vs28"
        self.status = "uploading"
        self.source_ai_url = "data:image/png;base64,QUJDMTIzNDU2Nzg5"
        self.source_file_path = None
        self.session_id = None
        self.message_id = None
        self.attachment_id = None
        self.filename = "img.png"
        self.target_url = None
        self.completed_at = None


class _FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_handle_success_clears_source_ai_url(monkeypatch):
    pool = UploadWorkerPool()
    monkeypatch.setattr("app.services.common.upload_worker_pool.redis_queue", _FakeQueue())
    monkeypatch.setattr(pool, "_log_task_db_state", _async_noop)

    task = _FakeTask()
    db = _FakeDB()
    await pool._handle_success(db, task, "https://cdn.example.com/img.png", "w1")

    assert task.status == "completed"
    assert task.target_url == "https://cdn.example.com/img.png"
    # V-S28: the plaintext base64 payload must be cleared in the success commit.
    assert task.source_ai_url is None
    assert db.commits >= 1


@pytest.mark.asyncio
async def test_handle_success_logs_url_summary_without_leaking_signed_url(monkeypatch, caplog):
    pool = UploadWorkerPool()
    monkeypatch.setattr("app.services.common.upload_worker_pool.redis_queue", _FakeQueue())
    monkeypatch.setattr(pool, "_log_task_db_state", _async_noop)

    signed_url = (
        "https://cdn.example.com/img.png"
        "?X-Amz-Signature=secret-signature&token=secret-token#private-fragment"
    )
    task = _FakeTask()
    db = _FakeDB()

    with caplog.at_level(logging.INFO, logger="app.services.common.upload_worker_pool"):
        await pool._handle_success(db, task, signed_url, "w1")

    assert task.target_url == signed_url
    assert "云存储 URL: http(len=" in caplog.text
    assert signed_url not in caplog.text
    assert "secret-signature" not in caplog.text
    assert "secret-token" not in caplog.text
    assert "private-fragment" not in caplog.text
