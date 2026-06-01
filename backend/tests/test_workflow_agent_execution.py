import json
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
    def __init__(self, agent):
        self._agent = agent

    def query(self, _model):
        return _FakeQuery(self._agent)


@pytest.mark.asyncio
async def test_agent_image_edit_default_uses_upstream_reference_image_instead_of_fallback_chat(monkeypatch):
    agent = SimpleNamespace(
        id="agent-image-edit",
        user_id="user-1",
        name="Image Edit Agent",
        agent_type="custom",
        provider_id="google",
        model_id="gemini-2.5-flash-image",
        system_prompt="Edit images.",
        temperature=0.7,
        max_tokens=4096,
        agent_card_json=json.dumps(
            {
                "defaults": {
                    "defaultTaskType": "image-edit",
                    "imageEdit": {
                        "editMode": "image-chat-edit",
                    },
                }
            }
        ),
    )
    engine = WorkflowEngine(db=_FakeDb(agent), llm_service=SimpleNamespace(user_id="user-1"))
    monkeypatch.setattr(engine, "_is_candidate_for_agent_task", lambda **_kwargs: True)
    monkeypatch.setattr(engine, "_resolve_preferred_model_for_agent_task", lambda **_kwargs: "")

    captured = {}

    async def fake_image_edit(tool_args, latest_input, preferred_mode=""):
        captured["tool_args"] = dict(tool_args)
        captured["latest_input"] = latest_input
        captured["preferred_mode"] = preferred_mode
        return {"text": "edited", "imageUrl": "https://example.com/edited.png"}

    async def fail_chat(**_kwargs):
        raise AssertionError("image-edit agent must not silently fall back to chat")

    monkeypatch.setattr(engine, "_run_image_edit_tool", fake_image_edit)
    monkeypatch.setattr(engine, "_invoke_llm_chat", fail_chat)

    output = await engine._execute_agent_node(
        node_id="agent-node",
        node_data={
            "type": "agent",
            "agentName": "Image Edit Agent",
        },
        context=ExecutionContext({"task": "replace background"}),
        initial_input={"task": "replace background"},
        input_packets=[
            {
                "source": "input-image",
                "output": {"imageUrl": "https://example.com/source.png"},
            }
        ],
    )

    assert captured["tool_args"]["image_url"] == "https://example.com/source.png"
    assert output["agentTaskType"] == "image-edit"
    assert output["imageUrl"] == "https://example.com/edited.png"


@pytest.mark.asyncio
async def test_agent_video_gen_passes_strategy_and_driving_audio_to_runtime(monkeypatch):
    agent = SimpleNamespace(
        id="agent-video",
        user_id="user-1",
        name="Video Agent",
        agent_type="custom",
        provider_id="tongyi",
        model_id="wan2.7-i2v",
        system_prompt="Generate videos.",
        temperature=0.7,
        max_tokens=4096,
        agent_card_json=json.dumps(
            {
                "defaults": {
                    "defaultTaskType": "video-gen",
                    "videoGeneration": {
                        "videoInputStrategy": "first_frame_to_video",
                    },
                }
            }
        ),
    )
    engine = WorkflowEngine(db=_FakeDb(agent), llm_service=SimpleNamespace(user_id="user-1"))
    monkeypatch.setattr(engine, "_is_candidate_for_agent_task", lambda **_kwargs: True)
    monkeypatch.setattr(engine, "_resolve_preferred_model_for_agent_task", lambda **_kwargs: "")

    captured = {}

    async def fake_video_generate_task(**kwargs):
        captured.update(kwargs)
        return {
            "text": "generated",
            "videoUrl": "https://cdn.example.com/generated.mp4",
        }

    monkeypatch.setattr(engine, "_run_video_generate_task", fake_video_generate_task)

    output = await engine._execute_agent_node(
        node_id="agent-node",
        node_data={
            "type": "agent",
            "agentName": "Video Agent",
            "agentTaskType": "video-gen",
            "agentVideoInputStrategy": "video_continuation_to_last_frame",
            "agentAudioUrl": "{{input.audioUrl}}",
            "agentReferenceImageUrl": "{{input.imageUrl}}",
        },
        context=ExecutionContext(
            {
                "task": "make a talking product video",
                "imageUrl": "https://cdn.example.com/first.png",
                "audioUrl": "https://cdn.example.com/voice.mp3",
            }
        ),
        initial_input={
            "task": "make a talking product video",
            "imageUrl": "https://cdn.example.com/first.png",
            "audioUrl": "https://cdn.example.com/voice.mp3",
        },
        input_packets=[],
    )

    assert output["agentTaskType"] == "video-gen"
    assert output["videoUrl"] == "https://cdn.example.com/generated.mp4"
    assert captured["provider_id"] == "tongyi"
    assert captured["model_id"] == "wan2.7-i2v"
    assert captured["tool_args"]["video_input_strategy"] == "video_continuation_to_last_frame"
    assert captured["tool_args"]["audio_url"] == "https://cdn.example.com/voice.mp3"
    assert captured["tool_args"]["source_image"] == "https://cdn.example.com/first.png"

    runtime_kwargs = engine._build_video_generate_kwargs(captured["tool_args"])
    assert runtime_kwargs["video_input_strategy"] == "video_continuation_to_last_frame"
    assert runtime_kwargs["audio_url"] == "https://cdn.example.com/voice.mp3"
