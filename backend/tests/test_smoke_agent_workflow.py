"""Mock-backed smoke e2e for the agent/workflow happy path.

This test exercises a text agent node end-to-end through ``WorkflowEngine``
with the LLM call mocked. It deliberately uses NO real credentials and makes
NO network calls — every provider boundary is stubbed — so it stays
deterministic and safe to run in CI.

Pattern mirrors ``test_workflow_agent_execution.py`` (FakeDb + monkeypatched
candidate/model resolution + a fake ``_invoke_llm_chat``). The goal is a small
guard that the agent execution wiring stays intact, not exhaustive coverage.
"""

from types import SimpleNamespace

import pytest

from app.services.agent.execution_context import ExecutionContext
from app.services.agent.workflow_engine import WorkflowEngine


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeDb:
    """Minimal SQLAlchemy session stub returning a single agent row."""

    def __init__(self, agent):
        self._agent = agent

    def query(self, _model):
        return _FakeQuery(self._agent)


def _text_agent():
    return SimpleNamespace(
        id="agent-smoke-text",
        user_id="user-smoke",
        name="Smoke Text Agent",
        agent_type="custom",
        provider_id="google",
        model_id="gemini-2.5-flash",
        system_prompt="You are a concise assistant.",
        temperature=0.7,
        max_tokens=4096,
        agent_card_json=None,
    )


@pytest.mark.asyncio
async def test_smoke_text_agent_workflow_happy_path(monkeypatch):
    """A text agent node should return mocked LLM output without touching the network."""
    agent = _text_agent()
    engine = WorkflowEngine(
        db=_FakeDb(agent),
        llm_service=SimpleNamespace(user_id="user-smoke"),
    )

    # Force the simple text-chat path: the agent's own text model is a valid
    # candidate for the chat task, and the LLM call is stubbed with a
    # deterministic response (no provider/network call).
    monkeypatch.setattr(engine, "_is_candidate_for_agent_task", lambda **_kwargs: True)
    monkeypatch.setattr(engine, "_resolve_preferred_model_for_agent_task", lambda **_kwargs: "")

    captured = {}

    async def fake_invoke_llm_chat(**kwargs):
        captured.update(kwargs)
        return {"text": "Hello from the mocked agent.", "usage": {}}

    async def fail_image_edit(*_args, **_kwargs):
        raise AssertionError("text agent must not route to the image-edit tool")

    monkeypatch.setattr(engine, "_invoke_llm_chat", fake_invoke_llm_chat)
    monkeypatch.setattr(engine, "_run_image_edit_tool", fail_image_edit)

    output = await engine._execute_agent_node(
        node_id="agent-node",
        node_data={
            "type": "agent",
            "agentName": "Smoke Text Agent",
        },
        context=ExecutionContext({"task": "Say hello"}),
        initial_input={"task": "Say hello"},
        input_packets=[],
    )

    # The mocked LLM response must flow through to the node output unchanged.
    assert output["text"] == "Hello from the mocked agent."
    assert output["agentName"] == "Smoke Text Agent"
    assert output["model"] == "google/gemini-2.5-flash"
    assert output["runtime"] == "adapter"

    # The chat call must have been made with the agent's own provider/model and
    # the user task carried into the message content (proves wiring, not just
    # return shape).
    assert captured["provider_id"] == "google"
    assert captured["model_id"] == "gemini-2.5-flash"
    assert "Say hello" in captured["messages"][-1]["content"]
    assert captured["system_prompt"] == "You are a concise assistant."
