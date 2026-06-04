"""
Coverage + behavior tests for app.services.gemini.agent.adk_runner.

Strategy
--------
- The Linux test venv ships the real ``google.adk`` SDK, so ``ADKRunner``
  initializes with ``_adk_available=True`` and uses the genuine ``Content`` /
  ``Part`` / ``RunConfig`` / ``LiveRequest`` / ``Blob`` types. We therefore mock
  ONLY the true external boundaries:
    * the DB session (real in-memory SQLite, not a fake),
    * the ADK ``Runner`` instance (``_adk_runner``) whose ``run_async`` /
      ``run_live`` / ``rewind_async`` we replace with deterministic fakes,
    * the ADK session service (``_session_service``) for list/snapshot paths.
- Module-under-test logic (event conversion, run-config validation, dispatch
  loops, result aggregation, error classification, session persistence) is
  exercised for real.

Fake ADK events are plain ``SimpleNamespace`` objects shaped to match the
attributes the runner reads: ``content.parts[*].{text,function_call,...}``,
``actions``, ``error_message``, ``is_final_response()``, etc.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import ADKSession
from app.services.gemini.agent import adk_runner as adk_mod
from app.services.gemini.agent.adk_runner import (
    ADKRunner,
    compute_adk_accuracy_signals,
    validate_adk_run_config_allowlist,
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _make_runner(db) -> ADKRunner:
    """Build a runner; SDK is present so _adk_available should be True."""
    return ADKRunner(db=db, agent_id="agent-1", app_name="test-app")


def _fake_part(
    *,
    text: Optional[str] = None,
    function_call: Any = None,
    function_response: Any = None,
    inline_data: Any = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        function_call=function_call,
        function_response=function_response,
        inline_data=inline_data,
    )


def _fake_content(parts: List[Any]) -> SimpleNamespace:
    return SimpleNamespace(parts=parts)


def _fake_event(
    *,
    parts: Optional[List[Any]] = None,
    author: str = "",
    invocation_id: str = "",
    error_message: str = "",
    error_code: str = "",
    actions: Any = None,
    long_running_tool_ids: Any = None,
    usage_metadata: Any = None,
    is_final: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> SimpleNamespace:
    ev = SimpleNamespace(
        content=_fake_content(parts) if parts is not None else None,
        author=author,
        invocation_id=invocation_id,
        error_message=error_message,
        error_code=error_code,
        actions=actions,
        long_running_tool_ids=long_running_tool_ids,
        usage_metadata=usage_metadata,
        is_final_response=lambda: is_final,
    )
    for key, value in (extra or {}).items():
        setattr(ev, key, value)
    return ev


class _FakeRunner:
    """Stand-in for the ADK Runner instance.

    run_async yields the provided events; run_live yields live events; both can
    raise to exercise error-classification branches.
    """

    def __init__(
        self,
        events: Optional[List[Any]] = None,
        *,
        raise_exc: Optional[BaseException] = None,
        live_events: Optional[List[Any]] = None,
    ):
        self.events = events or []
        self.live_events = live_events or []
        self.raise_exc = raise_exc
        self.run_async_calls: List[Dict[str, Any]] = []
        self.run_live_calls: List[Dict[str, Any]] = []
        self.rewind_calls: List[Dict[str, Any]] = []

    async def run_async(self, **kwargs):
        self.run_async_calls.append(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        for ev in self.events:
            yield ev

    async def run_live(self, **kwargs):
        self.run_live_calls.append(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        for ev in self.live_events:
            yield ev

    async def rewind_async(self, **kwargs):
        self.rewind_calls.append(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        return {"ok": True}


async def _collect(agen) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async for item in agen:
        out.append(item)
    return out


# --------------------------------------------------------------------------- #
# Pure helpers: accuracy signals & run-config validation
# --------------------------------------------------------------------------- #


def test_compute_accuracy_signals_is_deterministic_and_order_independent():
    a = compute_adk_accuracy_signals(
        content="  hi  ",
        actions={"b": 1, "a": 2},
        long_running_tool_ids=["t2", "t1", "  "],
    )
    b = compute_adk_accuracy_signals(
        content="hi",
        actions={"a": 2, "b": 1},
        long_running_tool_ids=["t1", "t2"],
    )
    assert a == b
    assert set(a) == {"response_signature", "action_signature"}
    c = compute_adk_accuracy_signals(content="bye", actions={"a": 2, "b": 1})
    assert c["response_signature"] != a["response_signature"]


def test_compute_accuracy_signals_handles_none_and_non_dict_actions():
    sig = compute_adk_accuracy_signals(content=None, actions=None, long_running_tool_ids=None)
    assert sig["response_signature"]
    assert sig["action_signature"]


def test_stable_signature_payload_falls_back_on_unserializable():
    class Boom:
        def __repr__(self):
            return "boom-repr"

    out = adk_mod._stable_signature_payload(Boom())
    assert "boom-repr" in out


def test_validate_run_config_none_returns_none():
    assert validate_adk_run_config_allowlist(None) is None


def test_validate_run_config_accepts_allowed_keys():
    cfg = {"temperature": 0.5, "top_p": 0.9, "max_llm_calls": 10}
    assert validate_adk_run_config_allowlist(cfg) == cfg


def test_validate_run_config_rejects_unknown_keys():
    with pytest.raises(ValueError) as exc:
        validate_adk_run_config_allowlist({"temperature": 0.5, "bogus": 1})
    assert "invalid run_config keys" in str(exc.value)
    assert "bogus" in str(exc.value)


def test_validate_run_config_rejects_non_string_key():
    with pytest.raises(ValueError):
        validate_adk_run_config_allowlist({1: "x"})


def test_validate_run_config_budget_int_type_error():
    with pytest.raises(ValueError) as exc:
        validate_adk_run_config_allowlist({"max_llm_calls": 3.5})
    assert "max_llm_calls" in str(exc.value)


def test_validate_run_config_budget_int_bool_rejected():
    with pytest.raises(ValueError):
        validate_adk_run_config_allowlist({"max_llm_calls": True})


def test_validate_run_config_budget_int_out_of_range():
    with pytest.raises(ValueError) as exc:
        validate_adk_run_config_allowlist({"max_llm_calls": 9999})
    assert "[1, 500]" in str(exc.value)


def test_validate_run_config_budget_float_type_error():
    with pytest.raises(ValueError):
        validate_adk_run_config_allowlist({"temperature": "hot"})


def test_validate_run_config_budget_float_out_of_range():
    with pytest.raises(ValueError) as exc:
        validate_adk_run_config_allowlist({"temperature": 5.0})
    assert "[0.0, 2.0]" in str(exc.value)


def test_validate_run_config_budget_float_bool_rejected():
    with pytest.raises(ValueError):
        validate_adk_run_config_allowlist({"temperature": True})


def test_validate_run_config_accepts_model_dump_object():
    class FakeRunConfig:
        def model_dump(self):
            return {"temperature": 0.3}

    assert validate_adk_run_config_allowlist(FakeRunConfig()) == {"temperature": 0.3}


def test_validate_run_config_model_dump_raises_wrapped():
    class BadRunConfig:
        def model_dump(self):
            raise RuntimeError("kaboom")

    with pytest.raises(ValueError) as exc:
        validate_adk_run_config_allowlist(BadRunConfig())
    assert "invalid run_config object" in str(exc.value)


def test_validate_run_config_non_object_rejected():
    with pytest.raises(ValueError) as exc:
        validate_adk_run_config_allowlist(42)
    assert "must be an object" in str(exc.value)


# --------------------------------------------------------------------------- #
# Static / small helpers
# --------------------------------------------------------------------------- #


async def test_maybe_await_passthrough_and_awaitable():
    assert await ADKRunner._maybe_await(5) == 5

    async def coro():
        return 7

    assert await ADKRunner._maybe_await(coro()) == 7


def test_safe_json_loads_variants():
    assert ADKRunner._safe_json_loads(None, default={"x": 1}) == {"x": 1}
    assert ADKRunner._safe_json_loads("", default=[]) == []
    assert ADKRunner._safe_json_loads('{"a": 1}') == {"a": 1}
    assert ADKRunner._safe_json_loads("not-json", default="fb") == "fb"


def test_serialize_structured_paths():
    assert ADKRunner._serialize_structured(None) is None
    assert ADKRunner._serialize_structured("s") == "s"
    assert ADKRunner._serialize_structured([1, 2]) == [1, 2]

    class WithModelDump:
        def model_dump(self):
            return {"md": 1}

    assert ADKRunner._serialize_structured(WithModelDump()) == {"md": 1}

    class WithDict:
        def dict(self):
            return {"d": 2}

    assert ADKRunner._serialize_structured(WithDict()) == {"d": 2}

    class Plain:
        def __init__(self):
            self.public = 1
            self._private = 2

    assert ADKRunner._serialize_structured(Plain()) == {"public": 1}

    class ReprOnly:
        __slots__ = ()

        def __repr__(self):
            return "repr-only"

    assert ADKRunner._serialize_structured(ReprOnly()) == "repr-only"


def test_serialize_structured_model_dump_falls_through_on_error():
    class BadModelDump:
        def model_dump(self):
            raise ValueError("nope")

        def dict(self):
            return {"fallback": True}

    assert ADKRunner._serialize_structured(BadModelDump()) == {"fallback": True}


def test_preview_truncates():
    assert ADKRunner._preview("short") == "short"
    long = "x" * 300
    out = ADKRunner._preview(long, limit=10)
    assert out.endswith("...")
    assert out.startswith("x" * 10)


def test_normalize_role_mapping():
    assert ADKRunner._normalize_role("") == "user"
    assert ADKRunner._normalize_role("human") == "user"
    assert ADKRunner._normalize_role("assistant") == "model"
    assert ADKRunner._normalize_role("model") == "model"
    assert ADKRunner._normalize_role(None, default="model") == "model"


def test_get_or_create_runtime_service_caches():
    cache: Dict[str, Any] = {}
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return object()

    first = ADKRunner._get_or_create_runtime_service(
        cache=cache, runtime_key="k", factory=factory
    )
    second = ADKRunner._get_or_create_runtime_service(
        cache=cache, runtime_key="k", factory=factory
    )
    assert first is second
    assert calls["n"] == 1


def test_get_google_api_key_lock_is_shared():
    assert ADKRunner._get_google_api_key_lock() is ADKRunner._get_google_api_key_lock()


# --------------------------------------------------------------------------- #
# Initialization
# --------------------------------------------------------------------------- #


def test_init_sdk_available(db_session):
    runner = _make_runner(db_session)
    assert runner._adk_available is True
    assert runner.app_name == "test-app"
    assert runner.agent_id == "agent-1"
    assert runner.is_available is False
    assert runner._session_service is not None
    assert runner._memory_service is not None


def test_init_default_app_name(db_session):
    runner = ADKRunner(db=db_session, agent_id="a", app_name=None)
    assert runner.app_name == "gemini-multi-agent"


def test_init_with_memory_manager_skips_memory_service(db_session):
    sentinel = object()
    runner = ADKRunner(
        db=db_session, agent_id="a", memory_manager=sentinel, app_name="mm-app"
    )
    assert runner.memory_manager is sentinel
    assert runner._memory_service is None


# --------------------------------------------------------------------------- #
# _coerce_adk_agent / _coerce_adk_app / set_agent
# --------------------------------------------------------------------------- #


class _FakeRunnerClass:
    """Replacement for the SDK Runner constructor; records init kwargs."""

    last_kwargs: Optional[Dict[str, Any]] = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self.kwargs = kwargs

    async def run_async(self, **kwargs):  # pragma: no cover - not exercised here
        if False:
            yield {}


def test_coerce_adk_agent_passthrough(db_session):
    runner = _make_runner(db_session)
    plain = object()
    assert runner._coerce_adk_agent(plain) is plain


def test_coerce_adk_agent_none(db_session):
    runner = _make_runner(db_session)
    assert runner._coerce_adk_agent(None) is None


def test_coerce_adk_agent_wrapper_with_get_adk_agent(db_session):
    runner = _make_runner(db_session)
    inner = SimpleNamespace(name="inner-agent")

    class Wrapper:
        def get_adk_agent(self):
            return inner

    assert runner._coerce_adk_agent(Wrapper()) is inner


def test_coerce_adk_agent_wrapper_raises_returns_none(db_session):
    runner = _make_runner(db_session)

    class Wrapper:
        def get_adk_agent(self):
            raise RuntimeError("broken")

    assert runner._coerce_adk_agent(Wrapper()) is None


def test_coerce_adk_app_from_wrapper(db_session):
    runner = _make_runner(db_session)
    fake_app = SimpleNamespace(name="app")

    class Wrapper:
        def get_adk_app(self):
            return fake_app

    out = runner._coerce_adk_app(Wrapper(), SimpleNamespace(name="agent"))
    assert out is fake_app


def test_coerce_adk_app_wrapper_raises_then_attempts_build(db_session):
    runner = _make_runner(db_session)
    coerced_agent = SimpleNamespace(name="agent")

    class Wrapper:
        def get_adk_app(self):
            raise RuntimeError("broken")

    # get_adk_app raises (logged + swallowed) -> falls through to building a
    # real App from the coerced agent. A SimpleNamespace is not a valid ADK
    # agent, so the real App Pydantic model rejects it.
    with pytest.raises(Exception):
        runner._coerce_adk_app(Wrapper(), coerced_agent)


def test_coerce_adk_app_builds_app_with_real_agent(db_session):
    # Build a real ADK LlmAgent so the App fallback path constructs successfully.
    # The real ADK App requires a valid-identifier app name (no hyphens).
    from google.adk.agents import LlmAgent

    runner = ADKRunner(db=db_session, agent_id="agent-1", app_name="test_app")
    agent = LlmAgent(name="real_agent", model="gemini-2.0-flash")

    class Wrapper:
        # No get_adk_app -> code path builds App(name, root_agent) directly.
        pass

    app = runner._coerce_adk_app(Wrapper(), agent)
    assert app is not None
    assert getattr(app, "name", None) == "test_app"
    assert getattr(app, "root_agent", None) is agent


def test_coerce_adk_app_none_when_no_coerced_agent(db_session):
    runner = _make_runner(db_session)

    class Wrapper:
        pass

    assert runner._coerce_adk_app(Wrapper(), None) is None


def test_coerce_adk_app_none_input(db_session):
    runner = _make_runner(db_session)
    assert runner._coerce_adk_app(None, SimpleNamespace()) is None


def test_set_agent_none_raises(db_session):
    runner = _make_runner(db_session)
    runner._RunnerClass = _FakeRunnerClass
    with pytest.raises(ValueError) as exc:
        runner.set_agent(None)
    assert "valid ADK agent instance" in str(exc.value)


def test_set_agent_with_wrapper_builds_runner_via_app(db_session):
    runner = _make_runner(db_session)
    runner._RunnerClass = _FakeRunnerClass
    _FakeRunnerClass.last_kwargs = None

    inner_agent = SimpleNamespace(name="inner")
    fake_app = SimpleNamespace(name="wrapped-app")

    class Wrapper:
        def get_adk_agent(self):
            return inner_agent

        def get_adk_app(self):
            return fake_app

    runner.set_agent(Wrapper())
    assert runner._adk_agent is inner_agent
    assert runner._adk_app is fake_app
    # Runner initialized with app + app_name (recommended ADK path)
    kwargs = _FakeRunnerClass.last_kwargs
    assert kwargs["app"] is fake_app
    assert kwargs["app_name"] == "test-app"
    assert runner.is_available is True


def test_set_agent_with_real_agent_builds_app_path(db_session):
    from google.adk.agents import LlmAgent

    runner = ADKRunner(db=db_session, agent_id="agent-1", app_name="test_app")
    runner._RunnerClass = _FakeRunnerClass
    _FakeRunnerClass.last_kwargs = None

    agent = LlmAgent(name="real_agent", model="gemini-2.0-flash")

    class Wrapper:
        def get_adk_agent(self):
            return agent

        def get_adk_app(self):
            return None  # no app -> _coerce_adk_app builds App from coerced agent

    runner.set_agent(Wrapper())
    kwargs = _FakeRunnerClass.last_kwargs
    # _coerce_adk_app builds an App from the coerced agent, so the recommended
    # app path is taken (app + app_name).
    assert kwargs["app"] is not None
    assert kwargs["app_name"] == "test_app"
    assert runner._adk_agent is agent


def test_set_agent_noop_when_adk_unavailable(db_session):
    runner = _make_runner(db_session)
    runner._adk_available = False
    # Should silently return without constructing a runner
    runner.set_agent(SimpleNamespace())
    assert runner._adk_runner is None


def test_init_binds_agent_when_passed(db_session):
    # adk_agent passed at construction triggers set_agent if SDK available.
    inner_agent = SimpleNamespace(name="inner")
    fake_app = SimpleNamespace(name="wrapped-app")

    class Wrapper:
        def get_adk_agent(self):
            return inner_agent

        def get_adk_app(self):
            return fake_app

    # Patch the Runner class on the instance is not possible pre-init; instead
    # verify set_agent path by constructing then re-binding with a fake runner.
    runner = ADKRunner(db=db_session, agent_id="a", app_name="test-app")
    runner._RunnerClass = _FakeRunnerClass
    runner.set_agent(Wrapper())
    assert runner._adk_agent is inner_agent


# --------------------------------------------------------------------------- #
# Runtime-unavailable error builder
# --------------------------------------------------------------------------- #


def test_build_runtime_unavailable_error_defaults(db_session):
    runner = _make_runner(db_session)
    err = runner._build_runtime_unavailable_error(stage="", session_id="s1")
    assert err["error_code"] == "ADK_RUNTIME_UNAVAILABLE"
    assert err["stage"] == "run"
    assert err["is_final"] is True
    assert err["retryable"] is False
    assert err["session_id"] == "s1"
    assert "unavailable" in err["error"]


def test_build_runtime_unavailable_error_with_detail(db_session):
    runner = _make_runner(db_session)
    err = runner._build_runtime_unavailable_error(
        stage="run_live", session_id="s2", detail="LiveRequestQueue missing"
    )
    assert err["stage"] == "run_live"
    assert err["error"] == "LiveRequestQueue missing"


# --------------------------------------------------------------------------- #
# _build_new_message (uses real Content/Part)
# --------------------------------------------------------------------------- #


def test_build_new_message_from_text(db_session):
    runner = _make_runner(db_session)
    content = runner._build_new_message(input_data="hello", input_message=None)
    assert content.role == "user"
    assert content.parts[0].text == "hello"


def test_build_new_message_empty_text_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._build_new_message(input_data="   ", input_message=None)
    assert "input is required" in str(exc.value)


def test_build_new_message_from_message_dict_with_parts(db_session):
    runner = _make_runner(db_session)
    content = runner._build_new_message(
        input_data=None,
        input_message={"role": "assistant", "parts": [{"text": "hi"}, "world"]},
    )
    assert content.role == "model"
    assert content.parts[0].text == "hi"
    assert content.parts[1].text == "world"


def test_build_new_message_message_dict_uses_text_fallback(db_session):
    runner = _make_runner(db_session)
    content = runner._build_new_message(
        input_data="fallback-input",
        input_message={"role": "user", "text": "explicit"},
    )
    assert content.parts[0].text == "explicit"


def test_build_new_message_empty_parts_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._build_new_message(
            input_data=None, input_message={"role": "user", "parts": []}
        )
    assert "non-empty list" in str(exc.value)


def test_build_new_message_invalid_part_type_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._build_new_message(
            input_data=None, input_message={"role": "user", "parts": [123]}
        )
    assert "must be an object" in str(exc.value)


def test_build_new_message_invalid_part_payload_raises(db_session):
    runner = _make_runner(db_session)
    # A dict part with an invalid field type fails Part.model_validate, which the
    # runner wraps as "invalid part payload".
    with pytest.raises(ValueError) as exc:
        runner._build_new_message(
            input_data=None,
            input_message={"role": "user", "parts": [{"text": 123}]},
        )
    assert "invalid part payload" in str(exc.value)


# --------------------------------------------------------------------------- #
# _extract_input_preview
# --------------------------------------------------------------------------- #


def test_extract_input_preview_prefers_input_data():
    assert (
        ADKRunner._extract_input_preview(input_data="  direct ", input_message=None)
        == "direct"
    )


def test_extract_input_preview_non_dict_message():
    assert ADKRunner._extract_input_preview(input_data=None, input_message=None) == ""


def test_extract_input_preview_from_parts_and_function_response():
    msg = {
        "parts": [
            "string part",
            {"text": "dict text"},
            {"function_response": {"name": "f"}},
            {"other": 1},
            5,
        ]
    }
    out = ADKRunner._extract_input_preview(input_data=None, input_message=msg)
    assert "string part" in out
    assert "dict text" in out
    assert "[function_response]" in out


def test_extract_input_preview_message_text_when_parts_not_list():
    msg = {"text": "direct-msg", "parts": "not-a-list"}
    out = ADKRunner._extract_input_preview(input_data=None, input_message=msg)
    assert out == "direct-msg"


# --------------------------------------------------------------------------- #
# Event extraction helpers
# --------------------------------------------------------------------------- #


def test_extract_event_text_combines_text_call_and_result(db_session):
    runner = _make_runner(db_session)
    parts = [
        _fake_part(text="answer"),
        _fake_part(function_call=SimpleNamespace(name="search")),
        _fake_part(function_response=SimpleNamespace(result="done")),
    ]
    ev = _fake_event(parts=parts)
    text = runner._extract_event_text(ev)
    assert "answer" in text
    assert "[tool_call] search" in text
    assert "[tool_result]" in text


def test_extract_event_text_no_content_returns_empty(db_session):
    runner = _make_runner(db_session)
    assert runner._extract_event_text(_fake_event(parts=None)) == ""


def test_extract_event_function_calls(db_session):
    runner = _make_runner(db_session)
    fc = SimpleNamespace(id="c1", name="tool", args={"q": 1}, will_continue=True)
    ev = _fake_event(parts=[_fake_part(function_call=fc)])
    calls = runner._extract_event_function_calls(ev)
    assert calls == [
        {"id": "c1", "name": "tool", "args": {"q": 1}, "will_continue": True}
    ]


def test_extract_event_function_calls_dict_part(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=[{"function_call": {"id": "x", "name": "n", "args": {}}}])
    calls = runner._extract_event_function_calls(ev)
    assert calls[0]["id"] == "x"
    assert calls[0]["will_continue"] is None


def test_extract_event_function_calls_no_content(db_session):
    runner = _make_runner(db_session)
    assert runner._extract_event_function_calls(_fake_event(parts=None)) == []


def test_extract_event_function_calls_non_dict_payload_skipped(db_session):
    runner = _make_runner(db_session)

    class ListDump:
        # _serialize_structured returns a list -> not a dict -> skipped
        def model_dump(self):
            return ["not", "a", "dict"]

    ev = _fake_event(parts=[_fake_part(function_call=ListDump())])
    assert runner._extract_event_function_calls(ev) == []


def test_extract_event_function_responses_non_dict_payload_skipped(db_session):
    runner = _make_runner(db_session)

    class ListDump:
        def model_dump(self):
            return ["x"]

    ev = _fake_event(parts=[_fake_part(function_response=ListDump())])
    assert runner._extract_event_function_responses(ev) == []


def test_extract_event_actions_non_dict_payload(db_session):
    runner = _make_runner(db_session)

    class ListActions:
        def model_dump(self):
            return ["x"]

    assert runner._extract_event_actions(_fake_event(actions=ListActions())) == {}


def test_extract_event_function_responses(db_session):
    runner = _make_runner(db_session)
    fr = SimpleNamespace(id="r1", name="tool", response={"ok": True}, will_continue=False)
    ev = _fake_event(parts=[_fake_part(function_response=fr)])
    resps = runner._extract_event_function_responses(ev)
    assert resps[0]["id"] == "r1"
    assert resps[0]["response"] == {"ok": True}
    assert resps[0]["will_continue"] is False


def test_extract_event_function_responses_no_content(db_session):
    runner = _make_runner(db_session)
    assert runner._extract_event_function_responses(_fake_event(parts=None)) == []


def test_count_event_inline_data_parts(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(
        parts=[
            _fake_part(inline_data=SimpleNamespace(mime_type="image/png")),
            {"inline_data": {"mime_type": "audio/wav"}},
            _fake_part(text="t"),
        ]
    )
    assert runner._count_event_inline_data_parts(ev) == 2
    assert runner._count_event_inline_data_parts(_fake_event(parts=None)) == 0


def test_extract_event_actions_picks_known_keys(db_session):
    runner = _make_runner(db_session)
    actions = SimpleNamespace(
        transfer_to_agent="other",
        escalate=True,
        state_delta={"k": "v"},
        empty_field="",
        none_field=None,
        unrelated="ignored-key-not-in-allowlist",
    )
    ev = _fake_event(actions=actions)
    picked = runner._extract_event_actions(ev)
    assert picked["transfer_to_agent"] == "other"
    assert picked["escalate"] is True
    assert picked["state_delta"] == {"k": "v"}
    assert "empty_field" not in picked
    assert "unrelated" not in picked


def test_extract_event_actions_none(db_session):
    runner = _make_runner(db_session)
    assert runner._extract_event_actions(_fake_event(actions=None)) == {}


def test_extract_event_long_running_tools_variants(db_session):
    runner = _make_runner(db_session)
    assert runner._extract_event_long_running_tools(
        _fake_event(long_running_tool_ids=None)
    ) == []
    assert runner._extract_event_long_running_tools(
        _fake_event(long_running_tool_ids={"b", "a", "  "})
    ) == ["a", "b"]
    assert runner._extract_event_long_running_tools(
        _fake_event(long_running_tool_ids=["t1", "t2", "  "])
    ) == ["t1", "t2"]
    assert runner._extract_event_long_running_tools(
        _fake_event(long_running_tool_ids="single")
    ) == ["single"]


# --------------------------------------------------------------------------- #
# _convert_event: error / final / chunk / action / none
# --------------------------------------------------------------------------- #


def test_convert_event_error(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(error_message="boom", error_code="E1", invocation_id="inv1")
    out = runner._convert_event(ev)
    assert out["type"] == "error"
    assert out["error"] == "boom"
    assert out["error_code"] == "E1"
    assert out["invocation_id"] == "inv1"


def test_convert_event_final(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(
        parts=[_fake_part(text="final answer")],
        author="agent",
        is_final=True,
        usage_metadata=SimpleNamespace(total=10),
    )
    out = runner._convert_event(ev)
    assert out["type"] == "final"
    assert out["content"] == "final answer"
    assert out["author"] == "agent"
    assert out["is_final"] is True
    assert isinstance(out["usage"], dict)


def test_convert_event_chunk(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=[_fake_part(text="streaming text")], author="agent")
    out = runner._convert_event(ev)
    assert out["type"] == "chunk"
    assert out["content"] == "streaming text"
    assert out["is_final"] is False


def test_convert_event_is_final_response_raises_treated_as_false(db_session):
    runner = _make_runner(db_session)

    def _raise():
        raise RuntimeError("bad")

    ev = _fake_event(parts=[_fake_part(text="x")])
    ev.is_final_response = _raise
    out = runner._convert_event(ev)
    assert out["type"] == "chunk"


def test_convert_event_action_only_tool_markers(db_session):
    runner = _make_runner(db_session)
    fc = SimpleNamespace(id="c", name="tool", args={}, will_continue=None)
    ev = _fake_event(
        parts=[_fake_part(function_call=fc)],
        actions=SimpleNamespace(transfer_to_agent="other"),
    )
    out = runner._convert_event(ev)
    assert out["type"] == "action"
    assert "function_calls" in out
    assert out["actions"]["transfer_to_agent"] == "other"


def test_convert_event_action_from_invocation_only(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=None, invocation_id="inv-x")
    out = runner._convert_event(ev)
    assert out["type"] == "action"
    assert out["invocation_id"] == "inv-x"


def test_convert_event_returns_none_when_empty(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=None)
    assert runner._convert_event(ev) is None


# --------------------------------------------------------------------------- #
# _convert_live_event
# --------------------------------------------------------------------------- #


def test_convert_live_event_turn_complete_becomes_final(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=[_fake_part(text="partial")])
    ev.partial = True
    ev.turn_complete = True
    ev.interrupted = False
    out = runner._convert_live_event(ev)
    assert out["turn_complete"] is True
    assert out["is_final"] is True
    assert out["type"] == "final"
    assert "response_signature" in out
    assert "action_signature" in out


def test_convert_live_event_non_final_keeps_partial_flags(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=[_fake_part(text="chunk")])
    ev.partial = True
    ev.turn_complete = False
    ev.interrupted = False
    out = runner._convert_live_event(ev)
    assert out["partial"] is True
    assert out["is_final"] is False
    assert "response_signature" not in out


def test_convert_live_event_empty_event_becomes_live_event(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=None)
    ev.partial = False
    ev.turn_complete = False
    ev.interrupted = False
    out = runner._convert_live_event(ev)
    assert out["type"] == "live_event"


def test_convert_live_event_inline_data_and_transcriptions(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=[_fake_part(inline_data=SimpleNamespace(mime_type="image/png"))])
    ev.partial = False
    ev.turn_complete = False
    ev.interrupted = False
    ev.input_transcription = SimpleNamespace(text="hi")
    ev.output_transcription = SimpleNamespace(text="bye")
    ev.live_session_resumption_update = SimpleNamespace(handle="h1")
    out = runner._convert_live_event(ev)
    assert out["inline_data_parts"] == 1
    assert out["input_transcription"]
    assert out["output_transcription"]
    assert out["live_session_resumption_update"]


# --------------------------------------------------------------------------- #
# _build_run_config (real RunConfig)
# --------------------------------------------------------------------------- #


def test_build_run_config_none(db_session):
    runner = _make_runner(db_session)
    assert runner._build_run_config(None) is None


def test_build_run_config_dict_to_runconfig(db_session):
    runner = _make_runner(db_session)
    rc = runner._build_run_config({"max_llm_calls": 5})
    assert rc.__class__.__name__ == "RunConfig"
    assert rc.max_llm_calls == 5


def test_build_run_config_runconfig_instance_rejected_by_allowlist(db_session):
    # A real ADK RunConfig dumps many default fields (e.g. avatar_config) that
    # are not on the backend allowlist, so passing an instance through
    # _build_run_config validates -> raises before the isinstance passthrough.
    runner = _make_runner(db_session)
    instance = runner._RunConfigClass(max_llm_calls=3)
    with pytest.raises(ValueError):
        runner._build_run_config(instance)


def test_build_run_config_dict_invalid_budget_wrapped(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError):
        runner._build_run_config({"temperature": 9.9})


def test_build_run_config_rejects_unknown_keys(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError):
        runner._build_run_config({"not_allowed": 1})


# --------------------------------------------------------------------------- #
# Session persistence: _get_or_create_session
# --------------------------------------------------------------------------- #


async def test_get_or_create_session_creates_and_updates(db_session):
    runner = _make_runner(db_session)
    created = await runner._get_or_create_session(user_id="u1", session_id="s1")
    assert created["session_id"] == "s1"
    assert created["metadata"]["app_name"] == "test-app"

    row = (
        db_session.query(ADKSession)
        .filter(ADKSession.user_id == "u1", ADKSession.session_id == "s1")
        .first()
    )
    assert row is not None

    updated = await runner._get_or_create_session(
        user_id="u1", session_id="s1", extra_metadata={"last_invocation_id": "inv9"}
    )
    assert updated["metadata"]["last_invocation_id"] == "inv9"


async def test_get_or_create_session_skips_none_extra_metadata(db_session):
    runner = _make_runner(db_session)
    out = await runner._get_or_create_session(
        user_id="u1",
        session_id="s2",
        extra_metadata={"present": "yes", "absent": None},
    )
    assert out["metadata"]["present"] == "yes"
    assert "absent" not in out["metadata"]


# --------------------------------------------------------------------------- #
# run(): runtime unavailable, success aggregation, error classification
# --------------------------------------------------------------------------- #


async def test_run_runtime_unavailable_yields_error(db_session):
    runner = _make_runner(db_session)
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hi")
    )
    assert len(events) == 1
    assert events[0]["error_code"] == "ADK_RUNTIME_UNAVAILABLE"
    assert (
        db_session.query(ADKSession)
        .filter(ADKSession.session_id == "s1")
        .first()
        is not None
    )


async def test_run_success_aggregates_chunks_and_final(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[
            _fake_event(parts=[_fake_part(text="chunk-1")], author="a"),
            _fake_event(parts=[_fake_part(text="chunk-2")], author="a"),
            _fake_event(
                parts=[_fake_part(text="FINAL")],
                author="a",
                is_final=True,
                usage_metadata=SimpleNamespace(total=3),
                invocation_id="inv-1",
            ),
        ]
    )
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hello")
    )
    types = [e["type"] for e in events]
    assert "chunk" in types
    final = [e for e in events if e["type"] == "content"][0]
    assert final["content"] == "FINAL"
    assert final["is_final"] is True
    assert final["invocation_id"] == "inv-1"
    assert "response_signature" in final
    assert isinstance(runner._adk_runner.run_async_calls[0], dict)


async def test_run_uses_chunk_buffer_when_no_final_text(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[
            _fake_event(parts=[_fake_part(text="only-chunk")], author="a"),
            _fake_event(parts=[_fake_part(text="")], author="a", is_final=True),
        ]
    )
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hello")
    )
    final = [e for e in events if e["type"] == "content"][0]
    assert final["content"] == "only-chunk"


async def test_run_propagates_error_event(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[_fake_event(error_message="upstream failed", error_code="E_UP")]
    )
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hello")
    )
    err = [e for e in events if e["type"] == "error"]
    assert err
    assert err[0]["error"] == "upstream failed"


async def test_run_emits_action_event(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[
            _fake_event(parts=None, invocation_id="inv-act"),
            _fake_event(parts=[_fake_part(text="done")], author="a", is_final=True),
        ]
    )
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hello")
    )
    assert any(e["type"] == "action" for e in events)


async def test_run_invalid_request_value_error(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(events=[])
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="   ")
    )
    assert len(events) == 1
    assert events[0]["error_code"] == "ADK_INVALID_REQUEST"
    assert events[0]["invalid_request"] is True


async def test_run_unexpected_exception_classified_as_run_failed(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(raise_exc=RuntimeError("driver exploded"))
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hello")
    )
    assert len(events) == 1
    assert events[0]["error_code"] == "ADK_RUN_FAILED"
    assert "driver exploded" in events[0]["error"]


async def test_run_aggregates_actions_and_long_running_into_final(db_session):
    runner = _make_runner(db_session)
    action_event = _fake_event(
        parts=None,
        invocation_id="inv-agg",
        actions=SimpleNamespace(transfer_to_agent="next"),
        long_running_tool_ids=["lrt-1", "lrt-2"],
    )
    runner._adk_runner = _FakeRunner(
        events=[
            action_event,
            _fake_event(parts=[_fake_part(text="DONE")], author="a", is_final=True),
        ]
    )
    events = await _collect(
        runner.run(user_id="u1", session_id="s1", input_data="hi")
    )
    final = [e for e in events if e["type"] == "content"][0]
    assert final["invocation_id"] == "inv-agg"
    assert final["actions"] == {"transfer_to_agent": "next"}
    assert final["long_running_tool_ids"] == ["lrt-1", "lrt-2"]
    # Persisted metadata carries the long-running tool ids
    row = (
        db_session.query(ADKSession)
        .filter(ADKSession.session_id == "s1")
        .first()
    )
    meta = json.loads(row.metadata_json)
    assert meta["last_long_running_tool_ids"] == ["lrt-1", "lrt-2"]


async def test_run_with_state_delta_and_invocation_id(db_session):
    runner = _make_runner(db_session)
    fake = _FakeRunner(
        events=[_fake_event(parts=[_fake_part(text="ok")], author="a", is_final=True)]
    )
    runner._adk_runner = fake
    await _collect(
        runner.run(
            user_id="u1",
            session_id="s1",
            input_data="hi",
            state_delta={"k": "v"},
            invocation_id="inv-resume",
        )
    )
    call = fake.run_async_calls[0]
    assert call["state_delta"] == {"k": "v"}
    assert call["invocation_id"] == "inv-resume"


async def test_run_with_google_api_key_uses_lock_and_restores_env(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[_fake_event(parts=[_fake_part(text="ok")], author="a", is_final=True)]
    )
    os.environ.pop("GOOGLE_API_KEY", None)
    events = await _collect(
        runner.run(
            user_id="u1",
            session_id="s1",
            input_data="hi",
            google_api_key="secret-key",
        )
    )
    assert any(e["type"] == "content" for e in events)
    assert "GOOGLE_API_KEY" not in os.environ


# --------------------------------------------------------------------------- #
# run_once()
# --------------------------------------------------------------------------- #


async def test_run_once_returns_final_text_and_signals(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[
            _fake_event(parts=[_fake_part(text="partial")], author="a"),
            _fake_event(
                parts=[_fake_part(text="DONE")],
                author="a",
                is_final=True,
                usage_metadata=SimpleNamespace(total=2),
            ),
        ]
    )
    result = await runner.run_once(user_id="u1", session_id="s1", input_data="hi")
    assert result["text"] == "DONE"
    assert result["event_count"] >= 2
    assert result["session_id"] == "s1"
    assert result["response_signature"]
    assert result["action_signature"]


async def test_run_once_aggregates_actions_and_long_running(db_session):
    runner = _make_runner(db_session)
    action_event = _fake_event(
        parts=None,
        invocation_id="inv-q",
        actions=SimpleNamespace(escalate=True),
        long_running_tool_ids=["lrt-x"],
    )
    runner._adk_runner = _FakeRunner(
        events=[
            action_event,
            _fake_event(parts=[_fake_part(text="ANSWER")], author="a", is_final=True),
        ]
    )
    result = await runner.run_once(user_id="u1", session_id="s1", input_data="hi")
    assert result["invocation_id"] == "inv-q"
    assert result["actions"] == {"escalate": True}
    assert result["long_running_tool_ids"] == ["lrt-x"]
    assert result["text"] == "ANSWER"


async def test_run_once_raises_runtime_error_on_runner_error(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(
        events=[_fake_event(error_message="explode", error_code="E")]
    )
    with pytest.raises(RuntimeError) as exc:
        await runner.run_once(user_id="u1", session_id="s1", input_data="hi")
    assert "explode" in str(exc.value)


async def test_run_once_raises_value_error_on_invalid_request(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(events=[])
    with pytest.raises(ValueError):
        await runner.run_once(user_id="u1", session_id="s1", input_data="   ")


async def test_run_once_runtime_unavailable_raises_runtime_error(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(RuntimeError):
        await runner.run_once(user_id="u1", session_id="s1", input_data="hi")


# --------------------------------------------------------------------------- #
# _coerce_live_request and _enqueue_live_requests
# --------------------------------------------------------------------------- #


def test_coerce_live_request_text(db_session):
    runner = _make_runner(db_session)
    req = runner._coerce_live_request(item={"kind": "text", "text": "hi"})
    assert req.content is not None


def test_coerce_live_request_text_missing_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._coerce_live_request(item={"kind": "text", "text": "  "})
    assert "text live request requires text" in str(exc.value)


def test_coerce_live_request_activity_start_and_end(db_session):
    runner = _make_runner(db_session)
    start = runner._coerce_live_request(item={"kind": "activity_start"})
    assert start.activity_start is not None
    end = runner._coerce_live_request(item={"kind": "end"})
    assert end.activity_end is not None


def test_coerce_live_request_both_activities_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._coerce_live_request(item={"activity_start": {}, "activity_end": {}})
    assert "cannot include both" in str(exc.value)


def test_coerce_live_request_close(db_session):
    runner = _make_runner(db_session)
    req = runner._coerce_live_request(item={"kind": "close"})
    assert req.close is True


def test_coerce_live_request_blob_from_string_data(db_session):
    runner = _make_runner(db_session)
    req = runner._coerce_live_request(
        item={"kind": "blob", "mime_type": "audio/pcm", "data": "AAAA"}
    )
    assert req.blob is not None
    assert req.blob.mime_type == "audio/pcm"


def test_coerce_live_request_blob_from_bytes(db_session):
    runner = _make_runner(db_session)
    raw = b"\x00\x01\x02"
    req = runner._coerce_live_request(
        item={"kind": "audio", "mime_type": "audio/pcm", "data": raw}
    )
    # The runner base64-encodes bytes before constructing the Blob, and the real
    # ADK Blob decodes the base64 string back to raw bytes for the .data field.
    assert req.blob.data == raw
    assert req.blob.mime_type == "audio/pcm"


def test_coerce_live_request_blob_missing_mime_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._coerce_live_request(item={"kind": "blob", "data": "AAAA"})
    assert "requires mime_type" in str(exc.value)


def test_coerce_live_request_blob_bad_data_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._coerce_live_request(
            item={"kind": "blob", "mime_type": "audio/pcm", "data": 123}
        )
    assert "base64 data" in str(exc.value)


def test_build_live_blob_payload_invalid_raises(db_session):
    runner = _make_runner(db_session)
    # Directly exercise _build_live_blob_payload's error wrapping: an invalid
    # mime_type type fails the real Blob.model_validate.
    with pytest.raises(ValueError) as exc:
        runner._build_live_blob_payload({"mime_type": 123, "data": "AAAA"})
    assert "invalid live blob payload" in str(exc.value)


def test_build_live_blob_payload_valid(db_session):
    runner = _make_runner(db_session)
    blob = runner._build_live_blob_payload({"mime_type": "audio/pcm", "data": "AAAA"})
    assert blob.mime_type == "audio/pcm"


def test_coerce_live_request_function_response(db_session):
    runner = _make_runner(db_session)
    req = runner._coerce_live_request(
        item={
            "kind": "function_response",
            "function_response": {"name": "f", "response": {"ok": True}},
        }
    )
    assert req.content is not None


def test_coerce_live_request_function_response_invalid_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(ValueError) as exc:
        runner._coerce_live_request(
            item={"kind": "function_response", "function_response": "bad"}
        )
    assert "requires function_response object" in str(exc.value)


def test_coerce_live_request_explicit_close_key(db_session):
    runner = _make_runner(db_session)
    req = runner._coerce_live_request(item={"close": True})
    assert req.close is True


class _FakeQueue:
    def __init__(self):
        self.sent: List[Any] = []
        self.closed = False

    def send(self, item):
        self.sent.append(item)

    def close(self):
        self.closed = True


def test_enqueue_live_requests_explicit_list(db_session):
    runner = _make_runner(db_session)
    queue = _FakeQueue()
    runner._enqueue_live_requests(
        live_request_queue=queue,
        input_data=None,
        live_requests=[{"kind": "text", "text": "a"}, {"kind": "close"}],
        close_queue=True,
    )
    assert len(queue.sent) == 2
    assert queue.closed is True


def test_enqueue_live_requests_falls_back_to_input_data(db_session):
    runner = _make_runner(db_session)
    queue = _FakeQueue()
    runner._enqueue_live_requests(
        live_request_queue=queue,
        input_data="hello",
        live_requests=None,
        close_queue=False,
    )
    assert len(queue.sent) == 1
    assert queue.closed is False


def test_enqueue_live_requests_invalid_item_raises(db_session):
    runner = _make_runner(db_session)
    queue = _FakeQueue()
    with pytest.raises(ValueError) as exc:
        runner._enqueue_live_requests(
            live_request_queue=queue,
            input_data=None,
            live_requests=["not-a-dict"],
            close_queue=False,
        )
    assert "must be an object" in str(exc.value)


# --------------------------------------------------------------------------- #
# run_live()
# --------------------------------------------------------------------------- #


async def test_run_live_runtime_unavailable(db_session):
    runner = _make_runner(db_session)
    events = await _collect(
        runner.run_live(user_id="u1", session_id="s1", input_data="hi")
    )
    assert events[0]["error_code"] == "ADK_RUNTIME_UNAVAILABLE"
    assert events[0]["stage"] == "run_live"


async def test_run_live_queue_class_unavailable(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner()
    runner._LiveRequestQueueClass = None
    events = await _collect(
        runner.run_live(user_id="u1", session_id="s1", input_data="hi")
    )
    assert events[0]["error_code"] == "ADK_RUNTIME_UNAVAILABLE"
    assert "LiveRequestQueue" in events[0]["error"]


async def test_run_live_success_and_max_events(db_session):
    runner = _make_runner(db_session)
    live_events = []
    for i in range(3):
        ev = _fake_event(parts=[_fake_part(text=f"live-{i}")], author="a")
        ev.partial = False
        ev.turn_complete = False
        ev.interrupted = False
        live_events.append(ev)
    runner._adk_runner = _FakeRunner(live_events=live_events)

    events = await _collect(
        runner.run_live(
            user_id="u1",
            session_id="s1",
            input_data="hi",
            max_events=2,
        )
    )
    assert len(events) == 2
    row = (
        db_session.query(ADKSession)
        .filter(ADKSession.session_id == "s1")
        .first()
    )
    assert row is not None
    meta = json.loads(row.metadata_json)
    assert meta["last_live_event_count"] == 2


async def test_run_live_aggregates_metadata(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(
        parts=[_fake_part(text="live-chunk")],
        author="a",
        invocation_id="inv-live",
        actions=SimpleNamespace(transfer_to_agent="peer"),
        long_running_tool_ids=["lrt-live"],
    )
    ev.partial = False
    ev.turn_complete = True
    ev.interrupted = False
    runner._adk_runner = _FakeRunner(live_events=[ev])

    events = await _collect(
        runner.run_live(user_id="u1", session_id="s1", input_data="hi")
    )
    assert events
    row = (
        db_session.query(ADKSession)
        .filter(ADKSession.session_id == "s1")
        .first()
    )
    meta = json.loads(row.metadata_json)
    assert meta["last_invocation_id"] == "inv-live"
    assert meta["last_actions"] == {"transfer_to_agent": "peer"}
    assert meta["last_long_running_tool_ids"] == ["lrt-live"]
    assert meta["last_live_event_count"] == 1


async def test_run_live_invalid_request(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(live_events=[])
    events = await _collect(
        runner.run_live(
            user_id="u1",
            session_id="s1",
            live_requests=["not-a-dict"],
        )
    )
    assert events[0]["error_code"] == "ADK_INVALID_REQUEST"
    assert events[0]["stage"] == "run_live"


async def test_run_live_unexpected_exception(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner(raise_exc=RuntimeError("live exploded"))
    events = await _collect(
        runner.run_live(user_id="u1", session_id="s1", input_data="hi")
    )
    assert events[0]["error_code"] == "ADK_RUN_LIVE_FAILED"


async def test_run_live_with_api_key_lock(db_session):
    runner = _make_runner(db_session)
    ev = _fake_event(parts=[_fake_part(text="x")], author="a")
    ev.partial = False
    ev.turn_complete = True
    ev.interrupted = False
    runner._adk_runner = _FakeRunner(live_events=[ev])
    os.environ.pop("GOOGLE_API_KEY", None)
    events = await _collect(
        runner.run_live(
            user_id="u1",
            session_id="s1",
            input_data="hi",
            google_api_key="k",
        )
    )
    assert events
    assert "GOOGLE_API_KEY" not in os.environ


# --------------------------------------------------------------------------- #
# rewind()
# --------------------------------------------------------------------------- #


async def test_rewind_requires_target(db_session):
    runner = _make_runner(db_session)
    runner._adk_runner = _FakeRunner()
    with pytest.raises(ValueError) as exc:
        await runner.rewind(
            user_id="u1", session_id="s1", rewind_before_invocation_id="  "
        )
    assert "rewind_before_invocation_id is required" in str(exc.value)


async def test_rewind_unavailable_raises(db_session):
    runner = _make_runner(db_session)
    with pytest.raises(RuntimeError) as exc:
        await runner.rewind(
            user_id="u1", session_id="s1", rewind_before_invocation_id="inv1"
        )
    assert "cannot rewind" in str(exc.value)


async def test_rewind_success_persists_metadata(db_session):
    runner = _make_runner(db_session)
    fake = _FakeRunner()
    runner._adk_runner = fake
    result = await runner.rewind(
        user_id="u1", session_id="s1", rewind_before_invocation_id="inv-7"
    )
    assert result["ok"] is True
    assert result["rewind_before_invocation_id"] == "inv-7"
    assert fake.rewind_calls[0]["rewind_before_invocation_id"] == "inv-7"
    row = (
        db_session.query(ADKSession)
        .filter(ADKSession.session_id == "s1")
        .first()
    )
    meta = json.loads(row.metadata_json)
    assert meta["last_rewind_before_invocation_id"] == "inv-7"


async def test_rewind_success_with_api_key_lock(db_session):
    runner = _make_runner(db_session)
    fake = _FakeRunner()
    runner._adk_runner = fake
    os.environ.pop("GOOGLE_API_KEY", None)
    result = await runner.rewind(
        user_id="u1",
        session_id="s1",
        rewind_before_invocation_id="inv-9",
        google_api_key="key",
    )
    assert result["ok"] is True
    assert "GOOGLE_API_KEY" not in os.environ


# --------------------------------------------------------------------------- #
# list_sessions / get_session_snapshot / _serialize_session_snapshot
# --------------------------------------------------------------------------- #


def test_serialize_session_snapshot_dict(db_session):
    runner = _make_runner(db_session)
    raw = SimpleNamespace(
        id="sess-1",
        app_name="test-app",
        user_id="u1",
        state={"flag": True},
        events=[{"e": 1}, {"e": 2}],
        last_update_time=123,
    )
    snap = runner._serialize_session_snapshot(raw)
    assert snap["session_id"] == "sess-1"
    assert snap["event_count"] == 2
    assert snap["state"] == {"flag": True}


def test_serialize_session_snapshot_non_dict(db_session):
    runner = _make_runner(db_session)

    class NoDict:
        __slots__ = ()

        def __repr__(self):
            return "scalar"

    snap = runner._serialize_session_snapshot(NoDict())
    assert snap == {"raw": "scalar"}


async def test_list_sessions_merges_db_and_runtime(db_session):
    runner = _make_runner(db_session)
    await runner._get_or_create_session(user_id="u1", session_id="s1")
    await runner._get_or_create_session(user_id="u1", session_id="s2")

    runtime_sessions = [
        SimpleNamespace(
            id="s1",
            app_name="test-app",
            user_id="u1",
            state={"x": 1},
            events=[{"e": 1}],
            last_update_time=999,
        )
    ]

    class FakeSessionService:
        async def list_sessions(self, *, app_name, user_id):
            return SimpleNamespace(sessions=runtime_sessions)

    runner._session_service = FakeSessionService()
    out = await runner.list_sessions(user_id="u1")
    by_id = {item["session_id"]: item for item in out}
    assert by_id["s1"]["runtime_available"] is True
    assert by_id["s1"]["runtime_event_count"] == 1
    assert by_id["s2"]["runtime_available"] is False


async def test_list_sessions_runtime_failure_is_swallowed(db_session):
    runner = _make_runner(db_session)
    await runner._get_or_create_session(user_id="u1", session_id="s1")

    class BrokenSessionService:
        async def list_sessions(self, *, app_name, user_id):
            raise RuntimeError("svc down")

    runner._session_service = BrokenSessionService()
    out = await runner.list_sessions(user_id="u1")
    assert len(out) == 1
    assert out[0]["runtime_available"] is False


async def test_get_session_snapshot_missing_returns_none(db_session):
    runner = _make_runner(db_session)
    assert await runner.get_session_snapshot(user_id="u1", session_id="") is None
    assert await runner.get_session_snapshot(user_id="u1", session_id="nope") is None


async def test_get_session_snapshot_with_runtime(db_session):
    runner = _make_runner(db_session)
    await runner._get_or_create_session(user_id="u1", session_id="s1")

    runtime = SimpleNamespace(
        id="s1",
        app_name="test-app",
        user_id="u1",
        state={"k": "v"},
        events=[{"e": 1}, {"e": 2}],
        last_update_time=42,
    )

    class FakeSessionService:
        async def get_session(self, *, app_name, user_id, session_id):
            return runtime

    runner._session_service = FakeSessionService()
    snap = await runner.get_session_snapshot(user_id="u1", session_id="s1")
    assert snap["runtime_available"] is True
    assert snap["runtime_event_count"] == 2
    assert snap["runtime_state"] == {"k": "v"}
    assert len(snap["events"]) == 2


async def test_get_session_snapshot_runtime_failure_swallowed(db_session):
    runner = _make_runner(db_session)
    await runner._get_or_create_session(user_id="u1", session_id="s1")

    class BrokenSessionService:
        async def get_session(self, *, app_name, user_id, session_id):
            raise RuntimeError("svc down")

    runner._session_service = BrokenSessionService()
    snap = await runner.get_session_snapshot(user_id="u1", session_id="s1")
    assert snap["runtime_available"] is False
    assert snap["events"] == []


# --------------------------------------------------------------------------- #
# _ensure_adk_session: create-if-missing
# --------------------------------------------------------------------------- #


async def test_ensure_adk_session_creates_when_missing(db_session):
    runner = _make_runner(db_session)
    created: List[Dict[str, Any]] = []

    class FakeSessionService:
        async def get_session(self, *, app_name, user_id, session_id):
            return None

        async def create_session(self, *, app_name, user_id, session_id):
            created.append({"session_id": session_id})
            return SimpleNamespace(id=session_id)

    runner._session_service = FakeSessionService()
    await runner._ensure_adk_session(user_id="u1", session_id="s1")
    assert created == [{"session_id": "s1"}]


async def test_ensure_adk_session_noop_when_exists(db_session):
    runner = _make_runner(db_session)

    class FakeSessionService:
        async def get_session(self, *, app_name, user_id, session_id):
            return SimpleNamespace(id=session_id)

        async def create_session(self, *, app_name, user_id, session_id):
            raise AssertionError("should not create")

    runner._session_service = FakeSessionService()
    await runner._ensure_adk_session(user_id="u1", session_id="s1")


async def test_ensure_adk_session_noop_without_service(db_session):
    runner = _make_runner(db_session)
    runner._session_service = None
    await runner._ensure_adk_session(user_id="u1", session_id="s1")


# --------------------------------------------------------------------------- #
# _temporary_google_api_key context manager
# --------------------------------------------------------------------------- #


def test_temporary_google_api_key_restores_previous(db_session):
    runner = _make_runner(db_session)
    os.environ["GOOGLE_API_KEY"] = "original"
    try:
        with runner._temporary_google_api_key("override"):
            assert os.environ["GOOGLE_API_KEY"] == "override"
        assert os.environ["GOOGLE_API_KEY"] == "original"
    finally:
        os.environ.pop("GOOGLE_API_KEY", None)


def test_temporary_google_api_key_noop_when_empty(db_session):
    runner = _make_runner(db_session)
    os.environ.pop("GOOGLE_API_KEY", None)
    with runner._temporary_google_api_key(None):
        assert "GOOGLE_API_KEY" not in os.environ
    assert "GOOGLE_API_KEY" not in os.environ
