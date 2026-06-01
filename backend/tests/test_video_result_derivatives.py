import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.routers.ai import workflows
from app.services.common import video_result_derivatives
from app.services.gemini.base.video_common import LoadedReferenceImage


class _FakeAttachmentService:
    def __init__(self):
        self.db = None
        self.calls = []

    async def process_ai_result(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "attachment_id": "frame-att-1",
            "display_url": "/api/temp-images/frame-att-1",
            "cloud_url": "",
            "status": "pending",
            "task_id": "task-frame-1",
            "mime_type": kwargs["mime_type"],
            "filename": kwargs["filename"],
            "session_id": kwargs["session_id"],
            "message_id": kwargs["message_id"],
            "user_id": kwargs["user_id"],
        }


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_persist_video_last_frame_derivative_uses_existing_attachment_service(monkeypatch):
    service = _FakeAttachmentService()

    async def fake_load_video_result_bytes(*_args, **_kwargs):
        return b"video-bytes", "video/mp4"

    def fake_extract_last_frame_image(source_video):
        assert source_video.video_bytes == b"video-bytes"
        assert source_video.mime_type == "video/mp4"
        return LoadedReferenceImage(image_bytes=b"png-bytes", mime_type="image/png")

    monkeypatch.setattr(video_result_derivatives, "load_video_result_bytes", fake_load_video_result_bytes)
    monkeypatch.setattr(video_result_derivatives, "extract_last_frame_image", fake_extract_last_frame_image)

    derivative = await video_result_derivatives.safe_persist_video_last_frame_derivative(
        service,
        video_payload={
            "url": "/api/temp-images/video-att-1",
            "mime_type": "video/mp4",
            "filename": "generated-video.mp4",
            "attachment_id": "video-att-1",
        },
        source_url="data:video/mp4;base64,AAAA",
        session_id="session-1",
        message_id="message-1",
        user_id="user-1",
    )

    assert derivative == {
        "kind": "video_last_frame",
        "role": "last_frame",
        "url": "/api/temp-images/frame-att-1",
        "attachment_id": "frame-att-1",
        "upload_status": "pending",
        "task_id": "task-frame-1",
        "mime_type": "image/png",
        "filename": "generated-video-last-frame.png",
        "session_id": "session-1",
        "message_id": "message-1",
        "user_id": "user-1",
        "cloud_url": "",
        "derived_from_attachment_id": "video-att-1",
        "derived_from_video_url": "data:video/mp4;base64,AAAA",
    }
    assert len(service.calls) == 1
    persist_call = service.calls[0]
    assert persist_call["prefix"] == "video-last-frame"
    assert persist_call["mime_type"] == "image/png"
    assert persist_call["filename"] == "generated-video-last-frame.png"
    assert persist_call["ai_url"].startswith("data:image/png;base64,")
    assert base64.b64decode(persist_call["ai_url"].split(",", 1)[1]) == b"png-bytes"


@pytest.mark.asyncio
async def test_persist_video_last_frame_derivative_returns_none_without_video_source():
    derivative = await video_result_derivatives.safe_persist_video_last_frame_derivative(
        _FakeAttachmentService(),
        video_payload={},
        session_id="session-1",
        message_id="message-1",
        user_id="user-1",
    )

    assert derivative is None


@pytest.mark.asyncio
async def test_workflow_video_media_persistence_attaches_last_frame_derivative(monkeypatch):
    db = _session()

    async def fake_safe_persist_ai_result(_attachment_service, **kwargs):
        assert kwargs["ai_url"] == "https://cdn.example.com/final.mp4"
        return {
            "attachment_id": "video-att-1",
            "display_url": "/api/temp-images/video-att-1",
            "cloud_url": "",
            "status": "pending",
            "task_id": "task-video-1",
            "mime_type": "video/mp4",
            "filename": "workflow-video.mp4",
        }

    async def fake_last_frame_derivative(_attachment_service, **kwargs):
        assert kwargs["source_url"] == "https://cdn.example.com/final.mp4"
        assert kwargs["video_payload"]["attachment_id"] == "video-att-1"
        return {
            "kind": "video_last_frame",
            "role": "last_frame",
            "url": "/api/temp-images/frame-att-1",
            "attachment_id": "frame-att-1",
            "upload_status": "pending",
            "task_id": "task-frame-1",
            "mime_type": "image/png",
            "filename": "workflow-video-last-frame.png",
            "session_id": "execution-1",
            "message_id": "execution-1",
            "user_id": "user-1",
            "cloud_url": "",
            "derived_from_attachment_id": "video-att-1",
            "derived_from_video_url": "https://cdn.example.com/final.mp4",
        }

    monkeypatch.setattr(workflows, "safe_persist_ai_result", fake_safe_persist_ai_result)
    monkeypatch.setattr(workflows, "safe_persist_video_last_frame_derivative", fake_last_frame_derivative)

    persisted, replacements = await workflows._persist_workflow_result_media(
        db=db,
        execution_id="execution-1",
        user_id="user-1",
        result_payload={
            "videoUrl": "https://cdn.example.com/final.mp4",
            "mimeType": "video/mp4",
        },
        media_kind="video",
    )

    assert replacements == {"https://cdn.example.com/final.mp4": "/api/temp-images/video-att-1"}
    assert persisted["videoUrl"] == "/api/temp-images/video-att-1"
    assert persisted["last_frame_image_url"] == "/api/temp-images/frame-att-1"
    assert persisted["last_frame_attachment_id"] == "frame-att-1"
    assert persisted["derived_assets"][0]["kind"] == "video_last_frame"
