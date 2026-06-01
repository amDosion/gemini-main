import pytest

from app.services.common.video_mode_contract import resolve_runtime_mode_controls_schema
from app.services.grok import video_generator as grok_video_generator
from app.services.grok.video_generator import VideoGenerator


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    requests: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict):
        self.requests.append({"url": url, "json": json, "headers": headers})
        if url.endswith("/chat/completions"):
            return _FakeResponse({
                "choices": [
                    {"message": {"content": "enhanced grok video prompt"}}
                ]
            })
        return _FakeResponse({
            "id": "video_grok",
            "url": "https://example.test/grok.mp4",
            "status": "completed",
        })


def test_grok_video_contract_exposes_extension_options_for_every_slider_second() -> None:
    schema = resolve_runtime_mode_controls_schema(
        provider="grok",
        mode="video-gen",
        model_id="grok-imagine-1.0-video",
    )

    assert schema is not None
    matrix_by_seconds = {
        entry["base_seconds"]: entry["options"]
        for entry in schema["video_contract"]["extension_duration_matrix"]
    }

    for seconds in range(6, 31):
        options = matrix_by_seconds.get(str(seconds))
        assert options, seconds
        assert any(option["count"] > 0 for option in options), seconds


@pytest.mark.asyncio
async def test_grok_video_generator_uses_prompt_enhancement_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncClient.requests = []
    monkeypatch.setattr("app.services.grok.video_generator.httpx.AsyncClient", _FakeAsyncClient)

    generator = VideoGenerator(api_key="xai-test", base_url="https://grok.test/v1", timeout=30)
    result = await generator.generate_video(
        "make a cinematic product teaser",
        enhance_prompt=True,
        enhance_prompt_model="grok-4",
    )

    chat_request, video_request = _FakeAsyncClient.requests
    assert chat_request["url"] == "https://grok.test/v1/chat/completions"
    assert chat_request["json"]["model"] == "grok-4"
    assert video_request["url"] == "https://grok.test/v1/videos"
    assert video_request["json"]["prompt"] == "enhanced grok video prompt"
    assert result["enhanced_prompt"] == "enhanced grok video prompt"


@pytest.mark.asyncio
async def test_grok_video_generator_uses_shared_last_frame_chain_for_multi_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_chain(**kwargs):
        assert kwargs["provider_name"] == "grok"
        assert kwargs["extension_count"] == 2
        assert kwargs["continuation_model"] == "grok-imagine-1.0-video"
        assert kwargs["segment_seconds"] == 10
        assert kwargs["request_kwargs"]["storyboard_segments"] == ["first continuation", "second continuation"]
        return {
            "url": "data:video/mp4;base64,am9pbmVk",
            "mime_type": "video/mp4",
            "filename": "joined.mp4",
            "video_extension_count": 2,
            "video_extension_applied": 2,
            "continuation_strategy": "last_frame_bridge_chain",
        }

    monkeypatch.setattr(grok_video_generator, "run_last_frame_video_extension_chain", _fake_chain)

    generator = VideoGenerator(api_key="xai-test", base_url="https://grok.test/v1", timeout=30)
    result = await generator.generate_video(
        "continue the product shot",
        video_extension_count=2,
        storyboard_segments=["first continuation", "second continuation"],
        seconds=10,
    )

    assert result["continuation_strategy"] == "last_frame_bridge_chain"
    assert result["video_extension_applied"] == 2


@pytest.mark.asyncio
async def test_grok_video_extension_enhances_storyboard_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enhance_calls: list[str] = []

    async def _fake_chain(**kwargs):
        assert kwargs["prompt"] == "enhanced::continue the product shot"
        assert kwargs["request_kwargs"]["storyboard_segments"] == [
            "enhanced::first continuation",
            "enhanced::second continuation",
        ]
        return {
            "url": "data:video/mp4;base64,am9pbmVk",
            "mime_type": "video/mp4",
            "filename": "joined.mp4",
            "video_extension_count": 2,
            "video_extension_applied": 2,
            "continuation_strategy": "last_frame_bridge_chain",
        }

    async def _fake_enhance(prompt: str, _kwargs: dict) -> str:
        enhance_calls.append(prompt)
        return f"enhanced::{prompt}"

    monkeypatch.setattr(grok_video_generator, "run_last_frame_video_extension_chain", _fake_chain)

    generator = VideoGenerator(api_key="xai-test", base_url="https://grok.test/v1", timeout=30)
    monkeypatch.setattr(generator, "_maybe_enhance_prompt", _fake_enhance)

    result = await generator.generate_video(
        "continue the product shot",
        video_extension_count=2,
        storyboard_segments=["first continuation", "second continuation"],
        enhance_prompt=True,
        enhance_prompt_model="grok-4",
        seconds=10,
    )

    assert enhance_calls == ["continue the product shot", "first continuation", "second continuation"]
    assert result["enhanced_prompt"] == "enhanced::continue the product shot"
    assert result["enhanced_storyboard_segments"] == [
        "enhanced::first continuation",
        "enhanced::second continuation",
    ]
