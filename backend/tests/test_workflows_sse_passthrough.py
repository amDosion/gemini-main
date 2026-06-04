"""Workflow status SSE frames are emitted verbatim (no case conversion).

_build_execution_state_with_runtime already builds camelCase STRUCTURAL keys
(executionId/nodeResults/nodeStatuses/isTerminal/...). The per-node maps
(nodeResults/nodeStatuses/nodeProgress/nodeErrors) are keyed by DYNAMIC workflow
node ids, which routinely contain underscores (e.g. "image_gen_1", "start_node").

_format_sse must therefore emit the payload byte-for-byte and must NOT run
to_camel_case: conversion is unnecessary (structural keys are already camelCase)
and actively harmful (it would rewrite node-id map keys image_gen_1 -> imageGen1,
desyncing them from the graph node ids the frontend reducer keys by).
"""

import json

from app.routers.ai.workflows import _format_sse


def _parse_sse_data(frame: str) -> dict:
    for line in frame.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
    raise AssertionError(f"no data line in SSE frame: {frame!r}")


def test_format_sse_preserves_already_camelcase_structural_keys():
    payload = {"executionId": "abc", "isTerminal": False, "nodeResults": {}}
    data = _parse_sse_data(_format_sse("execution_state", payload))
    assert data == payload


def test_format_sse_preserves_dynamic_node_id_keys_with_underscores():
    # Regression guard: node-id map keys must survive untouched. If _format_sse
    # ever camelCases the payload again, image_gen_1 becomes imageGen1 and the
    # frontend reducer can no longer correlate node output with the graph node.
    payload = {
        "executionId": "exec-1",
        "nodeStatuses": {"image_gen_1": "running", "start_node": "completed"},
        "nodeResults": {"image_gen_1": {"output": "x"}},
    }
    data = _parse_sse_data(_format_sse("execution_state", payload))
    assert set(data["nodeStatuses"].keys()) == {"image_gen_1", "start_node"}
    assert "imageGen1" not in data["nodeStatuses"]
    assert list(data["nodeResults"].keys()) == ["image_gen_1"]


def test_format_sse_preserves_event_line_and_framing():
    frame = _format_sse("execution_state", {"executionId": "abc"})
    assert frame.startswith("event: execution_state\n")
    assert frame.endswith("\n\n")
