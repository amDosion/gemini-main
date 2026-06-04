"""Coverage-focused tests for two agent service modules.

Modules under test (SUT):
  - app.services.gemini.agent.memory_bank_service
        BaseMemoryService helpers (_safe_json_loads / _serialize_structured /
        _maybe_await / _load_session_messages), InMemoryMemoryService CRUD +
        search, and VertexAiMemoryBankService DB-fallback + ADK-indexing paths
        (memory bank get/create, touch session, search parsing, create/get/delete).
  - app.services.agent.sheet_stage_protocol_service
        Pure transform builders (profile/query/export payloads, ingest kwargs,
        failure detail, summary-text extraction) and the full async protocol
        state machine ``execute_sheet_stage_protocol_request`` end-to-end
        (ingest -> profile -> query -> export) plus its error branches
        (protocol version, transition, stale/forbidden/missing artifact,
        session binding, ingest failure, missing query).

Strategy
--------
* memory_bank_service: a REAL in-memory SQLite engine populated with the actual
  SQLAlchemy models drives the service DB paths. Only the external Vertex/ADK
  SDK boundary is faked — we either disable it (``_vertexai_available=False``)
  to hit the DB fallback, or inject a fake ADK service object to exercise the
  indexing / search-parsing branches. No SUT logic is mocked.
* sheet_stage_protocol_service: the real default in-process runtime store +
  ADKArtifactService back the protocol. The real ``sheet_analyze`` builtin tool
  ingests a tiny inline CSV (pandas runs for real). Pure builders are called
  directly. Only filesystem/HTTP boundaries (never reached here) would be
  external.

asyncio_mode=auto is on (plain ``async def`` tests). filterwarnings=error::
RuntimeWarning is active, so every coroutine boundary is awaited.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.db_models import (
    AgentMemoryBank,
    AgentMemorySession,
    MessageIndex,
    MessagesChat,
    MessagesGeneric,
)

# Pin the synthetic table-analysis loader to the real, already-imported module BEFORE
# importing the gemini package (see ``_pin_table_analysis_module_to_real_import`` for
# the full rationale: numpy's C-extension can only load once per process, and the
# synthetic re-load otherwise collides with the gemini chain's numpy under ``--cov``).
from app.services.agent import adk_builtin_tools as _adk_builtin_tools  # noqa: E402


def _pin_table_analysis_module_to_real_import() -> None:
    """Make the synthetic table-analysis loader reuse the real, already-imported module.

    ``adk_builtin_tools._load_table_analysis_module`` loads
    ``app/services/common/table_analysis_service.py`` under a *synthetic* module name
    via ``importlib.util.spec_from_file_location`` and re-executes it. That
    re-execution re-imports numpy's C-extension, which can only be loaded ONCE per
    process. Under ``--cov=app.services.gemini.agent.memory_bank_service`` the cov
    machinery imports the gemini/vertexai chain (loading numpy) before this module
    runs, so the synthetic re-load fails and ``sheet_analyze`` reports a spurious
    "requires pandas dependency".

    We sidestep that purely-environmental hazard by importing the REAL
    ``table_analysis_service`` module (which shares the process's single numpy) and
    pinning it into the loader's module cache. The loader then returns the genuine
    module — the real ``sheet_analyze`` analysis path still runs end-to-end; nothing
    in the SUT is mocked or stubbed.
    """
    import app.services.common.table_analysis_service as _real_table_analysis

    _adk_builtin_tools._TABLE_ANALYSIS_MODULE_CACHE = _real_table_analysis


_pin_table_analysis_module_to_real_import()

from app.services.gemini.agent.memory_bank_service import (  # noqa: E402
    BaseMemoryService,
    InMemoryMemoryService,
    VertexAiMemoryBankService,
)

from app.services.agent.sheet_stage_protocol_service import (
    SheetStageProtocolError,
    build_export_payload,
    build_profile_payload_from_ingest,
    build_query_payload,
    build_sheet_ingest_kwargs_from_request,
    build_sheet_stage_failure_detail,
    execute_sheet_stage_protocol_request,
    extract_sheet_stage_summary_text,
    get_default_sheet_stage_artifact_service,
    get_default_sheet_stage_runtime_store,
)
from app.services.agent.adk_artifact_service import ADKArtifactService
from app.services.agent.workflow_runtime_store import (
    LocalWorkflowRuntimeStore,
    RedisWorkflowRuntimeStore,
    WorkflowRuntimeStore,
)


USER_ID = "user-mem-1"
OTHER_USER_ID = "user-mem-2"


# --------------------------------------------------------------------------- #
# Shared in-memory DB fixture for memory_bank_service tests
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


def _seed_chat_message(
    db,
    *,
    msg_id: str,
    user_id: str,
    session_id: str,
    seq: int,
    role: str,
    content: str,
    table_name: str = "messages_chat",
) -> None:
    db.add(
        MessageIndex(
            id=msg_id,
            user_id=user_id,
            session_id=session_id,
            mode="chat",
            table_name=table_name,
            seq=seq,
            timestamp=1_700_000_000_000 + seq,
        )
    )
    model = MessagesChat if table_name == "messages_chat" else MessagesGeneric
    db.add(
        model(
            id=msg_id,
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            timestamp=1_700_000_000_000 + seq,
        )
    )


# =========================================================================== #
# BaseMemoryService static helpers
# =========================================================================== #
class TestBaseMemoryHelpers:
    async def test_maybe_await_passes_through_plain_value(self):
        assert await BaseMemoryService._maybe_await(42) == 42

    async def test_maybe_await_awaits_coroutine(self):
        async def coro():
            return "done"

        assert await BaseMemoryService._maybe_await(coro()) == "done"

    def test_safe_json_loads_valid_and_invalid(self):
        assert BaseMemoryService._safe_json_loads('{"a": 1}') == {"a": 1}
        assert BaseMemoryService._safe_json_loads("not-json", default={"x": 1}) == {"x": 1}
        assert BaseMemoryService._safe_json_loads("", default=[]) == []
        assert BaseMemoryService._safe_json_loads(None) is None

    def test_serialize_structured_primitives_and_none(self):
        assert BaseMemoryService._serialize_structured(None) is None
        assert BaseMemoryService._serialize_structured("s") == "s"
        assert BaseMemoryService._serialize_structured(5) == 5
        assert BaseMemoryService._serialize_structured([1, 2]) == [1, 2]
        assert BaseMemoryService._serialize_structured({"k": "v"}) == {"k": "v"}

    def test_serialize_structured_model_dump(self):
        class HasModelDump:
            def model_dump(self):
                return {"dumped": True}

        assert BaseMemoryService._serialize_structured(HasModelDump()) == {"dumped": True}

    def test_serialize_structured_dict_method(self):
        class HasDict:
            def dict(self):
                return {"viadict": 1}

        assert BaseMemoryService._serialize_structured(HasDict()) == {"viadict": 1}

    def test_serialize_structured_falls_back_to_str(self):
        class Weird:
            def __str__(self):
                return "weird-repr"

        assert BaseMemoryService._serialize_structured(Weird()) == "weird-repr"

    def test_serialize_structured_model_dump_raises_then_str(self):
        class Broken:
            def model_dump(self):
                raise RuntimeError("boom")

            def __str__(self):
                return "broken-str"

        assert BaseMemoryService._serialize_structured(Broken()) == "broken-str"


# =========================================================================== #
# _load_session_messages (real DB)
# =========================================================================== #
class TestLoadSessionMessages:
    def test_loads_ordered_messages_and_skips_blank(self, db_session):
        _seed_chat_message(
            db_session, msg_id="m2", user_id=USER_ID, session_id="s1",
            seq=2, role="MODEL", content="second",
        )
        _seed_chat_message(
            db_session, msg_id="m1", user_id=USER_ID, session_id="s1",
            seq=1, role="user", content="first",
        )
        _seed_chat_message(
            db_session, msg_id="m3", user_id=USER_ID, session_id="s1",
            seq=3, role="user", content="   ",
        )
        db_session.commit()

        svc = InMemoryMemoryService(db_session)
        messages = svc._load_session_messages(user_id=USER_ID, session_id="s1")

        assert [m["content"] for m in messages] == ["first", "second"]
        assert messages[1]["role"] == "model"
        assert messages[0]["seq"] == 1

    def test_index_without_message_row_is_skipped(self, db_session):
        db_session.add(
            MessageIndex(
                id="orphan", user_id=USER_ID, session_id="s2", mode="chat",
                table_name="messages_chat", seq=1, timestamp=1,
            )
        )
        db_session.commit()
        svc = InMemoryMemoryService(db_session)
        assert svc._load_session_messages(user_id=USER_ID, session_id="s2") == []

    def test_unknown_table_name_falls_back_to_generic(self, db_session):
        db_session.add(
            MessageIndex(
                id="g1", user_id=USER_ID, session_id="s3", mode="weird",
                table_name="messages_unknown_mode", seq=1, timestamp=10,
            )
        )
        db_session.add(
            MessagesGeneric(
                id="g1", user_id=USER_ID, session_id="s3",
                role="user", content="generic-content", timestamp=10,
            )
        )
        db_session.commit()
        svc = InMemoryMemoryService(db_session)
        messages = svc._load_session_messages(user_id=USER_ID, session_id="s3")
        assert messages[0]["content"] == "generic-content"


# =========================================================================== #
# InMemoryMemoryService
# =========================================================================== #
class TestInMemoryMemoryService:
    async def test_add_session_to_memory_aggregates(self, db_session):
        _seed_chat_message(
            db_session, msg_id="a1", user_id=USER_ID, session_id="sess",
            seq=1, role="user", content="hello",
        )
        _seed_chat_message(
            db_session, msg_id="a2", user_id=USER_ID, session_id="sess",
            seq=2, role="model", content="world",
        )
        db_session.commit()

        svc = InMemoryMemoryService(db_session)
        result = await svc.add_session_to_memory(user_id=USER_ID, session_id="sess")
        assert len(result) == 1
        assert result[0]["message_count"] == 2
        assert "user: hello" in result[0]["content"]
        assert "model: world" in result[0]["content"]

    async def test_add_session_to_memory_empty_returns_empty(self, db_session):
        svc = InMemoryMemoryService(db_session)
        assert await svc.add_session_to_memory(user_id=USER_ID, session_id="missing") == []

    async def test_search_memory_matches_and_limits(self, db_session):
        svc = InMemoryMemoryService(db_session)
        await svc.create_memory(user_id=USER_ID, content="apple pie recipe")
        await asyncio.sleep(0.002)
        await svc.create_memory(user_id=USER_ID, content="apple juice notes")
        await svc.create_memory(user_id=USER_ID, content="banana bread")

        matches = await svc.search_memory(user_id=USER_ID, query="APPLE")
        assert len(matches) == 2
        assert matches[0]["content"] == "apple juice notes"

        limited = await svc.search_memory(user_id=USER_ID, query="apple", limit=1)
        assert len(limited) == 1

    async def test_search_memory_unknown_user(self, db_session):
        svc = InMemoryMemoryService(db_session)
        assert await svc.search_memory(user_id="nobody", query="x") == []

    async def test_create_get_delete_roundtrip(self, db_session):
        svc = InMemoryMemoryService(db_session)
        mem = await svc.create_memory(
            user_id=USER_ID, content="remember this",
            memory_bank_id="bank-1", session_id="sx", metadata={"tag": "t"},
        )
        mem_id = mem["id"]
        assert mem["metadata"] == {"tag": "t"}

        fetched = await svc.get_memory(user_id=USER_ID, memory_id=mem_id)
        assert fetched is not None and fetched["content"] == "remember this"

        assert await svc.get_memory(user_id=USER_ID, memory_id="nope") is None

        assert await svc.delete_memory(user_id=USER_ID, memory_id=mem_id) is True
        assert await svc.delete_memory(user_id=USER_ID, memory_id=mem_id) is False
        assert await svc.get_memory(user_id=USER_ID, memory_id=mem_id) is None


# =========================================================================== #
# VertexAiMemoryBankService - DB fallback + ADK indexing
# =========================================================================== #
class _FakeADKService:
    """Stand-in for the external ADK Vertex memory client.

    Records calls and returns a structured search response shaped like what the
    real SDK serializes to (memories -> content.parts[].text).
    """

    def __init__(self, *, search_response: Any = None, raise_on_add: bool = False,
                 raise_on_search: bool = False):
        self.search_response = search_response
        self.raise_on_add = raise_on_add
        self.raise_on_search = raise_on_search
        self.added_sessions: List[Any] = []
        self.search_calls: List[Dict[str, Any]] = []

    async def add_session_to_memory(self, adk_session):
        if self.raise_on_add:
            raise RuntimeError("adk add failed")
        self.added_sessions.append(adk_session)
        return {"ok": True}

    async def search_memory(self, *, app_name, user_id, query):
        self.search_calls.append({"app_name": app_name, "user_id": user_id, "query": query})
        if self.raise_on_search:
            raise RuntimeError("adk search failed")
        return self.search_response


def _make_vertex_service(db, *, vertex_available: bool = False) -> VertexAiMemoryBankService:
    svc = VertexAiMemoryBankService(db, project="proj", location="us-central1", agent_engine_id="engine-x")
    # Force a deterministic external-boundary state regardless of whether the
    # ADK SDK happens to import in this environment.
    svc._vertexai_available = vertex_available
    if not vertex_available:
        svc._ADKMemoryBankServiceClass = None
    return svc


class TestVertexMemoryBankDbPaths:
    async def test_get_or_create_memory_bank_creates_then_reuses(self, db_session):
        svc = _make_vertex_service(db_session)
        bank = await svc._get_or_create_memory_bank(USER_ID)
        assert bank.user_id == USER_ID
        assert bank.vertex_memory_bank_id == "engine-x"
        config = json.loads(bank.config_json)
        assert config["app_name"] == f"gemini-memory-{USER_ID}"

        again = await svc._get_or_create_memory_bank(USER_ID)
        assert again.id == bank.id

    async def test_get_or_create_memory_bank_by_explicit_id(self, db_session):
        svc = _make_vertex_service(db_session)
        bank = await svc._get_or_create_memory_bank(USER_ID)
        resolved = await svc._get_or_create_memory_bank(USER_ID, memory_bank_id=bank.id)
        assert resolved.id == bank.id

    async def test_get_or_create_unknown_id_falls_back_to_create(self, db_session):
        svc = _make_vertex_service(db_session)
        bank = await svc._get_or_create_memory_bank(USER_ID, memory_bank_id="does-not-exist")
        assert bank.user_id == USER_ID

    async def test_create_get_delete_memory_db(self, db_session):
        svc = _make_vertex_service(db_session)
        mem = await svc.create_memory(
            user_id=USER_ID, content="db memory", metadata={"k": "v"},
        )
        mem_id = mem["id"]
        assert mem["content"] == "db memory"
        assert mem["metadata"] == {"k": "v"}

        fetched = await svc.get_memory(user_id=USER_ID, memory_id=mem_id)
        assert fetched is not None

        assert await svc.get_memory(user_id=OTHER_USER_ID, memory_id=mem_id) is None
        assert await svc.delete_memory(user_id=OTHER_USER_ID, memory_id=mem_id) is False

        assert await svc.delete_memory(user_id=USER_ID, memory_id=mem_id) is True
        assert await svc.get_memory(user_id=USER_ID, memory_id=mem_id) is None

    async def test_create_memory_without_metadata_stores_null(self, db_session):
        svc = _make_vertex_service(db_session)
        mem = await svc.create_memory(user_id=USER_ID, content="no-meta")
        assert mem.get("metadata") is None

    async def test_search_memory_db_fallback_ilike(self, db_session):
        svc = _make_vertex_service(db_session)
        await svc.create_memory(user_id=USER_ID, content="The quick brown fox")
        await svc.create_memory(user_id=USER_ID, content="lazy dog sleeps")

        results = await svc.search_memory(user_id=USER_ID, query="brown")
        assert len(results) == 1
        assert "brown" in results[0]["content"]

        assert await svc.search_memory(user_id=USER_ID, query="zzz-nomatch") == []

    async def test_add_session_to_memory_db_snapshot_and_update(self, db_session):
        _seed_chat_message(
            db_session, msg_id="v1", user_id=USER_ID, session_id="vsess",
            seq=1, role="user", content="line one",
        )
        _seed_chat_message(
            db_session, msg_id="v2", user_id=USER_ID, session_id="vsess",
            seq=2, role="model", content="line two",
        )
        db_session.commit()

        svc = _make_vertex_service(db_session)
        out = await svc.add_session_to_memory(user_id=USER_ID, session_id="vsess")
        assert len(out) == 1
        first_id = out[0]["id"]
        meta = out[0]["metadata"]
        assert meta["source"] == "db"
        assert meta["message_count"] == 2

        sess = db_session.query(AgentMemorySession).filter(
            AgentMemorySession.session_id == "vsess",
        ).first()
        assert sess is not None

        out2 = await svc.add_session_to_memory(user_id=USER_ID, session_id="vsess")
        assert out2[0]["id"] == first_id

    async def test_add_session_to_memory_empty_returns_empty(self, db_session):
        svc = _make_vertex_service(db_session)
        assert await svc.add_session_to_memory(user_id=USER_ID, session_id="empty") == []

    async def test_touch_memory_session_creates_then_refreshes(self, db_session):
        svc = _make_vertex_service(db_session)
        bank = await svc._get_or_create_memory_bank(USER_ID)
        rec1 = await svc._touch_memory_session(
            user_id=USER_ID, memory_bank_id=bank.id, session_id="touch-sess",
        )
        assert rec1["session_id"] == "touch-sess"
        created_at = rec1["created_at"]

        await asyncio.sleep(0.002)
        rec2 = await svc._touch_memory_session(
            user_id=USER_ID, memory_bank_id=bank.id, session_id="touch-sess",
        )
        assert rec2["created_at"] == created_at
        assert rec2["last_used_at"] >= created_at


class TestVertexMemoryBankAdkPaths:
    async def test_add_session_indexed_by_vertex(self, db_session):
        _seed_chat_message(
            db_session, msg_id="i1", user_id=USER_ID, session_id="isess",
            seq=1, role="user", content="indexed line",
        )
        db_session.commit()

        svc = _make_vertex_service(db_session, vertex_available=True)
        fake = _FakeADKService()
        svc._ensure_adk_service = lambda memory_bank: fake  # type: ignore[assignment]

        out = await svc.add_session_to_memory(user_id=USER_ID, session_id="isess")
        assert len(fake.added_sessions) == 1
        assert out[0]["metadata"]["source"] == "vertex+db"

    async def test_add_session_adk_failure_falls_back_to_db(self, db_session):
        _seed_chat_message(
            db_session, msg_id="f1", user_id=USER_ID, session_id="fsess",
            seq=1, role="user", content="fallback line",
        )
        db_session.commit()

        svc = _make_vertex_service(db_session, vertex_available=True)
        fake = _FakeADKService(raise_on_add=True)
        svc._ensure_adk_service = lambda memory_bank: fake  # type: ignore[assignment]

        out = await svc.add_session_to_memory(user_id=USER_ID, session_id="fsess")
        assert out[0]["metadata"]["source"] == "db"

    async def test_search_memory_vertex_parsed_results(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=True)
        response = {
            "memories": [
                {"content": {"parts": [{"text": "vertex hit one"}]}},
                {"text": "vertex hit two"},
                {"content": {"parts": [{"text": ""}]}},  # empty -> skipped
            ]
        }
        fake = _FakeADKService(search_response=response)
        svc._ensure_adk_service = lambda memory_bank: fake  # type: ignore[assignment]

        results = await svc.search_memory(user_id=USER_ID, query="vertex")
        assert [r["content"] for r in results] == ["vertex hit one", "vertex hit two"]
        assert all(r["source"] == "vertex" for r in results)
        assert fake.search_calls[0]["query"] == "vertex"

    async def test_search_memory_vertex_empty_falls_back_to_db(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=True)
        await svc.create_memory(user_id=USER_ID, content="db side memory")
        fake = _FakeADKService(search_response={"memories": []})
        svc._ensure_adk_service = lambda memory_bank: fake  # type: ignore[assignment]

        results = await svc.search_memory(user_id=USER_ID, query="db side")
        assert len(results) == 1
        assert "db side" in results[0]["content"]

    async def test_search_memory_vertex_raises_falls_back_to_db(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=True)
        await svc.create_memory(user_id=USER_ID, content="resilient memory")
        fake = _FakeADKService(raise_on_search=True)
        svc._ensure_adk_service = lambda memory_bank: fake  # type: ignore[assignment]

        results = await svc.search_memory(user_id=USER_ID, query="resilient")
        assert len(results) == 1

    def test_resolve_memory_app_name_from_config_and_default(self, db_session):
        svc = _make_vertex_service(db_session)
        bank_with_cfg = AgentMemoryBank(
            user_id=USER_ID, name="b", vertex_memory_bank_id="e",
            config_json=json.dumps({"app_name": "custom-app"}),
            created_at=1, updated_at=1,
        )
        assert svc._resolve_memory_app_name(bank_with_cfg, USER_ID) == "custom-app"

        bank_no_cfg = AgentMemoryBank(
            user_id=USER_ID, name="b", vertex_memory_bank_id="e",
            config_json=None, created_at=1, updated_at=1,
        )
        assert svc._resolve_memory_app_name(bank_no_cfg, USER_ID) == f"gemini-memory-{USER_ID}"

    def test_ensure_adk_service_disabled_returns_none(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=False)
        bank = AgentMemoryBank(
            user_id=USER_ID, name="b", vertex_memory_bank_id="e",
            config_json=None, created_at=1, updated_at=1,
        )
        assert svc._ensure_adk_service(bank) is None

    def test_ensure_adk_service_no_engine_id_returns_none(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=True)
        svc._ADKMemoryBankServiceClass = lambda **kw: object()  # type: ignore[assignment]
        svc.agent_engine_id = None
        bank = AgentMemoryBank(
            user_id=USER_ID, name="b", vertex_memory_bank_id=None,
            config_json=None, created_at=1, updated_at=1,
        )
        assert svc._ensure_adk_service(bank) is None

    def test_ensure_adk_service_constructs_and_caches(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=True)
        constructed: List[Dict[str, Any]] = []

        def _factory(**kwargs):
            constructed.append(kwargs)
            return object()

        svc._ADKMemoryBankServiceClass = _factory  # type: ignore[assignment]
        bank = AgentMemoryBank(
            user_id=USER_ID, name="b", vertex_memory_bank_id="engine-abc",
            config_json=None, created_at=1, updated_at=1,
        )
        first = svc._ensure_adk_service(bank)
        second = svc._ensure_adk_service(bank)
        assert first is second  # cached by engine id
        assert len(constructed) == 1
        assert constructed[0]["agent_engine_id"] == "engine-abc"

    def test_ensure_adk_service_construct_failure_returns_none(self, db_session):
        svc = _make_vertex_service(db_session, vertex_available=True)

        def _boom(**kwargs):
            raise RuntimeError("cannot init")

        svc._ADKMemoryBankServiceClass = _boom  # type: ignore[assignment]
        bank = AgentMemoryBank(
            user_id=USER_ID, name="b", vertex_memory_bank_id="engine-z",
            config_json=None, created_at=1, updated_at=1,
        )
        assert svc._ensure_adk_service(bank) is None

    def test_extract_memory_entry_text_branches(self, db_session):
        svc = _make_vertex_service(db_session)
        assert svc._extract_memory_entry_text(
            {"content": {"parts": [{"text": "x"}]}}
        ) == "x"
        assert svc._extract_memory_entry_text({"text": "direct"}) == "direct"
        assert svc._extract_memory_entry_text({"nothing": True}) == ""

    def test_parse_adk_search_results_non_list_and_limit(self, db_session):
        svc = _make_vertex_service(db_session)
        assert svc._parse_adk_search_results({"memories": "not-a-list"}, limit=5) == []
        assert svc._parse_adk_search_results("not-a-dict", limit=5) == []
        big = {"memories": [{"text": f"m{i}"} for i in range(5)]}
        parsed = svc._parse_adk_search_results(big, limit=2)
        assert len(parsed) == 2


# =========================================================================== #
# sheet_stage_protocol_service - pure builders
# =========================================================================== #
class TestSheetPureBuilders:
    def test_build_failure_detail_normalizes_stage(self):
        detail = build_sheet_stage_failure_detail(
            stage="bogus", session_id="", message="oops",
        )
        assert detail["stage"] == "ingest"  # unknown -> ingest
        assert detail["session_id"] == "pending"  # empty -> pending
        assert detail["status"] == "failed"
        assert detail["error"]["message"] == "oops"

    def test_build_failure_detail_keeps_known_stage(self):
        detail = build_sheet_stage_failure_detail(
            stage="export", session_id="sid-1", message="bad", error_code="X",
        )
        assert detail["stage"] == "export"
        assert detail["session_id"] == "sid-1"
        assert detail["error"]["code"] == "X"

    def test_extract_summary_prefers_error_message(self):
        env = {"error": {"message": "the error"}, "data": {"payload": {"rendered": "x"}}}
        assert extract_sheet_stage_summary_text(env) == "the error"

    def test_extract_summary_payload_text_fields(self):
        env = {"data": {"payload": {"answer": "the answer"}}}
        assert extract_sheet_stage_summary_text(env) == "the answer"

    def test_extract_summary_from_summary_counts(self):
        env = {"data": {"payload": {"summary": {"row_count": 3, "column_count": 2}}}}
        assert extract_sheet_stage_summary_text(env) == "3 rows, 2 columns"

    def test_extract_summary_stage_status_fallback(self):
        env = {"stage": "query", "status": "completed", "data": {"payload": {}}}
        assert extract_sheet_stage_summary_text(env) == "sheet-stage query: completed"

    def test_extract_summary_non_dict_and_empty(self):
        assert extract_sheet_stage_summary_text("nope") == ""
        assert extract_sheet_stage_summary_text({}) == ""

    def test_build_profile_payload_from_ingest(self):
        ingest_payload = {
            "file_name": "data.csv",
            "file_format": "csv",
            "source_type": "inline",
            "analysis": {
                "summary": {"row_count": 10, "column_count": 3},
                "columns": [
                    {"name": "a"},
                    {"column": "b"},
                    {"name": ""},  # skipped
                    "not-a-dict",  # skipped
                ],
            },
        }
        profile = build_profile_payload_from_ingest(ingest_payload)
        assert profile["summary"] == {"row_count": 10, "column_count": 3}
        assert profile["columns"] == ["a", "b"]
        assert profile["source"]["file_name"] == "data.csv"

    def test_build_profile_payload_defaults_column_count(self):
        ingest_payload = {
            "analysis": {"summary": {}, "columns": [{"name": "x"}, {"name": "y"}]},
        }
        profile = build_profile_payload_from_ingest(ingest_payload)
        assert profile["summary"]["column_count"] == 2

    def test_build_query_payload(self):
        profile = {"summary": {"row_count": 4, "column_count": 2}, "columns": ["a", "b"]}
        out = build_query_payload(profile_payload=profile, query_text="count rows")
        assert out["query"] == "count rows"
        assert "4 rows, 2 columns" in out["answer"]
        assert out["columns"] == ["a", "b"]

    def test_build_export_payload_json_and_markdown(self):
        query_payload = {
            "query": "q", "answer": "a",
            "summary": {"row_count": 1, "column_count": 1}, "columns": ["c"],
        }
        json_out = build_export_payload(
            query_payload=query_payload, user_id=USER_ID, export_format="json",
        )
        assert json_out["export_format"] == "json"
        assert json.loads(json_out["rendered"])["query"] == "q"
        assert json_out["export_precheck"]["status"] == "passed"

        md_out = build_export_payload(
            query_payload=query_payload, user_id=USER_ID, export_format="weird",
        )
        assert md_out["export_format"] == "markdown"
        assert "# Sheet Query Result" in md_out["rendered"]


# =========================================================================== #
# build_sheet_ingest_kwargs_from_request - source resolution branches
# =========================================================================== #
class TestBuildIngestKwargs:
    def test_inline_content_branch(self):
        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"content": "a,b\n1,2", "content_encoding": "plain"},
            user_id=USER_ID,
        )
        assert kwargs["content"] == "a,b\n1,2"
        assert kwargs["content_encoding"] == "plain"
        assert kwargs["tenant_id"] == USER_ID
        assert kwargs["export_format"] == "json"

    def test_data_url_branch(self):
        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"data_url": "data:text/csv;base64,YQ=="},
            user_id=USER_ID,
        )
        assert kwargs["data_url"] == "data:text/csv;base64,YQ=="
        assert "content" not in kwargs

    def test_http_file_url_branch(self):
        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"file_url": "https://example.com/x.csv"},
            user_id=USER_ID,
        )
        assert kwargs["file_url"] == "https://example.com/x.csv"

    def test_base64_data_url_in_file_url(self):
        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"file_url": "data:text/csv;base64,YQ=="},
            user_id=USER_ID,
        )
        assert kwargs["data_url"] == "data:text/csv;base64,YQ=="

    def test_local_file_url_read_as_base64(self, tmp_path):
        f = tmp_path / "local.csv"
        f.write_text("col\nval\n", encoding="utf-8")
        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"file_url": str(f)},
            user_id=USER_ID,
        )
        assert kwargs["content_encoding"] == "base64"
        assert kwargs["file_name"] == "local.csv"

    def test_nonexistent_local_path_treated_as_file_url(self, tmp_path):
        missing = tmp_path / "ghost.csv"
        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"file_url": str(missing)},
            user_id=USER_ID,
        )
        assert kwargs["file_url"] == str(missing)

    def test_no_source_without_resolver_raises(self):
        with pytest.raises(ValueError, match="content, data_url, file_url"):
            build_sheet_ingest_kwargs_from_request(
                request_body={"file_name": "x.csv"}, user_id=USER_ID,
            )

    def test_resolver_returns_http_url(self):
        def resolver(attachment_id, file_url, file_path):
            return "https://resolved.example.com/data.csv"

        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"attachment_id": "att-1"},
            user_id=USER_ID,
            resolve_file_reference=resolver,
        )
        assert kwargs["file_url"] == "https://resolved.example.com/data.csv"

    def test_resolver_returns_data_url(self):
        def resolver(attachment_id, file_url, file_path):
            return "data:text/csv;base64,YQ=="

        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"attachment_id": "att-2"},
            user_id=USER_ID,
            resolve_file_reference=resolver,
        )
        assert kwargs["data_url"] == "data:text/csv;base64,YQ=="

    def test_resolver_returns_local_path(self, tmp_path):
        f = tmp_path / "resolved.csv"
        f.write_text("h\nv\n", encoding="utf-8")

        def resolver(attachment_id, file_url, file_path):
            return str(f)

        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body={"attachment_id": "att-3"},
            user_id=USER_ID,
            resolve_file_reference=resolver,
        )
        assert kwargs["content_encoding"] == "base64"
        assert kwargs["file_name"] == "resolved.csv"

    def test_request_to_payload_via_model_dump(self):
        class _Body:
            def model_dump(self, by_alias=False):
                return {"content": "x,y\n1,2"}

        kwargs = build_sheet_ingest_kwargs_from_request(
            request_body=_Body(), user_id=USER_ID,
        )
        assert kwargs["content"] == "x,y\n1,2"


# =========================================================================== #
# SheetStageProtocolError shape
# =========================================================================== #
class TestSheetStageProtocolError:
    def test_message_extracted_from_detail(self):
        err = SheetStageProtocolError(
            status_code=409,
            detail={"error": {"message": "conflict here"}},
        )
        assert err.status_code == 409
        assert "conflict here" in str(err)

    def test_default_message_when_detail_missing(self):
        err = SheetStageProtocolError(status_code=400, detail={"no": "error"})
        assert str(err) == "sheet stage protocol failed"


# =========================================================================== #
# execute_sheet_stage_protocol_request - full state machine, isolated store
# =========================================================================== #
class _InertRedisPool:
    """A connection pool stub that never yields a Redis connection.

    Passing this to ``RedisWorkflowRuntimeStore`` keeps the store on its
    local-fallback path deterministically, bypassing the process-global
    ``GlobalRedisConnectionPool`` (which may be reachable in this environment
    and whose connection is bound to whichever event loop first touched it —
    a cross-test-loop hazard under asyncio_mode=auto). This isolates each
    sheet-stage test fully while still exercising the real local runtime store.
    """

    def is_initialized(self) -> bool:
        return True

    def get_connection(self):
        return None


@pytest.fixture()
def isolated_artifact_service() -> ADKArtifactService:
    """A fresh local-backed artifact service so each test starts with empty state.

    The store uses a dedicated :class:`LocalWorkflowRuntimeStore` (its own private
    cache) plus a Redis store wired to an inert pool so it always falls back to
    local. Combined with a per-test-unique namespace this guarantees zero leakage
    of session/invocation/artifact records across tests, independent of any
    process-global Redis or coverage-tracing timing effects.
    """
    unique = uuid.uuid4().hex[:12]
    local_store = LocalWorkflowRuntimeStore(shared_state={}, shared_payload_state={})
    redis_store = RedisWorkflowRuntimeStore(
        redis_pool=_InertRedisPool(),
        key_prefix=f"test:wf:{unique}",
    )
    store = WorkflowRuntimeStore(redis_store=redis_store, local_store=local_store)
    return ADKArtifactService(runtime_store=store, namespace=f"sheet-stage-test-{unique}")


@pytest.fixture()
def invocation_id() -> str:
    """Per-test unique invocation id.

    The invocation->session binding is keyed by invocation_id; a process-global
    Redis (reachable in this environment) could otherwise let one test's binding
    collide with another's. A unique id per test guarantees independence even if
    the underlying runtime store is shared at the process level.
    """
    return f"inv-{uuid.uuid4().hex[:12]}"


_INLINE_CSV = "name,score\nAlice,90\nBob,80\n"


async def _run_ingest(artifact_service, invocation_id, *, user_id=USER_ID):
    return await execute_sheet_stage_protocol_request(
        request_body={
            "stage": "ingest",
            "content": _INLINE_CSV,
            "content_encoding": "plain",
            "file_format": "csv",
            "file_name": "sheet.csv",
            "invocation_id": invocation_id,
        },
        user_id=user_id,
        artifact_service=artifact_service,
    )


class TestSheetStageStateMachine:
    async def test_full_ingest_profile_query_export(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service

        ingest_env = await _run_ingest(svc, invocation_id)
        assert ingest_env["status"] == "completed"
        assert ingest_env["stage"] == "ingest"
        session_id = ingest_env["session_id"]
        ingest_artifact = ingest_env["artifact"]
        assert ingest_artifact["artifact_key"] == "sheet/ingest"
        assert ingest_env["data"]["next_stage"] == "profile"

        profile_env = await execute_sheet_stage_protocol_request(
            request_body={
                "stage": "profile",
                "session_id": session_id,
                "artifact": ingest_artifact,
                "invocation_id": invocation_id,
            },
            user_id=USER_ID,
            artifact_service=svc,
        )
        assert profile_env["status"] == "completed"
        profile_artifact = profile_env["artifact"]
        assert profile_artifact["artifact_key"] == "sheet/profile"
        assert profile_env["data"]["payload"]["summary"]["row_count"] == 2

        query_env = await execute_sheet_stage_protocol_request(
            request_body={
                "stage": "query",
                "session_id": session_id,
                "artifact": profile_artifact,
                "query": "how many rows",
                "invocation_id": invocation_id,
            },
            user_id=USER_ID,
            artifact_service=svc,
        )
        assert query_env["status"] == "completed"
        query_artifact = query_env["artifact"]
        assert "how many rows" in query_env["data"]["payload"]["answer"]

        export_env = await execute_sheet_stage_protocol_request(
            request_body={
                "stage": "export",
                "session_id": session_id,
                "artifact": query_artifact,
                "export_format": "json",
                "invocation_id": invocation_id,
            },
            user_id=USER_ID,
            artifact_service=svc,
        )
        assert export_env["status"] == "completed"
        assert export_env["stage"] == "export"
        payload = export_env["data"]["payload"]
        assert payload["export_format"] == "json"
        assert "export_constraint" in payload

    async def test_unsupported_protocol_version(self, isolated_artifact_service):
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "ingest",
                    "protocol_version": "sheet-stage/v999",
                    "content": _INLINE_CSV,
                    "file_format": "csv",
                },
                user_id=USER_ID,
                artifact_service=isolated_artifact_service,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_PROTOCOL_UNSUPPORTED"

    async def test_ingest_rejects_provided_artifact(self, isolated_artifact_service):
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "ingest",
                    "content": _INLINE_CSV,
                    "file_format": "csv",
                    "artifact": {
                        "artifact_key": "sheet/ingest",
                        "artifact_version": 1,
                        "artifact_session_id": "x",
                    },
                },
                user_id=USER_ID,
                artifact_service=isolated_artifact_service,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_ARTIFACT_UNEXPECTED"

    async def test_ingest_failure_maps_to_422(self, isolated_artifact_service):
        # csv content claimed as xlsx -> table analysis parse failure -> status failed
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "ingest",
                    "content": "not,a,valid\nrow,count,mismatch,extra",
                    "file_format": "xlsx",
                },
                user_id=USER_ID,
                artifact_service=isolated_artifact_service,
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_INGEST_FAILED"

    async def test_non_ingest_without_session_id_raises(self, isolated_artifact_service):
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "profile",
                    "artifact": {
                        "artifact_key": "sheet/ingest",
                        "artifact_version": 1,
                        "artifact_session_id": "missing",
                    },
                },
                user_id=USER_ID,
                artifact_service=isolated_artifact_service,
            )
        assert exc.value.status_code in (400, 404, 409)

    async def test_query_requires_query_text(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service
        ingest_env = await _run_ingest(svc, invocation_id)
        session_id = ingest_env["session_id"]
        profile_env = await execute_sheet_stage_protocol_request(
            request_body={
                "stage": "profile",
                "session_id": session_id,
                "artifact": ingest_env["artifact"],
                "invocation_id": invocation_id,
            },
            user_id=USER_ID,
            artifact_service=svc,
        )
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "query",
                    "session_id": session_id,
                    "artifact": profile_env["artifact"],
                    "invocation_id": invocation_id,
                },
                user_id=USER_ID,
                artifact_service=svc,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_QUERY_REQUIRED"

    async def test_stale_artifact_reference_conflict(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service
        ingest_env = await _run_ingest(svc, invocation_id)
        session_id = ingest_env["session_id"]
        stale_ref = dict(ingest_env["artifact"])
        stale_ref["artifact_version"] = 999  # latest is 1
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "profile",
                    "session_id": session_id,
                    "artifact": stale_ref,
                    "invocation_id": invocation_id,
                },
                user_id=USER_ID,
                artifact_service=svc,
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_ARTIFACT_STALE"

    async def test_artifact_bound_to_other_session_rejected(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service
        ingest_env = await _run_ingest(svc, invocation_id)
        session_id = ingest_env["session_id"]
        wrong_session_ref = dict(ingest_env["artifact"])
        wrong_session_ref["artifact_session_id"] = "some-other-session"
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "profile",
                    "session_id": session_id,
                    "artifact": wrong_session_ref,
                    "invocation_id": invocation_id,
                },
                user_id=USER_ID,
                artifact_service=svc,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_INVALID_REQUEST"

    async def test_artifact_bound_to_other_tenant_forbidden(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service
        ingest_env = await _run_ingest(svc, invocation_id)
        session_id = ingest_env["session_id"]
        ref_with_tenant = dict(ingest_env["artifact"])
        ref_with_tenant["artifact_tenant_id"] = OTHER_USER_ID
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "profile",
                    "session_id": session_id,
                    "artifact": ref_with_tenant,
                    "invocation_id": invocation_id,
                },
                user_id=USER_ID,
                artifact_service=svc,
            )
        assert exc.value.status_code == 403
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_ARTIFACT_FORBIDDEN"

    async def test_export_against_wrong_input_key_raises_value_error(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service
        ingest_env = await _run_ingest(svc, invocation_id)
        session_id = ingest_env["session_id"]
        # export expects sheet/query as input; passing the ingest artifact triggers
        # ``validate_sheet_artifact_binding`` which is invoked OUTSIDE any try/except
        # in the protocol, so the artifact_key mismatch surfaces as a raw ValueError
        # (not a structured SheetStageProtocolError). Asserting the real behavior.
        with pytest.raises(ValueError, match="artifact_key binding mismatch"):
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "export",
                    "session_id": session_id,
                    "artifact": ingest_env["artifact"],
                    "invocation_id": invocation_id,
                },
                user_id=USER_ID,
                artifact_service=svc,
            )

    async def test_session_bound_to_other_user_forbidden(self, isolated_artifact_service, invocation_id):
        svc = isolated_artifact_service
        ingest_env = await _run_ingest(svc, invocation_id, user_id=USER_ID)
        session_id = ingest_env["session_id"]
        with pytest.raises(SheetStageProtocolError) as exc:
            await execute_sheet_stage_protocol_request(
                request_body={
                    "stage": "profile",
                    "session_id": session_id,
                    "artifact": ingest_env["artifact"],
                    "invocation_id": invocation_id,
                },
                user_id=OTHER_USER_ID,
                artifact_service=svc,
            )
        assert exc.value.status_code == 403
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_SESSION_FORBIDDEN"


# =========================================================================== #
# Module-level default singletons
# =========================================================================== #
def test_default_runtime_store_and_artifact_service_singletons():
    store1 = get_default_sheet_stage_runtime_store()
    store2 = get_default_sheet_stage_runtime_store()
    assert store1 is store2
    svc1 = get_default_sheet_stage_artifact_service()
    svc2 = get_default_sheet_stage_artifact_service()
    assert svc1 is svc2
    assert isinstance(svc1, ADKArtifactService)
