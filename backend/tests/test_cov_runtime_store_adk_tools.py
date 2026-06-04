"""Coverage-focused genuine tests for:

- app.services.agent.workflow_runtime_store  (Local/Redis/Unified store CRUD + state merge + payloads)
- app.services.agent.adk_builtin_tools        (sheet stage protocol helpers + sheet_analyze dispatch)

Strategy:
- workflow_runtime_store: LocalWorkflowRuntimeStore is exercised directly (real in-process logic,
  no external boundary). RedisWorkflowRuntimeStore is exercised against an in-memory fake async
  redis client (mock only the redis boundary, never the store logic). WorkflowRuntimeStore is
  exercised over real local + (fake-redis | None) sub-stores to validate the merge/fallback policy.
- adk_builtin_tools: pure protocol/validation helpers are tested against real behavior; the
  sheet_analyze tool dispatch is tested by patching ONLY the external table-analysis module
  boundary (_load_table_analysis_module) and the network download boundary, asserting the
  real branching/normalization/precheck logic of the tool itself.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

import pytest

from app.services.agent import adk_builtin_tools as adk
from app.services.agent import workflow_runtime_store as store_mod
from app.services.agent.workflow_runtime_store import (
    LocalWorkflowRuntimeStore,
    RedisWorkflowRuntimeStore,
    WorkflowRuntimeState,
    WorkflowRuntimeStore,
    _decode_bool,
    _decode_int,
    _decode_json_dict,
    _decode_text,
    _extract_payload_updated_at,
    _is_empty_state,
    _lookup,
    _merge_runtime_states,
    create_workflow_runtime_store,
)


# ---------------------------------------------------------------------------
# In-memory fake async redis (the ONLY mocked boundary for the redis store).
# Mirrors the subset of the redis API the store uses: hset/expire/hgetall/get/
# set/delete/ping.
# ---------------------------------------------------------------------------
class FakeAsyncRedis:
    def __init__(self) -> None:
        self.hashes: Dict[str, Dict[str, str]] = {}
        self.strings: Dict[str, str] = {}
        self.expired: Dict[str, int] = {}
        self.ping_calls = 0

    async def ping(self) -> bool:
        self.ping_calls += 1
        return True

    async def hset(self, key: str, mapping: Dict[str, str]) -> int:
        bucket = self.hashes.setdefault(key, {})
        bucket.update({str(k): str(v) for k, v in mapping.items()})
        return len(mapping)

    async def expire(self, key: str, ttl: int) -> bool:
        self.expired[key] = ttl
        return True

    async def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def get(self, key: str) -> Optional[str]:
        return self.strings.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self.strings[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.hashes:
                del self.hashes[key]
                removed += 1
            if key in self.strings:
                del self.strings[key]
                removed += 1
        return removed


class BrokenAsyncRedis(FakeAsyncRedis):
    """Raises on every data op to exercise the store's exception/fallback paths."""

    async def hset(self, *_a: Any, **_k: Any) -> int:
        raise RuntimeError("boom-hset")

    async def hgetall(self, *_a: Any, **_k: Any) -> Dict[str, str]:
        raise RuntimeError("boom-hgetall")

    async def get(self, *_a: Any, **_k: Any) -> Optional[str]:
        raise RuntimeError("boom-get")

    async def set(self, *_a: Any, **_k: Any) -> bool:
        raise RuntimeError("boom-set")

    async def delete(self, *_a: Any, **_k: Any) -> int:
        raise RuntimeError("boom-delete")


def _redis_store(client: Any) -> RedisWorkflowRuntimeStore:
    # Inject a concrete client so _ensure_redis short-circuits to it (no pool/network).
    return RedisWorkflowRuntimeStore(redis_client=client, key_prefix="test:rt")


# ===========================================================================
# Module-level decode/util helpers
# ===========================================================================
def test_decode_text_handles_bytes_none_and_str():
    assert _decode_text(b"hello") == "hello"
    assert _decode_text(None) == ""
    assert _decode_text(123) == "123"


def test_decode_bool_truthy_and_falsey_variants():
    for truthy in ("1", "true", "YES", b"on", "y"):
        assert _decode_bool(truthy) is True
    for falsey in ("0", "false", "", "no", None):
        assert _decode_bool(falsey) is False


def test_decode_int_parses_floats_and_falls_back_to_zero():
    assert _decode_int("42") == 42
    assert _decode_int("3.9") == 3
    assert _decode_int("") == 0
    assert _decode_int("not-a-number") == 0
    assert _decode_int(b"7") == 7


def test_decode_json_dict_only_returns_dicts():
    assert _decode_json_dict('{"a": 1}') == {"a": 1}
    assert _decode_json_dict("[1, 2]") is None  # valid json but not a dict
    assert _decode_json_dict("not json") is None
    assert _decode_json_dict("") is None


def test_lookup_finds_str_or_bytes_key():
    raw = {b"done": b"1", "updated_at": "5"}
    assert _lookup(raw, "done") == b"1"
    assert _lookup(raw, "updated_at") == "5"
    assert _lookup(raw, "missing") is None


def test_extract_payload_updated_at_reads_marker_field():
    payload = {store_mod._RUNTIME_PAYLOAD_UPDATED_AT_FIELD: "99"}
    assert _extract_payload_updated_at(payload) == 99
    assert _extract_payload_updated_at(None) == 0
    assert _extract_payload_updated_at({}) == 0


# ===========================================================================
# State merge policy
# ===========================================================================
def test_is_empty_state_distinguishes_default_from_active():
    assert _is_empty_state(WorkflowRuntimeState()) is True
    assert _is_empty_state(WorkflowRuntimeState(cancel_requested=True)) is False
    assert _is_empty_state(WorkflowRuntimeState(updated_at=5)) is False


def test_merge_prefers_nonempty_local_when_redis_empty():
    local = WorkflowRuntimeState(pause_requested=True, updated_at=10)
    redis = WorkflowRuntimeState()  # empty
    assert _merge_runtime_states(local, redis) is local


def test_merge_prefers_nonempty_redis_when_local_empty():
    local = WorkflowRuntimeState()  # empty
    redis = WorkflowRuntimeState(cancel_requested=True, updated_at=10)
    assert _merge_runtime_states(local, redis) is redis


def test_merge_prefers_newer_updated_at():
    older = WorkflowRuntimeState(done=True, updated_at=10)
    newer = WorkflowRuntimeState(paused=True, updated_at=20)
    assert _merge_runtime_states(older, newer) is newer
    assert _merge_runtime_states(newer, older) is newer


def test_merge_equal_timestamps_ors_flags_and_keeps_redis_checkpoint():
    local = WorkflowRuntimeState(done=True, cancel_requested=True, updated_at=5, checkpoint={"l": 1})
    redis = WorkflowRuntimeState(paused=True, pause_requested=True, updated_at=5, checkpoint={"r": 2})
    merged = _merge_runtime_states(local, redis)
    assert merged.done is True
    assert merged.cancel_requested is True
    assert merged.paused is True
    assert merged.pause_requested is True
    assert merged.checkpoint == {"r": 2}  # redis checkpoint wins when present
    assert merged.updated_at == 5


def test_merge_equal_timestamps_falls_back_to_local_checkpoint():
    local = WorkflowRuntimeState(updated_at=5, checkpoint={"l": 1})
    redis = WorkflowRuntimeState(done=True, updated_at=5, checkpoint=None)
    merged = _merge_runtime_states(local, redis)
    assert merged.checkpoint == {"l": 1}


# ===========================================================================
# LocalWorkflowRuntimeStore — real in-process CRUD + state transitions
# ===========================================================================
@pytest.fixture
def local_store() -> LocalWorkflowRuntimeStore:
    return LocalWorkflowRuntimeStore(shared_state={}, shared_payload_state={})


async def test_local_get_state_defaults_to_empty(local_store: LocalWorkflowRuntimeStore):
    state = await local_store.get_state("missing")
    assert state == WorkflowRuntimeState()


async def test_local_initialize_and_touch(local_store: LocalWorkflowRuntimeStore):
    init = await local_store.initialize_execution("e1", updated_at=100)
    assert init.updated_at == 100
    assert init.done is False and init.cancel_requested is False
    touched = await local_store.touch("e1", updated_at=200)
    assert touched.updated_at == 200
    # touch preserves other fields
    assert touched.done is False


async def test_local_touch_on_unknown_creates_baseline(local_store: LocalWorkflowRuntimeStore):
    touched = await local_store.touch("ghost", updated_at=7)
    assert touched.updated_at == 7
    assert touched.cancel_requested is False


async def test_local_request_cancel_sets_flag(local_store: LocalWorkflowRuntimeStore):
    state = await local_store.request_cancel("e1", updated_at=10)
    assert state.cancel_requested is True
    assert state.updated_at == 10


async def test_local_pause_then_mark_paused_then_running_lifecycle(local_store: LocalWorkflowRuntimeStore):
    paused_req = await local_store.request_pause("e1", updated_at=1)
    assert paused_req.pause_requested is True
    assert paused_req.paused is False

    marked = await local_store.mark_paused("e1", paused=True, checkpoint={"step": 3}, updated_at=2)
    assert marked.paused is True
    assert marked.pause_requested is False  # cleared on mark_paused
    assert marked.checkpoint == {"step": 3}

    # mark_paused without checkpoint preserves the previous checkpoint
    again = await local_store.mark_paused("e1", paused=True, updated_at=3)
    assert again.checkpoint == {"step": 3}

    running = await local_store.mark_running("e1", clear_checkpoint=True, updated_at=4)
    assert running.paused is False
    assert running.pause_requested is False
    assert running.cancel_requested is False
    assert running.checkpoint is None


async def test_local_mark_running_can_keep_checkpoint(local_store: LocalWorkflowRuntimeStore):
    await local_store.mark_paused("e1", paused=True, checkpoint={"k": 1}, updated_at=1)
    running = await local_store.mark_running("e1", clear_checkpoint=False, updated_at=2)
    assert running.checkpoint == {"k": 1}


async def test_local_mark_done_preserves_flags(local_store: LocalWorkflowRuntimeStore):
    await local_store.request_cancel("e1", updated_at=1)
    done = await local_store.mark_done("e1", done=True, updated_at=2)
    assert done.done is True
    assert done.cancel_requested is True  # preserved


async def test_local_clear_removes_state(local_store: LocalWorkflowRuntimeStore):
    await local_store.initialize_execution("e1", updated_at=1)
    await local_store.clear("e1")
    assert await local_store.get_state("e1") == WorkflowRuntimeState()


async def test_local_payload_put_get_delete_roundtrip(local_store: LocalWorkflowRuntimeStore):
    stored = await local_store.put_payload("pk", {"a": 1}, updated_at=55)
    assert stored is not None
    assert stored["a"] == 1
    assert stored[store_mod._RUNTIME_PAYLOAD_UPDATED_AT_FIELD] == 55

    fetched = await local_store.get_payload("pk")
    assert fetched["a"] == 1
    # returned values are clones; mutating one must not affect the store
    fetched["a"] = 999
    refetched = await local_store.get_payload("pk")
    assert refetched["a"] == 1

    await local_store.delete_payload("pk")
    assert await local_store.get_payload("pk") is None


async def test_local_payload_blank_key_handling(local_store: LocalWorkflowRuntimeStore):
    assert await local_store.get_payload("   ") is None
    with pytest.raises(ValueError):
        await local_store.put_payload("  ", {"a": 1})
    # delete with blank key is a no-op (no raise)
    await local_store.delete_payload("")


async def test_local_default_ttlcache_construction_when_no_shared_state():
    # exercise the TTLCache construction branch (no shared containers provided)
    s = LocalWorkflowRuntimeStore()
    await s.initialize_execution("x", updated_at=1)
    assert (await s.get_state("x")).updated_at == 1


# ===========================================================================
# RedisWorkflowRuntimeStore — over the in-memory fake redis boundary
# ===========================================================================
async def test_redis_initialize_writes_and_decodes_state():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    state = await store.initialize_execution("e1", updated_at=100)
    assert state is not None
    assert state.done is False
    assert state.updated_at == 100
    # expire is set on the namespaced key
    assert fake.expired["test:rt:e1"] == store._ttl_seconds


async def test_redis_full_state_lifecycle():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    await store.initialize_execution("e1", updated_at=1)

    cancel = await store.request_cancel("e1", updated_at=2)
    assert cancel.cancel_requested is True

    pause = await store.request_pause("e1", updated_at=3)
    assert pause.pause_requested is True

    paused = await store.mark_paused("e1", paused=True, checkpoint={"s": 9}, updated_at=4)
    assert paused.paused is True
    assert paused.pause_requested is False
    assert paused.checkpoint == {"s": 9}

    running = await store.mark_running("e1", clear_checkpoint=True, updated_at=5)
    assert running.paused is False
    assert running.checkpoint is None

    done = await store.mark_done("e1", done=True, updated_at=6)
    assert done.done is True

    touched = await store.touch("e1", updated_at=7)
    assert touched.updated_at == 7

    got = await store.get_state("e1")
    assert got.done is True


async def test_redis_mark_paused_with_non_serializable_checkpoint_stores_empty():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    await store.initialize_execution("e1", updated_at=1)
    # set is non-serializable for json -> checkpoint_json becomes "" -> decoded checkpoint None
    paused = await store.mark_paused("e1", paused=True, checkpoint={"bad": {1, 2}}, updated_at=2)
    assert paused.checkpoint is None


async def test_redis_clear_deletes_key():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    await store.initialize_execution("e1", updated_at=1)
    assert "test:rt:e1" in fake.hashes
    assert await store.clear("e1") is True
    assert "test:rt:e1" not in fake.hashes


async def test_redis_payload_roundtrip_and_delete():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    stored = await store.put_payload("pk", {"a": 1}, updated_at=42)
    assert stored["a"] == 1
    assert stored[store_mod._RUNTIME_PAYLOAD_UPDATED_AT_FIELD] == 42

    got = await store.get_payload("pk")
    assert got["a"] == 1

    assert await store.delete_payload("pk") is True
    assert await store.get_payload("pk") is None


async def test_redis_payload_blank_key_paths():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    assert await store.get_payload("") is None
    assert await store.delete_payload("") is False
    with pytest.raises(ValueError):
        await store.put_payload("   ", {"a": 1})


async def test_redis_put_payload_non_serializable_raises_value_error():
    fake = FakeAsyncRedis()
    store = _redis_store(fake)
    with pytest.raises(ValueError):
        await store.put_payload("pk", {"bad": {1, 2}})  # set is not json serializable


async def test_redis_disabled_when_no_client_and_no_pool(monkeypatch):
    # Force GlobalRedisConnectionPool import to fail so the store has no backend.
    import app.services.common.redis_queue_service as rqs

    class _NoPool:
        @staticmethod
        def get_instance():
            raise RuntimeError("no pool")

    monkeypatch.setattr(rqs, "GlobalRedisConnectionPool", _NoPool)
    store = RedisWorkflowRuntimeStore(key_prefix="test:rt")
    assert store._pool is None
    # Every op returns the "redis unavailable" sentinel.
    assert await store.get_state("e1") is None
    assert await store.initialize_execution("e1") is None
    assert await store.touch("e1") is None
    assert await store.clear("e1") is False
    assert await store.get_payload("pk") is None
    assert await store.delete_payload("pk") is False


async def test_redis_exceptions_return_fallback_sentinels_and_drop_client():
    broken = BrokenAsyncRedis()
    store = _redis_store(broken)
    # write path swallows exception -> None and resets the cached client
    assert await store.initialize_execution("e1", updated_at=1) is None
    assert store._redis is None

    store2 = _redis_store(BrokenAsyncRedis())
    assert await store2.get_state("e1") is None
    assert store2._redis is None

    store3 = _redis_store(BrokenAsyncRedis())
    assert await store3.clear("e1") is False

    store4 = _redis_store(BrokenAsyncRedis())
    assert await store4.get_payload("pk") is None

    store5 = _redis_store(BrokenAsyncRedis())
    assert await store5.delete_payload("pk") is False


async def test_redis_hgetall_non_dict_returns_default_state():
    class WeirdRedis(FakeAsyncRedis):
        async def hgetall(self, *_a: Any, **_k: Any):
            return ["not", "a", "dict"]

    store = _redis_store(WeirdRedis())
    state = await store.get_state("e1")
    assert state == WorkflowRuntimeState()


# ===========================================================================
# WorkflowRuntimeStore — unified store merge + fallback over real sub-stores
# ===========================================================================
def _unified_with_fake_redis() -> tuple[WorkflowRuntimeStore, FakeAsyncRedis]:
    fake = FakeAsyncRedis()
    redis_store = _redis_store(fake)
    local_store = LocalWorkflowRuntimeStore(shared_state={}, shared_payload_state={})
    return WorkflowRuntimeStore(redis_store=redis_store, local_store=local_store), fake


async def test_unified_initialize_writes_both_and_returns_redis():
    unified, fake = _unified_with_fake_redis()
    state = await unified.initialize_execution("e1", updated_at=100)
    assert state.updated_at == 100
    assert "test:rt:e1" in fake.hashes  # redis written


async def test_unified_falls_back_to_local_when_redis_unavailable():
    # local-only unified: redis store has neither client nor pool.
    local_store = LocalWorkflowRuntimeStore(shared_state={}, shared_payload_state={})

    class _DeadRedisStore(RedisWorkflowRuntimeStore):
        async def _ensure_redis(self):  # type: ignore[override]
            return None

    dead = _DeadRedisStore(key_prefix="test:rt")
    unified = WorkflowRuntimeStore(redis_store=dead, local_store=local_store)

    init = await unified.initialize_execution("e1", updated_at=50)
    assert init.updated_at == 50  # local value used
    cancel = await unified.request_cancel("e1", updated_at=60)
    assert cancel.cancel_requested is True
    assert await unified.is_cancel_requested("e1") is True


async def test_unified_state_predicates():
    unified, _ = _unified_with_fake_redis()
    await unified.initialize_execution("e1", updated_at=1)
    await unified.mark_done("e1", done=True, updated_at=10)
    assert await unified.is_done("e1") is True
    assert await unified.is_cancel_requested("e1") is False

    await unified.request_pause("e1", updated_at=20)
    assert await unified.is_pause_requested("e1") is True


async def test_unified_get_checkpoint_returns_dict_or_none():
    unified, _ = _unified_with_fake_redis()
    await unified.initialize_execution("e1", updated_at=1)
    assert await unified.get_checkpoint("e1") is None
    await unified.mark_paused("e1", paused=True, checkpoint={"cp": 7}, updated_at=10)
    assert await unified.get_checkpoint("e1") == {"cp": 7}


async def test_unified_touch_local_and_initialize_local_only():
    unified, fake = _unified_with_fake_redis()
    # *_local variants must not touch redis
    await unified.initialize_execution_local("e1", updated_at=5)
    assert "test:rt:e1" not in fake.hashes
    touched = await unified.touch_local("e1", updated_at=6)
    assert touched.updated_at == 6
    assert "test:rt:e1" not in fake.hashes


async def test_unified_mark_running_and_clear():
    unified, fake = _unified_with_fake_redis()
    await unified.mark_paused("e1", paused=True, checkpoint={"x": 1}, updated_at=1)
    running = await unified.mark_running("e1", clear_checkpoint=True, updated_at=2)
    assert running.paused is False
    await unified.clear("e1")
    assert "test:rt:e1" not in fake.hashes


async def test_unified_payload_put_get_delete_and_newest_wins():
    unified, _ = _unified_with_fake_redis()
    await unified.put_payload("pk", {"v": 1}, updated_at=10)
    got = await unified.get_payload("pk")
    assert got["v"] == 1

    # Newer redis payload should win on get when both present (equal->redis, newer->newer).
    await unified.put_payload("pk", {"v": 2}, updated_at=20)
    got2 = await unified.get_payload("pk")
    assert got2["v"] == 2

    await unified.delete_payload("pk")
    assert await unified.get_payload("pk") is None


async def test_unified_get_payload_local_only_when_redis_returns_none():
    local_store = LocalWorkflowRuntimeStore(shared_state={}, shared_payload_state={})

    class _DeadRedisStore(RedisWorkflowRuntimeStore):
        async def _ensure_redis(self):  # type: ignore[override]
            return None

    dead = _DeadRedisStore(key_prefix="test:rt")
    unified = WorkflowRuntimeStore(redis_store=dead, local_store=local_store)
    await unified.put_payload("pk", {"only": "local"}, updated_at=1)
    got = await unified.get_payload("pk")
    assert got["only"] == "local"


async def test_unified_get_payload_prefers_newer_local_over_older_redis():
    unified, _ = _unified_with_fake_redis()
    # Seed redis first (older), then write only local (newer) directly.
    await unified.put_payload("pk", {"src": "redis"}, updated_at=10)
    await unified._local_store.put_payload("pk", {"src": "local"}, updated_at=99)
    got = await unified.get_payload("pk")
    assert got["src"] == "local"


def test_create_workflow_runtime_store_factory():
    store = create_workflow_runtime_store()
    assert isinstance(store, WorkflowRuntimeStore)


# ===========================================================================
# adk_builtin_tools — protocol/validation helpers (pure, real behavior)
# ===========================================================================
def test_normalize_sheet_stage_valid_and_invalid():
    assert adk.normalize_sheet_stage("INGEST") == "ingest"
    assert adk.normalize_sheet_stage(" query ") == "query"
    with pytest.raises(ValueError):
        adk.normalize_sheet_stage("bogus")


def test_normalize_sheet_protocol_version_default_and_mismatch():
    assert adk._normalize_sheet_protocol_version("") == adk.SHEET_STAGE_PROTOCOL_VERSION
    assert adk._normalize_sheet_protocol_version(adk.SHEET_STAGE_PROTOCOL_VERSION) == adk.SHEET_STAGE_PROTOCOL_VERSION
    with pytest.raises(ValueError):
        adk._normalize_sheet_protocol_version("sheet-stage/v999")


def test_coerce_artifact_version_rules():
    assert adk._coerce_sheet_artifact_version(3) == 3
    assert adk._coerce_sheet_artifact_version("4") == 4
    assert adk._coerce_sheet_artifact_version("5.0") == 5
    with pytest.raises(ValueError):
        adk._coerce_sheet_artifact_version(True)  # bool rejected
    with pytest.raises(ValueError):
        adk._coerce_sheet_artifact_version(0)  # must be >= 1
    with pytest.raises(ValueError):
        adk._coerce_sheet_artifact_version("")  # required
    with pytest.raises(ValueError):
        adk._coerce_sheet_artifact_version("abc")  # not numeric


def test_normalize_artifact_ref_camel_and_snake_and_optional():
    assert adk.normalize_sheet_artifact_ref(None, required=False) is None
    with pytest.raises(ValueError):
        adk.normalize_sheet_artifact_ref(None, required=True)
    with pytest.raises(ValueError):
        adk.normalize_sheet_artifact_ref("not-a-dict")

    ref = adk.normalize_sheet_artifact_ref(
        {
            "artifactKey": "k1",
            "artifactVersion": 2,
            "artifactSessionId": "s1",
        }
    )
    assert ref == {"artifact_key": "k1", "artifact_version": 2, "artifact_session_id": "s1"}

    with pytest.raises(ValueError):
        adk.normalize_sheet_artifact_ref({"artifact_version": 1, "artifact_session_id": "s"})  # missing key
    with pytest.raises(ValueError):
        adk.normalize_sheet_artifact_ref({"artifact_key": "k", "artifact_version": 1})  # missing session


def test_validate_artifact_binding_session_and_key():
    ref = {"artifact_key": "k1", "artifact_version": 1, "artifact_session_id": "s1"}
    out = adk.validate_sheet_artifact_binding(artifact_ref=ref, expected_session_id="s1", expected_artifact_key="k1")
    assert out["artifact_key"] == "k1"

    with pytest.raises(ValueError):
        adk.validate_sheet_artifact_binding(artifact_ref=ref, expected_session_id="other")
    with pytest.raises(ValueError):
        adk.validate_sheet_artifact_binding(artifact_ref=ref, expected_session_id="s1", expected_artifact_key="kX")
    with pytest.raises(ValueError):
        adk.validate_sheet_artifact_binding(artifact_ref=ref, expected_session_id="   ")  # blank expected session


def test_build_sheet_stage_envelope_happy_and_validation():
    env = adk.build_sheet_stage_envelope(
        stage="export",
        status="completed",
        session_id="s1",
        artifact={"artifact_key": "k", "artifact_version": 1, "artifact_session_id": "s1"},
        data={"rows": 3},
    )
    assert env["protocol_version"] == adk.SHEET_STAGE_PROTOCOL_VERSION
    assert env["stage"] == "export"
    assert env["status"] == "completed"
    assert env["session_id"] == "s1"
    assert env["artifact"]["artifact_key"] == "k"
    assert env["data"] == {"rows": 3}

    # error normalization: str -> {"message": ...}; dict passes through
    env_err = adk.build_sheet_stage_envelope(stage="query", status="failed", session_id="s1", error="kaboom")
    assert env_err["error"] == {"message": "kaboom"}
    env_err2 = adk.build_sheet_stage_envelope(stage="query", status="failed", session_id="s1", error={"code": 7})
    assert env_err2["error"] == {"code": 7}


def test_build_sheet_stage_envelope_invalid_status_and_session():
    with pytest.raises(ValueError):
        adk.build_sheet_stage_envelope(stage="ingest", status="weird", session_id="s1")
    with pytest.raises(ValueError):
        adk.build_sheet_stage_envelope(stage="ingest", status="completed", session_id="   ")


def test_validate_sheet_export_precheck_tenant_mismatch_and_sensitive():
    # tenant mismatch -> PermissionError
    with pytest.raises(PermissionError):
        adk.validate_sheet_export_precheck(
            tenant_id="t1",
            resource_tenant_id="t2",
            payload_bytes=b"name,age\nA,1",
            analysis={},
        )
    # sensitive keyword in payload -> ValueError
    with pytest.raises(ValueError):
        adk.validate_sheet_export_precheck(
            tenant_id="t1",
            resource_tenant_id="t1",
            payload_bytes=b"user,password\nbob,secret",
            analysis={},
        )
    # clean payload passes
    out = adk.validate_sheet_export_precheck(
        tenant_id="t1",
        resource_tenant_id="t1",
        payload_bytes=b"city,count\nNYC,5",
        analysis={"columns": ["city", "count"]},
    )
    assert out["status"] == "passed"
    assert out["tenant_id"] == "t1"
    assert out["sensitive_hits"] == []


def test_scan_sensitive_keywords_scans_nested_analysis():
    hits = adk._scan_sheet_sensitive_keywords(
        payload_bytes=b"",
        analysis={"fields": [{"name": "api_key"}, {"name": "ok"}], "note": ["护照"]},
    )
    assert "api_key" in hits
    assert "护照" in hits


def test_iter_sheet_security_strings_handles_types():
    out = adk._iter_sheet_security_strings({"a": [1, 2.5, True], "b": None})
    # keys + scalars are stringified; None -> nothing
    assert "a" in out
    assert "1" in out


def test_guess_file_name_and_format():
    assert adk._guess_file_name("https://host/path/data.csv") == "data.csv"
    assert adk._guess_file_name("") == "sheet.csv"
    assert adk._guess_file_name("", fallback="x.bin") == "x.bin"

    assert adk._guess_file_format(file_name="x.xlsx", explicit_file_format=None, mime_type=None) == "xlsx"
    assert adk._guess_file_format(file_name="x.csv", explicit_file_format=None, mime_type=None) == "csv"
    assert adk._guess_file_format(file_name="x.bin", explicit_file_format="CSV", mime_type=None) == "csv"
    assert (
        adk._guess_file_format(file_name="x.bin", explicit_file_format=None, mime_type="text/csv") == "csv"
    )
    assert (
        adk._guess_file_format(
            file_name="x.bin",
            explicit_file_format=None,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        == "xlsx"
    )
    assert adk._guess_file_format(file_name="x.bin", explicit_file_format=None, mime_type=None) is None


def test_clamp_sample_rows_bounds():
    assert adk._clamp_sample_rows(0) == 1
    assert adk._clamp_sample_rows(500) == 100
    assert adk._clamp_sample_rows("oops", default=9) == 9
    assert adk._clamp_sample_rows(7) == 7


def test_normalize_sheet_name_variants():
    assert adk._normalize_sheet_name(None) == 0
    assert adk._normalize_sheet_name(2) == 2
    assert adk._normalize_sheet_name("3") == 3
    assert adk._normalize_sheet_name("Sheet1") == "Sheet1"
    assert adk._normalize_sheet_name("  ") == 0


def test_decode_data_url_base64_and_plain_and_invalid():
    b64 = base64.b64encode(b"hello").decode()
    data_url = f"data:text/csv;base64,{b64}"
    payload, mime = adk._decode_data_url(data_url)
    assert payload == b"hello"
    assert mime == "text/csv"

    plain = "data:text/csv,a%2Cb"
    payload2, mime2 = adk._decode_data_url(plain)
    assert payload2 == b"a,b"
    assert mime2 == "text/csv"

    with pytest.raises(ValueError):
        adk._decode_data_url("not-a-data-url")


def test_resolve_allowed_sheet_hosts_parsing(monkeypatch):
    monkeypatch.setenv(adk._SHEET_ALLOWED_HOSTS_ENV, "Example.com, *.cdn.net, https://files.org/, ,*.cdn.net")
    hosts = adk._resolve_allowed_sheet_hosts()
    assert "example.com" in hosts
    assert ".cdn.net" in hosts
    assert "files.org" in hosts
    # dedupe of the repeated wildcard
    assert hosts.count(".cdn.net") == 1

    monkeypatch.setenv(adk._SHEET_ALLOWED_HOSTS_ENV, "")
    assert adk._resolve_allowed_sheet_hosts() == []


def test_is_allowed_sheet_host_exact_and_wildcard():
    allowed = ["example.com", ".cdn.net"]
    assert adk._is_allowed_sheet_host("example.com", allowed) is True
    assert adk._is_allowed_sheet_host("EXAMPLE.COM", allowed) is True
    assert adk._is_allowed_sheet_host("a.cdn.net", allowed) is True
    assert adk._is_allowed_sheet_host("cdn.net", allowed) is True  # suffix root matches
    assert adk._is_allowed_sheet_host("evil.com", allowed) is False
    assert adk._is_allowed_sheet_host("", allowed) is False


def test_validate_sheet_file_url_allowlist():
    from app.utils.url_security import UnsafeURLError

    with pytest.raises(UnsafeURLError):
        adk._validate_sheet_file_url_allowlist("https://host/x.csv", [])  # empty allowlist
    with pytest.raises(UnsafeURLError):
        adk._validate_sheet_file_url_allowlist("https://evil.com/x.csv", ["good.com"])
    # allowed host does not raise
    adk._validate_sheet_file_url_allowlist("https://good.com/x.csv", ["good.com"])


# ===========================================================================
# sheet_analyze tool dispatch — mock ONLY the table-analysis module + network
# ===========================================================================
class _FakeTableModule:
    """Stand-in for table_analysis_service (the external SUT boundary)."""

    class TableAnalysisError(Exception):
        pass

    @staticmethod
    def analyze_table_bytes(file_bytes, *, file_name, file_format, sample_rows, csv_encoding, sheet_name):
        return {
            "file_name": file_name,
            "file_format": file_format,
            "rows": file_bytes.decode("utf-8", "ignore").count("\n"),
            "sample_rows": sample_rows,
            "sheet_name": sheet_name,
        }

    @staticmethod
    def export_table_analysis(*, analysis, export_format):
        if export_format == "json":
            return {"rendered_as": "json", "analysis": analysis}
        return f"# Table {analysis.get('file_name')} ({analysis.get('rows')} rows)"


@pytest.fixture
def sheet_analyze(monkeypatch):
    monkeypatch.setattr(adk, "_load_table_analysis_module", lambda: _FakeTableModule)
    tools = adk.build_adk_builtin_tools()
    assert len(tools) == 1
    return tools[0]


def test_sheet_analyze_inline_plain_content(sheet_analyze):
    result = sheet_analyze(
        file_name="data.csv",
        content="name,age\nAlice,30\nBob,25\n",
        export_format="markdown",
    )
    assert result["status"] == "success"
    assert result["tool"] == "sheet_analyze"
    assert result["source_type"] == "inline"
    assert result["file_format"] == "csv"
    assert "Table data.csv" in result["summaryText"]
    assert result["export_precheck"]["status"] == "passed"


def test_sheet_analyze_inline_base64_content(sheet_analyze):
    raw = "x,y\n1,2\n"
    b64 = base64.b64encode(raw.encode()).decode()
    result = sheet_analyze(
        file_name="data.csv",
        content=b64,
        content_encoding="base64",
        export_format="json",
    )
    assert result["status"] == "success"
    # json export path renders a dict serialized to text
    assert json.loads(result["text"])["rendered_as"] == "json"


def test_sheet_analyze_data_url_path_infers_xlsx_name(sheet_analyze):
    # excel mime should rename the default sheet.csv -> sheet.xlsx
    payload = base64.b64encode(b"a,b\n1,2\n").decode()
    data_url = (
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + payload
    )
    result = sheet_analyze(data_url=data_url, file_name="sheet.csv")
    assert result["status"] == "success"
    assert result["source_type"] == "data_url"
    assert result["file_name"] == "sheet.xlsx"
    assert result["file_format"] == "xlsx"


def test_sheet_analyze_remote_url_path(monkeypatch, sheet_analyze):
    # mock the download boundary only
    monkeypatch.setattr(
        adk,
        "_download_remote_file",
        lambda url: (b"c,d\n3,4\n", "https://host/remote.csv", "text/csv"),
    )
    result = sheet_analyze(file_url="https://host/remote.csv", file_name="sheet.csv")
    assert result["status"] == "success"
    assert result["source_type"] == "remote_url"
    assert result["file_name"] == "remote.csv"
    assert result["file_format"] == "csv"


def test_sheet_analyze_requires_a_source(sheet_analyze):
    result = sheet_analyze()  # no content/data_url/file_url
    assert result["status"] == "failed"
    assert "required" in result["error"]


def test_sheet_analyze_unable_to_infer_format(sheet_analyze):
    # no extension, no explicit format, no mime -> infer fails
    result = sheet_analyze(file_name="mystery", content="a,b\n1,2\n")
    assert result["status"] == "failed"
    assert "infer" in result["error"]


def test_sheet_analyze_maps_unsafe_url_error(monkeypatch, sheet_analyze):
    from app.utils.url_security import UnsafeURLError

    def _boom(_url):
        raise UnsafeURLError("blocked host")

    monkeypatch.setattr(adk, "_download_remote_file", _boom)
    result = sheet_analyze(file_url="https://evil/x.csv", file_name="x.csv")
    assert result["status"] == "failed"
    assert "unsafe file_url" in result["error"]


def test_sheet_analyze_maps_table_analysis_error(monkeypatch, sheet_analyze):
    def _raise(*_a, **_k):
        raise _FakeTableModule.TableAnalysisError("bad table")

    monkeypatch.setattr(_FakeTableModule, "analyze_table_bytes", staticmethod(_raise))
    result = sheet_analyze(file_name="data.csv", content="a,b\n1,2\n")
    assert result["status"] == "failed"
    assert result["error"] == "bad table"


def test_sheet_analyze_maps_http_status_error(monkeypatch, sheet_analyze):
    import httpx

    def _boom(_url):
        request = httpx.Request("GET", "https://host/x.csv")
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("err", request=request, response=response)

    monkeypatch.setattr(adk, "_download_remote_file", _boom)
    result = sheet_analyze(file_url="https://host/x.csv", file_name="x.csv")
    assert result["status"] == "failed"
    assert "http status 503" in result["error"]


def test_sheet_analyze_maps_request_error(monkeypatch, sheet_analyze):
    import httpx

    def _boom(_url):
        raise httpx.ConnectError("conn refused", request=httpx.Request("GET", "https://host/x.csv"))

    monkeypatch.setattr(adk, "_download_remote_file", _boom)
    result = sheet_analyze(file_url="https://host/x.csv", file_name="x.csv")
    assert result["status"] == "failed"
    assert "http request failed" in result["error"]


def test_sheet_analyze_maps_permission_error_from_precheck(sheet_analyze):
    # tenant mismatch inside the tool propagates as PermissionError -> failed envelope
    result = sheet_analyze(
        file_name="data.csv",
        content="a,b\n1,2\n",
        tenant_id="t1",
        resource_tenant_id="t2",
    )
    assert result["status"] == "failed"
    assert "tenant binding mismatch" in result["error"]


def test_sheet_analyze_missing_module_functions(monkeypatch):
    class _BadModule:
        TableAnalysisError = Exception
        # analyze_table_bytes/export_table_analysis intentionally absent

    monkeypatch.setattr(adk, "_load_table_analysis_module", lambda: _BadModule)
    tool = adk.build_adk_builtin_tools()[0]
    result = tool(file_name="data.csv", content="a,b\n1,2\n")
    assert result["status"] == "failed"
    assert "required functions" in result["error"]
