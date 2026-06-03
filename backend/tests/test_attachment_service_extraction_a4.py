"""Adversarial regression pins for cluster a4-deeper extraction.

`attachment_service.py` was ~934 lines; project max is 800. The two large
orchestration methods (`resolve_continuity_attachment` ~229 lines and
`process_ai_result` ~182 lines) get their internal logic extracted into a
cohesive sibling module so the service keeps thin delegating wrappers.

These tests pin the INVARIANTS the refactor must not violate:

1. attachment_service.py is under the 800-line project ceiling.
2. The public API is unchanged: AttachmentService still exposes both async
   methods, importable from attachment_service, and they remain settable on
   the class (monkeypatch contract used by the persist-diagnostics suite).
3. The extracted module exists and is import-safe.
4. resolve_continuity_attachment still returns None when nothing matches and
   delegates the "completed + persistent url" fast path (behavior identical),
   exercised against a real in-memory DB without any Worker Pool / Redis I/O.
5. process_ai_result still produces a temp-proxy display_url + pending task
   when no local-storage direct-write applies, with all metadata fields.
"""

import inspect
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.db_models import Base, MessageAttachment
from app.services.common.attachment_service import AttachmentService

_SERVICE_PATH = Path(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "app",
        "services",
        "common",
        "attachment_service.py",
    )
).resolve()

_MAX_LINES = 800


def _line_count(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _sessionmaker():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_attachment_service_is_under_project_line_ceiling():
    count = _line_count(_SERVICE_PATH)
    assert count < _MAX_LINES, (
        f"attachment_service.py has {count} lines; must be < {_MAX_LINES}. "
        "Extract orchestration helpers into a sibling module."
    )


def test_public_api_methods_present_and_async():
    assert inspect.iscoroutinefunction(AttachmentService.process_ai_result)
    assert inspect.iscoroutinefunction(AttachmentService.resolve_continuity_attachment)
    assert inspect.iscoroutinefunction(AttachmentService.process_user_upload)
    assert inspect.iscoroutinefunction(AttachmentService.get_cloud_url)


def test_public_methods_remain_settable_on_class(monkeypatch):
    # The persist-diagnostics suite monkeypatches process_ai_result on the
    # class; a thin wrapper must keep that contract intact.
    async def _stub(self, **_kw):
        return {"sentinel": True}

    monkeypatch.setattr(AttachmentService, "process_ai_result", _stub, raising=True)
    assert AttachmentService.process_ai_result is _stub


def test_extracted_orchestration_module_importable():
    # At least one cohesive extraction module must exist and import cleanly.
    import importlib

    candidates = [
        "app.services.common.attachment_continuity",
        "app.services.common.attachment_ai_result",
    ]
    imported = []
    for name in candidates:
        try:
            imported.append(importlib.import_module(name))
        except ModuleNotFoundError:
            continue
    assert imported, (
        "Expected at least one of attachment_continuity / attachment_ai_result "
        "to be extracted and importable."
    )


@pytest.mark.asyncio
async def test_resolve_continuity_returns_none_when_no_match():
    db = _sessionmaker()()
    svc = AttachmentService(db)
    result = await svc.resolve_continuity_attachment(
        active_image_url="https://example.com/never-seen.png",
        session_id="s1",
        user_id="u1",
        messages=[],
    )
    assert result is None
    db.close()


@pytest.mark.asyncio
async def test_resolve_continuity_completed_persistent_url_fast_path():
    db = _sessionmaker()()
    att = MessageAttachment(
        id="att-1",
        message_id="msg-1",
        user_id="u1",
        session_id="s1",
        name="img.png",
        mime_type="image/png",
        url="https://cdn.example.com/img.png",
        upload_status="completed",
    )
    db.add(att)
    db.commit()

    svc = AttachmentService(db)
    messages = [{"attachments": [{"id": "att-1", "url": "https://cdn.example.com/img.png"}]}]
    result = await svc.resolve_continuity_attachment(
        active_image_url="https://cdn.example.com/img.png",
        session_id="s1",
        user_id="u1",
        messages=messages,
    )
    assert result is not None
    assert result["attachment_id"] == "att-1"
    assert result["status"] == "completed"
    assert result["task_id"] is None
    assert result["url"] == "https://cdn.example.com/img.png"
    assert result["cloud_url"] == "https://cdn.example.com/img.png"
    db.close()


@pytest.mark.asyncio
async def test_process_ai_result_pending_proxy_url(monkeypatch):
    db = _sessionmaker()()
    svc = AttachmentService(db)
    # No local-storage provider -> direct write is skipped.
    svc._get_effective_storage_config = lambda **_kw: None  # type: ignore[method-assign]

    async def _fake_submit(**kwargs):
        return "task-xyz"

    svc._submit_upload_task = _fake_submit  # type: ignore[method-assign]

    result = await svc.process_ai_result(
        ai_url="https://example.com/ai.png",
        mime_type="image/png",
        session_id="s1",
        message_id="m1",
        user_id="u1",
        prefix="generated",
        filename=None,
    )
    assert result["status"] == "pending"
    assert result["task_id"] == "task-xyz"
    assert result["display_url"] == f"/api/temp-images/{result['attachment_id']}"
    assert result["cloud_url"] == ""
    assert result["session_id"] == "s1"
    assert result["message_id"] == "m1"
    assert result["user_id"] == "u1"
    assert result["mime_type"] == "image/png"
    assert result["filename"].endswith(".png")

    row = db.query(MessageAttachment).filter_by(id=result["attachment_id"]).one()
    assert row.upload_status == "pending"
    assert row.temp_url == "https://example.com/ai.png"
    db.close()
