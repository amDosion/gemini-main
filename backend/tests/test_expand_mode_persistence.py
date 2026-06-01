import base64
import importlib
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base
from app.models.db_models import (
    ChatSession,
    MessageAttachment,
    MessageIndex,
    MessagesGeneric,
    UploadTask,
)
from app.routers.core.modes import Attachment, ModeOptions, ModeRequest
from app.services.common import attachment_service as attachment_service_module

modes = importlib.import_module("app.routers.core.modes")


_PNG_DATA_URL = (
    "data:image/png;base64,"
    + base64.b64encode(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
    ).decode("ascii")
)


class _DummyCache:
    def __init__(self) -> None:
        self.deleted_patterns = []

    def _make_key(self, *parts) -> str:
        return ":".join(str(part) for part in parts)

    async def delete(self, pattern: str) -> None:
        self.deleted_patterns.append(pattern)


class _FakeExpandService:
    def __init__(self) -> None:
        self.calls = []

    async def expand_image(self, **kwargs):
        self.calls.append(kwargs)
        mode = str(kwargs.get("mode") or "unknown")
        return [
            {
                "url": _PNG_DATA_URL,
                "mime_type": "image/png",
                "filename": f"{mode}.png",
                "enhanced_prompt": f"expanded via {mode}",
            }
        ]


@pytest.fixture()
def expand_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(modes, "SessionLocal", testing_session_local)
    try:
        yield testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def expand_route_mocks(monkeypatch):
    fake_service = _FakeExpandService()

    async def fake_credentials(**_kwargs):
        return "fake-key", None

    async def fake_enqueue(_task_id: str, _priority: str) -> int:
        return 1

    async def fake_connect() -> None:
        return None

    async def fake_ensure_worker_running() -> None:
        return None

    monkeypatch.setattr(modes, "get_provider_credentials", fake_credentials)
    monkeypatch.setattr(
        modes.ProviderFactory,
        "create",
        staticmethod(lambda **_kwargs: fake_service),
    )
    monkeypatch.setattr(attachment_service_module.redis_queue, "_redis", object())
    monkeypatch.setattr(attachment_service_module.redis_queue, "connect", fake_connect)
    monkeypatch.setattr(attachment_service_module.redis_queue, "enqueue", fake_enqueue)
    monkeypatch.setattr(
        attachment_service_module.worker_pool,
        "ensure_worker_running",
        fake_ensure_worker_running,
    )
    return fake_service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outpaint_mode", "model_id", "mode_options"),
    [
        ("ratio", "imagen-3.0-capability-001", {"output_ratio": "16:9"}),
        ("scale", "imagen-3.0-capability-001", {"x_scale": 1.5, "y_scale": 1.3}),
        (
            "offset",
            "imagen-3.0-capability-001",
            {"left_offset": 16, "right_offset": 24, "top_offset": 8, "bottom_offset": 12},
        ),
        ("upscale", "imagen-4.0-upscale-preview", {"upscale_factor": "x3"}),
    ],
)
async def test_image_outpainting_submodes_persist_model_message_attachment_and_upload_task(
    expand_db,
    expand_route_mocks,
    outpaint_mode,
    model_id,
    mode_options,
):
    db = expand_db()
    cache = _DummyCache()
    session_id = f"expand-session-{outpaint_mode}"
    user_message_id = f"user-{outpaint_mode}"
    model_message_id = f"model-{outpaint_mode}"
    try:
        db.add(
            ChatSession(
                id=session_id,
                user_id="user-1",
                title="Expand session",
                mode="image-outpainting",
                created_at=1,
            )
        )
        db.add(
            MessageIndex(
                id=user_message_id,
                user_id="user-1",
                session_id=session_id,
                mode="image-outpainting",
                table_name="messages_generic",
                seq=0,
                timestamp=1,
            )
        )
        db.add(
            MessagesGeneric(
                id=user_message_id,
                user_id="user-1",
                session_id=session_id,
                role="user",
                content="expand this image",
                timestamp=1,
                is_error=False,
            )
        )
        db.commit()

        response = await modes.handle_mode(
            "google",
            "image-outpainting",
            ModeRequest(
                model_id=model_id,
                prompt="extend the clean studio background",
                attachments=[
                    Attachment(
                        id="input-image",
                        mime_type="image/png",
                        name="input.png",
                        url=_PNG_DATA_URL,
                    )
                ],
                options=ModeOptions(
                    frontend_session_id=session_id,
                    message_id=model_message_id,
                    outpaint_mode=outpaint_mode,
                    output_mime_type="image/png",
                    **mode_options,
                ),
            ),
            request=types.SimpleNamespace(headers={}, cookies={}),
            user_id="user-1",
            db=db,
            cache=cache,
        )

        assert response.success is True
        assert response.mode == "image-outpainting"
        assert isinstance(response.data, dict)
        assert set(response.data.keys()) == {"images"}
        assert len(response.data["images"]) == 1
        assert response.data["images"][0]["attachment_id"]
        assert response.data["images"][0]["url"].startswith("/api/temp-images/")

        [service_call] = expand_route_mocks.calls
        assert service_call["model"] == model_id
        assert service_call["mode"] == outpaint_mode
        assert service_call["reference_images"]["raw"]["url"] == _PNG_DATA_URL

        index = db.query(MessageIndex).filter_by(id=model_message_id).one()
        assert index.session_id == session_id
        assert index.mode == "image-outpainting"
        assert index.table_name == "messages_generic"
        assert index.seq == 1
        assert index.parent_id == user_message_id

        message = db.query(MessagesGeneric).filter_by(id=model_message_id).one()
        assert message.role == "model"
        assert (
            message.content
            == f"📝 extend the clean studio background\n✨ expanded via {outpaint_mode}"
        )

        attachment = (
            db.query(MessageAttachment)
            .filter_by(message_id=model_message_id, user_id="user-1")
            .one()
        )
        assert attachment.session_id == session_id
        assert attachment.mime_type == "image/png"
        assert attachment.name == f"{outpaint_mode}.png"
        assert attachment.temp_url == _PNG_DATA_URL
        assert attachment.upload_status == "pending"

        task = db.query(UploadTask).filter_by(attachment_id=attachment.id).one()
        assert task.session_id == session_id
        assert task.message_id == model_message_id
        assert task.source_ai_url == _PNG_DATA_URL
        assert task.filename == f"{outpaint_mode}.png"
        assert task.status == "pending"

        assert cache.deleted_patterns == ["sessions:user-1:*"]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_image_outpainting_orphan_provider_attachment_id_falls_back_to_router_persistence(
    expand_db,
    expand_route_mocks,
):
    async def orphan_attachment_result(**kwargs):
        expand_route_mocks.calls.append(kwargs)
        return [
            {
                "attachment_id": "provider-orphan-attachment",
                "url": _PNG_DATA_URL,
                "mime_type": "image/png",
                "filename": "orphan.png",
            }
        ]

    expand_route_mocks.expand_image = orphan_attachment_result
    db = expand_db()
    session_id = "expand-session-orphan"
    model_message_id = "model-orphan"
    try:
        db.add(
            ChatSession(
                id=session_id,
                user_id="user-1",
                title="Expand session",
                mode="image-outpainting",
                created_at=1,
            )
        )
        db.commit()

        response = await modes.handle_mode(
            "google",
            "image-outpainting",
            ModeRequest(
                model_id="imagen-3.0-capability-001",
                prompt="extend the clean studio background",
                attachments=[
                    Attachment(
                        id="input-image",
                        mime_type="image/png",
                        name="input.png",
                        url=_PNG_DATA_URL,
                    )
                ],
                options=ModeOptions(
                    frontend_session_id=session_id,
                    message_id=model_message_id,
                    outpaint_mode="ratio",
                    output_ratio="16:9",
                ),
            ),
            request=types.SimpleNamespace(headers={}, cookies={}),
            user_id="user-1",
            db=db,
            cache=None,
        )

        image = response.data["images"][0]
        assert image["attachment_id"] != "provider-orphan-attachment"
        attachment = (
            db.query(MessageAttachment)
            .filter_by(id=image["attachment_id"], message_id=model_message_id, user_id="user-1")
            .one()
        )
        assert attachment.temp_url == _PNG_DATA_URL
        assert db.query(UploadTask).filter_by(attachment_id=attachment.id).count() == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_virtual_tryon_persists_model_message_attachment_and_upload_task(
    expand_db,
    expand_route_mocks,
):
    async def fake_virtual_tryon(**kwargs):
        expand_route_mocks.calls.append(kwargs)
        return [
            {
                "url": _PNG_DATA_URL,
                "mime_type": "image/png",
                "filename": "tryon.png",
                "enhanced_prompt": "try-on via gpt image",
            }
        ]

    expand_route_mocks.virtual_tryon = fake_virtual_tryon
    db = expand_db()
    cache = _DummyCache()
    session_id = "tryon-session"
    model_message_id = "model-tryon"
    try:
        db.add(
            ChatSession(
                id=session_id,
                user_id="user-1",
                title="Try-on session",
                mode="virtual-try-on",
                created_at=1,
            )
        )
        db.commit()

        response = await modes.handle_mode(
            "openai",
            "virtual-try-on",
            ModeRequest(
                model_id="gpt-image-2",
                prompt="",
                attachments=[
                    Attachment(
                        id="person-image",
                        mime_type="image/png",
                        name="person.png",
                        url=_PNG_DATA_URL,
                    ),
                    Attachment(
                        id="garment-image",
                        mime_type="image/png",
                        name="garment.png",
                        url=_PNG_DATA_URL,
                    ),
                ],
                options=ModeOptions(
                    frontend_session_id=session_id,
                    message_id=model_message_id,
                    number_of_images=1,
                ),
            ),
            request=types.SimpleNamespace(headers={}, cookies={}),
            user_id="user-1",
            db=db,
            cache=cache,
        )

        assert response.success is True
        assert response.mode == "virtual-try-on"
        assert isinstance(response.data, dict)
        assert len(response.data["images"]) == 1
        assert response.data["images"][0]["attachment_id"]
        assert response.data["images"][0]["url"].startswith("/api/temp-images/")

        [service_call] = expand_route_mocks.calls
        assert service_call["model"] == "gpt-image-2"
        assert service_call["reference_images"]["raw"][0]["url"] == _PNG_DATA_URL
        assert service_call["reference_images"]["raw"][1]["url"] == _PNG_DATA_URL

        index = db.query(MessageIndex).filter_by(id=model_message_id).one()
        assert index.session_id == session_id
        assert index.mode == "virtual-try-on"

        message = db.query(MessagesGeneric).filter_by(id=model_message_id).one()
        assert message.role == "model"
        assert message.content == "✨ try-on via gpt image"

        attachment = (
            db.query(MessageAttachment)
            .filter_by(message_id=model_message_id, user_id="user-1")
            .one()
        )
        assert attachment.session_id == session_id
        assert attachment.mime_type == "image/png"
        assert attachment.name == "tryon.png"
        assert attachment.upload_status == "pending"

        task = db.query(UploadTask).filter_by(attachment_id=attachment.id).one()
        assert task.session_id == session_id
        assert task.message_id == model_message_id
        assert task.source_ai_url == _PNG_DATA_URL

        assert cache.deleted_patterns == ["sessions:user-1:*"]
    finally:
        db.close()
