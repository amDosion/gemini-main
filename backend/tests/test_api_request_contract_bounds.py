from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.routers.ai.multi_agent import (
    ADK_LIVE_MAX_EVENTS,
    ADK_LIVE_MAX_REQUESTS,
    ADKLiveRunRequest,
    ADKMemorySearchRequest,
    ADKToolConfirmationRequest,
    OrchestrateRequest,
    SHEET_STAGE_MAX_SAMPLE_ROWS,
    SheetStageProtocolRequest,
)
from app.routers.ai.workflows import (
    CreateAgentRequest,
    WorkflowExecuteRequest,
)
from app.routers.core.chat import (
    CHAT_MAX_ATTACHMENTS,
    CHAT_MAX_MESSAGES,
    ChatOptions,
    ChatRequest,
    Message,
)
from app.routers.core.modes import (
    MODE_MAX_ATTACHMENTS,
    MODE_MAX_SEGMENTATION_CLASSES,
    MODE_MAX_STORYBOARD_SEGMENTS,
    ModeOptions,
    ModeRequest,
)
from app.services.agent.workflow_payload_normalizer import MAX_WORKFLOW_NODES


def test_chat_request_enforces_runtime_payload_bounds():
    messages = [Message(role="user", content="hello") for _ in range(CHAT_MAX_MESSAGES + 1)]
    with pytest.raises(ValidationError):
        ChatRequest(model_id="gpt-test", messages=messages, message="hello")

    attachments = [
        {"id": f"a{i}", "mime_type": "image/png", "name": f"{i}.png"}
        for i in range(CHAT_MAX_ATTACHMENTS + 1)
    ]
    with pytest.raises(ValidationError):
        ChatRequest(model_id="gpt-test", messages=[], message="hello", attachments=attachments)

    with pytest.raises(ValidationError):
        ChatRequest(model_id="gpt-test", messages=[], message="hello", unexpected=True)


def test_chat_options_bound_known_fields_but_keep_provider_extension_path():
    options = ChatOptions(definitely_not_allowed=1)

    assert options.model_dump()["definitely_not_allowed"] == 1

    with pytest.raises(ValidationError):
        ChatOptions(temperature=3)
    with pytest.raises(ValidationError):
        ChatOptions(max_tokens=0)
    with pytest.raises(ValidationError):
        ChatOptions(stop=["x"] * 9)


def test_workflow_execute_request_uses_engine_graph_bounds():
    with pytest.raises(ValidationError):
        WorkflowExecuteRequest(nodes=[], edges=[])

    nodes = [{"id": f"n{i}", "data": {"type": "agent"}} for i in range(MAX_WORKFLOW_NODES + 1)]
    with pytest.raises(ValidationError):
        WorkflowExecuteRequest(nodes=nodes, edges=[])

    with pytest.raises(ValidationError):
        WorkflowExecuteRequest(nodes=[{"id": "n1"}], edges=[], extra_field=True)


def test_agent_request_rejects_unknown_fields_and_unbounded_generation_params():
    valid = {
        "name": "Writer",
        "provider_id": "google",
        "model_id": "gemini-test",
    }

    with pytest.raises(ValidationError):
        CreateAgentRequest(**valid, temperature=99)
    with pytest.raises(ValidationError):
        CreateAgentRequest(**valid, max_tokens=0)
    with pytest.raises(ValidationError):
        CreateAgentRequest(**valid, unknown=True)


def test_multi_agent_request_models_bound_arrays_and_numbers():
    with pytest.raises(ValidationError):
        OrchestrateRequest(task="run", agent_ids=[str(i) for i in range(65)])

    with pytest.raises(ValidationError):
        ADKLiveRunRequest(input="hello", live_requests=[{}] * (ADK_LIVE_MAX_REQUESTS + 1))
    with pytest.raises(ValidationError):
        ADKLiveRunRequest(input="hello", max_events=ADK_LIVE_MAX_EVENTS + 1)

    with pytest.raises(ValidationError):
        ADKMemorySearchRequest(query="hello", limit=0)


def test_confirmation_and_sheet_stage_models_are_typed_at_runtime():
    confirmation = ADKToolConfirmationRequest(
        function_call_id="fc-1",
        invocation_id="inv-1",
        nonce="nonce-1",
        ticketTimestampMs=1_700_000_000_000,
        ticketTtlSeconds=600,
        payload={"ok": True},
    )

    assert confirmation.ticket_timestamp_ms == 1_700_000_000_000
    assert confirmation.ticket_ttl_seconds == 600

    with pytest.raises(ValidationError):
        ADKToolConfirmationRequest(function_call_id="fc-1", unexpected=True)

    with pytest.raises(ValidationError):
        SheetStageProtocolRequest(stage="ingest", sampleRows=0)
    with pytest.raises(ValidationError):
        SheetStageProtocolRequest(stage="ingest", sampleRows=SHEET_STAGE_MAX_SAMPLE_ROWS + 1)

    request = SheetStageProtocolRequest(stage="ingest", sheetName="Data", sampleRows=25)
    assert request.sheet_name == "Data"
    assert request.sample_rows == 25


def test_mode_request_and_options_bound_generation_controls():
    with pytest.raises(ValidationError):
        ModeRequest(model_id="gemini-test", prompt="draw", attachments=[{}] * (MODE_MAX_ATTACHMENTS + 1))
    with pytest.raises(ValidationError):
        ModeRequest(model_id="gemini-test", prompt="draw", unexpected=True)

    with pytest.raises(ValidationError):
        ModeOptions(temperature=3)
    with pytest.raises(ValidationError):
        ModeOptions(canvas_w=16)
    with pytest.raises(ValidationError):
        ModeOptions(number_of_images=99)
    with pytest.raises(ValidationError):
        ModeOptions(segmentation_classes=list(range(MODE_MAX_SEGMENTATION_CLASSES + 1)))
    with pytest.raises(ValidationError):
        ModeOptions(storyboard_segments=["shot"] * (MODE_MAX_STORYBOARD_SEGMENTS + 1))

    options = ModeOptions(source_image={"url": "data:image/png;base64,abc"}, provider_extra=True)
    assert options.source_image == {"url": "data:image/png;base64,abc"}
    assert options.model_dump()["provider_extra"] is True
