"""Regression for the modes.py edit-continuity message loader.

The edit_image CONTINUITY branch did `from ...models.db_models import Message`,
but the `Message` model was removed in the v3 sharded-schema refactor, so a
request with session_id but no extra.messages raised ImportError -> 500.

The fix is a v3-correct loader that rebuilds the minimal message shape
(id + attachments with id/url/tempUrl) needed by find_attachment_by_url, from
MessageAttachment ordered by MessageIndex.seq.
"""

import importlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    from app.models.db_models import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _modes():
    return importlib.import_module("app.routers.core.modes")


def _add_index(db, mid, seq):
    from app.models.db_models import MessageIndex

    db.add(MessageIndex(
        id=mid, user_id="u1", session_id="s1", mode="image-gen",
        table_name="messages_image_gen", seq=seq, timestamp=seq + 1,
    ))


def _add_att(db, aid, mid, url, temp_url=None):
    from app.models.db_models import MessageAttachment

    db.add(MessageAttachment(
        id=aid, message_id=mid, user_id="u1", session_id="s1",
        url=url, temp_url=temp_url, upload_status="completed",
    ))


def test_loads_messages_with_attachments_ordered_by_seq(db):
    _add_index(db, "m0", 0)
    _add_index(db, "m1", 1)
    _add_att(db, "a0", "m0", "http://cdn/old.png")
    _add_att(db, "a1", "m1", "http://cdn/new.png", temp_url="blob:new")
    db.commit()

    messages = _modes()._load_session_messages_with_attachments(db, "s1", "u1")

    assert [m["id"] for m in messages] == ["m0", "m1"]
    assert messages[1]["attachments"][0]["url"] == "http://cdn/new.png"
    assert messages[1]["attachments"][0]["tempUrl"] == "blob:new"

    # The continuity matcher must resolve through the rebuilt messages.
    from app.services.common.attachment_records import find_attachment_by_url

    assert find_attachment_by_url("http://cdn/old.png", messages) == "a0"
    assert find_attachment_by_url("blob:new", messages) == "a1"


def test_returns_empty_for_session_without_attachments(db):
    assert _modes()._load_session_messages_with_attachments(db, "missing", "u1") == []


def test_scopes_to_user(db):
    from app.models.db_models import MessageAttachment

    _add_index(db, "m0", 0)
    _add_att(db, "a0", "m0", "http://cdn/old.png")
    # An attachment owned by a different user must not leak in.
    db.add(MessageAttachment(
        id="aX", message_id="mX", user_id="other", session_id="s1",
        url="http://cdn/secret.png", upload_status="completed",
    ))
    db.commit()

    messages = _modes()._load_session_messages_with_attachments(db, "s1", "u1")
    all_urls = [a["url"] for m in messages for a in m["attachments"]]
    assert "http://cdn/secret.png" not in all_urls
    assert "http://cdn/old.png" in all_urls
