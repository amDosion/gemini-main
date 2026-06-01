import inspect
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _constraint_value(query_default, attribute):
    for metadata_item in getattr(query_default, "metadata", []):
        if hasattr(metadata_item, attribute):
            return getattr(metadata_item, attribute)
    return None


@pytest.mark.asyncio
async def test_non_critical_sessions_has_more_uses_snake_case_service_key(monkeypatch):
    from app.routers.user import init as init_router
    from app.services.common import init_service

    async def fake_sessions(user_id, db, limit=20, mode=None):
        assert user_id == "user-1"
        assert limit == 20
        assert mode == "image-gen"
        return {
            "sessions": [],
            "total": 21,
            "has_more": True,
            "error": None,
        }

    async def fake_personas(user_id, db):
        return {"personas": []}

    async def fake_storage(user_id, db):
        return {"storage_configs": [], "active_storage_id": None}

    async def fake_vertex(user_id, db):
        return {"imagenConfig": None}

    monkeypatch.setattr(init_service, "_query_sessions_with_first_messages", fake_sessions)
    monkeypatch.setattr(init_service, "_query_personas", fake_personas)
    monkeypatch.setattr(init_service, "_query_storage_configs", fake_storage)
    monkeypatch.setattr(init_service, "_query_vertex_ai_config", fake_vertex)

    result = await init_router.get_non_critical_init_data(
        user_id="user-1",
        db=object(),
        mode="image-gen",
    )

    assert result["sessionsHasMore"] is True
    assert result["sessionsTotal"] == 21
    assert result["sessionsMode"] == "image-gen"


def test_more_sessions_limit_and_offset_are_constrained():
    from app.routers.user import init as init_router

    signature = inspect.signature(init_router.get_more_sessions)

    offset_default = signature.parameters["offset"].default
    limit_default = signature.parameters["limit"].default

    assert _constraint_value(offset_default, "ge") == 0
    assert _constraint_value(limit_default, "ge") == 1
    assert _constraint_value(limit_default, "le") == 50


@pytest.mark.asyncio
async def test_more_sessions_cursor_keeps_rows_with_same_created_at():
    from app.core.database import Base
    from app.models.db_models import ChatSession, MessageIndex
    from app.services.common.init_service import _query_sessions_metadata_only

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[ChatSession.__table__, MessageIndex.__table__],
    )
    TestingSessionLocal = sessionmaker(bind=engine)

    db = TestingSessionLocal()
    try:
        for session_id in ("session-c", "session-b", "session-a"):
            db.add(
                ChatSession(
                    id=session_id,
                    user_id="user-1",
                    title=session_id,
                    mode="chat",
                    created_at=1000,
                )
            )
        db.commit()

        first_page = await _query_sessions_metadata_only(
            "user-1",
            db,
            limit=2,
            mode="chat",
        )

        assert first_page["has_more"] is True
        assert first_page["next_cursor"]

        second_page = await _query_sessions_metadata_only(
            "user-1",
            db,
            limit=2,
            cursor=first_page["next_cursor"],
            mode="chat",
        )

        first_ids = {session["id"] for session in first_page["sessions"]}
        second_ids = {session["id"] for session in second_page["sessions"]}

        assert len(first_ids) == 2
        assert second_ids == {"session-a"}
        assert first_ids.isdisjoint(second_ids)
    finally:
        db.close()
