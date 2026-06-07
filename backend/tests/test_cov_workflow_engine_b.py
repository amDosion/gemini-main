"""Coverage-focused unit/integration tests for three WorkflowEngine helper modules.

Modules under test (SUT):
  - app.services.agent.workflow_engine.image_pipeline   (image gen/edit param mapping + pipelines)
  - app.services.agent.workflow_engine.builtin_tools    (builtin tool dispatch incl. SSRF-guarded ones)
  - app.services.agent.workflow_engine.flow_control      (loop/branch routing + expression eval)

Design notes
------------
These three modules are *helper* modules: every public function takes the live
``WorkflowEngine`` instance as its first argument and reaches back into the
engine for pure utilities (``_get_tool_arg``, ``_to_int`` ...) and for external
boundaries (``_create_provider_service``, the MCP manager, the network, the
browser). To exercise the real param-mapping / dispatch / routing logic faithfully
we construct a *real* ``WorkflowEngine`` (same pattern as
``test_smoke_agent_workflow.py``) so all the pure helpers bind correctly, and we
mock ONLY the external boundaries:

  * provider services (``generate_image`` / ``edit_image`` / ``expand_image`` / ``chat``)
  * provider profile ranking / candidate model listing / reference-image normalization
  * the MCP manager and per-user MCP config DB row
  * the network (DuckDuckGo ``urlopen`` via ``fetch_duckduckgo_results``)
  * the browser functions (``read_webpage`` / ``selenium_browse``)

The module-under-test's own logic (mode routing, kwargs assembly, retry loop,
validation gating, dispatch table, loop-bound math, branch selection, expression
evaluation) is never mocked.

asyncio_mode=auto is on, so plain ``async def`` tests run. ``filterwarnings=error::RuntimeWarning``
is active, so every coroutine boundary below is awaited.
"""

from __future__ import annotations

import json as _json
from types import SimpleNamespace

import pytest

from app.services.agent.execution_context import ExecutionContext
from app.services.agent.workflow_engine import WorkflowEngine
from app.services.agent.workflow_engine import builtin_tools, flow_control, image_pipeline


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
    """Minimal SQLAlchemy session stub returning a single row for any query."""

    def __init__(self, row=None):
        self._row = row

    def query(self, _model):
        return _FakeQuery(self._row)


def _make_engine(db_row=None, user_id="user-b") -> WorkflowEngine:
    """A real WorkflowEngine with a fake db + llm_service carrying a user id."""
    return WorkflowEngine(
        db=_FakeDb(db_row),
        llm_service=SimpleNamespace(user_id=user_id),
    )


class _FakeProfile:
    def __init__(self, provider_id: str, profile_id: str = "p1"):
        self.provider_id = provider_id
        self.id = profile_id


@pytest.fixture
def engine() -> WorkflowEngine:
    return _make_engine()


# ===========================================================================
# flow_control.py
# ===========================================================================


class TestResolveMaxVisits:
    def test_loop_node_uses_max_iterations_plus_buffer(self, engine):
        # max_iterations=5 -> max(2, 5+2) = 7
        assert flow_control.resolve_max_visits(engine, "loop", {"max_iterations": 5}) == 7

    def test_loop_node_camelcase_key(self, engine):
        assert flow_control.resolve_max_visits(engine, "loop", {"maxIterations": 1}) == 3

    def test_loop_node_floor_is_two(self, engine):
        # max_iterations default 3 when absent -> max(2, 3+2)=5
        assert flow_control.resolve_max_visits(engine, "loop", {}) == 5
        # explicit 0 is falsy and short-circuits the `or` chain back to the
        # default of 3 -> max(2, 3+2)=5 (0 is treated as "unset" by design).
        assert flow_control.resolve_max_visits(engine, "loop", {"max_iterations": 0}) == 5
        # negative still floors at 2: max(2, -1+2)=2
        assert flow_control.resolve_max_visits(engine, "loop", {"max_iterations": -1}) == 2

    def test_non_loop_node_uses_engine_default(self, engine):
        assert flow_control.resolve_max_visits(engine, "agent", {}) == engine.DEFAULT_MAX_NODE_VISITS


class TestResolveMaxParallelNodes:
    def test_explicit_value_clamped_to_server_ceiling(self, engine):
        # svc-agent-2: a caller-supplied value can never amplify fan-out beyond
        # the server ceiling (DEFAULT_MAX_PARALLEL_NODES); it may only reduce it.
        assert (
            flow_control.resolve_max_parallel_nodes(engine, {"max_parallel_nodes": 100})
            == engine.DEFAULT_MAX_PARALLEL_NODES
        )
        assert flow_control.resolve_max_parallel_nodes(engine, {"max_parallel_nodes": 1}) == 1
        assert flow_control.resolve_max_parallel_nodes(engine, {"maxParallelNodes": 4}) == 4

    def test_negative_string_clamped_up_to_one(self, engine):
        # "-5" is a truthy non-empty string -> parsed to -5 -> max(1, min(-5, ceiling))=1
        assert flow_control.resolve_max_parallel_nodes(engine, {"max_parallel_nodes": "-5"}) == 1

    def test_zero_is_falsy_and_uses_default(self, engine):
        # 0 short-circuits the `or` chain -> raw stays None -> engine default
        assert (
            flow_control.resolve_max_parallel_nodes(engine, {"max_parallel_nodes": 0})
            == engine.DEFAULT_MAX_PARALLEL_NODES
        )

    def test_float_string_is_parsed(self, engine):
        assert flow_control.resolve_max_parallel_nodes(engine, {"workflowMaxParallelNodes": "3.9"}) == 3

    def test_invalid_value_falls_back_to_default(self, engine):
        assert (
            flow_control.resolve_max_parallel_nodes(engine, {"max_parallel_nodes": "abc"})
            == engine.DEFAULT_MAX_PARALLEL_NODES
        )

    def test_missing_and_non_dict_use_default(self, engine):
        assert flow_control.resolve_max_parallel_nodes(engine, {}) == engine.DEFAULT_MAX_PARALLEL_NODES
        assert flow_control.resolve_max_parallel_nodes(engine, []) == engine.DEFAULT_MAX_PARALLEL_NODES  # type: ignore[arg-type]


class TestSelectOutgoingEdges:
    def _edges(self):
        return [
            {"id": "e1", "source_handle": "output-true"},
            {"id": "e2", "source_handle": "output-false"},
        ]

    def test_empty_edges_returns_empty(self, engine):
        assert flow_control.select_outgoing_edges(engine, {}, [], {"mode": "all"}) == []

    def test_mode_none_returns_empty(self, engine):
        assert flow_control.select_outgoing_edges(engine, {}, self._edges(), {"mode": "none"}) == []

    def test_mode_all_default_returns_all(self, engine):
        edges = self._edges()
        # routing missing -> defaults to "all"
        assert flow_control.select_outgoing_edges(engine, {}, edges, {}) == edges

    def test_branch_true_selects_true_handle(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "branch", "branch": "true"})
        assert selected == [edges[0]]

    def test_branch_false_selects_false_handle(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "branch", "branch": "false"})
        assert selected == [edges[1]]

    def test_branch_fallback_to_sorted_index_when_no_handle(self, engine):
        # No matching handles -> sorted by id, true->idx0, false->idx1
        edges = [{"id": "b"}, {"id": "a"}]
        sel_true = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "branch", "branch": "true"})
        assert sel_true == [{"id": "a"}]  # sorted first
        sel_false = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "branch", "branch": "false"})
        assert sel_false == [{"id": "b"}]

    def test_branch_index_selects_matching_handle(self, engine):
        edges = [
            {"id": "e0", "sourceHandle": "output-0"},
            {"id": "e1", "sourceHandle": "output-1"},
        ]
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "branch_index", "branchIndex": 1})
        assert selected == [edges[1]]

    def test_branch_index_fallback_wraps_modulo(self, engine):
        edges = [{"id": "b"}, {"id": "a"}]
        # branchIndex 3 % 2 == 1 -> sorted[1] == {"id": "b"}
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "branch_index", "branchIndex": 3})
        assert selected == [{"id": "b"}]

    def test_loop_continue_selects_true_handle(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "loop", "continue": True})
        assert selected == [edges[0]]

    def test_loop_stop_selects_false_handle(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "loop", "continue": False})
        assert selected == [edges[1]]

    def test_loop_fallback_sorted(self, engine):
        edges = [{"id": "z"}, {"id": "a"}]
        sel_stop = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "loop", "continue": False})
        assert sel_stop == [{"id": "z"}]  # idx min(1, len-1)=1

    def test_edge_id_mode_selects_by_id(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(engine, {}, edges, {"mode": "edge_id", "edgeId": "e2"})
        assert selected == [edges[1]]

    def test_unknown_mode_falls_back_to_all(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(
            engine, {"id": "node-x"}, edges, {"mode": "no-such-mode"}
        )
        assert selected == edges

    def test_edge_id_no_match_falls_through_to_all(self, engine):
        edges = self._edges()
        selected = flow_control.select_outgoing_edges(
            engine, {"id": "n"}, edges, {"mode": "edge_id", "edgeId": "missing"}
        )
        assert selected == edges


class TestGetSourceHandleAndNodeType:
    def test_get_source_handle_prefers_snake_case(self, engine):
        assert flow_control.get_source_handle(engine, {"source_handle": "a", "sourceHandle": "b"}) == "a"
        assert flow_control.get_source_handle(engine, {"sourceHandle": "b"}) == "b"
        assert flow_control.get_source_handle(engine, {}) == ""

    def test_get_node_type_normalizes(self, engine):
        assert flow_control.get_node_type(engine, {"data": {"type": "Loop-Node"}}) == "loop_node"
        assert flow_control.get_node_type(engine, {"type": "Branch"}) == "branch"
        assert flow_control.get_node_type(engine, {}) == "unknown"


class TestDeriveNodeInputText:
    def test_prefers_latest_packet(self, engine):
        ctx = ExecutionContext({"task": "ignored"})
        packets = [{"output": {"text": "from-packet"}}]
        assert flow_control.derive_node_input_text(engine, ctx, {"task": "x"}, packets) == "from-packet"

    def test_falls_back_to_context_latest_output(self, engine):
        ctx = ExecutionContext({"task": "x"})
        ctx.set_output("n1", {"text": "ctx-output"})
        assert flow_control.derive_node_input_text(engine, ctx, {"task": "x"}, []) == "ctx-output"

    def test_falls_back_to_initial_input_task(self, engine):
        ctx = ExecutionContext({"task": "the-task"})
        assert flow_control.derive_node_input_text(engine, ctx, {"task": "the-task"}, []) == "the-task"

    def test_initial_input_input_and_text_keys(self, engine):
        ctx = ExecutionContext({})
        assert flow_control.derive_node_input_text(engine, ctx, {"input": "via-input"}, []) == "via-input"
        assert flow_control.derive_node_input_text(engine, ctx, {"text": "via-text"}, []) == "via-text"


class TestEvaluateContainsClause:
    def test_blank_returns_none(self, engine):
        assert flow_control.evaluate_contains_clause(engine, "  ") is None

    def test_non_contains_returns_none(self, engine):
        assert flow_control.evaluate_contains_clause(engine, "hello world") is None

    def test_true_when_right_in_left(self, engine):
        assert flow_control.evaluate_contains_clause(engine, "hello world contains world") is True

    def test_false_when_right_absent(self, engine):
        assert flow_control.evaluate_contains_clause(engine, "hello contains zzz") is False

    def test_empty_right_returns_false(self, engine):
        assert flow_control.evaluate_contains_clause(engine, "left contains ''") is False


class TestEvaluateContainsExpression:
    def test_none_when_no_contains(self, engine):
        assert flow_control.evaluate_contains_expression(engine, "just text") is None

    def test_single_clause(self, engine):
        assert flow_control.evaluate_contains_expression(engine, "report success contains success") is True

    def test_and_operator(self, engine):
        expr = "abc def contains abc and abc def contains def"
        assert flow_control.evaluate_contains_expression(engine, expr) is True

    def test_or_operator_short_circuit_false_then_true(self, engine):
        expr = "abc contains zzz or abc contains abc"
        assert flow_control.evaluate_contains_expression(engine, expr) is True

    def test_invalid_clause_returns_none(self, engine):
        # second clause not a contains clause -> clause_value None -> None
        expr = "abc contains abc and not-a-clause"
        assert flow_control.evaluate_contains_expression(engine, expr) is None


class TestEvaluateExpression:
    def _ctx(self):
        return ExecutionContext({"task": "hi"})

    def test_none_expression(self, engine):
        assert flow_control.evaluate_expression(engine, None, self._ctx(), {}, []) == (False, "")

    def test_boolean_resolution(self, engine):
        ctx = self._ctx()
        assert flow_control.evaluate_expression(engine, True, ctx, {}, []) == (True, "True")  # type: ignore[arg-type]

    def test_numeric_resolution(self, engine):
        ctx = self._ctx()
        truthy, text = flow_control.evaluate_expression(engine, 5, ctx, {}, [])  # type: ignore[arg-type]
        assert truthy is True and text == "5"
        falsy, _ = flow_control.evaluate_expression(engine, 0, ctx, {}, [])  # type: ignore[arg-type]
        assert falsy is False

    def test_empty_string(self, engine):
        assert flow_control.evaluate_expression(engine, "", self._ctx(), {}, []) == (False, "")

    def test_truthy_keywords(self, engine):
        for token in ("true", "YES", "1"):
            assert flow_control.evaluate_expression(engine, token, self._ctx(), {}, [])[0] is True
        for token in ("false", "no", "0"):
            assert flow_control.evaluate_expression(engine, token, self._ctx(), {}, [])[0] is False

    def test_includes_syntax(self, engine):
        ok, _ = flow_control.evaluate_expression(engine, "'hello world'.includes('world')", self._ctx(), {}, [])
        assert ok is True
        bad, _ = flow_control.evaluate_expression(engine, "'hello'.includes('zzz')", self._ctx(), {}, [])
        assert bad is False

    def test_contains_expression_path(self, engine):
        ok, _ = flow_control.evaluate_expression(engine, "alpha beta contains beta", self._ctx(), {}, [])
        assert ok is True

    def test_safe_eval_numeric_comparison(self, engine):
        ok, _ = flow_control.evaluate_expression(engine, "len('abcd') > 2", self._ctx(), {}, [])
        assert ok is True
        bad, _ = flow_control.evaluate_expression(engine, "1 > 2", self._ctx(), {}, [])
        assert bad is False

    def test_js_operators_normalized(self, engine):
        ok, _ = flow_control.evaluate_expression(engine, "1 === 1 && 2 !== 3", self._ctx(), {}, [])
        assert ok is True

    def test_unparseable_expression_returns_false(self, engine):
        bad, text = flow_control.evaluate_expression(engine, "this is @@ not valid", self._ctx(), {}, [])
        assert bad is False
        assert text == "this is @@ not valid"


class TestMergeOutputs:
    def test_empty_inputs(self, engine):
        assert flow_control.merge_outputs(engine, [], "concat") == {"text": ""}

    def test_latest_strategy(self, engine):
        assert flow_control.merge_outputs(engine, ["a", "b"], "latest") == "b"

    def test_json_merge_strategy(self, engine):
        merged = flow_control.merge_outputs(engine, [{"a": 1}, {"b": 2}, "loose"], "json_merge")
        assert merged["a"] == 1 and merged["b"] == 2
        assert merged["items"] == ["loose"]

    def test_concat_strategy_joins_text(self, engine):
        merged = flow_control.merge_outputs(engine, [{"text": "x"}, {"text": "y"}], "concat")
        assert merged["text"] == "x\n\ny"
        assert merged["results"] == [{"text": "x"}, {"text": "y"}]


class TestParseToolArgs:
    def test_none_and_empty(self, engine):
        assert flow_control.parse_tool_args(engine, None) == {}
        assert flow_control.parse_tool_args(engine, "   ") == {}

    def test_dict_passthrough(self, engine):
        assert flow_control.parse_tool_args(engine, {"a": 1}) == {"a": 1}

    def test_list_wrapped(self, engine):
        assert flow_control.parse_tool_args(engine, [1, 2]) == {"items": [1, 2]}

    def test_json_object_string(self, engine):
        assert flow_control.parse_tool_args(engine, '{"k": "v"}') == {"k": "v"}

    def test_json_list_string(self, engine):
        assert flow_control.parse_tool_args(engine, "[1, 2]") == {"items": [1, 2]}

    def test_json_scalar_string(self, engine):
        assert flow_control.parse_tool_args(engine, "42") == {"value": 42}

    def test_non_json_string_becomes_input(self, engine):
        assert flow_control.parse_tool_args(engine, "free text") == {"input": "free text"}


class TestResolveToolArgsTemplate:
    def test_empty(self, engine):
        ctx = ExecutionContext({})
        assert flow_control.resolve_tool_args_template(engine, None, ctx) == {}
        assert flow_control.resolve_tool_args_template(engine, "", ctx) == {}

    def test_dict_template_recursive_resolve(self, engine):
        ctx = ExecutionContext({"task": "T"})
        out = flow_control.resolve_tool_args_template(engine, {"q": "{{input.task}}"}, ctx)
        assert out == {"q": "T"}

    def test_json_string_template_parsed_then_resolved(self, engine):
        ctx = ExecutionContext({"task": "T"})
        out = flow_control.resolve_tool_args_template(engine, '{"q": "{{input.task}}"}', ctx)
        assert out == {"q": "T"}

    def test_invalid_json_string_falls_back_to_template(self, engine):
        ctx = ExecutionContext({"task": "T"})
        # starts with "{" but invalid json -> resolve_template on raw string (no placeholders)
        out = flow_control.resolve_tool_args_template(engine, "{not json", ctx)
        assert out == "{not json"

    def test_plain_string_template(self, engine):
        ctx = ExecutionContext({"task": "T"})
        assert flow_control.resolve_tool_args_template(engine, "{{input.task}}", ctx) == "T"

    def test_non_string_non_collection_returned_as_is(self, engine):
        ctx = ExecutionContext({})
        assert flow_control.resolve_tool_args_template(engine, 123, ctx) == 123


class TestResolveTemplateValue:
    def test_recurses_list_and_dict(self, engine):
        ctx = ExecutionContext({"task": "T"})
        value = {"a": "{{input.task}}", "b": ["{{input.task}}", 5]}
        out = flow_control.resolve_template_value(engine, value, ctx)
        assert out == {"a": "T", "b": ["T", 5]}

    def test_scalar_passthrough(self, engine):
        ctx = ExecutionContext({})
        assert flow_control.resolve_template_value(engine, 7, ctx) == 7


class TestSelectRouterBranchHeuristic:
    def test_keyword_strategy_matches_rule(self, engine):
        idx, reason = flow_control.select_router_branch_heuristic(
            engine,
            strategy="keyword",
            router_prompt="1: urgent, hot\n2: cold",
            input_text="this is URGENT now",
            outgoing_count=3,
        )
        assert idx == 1
        assert reason.startswith("keyword:")

    def test_intent_error_routes_to_index_one(self, engine):
        idx, reason = flow_control.select_router_branch_heuristic(
            engine, strategy="intent", router_prompt="", input_text="there was an error", outgoing_count=3
        )
        assert idx == 1 and reason == "intent:error"

    def test_intent_approval_routes_to_last(self, engine):
        idx, reason = flow_control.select_router_branch_heuristic(
            engine, strategy="intent", router_prompt="", input_text="需要人工审批", outgoing_count=4
        )
        assert idx == 3 and reason == "intent:approval"

    def test_intent_summary_routes_to_first(self, engine):
        idx, reason = flow_control.select_router_branch_heuristic(
            engine, strategy="intent", router_prompt="", input_text="生成总结报告", outgoing_count=3
        )
        assert idx == 0 and reason == "intent:summary"

    def test_hash_fallback_is_deterministic(self, engine):
        idx, reason = flow_control.select_router_branch_heuristic(
            engine, strategy="intent", router_prompt="rp", input_text="neutral input", outgoing_count=3
        )
        assert 0 <= idx < 3 and reason == "intent:hash"


@pytest.mark.asyncio
class TestSelectRouterBranchLLM:
    async def test_single_branch_short_circuits(self, engine):
        idx, reason = await flow_control.select_router_branch(engine, "intent", "", "anything", 1)
        assert idx == 0 and reason == "single_branch"

    async def test_llm_strategy_parses_branch_index(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_select_text_chat_target", lambda: ("google", "gemini"))

        async def fake_invoke(**kwargs):
            return {"text": '{"branchIndex": 1, "reason": "because"}'}

        monkeypatch.setattr(engine, "_invoke_llm_chat", fake_invoke)
        idx, reason = await flow_control.select_router_branch(engine, "llm", "rules", "input", 3)
        assert idx == 1
        assert reason == "llm:because"

    async def test_llm_strategy_regex_fallback_on_bad_json(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_select_text_chat_target", lambda: ("google", "gemini"))

        async def fake_invoke(**kwargs):
            return {"text": "the answer is 2"}

        monkeypatch.setattr(engine, "_invoke_llm_chat", fake_invoke)
        idx, _ = await flow_control.select_router_branch(engine, "llm", "", "input", 3)
        assert idx == 2

    async def test_llm_failure_falls_back_to_heuristic(self, monkeypatch, engine):
        def boom():
            raise RuntimeError("no chat target")

        monkeypatch.setattr(engine, "_select_text_chat_target", boom)
        # heuristic path: "error" keyword -> index min(1, count-1)
        idx, reason = await flow_control.select_router_branch(engine, "llm", "", "fatal error here", 3)
        assert idx == 1 and reason == "intent:error"


# ===========================================================================
# image_pipeline.py
# ===========================================================================


class TestResolutionNormalization:
    def test_normalize_resolution_tier_mappings(self, engine):
        assert image_pipeline.normalize_resolution_tier(engine, "1024x1024") == "1K"
        assert image_pipeline.normalize_resolution_tier(engine, "2k") == "2K"
        assert image_pipeline.normalize_resolution_tier(engine, "4096") == "4K"
        assert image_pipeline.normalize_resolution_tier(engine, "1280*1280") == "1.25K"
        # already-canonical passthrough
        assert image_pipeline.normalize_resolution_tier(engine, "1.5K") == "1.5K"

    def test_normalize_resolution_tier_unknown_and_blank(self, engine):
        assert image_pipeline.normalize_resolution_tier(engine, "") is None
        assert image_pipeline.normalize_resolution_tier(engine, "999x999") is None

    def test_resolve_google_image_size(self, engine):
        assert image_pipeline.resolve_google_image_size(engine, "1024") == "1K"
        assert image_pipeline.resolve_google_image_size(engine, "1.25K") == "1K"
        assert image_pipeline.resolve_google_image_size(engine, "2K") == "2K"
        assert image_pipeline.resolve_google_image_size(engine, "4K") == "2K"
        assert image_pipeline.resolve_google_image_size(engine, "unknown") is None

    def test_resolve_tongyi_resolution(self, engine):
        assert image_pipeline.resolve_tongyi_resolution(engine, "1.5K") == "1.5K"
        assert image_pipeline.resolve_tongyi_resolution(engine, "4K") == "2K"  # downgraded
        assert image_pipeline.resolve_tongyi_resolution(engine, "") is None

    def test_resolve_generic_image_size(self, engine):
        assert image_pipeline.resolve_generic_image_size(engine, "1280x720") == "1280x720"
        assert image_pipeline.resolve_generic_image_size(engine, "1K") == "1024x1024"
        assert image_pipeline.resolve_generic_image_size(engine, "1.5K") == "1536x1536"
        assert image_pipeline.resolve_generic_image_size(engine, "4K") == "1792x1024"
        assert image_pipeline.resolve_generic_image_size(engine, "") is None
        assert image_pipeline.resolve_generic_image_size(engine, "weird") is None

    def test_resolve_video_resolution(self, engine):
        assert image_pipeline.resolve_video_resolution(engine, "1920x1080") == "1080p"
        assert image_pipeline.resolve_video_resolution(engine, "720p") == "720p"
        assert image_pipeline.resolve_video_resolution(engine, "4k") == "4k"
        assert image_pipeline.resolve_video_resolution(engine, "") is None
        assert image_pipeline.resolve_video_resolution(engine, "5000") is None

    def test_guess_audio_mime_type(self, engine):
        assert image_pipeline.guess_audio_mime_type(engine, "wav") == "audio/wav"
        assert image_pipeline.guess_audio_mime_type(engine, "FLAC") == "audio/flac"
        assert image_pipeline.guess_audio_mime_type(engine, "unknown") == "audio/mpeg"


class TestBuildGenerateKwargs:
    def test_google_branch_full_mapping(self, engine):
        args = {
            "number_of_images": "3",
            "aspect_ratio": "16:9",
            "image_size": "2K",
            "image_style": "vivid",
            "output_mime_type": "image/png",
            "output_compression_quality": "200",  # clamped to 100
            "enhance_prompt": "true",
        }
        kwargs = image_pipeline.build_generate_kwargs(engine, "google", args)
        assert kwargs["number_of_images"] == 3
        assert kwargs["aspect_ratio"] == "16:9"
        assert kwargs["image_size"] == "2K"
        assert kwargs["image_style"] == "vivid"
        assert kwargs["output_mime_type"] == "image/png"
        assert kwargs["output_compression_quality"] == 100
        assert kwargs["enhance_prompt"] is True

    def test_google_clamps_number_of_images(self, engine):
        kwargs = image_pipeline.build_generate_kwargs(engine, "google-vertex", {"n": "50"})
        assert kwargs["number_of_images"] == 8

    def test_tongyi_branch_mapping(self, engine):
        args = {
            "num_images": "10",  # clamped to 4
            "aspect_ratio": "1:1",
            "resolution": "4K",  # downgraded to 2K
            "style": "anime",
            "negative_prompt": "blurry",
            "seed": "7",
            "prompt_extend": "yes",
            "add_magic_suffix": "no",
        }
        kwargs = image_pipeline.build_generate_kwargs(engine, "tongyi", args)
        assert kwargs["num_images"] == 4
        assert kwargs["aspect_ratio"] == "1:1"
        assert kwargs["resolution"] == "2K"
        assert kwargs["style"] == "anime"
        assert kwargs["negative_prompt"] == "blurry"
        assert kwargs["seed"] == 7
        assert kwargs["promptExtend"] is True
        assert kwargs["addMagicSuffix"] is False

    def test_dashscope_uses_tongyi_branch(self, engine):
        kwargs = image_pipeline.build_generate_kwargs(engine, "dashscope", {"num_images": "2"})
        assert kwargs["num_images"] == 2

    def test_generic_openai_branch(self, engine):
        args = {"size": "1K", "quality": "hd", "style": "natural", "n": "20", "response_format": "url"}
        kwargs = image_pipeline.build_generate_kwargs(engine, "openai", args)
        assert kwargs["size"] == "1024x1024"
        assert kwargs["quality"] == "hd"
        assert kwargs["style"] == "natural"
        assert kwargs["n"] == 10  # clamped
        assert kwargs["response_format"] == "url"

    def test_generic_branch_empty_args(self, engine):
        assert image_pipeline.build_generate_kwargs(engine, "openai", {}) == {}


class TestBuildImageEditKwargs:
    def test_google_edit_mode_and_session_autofill(self, engine):
        # image-chat-edit with no session -> engine generates one
        kwargs = image_pipeline.build_image_edit_kwargs(
            engine, "google", {"mode": "image-chat-edit", "number_of_images": "2"}, is_outpaint=False
        )
        assert kwargs["mode"] == "image-chat-edit"
        assert kwargs["number_of_images"] == 2
        assert kwargs.get("frontend_session_id")  # auto-generated, non-empty

    def test_google_default_mode_when_unspecified(self, engine):
        # google + no mode + not outpaint -> normalize to image-chat-edit
        kwargs = image_pipeline.build_image_edit_kwargs(engine, "google", {}, is_outpaint=False)
        assert kwargs["mode"] == "image-chat-edit"

    def test_google_outpaint_offsets(self, engine):
        args = {
            "mode": "scale",
            "x_scale": "1.5",
            "y_scale": "2.0",
            "output_ratio": "16:9",
        }
        kwargs = image_pipeline.build_image_edit_kwargs(engine, "google", args, is_outpaint=True)
        assert kwargs["mode"] == "scale"
        assert kwargs["x_scale"] == 1.5
        assert kwargs["y_scale"] == 2.0
        assert kwargs["output_ratio"] == "16:9"

    def test_google_image_size_resolution(self, engine):
        kwargs = image_pipeline.build_image_edit_kwargs(
            engine, "google", {"mode": "image-mask-edit", "image_size": "2K"}, is_outpaint=False
        )
        assert kwargs["image_size"] == "2K"

    def test_tongyi_edit_mapping(self, engine):
        args = {"mode": "image-inpainting", "number_of_images": "9", "negative_prompt": "x", "seed": "3"}
        kwargs = image_pipeline.build_image_edit_kwargs(engine, "tongyi", args, is_outpaint=False)
        assert kwargs["mode"] == "image-inpainting"
        assert kwargs["number_of_images"] == 4  # clamped to 4 for tongyi
        assert kwargs["negative_prompt"] == "x"
        assert kwargs["seed"] == 3

    def test_other_provider_only_mode(self, engine):
        kwargs = image_pipeline.build_image_edit_kwargs(
            engine, "openai", {"mode": "image-mask-edit"}, is_outpaint=False
        )
        assert kwargs == {"mode": "image-mask-edit"}


class TestSanitizeVisionTextPrompt:
    def test_blank(self, engine):
        assert image_pipeline.sanitize_vision_text_prompt(engine, "  ") == ""

    def test_redacts_data_url_and_http(self, engine):
        text = "see data:image/png;base64,AAAABBBBCCCC and http://x.com/a.png"
        out = image_pipeline.sanitize_vision_text_prompt(engine, text)
        assert "[ATTACHED_IMAGE_DATA]" in out
        assert "[IMAGE_REFERENCE_URL]" in out
        assert "base64" not in out

    def test_redacts_filesystem_paths(self, engine):
        out = image_pipeline.sanitize_vision_text_prompt(engine, "open /tmp/foo.png now")
        assert "[IMAGE_REFERENCE_PATH]" in out


class TestVisionPromptAndSummary:
    def test_build_vision_understand_prompt_with_and_without_task(self, engine):
        with_task = image_pipeline.build_vision_understand_prompt(engine, "describe this")
        assert "describe this" in with_task
        assert "primaryObject" in with_task
        bare = image_pipeline.build_vision_understand_prompt(engine, "   ")
        assert "primaryObject" in bare

    def test_summary_from_analysis(self, engine):
        analysis = {"primaryObject": "shoe", "colors": ["", "red"], "confidence": 0.9}
        summary = image_pipeline.build_vision_understand_summary(engine, analysis)
        assert "识别主体：shoe" in summary
        assert "主色：red" in summary
        assert "置信度：0.9" in summary

    def test_summary_falls_back_to_text(self, engine):
        summary = image_pipeline.build_vision_understand_summary(
            engine, {}, fallback_text="```json\nplain fallback\n```"
        )
        assert "plain fallback" in summary

    def test_summary_default_when_empty(self, engine):
        assert image_pipeline.build_vision_understand_summary(engine, {}, fallback_text="") == "已完成图片理解。"


class TestExtractJsonObjectFromText:
    def test_direct_json(self, engine):
        assert image_pipeline.extract_json_object_from_text(engine, '{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self, engine):
        assert image_pipeline.extract_json_object_from_text(engine, '```json\n{"b": 2}\n```') == {"b": 2}

    def test_json_embedded_in_prose(self, engine):
        text = 'Here is the result: {"c": 3} thanks'
        assert image_pipeline.extract_json_object_from_text(engine, text) == {"c": 3}

    def test_no_json_returns_empty(self, engine):
        assert image_pipeline.extract_json_object_from_text(engine, "no json here") == {}

    def test_malformed_braces_returns_empty(self, engine):
        assert image_pipeline.extract_json_object_from_text(engine, "{not: valid, json}") == {}


class TestBuildGuardedEditPrompt:
    def test_includes_identity_constraint(self, engine):
        out = image_pipeline.build_guarded_edit_prompt(
            engine, "make it pop", preserve_product_identity=True, output_language="en"
        )
        assert "make it pop" in out
        assert "EXACT same product identity" in out
        assert "ENGLISH only" in out

    def test_feedback_hint_appended(self, engine):
        out = image_pipeline.build_guarded_edit_prompt(
            engine, "x", preserve_product_identity=False, output_language="zh", feedback_hint="brighter"
        )
        assert "Retry fix focus: brighter" in out
        assert "EXACT same product identity" not in out

    def test_empty_base_prompt_default(self, engine):
        out = image_pipeline.build_guarded_edit_prompt(engine, "", preserve_product_identity=False)
        assert "Enhance the image for ecommerce use." in out


class TestSelectGoogleVisionEvalModel:
    def test_prefers_high_rank_gemini(self, engine, monkeypatch):
        monkeypatch.setattr(
            engine,
            "_list_saved_model_ids",
            lambda profile: ["imagen-3", "gemini-2.5-flash", "gemini-1.5-pro"],
        )
        chosen = image_pipeline.select_google_vision_eval_model(engine, _FakeProfile("google"))
        # gemini-2.5-flash gets best (lowest) rank due to "2.5" and "flash"
        assert chosen == "gemini-2.5-flash"

    def test_default_when_no_vision_models(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "_list_saved_model_ids", lambda profile: ["imagen-3", "tts-1"])
        assert image_pipeline.select_google_vision_eval_model(engine, _FakeProfile("google")) == "gemini-2.5-flash"


# --- image_pipeline async pipelines (mock provider boundaries only) ---------


def _patch_image_boundaries(monkeypatch, engine, *, profiles, candidate_models):
    """Stub the engine's provider-boundary helpers; keep pipeline logic real."""
    monkeypatch.setattr(engine, "_rank_provider_profiles_for_tool", lambda *a, **k: profiles)
    monkeypatch.setattr(engine, "_list_candidate_image_models", lambda **k: list(candidate_models))
    monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda **k: "normalized-ref")


@pytest.mark.asyncio
class TestRunImageGenerateTool:
    async def test_happy_path_returns_normalized_payload(self, monkeypatch, engine):
        profile = _FakeProfile("google")
        _patch_image_boundaries(monkeypatch, engine, profiles=[profile], candidate_models=["imagen-3"])

        class FakeService:
            async def generate_image(self, prompt, model, **kwargs):
                return {"images": [{"imageUrl": "http://img/1.png"}]}

        async def fake_create(**kwargs):
            return FakeService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)

        result = await image_pipeline.run_image_generate_tool(
            engine, {"prompt": "a cat", "provider_id": "google"}, latest_input=None
        )
        assert result["tool"] == "image_generate"
        assert result["status"] == "completed"
        assert result["provider"] == "google"
        assert result["model"] == "imagen-3"
        assert result["imageUrl"] == "http://img/1.png"

    async def test_no_candidate_models_then_raises(self, monkeypatch, engine):
        _patch_image_boundaries(monkeypatch, engine, profiles=[_FakeProfile("google")], candidate_models=[])

        async def fake_create(**kwargs):
            raise AssertionError("should not create a service with no candidate models")

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)

        with pytest.raises(ValueError) as exc:
            await image_pipeline.run_image_generate_tool(engine, {"prompt": "x"}, latest_input=None)
        assert "图像生成失败" in str(exc.value)

    async def test_service_error_is_collected_and_raised(self, monkeypatch, engine):
        _patch_image_boundaries(monkeypatch, engine, profiles=[_FakeProfile("google")], candidate_models=["m1"])

        class FailingService:
            async def generate_image(self, prompt, model, **kwargs):
                raise RuntimeError("provider down")

        async def fake_create(**kwargs):
            return FailingService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)

        with pytest.raises(ValueError) as exc:
            await image_pipeline.run_image_generate_tool(engine, {"prompt": "x"}, latest_input=None)
        assert "provider down" in str(exc.value)

    async def test_missing_image_url_treated_as_failure(self, monkeypatch, engine):
        _patch_image_boundaries(monkeypatch, engine, profiles=[_FakeProfile("google")], candidate_models=["m1"])

        class EmptyService:
            async def generate_image(self, prompt, model, **kwargs):
                return {"images": []}

        async def fake_create(**kwargs):
            return EmptyService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        with pytest.raises(ValueError):
            await image_pipeline.run_image_generate_tool(engine, {"prompt": "x"}, latest_input=None)


@pytest.mark.asyncio
class TestRunImageEditTool:
    async def test_requires_source_image(self, engine):
        with pytest.raises(ValueError) as exc:
            await image_pipeline.run_image_edit_tool(engine, {}, latest_input=None)
        assert "缺少输入图片" in str(exc.value)

    async def test_happy_path_with_validation_passed(self, monkeypatch, engine):
        profile = _FakeProfile("google")
        _patch_image_boundaries(monkeypatch, engine, profiles=[profile], candidate_models=["edit-1"])

        class FakeService:
            async def edit_image(self, prompt, model, reference_images, **kwargs):
                return {"images": [{"imageUrl": "http://out/1.png"}]}

        async def fake_create(**kwargs):
            return FakeService()

        async def fake_validate(**kwargs):
            return {"passed": True, "checked": True, "productScore": 90}

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        monkeypatch.setattr(engine, "_validate_image_edit_result", fake_validate)

        result = await image_pipeline.run_image_edit_tool(
            engine,
            {"imageUrl": "http://in/0.png", "edit_prompt": "brighten", "mode": "image-chat-edit"},
            latest_input=None,
            is_outpaint=False,
        )
        assert result["tool"] == "image_edit"
        assert result["status"] == "completed"
        assert result["imageUrl"] == "http://out/1.png"
        assert result["validation"]["passed"] is True
        assert result["provider"] == "google"

    async def test_validation_failure_then_exhausts_and_raises(self, monkeypatch, engine):
        profile = _FakeProfile("google")
        _patch_image_boundaries(monkeypatch, engine, profiles=[profile], candidate_models=["edit-1"])

        class FakeService:
            async def edit_image(self, prompt, model, reference_images, **kwargs):
                return {"images": [{"imageUrl": "http://out/bad.png"}]}

        async def fake_create(**kwargs):
            return FakeService()

        async def fake_validate(**kwargs):
            return {"passed": False, "issues": ["color changed"], "suggestion": "keep color"}

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        monkeypatch.setattr(engine, "_validate_image_edit_result", fake_validate)

        with pytest.raises(ValueError) as exc:
            await image_pipeline.run_image_edit_tool(
                engine,
                {"imageUrl": "http://in/0.png", "max_retries": "0"},
                latest_input=None,
                is_outpaint=False,
            )
        assert "图片编辑失败" in str(exc.value)

    async def test_outpaint_uses_expand_image(self, monkeypatch, engine):
        profile = _FakeProfile("google")
        _patch_image_boundaries(monkeypatch, engine, profiles=[profile], candidate_models=["expand-1"])
        called = {"expand": False}

        class FakeService:
            async def expand_image(self, prompt, model, reference_images, **kwargs):
                called["expand"] = True
                return {"images": [{"imageUrl": "http://out/expanded.png"}]}

        async def fake_create(**kwargs):
            return FakeService()

        async def fake_validate(**kwargs):
            return {"passed": True}

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        monkeypatch.setattr(engine, "_validate_image_edit_result", fake_validate)

        result = await image_pipeline.run_image_edit_tool(
            engine,
            {"imageUrl": "http://in/0.png", "preserve_product_identity": "false"},
            latest_input=None,
            is_outpaint=True,
        )
        assert called["expand"] is True
        assert result["tool"] == "image_outpaint"

    async def test_source_image_pulled_from_latest_input(self, monkeypatch, engine):
        profile = _FakeProfile("openai")
        _patch_image_boundaries(monkeypatch, engine, profiles=[profile], candidate_models=["edit-1"])
        seen = {}

        class FakeService:
            async def edit_image(self, prompt, model, reference_images, **kwargs):
                seen["ref"] = reference_images
                return {"images": [{"imageUrl": "http://out/2.png"}]}

        async def fake_create(**kwargs):
            return FakeService()

        async def fake_validate(**kwargs):
            return {"passed": True}

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        monkeypatch.setattr(engine, "_validate_image_edit_result", fake_validate)

        # no imageUrl in tool_args -> falls back to engine._extract_first_image_url(latest_input)
        latest = {"imageUrl": "http://in/from-input.png"}
        result = await image_pipeline.run_image_edit_tool(
            engine, {"preserve_product_identity": "false"}, latest_input=latest, is_outpaint=False
        )
        assert result["status"] == "completed"
        assert seen["ref"]["raw"] == "normalized-ref"


@pytest.mark.asyncio
class TestRunVisionUnderstandTask:
    async def test_requires_reference_image(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda **k: "")
        with pytest.raises(ValueError) as exc:
            await image_pipeline.run_vision_understand_task(
                engine,
                provider_id="google",
                model_id="gemini",
                system_prompt="",
                prompt="describe",
                source_image_url="http://x/a.png",
                temperature=0.2,
                max_tokens=512,
            )
        assert "缺少有效参考图" in str(exc.value)

    async def test_happy_path_parses_json_and_summarizes(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda **k: "ref")
        monkeypatch.setattr(engine, "_guess_image_mime_type_from_reference", lambda ref: "image/png")

        captured = {}

        class FakeService:
            async def chat(self, messages, model, **kwargs):
                captured["model"] = model
                captured["kwargs"] = kwargs
                return {"content": '{"primaryObject": "mug", "confidence": 0.8}', "usage": {"in": 1}}

        async def fake_create(**kwargs):
            return FakeService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)

        result = await image_pipeline.run_vision_understand_task(
            engine,
            provider_id="google",
            model_id="gemini-2.5",
            system_prompt="be terse",
            prompt="what is this",
            source_image_url="http://x/a.png",
            temperature=0.3,
            max_tokens=256,
        )
        assert result["analysis"]["primaryObject"] == "mug"
        assert "识别主体：mug" in result["text"]
        assert result["usage"] == {"in": 1}
        # google provider routes max tokens through max_output_tokens
        assert captured["kwargs"]["max_output_tokens"] == 256

    async def test_non_google_uses_max_tokens(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda **k: "ref")
        monkeypatch.setattr(engine, "_guess_image_mime_type_from_reference", lambda ref: "image/jpeg")
        captured = {}

        class FakeService:
            async def chat(self, messages, model, **kwargs):
                captured["kwargs"] = kwargs
                return {"text": "not json"}

        async def fake_create(**kwargs):
            return FakeService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        result = await image_pipeline.run_vision_understand_task(
            engine,
            provider_id="openai",
            model_id="gpt",
            system_prompt="",
            prompt="x",
            source_image_url="http://x/a.png",
            temperature=0.1,
            max_tokens=128,
        )
        assert captured["kwargs"]["max_tokens"] == 128
        # non-json content -> empty analysis -> fallback summary text
        assert result["analysis"] == {}
        assert result["text"]


@pytest.mark.asyncio
class TestValidateImageEditResult:
    async def test_skip_when_not_preserving_identity(self, engine):
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="s",
            result_image_url="r",
            provider_id="google",
            profile=_FakeProfile("google"),
            preserve_product_identity=False,
            product_match_threshold=70,
        )
        assert out == {"checked": False, "passed": True, "issues": []}

    async def test_skip_when_missing_urls(self, engine):
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="",
            result_image_url="r",
            provider_id="google",
            profile=_FakeProfile("google"),
            preserve_product_identity=True,
            product_match_threshold=70,
        )
        assert out["checked"] is False and out["passed"] is True

    async def test_non_google_provider_not_supported(self, engine):
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="s",
            result_image_url="r",
            provider_id="openai",
            profile=_FakeProfile("openai"),
            preserve_product_identity=True,
            product_match_threshold=70,
        )
        assert out["reason"] == "vision_check_not_supported_for_provider"

    async def test_passed_when_score_above_threshold(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_select_google_vision_eval_model", lambda profile: "gemini-2.5-flash")
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda url, pid: url)

        class FakeService:
            async def chat(self, messages, model, **kwargs):
                return {"content": '{"product_match": true, "product_score": 88, "overlap_risk": "low", "issues": []}'}

        async def fake_create(*a, **k):
            return FakeService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="s.png",
            result_image_url="r.png",
            provider_id="google",
            profile=_FakeProfile("google"),
            preserve_product_identity=True,
            product_match_threshold=70,
        )
        assert out["checked"] is True
        assert out["passed"] is True
        assert out["productScore"] == 88

    async def test_failed_when_below_threshold(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_select_google_vision_eval_model", lambda profile: "gemini-2.5-flash")
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda url, pid: url)

        class FakeService:
            async def chat(self, messages, model, **kwargs):
                return {"content": '{"product_match": true, "product_score": 40, "issues": ["shape drift"]}'}

        async def fake_create(*a, **k):
            return FakeService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="s.png",
            result_image_url="r.png",
            provider_id="google-vertex",
            profile=_FakeProfile("google"),
            preserve_product_identity=True,
            product_match_threshold=70,
        )
        assert out["passed"] is False
        assert out["suggestion"] == "shape drift"  # backfilled from first issue

    async def test_unparseable_vision_response(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_select_google_vision_eval_model", lambda profile: "gemini-2.5-flash")
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda url, pid: url)

        class FakeService:
            async def chat(self, messages, model, **kwargs):
                return {"content": "totally not json"}

        async def fake_create(*a, **k):
            return FakeService()

        monkeypatch.setattr(engine, "_create_provider_service", fake_create)
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="s.png",
            result_image_url="r.png",
            provider_id="google",
            profile=_FakeProfile("google"),
            preserve_product_identity=True,
            product_match_threshold=70,
        )
        assert out["passed"] is True
        assert out["reason"] == "vision_parse_failed"

    async def test_exception_during_eval_is_swallowed(self, monkeypatch, engine):
        monkeypatch.setattr(engine, "_select_google_vision_eval_model", lambda profile: "gemini-2.5-flash")
        monkeypatch.setattr(engine, "_normalize_reference_image_for_provider", lambda url, pid: url)

        async def boom(*a, **k):
            raise RuntimeError("network gone")

        monkeypatch.setattr(engine, "_create_provider_service", boom)
        out = await image_pipeline.validate_image_edit_result(
            engine,
            source_image_url="s.png",
            result_image_url="r.png",
            provider_id="google",
            profile=_FakeProfile("google"),
            preserve_product_identity=True,
            product_match_threshold=70,
        )
        assert out["passed"] is True
        assert out["reason"].startswith("vision_check_failed:")


# ===========================================================================
# builtin_tools.py
# ===========================================================================


class TestNormalizeSearchItems:
    def test_list_payload(self):
        payload = [
            {"title": "T1", "snippet": "S1", "url": "u1"},
            {"name": "T2", "description": "S2", "link": "u2"},
        ]
        items = builtin_tools.normalize_search_items(payload, max_items=5)
        assert items[0]["title"] == "T1"
        assert items[1]["title"] == "T2"
        assert items[1]["snippet"] == "S2"

    def test_json_string_payload(self):
        items = builtin_tools.normalize_search_items('[{"title": "X", "snippet": "Y"}]', max_items=5)
        assert items == [{"title": "X", "snippet": "Y", "url": ""}]

    def test_duckduckgo_dict_payload(self):
        payload = {
            "AbstractText": "abstract body",
            "AbstractURL": "http://a",
            "AbstractSource": "Wikipedia",
            "RelatedTopics": [
                {"Text": "rel1", "FirstURL": "http://r1"},
                {"Topics": [{"Text": "nested", "FirstURL": "http://r2"}]},
            ],
        }
        items = builtin_tools.normalize_search_items(payload, max_items=10)
        titles = [i["title"] for i in items]
        assert "Wikipedia" in titles
        assert "rel1" in titles
        assert "nested" in titles

    def test_dedup_and_max_items(self):
        payload = [
            {"title": "same", "url": "u", "snippet": "a"},
            {"title": "same", "url": "u", "snippet": "b"},  # duplicate identity
            {"title": "other", "url": "u2", "snippet": "c"},
        ]
        items = builtin_tools.normalize_search_items(payload, max_items=10)
        assert len(items) == 2

    def test_invalid_json_string_yields_empty(self):
        assert builtin_tools.normalize_search_items("not json", max_items=5) == []


class TestMcpHelpers:
    def test_extract_mcp_server_map_via_mcpServers(self):
        root = {"mcpServers": {"a": {"command": "node"}, "bad": 5}}
        out = builtin_tools.extract_mcp_server_map(root)
        assert "a" in out and "bad" not in out

    def test_extract_mcp_server_map_flat(self):
        root = {"a": {"command": "x"}, "b": {"url": "y"}}
        out = builtin_tools.extract_mcp_server_map(root)
        assert set(out.keys()) == {"a", "b"}

    def test_extract_mcp_server_map_non_dict(self):
        assert builtin_tools.extract_mcp_server_map([]) == {}  # type: ignore[arg-type]

    def test_normalize_mcp_args_list(self):
        assert builtin_tools.normalize_mcp_args_list([1, "a"]) == ["1", "a"]
        assert builtin_tools.normalize_mcp_args_list("nope") is None

    def test_normalize_mcp_env_map(self):
        assert builtin_tools.normalize_mcp_env_map({"K": 1}) == {"K": "1"}
        assert builtin_tools.normalize_mcp_env_map(["x"]) is None


class TestLoadWorkflowMcpServerConfig:
    def test_no_user_id_raises(self):
        engine = _make_engine(user_id="")
        with pytest.raises(ValueError) as exc:
            builtin_tools.load_workflow_mcp_server_config(engine)
        assert "user_id is empty" in str(exc.value)

    def test_no_config_row_raises(self):
        engine = _make_engine(db_row=None, user_id="u1")
        with pytest.raises(ValueError) as exc:
            builtin_tools.load_workflow_mcp_server_config(engine)
        assert "未配置 MCP 服务" in str(exc.value)

    def test_invalid_json_raises(self):
        row = SimpleNamespace(user_id="u1", config_json="{not json")
        engine = _make_engine(db_row=row, user_id="u1")
        with pytest.raises(ValueError) as exc:
            builtin_tools.load_workflow_mcp_server_config(engine)
        assert "JSON 无效" in str(exc.value)

    def test_single_stdio_server_selected_and_policy_allows_node(self):
        config = {"mcpServers": {"srv": {"command": "node", "args": ["x.js"], "type": "stdio"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        key, mcp_config, session_id = builtin_tools.load_workflow_mcp_server_config(engine)
        assert key == "srv"
        assert session_id.startswith("workflow:u1:srv:")
        assert mcp_config.command == "node"

    def test_disallowed_stdio_command_rejected_by_policy(self):
        # "bash" is not in the default allowlist (node/npx/python/python3/uv/uvx)
        config = {"mcpServers": {"srv": {"command": "bash", "args": ["-c", "echo hi"], "type": "stdio"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        with pytest.raises(Exception):  # MCPCommandPolicyError / ValueError from validate
            builtin_tools.load_workflow_mcp_server_config(engine)

    def test_multiple_servers_require_explicit_key(self):
        config = {
            "mcpServers": {
                "a": {"url": "http://a", "type": "http"},
                "b": {"url": "http://b", "type": "http"},
            }
        }
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        with pytest.raises(ValueError) as exc:
            builtin_tools.load_workflow_mcp_server_config(engine)
        assert "显式提供 mcp_server_key" in str(exc.value)

    def test_explicit_key_selects_http_server(self):
        config = {
            "mcpServers": {
                "a": {"url": "http://a", "type": "http"},
                "b": {"url": "http://b", "type": "sse"},
            }
        }
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        key, mcp_config, _ = builtin_tools.load_workflow_mcp_server_config(engine, requested_server_key="b")
        assert key == "b"
        assert mcp_config.url == "http://b"

    def test_explicit_missing_key_raises(self):
        config = {"mcpServers": {"a": {"url": "http://a", "type": "http"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        with pytest.raises(ValueError) as exc:
            builtin_tools.load_workflow_mcp_server_config(engine, requested_server_key="zzz")
        assert "不存在或已禁用" in str(exc.value)

    def test_all_disabled_raises(self):
        config = {"mcpServers": {"a": {"url": "http://a", "type": "http", "disabled": True}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        with pytest.raises(ValueError) as exc:
            builtin_tools.load_workflow_mcp_server_config(engine)
        assert "已禁用" in str(exc.value)


@pytest.mark.asyncio
class TestRunWebSearchTool:
    async def test_returns_normalized_results(self, monkeypatch, engine):
        def fake_fetch(query, region):
            return [{"title": "Hit", "snippet": "Body", "url": "http://h"}]

        monkeypatch.setattr(builtin_tools, "fetch_duckduckgo_results", fake_fetch)
        result = await builtin_tools.run_web_search_tool(
            engine, {"query": "weather", "max_items": "3"}, latest_input=None
        )
        assert result["tool"] == "web_search"
        assert result["status"] == "completed"
        assert result["count"] == 1
        assert result["provider"] == "duckduckgo"
        assert "Hit" in result["text"]

    async def test_query_falls_back_to_latest_input(self, monkeypatch, engine):
        seen = {}

        def fake_fetch(query, region):
            seen["query"] = query
            return [{"title": "x", "snippet": "y", "url": "z"}]

        monkeypatch.setattr(builtin_tools, "fetch_duckduckgo_results", fake_fetch)
        await builtin_tools.run_web_search_tool(engine, {}, latest_input={"text": "from-input"})
        assert seen["query"] == "from-input"

    async def test_no_results_status(self, monkeypatch, engine):
        def fake_fetch(query, region):
            raise RuntimeError("ddg down")

        # Block the browser fallback so we land on no_results deterministically.
        import app.services.gemini.common.browser as browser_mod

        monkeypatch.setattr(builtin_tools, "fetch_duckduckgo_results", fake_fetch)
        monkeypatch.setattr(
            browser_mod, "web_search", lambda q: (_ for _ in ()).throw(RuntimeError("fallback down"))
        )
        result = await builtin_tools.run_web_search_tool(engine, {"query": "x"}, latest_input=None)
        assert result["status"] == "no_results"
        assert "errors" in result
        assert result["count"] == 0


@pytest.mark.asyncio
class TestRunReadWebpageTool:
    async def test_missing_url_raises(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.run_read_webpage_tool(engine, {}, latest_input=None)
        assert "缺少 url" in str(exc.value)

    async def test_reads_and_truncates_on_success(self, monkeypatch, engine):
        import app.services.gemini.common.browser as browser_mod

        long_text = "ok content " * 500
        monkeypatch.setattr(browser_mod, "read_webpage", lambda url, max_length: long_text)
        result = await builtin_tools.run_read_webpage_tool(
            engine, {"url": "http://x", "max_length": "5000"}, latest_input=None
        )
        assert result["tool"] == "read_webpage"
        assert result["status"] == "completed"
        assert len(result["text"]) <= 1200

    async def test_error_content_marks_status_error(self, monkeypatch, engine):
        import app.services.gemini.common.browser as browser_mod

        monkeypatch.setattr(browser_mod, "read_webpage", lambda url, max_length: "Error: blocked")
        result = await builtin_tools.run_read_webpage_tool(engine, {"url": "http://x"}, latest_input=None)
        assert result["status"] == "error"

    async def test_url_from_latest_input(self, monkeypatch, engine):
        import app.services.gemini.common.browser as browser_mod

        seen = {}

        def fake_read(url, max_length):
            seen["url"] = url
            return "fine"

        monkeypatch.setattr(browser_mod, "read_webpage", fake_read)
        await builtin_tools.run_read_webpage_tool(engine, {}, latest_input={"url": "http://from-input"})
        assert seen["url"] == "http://from-input"


@pytest.mark.asyncio
class TestRunSeleniumBrowseTool:
    async def test_missing_url_raises(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.run_selenium_browse_tool(engine, {}, latest_input=None)
        assert "缺少 url" in str(exc.value)

    async def test_success_with_screenshot(self, monkeypatch, engine):
        import app.services.gemini.common.browser as browser_mod

        def fake_browse(url, **kwargs):
            return {"content": "page body", "screenshot": "QUJD"}  # base64-ish

        monkeypatch.setattr(browser_mod, "selenium_browse", fake_browse)
        result = await builtin_tools.run_selenium_browse_tool(engine, {"url": "http://x"}, latest_input=None)
        assert result["status"] == "completed"
        assert result["imageUrl"].startswith("data:image/png;base64,")
        assert result["screenshotUrl"] == result["imageUrl"]

    async def test_error_result(self, monkeypatch, engine):
        import app.services.gemini.common.browser as browser_mod

        monkeypatch.setattr(browser_mod, "selenium_browse", lambda url, **kwargs: {"error": "driver crashed"})
        result = await builtin_tools.run_selenium_browse_tool(engine, {"url": "http://x"}, latest_input=None)
        assert result["status"] == "error"
        assert result["error"] == "driver crashed"
        assert "imageUrl" not in result


@pytest.mark.asyncio
class TestRunMcpToolCall:
    async def test_missing_tool_name_raises(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.run_mcp_tool_call(engine, {"mcp_server_key": "srv"}, latest_input=None)
        assert "缺少 mcp_tool_name" in str(exc.value)

    async def test_successful_call(self, monkeypatch):
        config = {"mcpServers": {"srv": {"command": "node", "type": "stdio"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")

        class FakeManager:
            async def create_session(self, session_id, mcp_config):
                return None

            async def call_tool(self, session_id, tool_name, arguments):
                return SimpleNamespace(success=True, is_error=False, error=None, result={"answer": 42})

        import app.services.mcp.mcp_manager as mcp_manager_mod

        monkeypatch.setattr(mcp_manager_mod, "get_mcp_manager", lambda: FakeManager())

        result = await builtin_tools.run_mcp_tool_call(
            engine,
            {"mcp_tool_name": "lookup", "arguments": {"k": "v"}},
            latest_input=None,
        )
        assert result["tool"] == "mcp_tool_call"
        assert result["status"] == "completed"
        assert result["success"] is True
        assert result["serverKey"] == "srv"

    async def test_failed_call_returns_error_payload(self, monkeypatch):
        config = {"mcpServers": {"srv": {"command": "node", "type": "stdio"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")

        class FakeManager:
            async def create_session(self, session_id, mcp_config):
                return None

            async def call_tool(self, session_id, tool_name, arguments):
                return SimpleNamespace(success=False, is_error=True, error="boom", result=None)

        import app.services.mcp.mcp_manager as mcp_manager_mod

        monkeypatch.setattr(mcp_manager_mod, "get_mcp_manager", lambda: FakeManager())

        result = await builtin_tools.run_mcp_tool_call(engine, {"mcp_tool_name": "lookup"}, latest_input=None)
        assert result["status"] == "error"
        assert result["success"] is False
        assert result["error"] == "boom"


@pytest.mark.asyncio
class TestExecuteBuiltinToolDispatch:
    """Cover the central dispatch table incl. SSRF/browser policy gate."""

    def _ctx(self):
        return ExecutionContext({"task": "hi"})

    async def test_text_length_tool(self, engine):
        result = await builtin_tools.execute_builtin_tool(
            engine, "text_length", {"text": "hello"}, self._ctx(), []
        )
        assert result["length"] == 5
        assert result["toolCategory"] == "generic"
        assert result["toolSchedule"]["tool"] == "text_length"

    async def test_json_extract_tool(self, engine):
        result = await builtin_tools.execute_builtin_tool(
            engine,
            "json_extract",
            {"source": {"a": {"b": 7}}, "path": "a.b"},
            self._ctx(),
            [],
        )
        assert result["value"] == 7

    async def test_browser_tool_blocked_by_policy_default(self, monkeypatch, engine):
        monkeypatch.delenv("WORKFLOW_BROWSER_TOOL_ALLOWLIST", raising=False)
        result = await builtin_tools.execute_builtin_tool(engine, "browser_navigate", {}, self._ctx(), [])
        assert result["status"] == "blocked_by_policy"
        assert "WORKFLOW_BROWSER_TOOL_ALLOWLIST" in result["policy"]["allowlist_env"]

    async def test_browser_tool_allowed_but_unsupported(self, monkeypatch, engine):
        monkeypatch.setenv("WORKFLOW_BROWSER_TOOL_ALLOWLIST", "browser_navigate")
        result = await builtin_tools.execute_builtin_tool(engine, "browser_navigate", {}, self._ctx(), [])
        assert result["status"] == "unsupported"
        assert "browser_navigate" in result["policy"]["allowlist"]

    async def test_unknown_tool_is_unsupported(self, engine):
        result = await builtin_tools.execute_builtin_tool(
            engine, "totally_made_up_tool", {"x": 1}, self._ctx(), []
        )
        assert result["status"] == "unsupported"
        assert "totally_made_up_tool" in result["message"]

    async def test_search_category_dispatches_to_web_search(self, monkeypatch, engine):
        async def fake_search(engine, tool_args, latest_input):
            return {"tool": "web_search", "status": "completed", "items": []}

        monkeypatch.setattr(builtin_tools, "run_web_search_tool", fake_search)
        result = await builtin_tools.execute_builtin_tool(
            engine, "google_search", {"query": "x"}, self._ctx(), []
        )
        assert result["tool"] == "web_search"
        assert result["toolCategory"] == "search"
        assert result["toolSchedule"]["priority"] == 20

    async def test_image_category_routes_through_resolve_and_edit(self, monkeypatch, engine):
        async def fake_edit(tool_args, latest_input, is_outpaint, preferred_mode):
            return {"tool": "image_edit", "status": "completed", "mode": preferred_mode}

        monkeypatch.setattr(engine, "_run_image_edit_tool", fake_edit)
        result = await builtin_tools.execute_builtin_tool(
            engine, "image_chat_edit", {"imageUrl": "u"}, self._ctx(), []
        )
        assert result["tool"] == "image_edit"
        assert result["toolCategory"] == "image"

    async def test_video_generate_requires_provider_and_model(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.execute_builtin_tool(
                engine, "video_generate", {"prompt": "make video"}, self._ctx(), []
            )
        assert "provider_id 和 model_id" in str(exc.value)

    async def test_tool_error_is_recorded_and_reraised(self, monkeypatch, engine):
        async def boom(engine, tool_args, latest_input):
            raise RuntimeError("search exploded")

        monkeypatch.setattr(builtin_tools, "run_web_search_tool", boom)
        with pytest.raises(RuntimeError):
            await builtin_tools.execute_builtin_tool(engine, "web_search", {"query": "x"}, self._ctx(), [])

    async def test_latest_input_drawn_from_packets(self, monkeypatch, engine):
        seen = {}

        async def fake_search(engine, tool_args, latest_input):
            seen["latest"] = latest_input
            return {"tool": "web_search", "status": "completed"}

        monkeypatch.setattr(builtin_tools, "run_web_search_tool", fake_search)
        packets = [{"output": {"text": "packet-text"}}]
        await builtin_tools.execute_builtin_tool(engine, "search", {}, self._ctx(), packets)
        assert seen["latest"] == {"text": "packet-text"}

    async def test_video_understand_requires_provider_and_model(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.execute_builtin_tool(
                engine, "video_understand", {"prompt": "analyze"}, self._ctx(), []
            )
        assert "provider_id 和 model_id" in str(exc.value)

    async def test_video_delete_requires_provider(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.execute_builtin_tool(
                engine, "video_delete", {"profile_id": "p"}, self._ctx(), []
            )
        assert "video_delete 需要 provider_id" in str(exc.value)

    async def test_video_generate_dispatches_when_provider_and_model_present(self, monkeypatch, engine):
        captured = {}

        async def fake_gen(**kwargs):
            captured.update(kwargs)
            return {"tool": "video_generate", "status": "completed"}

        monkeypatch.setattr(engine, "_run_video_generate_task", fake_gen)
        result = await builtin_tools.execute_builtin_tool(
            engine,
            "video_generate",
            {"prompt": "ocean", "provider_id": "tongyi", "model_id": "wan-2.1"},
            self._ctx(),
            [],
        )
        assert result["status"] == "completed"
        assert result["toolCategory"] == "video"
        assert captured["provider_id"] == "tongyi"
        assert captured["model_id"] == "wan-2.1"
        assert captured["prompt"] == "ocean"

    async def test_video_delete_merges_provider_file_name_from_input(self, monkeypatch, engine):
        captured = {}

        async def fake_delete(**kwargs):
            captured.update(kwargs)
            return {"tool": "video_delete", "status": "completed"}

        monkeypatch.setattr(engine, "_run_video_delete_task", fake_delete)
        latest = {"output": {"providerFileName": "files/abc"}}
        result = await builtin_tools.execute_builtin_tool(
            engine, "video_delete", {"provider_id": "google"}, self._ctx(), [latest]
        )
        assert result["status"] == "completed"
        # latest_input.providerFileName mapped into delete_args.provider_file_name
        assert captured["tool_args"]["provider_file_name"] == "files/abc"

    async def test_prompt_optimize_dispatch(self, monkeypatch, engine):
        async def fake_opt(**kwargs):
            return {"tool": "prompt_optimize", "status": "completed", "text": "better prompt"}

        monkeypatch.setattr(engine, "_run_prompt_optimize_tool", fake_opt)
        result = await builtin_tools.execute_builtin_tool(
            engine, "optimize_prompt", {"prompt": "a"}, self._ctx(), []
        )
        assert result["toolCategory"] == "text_optimization"
        assert result["toolSchedule"]["priority"] == 35


# ---- sheet-stage payload builders + artifact/session extractors (pure) ------


class TestSheetStageExtractors:
    def test_extract_artifact_ref_from_nested_value(self, engine):
        ref = {
            "artifact_key": "sheet/ingest",
            "artifact_version": 1,
            "artifact_session_id": "sess-1",
        }
        nested = {"result": {"artifact": ref}}
        out = builtin_tools.extract_sheet_stage_artifact_ref_from_value(engine, nested)
        assert out == ref

    def test_extract_artifact_ref_returns_none_for_plain(self, engine):
        assert builtin_tools.extract_sheet_stage_artifact_ref_from_value(engine, {"x": 1}) is None
        assert builtin_tools.extract_sheet_stage_artifact_ref_from_value(engine, None) is None

    def test_extract_artifact_ref_depth_guard(self, engine):
        # depth>=4 short-circuits to None
        deep = {"result": {"result": {"result": {"result": {"artifact_key": "k"}}}}}
        assert builtin_tools.extract_sheet_stage_artifact_ref_from_value(engine, deep) is None

    def test_extract_session_id_from_dict(self, engine):
        assert builtin_tools.extract_sheet_stage_session_id_from_value(engine, {"sessionId": "s9"}) == "s9"
        assert builtin_tools.extract_sheet_stage_session_id_from_value(engine, {"session_id": "s1"}) == "s1"

    def test_extract_session_id_nested_and_list(self, engine):
        nested = {"payload": {"session_id": "deep"}}
        assert builtin_tools.extract_sheet_stage_session_id_from_value(engine, nested) == "deep"
        assert (
            builtin_tools.extract_sheet_stage_session_id_from_value(engine, [{"session_id": "li"}])
            == "li"
        )

    def test_extract_session_id_missing(self, engine):
        assert builtin_tools.extract_sheet_stage_session_id_from_value(engine, {"x": 1}) == ""
        assert builtin_tools.extract_sheet_stage_session_id_from_value(engine, None) == ""


class TestBuildSheetStageRequestPayload:
    def test_ingest_pulls_file_url_from_dict_input(self, engine):
        payload = builtin_tools.build_sheet_stage_request_payload(
            engine,
            stage="ingest",
            tool_args={},
            latest_input={"fileUrl": "http://x/data.csv"},
        )
        assert payload["stage"] == "ingest"
        assert payload["protocol_version"] == "sheet-stage/v1"
        assert payload["file_url"] == "http://x/data.csv"

    def test_ingest_keeps_direct_source(self, engine):
        payload = builtin_tools.build_sheet_stage_request_payload(
            engine,
            stage="ingest",
            tool_args={"file_url": "http://direct"},
            latest_input={"fileUrl": "http://from-input"},
        )
        # direct source present -> latest_input is NOT consulted
        assert payload["file_url"] == "http://direct"

    def test_ingest_string_url_input(self, engine):
        payload = builtin_tools.build_sheet_stage_request_payload(
            engine, stage="ingest", tool_args={}, latest_input="https://host/file.xlsx"
        )
        assert payload["file_url"] == "https://host/file.xlsx"

    def test_ingest_string_plain_content(self, engine):
        payload = builtin_tools.build_sheet_stage_request_payload(
            engine, stage="ingest", tool_args={}, latest_input="a,b,c\n1,2,3"
        )
        assert payload["content"] == "a,b,c\n1,2,3"

    def test_query_pulls_artifact_and_session_and_query(self, engine):
        ref = {
            "artifact_key": "sheet/profile",
            "artifact_version": 2,
            "artifact_session_id": "sess-2",
        }
        latest = {"artifact": ref, "session_id": "S", "anything": "x"}
        payload = builtin_tools.build_sheet_stage_request_payload(
            engine, stage="query", tool_args={}, latest_input=latest
        )
        assert payload["artifact"] == ref
        assert payload["session_id"] == "S"

    def test_query_pulls_query_text_from_string_input(self, engine):
        payload = builtin_tools.build_sheet_stage_request_payload(
            engine, stage="query", tool_args={"session_id": "s"}, latest_input="top selling skus"
        )
        assert payload["query"] == "top selling skus"


@pytest.mark.asyncio
class TestRunSheetStageTool:
    async def test_unsupported_stage_raises(self, engine):
        with pytest.raises(ValueError) as exc:
            await builtin_tools.run_sheet_stage_tool(
                engine, normalized_tool_name="not_a_sheet_tool", tool_args={}, latest_input=None
            )
        assert "unsupported sheet-stage tool" in str(exc.value)

    async def test_success_path_attaches_summary_text(self, monkeypatch, engine):
        import app.services.agent.sheet_stage_protocol_service as svc

        async def fake_execute(*, request_body, user_id, artifact_service):
            return {"status": "completed", "stage": "ingest"}

        monkeypatch.setattr(svc, "execute_sheet_stage_protocol_request", fake_execute)
        monkeypatch.setattr(svc, "extract_sheet_stage_summary_text", lambda detail: "ingest done")
        # avoid touching the real default artifact service singleton
        monkeypatch.setattr(builtin_tools, "get_sheet_stage_artifact_service", lambda eng: object())

        result = await builtin_tools.run_sheet_stage_tool(
            engine, normalized_tool_name="sheet_stage_ingest", tool_args={}, latest_input=None
        )
        assert result["status"] == "completed"
        assert result["text"] == "ingest done"

    async def test_value_error_builds_failure_detail(self, monkeypatch, engine):
        import app.services.agent.sheet_stage_protocol_service as svc

        async def fake_execute(*, request_body, user_id, artifact_service):
            raise ValueError("bad request")

        monkeypatch.setattr(svc, "execute_sheet_stage_protocol_request", fake_execute)
        monkeypatch.setattr(builtin_tools, "get_sheet_stage_artifact_service", lambda eng: object())

        result = await builtin_tools.run_sheet_stage_tool(
            engine, normalized_tool_name="sheet_stage_query", tool_args={}, latest_input=None
        )
        # build_sheet_stage_failure_detail produces a structured dict with a text field
        assert isinstance(result, dict)
        assert result.get("text")

    async def test_protocol_error_returns_detail(self, monkeypatch, engine):
        import app.services.agent.sheet_stage_protocol_service as svc
        from app.services.agent.sheet_stage_protocol_service import SheetStageProtocolError

        async def fake_execute(*, request_body, user_id, artifact_service):
            raise SheetStageProtocolError(
                status_code=422, detail={"status": "failed", "error": {"message": "schema"}}
            )

        monkeypatch.setattr(svc, "execute_sheet_stage_protocol_request", fake_execute)
        monkeypatch.setattr(builtin_tools, "get_sheet_stage_artifact_service", lambda eng: object())

        result = await builtin_tools.run_sheet_stage_tool(
            engine, normalized_tool_name="sheet_stage_export", tool_args={}, latest_input=None
        )
        assert result["status"] == "failed"


@pytest.mark.asyncio
class TestRunMcpToolCallArgMerge:
    async def test_arguments_merged_from_latest_input_fallback(self, monkeypatch):
        config = {"mcpServers": {"srv": {"command": "node", "type": "stdio"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        seen = {}

        class FakeManager:
            async def create_session(self, session_id, mcp_config):
                return None

            async def call_tool(self, session_id, tool_name, arguments):
                seen["arguments"] = arguments
                return SimpleNamespace(success=True, is_error=False, error=None, result={"ok": 1})

        import app.services.mcp.mcp_manager as mcp_manager_mod

        monkeypatch.setattr(mcp_manager_mod, "get_mcp_manager", lambda: FakeManager())

        # No explicit arguments; latest_input carries an "args" dict to fall back on.
        result = await builtin_tools.run_mcp_tool_call(
            engine,
            {"mcp_tool_name": "lookup"},
            latest_input={"args": {"keyword": "shoes"}},
        )
        assert result["success"] is True
        assert seen["arguments"] == {"keyword": "shoes"}

    async def test_extra_tool_args_become_arguments(self, monkeypatch):
        config = {"mcpServers": {"srv": {"command": "node", "type": "stdio"}}}
        row = SimpleNamespace(user_id="u1", config_json=_json.dumps(config))
        engine = _make_engine(db_row=row, user_id="u1")
        seen = {}

        class FakeManager:
            async def create_session(self, session_id, mcp_config):
                return None

            async def call_tool(self, session_id, tool_name, arguments):
                seen["arguments"] = arguments
                return SimpleNamespace(success=True, is_error=False, error=None, result={})

        import app.services.mcp.mcp_manager as mcp_manager_mod

        monkeypatch.setattr(mcp_manager_mod, "get_mcp_manager", lambda: FakeManager())

        result = await builtin_tools.run_mcp_tool_call(
            engine,
            {"mcp_tool_name": "lookup", "asin": "B0XYZ", "marketplace": "US"},
            latest_input=None,
        )
        assert result["success"] is True
        # non-reserved keys are folded into the tool arguments
        assert seen["arguments"]["asin"] == "B0XYZ"
        assert seen["arguments"]["marketplace"] == "US"
