import asyncio
from types import SimpleNamespace

import pytest

from app.routers.ai import workflows
from app.services.agent.execution_context import ExecutionContext
from app.services.agent.workflow_engine.orchestration import execute_node


class _RuntimeStoreStub:
    async def touch(self, _execution_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_publish_runtime_event_only_enqueues_execution_state(monkeypatch):
    execution_id = "exec-runtime-contract"
    workflows._execution_runtime_local.pop(execution_id, None)
    monkeypatch.setattr(workflows, "_workflow_runtime_store", _RuntimeStoreStub())
    runtime = workflows._get_local_runtime(execution_id)
    queue: asyncio.Queue = asyncio.Queue(maxsize=4)
    runtime.subscribers.append(queue)

    await workflows._publish_runtime_event(
        execution_id,
        "node_start",
        {
            "nodeId": "node-1",
            "timestamp": 123,
        },
    )

    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())

    assert [message.get("event") for message in messages] == ["execution_state"]
    assert messages[0]["data"]["executionId"] == execution_id
    assert messages[0]["data"]["nodeStatuses"]["node-1"] == "running"

    workflows._execution_runtime_local.pop(execution_id, None)


def _engine_stub():
    return SimpleNamespace(
        _get_node_type=lambda node: str(
            (node.get("data") or {}).get("type") or node.get("type") or ""
        )
        .strip()
        .lower()
        .replace("-", "_"),
        _to_bool=lambda value, default=False: value if isinstance(value, bool) else default,
        _derive_node_input_text=lambda _context, initial_input, _input_packets: initial_input.get(
            "task", ""
        ),
    )


@pytest.mark.asyncio
async def test_human_node_requires_explicit_auto_approve_until_real_confirmation_exists():
    with pytest.raises(ValueError, match="autoApprove=true"):
        await execute_node(
            _engine_stub(),
            node={
                "id": "review",
                "type": "human",
                "data": {"type": "human", "approvalPrompt": "确认后继续"},
            },
            context=ExecutionContext({"task": "review content"}),
            initial_input={"task": "review content"},
            input_packets=[],
            outgoing_edges=[],
            incoming_edge_count=1,
        )


@pytest.mark.asyncio
async def test_unknown_workflow_node_type_fails_closed():
    with pytest.raises(ValueError, match="Unsupported workflow node type"):
        await execute_node(
            _engine_stub(),
            node={
                "id": "mystery",
                "type": "mystery_box",
                "data": {"type": "mystery_box"},
            },
            context=ExecutionContext({"task": "test"}),
            initial_input={"task": "test"},
            input_packets=[],
            outgoing_edges=[],
            incoming_edge_count=1,
        )
