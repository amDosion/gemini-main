"""Coverage-focused tests for the chat + session-CRUD REST routers.

Targets
-------
* ``app.routers.core.chat``        — the unified per-provider chat endpoint.
* ``app.routers.user.sessions``    — v3 session/message/attachment CRUD.

Strategy
--------
* Each router is mounted on a fresh :class:`FastAPI` app that overrides only the
  FastAPI boundary dependencies — ``require_current_user`` (auth), ``get_db``
  (DB session) and, for sessions, ``get_cache`` (Redis).  Everything else runs
  for real.
* The DB is a real in-memory SQLite engine populated with the actual SQLAlchemy
  models, so the routers' query / user-scoping / serialization / convergent
  delete logic executes against real rows instead of stubs.
* The only things patched are genuine external boundaries: the provider
  credential lookup, the ``ProviderFactory`` (network SDK), and the MCP manager.
  Pure helper functions are tested directly.

These tests assert real behaviour: status codes, response shapes, user scoping
(other user's data -> 404), validation branches, the per-mode session
immutability rules, convergent message deletion, cloud-URL protection on
attachments, favourite/preference toggles, and the chat option/credential/MCP
error mapping.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import require_current_user, get_cache
from app.models.db_models import (
    ChatSession as DBChatSession,
    MessageIndex,
    MessagesChat,
    MessageAttachment,
    MessageHistoryState,
    SessionHistoryPreference,
    UploadTask,
    Persona as DBPersona,
    UserMcpConfig,
)
from importlib import import_module

# NOTE: ``app.routers.core.__init__`` re-exports ``chat`` as the *router* object
# (``from .chat import router as chat``), which would shadow the module on a
# plain ``from app.routers.core import chat``. Import the real module explicitly.
chat_mod = import_module("app.routers.core.chat")
sessions_mod = import_module("app.routers.user.sessions")

USER_ID = "user-cs-1"
OTHER_USER_ID = "user-cs-2"


# --------------------------------------------------------------------------- #
# Shared in-memory DB fixture
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class _FakeCache:
    """A no-Redis CacheService stand-in.

    ``_make_key`` mirrors the real key shape, ``get_or_set`` always misses (so
    the router's real fetch function runs every call) and ``delete`` records the
    invalidation patterns for assertions.
    """

    def __init__(self) -> None:
        self.deleted: List[str] = []

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        parts = [prefix]
        for arg in args:
            if arg is not None:
                parts.append(str(arg))
        return ":".join(["cache"] + parts)

    async def get_or_set(self, key, fetch_func, ttl=None):
        return await fetch_func()

    async def delete(self, key) -> bool:
        self.deleted.append(key)
        return True


def _now_ms() -> int:
    return int(time.time() * 1000)


# =========================================================================== #
# SESSIONS ROUTER
# =========================================================================== #
@pytest.fixture()
def fake_cache():
    return _FakeCache()


@pytest.fixture()
def sessions_client(db_session, fake_cache):
    app = FastAPI()
    app.include_router(sessions_mod.router)
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_cache] = lambda: fake_cache
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_session(
    db,
    *,
    session_id: str,
    user_id: str = USER_ID,
    mode: str = "chat",
    title: str = "S",
    persona_id: Optional[str] = None,
) -> DBChatSession:
    s = DBChatSession(
        id=session_id,
        user_id=user_id,
        title=title,
        persona_id=persona_id,
        mode=mode,
        created_at=_now_ms(),
    )
    db.add(s)
    db.commit()
    return s


def _seed_chat_message(
    db,
    *,
    session_id: str,
    msg_id: str,
    seq: int = 0,
    user_id: str = USER_ID,
    role: str = "user",
    content: str = "hello",
) -> None:
    ts = _now_ms()
    db.add(
        MessageIndex(
            id=msg_id,
            user_id=user_id,
            session_id=session_id,
            mode="chat",
            table_name="messages_chat",
            seq=seq,
            timestamp=ts,
        )
    )
    db.add(
        MessagesChat(
            id=msg_id,
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            timestamp=ts,
            is_error=False,
        )
    )
    db.commit()


# --------------------------------------------------------------------------- #
# GET /sessions  (list)
# --------------------------------------------------------------------------- #
class TestListSessions:
    def test_list_empty(self, sessions_client):
        resp = sessions_client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_sessions_with_messages(self, sessions_client, db_session):
        _seed_session(db_session, session_id="sess-1", title="First")
        _seed_chat_message(db_session, session_id="sess-1", msg_id="m1", content="hi")
        resp = sessions_client.get("/api/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "sess-1"
        assert body[0]["title"] == "First"
        assert len(body[0]["messages"]) == 1
        assert body[0]["messages"][0]["content"] == "hi"

    def test_list_session_without_messages_has_empty_list(self, sessions_client, db_session):
        _seed_session(db_session, session_id="sess-empty")
        body = sessions_client.get("/api/sessions").json()
        assert body[0]["messages"] == []

    def test_list_filters_by_mode(self, sessions_client, db_session):
        _seed_session(db_session, session_id="chat-s", mode="chat")
        _seed_session(db_session, session_id="img-s", mode="image-gen")
        body = sessions_client.get("/api/sessions?mode=image-gen").json()
        assert {s["id"] for s in body} == {"img-s"}

    def test_list_is_user_scoped(self, sessions_client, db_session):
        _seed_session(db_session, session_id="mine")
        _seed_session(db_session, session_id="theirs", user_id=OTHER_USER_ID)
        body = sessions_client.get("/api/sessions").json()
        assert {s["id"] for s in body} == {"mine"}

    def test_list_falls_back_when_cache_raises(self, db_session):
        """When get_or_set blows up, the router degrades to a direct query."""

        class _BoomCache(_FakeCache):
            async def get_or_set(self, key, fetch_func, ttl=None):
                raise RuntimeError("redis down")

        app = FastAPI()
        app.include_router(sessions_mod.router)
        app.dependency_overrides[require_current_user] = lambda: USER_ID
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_cache] = lambda: _BoomCache()
        _seed_session(db_session, session_id="fb-1", title="Fallback")
        with TestClient(app) as c:
            resp = c.get("/api/sessions")
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()[0]["id"] == "fb-1"


# --------------------------------------------------------------------------- #
# POST /sessions  (create / update)
# --------------------------------------------------------------------------- #
class TestCreateOrUpdateSession:
    def test_create_new_session_with_message(self, sessions_client, fake_cache):
        payload = {
            "id": "new-1",
            "title": "Brand New",
            "mode": "chat",
            "messages": [
                {"id": "msg-a", "mode": "chat", "role": "user", "content": "hello world"}
            ],
        }
        resp = sessions_client.post("/api/sessions", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == "new-1"
        assert body["title"] == "Brand New"
        assert body["mode"] == "chat"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "hello world"
        # cache invalidation fired with the wildcard per-mode pattern
        assert any(p.endswith(":*") for p in fake_cache.deleted)

    def test_create_image_gen_session_persists_model_name_and_metadata(
        self, sessions_client, db_session
    ):
        """An image-gen message exercises the model_name / metadata persistence branches."""
        from app.models.db_models import MessagesImageGen

        payload = {
            "id": "ig-1",
            "title": "Image Session",
            "mode": "image-gen",
            "messages": [
                {
                    "id": "ig-msg",
                    "mode": "image-gen",
                    "role": "user",
                    "content": "a cat",
                    "model_name": "imagen-3.0",
                    "generated_images": ["https://cdn.example.com/cat.png"],
                }
            ],
        }
        resp = sessions_client.post("/api/sessions", json=payload)
        assert resp.status_code == 200, resp.text
        row = db_session.query(MessagesImageGen).filter_by(id="ig-msg").first()
        assert row is not None
        assert row.model_name == "imagen-3.0"
        # metadata (generated_images) was extracted and stored as JSON.
        assert row.metadata_json is not None
        assert "generated_images" in row.metadata_json

    def test_create_session_requires_mode(self, sessions_client):
        resp = sessions_client.post(
            "/api/sessions", json={"id": "no-mode", "messages": []}
        )
        assert resp.status_code == 400
        assert "mode is required" in resp.json()["detail"]

    def test_create_session_blank_mode_rejected(self, sessions_client):
        resp = sessions_client.post(
            "/api/sessions", json={"id": "blank", "mode": "   ", "messages": []}
        )
        assert resp.status_code == 400

    def test_update_existing_session_title(self, sessions_client, db_session):
        _seed_session(db_session, session_id="upd-1", title="Old", mode="chat")
        resp = sessions_client.post(
            "/api/sessions",
            json={"id": "upd-1", "title": "Renamed", "mode": "chat", "messages": []},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed"

    def test_mode_is_immutable_on_update(self, sessions_client, db_session):
        _seed_session(db_session, session_id="imm-1", mode="chat")
        resp = sessions_client.post(
            "/api/sessions",
            json={"id": "imm-1", "mode": "image-gen", "messages": []},
        )
        assert resp.status_code == 409
        assert "immutable" in resp.json()["detail"]

    def test_cross_mode_message_rejected(self, sessions_client, db_session):
        _seed_session(db_session, session_id="cm-1", mode="chat")
        resp = sessions_client.post(
            "/api/sessions",
            json={
                "id": "cm-1",
                "mode": "chat",
                "messages": [
                    {"id": "x", "mode": "image-gen", "role": "user", "content": "c"}
                ],
            },
        )
        assert resp.status_code == 409
        assert "mismatches session.mode" in resp.json()["detail"]

    def test_convergent_delete_removes_missing_messages(self, sessions_client, db_session):
        _seed_session(db_session, session_id="cv-1", mode="chat")
        _seed_chat_message(db_session, session_id="cv-1", msg_id="keep", seq=0)
        _seed_chat_message(db_session, session_id="cv-1", msg_id="drop", seq=1)
        # Repost with only "keep" -> "drop" must be convergent-deleted.
        resp = sessions_client.post(
            "/api/sessions",
            json={
                "id": "cv-1",
                "mode": "chat",
                "messages": [
                    {"id": "keep", "mode": "chat", "role": "user", "content": "kept"}
                ],
            },
        )
        assert resp.status_code == 200
        remaining = {idx.id for idx in db_session.query(MessageIndex).all()}
        assert remaining == {"keep"}
        assert db_session.query(MessagesChat).filter_by(id="drop").first() is None

    def test_update_existing_message_content(self, sessions_client, db_session):
        _seed_session(db_session, session_id="um-1", mode="chat")
        _seed_chat_message(db_session, session_id="um-1", msg_id="m", content="orig")
        resp = sessions_client.post(
            "/api/sessions",
            json={
                "id": "um-1",
                "mode": "chat",
                "messages": [
                    {"id": "m", "mode": "chat", "role": "user", "content": "edited"}
                ],
            },
        )
        body = resp.json()
        assert body["messages"][0]["content"] == "edited"

    def test_attachment_http_url_persisted(self, sessions_client, db_session):
        _seed_session(db_session, session_id="att-1", mode="chat")
        resp = sessions_client.post(
            "/api/sessions",
            json={
                "id": "att-1",
                "mode": "chat",
                "messages": [
                    {
                        "id": "m-att",
                        "mode": "chat",
                        "role": "user",
                        "content": "with image",
                        "attachments": [
                            {
                                "id": "a1",
                                "mime_type": "image/png",
                                "name": "p.png",
                                "url": "https://cdn.example.com/p.png",
                            }
                        ],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        att = db_session.query(MessageAttachment).filter_by(id="a1").first()
        assert att is not None
        assert att.url == "https://cdn.example.com/p.png"

    def test_attachment_blob_url_is_cleared(self, sessions_client, db_session):
        """blob:/data: URLs are temporary and must never be persisted as url."""
        _seed_session(db_session, session_id="att-2", mode="chat")
        sessions_client.post(
            "/api/sessions",
            json={
                "id": "att-2",
                "mode": "chat",
                "messages": [
                    {
                        "id": "m2",
                        "mode": "chat",
                        "role": "user",
                        "content": "blob",
                        "attachments": [
                            {
                                "id": "a2",
                                "mime_type": "image/png",
                                "name": "b.png",
                                "url": "blob:http://localhost/abc",
                            }
                        ],
                    }
                ],
            },
        )
        att = db_session.query(MessageAttachment).filter_by(id="a2").first()
        assert att.url == ""
        assert att.upload_status == "pending"

    def test_attachment_url_protected_by_completed_upload_task(
        self, sessions_client, db_session
    ):
        """A completed UploadTask is the authoritative URL even if frontend sends blob."""
        _seed_session(db_session, session_id="att-3", mode="chat")
        # Pre-create the attachment + a completed upload task pointing at the CDN.
        db_session.add(
            MessageAttachment(
                id="a3",
                message_id="m3",
                user_id=USER_ID,
                session_id="att-3",
                mime_type="image/png",
                name="x.png",
                url="https://cdn.example.com/old.png",
                upload_status="completed",
            )
        )
        db_session.add(
            UploadTask(
                id="task-1",
                attachment_id="a3",
                filename="x.png",
                status="completed",
                target_url="https://cdn.example.com/final.png",
                created_at=_now_ms(),
            )
        )
        db_session.commit()
        sessions_client.post(
            "/api/sessions",
            json={
                "id": "att-3",
                "mode": "chat",
                "messages": [
                    {
                        "id": "m3",
                        "mode": "chat",
                        "role": "user",
                        "content": "blob overwrite attempt",
                        "attachments": [
                            {
                                "id": "a3",
                                "mime_type": "image/png",
                                "name": "x.png",
                                "url": "blob:http://localhost/temp",
                            }
                        ],
                    }
                ],
            },
        )
        att = db_session.query(MessageAttachment).filter_by(id="a3").first()
        assert att.url == "https://cdn.example.com/final.png"
        assert att.upload_status == "completed"

    def test_update_existing_attachment_promotes_http_url(
        self, sessions_client, db_session
    ):
        """Re-posting an existing attachment with a real HTTP url promotes it to completed."""
        _seed_session(db_session, session_id="att-4", mode="chat")
        db_session.add(
            MessageAttachment(
                id="a4",
                message_id="m4",
                user_id=USER_ID,
                session_id="att-4",
                mime_type="image/png",
                name="x.png",
                url="",
                temp_url="blob:http://localhost/old",
                upload_status="pending",
            )
        )
        db_session.commit()
        sessions_client.post(
            "/api/sessions",
            json={
                "id": "att-4",
                "mode": "chat",
                "messages": [
                    {
                        "id": "m4",
                        "mode": "chat",
                        "role": "user",
                        "content": "now uploaded",
                        "attachments": [
                            {
                                "id": "a4",
                                "mime_type": "image/png",
                                "name": "x.png",
                                "url": "https://cdn.example.com/done.png",
                            }
                        ],
                    }
                ],
            },
        )
        att = db_session.query(MessageAttachment).filter_by(id="a4").first()
        assert att.url == "https://cdn.example.com/done.png"
        assert att.upload_status == "completed"
        assert att.temp_url is None

    def test_temp_url_invalid_is_stripped(self, sessions_client, db_session):
        """A temp_url that points at /temp/ or carries expires= is cleansed to None."""
        _seed_session(db_session, session_id="att-5", mode="chat")
        sessions_client.post(
            "/api/sessions",
            json={
                "id": "att-5",
                "mode": "chat",
                "messages": [
                    {
                        "id": "m5",
                        "mode": "chat",
                        "role": "user",
                        "content": "temp",
                        "attachments": [
                            {
                                "id": "a5",
                                "mime_type": "image/png",
                                "name": "x.png",
                                "url": "https://cdn.example.com/ok.png",
                                "temp_url": "https://cdn.example.com/temp/abc?expires=123",
                            }
                        ],
                    }
                ],
            },
        )
        att = db_session.query(MessageAttachment).filter_by(id="a5").first()
        assert att.temp_url is None

    def test_convergent_delete_cancels_upload_tasks(self, sessions_client, db_session):
        """Convergent delete of a message must cancel its attachment's upload task."""
        _seed_session(db_session, session_id="cv-2", mode="chat")
        _seed_chat_message(db_session, session_id="cv-2", msg_id="keep2", seq=0)
        _seed_chat_message(db_session, session_id="cv-2", msg_id="drop2", seq=1)
        db_session.add(
            MessageAttachment(
                id="adrop",
                message_id="drop2",
                user_id=USER_ID,
                session_id="cv-2",
                mime_type="image/png",
                name="d.png",
            )
        )
        db_session.add(
            UploadTask(
                id="cvtask",
                attachment_id="adrop",
                filename="d.png",
                status="pending",
                created_at=_now_ms(),
            )
        )
        db_session.commit()
        sessions_client.post(
            "/api/sessions",
            json={
                "id": "cv-2",
                "mode": "chat",
                "messages": [
                    {"id": "keep2", "mode": "chat", "role": "user", "content": "kept"}
                ],
            },
        )
        task = db_session.query(UploadTask).filter_by(id="cvtask").first()
        assert task.status == "cancelled"
        assert db_session.query(MessageAttachment).filter_by(id="adrop").first() is None


# --------------------------------------------------------------------------- #
# GET /sessions/{id}
# --------------------------------------------------------------------------- #
class TestGetSession:
    def test_get_existing(self, sessions_client, db_session):
        _seed_session(db_session, session_id="g-1", title="Detail", mode="chat")
        _seed_chat_message(db_session, session_id="g-1", msg_id="gm", content="body")
        body = sessions_client.get("/api/sessions/g-1").json()
        assert body["id"] == "g-1"
        assert body["title"] == "Detail"
        assert body["mode"] == "chat"
        assert body["messages"][0]["content"] == "body"

    def test_get_not_found(self, sessions_client):
        resp = sessions_client.get("/api/sessions/missing")
        assert resp.status_code == 404

    def test_get_other_user_scoped_404(self, sessions_client, db_session):
        _seed_session(db_session, session_id="theirs-g", user_id=OTHER_USER_ID)
        resp = sessions_client.get("/api/sessions/theirs-g")
        assert resp.status_code == 404

    def test_get_session_without_messages(self, sessions_client, db_session):
        _seed_session(db_session, session_id="g-empty")
        body = sessions_client.get("/api/sessions/g-empty").json()
        assert body["messages"] == []


# --------------------------------------------------------------------------- #
# DELETE /sessions/{id}
# --------------------------------------------------------------------------- #
class TestDeleteSession:
    def test_delete_cascades(self, sessions_client, db_session, fake_cache):
        _seed_session(db_session, session_id="d-1", mode="chat")
        _seed_chat_message(db_session, session_id="d-1", msg_id="dm")
        db_session.add(
            MessageAttachment(
                id="datt",
                message_id="dm",
                user_id=USER_ID,
                session_id="d-1",
                mime_type="image/png",
                name="d.png",
                url="https://cdn.example.com/d.png",
            )
        )
        db_session.commit()
        resp = sessions_client.delete("/api/sessions/d-1")
        assert resp.status_code == 200
        assert resp.json() == {"success": True}
        assert db_session.query(DBChatSession).filter_by(id="d-1").first() is None
        assert db_session.query(MessageIndex).filter_by(session_id="d-1").count() == 0
        assert db_session.query(MessagesChat).filter_by(id="dm").first() is None
        assert db_session.query(MessageAttachment).filter_by(id="datt").first() is None
        assert any(p.endswith(":*") for p in fake_cache.deleted)

    def test_delete_cancels_upload_tasks(self, sessions_client, db_session):
        _seed_session(db_session, session_id="d-2", mode="chat")
        _seed_chat_message(db_session, session_id="d-2", msg_id="dm2")
        db_session.add(
            MessageAttachment(
                id="datt2",
                message_id="dm2",
                user_id=USER_ID,
                session_id="d-2",
                mime_type="image/png",
                name="d.png",
            )
        )
        db_session.add(
            UploadTask(
                id="dtask",
                attachment_id="datt2",
                filename="d.png",
                status="pending",
                created_at=_now_ms(),
            )
        )
        db_session.commit()
        sessions_client.delete("/api/sessions/d-2")
        task = db_session.query(UploadTask).filter_by(id="dtask").first()
        assert task.status == "cancelled"

    def test_delete_not_found(self, sessions_client):
        resp = sessions_client.delete("/api/sessions/nope")
        assert resp.status_code == 404

    def test_delete_other_user_404(self, sessions_client, db_session):
        _seed_session(db_session, session_id="theirs-d", user_id=OTHER_USER_ID)
        resp = sessions_client.delete("/api/sessions/theirs-d")
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# History states (favourites)
# --------------------------------------------------------------------------- #
class TestHistoryStates:
    def test_get_history_states_empty(self, sessions_client, db_session):
        _seed_session(db_session, session_id="hs-1", mode="chat")
        body = sessions_client.get("/api/sessions/hs-1/history-states").json()
        assert body["states"] == []

    def test_get_history_states_session_not_found(self, sessions_client):
        resp = sessions_client.get("/api/sessions/missing/history-states")
        assert resp.status_code == 404

    def test_favorite_then_unfavorite_message(self, sessions_client, db_session):
        _seed_session(db_session, session_id="hs-2", mode="chat")
        _seed_chat_message(db_session, session_id="hs-2", msg_id="fm")
        # favourite
        resp = sessions_client.patch(
            "/api/sessions/hs-2/history-states/fm", json={"is_favorite": True}
        )
        assert resp.status_code == 200
        assert resp.json()["is_favorite"] is True
        states = sessions_client.get("/api/sessions/hs-2/history-states").json()["states"]
        assert states[0]["message_id"] == "fm"
        # unfavourite removes the row
        resp2 = sessions_client.patch(
            "/api/sessions/hs-2/history-states/fm", json={"is_favorite": False}
        )
        assert resp2.json()["is_favorite"] is False
        assert (
            db_session.query(MessageHistoryState).filter_by(message_id="fm").count() == 0
        )

    def test_favorite_idempotent_update(self, sessions_client, db_session):
        _seed_session(db_session, session_id="hs-id", mode="chat")
        _seed_chat_message(db_session, session_id="hs-id", msg_id="fi")
        sessions_client.patch(
            "/api/sessions/hs-id/history-states/fi", json={"is_favorite": True}
        )
        # second favourite hits the existing-row branch
        resp = sessions_client.patch(
            "/api/sessions/hs-id/history-states/fi", json={"is_favorite": True}
        )
        assert resp.status_code == 200
        assert (
            db_session.query(MessageHistoryState).filter_by(message_id="fi").count() == 1
        )

    def test_update_history_state_missing_field(self, sessions_client, db_session):
        _seed_session(db_session, session_id="hs-3", mode="chat")
        resp = sessions_client.patch(
            "/api/sessions/hs-3/history-states/any", json={}
        )
        assert resp.status_code == 400

    def test_update_history_state_session_not_found(self, sessions_client):
        resp = sessions_client.patch(
            "/api/sessions/missing/history-states/x", json={"is_favorite": True}
        )
        assert resp.status_code == 404

    def test_update_history_state_message_not_found(self, sessions_client, db_session):
        _seed_session(db_session, session_id="hs-4", mode="chat")
        resp = sessions_client.patch(
            "/api/sessions/hs-4/history-states/ghost", json={"is_favorite": True}
        )
        assert resp.status_code == 404
        assert "历史项不存在" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# History preferences (show-favourites-only)
# --------------------------------------------------------------------------- #
class TestHistoryPreferences:
    def test_get_preferences_default(self, sessions_client, db_session):
        _seed_session(db_session, session_id="pref-1", mode="chat")
        body = sessions_client.get("/api/sessions/pref-1/history-preferences").json()
        assert body["show_favorites_only"] is False
        assert body["updated_at"] is None

    def test_get_preferences_session_not_found(self, sessions_client):
        resp = sessions_client.get("/api/sessions/missing/history-preferences")
        assert resp.status_code == 404

    def test_set_and_read_preference(self, sessions_client, db_session):
        _seed_session(db_session, session_id="pref-2", mode="chat")
        resp = sessions_client.patch(
            "/api/sessions/pref-2/history-preferences",
            json={"show_favorites_only": True},
        )
        assert resp.status_code == 200
        assert resp.json()["show_favorites_only"] is True
        body = sessions_client.get(
            "/api/sessions/pref-2/history-preferences"
        ).json()
        assert body["show_favorites_only"] is True
        assert body["updated_at"] is not None

    def test_update_preference_existing_row(self, sessions_client, db_session):
        _seed_session(db_session, session_id="pref-3", mode="chat")
        sessions_client.patch(
            "/api/sessions/pref-3/history-preferences",
            json={"show_favorites_only": True},
        )
        # second update flips it off via the existing-row branch
        resp = sessions_client.patch(
            "/api/sessions/pref-3/history-preferences",
            json={"show_favorites_only": False},
        )
        assert resp.json()["show_favorites_only"] is False
        cnt = (
            db_session.query(SessionHistoryPreference)
            .filter_by(session_id="pref-3")
            .count()
        )
        assert cnt == 1

    def test_update_preference_missing_field(self, sessions_client, db_session):
        _seed_session(db_session, session_id="pref-4", mode="chat")
        resp = sessions_client.patch(
            "/api/sessions/pref-4/history-preferences", json={}
        )
        assert resp.status_code == 400

    def test_update_preference_session_not_found(self, sessions_client):
        resp = sessions_client.patch(
            "/api/sessions/missing/history-preferences",
            json={"show_favorites_only": True},
        )
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# GET /sessions/{id}/attachments/{att_id}
# --------------------------------------------------------------------------- #
class TestGetAttachment:
    def _seed_attachment(self, db, **overrides) -> str:
        defaults = dict(
            id="att",
            message_id="m",
            user_id=USER_ID,
            session_id="as-1",
            mime_type="image/png",
            name="a.png",
            url="https://cdn.example.com/a.png",
            upload_status="completed",
        )
        defaults.update(overrides)
        att = MessageAttachment(**defaults)
        db.add(att)
        db.commit()
        return att.id

    def test_get_attachment(self, sessions_client, db_session):
        _seed_session(db_session, session_id="as-1", mode="chat")
        self._seed_attachment(db_session)
        body = sessions_client.get("/api/sessions/as-1/attachments/att").json()
        assert body["id"] == "att"
        assert body["url"] == "https://cdn.example.com/a.png"

    def test_get_attachment_with_completed_task_overrides_url(
        self, sessions_client, db_session
    ):
        _seed_session(db_session, session_id="as-1", mode="chat")
        self._seed_attachment(
            db_session, upload_task_id="t-att", url="https://cdn.example.com/old.png"
        )
        db_session.add(
            UploadTask(
                id="t-att",
                attachment_id="att",
                filename="a.png",
                status="completed",
                target_url="https://cdn.example.com/new.png",
                created_at=_now_ms(),
            )
        )
        db_session.commit()
        body = sessions_client.get("/api/sessions/as-1/attachments/att").json()
        assert body["url"] == "https://cdn.example.com/new.png"
        assert body["task_status"] == "completed"

    def test_get_attachment_session_not_found(self, sessions_client):
        resp = sessions_client.get("/api/sessions/missing/attachments/att")
        assert resp.status_code == 404

    def test_get_attachment_not_found(self, sessions_client, db_session):
        _seed_session(db_session, session_id="as-2", mode="chat")
        resp = sessions_client.get("/api/sessions/as-2/attachments/ghost")
        assert resp.status_code == 404
        assert "附件不存在" in resp.json()["detail"]

    def test_get_attachment_other_user_session_404(self, sessions_client, db_session):
        _seed_session(db_session, session_id="theirs-as", user_id=OTHER_USER_ID)
        resp = sessions_client.get("/api/sessions/theirs-as/attachments/att")
        assert resp.status_code == 404


# =========================================================================== #
# CHAT ROUTER
# =========================================================================== #
class _FakeService:
    """Stands in for a real provider service produced by ProviderFactory."""

    def __init__(self, *, chunks=None, response=None, raise_on_stream=False):
        self._chunks = chunks or []
        self._response = response or {}
        self._raise_on_stream = raise_on_stream
        self.calls: Dict[str, Any] = {}

    async def stream_chat(self, *, messages, model, **options):
        self.calls["messages"] = messages
        self.calls["model"] = model
        self.calls["options"] = options
        if self._raise_on_stream:
            raise RuntimeError("provider blew up mid-stream")
        for chunk in self._chunks:
            yield chunk

    async def chat(self, *, messages, model, **options):
        self.calls["messages"] = messages
        self.calls["model"] = model
        self.calls["options"] = options
        return self._response


@pytest.fixture()
def chat_client(db_session):
    app = FastAPI()
    app.include_router(chat_mod.router)
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _install_provider(
    monkeypatch,
    service: _FakeService,
    *,
    api_key: str = "k",
    base_url: Optional[str] = None,
    create_raises: Optional[Exception] = None,
):
    async def _fake_creds(*, provider, db, user_id, request_api_key, request_base_url):
        return api_key, base_url

    monkeypatch.setattr(chat_mod, "get_provider_credentials", _fake_creds)

    from app.services.common.provider_factory import ProviderFactory

    def _fake_create(*args, **kwargs):
        if create_raises is not None:
            raise create_raises
        return service

    monkeypatch.setattr(ProviderFactory, "create", staticmethod(_fake_create))


def _chat_payload(**overrides) -> Dict[str, Any]:
    payload = {
        "model_id": "gpt-4o",
        "messages": [],
        "message": "hello",
        "stream": False,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Pure helper functions
# --------------------------------------------------------------------------- #
class TestChatHelpers:
    def test_convert_messages_skips_errors_and_empty(self):
        from app.routers.core.chat import Message, convert_messages_to_provider_format

        history = [
            Message(role="user", content="keep"),
            Message(role="assistant", content="", is_error=False),
            Message(role="assistant", content="boom", is_error=True),
        ]
        out = convert_messages_to_provider_format(history, "current", provider="openai")
        # error + empty dropped, current appended
        assert [m["content"] for m in out] == ["keep", "current"]

    def test_convert_messages_model_role_to_assistant_for_non_google(self):
        from app.routers.core.chat import Message, convert_messages_to_provider_format

        out = convert_messages_to_provider_format(
            [Message(role="model", content="hi")], "", provider="openai"
        )
        assert out[0]["role"] == "assistant"

    def test_convert_messages_keeps_model_role_for_google(self):
        from app.routers.core.chat import Message, convert_messages_to_provider_format

        out = convert_messages_to_provider_format(
            [Message(role="model", content="hi")], "", provider="google"
        )
        assert out[0]["role"] == "model"

    def test_convert_messages_injects_attachments(self):
        from app.routers.core.chat import (
            Attachment,
            convert_messages_to_provider_format,
        )

        atts = [
            Attachment(id="1", mime_type="image/png", name="p.png", base64_data="ABC"),
            Attachment(id="2", mime_type="", name="skip.png"),  # no mime -> dropped
        ]
        out = convert_messages_to_provider_format(
            [], "look", provider="openai", current_attachments=atts
        )
        assert len(out) == 1
        assert len(out[0]["attachments"]) == 1
        assert out[0]["attachments"][0]["base64_data"] == "ABC"

    def test_convert_chunk_content(self):
        out = chat_mod.convert_chunk_to_frontend_format(
            {"chunk_type": "content", "content": "hello"}
        )
        assert out == {"text": "hello", "chunk_type": "content"}

    def test_convert_chunk_done_includes_usage(self):
        out = chat_mod.convert_chunk_to_frontend_format(
            {
                "chunk_type": "done",
                "prompt_tokens": 3,
                "completion_tokens": 5,
                "total_tokens": 8,
                "finish_reason": "stop",
            }
        )
        assert out["usage"]["total_tokens"] == 8
        assert out["finish_reason"] == "stop"

    def test_convert_chunk_tool_call(self):
        out = chat_mod.convert_chunk_to_frontend_format(
            {
                "chunk_type": "tool_call",
                "tool_name": "search",
                "tool_args": {"q": "x"},
                "call_id": "c1",
                "tool_type": "function",
                "browserOperationId": "b1",
            }
        )
        assert out["tool_name"] == "search"
        assert out["call_id"] == "c1"
        assert out["browser_operation_id"] == "b1"

    def test_convert_chunk_tool_result_with_error(self):
        out = chat_mod.convert_chunk_to_frontend_format(
            {
                "chunk_type": "tool_result",
                "tool_name": "search",
                "tool_result": "data",
                "tool_error": "nope",
                "screenshot_url": "http://x/s.png",
            }
        )
        assert out["tool_result"] == "data"
        assert out["tool_error"] == "nope"
        assert out["screenshot_url"] == "http://x/s.png"

    def test_convert_chunk_surfaces_error_and_browser_op(self):
        out = chat_mod.convert_chunk_to_frontend_format(
            {"chunk_type": "content", "content": "", "error": "boom", "browser_operation_id": "bz"}
        )
        assert out["error"] == "boom"
        assert out["browser_operation_id"] == "bz"

    def test_build_stream_error_done_chunk(self):
        out = chat_mod.build_stream_error_done_chunk()
        assert out["chunk_type"] == "done"
        assert out["finish_reason"] == "error"

    def test_resolve_persona_none_when_no_id(self, db_session):
        assert chat_mod.resolve_persona_system_prompt(db_session, USER_ID, None) is None

    def test_resolve_persona_returns_prompt(self, db_session):
        now = _now_ms()
        db_session.add(
            DBPersona(
                id="p1",
                user_id=USER_ID,
                name="Helpful",
                system_prompt="You are helpful.",
                icon="bot",
                created_at=now,
                updated_at=now,
            )
        )
        db_session.commit()
        prompt = chat_mod.resolve_persona_system_prompt(db_session, USER_ID, "p1")
        assert prompt == "You are helpful."

    def test_resolve_persona_unauthorized_returns_none(self, db_session):
        now = _now_ms()
        db_session.add(
            DBPersona(
                id="p2",
                user_id=OTHER_USER_ID,
                name="Theirs",
                system_prompt="secret",
                icon="bot",
                created_at=now,
                updated_at=now,
            )
        )
        db_session.commit()
        # Queried as USER_ID -> not found -> None
        assert chat_mod.resolve_persona_system_prompt(db_session, USER_ID, "p2") is None

    def test_resolve_persona_empty_prompt_returns_none(self, db_session):
        now = _now_ms()
        db_session.add(
            DBPersona(
                id="p3",
                user_id=USER_ID,
                name="Blank",
                system_prompt="   ",
                icon="bot",
                created_at=now,
                updated_at=now,
            )
        )
        db_session.commit()
        assert chat_mod.resolve_persona_system_prompt(db_session, USER_ID, "p3") is None

    def test_parse_mcp_server_type_variants(self):
        from app.services.mcp.types import MCPServerType

        assert chat_mod._parse_mcp_server_type("stdio", {}) == MCPServerType.STDIO
        assert chat_mod._parse_mcp_server_type("sse", {}) == MCPServerType.SSE
        assert chat_mod._parse_mcp_server_type("http", {}) == MCPServerType.HTTP
        assert (
            chat_mod._parse_mcp_server_type("streamable_http", {})
            == MCPServerType.STREAMABLE_HTTP
        )
        # inferred from fields
        assert (
            chat_mod._parse_mcp_server_type(None, {"command": "npx"})
            == MCPServerType.STDIO
        )
        assert (
            chat_mod._parse_mcp_server_type(None, {"url": "http://x"})
            == MCPServerType.HTTP
        )

    def test_parse_mcp_server_type_unknown_raises(self):
        with pytest.raises(ValueError):
            chat_mod._parse_mcp_server_type(None, {})

    def test_normalize_args_and_env(self):
        assert chat_mod._normalize_args(["a", 1]) == ["a", "1"]
        assert chat_mod._normalize_args("not-a-list") is None
        assert chat_mod._normalize_args(None) is None
        assert chat_mod._normalize_env({"K": 5}) == {"K": "5"}
        assert chat_mod._normalize_env("x") is None

    def test_extract_mcp_server_map_from_mcpservers(self):
        out = chat_mod._extract_mcp_server_map(
            {"mcpServers": {"srv": {"command": "npx"}, "bad": "x"}}
        )
        assert set(out.keys()) == {"srv"}

    def test_extract_mcp_server_map_root_form(self):
        out = chat_mod._extract_mcp_server_map({"srv": {"command": "npx"}})
        assert "srv" in out


# --------------------------------------------------------------------------- #
# Non-streaming chat endpoint
# --------------------------------------------------------------------------- #
class TestChatNonStreaming:
    def test_chat_happy_path(self, chat_client, monkeypatch):
        service = _FakeService(
            response={
                "content": "hi there",
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            }
        )
        _install_provider(monkeypatch, service)
        resp = chat_client.post("/api/modes/openai/chat", json=_chat_payload())
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["content"] == "hi there"
        # The current user message was forwarded to the provider.
        assert service.calls["messages"][-1]["content"] == "hello"
        assert service.calls["model"] == "gpt-4o"

    def test_chat_forwards_options(self, chat_client, monkeypatch):
        service = _FakeService(response={"content": "ok"})
        _install_provider(monkeypatch, service)
        resp = chat_client.post(
            "/api/modes/openai/chat",
            json=_chat_payload(
                options={"temperature": 0.2, "max_tokens": 64, "enable_search": True}
            ),
        )
        assert resp.status_code == 200
        opts = service.calls["options"]
        assert opts["temperature"] == 0.2
        assert opts["max_tokens"] == 64
        assert opts["enable_search"] is True

    def test_chat_google_injects_user_id_and_persona(self, chat_client, db_session, monkeypatch):
        now = _now_ms()
        db_session.add(
            DBPersona(
                id="gp",
                user_id=USER_ID,
                name="Guide",
                system_prompt="Act as a guide.",
                icon="bot",
                created_at=now,
                updated_at=now,
            )
        )
        db_session.commit()
        service = _FakeService(response={"content": "ok"})
        _install_provider(monkeypatch, service)
        resp = chat_client.post(
            "/api/modes/google/chat",
            json=_chat_payload(options={"persona_id": "gp"}),
        )
        assert resp.status_code == 200
        opts = service.calls["options"]
        # Google providers always carry user_id and fold persona into system_instruction.
        assert opts["user_id"] == USER_ID
        assert "Act as a guide." in opts["system_instruction"]

    def test_chat_invalid_option_key_400(self, chat_client, monkeypatch):
        service = _FakeService(response={"content": "ok"})
        _install_provider(monkeypatch, service)
        # ChatOptions has extra="allow"; an unknown key trips the whitelist.
        resp = chat_client.post(
            "/api/modes/openai/chat",
            json=_chat_payload(options={"definitely_not_allowed": 1}),
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == "invalid_provider_params"
        assert "definitely_not_allowed" in detail["details"]["invalid_params"]

    def test_chat_unknown_provider_maps_to_404(self, chat_client, monkeypatch):
        _install_provider(
            monkeypatch,
            _FakeService(),
            create_raises=ValueError("Provider 'bogus' is not registered"),
        )
        resp = chat_client.post("/api/modes/bogus/chat", json=_chat_payload())
        assert resp.status_code == 404
        assert "not registered" in resp.json()["detail"]

    def test_chat_provider_runtime_error_maps_to_500(self, chat_client, monkeypatch):
        class _BoomService(_FakeService):
            async def chat(self, *, messages, model, **options):
                raise RuntimeError("provider exploded")

        _install_provider(monkeypatch, _BoomService())
        resp = chat_client.post("/api/modes/openai/chat", json=_chat_payload())
        assert resp.status_code == 500
        assert "provider exploded" in resp.json()["detail"]

    def test_chat_forwards_all_openai_option_fields(self, chat_client, monkeypatch):
        """Exercise every conditional option-forwarding branch for an openai provider."""
        service = _FakeService(response={"content": "ok"})
        _install_provider(monkeypatch, service)
        resp = chat_client.post(
            "/api/modes/openai/chat",
            json=_chat_payload(
                options={
                    "temperature": 0.5,
                    "max_tokens": 32,
                    "top_p": 0.9,
                    "top_k": 40,
                    "frequency_penalty": 0.1,
                    "presence_penalty": 0.2,
                    "seed": 7,
                    "stop": ["END"],
                    "response_format": {"type": "json_object"},
                    "logit_bias": {"50256": -100},
                    "n": 2,
                    "user": "end-user-1",
                    "enable_thinking": True,
                    "enable_code_execution": True,
                    "enable_browser": True,
                    "enable_grounding": True,
                }
            ),
        )
        assert resp.status_code == 200, resp.text
        opts = service.calls["options"]
        assert opts["top_p"] == 0.9
        assert opts["top_k"] == 40
        assert opts["frequency_penalty"] == 0.1
        assert opts["presence_penalty"] == 0.2
        assert opts["seed"] == 7
        assert opts["stop"] == ["END"]
        assert opts["response_format"] == {"type": "json_object"}
        assert opts["logit_bias"] == {"50256": -100}
        assert opts["n"] == 2
        assert opts["user"] == "end-user-1"
        assert opts["enable_thinking"] is True
        assert opts["enable_code_execution"] is True
        assert opts["enable_browser"] is True
        assert opts["enable_grounding"] is True
        # openai is not a google provider -> no user_id injected
        assert "user_id" not in opts

    def test_chat_request_base_url_used_when_db_has_none(self, chat_client, monkeypatch):
        """When credentials return no base_url, the request option base_url is used."""
        service = _FakeService(response={"content": "ok"})
        captured: Dict[str, Any] = {}

        async def _fake_creds(*, provider, db, user_id, request_api_key, request_base_url):
            captured["request_base_url"] = request_base_url
            return "k", None  # db base_url is None

        monkeypatch.setattr(chat_mod, "get_provider_credentials", _fake_creds)
        from app.services.common.provider_factory import ProviderFactory

        monkeypatch.setattr(
            ProviderFactory, "create", staticmethod(lambda *a, **k: service)
        )
        resp = chat_client.post(
            "/api/modes/openai/chat",
            json=_chat_payload(options={"base_url": "https://api.custom.test/v1"}),
        )
        assert resp.status_code == 200
        assert captured["request_base_url"] == "https://api.custom.test/v1"

    def test_chat_google_with_mcp_server(self, chat_client, db_session, monkeypatch):
        """Full Google + MCP path: session resolution, tool listing, system_instruction."""
        db_session.add(
            UserMcpConfig(
                user_id=USER_ID,
                config_json=json.dumps(
                    {"mcpServers": {"sorftime": {"command": "npx", "args": ["x"]}}}
                ),
            )
        )
        db_session.commit()

        class _FakeMcpManager:
            async def create_session(self, session_id, config):
                return None

            async def get_gemini_tools(self, session_id):
                return [
                    {
                        "function_declarations": [
                            {
                                "name": "amazon_lookup",
                                "description": "lookup",
                                "parameters": {"type": "object"},
                            }
                        ]
                    }
                ]

        monkeypatch.setattr(chat_mod, "get_mcp_manager", lambda: _FakeMcpManager())
        monkeypatch.setattr(
            chat_mod, "validate_mcp_stdio_command_policy", lambda *a, **k: None
        )
        service = _FakeService(response={"content": "ok"})
        _install_provider(monkeypatch, service)

        resp = chat_client.post(
            "/api/modes/google/chat",
            json=_chat_payload(options={"mcp_server_key": "sorftime"}),
        )
        assert resp.status_code == 200, resp.text
        opts = service.calls["options"]
        assert opts["mcp_session_id"].startswith("chat:")
        # MCP tool names are folded into the system_instruction text.
        assert "amazon_lookup" in opts["system_instruction"]
        # The function declarations are forwarded to the Google provider.
        decls = opts["additional_function_declarations"]
        assert decls[0]["name"] == "amazon_lookup"

    def test_chat_google_mcp_invalid_config_400(self, chat_client, db_session, monkeypatch):
        """A non-existent MCP server key maps the ValueError to a 400."""
        db_session.add(
            UserMcpConfig(
                user_id=USER_ID,
                config_json=json.dumps({"mcpServers": {"other": {"command": "npx"}}}),
            )
        )
        db_session.commit()
        service = _FakeService(response={"content": "ok"})
        _install_provider(monkeypatch, service)
        resp = chat_client.post(
            "/api/modes/google/chat",
            json=_chat_payload(options={"mcp_server_key": "missing-key"}),
        )
        assert resp.status_code == 400
        assert "Invalid MCP server config" in resp.json()["detail"]

    def test_chat_validation_error_on_missing_field(self, chat_client, monkeypatch):
        _install_provider(monkeypatch, _FakeService())
        # missing required "message" -> FastAPI request validation 422
        resp = chat_client.post(
            "/api/modes/openai/chat", json={"model_id": "x", "messages": []}
        )
        assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Streaming chat endpoint
# --------------------------------------------------------------------------- #
class TestChatStreaming:
    def test_stream_emits_content_and_done(self, chat_client, monkeypatch):
        service = _FakeService(
            chunks=[
                {"chunk_type": "content", "content": "par"},
                {"chunk_type": "content", "content": "tial"},
                {
                    "chunk_type": "done",
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "total_tokens": 3,
                    "finish_reason": "stop",
                },
            ]
        )
        _install_provider(monkeypatch, service)
        resp = chat_client.post(
            "/api/modes/openai/chat", json=_chat_payload(stream=True)
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = resp.text
        assert '"par"' in text
        assert '"tial"' in text
        # done chunk carries usage (camelCased by encoder)
        assert "totalTokens" in text or "total_tokens" in text

    def test_stream_error_emits_safe_error_chunk(self, chat_client, monkeypatch):
        service = _FakeService(raise_on_stream=True)
        _install_provider(monkeypatch, service)
        resp = chat_client.post(
            "/api/modes/openai/chat", json=_chat_payload(stream=True)
        )
        assert resp.status_code == 200
        text = resp.text
        # The generator catches the provider exception and emits a sanitized
        # error chunk + a terminal done chunk rather than leaking the traceback.
        assert "stream_error" in text
        assert "Stream processing failed" in text


# --------------------------------------------------------------------------- #
# MCP resolution helper (async, DB-backed)
# --------------------------------------------------------------------------- #
class TestResolveMcpSessionId:
    async def test_no_config_raises(self, db_session):
        with pytest.raises(ValueError, match="No MCP config"):
            await chat_mod.resolve_mcp_session_id(db_session, USER_ID, "srv")

    async def test_invalid_json_raises(self, db_session):
        db_session.add(UserMcpConfig(user_id=USER_ID, config_json="{not json"))
        db_session.commit()
        with pytest.raises(ValueError, match="Invalid persisted MCP config JSON"):
            await chat_mod.resolve_mcp_session_id(db_session, USER_ID, "srv")

    async def test_server_not_found_raises(self, db_session):
        db_session.add(
            UserMcpConfig(
                user_id=USER_ID,
                config_json=json.dumps({"mcpServers": {"other": {"command": "npx"}}}),
            )
        )
        db_session.commit()
        with pytest.raises(ValueError, match="not found in user config"):
            await chat_mod.resolve_mcp_session_id(db_session, USER_ID, "srv")

    async def test_disabled_server_raises(self, db_session):
        db_session.add(
            UserMcpConfig(
                user_id=USER_ID,
                config_json=json.dumps(
                    {"mcpServers": {"srv": {"command": "npx", "disabled": True}}}
                ),
            )
        )
        db_session.commit()
        with pytest.raises(ValueError, match="is disabled"):
            await chat_mod.resolve_mcp_session_id(db_session, USER_ID, "srv")
