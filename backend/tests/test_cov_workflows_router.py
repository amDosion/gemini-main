"""Coverage-focused tests for ``app.routers.ai.workflows`` (the workflows REST router).

Strategy
--------
* Real router logic is exercised through a fresh :class:`FastAPI` app that mounts
  the production ``router`` and overrides only the two FastAPI boundary
  dependencies — ``require_current_user`` (auth) and ``get_db`` (DB session).
* The DB is a real in-memory SQLite engine populated with the actual SQLAlchemy
  models, so the router's query / pagination / permission / serialization logic
  runs for real instead of being stubbed.
* External boundaries that would touch the network or run the full graph engine
  (``WorkflowEngine.execute``, image/media persistence) are the only things
  patched. Pure helper functions are tested directly.

These tests assert real behavior: status codes, response envelopes,
auth/permission (user scoping → 404), error mapping, pagination clamping,
idempotency replay, state-machine transitions, and validation branches.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import require_current_user
from app.models.db_models import (
    AgentRegistry,
    ConfigProfile,
    NodeExecution,
    WorkflowExecution,
    WorkflowTemplate,
    generate_uuid,
)
from app.routers.ai import workflows as wf

USER_ID = "user-cov-1"
OTHER_USER_ID = "user-cov-2"


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
def client(db_session, monkeypatch):
    """TestClient whose auth + DB dependencies resolve to our fixtures.

    Seed-agent insertion and agent-binding validation are neutralized so the
    happy paths don't depend on the (large) starter-template definitions; the
    individual endpoint logic under test is still real.
    """
    app = FastAPI()
    app.include_router(wf.router)

    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session

    # Neutralize seed-agent side effects (they insert rows + read big presets).
    monkeypatch.setattr(wf, "ensure_seed_agents", lambda *a, **k: 0)
    monkeypatch.setattr(wf, "get_default_seed_agents", lambda: [])

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _add_execution(
    db,
    *,
    user_id: str = USER_ID,
    status: str = "completed",
    workflow: Optional[Dict[str, Any]] = None,
    input_payload: Optional[Dict[str, Any]] = None,
    result: Optional[Any] = None,
    error: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    started_at: Optional[int] = None,
    completed_at: Optional[int] = None,
) -> WorkflowExecution:
    now = int(time.time() * 1000)
    workflow = workflow or {
        "schemaVersion": 2,
        "nodes": [{"id": "n1", "type": "start"}, {"id": "n2", "type": "end"}],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
        "meta": {"source": "test", "title": "My Flow"},
    }
    execution = WorkflowExecution(
        id=generate_uuid(),
        user_id=user_id,
        idempotency_key=idempotency_key,
        workflow_json=json.dumps(workflow, ensure_ascii=False),
        input_json=json.dumps(input_payload or {"task": "do thing"}, ensure_ascii=False),
        result_json=json.dumps(result, ensure_ascii=False) if result is not None else None,
        status=status,
        error=error,
        started_at=started_at if started_at is not None else now,
        completed_at=completed_at,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _add_agent(
    db,
    *,
    name: str,
    user_id: str = USER_ID,
    status: str = "active",
    provider_id: str = "google",
    model_id: str = "gemini-2.5-flash",
    agent_type: str = "custom",
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
        system_prompt="",
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


def _workflow_log_text(caplog) -> str:
    return "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == wf.logger.name
    )


# --------------------------------------------------------------------------- #
# Pure helpers / module-level state machines (no DB, no client)
# --------------------------------------------------------------------------- #
class TestWorkflowRuntimeLogSanitization:
    def test_background_runtime_store_sync_logs_error_summary(self, caplog):
        secret = "runtime-store-sync-secret"

        async def _boom():
            raise RuntimeError(f"sync failed {secret}")

        async def _run():
            with caplog.at_level(logging.DEBUG, logger=wf.logger.name):
                wf._schedule_runtime_store_sync(
                    _boom(),
                    execution_id="exec-runtime-sync",
                    action="touch",
                )
                await asyncio.sleep(0)
                await asyncio.sleep(0)

        asyncio.run(_run())

        log_text = _workflow_log_text(caplog)
        assert secret not in log_text
        assert "Traceback" not in log_text
        assert "<redacted error; length=" in log_text

    def test_cleanup_runtime_clear_logs_error_summary(self, monkeypatch, caplog):
        secret = "runtime-clear-secret"

        class FakeRuntimeStore:
            async def clear(self, *args, **kwargs):
                raise RuntimeError(f"clear failed {secret}")

        monkeypatch.setattr(wf, "_workflow_runtime_store", FakeRuntimeStore())

        with caplog.at_level(logging.DEBUG, logger=wf.logger.name):
            asyncio.run(
                wf._cleanup_execution_runtime(
                    "exec-runtime-clear",
                    clear_store=True,
                    clear_local_runtime=True,
                )
            )

        log_text = _workflow_log_text(caplog)
        assert secret not in log_text
        assert "Traceback" not in log_text
        assert "<redacted error; length=" in log_text

    def test_serialize_workflow_result_logs_error_summary(self, monkeypatch, caplog):
        secret = "serialize-secret"
        payload = {"text": secret}

        def _boom(_payload):
            raise RuntimeError(f"serialize failed {secret}")

        monkeypatch.setattr(wf, "to_camel_case", _boom)

        with caplog.at_level(logging.WARNING, logger=wf.logger.name):
            result = wf._serialize_workflow_result(payload)

        log_text = _workflow_log_text(caplog)
        assert result is payload
        assert secret not in log_text
        assert "Traceback" not in log_text
        assert "<redacted error; length=" in log_text


class TestStatusNormalization:
    def test_workflow_status_alias_mapping(self):
        assert wf._normalize_workflow_status("queued") == "pending"
        assert wf._normalize_workflow_status("in_progress") == "running"
        assert wf._normalize_workflow_status("done") == "completed"
        assert wf._normalize_workflow_status("error") == "failed"
        assert wf._normalize_workflow_status("canceled") == "cancelled"

    def test_workflow_status_unknown_falls_back_to_default(self):
        assert wf._normalize_workflow_status("nonsense") == "pending"
        assert wf._normalize_workflow_status("", default="running") == "running"
        assert wf._normalize_workflow_status(None) == "pending"

    def test_node_status_alias_mapping(self):
        assert wf._normalize_node_status("queued") == "pending"
        assert wf._normalize_node_status("success") == "completed"
        assert wf._normalize_node_status("cancelled") == "skipped"
        assert wf._normalize_node_status("weird", default="failed") == "failed"

    def test_resolve_terminal_workflow_event(self):
        assert wf._resolve_terminal_workflow_event("completed") == "workflow_complete"
        assert wf._resolve_terminal_workflow_event("cancelled") == "workflow_cancelled"
        assert wf._resolve_terminal_workflow_event("failed") == "workflow_failed"
        # unknown maps to failed
        assert wf._resolve_terminal_workflow_event("???") == "workflow_failed"

    def test_resolve_workflow_final_status_paused(self):
        assert wf._resolve_workflow_final_status("paused") == "workflow_paused"
        assert wf._resolve_workflow_final_status("completed") == "completed"


class TestTransitionStateMachine:
    def test_workflow_transition_allowed(self):
        execution = WorkflowExecution(status="pending")
        assert wf._transition_workflow_status(execution, "running") == "running"
        assert execution.status == "running"
        assert wf._transition_workflow_status(execution, "completed") == "completed"

    def test_workflow_transition_same_status_is_noop(self):
        execution = WorkflowExecution(status="running")
        assert wf._transition_workflow_status(execution, "running") == "running"

    def test_workflow_transition_illegal_raises(self):
        execution = WorkflowExecution(status="completed")
        with pytest.raises(wf.InvalidWorkflowStateTransitionError):
            wf._transition_workflow_status(execution, "running")

    def test_workflow_transition_empty_target_raises(self):
        execution = WorkflowExecution(status="pending")
        with pytest.raises(wf.InvalidWorkflowStateTransitionError):
            wf._transition_workflow_status(execution, "")

    def test_node_transition_allowed_and_illegal(self):
        node = NodeExecution(status="pending")
        assert wf._transition_node_status(node, "running") == "running"
        assert wf._transition_node_status(node, "completed") == "completed"
        with pytest.raises(wf.InvalidWorkflowStateTransitionError):
            wf._transition_node_status(node, "running")  # completed -> running illegal


class TestIdempotencyHelpers:
    def test_normalize_idempotency_key_trims_and_caps(self):
        assert wf._normalize_idempotency_key("  abc  ") == "abc"
        assert wf._normalize_idempotency_key("") == ""
        assert wf._normalize_idempotency_key(None) == ""
        long_key = "x" * 200
        normalized = wf._normalize_idempotency_key(long_key)
        assert len(normalized) == wf.WORKFLOW_IDEMPOTENCY_MAX_KEY_LENGTH

    def test_resolve_execute_idempotency_key_from_meta(self):
        key = wf._resolve_execute_idempotency_key({"idempotencyKey": "meta-key"}, None)
        assert key == "meta-key"

    def test_resolve_execute_idempotency_key_none_meta(self):
        assert wf._resolve_execute_idempotency_key(None, None) == ""


class TestAgentTaskFilters:
    def test_normalize_agent_list_status(self):
        assert wf._normalize_agent_list_status("active") == "active"
        assert wf._normalize_agent_list_status("INACTIVE") == "inactive"
        assert wf._normalize_agent_list_status("garbage") == ""

    def test_normalize_agent_task_filter_default(self):
        assert wf._normalize_agent_task_filter("") == "all"
        assert wf._normalize_agent_task_filter("chat") == "chat"
        assert wf._normalize_agent_task_filter("nope") == "all"

    def test_extract_agent_default_task_type(self):
        payload = {"agentCard": {"defaults": {"defaultTaskType": "image-gen"}}}
        assert wf._extract_agent_default_task_type(payload) == "image-gen"
        # Missing / malformed → chat
        assert wf._extract_agent_default_task_type({}) == "chat"
        assert wf._extract_agent_default_task_type("not-a-dict") == "chat"

    def test_build_and_filter_task_counts(self):
        payloads = [
            {"agentCard": {"defaults": {"defaultTaskType": "chat"}}},
            {"agentCard": {"defaults": {"defaultTaskType": "image-gen"}}},
            {"agentCard": {"defaults": {"defaultTaskType": "image-gen"}}},
        ]
        counts = wf._build_agent_task_counts(payloads)
        assert counts["all"] == 3
        assert counts["image-gen"] == 2
        assert counts["chat"] == 1

        filtered = wf._filter_agent_payloads_by_task(payloads, "image-gen")
        assert len(filtered) == 2
        assert wf._filter_agent_payloads_by_task(payloads, "all") == payloads


class TestRegistryTypeHelpers:
    def test_normalize_agent_registry_type_alias(self):
        assert wf._normalize_agent_registry_type("google-adk") == "adk"
        assert wf._normalize_agent_registry_type("Custom") == "custom"
        assert wf._normalize_agent_registry_type(None) == "custom"

    def test_agent_type_requires_google_provider(self):
        assert wf._agent_type_requires_google_provider("adk") is True
        assert wf._agent_type_requires_google_provider("custom") is False


class TestModePresetHelpers:
    def test_normalize_mode_preset_id_alias(self):
        assert wf._normalize_mode_preset_id("image_gen") == "image-gen"
        assert wf._normalize_mode_preset_id("image-edit") == "image-chat-edit"
        assert wf._normalize_mode_preset_id("") == ""

    def test_build_mode_preset_summary_shape(self):
        preset = wf.MODE_WORKFLOW_PRESETS["image-gen"]
        summary = wf._build_mode_preset_summary(preset)
        assert summary["id"] == "image-gen"
        assert summary["node_count"] > 0
        assert summary["edge_count"] > 0
        assert "requires_image" in summary


class TestSanitizeAndSerialize:
    def test_sanitize_truncates_long_strings(self):
        # Spaces keep it off the base64-blob heuristic so the length-truncation
        # branch is exercised instead.
        text = "word " * 1000
        out = wf._sanitize_history_detail_payload(text, max_text_chars=100)
        assert out.startswith("word ")
        assert "truncated" in out

    def test_sanitize_omits_base64_image(self):
        data_url = "data:image/png;base64," + ("A" * 100)
        out = wf._sanitize_history_detail_payload(data_url)
        assert "inline-image-omitted" in out

    def test_sanitize_truncates_lists_and_dicts(self):
        big_list = list(range(100))
        out = wf._sanitize_history_detail_payload(big_list, max_list_items=5)
        assert out[-1]["_truncated"] is True
        assert out[-1]["remainingItems"] == 95

    def test_safe_json_loads_invalid_returns_default(self):
        assert wf._safe_json_loads("not json", default={"x": 1}) == {"x": 1}
        assert wf._safe_json_loads(None, default=[]) == []
        assert wf._safe_json_loads('{"a": 1}') == {"a": 1}

    def test_serialize_workflow_result_none(self):
        assert wf._serialize_workflow_result(None) is None

    def test_build_node_summary_aggregates(self):
        summary = wf._build_node_summary({"completed": 2, "success": 1, "failed": 1})
        # "success" normalizes into "completed"
        assert summary["completed"] == 3
        assert summary["failed"] == 1
        assert summary["total"] == 4

    def test_derive_execution_title_prefers_meta(self):
        assert wf._derive_execution_title({"title": "Hello"}, {}) == "Hello"
        assert wf._derive_execution_title({}, {"task": "do x"}) == "do x"
        assert wf._derive_execution_title({}, {}) == "未命名工作流"


# --------------------------------------------------------------------------- #
# Mode-preset endpoints
# --------------------------------------------------------------------------- #
class TestModePresetEndpoints:
    def test_list_mode_presets(self, client):
        resp = client.get("/api/workflows/mode-presets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == len(body["items"]) > 0
        assert all("id" in item for item in body["items"])

    def test_get_single_mode_preset(self, client):
        resp = client.get("/api/workflows/mode-presets/image-gen")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "image-gen"
        assert "workflow" in body

    def test_get_mode_preset_alias_resolves(self, client):
        resp = client.get("/api/workflows/mode-presets/image_gen")
        assert resp.status_code == 200
        assert resp.json()["id"] == "image-gen"

    def test_get_mode_preset_not_found(self, client):
        resp = client.get("/api/workflows/mode-presets/does-not-exist")
        assert resp.status_code == 404


class TestExecutionPolicyEndpoint:
    def test_execution_policy(self, client):
        resp = client.get("/api/workflows/execution-policy")
        assert resp.status_code == 200
        body = resp.json()
        assert "hard_timeout_ms" in body
        assert body["polling_interval_ms"] == wf.WORKFLOW_EXECUTION_CLIENT_POLICY["polling_interval_ms"]


# --------------------------------------------------------------------------- #
# Agent CRUD endpoints
# --------------------------------------------------------------------------- #
class TestAgentCrud:
    def test_create_agent_happy_path(self, client):
        resp = client.post(
            "/api/agents",
            json={
                "name": "My Agent",
                "provider_id": "google",
                "model_id": "gemini-2.5-flash",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "My Agent"
        assert body["status"] == "active"
        assert body["provider_id"] == "google"

    def test_create_agent_empty_name_rejected(self, client):
        resp = client.post(
            "/api/agents",
            json={"name": "   ", "provider_id": "google", "model_id": "x"},
        )
        assert resp.status_code == 400
        assert "name" in resp.json()["detail"].lower()

    def test_create_agent_missing_provider(self, client):
        resp = client.post(
            "/api/agents",
            json={"name": "A", "provider_id": "", "model_id": "x"},
        )
        assert resp.status_code == 400
        assert "providerId" in resp.json()["detail"]

    def test_create_agent_missing_model(self, client):
        resp = client.post(
            "/api/agents",
            json={"name": "A", "provider_id": "google", "model_id": ""},
        )
        assert resp.status_code == 400
        assert "modelId" in resp.json()["detail"]

    def test_create_agent_unsupported_type(self, client):
        resp = client.post(
            "/api/agents",
            json={
                "name": "A",
                "agent_type": "wizard",
                "provider_id": "google",
                "model_id": "x",
            },
        )
        assert resp.status_code == 400
        assert "Unsupported agentType" in resp.json()["detail"]

    def test_create_adk_agent_requires_google_provider(self, client):
        resp = client.post(
            "/api/agents",
            json={
                "name": "A",
                "agent_type": "google-adk",
                "provider_id": "openai",
                "model_id": "gpt-4o",
            },
        )
        assert resp.status_code == 400
        assert "Google provider" in resp.json()["detail"]

    def test_create_agent_duplicate_name_conflict(self, client, db_session):
        _add_agent(db_session, name="Dup")
        resp = client.post(
            "/api/agents",
            json={"name": "Dup", "provider_id": "google", "model_id": "x"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_list_agents_active_only_by_default(self, client, db_session):
        _add_agent(db_session, name="Active1")
        _add_agent(db_session, name="Inactive1", status="inactive")
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        body = resp.json()
        names = {a["name"] for a in body["agents"]}
        assert "Active1" in names
        assert "Inactive1" not in names
        assert body["active_count"] == 1
        assert body["inactive_count"] == 1

    def test_list_agents_include_inactive(self, client, db_session):
        _add_agent(db_session, name="Active1")
        _add_agent(db_session, name="Inactive1", status="inactive")
        resp = client.get("/api/agents?include_inactive=true")
        body = resp.json()
        names = {a["name"] for a in body["agents"]}
        assert {"Active1", "Inactive1"} <= names

    def test_list_agents_search_filter(self, client, db_session):
        _add_agent(db_session, name="Alpha")
        _add_agent(db_session, name="Beta")
        resp = client.get("/api/agents?search=alph")
        body = resp.json()
        assert {a["name"] for a in body["agents"]} == {"Alpha"}
        assert body["search"] == "alph"

    def test_list_agents_status_inactive_filter(self, client, db_session):
        _add_agent(db_session, name="A")
        _add_agent(db_session, name="B", status="inactive")
        resp = client.get("/api/agents?status=inactive")
        body = resp.json()
        assert {a["name"] for a in body["agents"]} == {"B"}
        assert body["status"] == "inactive"

    def test_get_agent_detail(self, client, db_session):
        agent = _add_agent(db_session, name="Detail")
        resp = client.get(f"/api/agents/{agent.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == agent.id

    def test_get_agent_not_found(self, client):
        resp = client.get("/api/agents/nope")
        assert resp.status_code == 404

    def test_get_agent_other_user_scoped_404(self, client, db_session):
        agent = _add_agent(db_session, name="Theirs", user_id=OTHER_USER_ID)
        resp = client.get(f"/api/agents/{agent.id}")
        assert resp.status_code == 404

    def test_update_agent_name(self, client, db_session):
        agent = _add_agent(db_session, name="Old")
        resp = client.put(f"/api/agents/{agent.id}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_update_agent_empty_name_rejected(self, client, db_session):
        agent = _add_agent(db_session, name="Old")
        resp = client.put(f"/api/agents/{agent.id}", json={"name": "  "})
        assert resp.status_code == 400

    def test_update_agent_duplicate_name_conflict(self, client, db_session):
        _add_agent(db_session, name="Taken")
        agent = _add_agent(db_session, name="Mine")
        resp = client.put(f"/api/agents/{agent.id}", json={"name": "Taken"})
        assert resp.status_code == 409

    def test_update_agent_invalid_status(self, client, db_session):
        agent = _add_agent(db_session, name="S")
        resp = client.put(f"/api/agents/{agent.id}", json={"status": "weird"})
        assert resp.status_code == 400
        assert "Invalid status" in resp.json()["detail"]

    def test_update_agent_not_found(self, client):
        resp = client.put("/api/agents/missing", json={"name": "x"})
        assert resp.status_code == 404

    def test_update_agent_adk_requires_google(self, client, db_session):
        agent = _add_agent(db_session, name="ADK", provider_id="google", agent_type="adk")
        resp = client.put(f"/api/agents/{agent.id}", json={"provider_id": "openai"})
        assert resp.status_code == 400
        assert "Google provider" in resp.json()["detail"]

    def test_delete_agent_soft(self, client, db_session):
        agent = _add_agent(db_session, name="ToDelete")
        resp = client.delete(f"/api/agents/{agent.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted_mode"] == "soft"
        db_session.expire_all()
        refreshed = db_session.query(AgentRegistry).filter_by(id=agent.id).first()
        assert refreshed.status == "inactive"

    def test_delete_agent_hard(self, client, db_session):
        agent = _add_agent(db_session, name="ToHardDelete")
        resp = client.delete(f"/api/agents/{agent.id}?hard_delete=true")
        assert resp.status_code == 200
        assert resp.json()["deleted_mode"] == "hard"
        assert db_session.query(AgentRegistry).filter_by(id=agent.id).first() is None

    def test_delete_agent_not_found(self, client):
        resp = client.delete("/api/agents/missing")
        assert resp.status_code == 404

    def test_restore_agent_success(self, client, db_session):
        agent = _add_agent(db_session, name="Gone", status="inactive")
        resp = client.post(f"/api/agents/{agent.id}/restore")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["agent"]["status"] == "active"

    def test_restore_agent_conflict_without_rename(self, client, db_session):
        _add_agent(db_session, name="Clash")
        inactive = _add_agent(db_session, name="Clash", status="inactive")
        resp = client.post(f"/api/agents/{inactive.id}/restore")
        assert resp.status_code == 409

    def test_restore_agent_conflict_with_rename(self, client, db_session):
        _add_agent(db_session, name="Clash")
        inactive = _add_agent(db_session, name="Clash", status="inactive")
        resp = client.post(f"/api/agents/{inactive.id}/restore?rename_on_conflict=true")
        assert resp.status_code == 200
        assert "(restored" in resp.json()["agent"]["name"]

    def test_restore_agent_not_found(self, client):
        resp = client.post("/api/agents/missing/restore")
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Available-models endpoint (exercises _load_provider_models)
# --------------------------------------------------------------------------- #
class TestAvailableModels:
    def _add_profile(self, db, *, provider_id, name, saved_models, api_key="k"):
        now = int(time.time() * 1000)
        # ``saved_models`` is a native JSON column → pass the list directly.
        profile = ConfigProfile(
            id=generate_uuid(),
            user_id=USER_ID,
            name=name,
            provider_id=provider_id,
            api_key=api_key,
            protocol="openai" if provider_id == "openai" else "google",
            saved_models=saved_models if saved_models is not None else [],
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
        db.commit()
        return profile

    def test_available_models_empty(self, client):
        resp = client.get("/api/agents/available-models")
        assert resp.status_code == 200
        body = resp.json()
        assert body["providers"] == []
        assert "selection_policy" in body

    def test_available_models_with_saved_models(self, client, db_session):
        self._add_profile(
            db_session,
            provider_id="google",
            name="Google",
            saved_models=[
                {"id": "gemini-2.5-flash", "name": "Flash"},
                {"id": "imagen-3.0-generate-002", "name": "Imagen"},
            ],
        )
        resp = client.get("/api/agents/available-models")
        body = resp.json()
        assert len(body["providers"]) == 1
        provider = body["providers"][0]
        assert provider["provider_id"] == "google"
        # chat-capable gemini classified into chat models; imagen into image-gen
        chat_ids = {m["id"] for m in provider["models"]}
        assert "gemini-2.5-flash" in chat_ids
        image_gen_ids = {m["id"] for m in provider["image_generation_models"]}
        assert "imagen-3.0-generate-002" in image_gen_ids

    def test_available_models_profile_without_key_skipped(self, client, db_session):
        self._add_profile(
            db_session,
            provider_id="google",
            name="NoKey",
            saved_models=[{"id": "gemini-2.5-flash"}],
            api_key="",
        )
        resp = client.get("/api/agents/available-models")
        assert resp.json()["providers"] == []

    def test_available_models_falls_back_to_defaults(self, client, db_session):
        # Profile has a key but no saved_models → default models for provider.
        self._add_profile(
            db_session, provider_id="openai", name="OpenAI", saved_models=[]
        )
        resp = client.get("/api/agents/available-models")
        providers = resp.json()["providers"]
        assert len(providers) == 1
        all_ids = {m["id"] for m in providers[0]["all_models"]}
        assert "gpt-4o" in all_ids  # from default_models_for_provider


# --------------------------------------------------------------------------- #
# Workflow history endpoints
# --------------------------------------------------------------------------- #
class TestWorkflowHistory:
    def test_history_empty(self, client):
        resp = client.get("/api/workflows/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["executions"] == []
        assert body["total"] == 0
        assert body["limit"] == 20

    def test_history_lists_and_paginates(self, client, db_session):
        for i in range(3):
            _add_execution(db_session, input_payload={"task": f"task-{i}"})
        resp = client.get("/api/workflows/history?limit=2&offset=0")
        body = resp.json()
        assert body["total"] == 3
        assert body["count"] == 2
        assert body["limit"] == 2

    def test_history_limit_clamped_to_max(self, client):
        resp = client.get("/api/workflows/history?limit=9999")
        assert resp.json()["limit"] == 100

    def test_history_limit_clamped_to_min(self, client):
        resp = client.get("/api/workflows/history?limit=0")
        assert resp.json()["limit"] == 1

    def test_history_negative_offset_clamped(self, client):
        resp = client.get("/api/workflows/history?offset=-5")
        assert resp.json()["offset"] == 0

    def test_history_status_filter(self, client, db_session):
        _add_execution(db_session, status="completed")
        _add_execution(db_session, status="failed", error="boom")
        resp = client.get("/api/workflows/history?status=failed")
        body = resp.json()
        assert body["total"] == 1
        assert body["executions"][0]["status"] == "failed"

    def test_history_user_scoped(self, client, db_session):
        _add_execution(db_session, user_id=OTHER_USER_ID)
        resp = client.get("/api/workflows/history")
        assert resp.json()["total"] == 0

    def test_history_detail(self, client, db_session):
        execution = _add_execution(
            db_session,
            result={"text": "final"},
            input_payload={"task": "analyze"},
        )
        # node row to exercise node summary path
        db_session.add(
            NodeExecution(
                id=generate_uuid(),
                execution_id=execution.id,
                node_id="n1",
                node_type="start",
                status="completed",
                output_json=json.dumps({"text": "ok"}),
                started_at=execution.started_at,
                completed_at=execution.started_at + 10,
            )
        )
        db_session.commit()
        resp = client.get(f"/api/workflows/history/{execution.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == execution.id
        assert body["task"] == "analyze"
        assert body["node_summary"]["completed"] == 1
        assert len(body["node_executions"]) == 1

    def test_history_detail_not_found(self, client):
        resp = client.get("/api/workflows/history/missing")
        assert resp.status_code == 404

    def test_history_detail_other_user_404(self, client, db_session):
        execution = _add_execution(db_session, user_id=OTHER_USER_ID)
        resp = client.get(f"/api/workflows/history/{execution.id}")
        assert resp.status_code == 404

    def test_history_analysis_download_build_error_is_generic(
        self, client, db_session, monkeypatch, caplog
    ):
        secret = "workflow-analysis-download-secret"
        execution = _add_execution(db_session, status="completed", result={"text": "final"})

        def _boom(*args, **kwargs):
            raise RuntimeError(f"workbook failed {secret}")

        monkeypatch.setattr(wf, "_build_workflow_analysis_excel_bytes", _boom)
        with caplog.at_level(logging.ERROR, logger=wf.logger.name):
            resp = client.get(
                f"/api/workflows/history/{execution.id}/analysis/download"
            )

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Workflow analysis workbook generation failed"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_delete_history(self, client, db_session):
        execution = _add_execution(db_session, status="completed")
        resp = client.delete(f"/api/workflows/history/{execution.id}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert db_session.query(WorkflowExecution).filter_by(id=execution.id).first() is None

    def test_delete_running_history_conflict(self, client, db_session):
        execution = _add_execution(db_session, status="running")
        resp = client.delete(f"/api/workflows/history/{execution.id}")
        assert resp.status_code == 409

    def test_delete_history_not_found(self, client):
        resp = client.delete("/api/workflows/history/missing")
        assert resp.status_code == 404

    def test_clear_all_history(self, client, db_session):
        _add_execution(db_session, status="completed")
        _add_execution(db_session, status="failed")
        resp = client.delete("/api/workflows/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["execution_deleted_count"] == 2
        assert db_session.query(WorkflowExecution).count() == 0


# --------------------------------------------------------------------------- #
# State / status snapshot endpoints
# --------------------------------------------------------------------------- #
class TestStateEndpoints:
    def test_get_state_snapshot(self, client, db_session):
        execution = _add_execution(db_session, status="completed", result={"text": "done"})
        resp = client.get(f"/api/workflows/{execution.id}/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["isTerminal"] is True
        assert body["finalStatus"] == "completed"
        assert "clientPolicy" in body

    def test_get_state_not_found(self, client):
        resp = client.get("/api/workflows/missing/state")
        assert resp.status_code == 404

    def test_get_state_other_user_404(self, client, db_session):
        execution = _add_execution(db_session, user_id=OTHER_USER_ID)
        resp = client.get(f"/api/workflows/{execution.id}/state")
        assert resp.status_code == 404

    def test_debug_execution_state_runtime(self, client, db_session):
        execution = _add_execution(db_session, status="running")
        resp = client.get(
            f"/api/workflows/{execution.id}/debug/execution-state-runtime"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["execution_id"] == execution.id
        assert "execution_state_runtime" in body

    def test_debug_execution_state_runtime_not_found(self, client):
        resp = client.get("/api/workflows/missing/debug/execution-state-runtime")
        assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Pause / resume / cancel endpoints
# --------------------------------------------------------------------------- #
class TestPauseResumeCancel:
    def test_pause_running_requests_pause(self, client, db_session):
        execution = _add_execution(db_session, status="running")
        resp = client.post(f"/api/workflows/history/{execution.id}/pause")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pause_requested"
        assert body["pause_requested"] is True

    def test_pause_terminal_execution_noop(self, client, db_session):
        execution = _add_execution(db_session, status="completed")
        resp = client.post(f"/api/workflows/history/{execution.id}/pause")
        body = resp.json()
        assert body["already_terminal"] is True
        assert body["status"] == "completed"

    def test_pause_pending_execution_conflict(self, client, db_session):
        execution = _add_execution(db_session, status="pending")
        resp = client.post(f"/api/workflows/history/{execution.id}/pause")
        assert resp.status_code == 409

    def test_pause_not_found(self, client):
        resp = client.post("/api/workflows/history/missing/pause")
        assert resp.status_code == 404

    def test_cancel_running_transitions(self, client, db_session):
        execution = _add_execution(db_session, status="running")
        resp = client.post(f"/api/workflows/history/{execution.id}/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["cancel_transitioned"] is True

    def test_cancel_terminal_noop(self, client, db_session):
        execution = _add_execution(db_session, status="failed", error="x")
        resp = client.post(f"/api/workflows/history/{execution.id}/cancel")
        body = resp.json()
        assert body["already_terminal"] is True

    def test_cancel_not_found(self, client):
        resp = client.post("/api/workflows/history/missing/cancel")
        assert resp.status_code == 404

    def test_resume_terminal_noop(self, client, db_session):
        execution = _add_execution(db_session, status="completed")
        resp = client.post(f"/api/workflows/history/{execution.id}/resume")
        body = resp.json()
        assert body["already_terminal"] is True

    def test_resume_non_paused_conflict(self, client, db_session):
        execution = _add_execution(db_session, status="pending")
        resp = client.post(f"/api/workflows/history/{execution.id}/resume")
        assert resp.status_code == 409

    def test_resume_not_found(self, client):
        resp = client.post("/api/workflows/history/missing/resume")
        assert resp.status_code == 404

    def test_resume_paused_restarts(self, client, db_session, monkeypatch):
        # A paused execution with a valid checkpoint should restart in background.
        execution = _add_execution(db_session, status="paused")

        # Avoid actually running the engine: stub the background runner.
        async def _fake_bg(**kwargs):
            return None

        monkeypatch.setattr(wf, "_run_workflow_in_background", _fake_bg)
        monkeypatch.setattr(wf, "validate_workflow_agent_bindings", lambda **k: None)
        resp = client.post(f"/api/workflows/history/{execution.id}/resume")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["resume_strategy"] == "restart"


# --------------------------------------------------------------------------- #
# Reset / rebuild endpoints (template service is real; uses in-mem DB)
# --------------------------------------------------------------------------- #
class TestRebuildReset:
    def test_rebuild_templates_no_recreate(self, client, db_session):
        now = int(time.time() * 1000)
        db_session.add(
            WorkflowTemplate(
                id=generate_uuid(),
                user_id=USER_ID,
                name="T1",
                description="",
                category="general",
                workflow_type="graph",
                config_json=json.dumps({"nodes": [], "edges": []}),
                created_at=now,
                updated_at=now,
            )
        )
        db_session.commit()
        resp = client.post(
            "/api/workflows/templates/rebuild", json={"recreate_starters": False}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted_count"] == 1
        assert body["created_count"] == 0
        assert db_session.query(WorkflowTemplate).count() == 0


# --------------------------------------------------------------------------- #
# Execute endpoint (engine boundary mocked)
# --------------------------------------------------------------------------- #
class TestExecuteEndpoint:
    def _valid_payload(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {"id": "start-1", "type": "start", "data": {"type": "start"}},
                {"id": "end-1", "type": "end", "data": {"type": "end"}},
            ],
            "edges": [{"id": "e1", "source": "start-1", "target": "end-1"}],
            "input": {"task": "hello"},
        }

    def test_execute_invalid_payload_rejected(self, client):
        resp = client.post(
            "/api/workflows/execute",
            json={"nodes": [], "edges": []},
        )
        assert resp.status_code == 400

    def test_execute_non_graph_validation_errors_remain_422(self, client):
        resp = client.post(
            "/api/workflows/execute",
            json={"nodes": [{"id": "start-1"}]},
        )
        assert resp.status_code == 422

    def test_execute_sync_happy_path(self, client, db_session, monkeypatch):
        captured: Dict[str, Any] = {}

        async def fake_execute(self, *, nodes, edges, initial_input, on_event):
            captured["nodes"] = nodes
            return {"text": "engine output", "runtime": "adapter"}

        # Patch the engine's execute (external boundary) and image/media persist.
        from app.services.agent.workflow_engine import WorkflowEngine

        monkeypatch.setattr(WorkflowEngine, "execute", fake_execute)

        async def _passthrough_images(*, db, execution_id, user_id, result_payload):
            return result_payload, {}

        async def _passthrough_media(*, db, execution_id, user_id, result_payload, media_kind):
            return result_payload, {}

        monkeypatch.setattr(wf, "_persist_workflow_result_images", _passthrough_images)
        monkeypatch.setattr(wf, "_persist_workflow_result_media", _passthrough_media)

        resp = client.post("/api/workflows/execute", json=self._valid_payload())
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Execution record persisted + a terminal status returned.
        assert "execution_id" in body or "executionId" in body
        assert captured["nodes"]  # engine actually invoked with normalized nodes

    def test_execute_engine_failure_maps_to_500(self, client, monkeypatch, caplog):
        secret = "workflow-engine-secret"

        class FakeRuntimeStore:
            async def initialize_execution_local(self, *args, **kwargs):
                return None

            async def initialize_execution(self, *args, **kwargs):
                return None

            async def mark_done(self, *args, **kwargs):
                return None

            async def clear(self, *args, **kwargs):
                return None

        async def boom(self, *, nodes, edges, initial_input, on_event):
            raise RuntimeError(f"engine exploded {secret}")

        from app.services.agent.workflow_engine import WorkflowEngine

        monkeypatch.setattr(WorkflowEngine, "execute", boom)
        monkeypatch.setattr(wf, "_workflow_runtime_store", FakeRuntimeStore())
        monkeypatch.setattr(
            wf,
            "_schedule_runtime_store_sync",
            lambda awaitable, **kwargs: getattr(awaitable, "close", lambda: None)(),
        )
        with caplog.at_level(logging.ERROR, logger=wf.logger.name):
            resp = client.post("/api/workflows/execute", json=self._valid_payload())

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert detail["code"] == "workflow_execution_failed"
        assert detail["message"] == "Workflow execution failed"
        workflow_log_text = _workflow_log_text(caplog)
        assert secret not in resp.text
        assert secret not in workflow_log_text
        assert "Traceback" not in workflow_log_text
        assert "<redacted error; length=" in workflow_log_text

    def test_execute_idempotency_replay(self, client, db_session, monkeypatch):
        # Pre-create a terminal execution carrying the idempotency key; a second
        # request with the same key must replay it instead of re-running.
        key = "idem-123"
        existing = _add_execution(
            db_session,
            status="completed",
            result={"text": "cached"},
            idempotency_key=key,
        )

        payload = self._valid_payload()
        payload["meta"] = {"idempotencyKey": key}

        # Engine must NOT be called on replay.
        from app.services.agent.workflow_engine import WorkflowEngine

        async def must_not_run(self, **kwargs):
            raise AssertionError("engine should not run on idempotent replay")

        monkeypatch.setattr(WorkflowEngine, "execute", must_not_run)

        resp = client.post("/api/workflows/execute", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("idempotency_replay") is True
        assert body["execution_id"] == existing.id


# --------------------------------------------------------------------------- #
# Media / result-summary helpers (no DB)
# --------------------------------------------------------------------------- #
class TestMediaAndSummaryHelpers:
    def test_extract_media_urls_unknown_kind(self):
        assert wf._extract_workflow_output_media_urls({"finalOutput": {}}, "bogus") == []

    def test_extract_image_urls_from_final_output(self):
        payload = {
            "finalOutput": {"imageUrl": "https://cdn.example.com/a.png"},
            "finalNodeId": "tool-1",
        }
        urls = wf._extract_workflow_output_media_urls(payload, "image")
        assert "https://cdn.example.com/a.png" in urls

    def test_build_workflow_result_summary_none(self):
        summary = wf._build_workflow_result_summary(None)
        assert summary["has_result"] is False
        assert summary["image_count"] == 0
        assert summary["video_count"] == 0

    def test_build_workflow_result_summary_with_image(self):
        payload = {
            "finalOutput": {"imageUrl": "https://cdn.example.com/x.png"},
            "finalNodeId": "tool-1",
        }
        summary = wf._build_workflow_result_summary(payload)
        assert summary["has_result"] is True
        assert summary["image_count"] >= 1
        # Non-data URLs are surfaced in image_urls.
        assert "https://cdn.example.com/x.png" in summary["image_urls"]

    def test_result_summary_excludes_inline_data_urls(self):
        inline = "data:image/png;base64,AAAA"
        payload = {"finalOutput": {"imageUrl": inline}, "finalNodeId": "tool-1"}
        summary = wf._build_workflow_result_summary(payload)
        # counted but not surfaced as a downloadable URL
        assert summary["image_count"] >= 1
        assert inline not in summary["image_urls"]


# --------------------------------------------------------------------------- #
# Workflow template CRUD endpoints (real WorkflowTemplateService + in-mem DB)
# --------------------------------------------------------------------------- #
def _template_config() -> Dict[str, Any]:
    return {
        "nodes": [
            {"id": "start-1", "type": "start", "data": {"type": "start"}},
            {"id": "end-1", "type": "end", "data": {"type": "end"}},
        ],
        "edges": [{"id": "e1", "source": "start-1", "target": "end-1"}],
    }


class TestWorkflowTemplates:
    def test_create_template_happy_path(self, client):
        resp = client.post(
            "/api/workflows/templates",
            json={
                "name": "Tmpl One",
                "category": "general",
                "config": _template_config(),
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Tmpl One"
        assert body["id"]

    def test_create_template_invalid_config_400(self, client):
        resp = client.post(
            "/api/workflows/templates",
            json={"name": "Bad", "category": "general", "config": {"nodes": [], "edges": []}},
        )
        assert resp.status_code == 400

    def test_create_template_duplicate_name_409(self, client):
        payload = {"name": "Dup Tmpl", "category": "general", "config": _template_config()}
        first = client.post("/api/workflows/templates", json=payload)
        assert first.status_code == 200
        second = client.post("/api/workflows/templates", json=payload)
        assert second.status_code == 409

    def test_list_templates(self, client):
        client.post(
            "/api/workflows/templates",
            json={"name": "Listed", "category": "general", "config": _template_config()},
        )
        resp = client.get("/api/workflows/templates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
        assert any(t["name"] == "Listed" for t in body["templates"])

    def test_get_template_detail_and_not_found(self, client):
        created = client.post(
            "/api/workflows/templates",
            json={"name": "Detail", "category": "general", "config": _template_config()},
        ).json()
        resp = client.get(f"/api/workflows/templates/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

        missing = client.get("/api/workflows/templates/nope")
        assert missing.status_code == 404

    def test_update_template(self, client):
        created = client.post(
            "/api/workflows/templates",
            json={"name": "ToUpdate", "category": "general", "config": _template_config()},
        ).json()
        resp = client.put(
            f"/api/workflows/templates/{created['id']}",
            json={"description": "updated desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated desc"

    def test_update_template_not_found(self, client):
        resp = client.put(
            "/api/workflows/templates/missing", json={"description": "x"}
        )
        assert resp.status_code == 404

    def test_copy_template(self, client):
        created = client.post(
            "/api/workflows/templates",
            json={"name": "Original", "category": "general", "config": _template_config()},
        ).json()
        resp = client.post(
            f"/api/workflows/templates/{created['id']}/copy",
            json={"name": "Copied"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Copied"

    def test_copy_template_not_found(self, client):
        resp = client.post("/api/workflows/templates/missing/copy", json={})
        assert resp.status_code == 404

    def test_delete_template(self, client):
        created = client.post(
            "/api/workflows/templates",
            json={"name": "ToDelete", "category": "general", "config": _template_config()},
        ).json()
        resp = client.delete(f"/api/workflows/templates/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # subsequent fetch is 404
        assert client.get(f"/api/workflows/templates/{created['id']}").status_code == 404

    def test_delete_template_not_found(self, client):
        resp = client.delete("/api/workflows/templates/missing")
        assert resp.status_code == 404

    def test_template_categories_list(self, client):
        resp = client.get("/api/workflows/template-categories")
        assert resp.status_code == 200
        body = resp.json()
        assert "categories" in body
        assert body["count"] == len(body["categories"])

    def test_create_template_category(self, client):
        resp = client.post(
            "/api/workflows/template-categories", json={"name": "MyCategory"}
        )
        assert resp.status_code == 200
        # duplicate → 409
        dup = client.post(
            "/api/workflows/template-categories", json={"name": "MyCategory"}
        )
        assert dup.status_code == 409

    def test_template_coverage_report(self, client):
        client.post(
            "/api/workflows/templates",
            json={"name": "Cov", "category": "general", "config": _template_config()},
        )
        resp = client.get("/api/workflows/templates/coverage")
        assert resp.status_code == 200
        body = resp.json()
        assert "coverage" in body
        assert body["templates"]["count"] >= 1
