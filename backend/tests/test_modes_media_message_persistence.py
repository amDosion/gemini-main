import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import ChatSession, MessageIndex, MessagesVideoGen
from app.routers.core.modes import _persist_generated_media_message


class _DummyCache:
    def __init__(self) -> None:
        self.deleted_patterns = []

    def _make_key(self, *parts) -> str:
        return ":".join(str(part) for part in parts)

    async def delete(self, pattern: str) -> None:
        self.deleted_patterns.append(pattern)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_persist_generated_video_message_creates_reloadable_message_row() -> None:
    db = _session()
    cache = _DummyCache()
    db.add(
        ChatSession(
            id="session-1",
            user_id="user-1",
            title="Existing Video Session",
            created_at=1,
            mode="video-gen",
        )
    )
    db.commit()

    persisted = await _persist_generated_media_message(
        db,
        cache,
        user_id="user-1",
        session_id="session-1",
        message_id="model-1",
        mode="video-gen",
        prompt="make a product video",
        model_id="veo-3.1-generate-preview",
        payload={
            "attachment_id": "att-1",
            "enhanced_prompt": "make a cinematic product video",
            "continuation_strategy": "last_frame_bridge_chain",
            "video_extension_count": 5,
            "video_extension_applied": 5,
            "total_duration_seconds": 43,
            "video_size": "3840*2160",
        },
    )

    assert persisted is True
    index = db.query(MessageIndex).filter_by(id="model-1").one()
    assert index.session_id == "session-1"
    assert index.mode == "video-gen"
    assert index.table_name == "messages_video_gen"
    assert index.seq == 0

    message = db.query(MessagesVideoGen).filter_by(id="model-1").one()
    assert message.role == "model"
    assert message.content == "📝 make a product video\n✨ make a cinematic product video"
    assert message.model_name == "veo-3.1-generate-preview"
    assert message.video_duration == 43
    assert message.video_resolution == "3840*2160"
    metadata = json.loads(message.metadata_json)
    assert metadata["continuation_strategy"] == "last_frame_bridge_chain"
    assert metadata["video_extension_applied"] == 5
    assert cache.deleted_patterns == ["sessions:user-1:*"]


@pytest.mark.asyncio
async def test_persist_generated_media_message_creates_missing_session() -> None:
    db = _session()

    persisted = await _persist_generated_media_message(
        db,
        None,
        user_id="user-1",
        session_id="new-session",
        message_id="model-1",
        mode="video-gen",
        prompt="new session prompt",
        model_id="veo-3.1-generate-preview",
        payload={"attachment_id": "att-1"},
    )

    assert persisted is True
    session = db.query(ChatSession).filter_by(id="new-session").one()
    assert session.user_id == "user-1"
    assert session.mode == "video-gen"
    assert session.title == "new session prompt"
    assert db.query(MessageIndex).filter_by(id="model-1").count() == 1
    assert db.query(MessagesVideoGen).filter_by(id="model-1").count() == 1


@pytest.mark.asyncio
async def test_persist_generated_media_message_uses_first_image_metadata_fallback() -> None:
    db = _session()
    db.add(
        ChatSession(
            id="session-1",
            user_id="user-1",
            title="Existing Image Session",
            created_at=1,
            mode="image-gen",
        )
    )
    db.commit()

    persisted = await _persist_generated_media_message(
        db,
        None,
        user_id="user-1",
        session_id="session-1",
        message_id="model-1",
        mode="image-gen",
        prompt="draw a product photo",
        model_id="imagen-3.0-generate-002",
        payload={
            "images": [
                {
                    "attachment_id": "att-1",
                    "enhanced_prompt": "draw a polished studio product photo",
                    "thoughts": [{"text": "use soft light"}],
                    "text": "Generated one image.",
                }
            ]
        },
    )

    assert persisted is True
    from app.models.db_models import MessagesImageGen

    message = db.query(MessagesImageGen).filter_by(id="model-1").one()
    assert message.content == "📝 draw a product photo\n✨ draw a polished studio product photo"
    metadata = json.loads(message.metadata_json)
    assert metadata["enhanced_prompt"] == "draw a polished studio product photo"
    assert metadata["thoughts"] == [{"text": "use soft light"}]
    assert metadata["text_response"] == "Generated one image."
