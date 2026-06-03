"""
Regression / characterization tests for cluster perf-misc.

Covers three findings:
- B3: workflow BFS reachability must keep identical traversal semantics after
      switching from list.pop(0) to collections.deque.popleft().
- P4: config TTL cache get_or_load must coalesce concurrent loads of the SAME
      key to a single loader() invocation (TOCTOU fix via double-checked /
      per-key locking).
- P3: case-conversion middleware must NOT fully buffer + convert very large
      JSON response bodies above a size threshold (passthrough), while normal
      bodies still get snake_case -> camelCase conversion.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest


# ---------------------------------------------------------------------------
# P4 — get_or_load concurrent coalescing (TOCTOU)
# ---------------------------------------------------------------------------

def _fresh_config_cache_module():
    """Import the config cache module and reset its global cache."""
    from app.services.gemini.coordinators import _config_cache

    _config_cache.clear_config_cache()
    return _config_cache


def test_get_or_load_coalesces_concurrent_same_key_loads():
    """
    Under concurrent get_or_load() for the SAME key with a slow loader,
    the loader must run exactly once. Before the fix, multiple threads
    each observe a cache miss (lock released between check and store) and
    each call loader() -> count > 1.
    """
    cache = _fresh_config_cache_module()

    load_count = {"n": 0}
    count_lock = threading.Lock()

    def slow_loader():
        with count_lock:
            load_count["n"] += 1
        # Simulate a real DB read so the race window is wide and deterministic.
        time.sleep(0.2)
        return {"value": "loaded"}

    results = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()  # release all threads simultaneously
        out = cache.get_or_load("user-1", "vertex_ai", slow_loader)
        with results_lock:
            results.append(out)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert load_count["n"] == 1, (
        f"loader ran {load_count['n']} times; concurrent same-key loads "
        "must coalesce to exactly one DB read"
    )
    assert all(r == {"value": "loaded"} for r in results)
    assert len(results) == 8


def test_get_or_load_different_keys_load_in_parallel():
    """
    Distinct keys must NOT serialize behind one another. If the fix held a
    single global lock across the slow loader, two different keys would run
    sequentially (~0.4s). With per-key locking they overlap (~0.2s).
    """
    cache = _fresh_config_cache_module()

    def slow_loader_factory(val):
        def _loader():
            time.sleep(0.2)
            return {"value": val}
        return _loader

    outputs = {}
    out_lock = threading.Lock()

    def worker(user_id, val):
        out = cache.get_or_load(user_id, "vertex_ai", slow_loader_factory(val))
        with out_lock:
            outputs[user_id] = out

    start = time.perf_counter()
    threads = [
        threading.Thread(target=worker, args=("u-a", "A")),
        threading.Thread(target=worker, args=("u-b", "B")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    assert outputs["u-a"] == {"value": "A"}
    assert outputs["u-b"] == {"value": "B"}
    # Two 0.2s loaders should overlap; allow generous slack but reject full
    # serialization (~0.4s+).
    assert elapsed < 0.35, (
        f"different keys serialized ({elapsed:.3f}s); per-key locking should "
        "let distinct keys load in parallel"
    )


def test_get_or_load_caches_none_result():
    """A loader returning None must be cached (not re-run on next call)."""
    cache = _fresh_config_cache_module()

    calls = {"n": 0}

    def none_loader():
        calls["n"] += 1
        return None

    first = cache.get_or_load("user-x", "settings", none_loader)
    second = cache.get_or_load("user-x", "settings", none_loader)
    assert first is None
    assert second is None
    assert calls["n"] == 1, "cached None must not trigger a second loader call"


def test_get_or_load_skips_cache_for_falsy_user():
    """Falsy user_id bypasses cache entirely (loader runs each time)."""
    cache = _fresh_config_cache_module()

    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return {"value": calls["n"]}

    cache.get_or_load(None, "vertex_ai", loader)
    cache.get_or_load("", "vertex_ai", loader)
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# B3 — workflow BFS reachability (deque vs list.pop(0))
# ---------------------------------------------------------------------------

class _FakeEngine:
    """Minimal engine stub exposing only what orchestration.execute() reads
    for the validation / BFS phase. _execute_node is never reached here because
    we assert on validation errors raised before scheduling."""

    DEFAULT_AGENT_TIMEOUT_SECONDS = 60
    DEFAULT_IMAGE_AGENT_TIMEOUT_SECONDS = 120
    DEFAULT_VIDEO_AGENT_TIMEOUT_SECONDS = 600
    DEFAULT_DATA_AGENT_TIMEOUT_SECONDS = 180
    MAX_TOTAL_STEPS = 1000

    def __init__(self):
        self._trace_events = []

    def _record_trace_event(self, event_type, payload=None):
        self._trace_events.append((event_type, payload))

    async def _emit_callback(self, hook_name, payload):
        return None

    def _get_node_type(self, node):
        return (node.get("data", {}) or {}).get("type") or node.get("type")

    def _resolve_max_parallel_nodes(self, initial_input=None):
        return 4

    def _to_bool(self, value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _node(node_id, node_type):
    return {"id": node_id, "type": node_type, "data": {"type": node_type}}


def _edge(edge_id, source, target):
    return {"id": edge_id, "source": source, "target": target}


def _run_execute(nodes, edges, initial_input=None):
    from app.services.agent.workflow_engine import orchestration

    engine = _FakeEngine()
    return asyncio.run(
        orchestration.execute(engine, nodes, edges, initial_input or {"task": "t"})
    )


def test_bfs_detects_unreachable_node_from_start():
    """
    A node not reachable from start must raise the unreachable error. This
    exercises forward BFS traversal; the deque migration must keep identical
    reachability semantics.
    """
    nodes = [
        _node("start", "start"),
        _node("a", "agent"),
        _node("orphan", "agent"),  # not connected from start
        _node("end", "end"),
    ]
    edges = [
        _edge("e1", "start", "a"),
        _edge("e2", "a", "end"),
        _edge("e3", "orphan", "end"),  # reachable to end but not from start
    ]
    with pytest.raises(ValueError) as exc:
        _run_execute(nodes, edges)
    assert "未从开始节点连通" in str(exc.value)


def test_bfs_detects_node_with_no_path_to_end():
    """Reverse BFS: a node that cannot flow to end must raise its error."""
    nodes = [
        _node("start", "start"),
        _node("a", "agent"),
        _node("deadend", "agent"),
        _node("end", "end"),
    ]
    edges = [
        _edge("e1", "start", "a"),
        _edge("e2", "a", "end"),
        _edge("e3", "a", "deadend"),  # reachable from start, cannot reach end
    ]
    with pytest.raises(ValueError) as exc:
        _run_execute(nodes, edges)
    assert "无法流向结束节点" in str(exc.value)


def test_bfs_full_reachability_accepts_diamond_graph():
    """
    A diamond (start -> a, start -> b, a -> end, b -> end) is fully reachable
    both forward and reverse. Validation must pass (no ValueError about
    reachability). We stop before real node execution by making _execute_node
    raise a sentinel, proving BFS validation completed successfully.
    """
    from app.services.agent.workflow_engine import orchestration

    nodes = [
        _node("start", "start"),
        _node("a", "agent"),
        _node("b", "agent"),
        _node("end", "end"),
    ]
    edges = [
        _edge("e1", "start", "a"),
        _edge("e2", "start", "b"),
        _edge("e3", "a", "end"),
        _edge("e4", "b", "end"),
    ]

    engine = _FakeEngine()

    # If BFS validation passed, execute() proceeds to schedule nodes and call
    # _execute_node. We short-circuit with a sentinel to confirm we got past
    # all reachability checks without a ValueError.
    class _Sentinel(Exception):
        pass

    async def _boom(**kwargs):
        raise _Sentinel("reached scheduling")

    engine._execute_node = _boom  # type: ignore[attr-defined]
    engine._resolve_max_visits = lambda *a, **k: 5  # type: ignore[attr-defined]
    engine._build_node_input_snapshot = lambda **k: {}  # type: ignore[attr-defined]
    engine._select_outgoing_edges = lambda **k: []  # type: ignore[attr-defined]
    engine._get_source_handle = lambda e: None  # type: ignore[attr-defined]

    with pytest.raises(_Sentinel):
        asyncio.run(orchestration.execute(engine, nodes, edges, {"task": "t"}))


# ---------------------------------------------------------------------------
# P3 — case-conversion middleware large-body passthrough threshold
# ---------------------------------------------------------------------------

def _build_app_with_json_response(body_bytes: bytes, status: int = 200):
    """A tiny ASGI app that returns a fixed JSON body in one chunk."""

    async def app(scope, receive, send):
        # drain request
        more = True
        while more:
            msg = await receive()
            more = msg.get("more_body", False)
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body_bytes)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body_bytes,
            "more_body": False,
        })

    return app


async def _drive(middleware, path="/x", method="GET"):
    """Run an ASGI request through the middleware and collect sent messages."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "query_string": b"",
        # no "app" -> middleware resolves default (no skip) options
    }
    await middleware(scope, receive, send)
    return sent


def test_middleware_converts_normal_json_body():
    """Small/normal JSON bodies must still be converted snake_case->camelCase."""
    from app.middleware.case_conversion_middleware import CaseConversionMiddleware

    payload = {"user_id": 42, "session_name": "abc"}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    inner = _build_app_with_json_response(body)
    mw = CaseConversionMiddleware(inner)

    sent = asyncio.run(_drive(mw))
    body_msgs = [m for m in sent if m.get("type") == "http.response.body"]
    assert body_msgs, "no response body emitted"
    out = json.loads(body_msgs[-1]["body"].decode("utf-8"))
    assert out == {"userId": 42, "sessionName": "abc"}, (
        "normal JSON must be converted to camelCase"
    )


def test_middleware_skips_buffering_for_huge_body():
    """
    A JSON response above the size threshold must be passed through WITHOUT
    full-body conversion. Before the fix the middleware always buffered the
    full body and converted every key (snake->camel), so 'snake_key' would
    become 'snakeKey'. After the fix, an oversized body is streamed through
    untouched, so the original snake_case bytes survive verbatim.
    """
    from app.middleware import case_conversion_middleware as mod
    from app.middleware.case_conversion_middleware import CaseConversionMiddleware

    threshold = getattr(mod, "MAX_RESPONSE_CONVERSION_BYTES", None)
    assert threshold is not None, (
        "expected MAX_RESPONSE_CONVERSION_BYTES threshold constant"
    )

    # Build a JSON body that exceeds the threshold and contains snake_case keys.
    big_list = [{"snake_key": i, "another_field": "x" * 16} for i in range(1)]
    # Inflate to exceed threshold deterministically.
    filler = "y" * (threshold + 4096)
    payload = {"snake_key": filler, "items": big_list}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(body) > threshold

    inner = _build_app_with_json_response(body)
    mw = CaseConversionMiddleware(inner)

    sent = asyncio.run(_drive(mw))
    body_msgs = [m for m in sent if m.get("type") == "http.response.body"]
    assert body_msgs, "no response body emitted"
    emitted = body_msgs[-1]["body"]

    # Passthrough: original snake_case bytes survive (no key conversion).
    assert b"snake_key" in emitted, (
        "oversized body must be passed through unconverted (snake_key preserved)"
    )
    assert b"snakeKey" not in emitted, (
        "oversized body must NOT be key-converted to camelCase"
    )
    assert emitted == body, "oversized body bytes must be streamed verbatim"
