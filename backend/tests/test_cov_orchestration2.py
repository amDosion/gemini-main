"""Coverage-focused tests for the workflow DAG orchestrator + payload normalizer.

Modules under test (SUT):
  - app.services.agent.workflow_engine.orchestration
        DAG traversal, defer/merge gating, continue-on-error, per-node-type
        execution (start / input_* / end / agent / condition / router /
        parallel / merge / loop / tool / human), trace events, callbacks.
  - app.services.agent.workflow_payload_normalizer
        request payload + node + agentCard normalization/validation branches.

Strategy
--------
``orchestration.execute`` / ``execute_node`` are *helper* functions: every public
function takes the live ``WorkflowEngine`` instance as its first argument and
reaches back into the engine for the real pure helpers (``_get_node_type``,
``_to_bool``, ``_select_outgoing_edges``, ``_merge_outputs``, expression eval...).
To exercise the real traversal/routing/merge logic faithfully we construct a
*real* ``WorkflowEngine`` (same pattern as ``test_cov_workflow_engine_b.py`` /
``test_smoke_agent_workflow.py``) and run whole workflows end-to-end through
``engine.execute(...)``.

We mock ONLY external boundaries that would otherwise hit a provider / LLM:
  * ``engine._execute_agent_node``       (would call provider services)
  * ``engine._execute_builtin_tool``     (would dispatch real builtin tools)
  * ``engine._select_router_branch``     (would call an LLM for routing)

The orchestrator's own logic — BFS reachability validation, defer/merge wait-for-all
gating, continue-on-error fan-out, visit/step caps, trace/event emission, and the
``execute_node`` per-type payload assembly — is never mocked.

asyncio_mode=auto is on (plain ``async def``). ``filterwarnings=error::RuntimeWarning``
is active, so every coroutine boundary is awaited.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.agent.execution_context import ExecutionContext
from app.services.agent.workflow_engine import WorkflowEngine
from app.services.agent.workflow_engine import orchestration
import app.services.agent.workflow_payload_normalizer as wpn


# ---------------------------------------------------------------------------
# Fakes / fixtures
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeDb:
    def __init__(self, row=None):
        self._row = row

    def query(self, _model):
        return _FakeQuery(self._row)


def _make_engine(user_id="orch-user") -> WorkflowEngine:
    return WorkflowEngine(
        db=_FakeDb(None),
        llm_service=SimpleNamespace(user_id=user_id),
    )


@pytest.fixture
def engine() -> WorkflowEngine:
    return _make_engine()


# --- graph builders --------------------------------------------------------


def _node(node_id, node_type, **data):
    d = {"type": node_type}
    d.update(data)
    return {"id": node_id, "data": d}


def _edge(eid, source, target, source_handle=None):
    e = {"id": eid, "source": source, "target": target}
    if source_handle is not None:
        e["sourceHandle"] = source_handle
    return e


def _patch_agent(monkeypatch, engine, fn):
    """Replace the provider boundary; keep all orchestration logic real."""
    async def _agent(node_id, node_data, context, initial_input, input_packets):
        return fn(node_id=node_id, node_data=node_data, context=context,
                  initial_input=initial_input, input_packets=input_packets)
    monkeypatch.setattr(engine, "_execute_agent_node", _agent)


def _patch_tool(monkeypatch, engine, fn):
    async def _tool(tool_name, tool_args, context, input_packets):
        return fn(tool_name=tool_name, tool_args=tool_args,
                  context=context, input_packets=input_packets)
    monkeypatch.setattr(engine, "_execute_builtin_tool", _tool)


async def _collect_events(engine, nodes, edges, initial_input):
    """Run a workflow and capture the emitted on_event stream."""
    events: list[tuple[str, dict]] = []

    async def on_event(name, payload):
        events.append((name, payload))

    result = await engine.execute(nodes, edges, initial_input, on_event=on_event)
    return result, events


# ===========================================================================
# orchestration.execute — graph validation gate
# ===========================================================================


@pytest.mark.asyncio
class TestExecuteGraphValidation:
    async def test_empty_node_map_raises(self, engine):
        with pytest.raises(ValueError, match="缺少可执行节点"):
            await engine.execute([], [], {})

    async def test_missing_start_node(self, engine):
        nodes = [_node("e", "end")]
        with pytest.raises(ValueError, match="必须包含一个开始节点"):
            await engine.execute(nodes, [], {})

    async def test_two_start_nodes(self, engine):
        nodes = [_node("s1", "start"), _node("s2", "start"), _node("e", "end")]
        edges = [_edge("a", "s1", "e"), _edge("b", "s2", "e")]
        with pytest.raises(ValueError, match="只能包含一个开始节点"):
            await engine.execute(nodes, edges, {})

    async def test_missing_end_node(self, engine):
        nodes = [_node("s", "start"), _node("x", "agent")]
        edges = [_edge("a", "s", "x")]
        with pytest.raises(ValueError, match="必须包含一个结束节点"):
            await engine.execute(nodes, edges, {})

    async def test_two_end_nodes(self, engine):
        nodes = [_node("s", "start"), _node("e1", "end"), _node("e2", "end")]
        edges = [_edge("a", "s", "e1"), _edge("b", "s", "e2")]
        with pytest.raises(ValueError, match="只能包含一个结束节点"):
            await engine.execute(nodes, edges, {})

    async def test_start_with_incoming_edge_rejected(self, engine):
        nodes = [_node("s", "start"), _node("e", "end"), _node("m", "agent")]
        # m -> s gives start an incoming connection
        edges = [_edge("ms", "m", "s"), _edge("se", "s", "e")]
        with pytest.raises(ValueError, match="开始节点不能有输入连接"):
            await engine.execute(nodes, edges, {})

    async def test_start_without_outgoing_rejected(self, engine):
        nodes = [_node("s", "start"), _node("e", "end"), _node("a", "agent")]
        edges = [_edge("x", "a", "e")]  # start has no outgoing
        with pytest.raises(ValueError, match="开始节点至少需要一条输出连接"):
            await engine.execute(nodes, edges, {})

    async def test_end_without_incoming_rejected(self, engine):
        nodes = [_node("s", "start"), _node("e", "end"), _node("m", "agent")]
        edges = [_edge("a", "s", "m")]  # end has no incoming
        with pytest.raises(ValueError, match="结束节点至少需要一条输入连接"):
            await engine.execute(nodes, edges, {})

    async def test_end_with_outgoing_rejected(self, engine):
        nodes = [_node("s", "start"), _node("e", "end"), _node("m", "agent")]
        edges = [_edge("a", "s", "e"), _edge("b", "e", "m")]
        with pytest.raises(ValueError, match="结束节点不能有输出连接"):
            await engine.execute(nodes, edges, {})

    async def test_unreachable_node_rejected(self, engine):
        nodes = [
            _node("s", "start"), _node("e", "end"),
            _node("iso_a", "agent"), _node("iso_b", "agent"),
        ]
        edges = [
            _edge("se", "s", "e"),
            _edge("ab", "iso_a", "iso_b"),
            _edge("be", "iso_b", "e"),
        ]
        with pytest.raises(ValueError, match="未从开始节点连通"):
            await engine.execute(nodes, edges, {})

    async def test_no_path_to_end_rejected(self, engine):
        nodes = [_node("s", "start"), _node("e", "end"), _node("dead", "agent")]
        edges = [_edge("se", "s", "e"), _edge("sd", "s", "dead")]
        with pytest.raises(ValueError, match="无法流向结束节点"):
            await engine.execute(nodes, edges, {})

    async def test_edge_with_unknown_endpoints_ignored(self, engine):
        # An edge referencing a non-existent node is silently dropped (continue branch).
        nodes = [_node("s", "start"), _node("e", "end")]
        edges = [_edge("se", "s", "e"), _edge("ghost", "s", "nonexistent")]
        result = await engine.execute(nodes, edges, {"task": "hi"})
        assert result["node_states"]["s"] == "completed"
        assert result["node_states"]["e"] == "completed"


# ===========================================================================
# orchestration.execute — happy-path traversal + node_states + trace
# ===========================================================================


@pytest.mark.asyncio
class TestExecuteHappyPath:
    async def test_start_to_end_minimal(self, engine):
        nodes = [_node("s", "start"), _node("e", "end")]
        edges = [_edge("se", "s", "e")]
        result = await engine.execute(nodes, edges, {"task": "hello"})
        assert result["node_states"] == {"s": "completed", "e": "completed"}
        assert result["visit_counts"]["s"] == 1
        assert result["outputs"]["s"]["text"] == "hello"
        trace = result["trace"]
        assert trace["event_count"] >= 2
        event_types = {ev["event"] for ev in trace["events"]}
        assert "workflow_start" in event_types
        assert "workflow_complete" in event_types
        assert "node_complete" in event_types

    async def test_agent_chain_passes_output_downstream(self, monkeypatch, engine):
        seen_inputs = {}

        def agent(node_id, node_data, context, initial_input, input_packets):
            seen_inputs[node_id] = [p.get("output") for p in input_packets]
            return {"text": f"out-{node_id}"}

        _patch_agent(monkeypatch, engine, agent)
        nodes = [
            _node("s", "start"),
            _node("a1", "agent", agentId="x"),
            _node("a2", "agent", agentId="y"),
            _node("e", "end"),
        ]
        edges = [
            _edge("s_a1", "s", "a1"),
            _edge("a1_a2", "a1", "a2"),
            _edge("a2_e", "a2", "e"),
        ]
        result = await engine.execute(nodes, edges, {"task": "go"})
        assert result["node_states"]["a1"] == "completed"
        assert result["node_states"]["a2"] == "completed"
        assert seen_inputs["a2"] == [{"text": "out-a1"}]
        assert result["outputs"]["e"] == {"text": "out-a2"}

    async def test_on_event_stream_node_lifecycle(self, monkeypatch, engine):
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "ok"})
        nodes = [
            _node("s", "start"),
            _node("a", "agent", agentId="x"),
            _node("e", "end"),
        ]
        edges = [_edge("sa", "s", "a"), _edge("ae", "a", "e")]
        _result, events = await _collect_events(engine, nodes, edges, {"task": "t"})
        names = [n for n, _ in events]
        assert "node_start" in names
        assert "node_progress" in names
        assert "node_complete" in names
        completed = [p for n, p in events if n == "node_progress" and p["stage"] == "completed"]
        assert completed and completed[0]["progress"] == 100


# ===========================================================================
# orchestration.execute — merge / defer (wait_for_all) gating
# ===========================================================================


@pytest.mark.asyncio
class TestMergeAndDefer:
    async def test_merge_waits_for_all_branches(self, monkeypatch, engine):
        def agent(node_id, node_data, context, initial_input, input_packets):
            return {"text": node_id}

        _patch_agent(monkeypatch, engine, agent)
        nodes = [
            _node("s", "start"),
            _node("a1", "agent", agentId="x"),
            _node("a2", "agent", agentId="y"),
            _node("m", "merge", merge_strategy="append"),
            _node("e", "end"),
        ]
        edges = [
            _edge("s_a1", "s", "a1"),
            _edge("s_a2", "s", "a2"),
            _edge("a1_m", "a1", "m"),
            _edge("a2_m", "a2", "m"),
            _edge("m_e", "m", "e"),
        ]
        result = await engine.execute(nodes, edges, {"task": "merge-me"})
        merge_out = result["outputs"]["m"]
        # wait_for_all default True -> merge runs once and sees BOTH upstream outputs
        assert merge_out["inputsCount"] == 2
        assert result["visit_counts"]["m"] == 1
        assert result["node_states"]["m"] == "completed"

    async def test_merge_wait_for_all_false_runs_eagerly(self, monkeypatch, engine):
        def agent(node_id, node_data, context, initial_input, input_packets):
            return {"text": node_id}

        _patch_agent(monkeypatch, engine, agent)
        nodes = [
            _node("s", "start"),
            _node("a1", "agent", agentId="x"),
            _node("a2", "agent", agentId="y"),
            _node("m", "merge", wait_for_all=False),
            _node("e", "end"),
        ]
        edges = [
            _edge("s_a1", "s", "a1"),
            _edge("s_a2", "s", "a2"),
            _edge("a1_m", "a1", "m"),
            _edge("a2_m", "a2", "m"),
            _edge("m_e", "m", "e"),
        ]
        result = await engine.execute(nodes, edges, {"task": "x"})
        assert result["visit_counts"]["m"] >= 1
        assert result["node_states"]["m"] == "completed"

    async def test_single_incoming_merge_does_not_defer(self, engine):
        nodes = [_node("s", "start"), _node("m", "merge"), _node("e", "end")]
        edges = [_edge("sm", "s", "m"), _edge("me", "m", "e")]
        result = await engine.execute(nodes, edges, {"task": "single"})
        assert result["node_states"]["m"] == "completed"


# ===========================================================================
# orchestration.execute — continue-on-error fan-out & hard failure
# ===========================================================================


@pytest.mark.asyncio
class TestContinueOnError:
    async def test_failure_without_continue_raises_and_marks_failed(self, monkeypatch, engine):
        def agent(node_id, node_data, context, initial_input, input_packets):
            raise RuntimeError("boom-from-agent")

        _patch_agent(monkeypatch, engine, agent)
        nodes = [
            _node("s", "start"),
            _node("a", "agent", agentId="x"),
            _node("e", "end"),
        ]
        edges = [_edge("sa", "s", "a"), _edge("ae", "a", "e")]
        with pytest.raises(RuntimeError, match="boom-from-agent"):
            await engine.execute(nodes, edges, {"task": "t"})

    async def test_continue_on_error_emits_fallback_and_reaches_end(self, monkeypatch, engine):
        def agent(node_id, node_data, context, initial_input, input_packets):
            if node_id == "a":
                raise RuntimeError("agent-fail")
            return {"text": "downstream-ran"}

        _patch_agent(monkeypatch, engine, agent)
        nodes = [
            _node("s", "start"),
            _node("a", "agent", agentId="x", continue_on_error=True),
            _node("b", "agent", agentId="y"),
            _node("e", "end"),
        ]
        edges = [_edge("sa", "s", "a"), _edge("ab", "a", "b"), _edge("be", "b", "e")]
        result, events = await _collect_events(engine, nodes, edges, {"task": "t"})
        assert result["node_states"]["a"] == "failed"
        assert result["node_states"]["b"] == "completed"
        node_error_events = [p for n, p in events if n == "node_error"]
        assert node_error_events and node_error_events[0]["continueOnError"] is True
        assert result["outputs"]["a"]["status"] == "failed"
        assert "[FAILED:a]" in result["outputs"]["a"]["text"]

    async def test_workflow_failed_trace_event_on_hard_error(self, monkeypatch, engine):
        def agent(node_id, node_data, context, initial_input, input_packets):
            raise ValueError("hard-stop")

        _patch_agent(monkeypatch, engine, agent)
        nodes = [_node("s", "start"), _node("a", "agent", agentId="x"), _node("e", "end")]
        edges = [_edge("sa", "s", "a"), _edge("ae", "a", "e")]
        with pytest.raises(ValueError):
            await engine.execute(nodes, edges, {"task": "t"})
        events = {ev["event"] for ev in engine._trace_events}
        assert "workflow_failed" in events


# ===========================================================================
# orchestration.execute — callback plugins
# ===========================================================================


@pytest.mark.asyncio
class TestCallbacks:
    async def test_callback_plugins_invoked_across_lifecycle(self, monkeypatch):
        hooks_seen: list[str] = []

        class Plugin:
            def before_node(self, payload):
                hooks_seen.append("before_node")

            def after_node(self, payload):
                hooks_seen.append("after_node")

            async def after_workflow(self, payload):
                hooks_seen.append("after_workflow")

        engine = WorkflowEngine(
            db=_FakeDb(None),
            llm_service=SimpleNamespace(user_id="cb"),
            callback_plugins=[Plugin()],
        )
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "ok"})
        nodes = [_node("s", "start"), _node("a", "agent", agentId="x"), _node("e", "end")]
        edges = [_edge("sa", "s", "a"), _edge("ae", "a", "e")]
        await engine.execute(nodes, edges, {"task": "t"})
        assert "before_node" in hooks_seen
        assert "after_node" in hooks_seen
        assert "after_workflow" in hooks_seen

    async def test_callback_plugin_exception_is_swallowed(self, monkeypatch):
        class BadPlugin:
            def before_node(self, payload):
                raise RuntimeError("plugin blew up")

        engine = WorkflowEngine(
            db=_FakeDb(None),
            llm_service=SimpleNamespace(user_id="cb2"),
            callback_plugins=[BadPlugin()],
        )
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "ok"})
        nodes = [_node("s", "start"), _node("a", "agent", agentId="x"), _node("e", "end")]
        edges = [_edge("sa", "s", "a"), _edge("ae", "a", "e")]
        result = await engine.execute(nodes, edges, {"task": "t"})
        assert result["node_states"]["a"] == "completed"


# ===========================================================================
# orchestration.execute — condition / router branching
# ===========================================================================


@pytest.mark.asyncio
class TestConditionAndRouter:
    async def test_condition_true_branch_selected(self, monkeypatch, engine):
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "branch-ran"})
        nodes = [
            _node("s", "start"),
            _node("c", "condition", expression="true"),
            _node("t", "agent", agentId="t"),
            _node("f", "agent", agentId="f"),
            _node("e", "end"),
        ]
        edges = [
            _edge("sc", "s", "c"),
            _edge("ct", "c", "t", source_handle="output-true"),
            _edge("cf", "c", "f", source_handle="output-false"),
            _edge("te", "t", "e"),
            _edge("fe", "f", "e"),
        ]
        result = await engine.execute(nodes, edges, {"task": "x"})
        assert result["outputs"]["c"]["branch"] == "true"
        assert result["node_states"]["t"] == "completed"
        assert result["node_states"]["f"] == "skipped"

    async def test_condition_false_branch_selected(self, monkeypatch, engine):
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "ran"})
        nodes = [
            _node("s", "start"),
            _node("c", "condition", expression="false"),
            _node("t", "agent", agentId="t"),
            _node("f", "agent", agentId="f"),
            _node("e", "end"),
        ]
        edges = [
            _edge("sc", "s", "c"),
            _edge("ct", "c", "t", source_handle="output-true"),
            _edge("cf", "c", "f", source_handle="output-false"),
            _edge("te", "t", "e"),
            _edge("fe", "f", "e"),
        ]
        result = await engine.execute(nodes, edges, {"task": "x"})
        assert result["outputs"]["c"]["branch"] == "false"
        assert result["node_states"]["f"] == "completed"
        assert result["node_states"]["t"] == "skipped"

    async def test_router_selects_branch_by_index(self, monkeypatch, engine):
        async def fake_router(strategy, router_prompt, input_text, outgoing_count):
            return 1, "test:forced"

        monkeypatch.setattr(engine, "_select_router_branch", fake_router)
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "ran"})
        nodes = [
            _node("s", "start"),
            _node("r", "router", router_strategy="intent"),
            _node("b0", "agent", agentId="b0"),
            _node("b1", "agent", agentId="b1"),
            _node("e", "end"),
        ]
        edges = [
            _edge("sr", "s", "r"),
            _edge("rb0", "r", "b0", source_handle="output-0"),
            _edge("rb1", "r", "b1", source_handle="output-1"),
            _edge("b0e", "b0", "e"),
            _edge("b1e", "b1", "e"),
        ]
        result = await engine.execute(nodes, edges, {"task": "route"})
        assert result["outputs"]["r"]["selectedIndex"] == 1
        assert result["node_states"]["b1"] == "completed"
        assert result["node_states"]["b0"] == "skipped"


# ===========================================================================
# orchestration.execute_node — direct per-type assembly
# ===========================================================================


@pytest.mark.asyncio
class TestExecuteNodeStartAndEnd:
    async def test_start_uses_task_then_falls_back_to_json(self, engine):
        ctx = ExecutionContext({})
        node = _node("s", "start")
        out, routing = await orchestration.execute_node(
            engine, node, ctx, {"foo": "bar"}, [], []
        )
        assert '"foo"' in out["text"]
        assert routing == {"mode": "all"}

    async def test_start_prefers_input_key(self, engine):
        ctx = ExecutionContext({})
        node = _node("s", "start")
        out, _ = await orchestration.execute_node(engine, node, ctx, {"input": "hi"}, [], [])
        assert out["text"] == "hi"

    async def test_end_no_inputs_uses_latest_or_default(self, engine):
        ctx = ExecutionContext({})
        node = _node("e", "end")
        out, routing = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out == {"text": "工作流执行完成"}
        assert routing == {"mode": "none"}

    async def test_end_single_input_passthrough(self, engine):
        ctx = ExecutionContext({})
        node = _node("e", "end")
        packets = [{"output": {"text": "only"}}]
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, packets, [])
        assert out == {"text": "only"}

    async def test_end_multiple_inputs_aggregated(self, engine):
        ctx = ExecutionContext({})
        node = _node("e", "end")
        packets = [{"output": {"text": "a"}}, {"output": {"text": "b"}}]
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, packets, [])
        assert out["count"] == 2
        assert out["results"] == [{"text": "a"}, {"text": "b"}]


@pytest.mark.asyncio
class TestExecuteNodeInputs:
    async def test_input_text_uses_configured_start_task(self, engine):
        ctx = ExecutionContext({"task": "init"})
        node = _node("it", "input_text", start_task="configured")
        out, _ = await orchestration.execute_node(engine, node, ctx, {"task": "init"}, [], [])
        assert out["text"] == "configured"
        assert out["task"] == "configured"

    async def test_input_image_requires_url(self, engine):
        ctx = ExecutionContext({})
        node = _node("ii", "input_image")
        with pytest.raises(ValueError, match="图片输入节点缺少有效"):
            await orchestration.execute_node(engine, node, ctx, {}, [], [])

    async def test_input_image_from_initial_input(self, engine):
        ctx = ExecutionContext({})
        node = _node("ii", "input_image")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"imageUrl": "https://h/a.png"}, [], []
        )
        assert out["imageUrl"] == "https://h/a.png"
        assert out["imageUrls"] == ["https://h/a.png"]

    async def test_input_file_requires_url(self, engine):
        ctx = ExecutionContext({})
        node = _node("if", "input_file")
        with pytest.raises(ValueError, match="文件输入节点缺少"):
            await orchestration.execute_node(engine, node, ctx, {}, [], [])

    async def test_input_file_from_initial_input(self, engine):
        ctx = ExecutionContext({})
        node = _node("if", "input_file")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"fileUrl": "https://h/data.csv"}, [], []
        )
        assert out["fileUrl"] == "https://h/data.csv"

    async def test_input_video_requires_source(self, engine):
        ctx = ExecutionContext({})
        node = _node("iv", "input_video")
        with pytest.raises(ValueError, match="视频输入节点缺少"):
            await orchestration.execute_node(engine, node, ctx, {}, [], [])

    async def test_input_video_from_initial_input(self, engine):
        ctx = ExecutionContext({})
        node = _node("iv", "input_video")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"videoUrl": "https://h/clip.mp4"}, [], []
        )
        assert out.get("videoUrl") == "https://h/clip.mp4"
        assert "sourceVideo" in out

    async def test_input_text_template_resolved(self, engine):
        ctx = ExecutionContext({"task": "resolved-task"})
        node = _node("it", "input_text", start_task="{{input.task}}")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"task": "resolved-task"}, [], []
        )
        assert out["text"] == "resolved-task"
        assert out["task"] == "resolved-task"

    async def test_input_text_falls_back_to_packet_text(self, engine):
        ctx = ExecutionContext({})
        node = _node("it", "input_text")  # no configured text
        packets = [{"output": {"text": "from-upstream"}}]
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, packets, [])
        # latest packet dict is spread into output_payload, so text comes from it
        assert out["text"] == "from-upstream"

    async def test_input_image_from_node_config_value(self, engine):
        ctx = ExecutionContext({})
        node = _node("ii", "input_image", start_image_url="https://h/cfg.png")
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["imageUrl"] == "https://h/cfg.png"

    async def test_input_image_config_list_value(self, engine):
        ctx = ExecutionContext({})
        node = _node("ii", "input_image", startImageUrls=["https://h/a.png", "https://h/b.png"])
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["imageUrls"] == ["https://h/a.png", "https://h/b.png"]

    async def test_input_image_initial_input_url_list(self, engine):
        ctx = ExecutionContext({})
        node = _node("ii", "input_image")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"imageUrls": ["https://h/x.png", "https://h/x.png"]}, [], []
        )
        # dedupe keeps a single entry
        assert out["imageUrls"] == ["https://h/x.png"]

    async def test_input_video_dict_source_payload(self, engine):
        ctx = ExecutionContext({})
        node = _node("iv", "input_video")
        initial = {
            "sourceVideo": {
                "provider_file_name": "files/v1",
                "provider_file_uri": "files/v1",
                "mime_type": "video/mp4",
                "videoUrl": "https://h/v.mp4",
            }
        }
        out, _ = await orchestration.execute_node(engine, node, ctx, initial, [], [])
        assert out["sourceVideo"]  # dict payload preserved
        # at least one provider/url field propagated from the dict payload
        assert out.get("videoUrl") or out.get("provider_file_name") or out.get("mimeType")

    async def test_input_video_gcs_uri_string(self, engine):
        ctx = ExecutionContext({})
        node = _node("iv", "input_video")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"gcs_uri": "gs://bucket/clip.mp4"}, [], []
        )
        assert "sourceVideo" in out

    async def test_input_file_from_config(self, engine):
        ctx = ExecutionContext({})
        node = _node("if", "input_file", start_file_url="https://h/cfg.csv")
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["fileUrl"] == "https://h/cfg.csv"

    async def test_input_file_table_from_initial_input(self, engine):
        ctx = ExecutionContext({})
        node = _node("if", "input_file")
        out, _ = await orchestration.execute_node(
            engine, node, ctx, {"fileUrls": ["https://h/a.csv", "https://h/b.csv"]}, [], []
        )
        assert out["fileUrl"] == "https://h/a.csv"
        assert out["fileUrls"] == ["https://h/a.csv", "https://h/b.csv"]


@pytest.mark.asyncio
class TestExecuteNodeMergeParallelLoopHuman:
    async def test_merge_append_strategy(self, engine):
        ctx = ExecutionContext({})
        node = _node("m", "merge", merge_strategy="append")
        packets = [{"output": {"text": "x"}}, {"output": {"text": "y"}}]
        out, routing = await orchestration.execute_node(engine, node, ctx, {}, packets, [])
        assert out["inputsCount"] == 2
        assert out["mergeStrategy"] == "append"
        assert routing == {"mode": "all"}

    async def test_parallel_node_passthrough(self, engine):
        ctx = ExecutionContext({})
        node = _node("p", "parallel", join_mode="wait_all")
        packets = [{"output": {"text": "payload", "imageUrl": "u"}}]
        outgoing = [{"id": "o1"}, {"id": "o2"}]
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, packets, outgoing)
        assert out["mode"] == "parallel"
        assert out["branchCount"] == 2
        assert out["imageUrl"] == "u"

    async def test_loop_should_continue_true(self, engine):
        ctx = ExecutionContext({})
        node = _node("l", "loop", max_iterations=3, loop_condition="true")
        out, routing = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["iteration"] == 1
        assert out["shouldContinue"] is True
        assert routing == {"mode": "loop", "continue": True}

    async def test_loop_stops_when_condition_false(self, engine):
        ctx = ExecutionContext({})
        node = _node("l", "loop", max_iterations=3, loop_condition="false")
        out, routing = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["shouldContinue"] is False
        assert routing["continue"] is False

    async def test_human_requires_explicit_auto_approve(self, engine):
        ctx = ExecutionContext({})
        node = _node("h", "human")
        with pytest.raises(ValueError, match="Human approval node requires explicit"):
            await orchestration.execute_node(engine, node, ctx, {}, [], [])

    async def test_human_auto_approved(self, engine):
        ctx = ExecutionContext({})
        node = _node("h", "human", autoApprove=True, approval_prompt="ok?")
        out, routing = await orchestration.execute_node(engine, node, ctx, {"task": "t"}, [], [])
        assert out["approved"] is True
        assert out["approvalPrompt"] == "ok?"
        assert routing == {"mode": "all"}

    async def test_unsupported_node_type_raises(self, engine):
        ctx = ExecutionContext({})
        node = _node("z", "totally_unknown")
        with pytest.raises(ValueError, match="Unsupported workflow node type"):
            await orchestration.execute_node(engine, node, ctx, {}, [], [])


@pytest.mark.asyncio
class TestExecuteNodeAgentAndTool:
    async def test_agent_node_returns_output_and_all_routing(self, monkeypatch, engine):
        _patch_agent(monkeypatch, engine, lambda **k: {"text": "agent-out"})
        ctx = ExecutionContext({})
        node = _node("a", "agent", agentId="x")
        out, routing = await orchestration.execute_node(engine, node, ctx, {"task": "t"}, [], [])
        assert out == {"text": "agent-out"}
        assert routing == {"mode": "all"}

    async def test_agent_node_timeout_maps_to_timeout_error(self, monkeypatch, engine):
        import asyncio

        async def slow_agent(node_id, node_data, context, initial_input, input_packets):
            raise asyncio.TimeoutError()

        monkeypatch.setattr(engine, "_execute_agent_node", slow_agent)

        async def instant_timeout(coro, timeout):
            # consume the coroutine to avoid "never awaited" RuntimeWarning
            await asyncio.gather(coro, return_exceptions=True)
            raise asyncio.TimeoutError()

        monkeypatch.setattr(orchestration.asyncio, "wait_for", instant_timeout)
        ctx = ExecutionContext({})
        node = _node("a", "agent", agentId="x", agent_task_type="video-gen")
        with pytest.raises(TimeoutError, match="timed out"):
            await orchestration.execute_node(engine, node, ctx, {}, [], [])

    async def test_tool_node_assembles_output(self, monkeypatch, engine):
        _patch_tool(monkeypatch, engine, lambda **k: {"text": "tool-result", "url": "x"})
        ctx = ExecutionContext({})
        node = _node("t", "tool", tool_name="my_tool")
        out, routing = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["toolName"] == "my_tool"
        assert out["text"] == "tool-result"
        assert routing == {"mode": "all"}

    async def test_tool_node_image_url_extraction(self, monkeypatch, engine):
        _patch_tool(
            monkeypatch, engine,
            lambda **k: {"images": [{"imageUrl": "https://h/r.png"}], "text": "done"},
        )
        ctx = ExecutionContext({})
        node = _node("t", "tool", tool_name="img_tool")
        out, _ = await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert out["imageUrl"] == "https://h/r.png"
        assert out["imageUrls"] == ["https://h/r.png"]

    async def test_tool_node_default_name_when_blank(self, monkeypatch, engine):
        captured = {}

        def tool(tool_name, tool_args, context, input_packets):
            captured["name"] = tool_name
            return {"text": "ok"}

        _patch_tool(monkeypatch, engine, tool)
        ctx = ExecutionContext({})
        node = _node("t", "tool")  # no tool_name
        await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert captured["name"] == "mock_tool"

    async def test_tool_node_structured_field_map_backfill(self, monkeypatch, engine):
        captured = {}

        def tool(tool_name, tool_args, context, input_packets):
            captured["args"] = tool_args
            return {"text": "ok"}

        _patch_tool(monkeypatch, engine, tool)
        ctx = ExecutionContext({})
        node = _node("t", "tool", tool_name="gen", toolProviderId="google", toolModelId="m1")
        await orchestration.execute_node(engine, node, ctx, {}, [], [])
        assert captured["args"]["provider_id"] == "google"
        assert captured["args"]["model_id"] == "m1"


# ===========================================================================
# orchestration helpers: trace event + agent timeout resolution
# ===========================================================================


class TestRecordTraceEvent:
    def test_caps_at_500_events(self, engine):
        engine._trace_events = []
        for i in range(520):
            orchestration.record_trace_event(engine, "tick", {"i": i})
        assert len(engine._trace_events) == 500
        assert engine._trace_events[-1]["payload"]["i"] == 519

    def test_blank_event_type_becomes_unknown(self, engine):
        engine._trace_events = []
        orchestration.record_trace_event(engine, "   ", None)
        assert engine._trace_events[-1]["event"] == "unknown"
        assert engine._trace_events[-1]["payload"] == {}


class TestResolveAgentTimeoutSeconds:
    def test_explicit_timeout_clamped(self, engine):
        assert orchestration.resolve_agent_timeout_seconds(engine, {"agent_timeout_seconds": "999999"}) == 7200
        assert orchestration.resolve_agent_timeout_seconds(engine, {"timeoutSeconds": "0"}) == 1

    def test_invalid_explicit_falls_back_to_default(self, engine):
        assert (
            orchestration.resolve_agent_timeout_seconds(engine, {"agent_timeout_seconds": "abc"})
            == engine.DEFAULT_AGENT_TIMEOUT_SECONDS
        )

    def test_task_type_image_uses_image_timeout(self, engine):
        assert (
            orchestration.resolve_agent_timeout_seconds(engine, {"agent_task_type": "image-edit"})
            == engine.DEFAULT_IMAGE_AGENT_TIMEOUT_SECONDS
        )

    def test_task_type_video_uses_video_timeout(self, engine):
        assert (
            orchestration.resolve_agent_timeout_seconds(engine, {"agentTaskType": "video-gen"})
            == engine.DEFAULT_VIDEO_AGENT_TIMEOUT_SECONDS
        )

    def test_task_type_data_uses_data_timeout(self, engine):
        assert (
            orchestration.resolve_agent_timeout_seconds(engine, {"agent_task_type": "data_analysis"})
            == engine.DEFAULT_DATA_AGENT_TIMEOUT_SECONDS
        )

    def test_default_when_no_hints(self, engine):
        assert (
            orchestration.resolve_agent_timeout_seconds(engine, {})
            == engine.DEFAULT_AGENT_TIMEOUT_SECONDS
        )


@pytest.mark.asyncio
class TestEmitCallback:
    async def test_no_plugins_is_noop(self, engine):
        await orchestration.emit_callback(engine, "before_node", {"x": 1})

    async def test_async_callback_awaited(self):
        seen = {}

        class P:
            async def before_node(self, payload):
                seen["payload"] = payload

        eng = WorkflowEngine(db=_FakeDb(None), llm_service=SimpleNamespace(user_id="u"),
                             callback_plugins=[P()])
        await orchestration.emit_callback(eng, "before_node", {"k": "v"})
        assert seen["payload"] == {"k": "v"}

    async def test_missing_hook_skipped(self):
        class P:
            pass  # no before_node attribute

        eng = WorkflowEngine(db=_FakeDb(None), llm_service=SimpleNamespace(user_id="u"),
                             callback_plugins=[P()])
        await orchestration.emit_callback(eng, "before_node", {})


# ===========================================================================
# workflow_payload_normalizer — scalar helpers
# ===========================================================================


class TestNormalizerScalarHelpers:
    def test_normalize_analysis_type_aliases(self):
        assert wpn._normalize_analysis_type("summary") == "statistics"
        assert wpn._normalize_analysis_type("trend") == "trends"
        assert wpn._normalize_analysis_type("anomaly") == "distribution"
        assert wpn._normalize_analysis_type("all") == "comprehensive"
        assert wpn._normalize_analysis_type("nope") == "comprehensive"
        assert wpn._normalize_analysis_type("correlation") == "correlation"

    def test_clamp_optional_int(self):
        assert wpn._clamp_optional_int(None, minimum=1, maximum=8) is None
        assert wpn._clamp_optional_int("  ", minimum=1, maximum=8) is None
        assert wpn._clamp_optional_int("abc", minimum=1, maximum=8) is None
        assert wpn._clamp_optional_int("100", minimum=1, maximum=8) == 8
        assert wpn._clamp_optional_int("0", minimum=1, maximum=8) == 1
        assert wpn._clamp_optional_int("3.9", minimum=1, maximum=8) == 3

    def test_clamp_optional_float(self):
        assert wpn._clamp_optional_float(None, minimum=0.25, maximum=4.0) is None
        assert wpn._clamp_optional_float("x", minimum=0.25, maximum=4.0) is None
        assert wpn._clamp_optional_float("9.0", minimum=0.25, maximum=4.0) == 4.0
        assert wpn._clamp_optional_float("0.1", minimum=0.25, maximum=4.0) == 0.25

    def test_coerce_optional_bool(self):
        assert wpn._coerce_optional_bool(None, default=True) is True
        assert wpn._coerce_optional_bool(True) is True
        assert wpn._coerce_optional_bool(0) is False
        assert wpn._coerce_optional_bool(2) is True
        assert wpn._coerce_optional_bool("yes") is True
        assert wpn._coerce_optional_bool("off") is False
        assert wpn._coerce_optional_bool("maybe", default=True) is True

    def test_normalize_optional_choice(self):
        assert wpn._normalize_optional_choice("PNG", allowed={"png", "jpg"}) == "png"
        assert wpn._normalize_optional_choice("gif", allowed={"png"}) is None
        assert wpn._normalize_optional_choice("  ", allowed={"png"}) is None

    def test_normalize_optional_string_truncates(self):
        assert wpn._normalize_optional_string("  ") is None
        assert wpn._normalize_optional_string("hello") == "hello"
        assert wpn._normalize_optional_string("abcdef", max_length=3) == "abc"

    def test_normalize_string_list_dedupes_and_caps(self):
        out = wpn._normalize_string_list(["a", " a ", "", "b", "c"], max_items=2)
        assert out == ["a", "b"]
        assert wpn._normalize_string_list("not-a-list") == []


# ===========================================================================
# workflow_payload_normalizer — input payload normalization
# ===========================================================================


class TestNormalizeWorkflowInputPayload:
    def test_url_fields_collapsed_and_deduped(self):
        payload = {
            "imageUrls": ["https://h/1.png", "https://h/1.png", "https://h/2.png"],
            "imageUrl": "https://h/0.png",
        }
        out = wpn._normalize_workflow_input_payload(payload)
        assert out["imageUrl"] == "https://h/0.png"
        assert out["imageUrls"][0] == "https://h/0.png"
        assert "https://h/2.png" in out["imageUrls"]

    def test_empty_url_fields_removed(self):
        out = wpn._normalize_workflow_input_payload({"imageUrl": "", "imageUrls": []})
        assert "imageUrl" not in out
        assert "imageUrls" not in out

    def test_snake_case_url_fallback(self):
        out = wpn._normalize_workflow_input_payload({"image_urls": ["https://h/a.png"]})
        assert out["imageUrls"] == ["https://h/a.png"]

    def test_analysis_type_normalized(self):
        out = wpn._normalize_workflow_input_payload({"analysis_type": "summary", "analysisType": "trend"})
        assert out["analysis_type"] == "statistics"
        assert out["analysisType"] == "trends"

    def test_task_derived_from_prompt_or_text(self):
        assert wpn._normalize_workflow_input_payload({"prompt": " hello "})["task"] == "hello"
        assert wpn._normalize_workflow_input_payload({"text": "world"})["task"] == "world"
        assert "task" not in wpn._normalize_workflow_input_payload({"other": 1})


# ===========================================================================
# workflow_payload_normalizer — node normalization
# ===========================================================================


class TestNormalizeWorkflowNodes:
    def test_non_dict_node_skipped(self):
        out = wpn._normalize_workflow_nodes(["not-a-dict", 42])
        assert out == []

    def test_node_without_data_dict_passthrough(self):
        node = {"id": "n", "data": "string-data"}
        out = wpn._normalize_workflow_nodes([node])
        assert out == [node]

    def test_agent_task_type_normalized_both_keys(self):
        node = {"id": "a", "data": {"agentTaskType": "video-generation"}}
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert data["agentTaskType"] == "video-gen"
        assert data["agent_task_type"] == "video-gen"

    def test_number_of_images_clamped_and_dropped_when_invalid(self):
        node = {"id": "a", "data": {"toolNumberOfImages": "99", "numberOfImages": "junk"}}
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert data["toolNumberOfImages"] == 8
        assert "numberOfImages" not in data

    def test_image_edit_retries_default_to_one_when_invalid(self):
        node = {"id": "a", "data": {"agentImageEditMaxRetries": "junk"}}
        out = wpn._normalize_workflow_nodes([node])
        assert out[0]["data"]["agentImageEditMaxRetries"] == 1

    def test_analysis_type_fields_normalized(self):
        node = {"id": "a", "data": {"toolAnalysisType": "summary", "analysisType": "trend"}}
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert data["toolAnalysisType"] == "statistics"
        assert data["analysisType"] == "trends"

    def test_output_mime_and_format_dropped_when_invalid(self):
        node = {"id": "a", "data": {"agentOutputMimeType": "image/gif", "agentOutputFormat": "xml"}}
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert "agentOutputMimeType" not in data
        assert "agentOutputFormat" not in data

    def test_edit_mode_normalized(self):
        node = {"id": "a", "data": {"toolEditMode": "inpainting"}}
        out = wpn._normalize_workflow_nodes([node])
        assert out[0]["data"]["toolEditMode"] == "image-inpainting"

    def test_video_gen_fields_normalized(self):
        node = {
            "id": "a",
            "data": {
                "agentTaskType": "video-gen",
                "agentVideoDurationSeconds": "100",   # clamp to 20
                "agentVideoAspectRatio": "16:9",
                "agentVideoResolution": "1080p",
                "agentGenerateAudio": "true",
                "agentSubtitleMode": "srt",
                "agentSeed": "5",
                "agentNegativePrompt": "  blurry  ",
            },
        }
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert data["agentVideoDurationSeconds"] == 20
        assert data["agentVideoAspectRatio"] == "16:9"
        assert data["agentVideoResolution"] == "1080p"
        assert data["agentGenerateAudio"] is True
        assert data["agentSubtitleMode"] == "srt"
        assert data["agentSeed"] == 5
        assert data["agentNegativePrompt"] == "blurry"

    def test_video_gen_invalid_aspect_ratio_dropped(self):
        node = {"id": "a", "data": {"agentTaskType": "video-gen", "agentVideoAspectRatio": "4:3"}}
        out = wpn._normalize_workflow_nodes([node])
        assert "agentVideoAspectRatio" not in out[0]["data"]

    def test_audio_gen_speed_and_format(self):
        node = {
            "id": "a",
            "data": {
                "agentTaskType": "audio-gen",
                "agentSpeechSpeed": "9.0",        # clamp to 4.0
                "agentAudioFormat": "mp3",
                "agentVoice": "  narrator  ",
            },
        }
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert data["agentSpeechSpeed"] == 4.0
        assert data["agentAudioFormat"] == "mp3"
        assert data["agentVoice"] == "narrator"

    def test_start_url_fields_collapsed(self):
        node = {
            "id": "a",
            "data": {
                "startImageUrls": ["https://h/2.png"],
                "startImageUrl": "https://h/1.png",
                "startVideoUrl": "",  # empty -> removed
            },
        }
        out = wpn._normalize_workflow_nodes([node])
        data = out[0]["data"]
        assert data["startImageUrl"] == "https://h/1.png"
        assert data["startImageUrls"] == ["https://h/1.png", "https://h/2.png"]
        assert "startVideoUrl" not in data


# ===========================================================================
# workflow_payload_normalizer — agentCard validation
# ===========================================================================


class TestValidateAndNormalizeAgentCard:
    def test_none_returns_none(self):
        assert wpn._validate_and_normalize_agent_card(None) is None

    def test_non_dict_raises_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            wpn._validate_and_normalize_agent_card("not-a-dict")
        assert exc.value.status_code == 400

    def test_card_without_defaults_passthrough(self):
        card = {"name": "x"}
        out = wpn._validate_and_normalize_agent_card(card)
        assert out == {"name": "x"}

    def test_defaults_not_dict_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            wpn._validate_and_normalize_agent_card({"defaults": "bad"})

    def test_default_task_type_invalid_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="defaultTaskType"):
            wpn._validate_and_normalize_agent_card({"defaults": {"defaultTaskType": "nonsense"}})

    def test_default_task_type_normalized(self):
        out = wpn._validate_and_normalize_agent_card(
            {"defaults": {"defaultTaskType": "video-generation"}}
        )
        assert out["defaults"]["defaultTaskType"] == "video-gen"

    def test_vision_output_format_validated(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="outputFormat"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"visionUnderstand": {"outputFormat": "xml"}}}
            )
        out = wpn._validate_and_normalize_agent_card(
            {"defaults": {"visionUnderstand": {"outputFormat": "JSON"}}}
        )
        assert out["defaults"]["visionUnderstand"]["outputFormat"] == "json"

    def test_data_analysis_output_format_normalized(self):
        out = wpn._validate_and_normalize_agent_card(
            {"defaults": {"dataAnalysis": {"outputFormat": "Markdown"}}}
        )
        assert out["defaults"]["dataAnalysis"]["outputFormat"] == "markdown"

    def test_image_edit_defaults_validation(self):
        card = {
            "defaults": {
                "imageEdit": {
                    "editMode": "inpainting",
                    "numberOfImages": "4",
                    "outputMimeType": "image/png",
                    "promptExtend": "true",
                    "productMatchThreshold": "80",
                    "maxRetries": "2",
                    "aspectRatio": "  1:1  ",
                }
            }
        }
        out = wpn._validate_and_normalize_agent_card(card)
        ie = out["defaults"]["imageEdit"]
        assert ie["editMode"] == "image-inpainting"
        assert ie["numberOfImages"] == 4
        assert ie["outputMimeType"] == "image/png"
        assert ie["promptExtend"] is True
        assert ie["productMatchThreshold"] == 80
        assert ie["maxRetries"] == 2
        assert ie["aspectRatio"] == "1:1"

    def test_image_edit_invalid_edit_mode_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="editMode"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"imageEdit": {"editMode": "no-such-mode"}}}
            )

    def test_image_edit_invalid_number_of_images_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="numberOfImages"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"imageEdit": {"numberOfImages": "junk"}}}
            )

    def test_image_edit_invalid_mime_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="outputMimeType"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"imageEdit": {"outputMimeType": "image/gif"}}}
            )

    def test_video_generation_defaults(self):
        card = {
            "defaults": {
                "videoGeneration": {
                    "aspectRatio": "9:16",
                    "resolution": "1080p",
                    "durationSeconds": "8",
                    "generateAudio": "yes",
                    "subtitleMode": "vtt",
                    "seed": "11",
                    "negativePrompt": "  bad  ",
                }
            }
        }
        out = wpn._validate_and_normalize_agent_card(card)
        vg = out["defaults"]["videoGeneration"]
        assert vg["aspectRatio"] == "9:16"
        assert vg["resolution"] == "1080p"
        assert vg["durationSeconds"] == 8
        assert vg["generateAudio"] is True
        assert vg["subtitleMode"] == "vtt"
        assert vg["seed"] == 11
        assert vg["negativePrompt"] == "bad"

    def test_video_invalid_aspect_ratio_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="aspectRatio"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"videoGeneration": {"aspectRatio": "4:3"}}}
            )

    def test_video_invalid_duration_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="durationSeconds"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"videoGeneration": {"durationSeconds": "junk"}}}
            )

    def test_audio_generation_with_legacy_speech_alias(self):
        card = {
            "defaults": {
                "speechGeneration": {
                    "voice": "alloy",
                    "responseFormat": "wav",
                    "speed": "1.5",
                }
            }
        }
        out = wpn._validate_and_normalize_agent_card(card)
        assert out["defaults"]["audioGeneration"]["voice"] == "alloy"
        assert out["defaults"]["audioGeneration"]["responseFormat"] == "wav"
        assert out["defaults"]["audioGeneration"]["speed"] == 1.5
        assert out["defaults"]["speechGeneration"]["voice"] == "alloy"

    def test_audio_invalid_format_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="responseFormat"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"audioGeneration": {"responseFormat": "ogg2"}}}
            )

    def test_llm_defaults_validation(self):
        card = {
            "defaults": {
                "llm": {
                    "providerId": " google ",
                    "modelId": " gemini ",
                    "temperature": "0.7",
                    "maxTokens": "2048",
                    "preferLatestModel": "true",
                }
            }
        }
        out = wpn._validate_and_normalize_agent_card(card)
        llm = out["defaults"]["llm"]
        assert llm["providerId"] == "google"
        assert llm["modelId"] == "gemini"
        assert llm["temperature"] == 0.7
        assert llm["maxTokens"] == 2048
        assert llm["preferLatestModel"] is True

    def test_llm_empty_provider_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="providerId"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"llm": {"providerId": "   "}}}
            )

    def test_llm_temperature_out_of_range_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="temperature"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"llm": {"temperature": "5"}}}
            )

    def test_llm_temperature_non_numeric_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="temperature"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"llm": {"temperature": "hot"}}}
            )

    def test_llm_max_tokens_out_of_range_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="maxTokens"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"llm": {"maxTokens": "999999"}}}
            )

    def test_llm_prefer_latest_invalid_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="preferLatestModel"):
            wpn._validate_and_normalize_agent_card(
                {"defaults": {"llm": {"preferLatestModel": "perhaps"}}}
            )

    def test_llm_prefer_latest_bool_passthrough(self):
        out = wpn._validate_and_normalize_agent_card(
            {"defaults": {"llm": {"preferLatestModel": False}}}
        )
        assert out["defaults"]["llm"]["preferLatestModel"] is False


# ===========================================================================
# workflow_payload_normalizer — full structural validation
# ===========================================================================


class TestValidateWorkflowExecutePayload:
    def test_empty_nodes(self):
        assert wpn._validate_workflow_execute_payload([], []) == "工作流至少需要一个节点"

    def test_missing_node_id(self):
        msg = wpn._validate_workflow_execute_payload([{"data": {"type": "start"}}], [])
        assert "缺少 id" in msg

    def test_unsupported_node_type(self):
        nodes = [{"id": "n", "data": {"type": "wormhole"}}]
        msg = wpn._validate_workflow_execute_payload(nodes, [])
        assert "Unsupported workflow node type" in msg

    def test_node_type_read_from_top_level(self):
        # node type may live on the node itself when data lacks 'type'
        nodes = [{"id": "n", "type": "wormhole", "data": {}}]
        msg = wpn._validate_workflow_execute_payload(nodes, [])
        assert "Unsupported workflow node type" in msg

    def test_agent_node_missing_binding(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "a", "data": {"type": "agent"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "a"}, {"source": "a", "target": "e"}]
        msg = wpn._validate_workflow_execute_payload(nodes, edges)
        assert "必须配置 agentId" in msg

    def test_agent_node_with_inline_binding_ok(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "a", "data": {"type": "agent", "inlineProviderId": "google", "inlineModelId": "gemini"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "a"}, {"source": "a", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) is None

    def test_agent_active_inline_binding_ok(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "a", "data": {"type": "agent", "inlineProviderId": "__active__", "inlineModelId": "__auto__"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "a"}, {"source": "a", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) is None

    def test_agent_use_active_profile_ok(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "a", "data": {"type": "agent", "inlineUseActiveProfile": "true"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "a"}, {"source": "a", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) is None

    def test_human_node_requires_auto_approve(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "h", "data": {"type": "human"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "h"}, {"source": "h", "target": "e"}]
        msg = wpn._validate_workflow_execute_payload(nodes, edges)
        assert "autoApprove=true" in msg

    def test_human_node_auto_approve_ok(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "h", "data": {"type": "human", "autoApprove": True}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "h"}, {"source": "h", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) is None

    def test_duplicate_node_ids(self):
        nodes = [
            {"id": "dup", "data": {"type": "start"}},
            {"id": "dup", "data": {"type": "end"}},
        ]
        assert wpn._validate_workflow_execute_payload(nodes, []) == "存在重复的节点 id"

    def test_edges_not_list(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        assert wpn._validate_workflow_execute_payload(nodes, "bad") == "edges 必须是数组"

    def test_edge_missing_source_target(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        msg = wpn._validate_workflow_execute_payload(nodes, [{"source": "s"}])
        assert "缺少 source 或 target" in msg

    def test_edge_unknown_source(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        msg = wpn._validate_workflow_execute_payload(nodes, [{"source": "ghost", "target": "e"}])
        assert "source 不存在" in msg

    def test_edge_unknown_target(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        msg = wpn._validate_workflow_execute_payload(nodes, [{"source": "s", "target": "ghost"}])
        assert "target 不存在" in msg

    def test_missing_start(self):
        nodes = [{"id": "e", "data": {"type": "end"}}, {"id": "a", "data": {"type": "agent", "agentId": "x"}}]
        edges = [{"source": "a", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) == "工作流必须包含一个开始节点"

    def test_two_start_nodes(self):
        nodes = [
            {"id": "s1", "data": {"type": "start"}},
            {"id": "s2", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s1", "target": "e"}, {"source": "s2", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) == "工作流只能包含一个开始节点"

    def test_start_with_incoming(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
            {"id": "a", "data": {"type": "agent", "agentId": "x"}},
        ]
        edges = [
            {"source": "s", "target": "a"},
            {"source": "a", "target": "s"},
            {"source": "a", "target": "e"},
        ]
        assert wpn._validate_workflow_execute_payload(nodes, edges) == "开始节点不能有输入连接"

    def test_unreachable_node(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
            {"id": "iso", "data": {"type": "agent", "agentId": "x"}},
        ]
        edges = [{"source": "s", "target": "e"}, {"source": "iso", "target": "e"}]
        msg = wpn._validate_workflow_execute_payload(nodes, edges)
        assert "未从开始节点连通" in msg

    def test_no_path_to_end(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "e", "data": {"type": "end"}},
            {"id": "dead", "data": {"type": "agent", "agentId": "x"}},
        ]
        edges = [{"source": "s", "target": "e"}, {"source": "s", "target": "dead"}]
        msg = wpn._validate_workflow_execute_payload(nodes, edges)
        assert "无法流向结束节点" in msg

    def test_valid_payload_returns_none(self):
        nodes = [
            {"id": "s", "data": {"type": "start"}},
            {"id": "a", "data": {"type": "agent", "agentId": "x"}},
            {"id": "e", "data": {"type": "end"}},
        ]
        edges = [{"source": "s", "target": "a"}, {"source": "a", "target": "e"}]
        assert wpn._validate_workflow_execute_payload(nodes, edges) is None
