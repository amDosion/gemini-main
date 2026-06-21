"""Coverage-focused tests for ``app.services.common.interactions_manager``.

Module under test (SUT)
-----------------------
``app.services.common.interactions_manager.InteractionsManager`` and its
module-level helpers / singleton factory.

This is the high-level Interactions (Deep Research) orchestration service:

  * env-driven config helpers (``_get_interactions_stream_timeout_ms`` /
    ``_get_interactions_stream_max_resume`` /
    ``_get_interactions_stream_resume_backoff_sec``)
  * retryable-error classification (``_is_retryable_stream_exception``)
  * client acquisition (``get_client`` / ``get_async_client`` via the unified pool)
  * ``create_interaction`` / ``create_interaction_async`` (Vertex-vs-Gemini mode,
    DB credential lookup, MCP tool injection, the ``background``/``store`` contract)
  * ``deep_research`` parameter-mapping wrapper
  * status polling (``get_interaction_status`` / ``get_interaction_status_async`` /
    ``wait_for_completion`` terminal states + timeout)
  * streaming (``stream_interaction`` thread-pump + event normalization,
    ``stream_existing_interaction`` worker resume/error paths)
  * delete / cancel / close_all / list_clients
  * ``get_interactions_manager`` singleton factory

Strategy
--------
Same proven pattern as the other ``test_cov_*`` suites: drive the *real*
``InteractionsManager`` logic and mock ONLY external boundaries:

  * ``get_client_pool``  -> fake pool returning a fake google.genai Client
  * ``run_in_sdk_thread`` -> awaitable shim that calls the func directly (no real pool)
  * ``get_vertex_ai_credentials_from_db`` (lazy import target) -> fake DB lookup
  * ``get_mcp_manager``  -> fake MCP manager singleton
  * MCPManager.get_gemini_tools -> async fake returning fake tools

The SUT's own transform / branch / error-handling logic is never mocked.

asyncio_mode=auto (plain ``async def`` tests run). ``filterwarnings=error::RuntimeWarning``
is active, so every coroutine boundary is awaited.
"""

from __future__ import annotations

import logging
import warnings
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

import app.services.common.interactions_manager as im
from app.services.common.interactions_manager import (
    InteractionsManager,
    _get_interactions_stream_max_resume,
    _get_interactions_stream_resume_backoff_sec,
    _get_interactions_stream_timeout_ms,
    _is_retryable_stream_exception,
    get_interactions_manager,
)


# ---------------------------------------------------------------------------
# Fakes for external boundaries
# ---------------------------------------------------------------------------


class _FakeInteraction:
    """Mimic the SDK Interaction object returned by create/get/cancel."""

    def __init__(self, id="int-1", status="completed", outputs=None, error=None):
        self.id = id
        self.status = status
        if outputs is not None:
            self.outputs = outputs
        if error is not None:
            self.error = error


class _FakeInteractionsResource:
    """Sync interactions resource (client.interactions.*)."""

    def __init__(self, *, create_result=None, get_result=None, stream=None,
                 create_exc=None):
        self.create_result = create_result
        self.get_result = get_result
        self.stream = stream
        self.create_exc = create_exc
        self.create_calls: List[Dict[str, Any]] = []
        self.get_calls: List[Dict[str, Any]] = []
        self.delete_calls: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.create_exc is not None:
            raise self.create_exc
        if kwargs.get("stream"):
            return self.stream
        return self.create_result

    def get(self, *args, **kwargs):
        # supports both positional (status) and kw stream form
        self.get_calls.append({"args": args, "kwargs": kwargs})
        if kwargs.get("stream"):
            return self.stream
        return self.get_result

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)


class _FakeAsyncInteractionsResource:
    """Async interactions resource (client.aio.interactions.*)."""

    def __init__(self, *, create_result=None, get_result=None, cancel_result=None,
                 stream=None):
        self.create_result = create_result
        self.get_result = get_result
        self.cancel_result = cancel_result
        self.stream = stream
        self.create_calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if kwargs.get("stream"):
            return self.stream
        return self.create_result

    async def get(self, *args, **kwargs):
        return self.get_result

    async def cancel(self, **kwargs):
        return self.cancel_result


class _FakeAio:
    def __init__(self, interactions):
        self.interactions = interactions


class _FakeClient:
    def __init__(self, *, interactions=None, aio_interactions=None):
        self.interactions = interactions or _FakeInteractionsResource()
        self.aio = _FakeAio(aio_interactions or _FakeAsyncInteractionsResource())


class _FakePool:
    """Records get_client args and returns a preset client."""

    def __init__(self, client):
        self._client = client
        self.get_client_calls: List[Dict[str, Any]] = []
        self.closed = False
        self.listed = False

    def get_client(self, **kwargs):
        self.get_client_calls.append(kwargs)
        return self._client

    def close_all(self):
        self.closed = True

    def list_clients(self):
        self.listed = True
        return {"key-a": {"vertexai": False}}


class _FakeMcpManager:
    def __init__(self, tools=None, exc=None):
        self._tools = tools or []
        self._exc = exc
        self.calls: List[str] = []

    async def get_gemini_tools(self, session_id):
        self.calls.append(session_id)
        if self._exc is not None:
            raise self._exc
        return self._tools


@pytest.fixture
def patch_pool(monkeypatch):
    """Install a fake client pool; return a helper that wires a given client."""

    def _install(client) -> _FakePool:
        pool = _FakePool(client)
        monkeypatch.setattr(im, "get_client_pool", lambda: pool)
        return pool

    return _install


@pytest.fixture(autouse=True)
def patch_sdk_thread(monkeypatch):
    """run_in_sdk_thread should just invoke the func directly (awaitable)."""

    async def _shim(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(im, "run_in_sdk_thread", _shim)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure the module-level singleton does not leak between tests."""
    im._global_manager = None
    yield
    im._global_manager = None


# ---------------------------------------------------------------------------
# Module-level config + classifier helpers
# ---------------------------------------------------------------------------


def test_retryable_classifier_matches_timeout_and_transient():
    assert _is_retryable_stream_exception(Exception("The read operation timed out"))
    assert _is_retryable_stream_exception(Exception("ReadTimeout while polling"))
    assert _is_retryable_stream_exception(Exception("Connection reset by peer"))
    assert _is_retryable_stream_exception(Exception("Broken pipe"))


def test_retryable_classifier_rejects_other_errors():
    assert not _is_retryable_stream_exception(ValueError("bad input"))
    assert not _is_retryable_stream_exception(Exception("404 not found"))


def test_stream_timeout_default_and_override(monkeypatch):
    monkeypatch.delenv("GEMINI_INTERACTIONS_STREAM_TIMEOUT_MS", raising=False)
    assert _get_interactions_stream_timeout_ms() == 300000

    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_TIMEOUT_MS", "12345")
    assert _get_interactions_stream_timeout_ms() == 12345

    # Non-positive and garbage fall back to default.
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_TIMEOUT_MS", "0")
    assert _get_interactions_stream_timeout_ms() == 300000
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_TIMEOUT_MS", "not-an-int")
    assert _get_interactions_stream_timeout_ms() == 300000


def test_stream_max_resume_default_and_override(monkeypatch):
    monkeypatch.delenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", raising=False)
    assert _get_interactions_stream_max_resume() == 8

    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "3")
    assert _get_interactions_stream_max_resume() == 3

    # 0 is valid (>= 0), negative & garbage fall back to 8.
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "0")
    assert _get_interactions_stream_max_resume() == 0
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "-1")
    assert _get_interactions_stream_max_resume() == 8
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "xx")
    assert _get_interactions_stream_max_resume() == 8


def test_stream_backoff_default_and_override(monkeypatch):
    monkeypatch.delenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", raising=False)
    assert _get_interactions_stream_resume_backoff_sec() == 1.0

    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", "2.5")
    assert _get_interactions_stream_resume_backoff_sec() == 2.5
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", "0")
    assert _get_interactions_stream_resume_backoff_sec() == 1.0
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", "bad")
    assert _get_interactions_stream_resume_backoff_sec() == 1.0


# ---------------------------------------------------------------------------
# Client acquisition
# ---------------------------------------------------------------------------


def test_get_client_passes_through_to_pool(patch_pool):
    client = _FakeClient()
    pool = patch_pool(client)
    mgr = InteractionsManager()

    got = mgr.get_client(api_key="k", vertexai=True, project="p", location="us")
    assert got is client
    assert pool.get_client_calls[-1]["api_key"] == "k"
    assert pool.get_client_calls[-1]["vertexai"] is True
    assert pool.get_client_calls[-1]["project"] == "p"


def test_get_async_client_returns_aio(patch_pool):
    client = _FakeClient()
    patch_pool(client)
    mgr = InteractionsManager()

    aio = mgr.get_async_client(api_key="k")
    assert aio is client.aio


# ---------------------------------------------------------------------------
# create_interaction
# ---------------------------------------------------------------------------


async def test_create_interaction_background_requires_store(patch_pool):
    client = _FakeClient()
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    with pytest.raises(ValueError, match="store=True when background=True"):
        await mgr.create_interaction(input="q", api_key="k", background=True, store=None)


async def test_create_interaction_gemini_mode_builds_params(patch_pool):
    resource = _FakeInteractionsResource(create_result=_FakeInteraction(id="abc", status="queued"))
    client = _FakeClient(interactions=resource)
    pool = patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    result = await mgr.create_interaction(
        input="hello",
        api_key="my-key",
        agent="agent-x",
        background=True,
        store=True,
        agent_config={"depth": 2},
        system_instruction="be terse",
        tools=[{"type": "code_execution"}],
        previous_interaction_id="prev-1",
        vertexai=False,
    )

    assert result == {"id": "abc", "status": "queued", "outputs": [], "error": None}
    # Gemini mode passes the API key through to the pool (vertexai disabled).
    assert pool.get_client_calls[-1]["api_key"] == "my-key"
    assert pool.get_client_calls[-1]["vertexai"] is False
    # All optional params were forwarded to the SDK create call.
    sent = resource.create_calls[-1]
    assert sent["input"] == "hello"
    assert sent["agent"] == "agent-x"
    assert sent["agent_config"] == {"depth": 2}
    assert sent["system_instruction"] == "be terse"
    assert sent["previous_interaction_id"] == "prev-1"
    assert sent["store"] is True


async def test_create_interaction_debug_logs_are_summarized(patch_pool, caplog):
    resource = _FakeInteractionsResource(create_result=_FakeInteraction(id="abc", status="queued"))
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    with caplog.at_level(logging.DEBUG, logger=im.logger.name):
        result = await mgr.create_interaction(
            input="hello secret-token",
            api_key="my-key",
            agent="agent-secret-token",
            background=False,
            store=True,
            agent_config={"apiKey": "secret-token"},
            vertexai=False,
        )

    assert result["id"] == "abc"
    sent = resource.create_calls[-1]
    assert sent["input"] == "hello secret-token"
    assert sent["agent_config"] == {"apiKey": "secret-token"}

    log_text = "\n".join(record.getMessage() for record in caplog.records if record.name == im.logger.name)
    assert "<redacted input; length=" in log_text
    assert "<redacted agent; length=" in log_text
    assert "<redacted agent_config; length=" in log_text
    assert "secret-token" not in log_text


async def test_create_interaction_outputs_and_error_passthrough(patch_pool):
    inter = _FakeInteraction(id="i9", status="failed",
                             outputs=[{"text": "partial"}], error={"message": "boom"})
    client = _FakeClient(interactions=_FakeInteractionsResource(create_result=inter))
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    result = await mgr.create_interaction(input="q", api_key="k", background=False)
    assert result["outputs"] == [{"text": "partial"}]
    assert result["error"] == {"message": "boom"}


async def test_create_interaction_propagates_sdk_failure(patch_pool):
    resource = _FakeInteractionsResource(create_exc=RuntimeError("sdk exploded"))
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    with pytest.raises(RuntimeError, match="sdk exploded"):
        await mgr.create_interaction(input="q", api_key="k", background=False)


async def test_create_interaction_vertex_db_credentials(patch_pool, monkeypatch):
    """Vertex mode with db+user_id pulls project/location/credentials from DB."""
    resource = _FakeInteractionsResource(create_result=_FakeInteraction())
    client = _FakeClient(interactions=resource)
    pool = patch_pool(client)

    captured = {}

    def _fake_lookup(*, user_id, db, project, location):
        captured["user_id"] = user_id
        return ("db-project", "db-loc", "db-creds")

    monkeypatch.setattr(
        "app.services.gemini.credentials.get_vertex_ai_credentials_from_db",
        _fake_lookup,
    )

    mgr = InteractionsManager(db=object(), default_vertexai=True)
    await mgr.create_interaction(
        input="q", api_key="ignored-in-vertex", background=True, store=True,
        vertexai=True, user_id="u1",
    )

    assert captured["user_id"] == "u1"
    last = pool.get_client_calls[-1]
    # Vertex mode: api_key suppressed, db-provided project/location/credentials used.
    assert last["api_key"] is None
    assert last["project"] == "db-project"
    assert last["location"] == "db-loc"
    assert last["credentials"] == "db-creds"


async def test_create_interaction_injects_mcp_tools(patch_pool):
    resource = _FakeInteractionsResource(create_result=_FakeInteraction())
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mcp = _FakeMcpManager(tools=[{"type": "mcp_tool", "name": "search"}])
    mgr = InteractionsManager(mcp_manager=mcp, default_vertexai=False)

    await mgr.create_interaction(
        input="q", api_key="k", background=True, store=True,
        mcp_session_id="sess-1", tools=None,
    )

    assert mcp.calls == ["sess-1"]
    sent = resource.create_calls[-1]
    assert {"type": "mcp_tool", "name": "search"} in sent["tools"]


async def test_create_interaction_mcp_failure_is_swallowed(patch_pool):
    resource = _FakeInteractionsResource(create_result=_FakeInteraction())
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mcp = _FakeMcpManager(exc=RuntimeError("mcp down"))
    mgr = InteractionsManager(mcp_manager=mcp, default_vertexai=False)

    # Must not raise even though MCP tool fetch failed.
    result = await mgr.create_interaction(
        input="q", api_key="k", background=True, store=True, mcp_session_id="s",
    )
    assert result["id"] == "int-1"


# ---------------------------------------------------------------------------
# deep_research wrapper
# ---------------------------------------------------------------------------


async def test_deep_research_maps_params_and_forces_gemini(patch_pool):
    resource = _FakeInteractionsResource(create_result=_FakeInteraction(id="dr-1"))
    client = _FakeClient(interactions=resource)
    pool = patch_pool(client)
    mgr = InteractionsManager(default_vertexai=True)  # default vertex, but DR forces gemini

    result = await mgr.deep_research(
        prompt="research X",
        model="ignored",
        api_key="dr-key",
        user_id="u2",
        agent="custom-agent",
        agent_config={"k": 1},
    )

    assert result["id"] == "dr-1"
    # store=True + vertexai=False forced by deep_research.
    sent = resource.create_calls[-1]
    assert sent["agent"] == "custom-agent"
    assert sent["store"] is True
    assert pool.get_client_calls[-1]["vertexai"] is False
    assert pool.get_client_calls[-1]["api_key"] == "dr-key"


# ---------------------------------------------------------------------------
# create_interaction_async
# ---------------------------------------------------------------------------


async def test_create_interaction_async_requires_store(patch_pool):
    client = _FakeClient()
    patch_pool(client)
    mgr = InteractionsManager()

    with pytest.raises(ValueError, match="store=True when background=True"):
        await mgr.create_interaction_async(
            api_key="k", input="q", background=True, store=None,
        )


async def test_create_interaction_async_builds_params_and_mcp(patch_pool):
    aio = _FakeAsyncInteractionsResource(create_result=_FakeInteraction(id="a1", status="queued"))
    client = _FakeClient(aio_interactions=aio)
    patch_pool(client)
    mcp = _FakeMcpManager(tools=[{"type": "t", "name": "x"}])
    mgr = InteractionsManager(mcp_manager=mcp)

    result = await mgr.create_interaction_async(
        api_key="k", input="hi", background=True, store=True,
        mcp_session_id="sX", agent_config={"a": 1}, system_instruction="sys",
        previous_interaction_id="p0",
    )

    assert result == {"id": "a1", "status": "queued", "outputs": [], "error": None}
    sent = aio.create_calls[-1]
    assert sent["agent_config"] == {"a": 1}
    assert sent["system_instruction"] == "sys"
    assert sent["previous_interaction_id"] == "p0"
    assert {"type": "t", "name": "x"} in sent["tools"]


async def test_create_interaction_async_mcp_failure_is_swallowed(patch_pool):
    aio = _FakeAsyncInteractionsResource(create_result=_FakeInteraction(id="a2"))
    client = _FakeClient(aio_interactions=aio)
    patch_pool(client)
    mcp = _FakeMcpManager(exc=RuntimeError("mcp async down"))
    mgr = InteractionsManager(mcp_manager=mcp)

    # MCP fetch raises -> swallowed; create still succeeds.
    result = await mgr.create_interaction_async(
        api_key="k", input="q", background=True, store=True, mcp_session_id="s",
    )
    assert result["id"] == "a2"
    assert mcp.calls == ["s"]


# ---------------------------------------------------------------------------
# status polling
# ---------------------------------------------------------------------------


async def test_get_interaction_status_sync_path(patch_pool):
    resource = _FakeInteractionsResource(get_result=_FakeInteraction(id="g1", status="running"))
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager()

    result = await mgr.get_interaction_status(api_key="k", interaction_id="g1")
    assert result == {"id": "g1", "status": "running", "outputs": [], "error": None}


async def test_get_interaction_status_async_vertex_db_lookup(patch_pool, monkeypatch):
    aio = _FakeAsyncInteractionsResource(get_result=_FakeInteraction(id="g2", status="completed"))
    client = _FakeClient(aio_interactions=aio)
    pool = patch_pool(client)

    def _fake_lookup(*, user_id, db, project, location):
        return ("dbp", "dbl", "dbc")

    monkeypatch.setattr(
        "app.services.gemini.credentials.get_vertex_ai_credentials_from_db",
        _fake_lookup,
    )

    mgr = InteractionsManager(db=object(), default_vertexai=True)
    result = await mgr.get_interaction_status_async(
        api_key="k", interaction_id="g2", vertexai=True, user_id="u",
    )
    assert result["status"] == "completed"
    last = pool.get_client_calls[-1]
    assert last["api_key"] is None
    assert last["project"] == "dbp"
    assert last["credentials"] == "dbc"


async def test_get_interaction_status_async_skips_db_when_params_present(patch_pool, monkeypatch):
    aio = _FakeAsyncInteractionsResource(get_result=_FakeInteraction(id="g3", status="completed"))
    client = _FakeClient(aio_interactions=aio)
    patch_pool(client)

    called = {"n": 0}

    def _fake_lookup(**kwargs):
        called["n"] += 1
        return (None, None, None)

    monkeypatch.setattr(
        "app.services.gemini.credentials.get_vertex_ai_credentials_from_db",
        _fake_lookup,
    )

    mgr = InteractionsManager(db=object(), default_vertexai=True)
    # project AND location supplied -> DB lookup branch is skipped.
    await mgr.get_interaction_status_async(
        api_key="k", interaction_id="g3", vertexai=True, user_id="u",
        project="p", location="l",
    )
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# wait_for_completion
# ---------------------------------------------------------------------------


async def test_wait_for_completion_returns_on_completed(monkeypatch):
    mgr = InteractionsManager(default_vertexai=False)

    async def _status(*a, **k):
        return {"id": "w1", "status": "completed", "outputs": [], "error": None}

    monkeypatch.setattr(mgr, "get_interaction_status_async", _status)
    result = await mgr.wait_for_completion(api_key="k", interaction_id="w1")
    assert result["status"] == "completed"


async def test_wait_for_completion_raises_on_failed(monkeypatch):
    mgr = InteractionsManager(default_vertexai=False)

    async def _status(*a, **k):
        return {"id": "w2", "status": "failed", "outputs": [], "error": None}

    monkeypatch.setattr(mgr, "get_interaction_status_async", _status)
    with pytest.raises(Exception, match="交互失败"):
        await mgr.wait_for_completion(api_key="k", interaction_id="w2")


async def test_wait_for_completion_raises_on_cancelled(monkeypatch):
    mgr = InteractionsManager(default_vertexai=False)

    async def _status(*a, **k):
        return {"id": "w3", "status": "cancelled", "outputs": [], "error": None}

    monkeypatch.setattr(mgr, "get_interaction_status_async", _status)
    with pytest.raises(Exception, match="交互已取消"):
        await mgr.wait_for_completion(api_key="k", interaction_id="w3")


async def test_wait_for_completion_polls_then_completes(monkeypatch):
    mgr = InteractionsManager(default_vertexai=False)

    seq = iter([
        {"id": "w5", "status": "running", "outputs": [], "error": None},
        {"id": "w5", "status": "completed", "outputs": [], "error": None},
    ])

    async def _status(*a, **k):
        return next(seq)

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(mgr, "get_interaction_status_async", _status)
    monkeypatch.setattr(im.asyncio, "sleep", _no_sleep)
    result = await mgr.wait_for_completion(
        api_key="k", interaction_id="w5", timeout=30, poll_interval=0,
    )
    assert result["status"] == "completed"


async def test_wait_for_completion_times_out(monkeypatch):
    mgr = InteractionsManager(default_vertexai=False)

    async def _status(*a, **k):
        return {"id": "w4", "status": "running", "outputs": [], "error": None}

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(mgr, "get_interaction_status_async", _status)
    monkeypatch.setattr(im.asyncio, "sleep", _no_sleep)
    # timeout=0 -> the while loop never enters; TimeoutError raised immediately.
    with pytest.raises(TimeoutError, match="交互超时"):
        await mgr.wait_for_completion(
            api_key="k", interaction_id="w4", timeout=0, poll_interval=0,
        )


# ---------------------------------------------------------------------------
# stream_interaction (thread-pump path + event normalization)
# ---------------------------------------------------------------------------


def _make_delta(type_=None, text=None, content_text=None):
    delta = SimpleNamespace()
    if type_ is not None:
        delta.type = type_
    if text is not None:
        delta.text = text
    if content_text is not None:
        delta.content = SimpleNamespace(text=content_text)
    return delta


async def test_stream_interaction_emits_normalized_events(patch_pool):
    # Build a sequence of fake stream events covering interaction/delta/status/error/usage.
    interaction_obj = SimpleNamespace(id="si-1", status="running", outputs=["o"])
    ev_start = SimpleNamespace(event_type="interaction.start", event_id="e1",
                               interaction=interaction_obj)
    ev_delta = SimpleNamespace(event_type="content.delta", event_id="e2",
                               delta=_make_delta(type_="text", text="hello "))
    ev_thought = SimpleNamespace(event_type="content.delta",
                                 delta=_make_delta(type_="thought_summary",
                                                   content_text="thinking"))
    ev_status = SimpleNamespace(event_type="interaction.status_update", status="completed")
    ev_err = SimpleNamespace(error="something broke")
    ev_usage = SimpleNamespace(event_type="x",
                               usage=SimpleNamespace(total_tokens=5, prompt_tokens=2,
                                                     completion_tokens=3))
    stream = [ev_start, ev_delta, ev_thought, ev_status, ev_err, ev_usage]

    resource = _FakeInteractionsResource(stream=stream)
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = []
    async for ev in mgr.stream_interaction(input="q", api_key="k", vertexai=False):
        events.append(ev)

    types = [e["event_type"] for e in events]
    assert "interaction.start" in types
    # start event carries normalized interaction dict
    start = next(e for e in events if e["event_type"] == "interaction.start")
    assert start["interaction"]["id"] == "si-1"
    # text delta normalized
    text_delta = next(e for e in events if e.get("delta") and e["delta"].get("type") == "text")
    assert text_delta["delta"]["text"] == "hello "
    # thought_summary gets a content field
    thought = next(e for e in events if e.get("delta") and e["delta"].get("type") == "thought_summary")
    assert thought["delta"]["content"]["text"] == "thinking"
    # status event
    assert any(e.get("status") == "completed" for e in events)
    # error string normalized into dict
    assert any(isinstance(e.get("error"), dict) and e["error"]["message"] == "something broke"
               for e in events)
    # usage serialized
    assert any("usage" in e for e in events)


async def test_stream_interaction_propagates_worker_exception(patch_pool):
    class _BoomStream:
        def __iter__(self):
            raise RuntimeError("stream blew up")

    resource = _FakeInteractionsResource(stream=_BoomStream())
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    with pytest.raises(RuntimeError, match="stream blew up"):
        async for _ in mgr.stream_interaction(input="q", api_key="k", vertexai=False):
            pass


async def test_stream_interaction_vertex_mode_awaits_async_create(patch_pool):
    interaction_obj = SimpleNamespace(id="v-1", status="running", outputs=None)
    ev = SimpleNamespace(event_type="interaction.start", interaction=interaction_obj)
    aio = _FakeAsyncInteractionsResource(stream=[ev])
    client = _FakeClient(aio_interactions=aio)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=True)

    events = [e async for e in mgr.stream_interaction(input="q", vertexai=True)]
    assert any(e["event_type"] == "interaction.start" for e in events)
    # Vertex stream create path went through the async aio resource.
    assert aio.create_calls and aio.create_calls[-1]["stream"] is True


async def test_stream_interaction_event_type_inferred_from_classname(patch_pool):
    class InteractionStartEvent:
        # no event_type attribute -> inferred from class name
        interaction = SimpleNamespace(id="cn-1", status="ok", outputs=None)

    stream = [InteractionStartEvent()]
    resource = _FakeInteractionsResource(stream=stream)
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(input="q", api_key="k", vertexai=False)]
    # "InteractionStartEvent" -> lower, strip 'event' -> "interactionstart"
    assert events[0]["event_type"] == "interactionstart"


async def test_stream_interaction_vertex_db_lookup_and_mcp(patch_pool, monkeypatch):
    """Vertex stream path: DB credential lookup + MCP tool injection + system_instruction."""
    interaction_obj = SimpleNamespace(id="vdb-1", status="ok", outputs=None)
    ev = SimpleNamespace(event_type="interaction.start", interaction=interaction_obj)
    aio = _FakeAsyncInteractionsResource(stream=[ev])
    client = _FakeClient(aio_interactions=aio)
    pool = patch_pool(client)

    def _fake_lookup(*, user_id, db, project, location):
        return ("sp", "sl", "sc")

    monkeypatch.setattr(
        "app.services.gemini.credentials.get_vertex_ai_credentials_from_db",
        _fake_lookup,
    )
    mcp = _FakeMcpManager(tools=[{"type": "mcp_tool", "name": "srch"}])

    mgr = InteractionsManager(mcp_manager=mcp, db=object(), default_vertexai=True)
    events = [e async for e in mgr.stream_interaction(
        input="q", vertexai=True, user_id="u", mcp_session_id="ms",
        system_instruction="sys", previous_interaction_id="prev",
    )]

    assert events[0]["event_type"] == "interaction.start"
    last = pool.get_client_calls[-1]
    assert last["api_key"] is None
    assert last["project"] == "sp"
    assert last["credentials"] == "sc"
    sent = aio.create_calls[-1]
    assert {"type": "mcp_tool", "name": "srch"} in sent["tools"]
    assert sent["system_instruction"] == "sys"
    assert sent["previous_interaction_id"] == "prev"


async def test_stream_interaction_mcp_failure_swallowed(patch_pool):
    interaction_obj = SimpleNamespace(id="mf-1", status="ok", outputs=None)
    ev = SimpleNamespace(event_type="interaction.start", interaction=interaction_obj)
    resource = _FakeInteractionsResource(stream=[ev])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mcp = _FakeMcpManager(exc=RuntimeError("mcp stream down"))
    mgr = InteractionsManager(mcp_manager=mcp, default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False, mcp_session_id="s")]
    assert events[0]["event_type"] == "interaction.start"


async def test_stream_interaction_content_text_event(patch_pool):
    """Event carrying a content.text attribute is normalized into event_dict['text']."""
    content = SimpleNamespace(text="rendered content", type="output_text")
    ev = SimpleNamespace(event_type="content.added", content=content)
    resource = _FakeInteractionsResource(stream=[ev])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False)]
    assert events[0]["text"] == "rendered content"
    assert events[0]["content_type"] == "output_text"


async def test_stream_interaction_content_and_delta_logs_are_summarized(patch_pool, caplog):
    secret_text = "rendered content with secret-token"
    secret_delta = "delta content with secret-token"
    ev_content = SimpleNamespace(
        event_type="content.added",
        content=SimpleNamespace(text=secret_text, type="output_text"),
    )
    ev_delta = SimpleNamespace(
        event_type="content.delta",
        delta=SimpleNamespace(type="text", text=secret_delta),
    )
    resource = _FakeInteractionsResource(stream=[ev_content, ev_delta])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    with caplog.at_level(logging.DEBUG, logger=im.logger.name):
        events = [
            e
            async for e in mgr.stream_interaction(
                input="q",
                api_key="k",
                vertexai=False,
            )
        ]

    assert events[0]["text"] == secret_text
    assert events[1]["delta"]["text"] == secret_delta
    log_text = "\n".join(record.getMessage() for record in caplog.records if record.name == im.logger.name)
    assert "<redacted content_text; length=" in log_text
    assert "<redacted delta_text; length=" in log_text
    assert "secret-token" not in log_text


async def test_stream_interaction_content_type_only_event(patch_pool):
    """Content object with a type but no text still records content_type."""
    content = SimpleNamespace(type="image")
    ev = SimpleNamespace(event_type="content.added", content=content)
    resource = _FakeInteractionsResource(stream=[ev])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False)]
    assert events[0]["content_type"] == "image"


async def test_stream_interaction_empty_delta_event(patch_pool):
    """A delta with no usable text yields delta=None in the event dict."""
    ev = SimpleNamespace(event_type="content.delta", delta=SimpleNamespace(type="text"))
    resource = _FakeInteractionsResource(stream=[ev])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False)]
    assert events[0]["delta"] is None


async def test_stream_interaction_dict_error_passthrough(patch_pool):
    ev = SimpleNamespace(event_type="error", error={"type": "X", "message": "dict err"})
    resource = _FakeInteractionsResource(stream=[ev])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False)]
    assert events[0]["error"] == {"type": "X", "message": "dict err"}


async def test_stream_interaction_interaction_without_id_and_object_error(patch_pool):
    """interaction with no id -> alternate debug branch; non-str/dict error -> typed dict."""
    interaction_obj = SimpleNamespace(status="running")  # no id attribute
    ev_no_id = SimpleNamespace(event_type="interaction.start", interaction=interaction_obj)

    class _ErrObj:
        def __str__(self):
            return "object error"

    ev_obj_err = SimpleNamespace(event_type="error", error=_ErrObj())
    resource = _FakeInteractionsResource(stream=[ev_no_id, ev_obj_err])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False)]
    # interaction with no id still serialized with id=None
    assert events[0]["interaction"]["id"] is None
    # object error normalized to {type, message}
    err_event = next(e for e in events if e.get("error"))
    assert err_event["error"]["type"] == "_ErrObj"
    assert err_event["error"]["message"] == "object error"


async def test_stream_interaction_code_execution_tool_branch(patch_pool):
    interaction_obj = SimpleNamespace(id="ce-1", status="ok", outputs=None)
    ev = SimpleNamespace(event_type="interaction.start", interaction=interaction_obj)
    resource = _FakeInteractionsResource(stream=[ev])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    # tool dict with code_execution exercises the code_execution_enabled branch.
    events = [e async for e in mgr.stream_interaction(
        input="q", api_key="k", vertexai=False,
        tools=[{"type": "code_execution"}], agent_config={"x": 1},
    )]
    assert events[0]["event_type"] == "interaction.start"


# ---------------------------------------------------------------------------
# stream_existing_interaction (worker resume/error)
# ---------------------------------------------------------------------------


async def test_stream_existing_interaction_completes(patch_pool):
    # build_interaction_stream_event is the real normalizer; feed chunks that
    # produce a complete terminal event.
    chunk_complete = SimpleNamespace(event_type="interaction.complete", event_id="ec1",
                                     interaction=SimpleNamespace(id="x", status="completed"))
    resource = _FakeInteractionsResource(stream=[chunk_complete])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = []
    async for ev in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False,
    ):
        events.append(ev)

    assert events[-1]["event_type"] == "interaction.complete"
    # get() was called with stream=True
    assert resource.get_calls[-1]["kwargs"]["stream"] is True


async def test_stream_existing_interaction_suppresses_known_sdk_warnings(patch_pool, recwarn):
    chunk_complete = SimpleNamespace(event_type="interaction.complete", event_id="ec1",
                                     interaction=SimpleNamespace(id="x", status="completed"))

    class _NoisySdkResource(_FakeInteractionsResource):
        def get(self, *args, **kwargs):
            self.get_calls.append({"args": args, "kwargs": kwargs})
            warnings.warn(
                "Interactions usage is experimental and may change in future versions.",
                UserWarning,
                stacklevel=2,
            )
            warnings.warn(
                "Granular retry options are not supported in `.interactions` yet",
                UserWarning,
                stacklevel=2,
            )
            return iter([chunk_complete])

    resource = _NoisySdkResource()
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]

    assert events[-1]["event_type"] == "interaction.complete"
    leaked = [str(warning.message) for warning in recwarn]
    assert "Interactions usage is experimental and may change in future versions." not in leaked
    assert "Granular retry options are not supported in `.interactions` yet" not in leaked


async def test_stream_existing_interaction_error_event_terminates(patch_pool):
    chunk_err = SimpleNamespace(event_type="error", event_id="ee1",
                                error="provider rejected")
    resource = _FakeInteractionsResource(stream=[chunk_err])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]
    assert events[-1]["event_type"] == "error"


async def test_stream_existing_interaction_worker_exception_yields_error(patch_pool, monkeypatch):
    # Force max_resume=0 so a raised exception is NOT retried and surfaces as error event.
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "0")

    class _BoomStream:
        def __iter__(self):
            raise RuntimeError("hard failure")

    resource = _FakeInteractionsResource(stream=_BoomStream())
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]
    assert events[-1]["event_type"] == "error"
    assert "hard failure" in events[-1]["error"]


async def test_stream_existing_interaction_resume_then_complete(patch_pool, monkeypatch):
    """Stream ends without a complete event -> worker resumes and finishes."""
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "3")
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", "0.001")

    chunk_data = SimpleNamespace(event_type="content.delta", event_id="d1",
                                 delta=SimpleNamespace(type="text", text="bit"))
    chunk_complete = SimpleNamespace(event_type="interaction.complete", event_id="c1",
                                     interaction=SimpleNamespace(id="x", status="completed"))

    streams = [iter([chunk_data]), iter([chunk_complete])]

    class _ResumingResource(_FakeInteractionsResource):
        def get(self, *args, **kwargs):
            self.get_calls.append({"args": args, "kwargs": kwargs})
            return streams.pop(0)

    resource = _ResumingResource()
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]
    assert events[-1]["event_type"] == "interaction.complete"
    # Two get() calls: initial + one resume.
    assert len(resource.get_calls) == 2


async def test_stream_existing_interaction_resume_exhausted(patch_pool, monkeypatch):
    """Never completes -> resume exceeds max -> synthetic error event."""
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "1")
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", "0.001")

    class _NeverCompleteResource(_FakeInteractionsResource):
        def get(self, *args, **kwargs):
            self.get_calls.append({"args": args, "kwargs": kwargs})
            return iter([])  # empty stream, never a complete event

    resource = _NeverCompleteResource()
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]
    assert events[-1]["event_type"] == "error"
    assert "resume exceeded" in events[-1]["error"]


async def test_stream_existing_interaction_retryable_then_complete(patch_pool, monkeypatch):
    """A retryable timeout error is retried; then the stream completes."""
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME", "3")
    monkeypatch.setenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC", "0.001")

    chunk_complete = SimpleNamespace(event_type="interaction.complete", event_id="c1",
                                     interaction=SimpleNamespace(id="x", status="completed"))

    class _FlakyResource(_FakeInteractionsResource):
        def __init__(self):
            super().__init__()
            self._attempt = 0

        def get(self, *args, **kwargs):
            self.get_calls.append({"args": args, "kwargs": kwargs})
            self._attempt += 1
            if self._attempt == 1:
                raise Exception("The read operation timed out")
            return iter([chunk_complete])

    resource = _FlakyResource()
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]
    assert events[-1]["event_type"] == "interaction.complete"
    assert len(resource.get_calls) == 2


async def test_stream_existing_interaction_outer_exception_yields_error(patch_pool, monkeypatch):
    """If the async queue pump itself raises, the outer handler yields one error event."""
    resource = _FakeInteractionsResource(stream=[])
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager(default_vertexai=False)

    async def _boom_to_thread(func, *a, **k):
        raise RuntimeError("queue pump exploded")

    monkeypatch.setattr(im.asyncio, "to_thread", _boom_to_thread)

    events = [e async for e in mgr.stream_existing_interaction(
        api_key="k", interaction_id="x", vertexai=False)]
    assert events[-1]["event_type"] == "error"
    assert "queue pump exploded" in events[-1]["error"]


async def test_stream_existing_interaction_vertex_db_lookup(patch_pool, monkeypatch):
    chunk_complete = SimpleNamespace(event_type="interaction.complete", event_id="ec",
                                     interaction=SimpleNamespace(id="x", status="completed"))
    resource = _FakeInteractionsResource(stream=[chunk_complete])
    client = _FakeClient(interactions=resource)
    pool = patch_pool(client)

    def _fake_lookup(*, user_id, db, project, location):
        return ("vp", "vl", "vc")

    monkeypatch.setattr(
        "app.services.gemini.credentials.get_vertex_ai_credentials_from_db",
        _fake_lookup,
    )

    mgr = InteractionsManager(db=object(), default_vertexai=True)
    events = [e async for e in mgr.stream_existing_interaction(
        interaction_id="x", vertexai=True, user_id="u")]
    assert events[-1]["event_type"] == "interaction.complete"
    last = pool.get_client_calls[-1]
    assert last["api_key"] is None
    assert last["project"] == "vp"
    assert last["credentials"] == "vc"


# ---------------------------------------------------------------------------
# delete / cancel / close_all / list_clients
# ---------------------------------------------------------------------------


async def test_delete_interaction(patch_pool):
    resource = _FakeInteractionsResource()
    client = _FakeClient(interactions=resource)
    patch_pool(client)
    mgr = InteractionsManager()

    await mgr.delete_interaction(api_key="k", interaction_id="del-1")
    assert resource.delete_calls[-1]["id"] == "del-1"


async def test_cancel_interaction(patch_pool):
    aio = _FakeAsyncInteractionsResource(
        cancel_result=_FakeInteraction(id="can-1", status="cancelled"))
    client = _FakeClient(aio_interactions=aio)
    patch_pool(client)
    mgr = InteractionsManager()

    result = await mgr.cancel_interaction(api_key="k", interaction_id="can-1")
    assert result == {"id": "can-1", "status": "cancelled", "outputs": [], "error": None}


async def test_close_all_and_list_clients(patch_pool):
    client = _FakeClient()
    pool = patch_pool(client)
    mgr = InteractionsManager()

    await mgr.close_all()
    assert pool.closed is True

    listing = mgr.list_clients()
    assert pool.listed is True
    assert "key-a" in listing


# ---------------------------------------------------------------------------
# singleton factory
# ---------------------------------------------------------------------------


def test_get_interactions_manager_singleton(monkeypatch):
    fake_mcp = _FakeMcpManager()
    monkeypatch.setattr(im, "get_mcp_manager", lambda: fake_mcp)

    first = get_interactions_manager()
    second = get_interactions_manager()
    assert first is second
    assert first._mcp_manager is fake_mcp


def test_get_interactions_manager_uses_supplied_mcp(monkeypatch):
    # When mcp_manager is supplied, get_mcp_manager must not be consulted.
    def _boom():
        raise AssertionError("get_mcp_manager should not be called")

    monkeypatch.setattr(im, "get_mcp_manager", _boom)
    supplied = _FakeMcpManager()
    mgr = get_interactions_manager(mcp_manager=supplied, default_vertexai=False)
    assert mgr._mcp_manager is supplied
    assert mgr._default_vertexai is False
