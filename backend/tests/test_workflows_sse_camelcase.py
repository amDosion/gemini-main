"""Workflow status SSE frames must go through the camelCase seam.

The case-conversion middleware passes SSE (text/event-stream) through unchanged,
so SSE producers are responsible for emitting camelCase themselves. The workflow
status stream copies nested objects (nodeResults, result, checkpoint payloads)
straight from runtime/backend state, which can carry snake_case keys. Those must
be camelCased before they reach a frontend that now reads camelCase only.
"""

import json

from app.routers.ai.workflows import _format_sse


def _parse_sse_data(frame: str) -> dict:
    for line in frame.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
    raise AssertionError(f"no data line in SSE frame: {frame!r}")


def test_format_sse_camelcases_top_level_keys():
    frame = _format_sse("execution_state", {"execution_id": "abc", "node_count": 3})
    data = _parse_sse_data(frame)
    assert data == {"executionId": "abc", "nodeCount": 3}
    assert "execution_id" not in data


def test_format_sse_camelcases_nested_runtime_payloads():
    # node_results is NOT a SKIP_VALUE_CONVERSION_FIELD, so its nested keys (copied
    # from runtime state) must be camelCased recursively. `result`/`state` ARE skip
    # fields and stay opaque by design — not asserted here.
    frame = _format_sse(
        "execution_state",
        {
            "status": "running",
            "node_results": {
                "node_a": {"output_value": 1, "is_final": False},
            },
        },
    )
    data = _parse_sse_data(frame)
    assert data["nodeResults"]["nodeA"] == {"outputValue": 1, "isFinal": False}
    assert "node_results" not in data


def test_format_sse_preserves_event_line():
    frame = _format_sse("execution_state", {"a_b": 1})
    assert frame.startswith("event: execution_state\n")
    assert frame.endswith("\n\n")
