"""Coverage-focused tests for ``app.routers.ai.multi_agent`` (the multi-agent REST router).

Strategy
--------
* Pure helper functions (timestamp / ticket parsing, nonce-replay cache, the
  confirm-tool security validator, excel-path resolution, sheet-stage payload
  builders, route-meta, name sanitization) are exercised directly — they are
  deterministic and carry a large share of the module's branches.
* The HTTP endpoints are driven through a fresh :class:`FastAPI` app that mounts
  the production ``router`` and overrides only the two boundary dependencies
  (``require_current_user`` and ``get_db``). The DB is a real in-memory SQLite
  engine populated with the actual SQLAlchemy models so user-scoping / 404 /
  permission logic runs for real.
* Only true external boundaries are patched: the ADK runner factory
  (``_create_adk_runner_for_agent``), ``get_provider_credentials``, the
  orchestration service classes, and the ADK-samples / workflow importers.
  The SUT's own routing, validation and error mapping run unmocked.

These tests assert real behavior: status codes, response envelopes,
auth/permission (user scoping → 404), provider/type gating (400), request
validation (400/403/409), nonce replay (409), and deprecation headers.
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict, List

import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import require_current_user
from app.models.db_models import AgentRegistry, MessageAttachment, generate_uuid
from app.routers.ai import multi_agent as ma

USER_ID = "user-ma-1"
OTHER_USER_ID = "user-ma-2"


# --------------------------------------------------------------------------- #
# Fixtures: in-memory DB + TestClient with dependency overrides
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


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(ma.router)
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _add_agent(
    db,
    *,
    name: str = "Agent",
    user_id: str = USER_ID,
    status: str = "active",
    provider_id: str = "google",
    model_id: str = "gemini-2.5-flash",
    agent_type: str = "adk",
    system_prompt: str = "You are helpful.",
) -> AgentRegistry:
    now = int(time.time() * 1000)
    agent = AgentRegistry(
        id=generate_uuid(),
        user_id=user_id,
        name=name,
        description="",
        agent_type=agent_type,
        provider_id=provider_id,
        model_id=model_id,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=4096,
        status=status,
        created_at=now,
        updated_at=now,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _add_attachment(
    db,
    *,
    user_id: str = USER_ID,
    url: str = "https://cdn.example.com/data.csv",
    file_uri: str = "",
    temp_url: str = "",
) -> MessageAttachment:
    attachment_id = generate_uuid()
    attachment = MessageAttachment(
        id=attachment_id,
        message_id=generate_uuid(),
        user_id=user_id,
        session_id=generate_uuid(),
        mime_type="text/csv",
        name="data.csv",
        url=url,
        temp_url=temp_url,
        file_uri=file_uri,
        upload_status="completed",
        size=10,
    )
    db.add(attachment)
    db.commit()
    return attachment


class _FakeRunner:
    """Stand-in for ADKRunner that records calls and returns canned responses."""

    def __init__(self, *, run_once_response=None, sessions=None, snapshot=None, rewind_result=None, live_events=None):
        self.is_available = True
        self._run_once_response = run_once_response or {
            "text": "hello world",
            "invocation_id": "inv-1",
            "usage": {"total_tokens": 5},
            "event_count": 2,
            "actions": {"a": 1},
            "long_running_tool_ids": ["t1"],
            "response_signature": "rsig",
            "action_signature": "asig",
        }
        self._sessions = sessions if sessions is not None else [{"id": "s1"}]
        self._snapshot = snapshot
        self._rewind_result = rewind_result or {"events_removed": 1}
        self._live_events = live_events or []
        self.run_once_calls: List[Dict[str, Any]] = []

    async def run_once(self, **kwargs):
        self.run_once_calls.append(kwargs)
        return dict(self._run_once_response)

    async def list_sessions(self, *, user_id):
        return list(self._sessions)

    async def get_session_snapshot(self, *, user_id, session_id):
        return self._snapshot

    async def rewind(self, **kwargs):
        return dict(self._rewind_result)

    async def run_live(self, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        for event in self._live_events:
            yield event


def _patch_runner(monkeypatch, runner: _FakeRunner, api_key: str = "key-123"):
    async def _fake_factory(*, db, user_id, agent, require_runtime=True):
        return runner, api_key

    monkeypatch.setattr(ma, "_create_adk_runner_for_agent", _fake_factory)


def _assert_generic_error_response(resp, caplog, *, detail: str, secret: str) -> None:
    assert resp.status_code == 500
    assert resp.json()["detail"] == detail
    assert secret not in resp.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


# =========================================================================== #
# Pure helpers — timestamp / ttl parsing
# =========================================================================== #
class TestTimestampParsing:
    def test_parse_ticket_timestamp_ms_seconds_promoted(self):
        # 10-digit seconds value is promoted to ms.
        assert ma._parse_ticket_timestamp_ms(1_700_000_000) == 1_700_000_000_000

    def test_parse_ticket_timestamp_ms_already_ms(self):
        assert ma._parse_ticket_timestamp_ms(1_700_000_000_000) == 1_700_000_000_000

    def test_parse_ticket_timestamp_ms_string(self):
        assert ma._parse_ticket_timestamp_ms("1700000000000") == 1_700_000_000_000

    def test_parse_ticket_timestamp_ms_bool_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_timestamp_ms(True)

    def test_parse_ticket_timestamp_ms_empty_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_timestamp_ms("")

    def test_parse_ticket_timestamp_ms_garbage_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_timestamp_ms("not-a-number")

    def test_parse_ticket_timestamp_ms_zero_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_timestamp_ms(0)

    def test_parse_ticket_ttl_seconds_valid(self):
        assert ma._parse_ticket_ttl_seconds(600) == 600

    def test_parse_ticket_ttl_seconds_string(self):
        assert ma._parse_ticket_ttl_seconds("120") == 120

    def test_parse_ticket_ttl_seconds_bool_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_ttl_seconds(True)

    def test_parse_ticket_ttl_seconds_zero_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_ttl_seconds(0)

    def test_parse_ticket_ttl_seconds_too_large_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_ttl_seconds(ma.ADK_CONFIRM_TICKET_MAX_TTL_SECONDS + 1)

    def test_parse_ticket_ttl_seconds_empty_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_ttl_seconds("")

    def test_parse_ticket_ttl_seconds_garbage_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_ticket_ttl_seconds("abc")

    def test_parse_legacy_expiry_numeric(self):
        assert ma._parse_legacy_expiry_timestamp_ms(1_700_000_000_000) == 1_700_000_000_000

    def test_parse_legacy_expiry_iso_with_z(self):
        ms = ma._parse_legacy_expiry_timestamp_ms("2024-01-01T00:00:00Z")
        assert ms > 0

    def test_parse_legacy_expiry_none_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_legacy_expiry_timestamp_ms(None)

    def test_parse_legacy_expiry_bool_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_legacy_expiry_timestamp_ms(True)

    def test_parse_legacy_expiry_garbage_rejected(self):
        with pytest.raises(ValueError):
            ma._parse_legacy_expiry_timestamp_ms("definitely-not-a-date")


# =========================================================================== #
# Pure helpers — small utilities
# =========================================================================== #
class TestSmallHelpers:
    def test_normalize_provider_id(self):
        assert ma._normalize_provider_id("  Google ") == "google"
        assert ma._normalize_provider_id(None) == ""

    def test_build_adk_session_id_sanitizes(self):
        sid = ma._build_adk_session_id("my agent!!*")
        assert sid.startswith("adk-myagent-")

    def test_build_adk_session_id_empty_fallback(self):
        sid = ma._build_adk_session_id("")
        assert sid.startswith("adk-agent-")

    def test_pick_first_value_and_text(self):
        payload = {"b": "", "c": "found"}
        assert ma._pick_first_value(payload, ["a", "b", "c"]) == ""
        assert ma._pick_first_text(payload, ["a", "b", "c"]) == "found"
        assert ma._pick_first_text({}, ["x"]) == ""

    def test_sanitize_adk_name(self):
        assert ma._sanitize_adk_name("My Cool Agent", "fb") == "My_Cool_Agent"
        assert ma._sanitize_adk_name("   ", "fallback") == "fallback"
        assert ma._sanitize_adk_name("___", "fb") == "fb"

    def test_coerce_legacy_ticket_dict_passthrough(self):
        assert ma._coerce_approval_ticket_legacy_object({"k": "v"}) == {"k": "v"}

    def test_coerce_legacy_ticket_json_string(self):
        out = ma._coerce_approval_ticket_legacy_object('{"nonce": "n1"}')
        assert out == {"nonce": "n1"}

    def test_coerce_legacy_ticket_plain_string_wrapped(self):
        assert ma._coerce_approval_ticket_legacy_object("opaque") == {"ticket": "opaque"}

    def test_coerce_legacy_ticket_empty_returns_none(self):
        assert ma._coerce_approval_ticket_legacy_object("") is None

    def test_build_confirm_nonce_cache_key(self):
        key = ma._build_confirm_nonce_cache_key(
            tenant_id="t", session_id="s", function_call_id="f",
            invocation_id="i", nonce="n",
        )
        assert key == "t|s|f|i|n"

    def test_resolve_sheet_stage_from_artifact_key(self):
        assert ma._resolve_sheet_stage_from_artifact_key("sheet/profile") == "profile"
        assert ma._resolve_sheet_stage_from_artifact_key("garbage") == "ingest"

    def test_is_truthy_env(self, monkeypatch):
        monkeypatch.setenv("MA_TEST_FLAG", "yes")
        assert ma._is_truthy_env("MA_TEST_FLAG") is True
        monkeypatch.setenv("MA_TEST_FLAG", "off")
        assert ma._is_truthy_env("MA_TEST_FLAG") is False
        monkeypatch.delenv("MA_TEST_FLAG", raising=False)
        assert ma._is_truthy_env("MA_TEST_FLAG", default=True) is True

    def test_is_path_within_roots(self, tmp_path):
        from pathlib import Path

        root = tmp_path
        child = root / "sub" / "file.csv"
        assert ma._is_path_within_roots(child, [root]) is True
        assert ma._is_path_within_roots(Path("/totally/other"), [root]) is False


# =========================================================================== #
# Route-meta + deprecation header helpers
# =========================================================================== #
class TestRouteMeta:
    def test_attach_route_meta_to_dict(self):
        out = ma._attach_legacy_orchestrate_route_meta({"output": "x"}, mode="sequential")
        assert out["output"] == "x"
        meta = out["route_meta"]
        assert meta["legacy"] is True
        assert meta["mode"] == "sequential"
        assert meta["recommended_path_template"] == ma.LEGACY_ORCHESTRATE_REPLACEMENT_PATH

    def test_attach_route_meta_merges_existing(self):
        out = ma._attach_legacy_orchestrate_route_meta(
            {"route_meta": {"custom": 1}}, mode="default"
        )
        assert out["route_meta"]["custom"] == 1
        assert out["route_meta"]["legacy"] is True

    def test_attach_route_meta_non_dict_wrapped(self):
        out = ma._attach_legacy_orchestrate_route_meta("string-result", mode="")
        assert out["result"] == "string-result"
        assert out["route_meta"]["mode"] == "default"

    def test_apply_legacy_headers(self):
        from starlette.responses import Response as StarletteResponse

        resp = StarletteResponse()
        ma._apply_legacy_orchestrate_response_headers(resp)
        assert resp.headers["Deprecation"] == "true"
        assert resp.headers["X-Legacy-Entrypoint"] == "legacy-orchestrate"
        assert ma.LEGACY_ORCHESTRATE_REPLACEMENT_PATH in resp.headers["X-Replacement-Path-Template"]


# =========================================================================== #
# Excel reference resolution helpers (no network, in-mem DB)
# =========================================================================== #
class TestExcelReferenceResolution:
    def test_validate_suffix_allowed(self):
        # No exception for an allowed suffix.
        ma._validate_excel_reference_suffix("https://x/data.xlsx")

    def test_validate_suffix_rejected(self):
        with pytest.raises(HTTPException) as exc:
            ma._validate_excel_reference_suffix("https://x/data.exe")
        assert exc.value.status_code == 400

    def test_resolve_file_reference_http_url(self, db_session):
        ref = ma._resolve_excel_file_reference(
            db=db_session, user_id=USER_ID,
            attachment_id=None, file_url="https://x/data.csv", file_path=None,
        )
        assert ref == "https://x/data.csv"

    def test_resolve_file_reference_bad_url_scheme(self, db_session):
        with pytest.raises(HTTPException) as exc:
            ma._resolve_excel_file_reference(
                db=db_session, user_id=USER_ID,
                attachment_id=None, file_url="ftp://x/data.csv", file_path=None,
            )
        assert exc.value.status_code == 400

    def test_resolve_file_reference_requires_one(self, db_session):
        with pytest.raises(HTTPException) as exc:
            ma._resolve_excel_file_reference(
                db=db_session, user_id=USER_ID,
                attachment_id=None, file_url=None, file_path=None,
            )
        assert exc.value.status_code == 400

    def test_resolve_attachment_reference_happy(self, db_session):
        attachment = _add_attachment(db_session, url="https://cdn.example.com/file.csv")
        ref = ma._resolve_excel_attachment_reference(db_session, USER_ID, attachment.id)
        assert ref == "https://cdn.example.com/file.csv"

    def test_resolve_attachment_reference_empty_id(self, db_session):
        with pytest.raises(HTTPException) as exc:
            ma._resolve_excel_attachment_reference(db_session, USER_ID, "")
        assert exc.value.status_code == 400

    def test_resolve_attachment_reference_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc:
            ma._resolve_excel_attachment_reference(db_session, USER_ID, "missing")
        assert exc.value.status_code == 404

    def test_resolve_attachment_reference_other_user_404(self, db_session):
        attachment = _add_attachment(db_session, user_id=OTHER_USER_ID)
        with pytest.raises(HTTPException) as exc:
            ma._resolve_excel_attachment_reference(db_session, USER_ID, attachment.id)
        assert exc.value.status_code == 404

    def test_resolve_attachment_reference_no_usable_ref_422(self, db_session):
        # Only a local file path / blob, nothing http/data → 422.
        attachment = _add_attachment(
            db_session, url="/local/only.csv", file_uri="", temp_url=""
        )
        with pytest.raises(HTTPException) as exc:
            ma._resolve_excel_attachment_reference(db_session, USER_ID, attachment.id)
        assert exc.value.status_code == 422

    def test_resolve_legacy_path_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv(ma._EXCEL_LEGACY_PATH_ENV, raising=False)
        with pytest.raises(HTTPException) as exc:
            ma._resolve_legacy_excel_path("/tmp/x.csv")
        assert exc.value.status_code == 400

    def test_resolve_legacy_path_empty_rejected(self):
        with pytest.raises(HTTPException) as exc:
            ma._resolve_legacy_excel_path("")
        assert exc.value.status_code == 400


# =========================================================================== #
# Sheet-stage payload builders (pure, no DB)
# =========================================================================== #
class TestSheetStagePayloadBuilders:
    def test_build_profile_payload_from_ingest(self):
        ingest = {
            "analysis": {
                "summary": {"row_count": 10, "column_count": 2},
                "columns": [{"name": "a"}, {"column": "b"}, {"noname": "x"}],
            },
            "file_name": "f.csv",
            "file_format": "csv",
            "source_type": "upload",
        }
        out = ma._build_profile_payload_from_ingest(ingest)
        assert out["summary"]["row_count"] == 10
        assert out["columns"] == ["a", "b"]
        assert out["source"]["file_name"] == "f.csv"

    def test_build_profile_payload_handles_missing(self):
        out = ma._build_profile_payload_from_ingest({})
        assert out["summary"]["row_count"] == 0
        assert out["columns"] == []

    def test_build_query_payload(self):
        profile = {"summary": {"row_count": 5, "column_count": 3}, "columns": ["a"]}
        out = ma._build_query_payload(profile_payload=profile, query_text="sum a")
        assert out["query"] == "sum a"
        assert "5 rows" in out["answer"]
        assert out["columns"] == ["a"]

    def test_build_export_payload_markdown(self):
        query = {"summary": {"row_count": 1, "column_count": 1}, "columns": [], "query": "q", "answer": "a"}
        out = ma._build_export_payload(query_payload=query, user_id=USER_ID, export_format="markdown")
        assert out["export_format"] == "markdown"
        assert "Sheet Query Result" in out["rendered"]

    def test_build_export_payload_json(self):
        query = {"summary": {"row_count": 1, "column_count": 1}, "columns": [], "query": "q", "answer": "a"}
        out = ma._build_export_payload(query_payload=query, user_id=USER_ID, export_format="json")
        assert out["export_format"] == "json"
        assert out["rendered"].startswith("{")

    def test_build_export_payload_unknown_format_defaults_markdown(self):
        query = {"summary": {"row_count": 0, "column_count": 0}, "columns": [], "query": "q", "answer": "a"}
        out = ma._build_export_payload(query_payload=query, user_id=USER_ID, export_format="pdf")
        assert out["export_format"] == "markdown"

    def test_build_sheet_stage_failure_detail(self):
        detail = ma._build_sheet_stage_failure_detail(
            stage="profile", session_id="s1", message="boom", error_code="X",
        )
        assert detail["status"] == "failed"
        assert detail["error"]["code"] == "X"

    def test_build_sheet_stage_failure_detail_unknown_stage_defaults_ingest(self):
        detail = ma._build_sheet_stage_failure_detail(
            stage="bogus", session_id="", message="m",
        )
        assert detail["stage"] == "ingest"

    def test_raise_sheet_stage_http_error(self):
        with pytest.raises(HTTPException) as exc:
            ma._raise_sheet_stage_http_error(
                status_code=409, stage="query", session_id="s", message="m", error_code="C",
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["error"]["code"] == "C"


# =========================================================================== #
# Confirm-tool nonce replay cache + security validator
# =========================================================================== #
def _valid_ticket(*, session_id, function_call_id, invocation_id, tenant_id, nonce, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    return {
        "session_id": session_id,
        "function_call_id": function_call_id,
        "invocation_id": invocation_id,
        "tenant_id": tenant_id,
        "nonce": nonce,
        "timestamp_ms": now_ms,
        "ttl_seconds": 600,
    }


def _confirm_body(**overrides):
    base = {
        "function_call_id": "fc-1",
        "confirmed": True,
        "invocation_id": "inv-1",
        "nonce": "nonce-1",
    }
    base.update(overrides)
    return ma.ADKToolConfirmationRequest(**base)


class TestConfirmToolSecurity:
    def setup_method(self):
        with ma._ADK_CONFIRM_NONCE_LOCK:
            ma._ADK_CONFIRM_USED_NONCES.clear()

    def test_requires_confirmed_true(self):
        body = _confirm_body(confirmed=False)
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403

    def test_requires_nonce_and_ticket(self):
        body = _confirm_body(approval_ticket=None, ticket=None, confirmation_ticket=None)
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403

    def test_happy_path_consumes_nonce(self):
        ticket = _valid_ticket(
            session_id="s1", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id=USER_ID, nonce="nonce-1",
        )
        body = _confirm_body(approval_ticket=ticket)
        out = ma._validate_confirm_tool_security_or_raise(
            request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
        )
        assert out["nonce"] == "nonce-1"
        assert out["tenant_id"] == USER_ID

    def test_replay_detected_409(self):
        ticket = _valid_ticket(
            session_id="s1", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id=USER_ID, nonce="nonce-replay",
        )
        body = _confirm_body(approval_ticket=ticket, nonce="nonce-replay")
        ma._validate_confirm_tool_security_or_raise(
            request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
        )
        # second identical confirmation → replay 409
        body2 = _confirm_body(approval_ticket=dict(ticket), nonce="nonce-replay")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body2, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 409

    def test_session_binding_mismatch(self):
        ticket = _valid_ticket(
            session_id="other", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id=USER_ID, nonce="n",
        )
        body = _confirm_body(approval_ticket=ticket, nonce="n")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403
        assert "session binding" in exc.value.detail

    def test_tenant_binding_mismatch(self):
        ticket = _valid_ticket(
            session_id="s1", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id="someone-else", nonce="n",
        )
        body = _confirm_body(approval_ticket=ticket, nonce="n")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403
        assert "tenant binding" in exc.value.detail

    def test_missing_invocation_in_request_403(self):
        ticket = _valid_ticket(
            session_id="s1", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id=USER_ID, nonce="n",
        )
        body = _confirm_body(approval_ticket=ticket, nonce="n", invocation_id="")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403

    def test_expired_ticket_403(self):
        old_ms = int(time.time() * 1000) - (10_000 * 1000)
        ticket = _valid_ticket(
            session_id="s1", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id=USER_ID, nonce="n", now_ms=old_ms,
        )
        ticket["ttl_seconds"] = 1  # long expired
        body = _confirm_body(approval_ticket=ticket, nonce="n")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403
        assert "expired" in exc.value.detail

    def test_future_ticket_403(self):
        future_ms = int(time.time() * 1000) + (10 * 60 * 1000)
        ticket = _valid_ticket(
            session_id="s1", function_call_id="fc-1", invocation_id="inv-1",
            tenant_id=USER_ID, nonce="n", now_ms=future_ms,
        )
        body = _confirm_body(approval_ticket=ticket, nonce="n")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403
        assert "future" in exc.value.detail

    def test_missing_binding_fields_403(self):
        # Ticket lacking invocation_id binding.
        ticket = {
            "session_id": "s1",
            "function_call_id": "fc-1",
            "tenant_id": USER_ID,
            "nonce": "n",
            "timestamp_ms": int(time.time() * 1000),
            "ttl_seconds": 600,
        }
        body = _confirm_body(approval_ticket=ticket, nonce="n")
        with pytest.raises(HTTPException) as exc:
            ma._validate_confirm_tool_security_or_raise(
                request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
            )
        assert exc.value.status_code == 403
        assert "missing session" in exc.value.detail


class TestMaterializeApprovalTicket:
    def test_dict_ticket_passthrough(self):
        body = _confirm_body(approval_ticket={"x": 1})
        out = ma._materialize_approval_ticket_from_request(
            request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
        )
        assert out == {"x": 1}

    def test_legacy_confirmation_ticket_materialized(self):
        body = _confirm_body(
            approval_ticket=None,
            confirmation_ticket='{"nonce": "n9"}',
            nonce="n9",
            tenant_id="tenant-x",
        )
        out = ma._materialize_approval_ticket_from_request(
            request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
        )
        assert out["session_id"] == "s1"
        assert out["function_call_id"] == "fc-1"
        assert out["tenant_id"] == "tenant-x"
        assert out["nonce"] == "n9"

    def test_no_ticket_returns_none(self):
        body = _confirm_body(approval_ticket=None, ticket=None, confirmation_ticket=None)
        out = ma._materialize_approval_ticket_from_request(
            request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
        )
        assert out is None

    def test_legacy_expiry_materializes_timing(self):
        future_ms = int(time.time() * 1000) + 5 * 60 * 1000
        body = _confirm_body(
            approval_ticket=None,
            ticket="opaque-ticket",
            nonce="n",
            nonce_expires_at=future_ms,
        )
        out = ma._materialize_approval_ticket_from_request(
            request_body=body, user_id=USER_ID, session_id="s1", function_call_id="fc-1",
        )
        assert "timestamp_ms" in out
        assert "ttl_seconds" in out


# =========================================================================== #
# Agent resolution + provider/type gating helpers (DB)
# =========================================================================== #
class TestAgentGating:
    async def test_resolve_user_agent_found(self, db_session):
        agent = _add_agent(db_session, name="A")
        resolved = await ma._resolve_user_agent_or_404(db_session, USER_ID, agent.id)
        assert resolved.id == agent.id

    async def test_resolve_user_agent_not_found(self, db_session):
        with pytest.raises(HTTPException) as exc:
            await ma._resolve_user_agent_or_404(db_session, USER_ID, "missing")
        assert exc.value.status_code == 404

    async def test_resolve_user_agent_other_user_404(self, db_session):
        agent = _add_agent(db_session, name="A", user_id=OTHER_USER_ID)
        with pytest.raises(HTTPException) as exc:
            await ma._resolve_user_agent_or_404(db_session, USER_ID, agent.id)
        assert exc.value.status_code == 404

    def test_ensure_adk_google_agent_ok(self, db_session):
        agent = _add_agent(db_session, agent_type="adk", provider_id="google")
        # Should not raise.
        ma._ensure_adk_google_agent(agent)

    def test_ensure_adk_google_agent_wrong_type(self, db_session):
        agent = _add_agent(db_session, agent_type="custom", provider_id="google")
        with pytest.raises(HTTPException) as exc:
            ma._ensure_adk_google_agent(agent)
        assert exc.value.status_code == 400

    def test_ensure_adk_google_agent_wrong_provider(self, db_session):
        agent = _add_agent(db_session, agent_type="adk", provider_id="openai")
        with pytest.raises(HTTPException) as exc:
            ma._ensure_adk_google_agent(agent)
        assert exc.value.status_code == 400


# =========================================================================== #
# HTTP endpoints — health / list / register
# =========================================================================== #
class TestBasicEndpoints:
    def test_health(self, client):
        resp = client.get("/api/multi-agent/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_list_agents_empty(self, client):
        resp = client.get("/api/multi-agent/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agents"] == []
        assert body["count"] == 0

    def test_list_agents_returns_user_scoped(self, client, db_session):
        _add_agent(db_session, name="Mine", agent_type="custom")
        _add_agent(db_session, name="Theirs", user_id=OTHER_USER_ID, agent_type="custom")
        resp = client.get("/api/multi-agent/agents")
        body = resp.json()
        names = {a["name"] for a in body["agents"]}
        assert names == {"Mine"}
        assert body["count"] == 1

    def test_list_agents_type_filter(self, client, db_session):
        _add_agent(db_session, name="ADKOne", agent_type="adk")
        _add_agent(db_session, name="CustomOne", agent_type="custom")
        resp = client.get("/api/multi-agent/agents?agent_type=adk")
        names = {a["name"] for a in resp.json()["agents"]}
        assert names == {"ADKOne"}

    def test_list_agents_error_is_generic(self, client, monkeypatch, caplog):
        secret = "registry-list-secret"

        async def boom(self, **kwargs):
            raise RuntimeError(f"registry exploded {secret}")

        monkeypatch.setattr(ma.AgentRegistryService, "list_agents", boom)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.get("/api/multi-agent/agents")

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to list agents"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_register_agent_happy_path(self, client, db_session):
        resp = client.post(
            "/api/multi-agent/agents/register",
            json={"name": "Registered", "agent_type": "custom", "tools": ["t1"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Registered"
        # Persisted to DB
        assert db_session.query(AgentRegistry).filter_by(name="Registered").first() is not None

    def test_register_agent_error_is_generic(self, client, monkeypatch, caplog):
        secret = "registry-register-secret"

        async def boom(self, **kwargs):
            raise RuntimeError(f"registry exploded {secret}")

        monkeypatch.setattr(ma.AgentRegistryService, "register_agent", boom)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                "/api/multi-agent/agents/register",
                json={"name": "X", "agent_type": "custom"},
            )

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to register agent"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text


# =========================================================================== #
# HTTP endpoints — ADK runtime run / sessions / rewind / memory
# =========================================================================== #
class TestRuntimeRun:
    def test_run_requires_input(self, client, db_session):
        agent = _add_agent(db_session)
        resp = client.post(f"/api/multi-agent/agents/{agent.id}/runtime/run", json={})
        assert resp.status_code == 400
        assert "input" in resp.json()["detail"]

    def test_run_agent_not_found(self, client):
        resp = client.post(
            "/api/multi-agent/agents/missing/runtime/run", json={"input": "hi"}
        )
        assert resp.status_code == 404

    def test_run_non_adk_agent_rejected(self, client, db_session):
        agent = _add_agent(db_session, agent_type="custom")
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run", json={"input": "hi"}
        )
        assert resp.status_code == 400

    def test_run_invalid_run_config_400(self, client, db_session):
        agent = _add_agent(db_session)
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run",
            json={"input": "hi", "run_config": {"bad_key": 1}},
        )
        assert resp.status_code == 400

    def test_run_happy_path(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        runner = _FakeRunner()
        _patch_runner(monkeypatch, runner)
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run", json={"input": "hi"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["output"] == "hello world"
        assert body["agent_id"] == agent.id
        assert body["invocation_id"] == "inv-1"
        # session id was auto-generated
        assert body["session_id"].startswith("adk-")
        assert runner.run_once_calls  # runner actually invoked

    def test_run_with_explicit_session(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner())
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run",
            json={"input": "hi", "session_id": "sess-xyz"},
        )
        assert resp.json()["session_id"] == "sess-xyz"

    def test_run_legacy_path_alias(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner())
        resp = client.post(
            f"/api/multi-agent/adk/agents/{agent.id}/run", json={"input": "hi"}
        )
        assert resp.status_code == 200

    def test_run_runner_failure_is_generic(self, client, db_session, monkeypatch, caplog):
        secret = "runtime-run-secret"
        agent = _add_agent(db_session)

        class _BoomRunner(_FakeRunner):
            async def run_once(self, **kwargs):
                raise RuntimeError(f"runner boom {secret}")

        _patch_runner(monkeypatch, _BoomRunner())
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                f"/api/multi-agent/agents/{agent.id}/runtime/run", json={"input": "hi"}
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="ADK run failed",
            secret=secret,
        )


class TestRuntimeSessions:
    def test_list_sessions(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner(sessions=[{"id": "a"}, {"id": "b"}]))
        resp = client.get(f"/api/multi-agent/agents/{agent.id}/runtime/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["agent_id"] == agent.id

    def test_list_sessions_agent_not_found(self, client):
        resp = client.get("/api/multi-agent/agents/missing/runtime/sessions")
        assert resp.status_code == 404

    def test_list_sessions_runner_failure_is_generic(
        self, client, db_session, monkeypatch, caplog
    ):
        secret = "runtime-list-sessions-secret"
        agent = _add_agent(db_session)

        class _BoomRunner(_FakeRunner):
            async def list_sessions(self, *, user_id):
                raise RuntimeError(f"session list boom {secret}")

        _patch_runner(monkeypatch, _BoomRunner())
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.get(f"/api/multi-agent/agents/{agent.id}/runtime/sessions")

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Failed to list ADK sessions",
            secret=secret,
        )

    def test_get_session_found(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner(snapshot={"id": "snap", "events": []}))
        resp = client.get(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/snap"
        )
        assert resp.status_code == 200
        assert resp.json()["session"]["id"] == "snap"

    def test_get_session_not_found_404(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner(snapshot=None))
        resp = client.get(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/missing"
        )
        assert resp.status_code == 404

    def test_get_session_runner_failure_is_generic(
        self, client, db_session, monkeypatch, caplog
    ):
        secret = "runtime-get-session-secret"
        agent = _add_agent(db_session)

        class _BoomRunner(_FakeRunner):
            async def get_session_snapshot(self, *, user_id, session_id):
                raise RuntimeError(f"session get boom {secret}")

        _patch_runner(monkeypatch, _BoomRunner())
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.get(
                f"/api/multi-agent/agents/{agent.id}/runtime/sessions/snap"
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Failed to get ADK session",
            secret=secret,
        )

    def test_rewind_session(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner(rewind_result={"events_removed": 3}))
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/rewind",
            json={"rewindBeforeInvocationId": "inv-9"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rewound"
        assert body["events_removed"] == 3

    def test_rewind_validation_missing_field(self, client, db_session):
        agent = _add_agent(db_session)
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/rewind",
            json={},
        )
        assert resp.status_code == 422  # pydantic required field

    def test_rewind_runner_failure_is_generic(self, client, db_session, monkeypatch, caplog):
        secret = "runtime-rewind-secret"
        agent = _add_agent(db_session)

        class _BoomRunner(_FakeRunner):
            async def rewind(self, **kwargs):
                raise RuntimeError(f"rewind boom {secret}")

        _patch_runner(monkeypatch, _BoomRunner())
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/rewind",
                json={"rewindBeforeInvocationId": "inv-9"},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="ADK rewind failed",
            secret=secret,
        )


class TestConfirmToolEndpoint:
    def setup_method(self):
        with ma._ADK_CONFIRM_NONCE_LOCK:
            ma._ADK_CONFIRM_USED_NONCES.clear()

    def test_confirm_missing_function_call_id_400(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner())
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/confirm-tool",
            json={"functionCallId": "", "confirmed": True},
        )
        assert resp.status_code == 400

    def test_confirm_not_confirmed_403(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner())
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/confirm-tool",
            json={"functionCallId": "fc-1", "confirmed": False},
        )
        assert resp.status_code == 403

    def test_confirm_happy_path(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner())
        now_ms = int(time.time() * 1000)
        ticket = {
            "session_id": "s1",
            "function_call_id": "fc-1",
            "invocation_id": "inv-1",
            "tenant_id": USER_ID,
            "nonce": "nonce-ok",
            "timestamp_ms": now_ms,
            "ttl_seconds": 600,
        }
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/confirm-tool",
            json={
                "functionCallId": "fc-1",
                "confirmed": True,
                "invocationId": "inv-1",
                "nonce": "nonce-ok",
                "approvalTicket": ticket,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "completed"

    def test_confirm_runner_failure_is_generic(
        self, client, db_session, monkeypatch, caplog
    ):
        secret = "runtime-confirm-secret"
        agent = _add_agent(db_session)

        class _BoomRunner(_FakeRunner):
            async def run_once(self, **kwargs):
                raise RuntimeError(f"confirm boom {secret}")

        _patch_runner(monkeypatch, _BoomRunner())
        now_ms = int(time.time() * 1000)
        ticket = {
            "session_id": "s1",
            "function_call_id": "fc-1",
            "invocation_id": "inv-1",
            "tenant_id": USER_ID,
            "nonce": "nonce-boom",
            "timestamp_ms": now_ms,
            "ttl_seconds": 600,
        }
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/confirm-tool",
                json={
                    "functionCallId": "fc-1",
                    "confirmed": True,
                    "invocationId": "inv-1",
                    "nonce": "nonce-boom",
                    "approvalTicket": ticket,
                },
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="ADK tool confirmation failed",
            secret=secret,
        )


class TestMemoryEndpoints:
    def test_memory_search_requires_query(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        _patch_runner(monkeypatch, _FakeRunner())
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/memory/search",
            json={"query": "  "},
        )
        assert resp.status_code == 400

    def test_memory_search_happy_path(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)

        class _FakeMemoryManager:
            async def search_memories(self, **kwargs):
                return [{"id": "m1", "text": "hi"}]

        monkeypatch.setattr(ma, "_build_memory_manager", lambda **k: _FakeMemoryManager())
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/memory/search",
            json={"query": "find", "limit": 3},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["count"] == 1
        assert body["query"] == "find"

    def test_memory_search_failure_is_generic(self, client, db_session, monkeypatch, caplog):
        secret = "runtime-memory-search-secret"
        agent = _add_agent(db_session)

        class _FakeMemoryManager:
            async def search_memories(self, **kwargs):
                raise RuntimeError(f"memory search boom {secret}")

        monkeypatch.setattr(ma, "_build_memory_manager", lambda **k: _FakeMemoryManager())
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                f"/api/multi-agent/agents/{agent.id}/runtime/memory/search",
                json={"query": "find", "limit": 3},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="ADK memory search failed",
            secret=secret,
        )

    def test_memory_index_happy_path(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)

        class _FakeMemoryManager:
            async def add_session_to_memory(self, **kwargs):
                return [{"id": "m1"}, {"id": "m2"}]

        monkeypatch.setattr(ma, "_build_memory_manager", lambda **k: _FakeMemoryManager())
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/memory/index",
            json={},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "indexed"
        assert body["count"] == 2

    def test_memory_index_agent_not_found(self, client):
        resp = client.post(
            "/api/multi-agent/agents/missing/runtime/sessions/s1/memory/index",
            json={},
        )
        assert resp.status_code == 404

    def test_memory_index_failure_is_generic(self, client, db_session, monkeypatch, caplog):
        secret = "runtime-memory-index-secret"
        agent = _add_agent(db_session)

        class _FakeMemoryManager:
            async def add_session_to_memory(self, **kwargs):
                raise RuntimeError(f"memory index boom {secret}")

        monkeypatch.setattr(ma, "_build_memory_manager", lambda **k: _FakeMemoryManager())
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                f"/api/multi-agent/agents/{agent.id}/runtime/sessions/s1/memory/index",
                json={},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="ADK memory index failed",
            secret=secret,
        )


# =========================================================================== #
# HTTP endpoints — orchestrate (legacy)
# =========================================================================== #
class TestOrchestrate:
    def test_orchestrate_sequential_requires_sub_agents(self, client, monkeypatch):
        # Avoid provider credential network call.
        async def _fake_creds(*a, **k):
            return ("key", "")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma.ProviderFactory, "create", lambda **k: object())
        resp = client.post(
            "/api/multi-agent/orchestrate",
            json={"task": "do", "mode": "sequential", "workflow_config": {}},
        )
        assert resp.status_code == 400

    def test_orchestrate_parallel_requires_sub_agents(self, client, monkeypatch):
        async def _fake_creds(*a, **k):
            return ("key", "")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma.ProviderFactory, "create", lambda **k: object())
        resp = client.post(
            "/api/multi-agent/orchestrate",
            json={"task": "do", "mode": "parallel", "workflow_config": {}},
        )
        assert resp.status_code == 400

    def test_orchestrate_coordinator_mode(self, client, monkeypatch):
        async def _fake_creds(*a, **k):
            return ("key", "")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma.ProviderFactory, "create", lambda **k: object())

        class _FakeCoordinator:
            def __init__(self, **kwargs):
                pass

            async def coordinate(self, **kwargs):
                return {"output": "coordinated"}

        import app.services.gemini.agent.coordinator_agent as coord_mod

        monkeypatch.setattr(coord_mod, "CoordinatorAgent", _FakeCoordinator)
        resp = client.post(
            "/api/multi-agent/orchestrate",
            json={"task": "do", "mode": "coordinator"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["output"] == "coordinated"
        assert body["route_meta"]["mode"] == "coordinator"

    def test_orchestrate_default_mode_uses_orchestrator(self, client, monkeypatch):
        async def _fake_creds(*a, **k):
            return ("key", "")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma.ProviderFactory, "create", lambda **k: object())

        async def _fake_orchestrate(self, **kwargs):
            return {"output": "done", "subtasks": []}

        monkeypatch.setattr(ma.Orchestrator, "orchestrate", _fake_orchestrate)
        resp = client.post("/api/multi-agent/orchestrate", json={"task": "do"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["output"] == "done"
        assert body["route_meta"]["mode"] == "default"

    def test_orchestrate_google_service_failure_log_is_summarized(
        self, client, monkeypatch, caplog
    ):
        secret = "google-service-secret"

        async def _fake_creds(*a, **k):
            raise RuntimeError(f"credential failure {secret}")

        async def _fake_orchestrate(self, **kwargs):
            return {"output": "done without google service", "subtasks": []}

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma.Orchestrator, "orchestrate", _fake_orchestrate)

        with caplog.at_level(logging.WARNING, logger=ma.logger.name):
            resp = client.post("/api/multi-agent/orchestrate", json={"task": "do"})

        assert resp.status_code == 200, resp.text
        assert resp.json()["output"] == "done without google service"
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text
        assert all(record.exc_info is None for record in caplog.records)


# =========================================================================== #
# HTTP endpoints — workflows (image-edit / excel) + adk-samples
# =========================================================================== #
class TestWorkflowEndpoints:
    def test_image_edit_credential_failure_is_generic(self, client, monkeypatch, caplog):
        secret = "workflow-image-secret"

        async def _boom_creds(*a, **k):
            raise RuntimeError(f"no google key {secret}")

        monkeypatch.setattr(ma, "get_provider_credentials", _boom_creds)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                "/api/multi-agent/workflows/image-edit",
                json={"image_url": "https://x/a.png", "edit_prompt": "make it blue"},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Image edit workflow failed",
            secret=secret,
        )

    def test_excel_analysis_requires_reference(self, client, monkeypatch):
        async def _fake_creds(*a, **k):
            return ("key", "")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        resp = client.post(
            "/api/multi-agent/workflows/excel-analysis",
            json={"analysis_type": "comprehensive"},
        )
        # No attachment_id/file_url/file_path → 400 from reference resolver
        assert resp.status_code == 400

    def test_excel_analysis_internal_error_is_generic(self, client, monkeypatch, caplog):
        secret = "workflow-excel-secret"

        async def _fake_creds(*a, **k):
            return ("key", "")

        def _boom_reference(**kwargs):
            raise RuntimeError(f"resolver failed {secret}")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma, "_resolve_excel_file_reference", _boom_reference)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                "/api/multi-agent/workflows/excel-analysis",
                json={"analysis_type": "comprehensive", "file_url": "https://x/data.xlsx"},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Excel analysis workflow failed",
            secret=secret,
        )

    def test_adk_samples_list_failure_is_generic(self, client, monkeypatch, caplog):
        secret = "workflow-adk-list-secret"

        class _FakeImporter:
            def __init__(self, **kwargs):
                pass

            async def list_available_templates(self):
                raise RuntimeError(f"list templates failed {secret}")

        import app.services.gemini.agent.adk_samples_importer as importer_mod

        monkeypatch.setattr(importer_mod, "ADKSamplesImporter", _FakeImporter)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.get("/api/multi-agent/workflows/adk-samples/templates")

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Failed to list ADK sample templates",
            secret=secret,
        )

    def test_adk_samples_import_bad_template_400(self, client, monkeypatch):
        class _FakeImporter:
            def __init__(self, **kwargs):
                pass

            async def import_template(self, **kwargs):
                raise ValueError("unknown template")

        import app.services.gemini.agent.adk_samples_importer as importer_mod

        monkeypatch.setattr(importer_mod, "ADKSamplesImporter", _FakeImporter)
        resp = client.post(
            "/api/multi-agent/workflows/adk-samples/import",
            json={"template_id": "nope"},
        )
        assert resp.status_code == 400

    def test_adk_samples_import_happy(self, client, monkeypatch):
        class _FakeImporter:
            def __init__(self, **kwargs):
                pass

            async def import_template(self, **kwargs):
                return {"id": "tmpl-1", "name": "Imported"}

        import app.services.gemini.agent.adk_samples_importer as importer_mod

        monkeypatch.setattr(importer_mod, "ADKSamplesImporter", _FakeImporter)
        resp = client.post(
            "/api/multi-agent/workflows/adk-samples/import",
            json={"template_id": "marketing-agency", "custom_name": "Imported"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "Imported"

    def test_adk_samples_import_failure_is_generic(self, client, monkeypatch, caplog):
        secret = "workflow-adk-import-secret"

        class _FakeImporter:
            def __init__(self, **kwargs):
                pass

            async def import_template(self, **kwargs):
                raise RuntimeError(f"import template failed {secret}")

        import app.services.gemini.agent.adk_samples_importer as importer_mod

        monkeypatch.setattr(importer_mod, "ADKSamplesImporter", _FakeImporter)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                "/api/multi-agent/workflows/adk-samples/import",
                json={"template_id": "marketing-agency"},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Failed to import ADK sample template",
            secret=secret,
        )

    def test_adk_samples_import_all(self, client, monkeypatch):
        class _FakeImporter:
            def __init__(self, **kwargs):
                pass

            async def import_all_templates(self, **kwargs):
                return [{"id": "a"}, {"id": "b"}]

        import app.services.gemini.agent.adk_samples_importer as importer_mod

        monkeypatch.setattr(importer_mod, "ADKSamplesImporter", _FakeImporter)
        resp = client.post("/api/multi-agent/workflows/adk-samples/import-all")
        assert resp.status_code == 200, resp.text
        assert resp.json()["count"] == 2

    def test_adk_samples_import_all_failure_is_generic(
        self, client, monkeypatch, caplog
    ):
        secret = "workflow-adk-import-all-secret"

        class _FakeImporter:
            def __init__(self, **kwargs):
                pass

            async def import_all_templates(self, **kwargs):
                raise RuntimeError(f"import all failed {secret}")

        import app.services.gemini.agent.adk_samples_importer as importer_mod

        monkeypatch.setattr(importer_mod, "ADKSamplesImporter", _FakeImporter)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post("/api/multi-agent/workflows/adk-samples/import-all")

        _assert_generic_error_response(
            resp,
            caplog,
            detail="Failed to import ADK sample templates",
            secret=secret,
        )


# =========================================================================== #
# Runtime run-live endpoint (aggregates fake event stream)
# =========================================================================== #
class TestRuntimeRunLive:
    def test_run_live_requires_input(self, client, db_session):
        agent = _add_agent(db_session)
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run-live", json={}
        )
        assert resp.status_code == 400

    def test_run_live_aggregates_events(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        events = [
            {"type": "chunk", "content": "partial", "invocation_id": "inv-1"},
            {
                "type": "final",
                "content": "final answer",
                "invocation_id": "inv-1",
                "is_final": True,
                "actions": {"done": True},
                "long_running_tool_ids": ["lr-1"],
            },
        ]
        _patch_runner(monkeypatch, _FakeRunner(live_events=events))
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run-live",
            json={"input": "hi"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["output"] == "final answer"
        assert body["event_count"] == 2
        assert body["invocation_id"] == "inv-1"
        assert "lr-1" in body["long_running_tool_ids"]

    def test_run_live_invalid_request_event_400(self, client, db_session, monkeypatch):
        agent = _add_agent(db_session)
        events = [{"type": "error", "error": "bad request", "invalid_request": True}]
        _patch_runner(monkeypatch, _FakeRunner(live_events=events))
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run-live",
            json={"input": "hi"},
        )
        assert resp.status_code == 400

    def test_run_live_runtime_error_event_is_generic(
        self, client, db_session, monkeypatch, caplog
    ):
        secret = "runtime-live-secret"
        agent = _add_agent(db_session)
        events = [{"type": "error", "error": f"engine fault {secret}"}]
        _patch_runner(monkeypatch, _FakeRunner(live_events=events))
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                f"/api/multi-agent/agents/{agent.id}/runtime/run-live",
                json={"input": "hi"},
            )

        _assert_generic_error_response(
            resp,
            caplog,
            detail="ADK live run failed",
            secret=secret,
        )

    def test_run_live_chunk_only_fallback_output(self, client, db_session, monkeypatch):
        # No final event → output joins the chunk contents.
        agent = _add_agent(db_session)
        events = [
            {"type": "chunk", "content": "a", "invocation_id": "inv-2"},
            {"type": "chunk", "content": "b", "invocation_id": "inv-2"},
        ]
        _patch_runner(monkeypatch, _FakeRunner(live_events=events))
        resp = client.post(
            f"/api/multi-agent/agents/{agent.id}/runtime/run-live",
            json={"input": "hi"},
        )
        body = resp.json()
        assert resp.status_code == 200
        assert "a" in body["output"] and "b" in body["output"]


# =========================================================================== #
# Runner factory + memory-manager builder (direct, runtime layer faked)
# =========================================================================== #
class TestRunnerFactoryAndMemoryBuilder:
    async def test_create_runner_no_runtime_skips_credentials(self, db_session, monkeypatch):
        # require_runtime=False must not call get_provider_credentials or ADK SDK.
        agent = _add_agent(db_session)

        async def _should_not_call(*a, **k):
            raise AssertionError("credentials must not be fetched when require_runtime=False")

        monkeypatch.setattr(ma, "get_provider_credentials", _should_not_call)
        runner, api_key = await ma._create_adk_runner_for_agent(
            db=db_session, user_id=USER_ID, agent=agent, require_runtime=False,
        )
        assert api_key == ""
        assert runner is not None

    def test_build_memory_manager_plain(self, db_session):
        mgr = ma._build_memory_manager(
            db=db_session, project=None, location=None, agent_engine_id=None,
        )
        assert mgr is not None

    def test_build_memory_manager_vertex(self, db_session):
        mgr = ma._build_memory_manager(
            db=db_session, project="p", location="us-central1", agent_engine_id="eng-1",
        )
        assert mgr is not None


# =========================================================================== #
# Sheet ingest kwargs builder + official orchestration early-return branches
# =========================================================================== #
class TestSheetIngestKwargs:
    def _request(self, **overrides):
        base = {"stage": "ingest"}
        base.update(overrides)
        return ma.SheetStageProtocolRequest(**base)

    def test_ingest_kwargs_inline_content(self, db_session):
        req = self._request(content="col_a,col_b\n1,2", content_encoding="plain")
        kwargs = ma._build_sheet_ingest_kwargs(request_body=req, db=db_session, user_id=USER_ID)
        assert kwargs["content"] == "col_a,col_b\n1,2"
        assert kwargs["tenant_id"] == USER_ID

    def test_ingest_kwargs_data_url(self, db_session):
        req = self._request(data_url="data:text/csv;base64,YWJj")
        kwargs = ma._build_sheet_ingest_kwargs(request_body=req, db=db_session, user_id=USER_ID)
        assert kwargs["data_url"].startswith("data:")

    def test_ingest_kwargs_file_url(self, db_session):
        req = self._request(file_url="https://x/data.csv")
        kwargs = ma._build_sheet_ingest_kwargs(request_body=req, db=db_session, user_id=USER_ID)
        assert kwargs["file_url"] == "https://x/data.csv"

    def test_ingest_kwargs_rejects_local_file_url(self, db_session, tmp_path):
        secret = tmp_path / "secret.csv"
        secret.write_text("do,not,read", encoding="utf-8")
        req = self._request(file_url=str(secret))

        with pytest.raises(HTTPException) as exc_info:
            ma._build_sheet_ingest_kwargs(request_body=req, db=db_session, user_id=USER_ID)

        assert exc_info.value.status_code == 400
        assert "file_url only supports http/https/data URL" in str(exc_info.value.detail)


class TestOfficialOrchestrationEarlyReturns:
    async def test_no_sub_agents_returns_none(self, db_session):
        out = await ma._try_execute_official_adk_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={},
        )
        assert out is None

    async def test_sub_agent_missing_id_returns_none(self, db_session):
        out = await ma._try_execute_official_adk_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={"sub_agents": [{"agent_name": "x"}]},
        )
        assert out is None

    async def test_unknown_agents_returns_none(self, db_session):
        # Referenced agent ids do not exist in DB → cannot resolve → None.
        out = await ma._try_execute_official_adk_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={"sub_agents": [{"agent_id": "nope"}]},
        )
        assert out is None

    async def test_non_google_agents_returns_none(self, db_session):
        # Agent exists but is not google-adk → official path declines (None).
        agent = _add_agent(db_session, agent_type="custom", provider_id="openai")
        out = await ma._try_execute_official_adk_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={"sub_agents": [{"agent_id": agent.id}]},
        )
        assert out is None


# =========================================================================== #
# Sheet-stage protocol + lineage endpoints
# =========================================================================== #
class TestSheetStageEndpoints:
    def test_sheet_stage_protocol_dispatches_to_executor(self, client, monkeypatch):
        async def _fake_executor(**kwargs):
            return {"stage": "ingest", "status": "completed", "session_id": "sess-1"}

        monkeypatch.setattr(ma, "execute_sheet_stage_protocol_request", _fake_executor)
        resp = client.post(
            "/api/multi-agent/workflows/excel-analysis/stage",
            json={"stage": "ingest", "content": "a,b\n1,2"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "completed"

    def test_sheet_stage_protocol_value_error_400(self, client, monkeypatch):
        async def _bad_executor(**kwargs):
            raise ValueError("bad sheet input")

        monkeypatch.setattr(ma, "execute_sheet_stage_protocol_request", _bad_executor)
        resp = client.post(
            "/api/multi-agent/workflows/excel-analysis/stage",
            json={"stage": "ingest", "content": "x"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "SHEET_STAGE_INVALID_REQUEST"

    def test_sheet_stage_protocol_permission_error_403(self, client, monkeypatch):
        async def _denied(**kwargs):
            raise PermissionError("not your sheet")

        monkeypatch.setattr(ma, "execute_sheet_stage_protocol_request", _denied)
        resp = client.post(
            "/api/multi-agent/workflows/excel-analysis/stage",
            json={"stage": "query", "sessionId": "sess-1", "query": "q"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["code"] == "SHEET_STAGE_FORBIDDEN"

    def test_sheet_stage_protocol_unexpected_error_is_generic(
        self, client, monkeypatch, caplog
    ):
        secret = "sheet-stage-protocol-secret"

        async def _boom(**kwargs):
            raise RuntimeError(f"kaboom {secret}")

        monkeypatch.setattr(ma, "execute_sheet_stage_protocol_request", _boom)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post(
                "/api/multi-agent/workflows/excel-analysis/stage",
                json={"stage": "ingest", "content": "x"},
            )

        assert resp.status_code == 500
        error = resp.json()["detail"]["error"]
        assert error["code"] == "SHEET_STAGE_INTERNAL_ERROR"
        assert error["message"] == "Sheet stage protocol failed"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_lineage_unsupported_protocol_version_400(self, client):
        resp = client.get(
            "/api/multi-agent/workflows/excel-analysis/stage/lineage",
            params={
                "sessionId": "sess-1",
                "artifactKey": "sheet/ingest",
                "artifactVersion": 1,
                "protocolVersion": "sheet-stage/v999",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "SHEET_STAGE_PROTOCOL_UNSUPPORTED"

    def test_lineage_happy_path(self, client, monkeypatch):
        async def _fake_lineage(**kwargs):
            return [{"artifact_key": "sheet/ingest", "artifact_version": 1}]

        monkeypatch.setattr(
            ma._sheet_stage_artifact_service,
            "query_sheet_artifact_lineage",
            _fake_lineage,
        )
        resp = client.get(
            "/api/multi-agent/workflows/excel-analysis/stage/lineage",
            params={
                "sessionId": "sess-1",
                "artifactKey": "sheet/ingest",
                "artifactVersion": 1,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert "lineage" in body["data"]

    def test_lineage_session_not_found_404(self, client, monkeypatch):
        async def _missing(**kwargs):
            raise ma.ADKArtifactSessionError("session not found")

        monkeypatch.setattr(
            ma._sheet_stage_artifact_service,
            "query_sheet_artifact_lineage",
            _missing,
        )
        resp = client.get(
            "/api/multi-agent/workflows/excel-analysis/stage/lineage",
            params={
                "sessionId": "sess-1",
                "artifactKey": "sheet/profile",
                "artifactVersion": 1,
            },
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "SHEET_STAGE_SESSION_NOT_FOUND"

    def test_lineage_unexpected_error_is_generic(self, client, monkeypatch, caplog):
        secret = "sheet-stage-lineage-secret"

        async def _boom(**kwargs):
            raise RuntimeError(f"lineage failed {secret}")

        monkeypatch.setattr(
            ma._sheet_stage_artifact_service,
            "query_sheet_artifact_lineage",
            _boom,
        )
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.get(
                "/api/multi-agent/workflows/excel-analysis/stage/lineage",
                params={
                    "sessionId": "sess-1",
                    "artifactKey": "sheet/profile",
                    "artifactVersion": 1,
                },
            )

        assert resp.status_code == 500
        error = resp.json()["detail"]["error"]
        assert error["code"] == "SHEET_STAGE_INTERNAL_ERROR"
        assert error["message"] == "Sheet stage lineage query failed"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text


# =========================================================================== #
# Sheet-stage authorization / freshness / transition validators (sync, pure)
# =========================================================================== #
class TestSheetStageValidators:
    def test_authorize_artifact_ref_ok(self):
        ref = {"artifact_session_id": "s1"}
        out = ma._authorize_sheet_artifact_ref_or_raise(
            stage="profile", session_id="s1", user_id=USER_ID,
            raw_artifact_ref={"tenant_id": USER_ID}, normalized_artifact_ref=ref,
        )
        assert out is ref

    def test_authorize_artifact_ref_session_mismatch_400(self):
        with pytest.raises(HTTPException) as exc:
            ma._authorize_sheet_artifact_ref_or_raise(
                stage="profile", session_id="s1", user_id=USER_ID,
                raw_artifact_ref={}, normalized_artifact_ref={"artifact_session_id": "other"},
            )
        assert exc.value.status_code == 400

    def test_authorize_artifact_ref_tenant_mismatch_403(self):
        with pytest.raises(HTTPException) as exc:
            ma._authorize_sheet_artifact_ref_or_raise(
                stage="profile", session_id="s1", user_id=USER_ID,
                raw_artifact_ref={"tenant_id": "intruder"},
                normalized_artifact_ref={"artifact_session_id": "s1"},
            )
        assert exc.value.status_code == 403

    def test_ensure_artifact_fresh_ok(self):
        state = {"artifact_versions": {"sheet/ingest": 2}}
        ma._ensure_sheet_stage_artifact_fresh_or_raise(
            session_state=state, stage="profile", session_id="s1",
            artifact_ref={"artifact_key": "sheet/ingest", "artifact_version": 2},
        )

    def test_ensure_artifact_fresh_not_found_404(self):
        with pytest.raises(HTTPException) as exc:
            ma._ensure_sheet_stage_artifact_fresh_or_raise(
                session_state={"artifact_versions": {}}, stage="profile", session_id="s1",
                artifact_ref={"artifact_key": "sheet/ingest", "artifact_version": 1},
            )
        assert exc.value.status_code == 404

    def test_ensure_artifact_fresh_stale_409(self):
        with pytest.raises(HTTPException) as exc:
            ma._ensure_sheet_stage_artifact_fresh_or_raise(
                session_state={"artifact_versions": {"sheet/ingest": 3}},
                stage="profile", session_id="s1",
                artifact_ref={"artifact_key": "sheet/ingest", "artifact_version": 1},
            )
        assert exc.value.status_code == 409

    def test_ensure_transition_ok(self):
        ma._ensure_sheet_stage_transition_or_raise(
            session_state={"current_stage": "ingest"}, stage="profile", session_id="s1",
        )

    def test_ensure_transition_invalid_409(self):
        with pytest.raises(HTTPException) as exc:
            ma._ensure_sheet_stage_transition_or_raise(
                session_state={"current_stage": "export"}, stage="profile", session_id="s1",
            )
        assert exc.value.status_code == 409

    def test_extract_tenant_binding(self):
        assert ma._extract_sheet_artifact_tenant_binding({"tenant_id": "t"}) == "t"
        assert ma._extract_sheet_artifact_tenant_binding("not-a-dict") == ""

    def test_new_session_state_shape(self):
        state = ma._new_sheet_stage_session_state(USER_ID)
        assert state["user_id"] == USER_ID
        assert state["current_stage"] == ""
        assert state["artifact_versions"] == {}

    def test_prune_sessions_noop_when_under_cap(self):
        # Just exercise the early-return branch; cache is small.
        ma._prune_sheet_stage_sessions_locked()

    def test_build_session_id(self):
        sid = ma._build_sheet_stage_session_id()
        assert isinstance(sid, str) and sid


# =========================================================================== #
# Sheet-stage async service wrappers (service layer faked → error mapping)
# =========================================================================== #
class TestSheetStageServiceWrappers:
    async def test_resolve_session_binding_other_user_403(self, monkeypatch):
        async def _raise(**kwargs):
            raise ma.ADKArtifactBindingError("session bound to another user")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "resolve_sheet_stage_session", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._resolve_sheet_stage_session(
                requested_session_id="s1", user_id=USER_ID, stage="profile",
            )
        assert exc.value.status_code == 403
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_SESSION_FORBIDDEN"

    async def test_resolve_session_binding_mismatch_409(self, monkeypatch):
        async def _raise(**kwargs):
            raise ma.ADKArtifactBindingError("some other binding error")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "resolve_sheet_stage_session", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._resolve_sheet_stage_session(
                requested_session_id="s1", user_id=USER_ID, stage="profile",
            )
        assert exc.value.status_code == 409

    async def test_resolve_session_required_400(self, monkeypatch):
        async def _raise(**kwargs):
            raise ma.ADKArtifactSessionError("session_id required for non-ingest stage")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "resolve_sheet_stage_session", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._resolve_sheet_stage_session(
                requested_session_id="", user_id=USER_ID, stage="profile",
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"]["code"] == "SHEET_STAGE_SESSION_REQUIRED"

    async def test_resolve_session_not_found_404(self, monkeypatch):
        async def _raise(**kwargs):
            raise ma.ADKArtifactSessionError("session not found")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "resolve_sheet_stage_session", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._resolve_sheet_stage_session(
                requested_session_id="s1", user_id=USER_ID, stage="query",
            )
        assert exc.value.status_code == 404

    async def test_resolve_session_happy(self, monkeypatch):
        async def _ok(**kwargs):
            return ("s1", {"current_stage": "ingest"})

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "resolve_sheet_stage_session", _ok)
        session_id, state = await ma._resolve_sheet_stage_session(
            requested_session_id="s1", user_id=USER_ID, stage="profile",
        )
        assert session_id == "s1"
        assert state["current_stage"] == "ingest"

    async def test_store_artifact_value_error_400(self, monkeypatch):
        async def _raise(**kwargs):
            raise ValueError("bad payload")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "store_sheet_stage_artifact", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._store_sheet_stage_artifact(
                session_state={}, session_id="s1", stage="ingest",
                artifact_key="sheet/ingest", payload={},
            )
        assert exc.value.status_code == 400

    async def test_store_artifact_happy(self, monkeypatch):
        async def _ok(**kwargs):
            return ({"artifact_key": "sheet/ingest", "artifact_version": 1}, {"stored": True})

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "store_sheet_stage_artifact", _ok)
        ref, meta = await ma._store_sheet_stage_artifact(
            session_state={}, session_id="s1", stage="ingest",
            artifact_key="sheet/ingest", payload={"x": 1},
        )
        assert ref["artifact_version"] == 1
        assert meta["stored"] is True

    async def test_load_artifact_not_found_404(self, monkeypatch):
        async def _raise(**kwargs):
            raise ma.ADKArtifactNotFoundError("version not found")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "load_sheet_stage_artifact", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._load_sheet_stage_artifact_or_raise(
                stage="profile", session_id="s1", user_id=USER_ID,
                artifact_ref={"artifact_key": "sheet/ingest", "artifact_version": 1},
            )
        assert exc.value.status_code == 404

    async def test_load_artifact_forbidden_403(self, monkeypatch):
        async def _raise(**kwargs):
            raise ma.ADKArtifactBindingError("not your artifact")

        monkeypatch.setattr(ma._sheet_stage_artifact_service, "load_sheet_stage_artifact", _raise)
        with pytest.raises(HTTPException) as exc:
            await ma._load_sheet_stage_artifact_or_raise(
                stage="profile", session_id="s1", user_id=USER_ID,
                artifact_ref={"artifact_key": "sheet/ingest", "artifact_version": 1},
            )
        assert exc.value.status_code == 403


# =========================================================================== #
# Legacy explicit orchestration (sequential / parallel) — service faked
# =========================================================================== #
class TestExplicitLegacyOrchestration:
    async def test_no_sub_agents_returns_none(self, db_session):
        out = await ma._execute_explicit_legacy_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={},
        )
        assert out is None

    async def test_sub_agent_missing_id_returns_none(self, db_session):
        out = await ma._execute_explicit_legacy_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={"sub_agents": [{"agent_name": "x"}]},
        )
        assert out is None

    async def test_sequential_executes(self, db_session, monkeypatch):
        class _FakeSeq:
            def __init__(self, **kwargs):
                pass

            async def execute(self, **kwargs):
                return {"success": True, "final_output": "seq result", "errors": {}}

        import app.services.gemini.agent.sequential_agent as seq_mod

        monkeypatch.setattr(seq_mod, "SequentialAgent", _FakeSeq)
        out = await ma._execute_explicit_legacy_orchestration(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={"sub_agents": [{"agent_id": "a1"}]},
        )
        assert out is not None
        assert out["runtime"] == "legacy-explicit-policy"
        assert out["output"] == "seq result"
        assert out["mode"] == "sequential"

    async def test_parallel_executes(self, db_session, monkeypatch):
        class _FakePar:
            def __init__(self, **kwargs):
                pass

            async def execute(self, **kwargs):
                return {"success": True, "results": {"a1": "ok"}, "errors": {}}

        import app.services.gemini.agent.parallel_agent as par_mod

        monkeypatch.setattr(par_mod, "ParallelAgent", _FakePar)
        out = await ma._execute_explicit_legacy_orchestration(
            db=db_session, user_id=USER_ID, mode="parallel", task="t",
            workflow_config={"sub_agents": [{"agent_id": "a1", "agent_name": "First"}]},
        )
        assert out is not None
        assert out["mode"] == "parallel"
        assert out["agents"][0]["name"] == "First"

    async def test_unknown_mode_returns_none(self, db_session):
        out = await ma._execute_explicit_legacy_orchestration(
            db=db_session, user_id=USER_ID, mode="weird", task="t",
            workflow_config={"sub_agents": [{"agent_id": "a1"}]},
        )
        assert out is None


# =========================================================================== #
# Orchestration runtime-contract dispatcher
# =========================================================================== #
class TestOrchestrationRuntimeContract:
    async def test_official_result_short_circuits(self, db_session, monkeypatch):
        async def _official(**kwargs):
            return {"runtime": "adk-official", "output": "official"}

        monkeypatch.setattr(ma, "_try_execute_official_adk_orchestration", _official)
        out = await ma._execute_orchestration_with_runtime_contract(
            db=db_session, user_id=USER_ID, mode="sequential", task="t",
            workflow_config={"sub_agents": [{"agent_id": "a"}]},
        )
        assert out["runtime"] == "adk-official"

    async def test_official_http_error_remapped(self, db_session, monkeypatch):
        async def _boom(**kwargs):
            raise HTTPException(status_code=400, detail="bad config")

        monkeypatch.setattr(ma, "_try_execute_official_adk_orchestration", _boom)
        with pytest.raises(HTTPException) as exc:
            await ma._execute_orchestration_with_runtime_contract(
                db=db_session, user_id=USER_ID, mode="sequential", task="t",
                workflow_config={"sub_agents": [{"agent_id": "a"}]},
            )
        # 4xx classification → ADK invalid-request error envelope.
        assert exc.value.status_code == 400


# =========================================================================== #
# Orchestrate endpoint — strict-mode default branch
# =========================================================================== #
class TestOrchestrateStrict:
    def test_default_mode_orchestrator_runtime_error_is_generic(
        self, client, monkeypatch, caplog
    ):
        secret = "orchestrator-runtime-secret"

        async def _fake_creds(*a, **k):
            return ("key", "")

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)
        monkeypatch.setattr(ma.ProviderFactory, "create", lambda **k: object())

        async def _raise(self, **kwargs):
            # Non-degrade marker absent + non-strict → RuntimeError re-raised → 500.
            raise RuntimeError(f"orchestrator failed hard {secret}")

        monkeypatch.setattr(ma.Orchestrator, "orchestrate", _raise)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post("/api/multi-agent/orchestrate", json={"task": "do"})

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to orchestrate task"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_orchestrate_unexpected_exception_is_generic(self, client, monkeypatch, caplog):
        secret = "orchestrator-unexpected-secret"
        # GoogleService creation failure is swallowed; force orchestrate to raise non-HTTP.
        async def _fake_creds(*a, **k):
            raise RuntimeError("creds boom")  # swallowed → google_service stays None

        monkeypatch.setattr(ma, "get_provider_credentials", _fake_creds)

        async def _raise(self, **kwargs):
            raise ValueError(f"unexpected {secret}")

        monkeypatch.setattr(ma.Orchestrator, "orchestrate", _raise)
        with caplog.at_level(logging.ERROR, logger=ma.logger.name):
            resp = client.post("/api/multi-agent/orchestrate", json={"task": "do"})

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to orchestrate task"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text


# =========================================================================== #
# Runtime contract helpers
# =========================================================================== #
class TestRuntimeContractHelpers:
    def test_classify_orchestration_http_error_4xx(self):
        out = ma._classify_orchestration_http_error(HTTPException(status_code=400, detail="bad"))
        assert out["status_code"] == 400
        assert out["error_code"] == ma.ADKRuntimeErrorCode.ADK_INVALID_REQUEST

    def test_classify_orchestration_http_error_5xx(self):
        out = ma._classify_orchestration_http_error(HTTPException(status_code=500, detail="boom"))
        assert out["status_code"] == 500
        assert out["error_code"] == ma.ADKRuntimeErrorCode.ADK_RUNTIME_UNAVAILABLE

    def test_classify_orchestration_classifier_failure_logs_summary(
        self, monkeypatch, caplog
    ):
        secret = "orchestration-classifier-secret"

        def _boom(exc):
            raise RuntimeError(f"classifier failed {secret}")

        monkeypatch.setattr(ma, "_classify_orchestration_http_exception", _boom)
        with caplog.at_level(logging.WARNING, logger=ma.logger.name):
            out = ma._classify_orchestration_http_error(
                HTTPException(status_code=400, detail="bad")
            )

        assert out["status_code"] == 400
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_resolve_runtime_contract_default(self):
        contract = ma._resolve_adk_orchestration_runtime_contract()
        assert "runtime_strategy" in contract
        assert "strict_mode" in contract
        assert "fallback_allowed" in contract
