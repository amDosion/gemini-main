import pytest

from app.routers.models.models import (
    _merge_openai_static_media_models,
    filter_models_by_mode,
)
from app.services.common.model_capabilities import build_model_config
from app.services.common.video_mode_contract import (
    normalize_video_generation_request_params,
    resolve_runtime_mode_controls_schema,
)
from app.services.openai import video_generator as openai_video_generator
from app.services.openai.video_generator import VideoGenerator


def test_openai_static_sora_models_are_available_for_video_mode() -> None:
    merged = _merge_openai_static_media_models("openai", [])
    video_ids = {model.id for model in filter_models_by_mode(merged, "video-gen")}

    assert {"sora-2", "sora-2-pro"}.issubset(video_ids)
    assert "gpt-image-2" not in video_ids


def test_openai_sora_models_are_not_exposed_to_image_modes() -> None:
    models = [
        build_model_config("openai", "sora-2"),
        build_model_config("openai", "sora-2-pro"),
        build_model_config("openai", "gpt-image-2"),
    ]

    assert {model.id for model in filter_models_by_mode(models, "video-gen")} == {
        "sora-2",
        "sora-2-pro",
    }
    assert "sora-2" not in {model.id for model in filter_models_by_mode(models, "image-gen")}
    assert "sora-2-pro" not in {model.id for model in filter_models_by_mode(models, "image-chat-edit")}


def test_openai_video_controls_include_independent_submodes() -> None:
    schema = resolve_runtime_mode_controls_schema(
        provider="openai",
        mode="video-gen",
        model_id="sora-2-pro",
    )

    assert schema is not None
    assert schema["runtime_api_mode"] == "openai_videos"
    assert [tier["value"] for tier in schema["resolution_tiers"]] == ["1K", "2K"]
    contract = schema["video_contract"]
    assert [strategy["id"] for strategy in contract["input_strategies"]] == [
        "text_to_video",
        "image_to_video",
        "video_extension",
        "video_edit",
    ]
    assert {slot["name"] for slot in contract["attachment_slots"] if slot["enabled"]} == {
        "source_image",
        "source_video",
    }
    unsupported = set(schema["constraints"]["unsupported_params"])
    assert "enhance_prompt" not in unsupported
    assert "prompt_extend" not in unsupported
    assert "storyboard_prompt" not in unsupported
    assert "storyboard_segments" not in unsupported
    assert contract["supports"]["video_extension"] is True
    assert contract["field_policies"]["storyboard_prompt"]["preferred"] is True
    assert contract["extension_duration_matrix"]


def test_openai_video_request_honors_explicit_submode_requirements() -> None:
    params, meta = normalize_video_generation_request_params(
        provider="openai",
        mode="video-gen",
        model_id="sora-2-pro",
        params={
            "video_input_strategy": "video_edit",
            "source_video": {"provider_file_uri": "video_123"},
            "seconds": "8",
            "resolution": "2K",
        },
    )

    assert params["video_input_strategy"] == "video_edit"
    assert meta["runtime_api_mode"] == "openai_videos"
    assert meta["input_strategy"] == "video_edit"


def test_openai_video_request_rejects_submode_missing_media() -> None:
    with pytest.raises(ValueError, match="source_video"):
        normalize_video_generation_request_params(
            provider="openai",
            mode="video-gen",
            model_id="sora-2-pro",
            params={
                "video_input_strategy": "video_extension",
                "seconds": "8",
                "resolution": "2K",
            },
        )


class _FakeVideo:
    def __init__(self, video_id: str, status: str = "queued") -> None:
        self.id = video_id
        self.status = status


class _FakeVideos:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def create(self, **payload):
        self.calls.append(("create", payload))
        return _FakeVideo("video_create")

    def extend(self, **payload):
        self.calls.append(("extend", payload))
        return _FakeVideo("video_extend")

    def edit(self, **payload):
        self.calls.append(("edit", payload))
        return _FakeVideo("video_edit")

    def retrieve(self, video_id: str):
        return _FakeVideo(video_id, "completed")

    def download_content(self, video_id: str, variant: str):
        return b"fake-mp4"


@pytest.mark.asyncio
async def test_openai_video_generator_routes_image_reference_to_create(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run_sync_inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(openai_video_generator, "run_in_sdk_thread", _run_sync_inline)
    generator = VideoGenerator(api_key="sk-test", base_url="https://api.openai.test/v1")
    fake_videos = _FakeVideos()
    generator.client.videos = fake_videos

    await generator.generate_video(
        "make this image move",
        "sora-2-pro",
        video_input_strategy="image_to_video",
        source_image={"url": "data:image/png;base64,aGVsbG8=", "mime_type": "image/png"},
        resolution="1K",
        aspect_ratio="16:9",
        seconds="8",
    )

    call_name, payload = fake_videos.calls[0]
    assert call_name == "create"
    assert payload["input_reference"] is not None
    assert payload["model"] == "sora-2-pro"
    assert payload["size"] == "1280x720"
    assert payload["seconds"] == "8"


@pytest.mark.asyncio
async def test_openai_video_generator_routes_video_submodes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run_sync_inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(openai_video_generator, "run_in_sdk_thread", _run_sync_inline)
    generator = VideoGenerator(api_key="sk-test", base_url="https://api.openai.test/v1")
    fake_videos = _FakeVideos()
    generator.client.videos = fake_videos

    await generator.generate_video(
        "extend the scene",
        "sora-2-pro",
        video_input_strategy="video_extension",
        source_video={"provider_file_uri": "video_123"},
        seconds="8",
    )
    await generator.generate_video(
        "make the palette warmer",
        "sora-2-pro",
        video_input_strategy="video_edit",
        source_video={"provider_file_uri": "video_456"},
        seconds="8",
    )

    assert fake_videos.calls[0] == (
        "extend",
        {"video": {"id": "video_123"}, "prompt": "extend the scene", "seconds": "8"},
    )
    assert fake_videos.calls[1] == (
        "edit",
        {"video": {"id": "video_456"}, "prompt": "make the palette warmer"},
    )


@pytest.mark.asyncio
async def test_openai_video_generator_uses_shared_last_frame_chain_for_multi_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_chain(**kwargs):
        assert kwargs["provider_name"] == "openai"
        assert kwargs["extension_count"] == 2
        assert kwargs["continuation_model"] == "sora-2-pro"
        assert kwargs["segment_seconds"] == 8
        assert kwargs["request_kwargs"]["storyboard_segments"] == ["first continuation", "second continuation"]
        return {
            "url": "data:video/mp4;base64,am9pbmVk",
            "mime_type": "video/mp4",
            "filename": "joined.mp4",
            "video_extension_count": 2,
            "video_extension_applied": 2,
            "continuation_strategy": "last_frame_bridge_chain",
        }

    monkeypatch.setattr(openai_video_generator, "run_last_frame_video_extension_chain", _fake_chain)
    generator = VideoGenerator(api_key="sk-test", base_url="https://api.openai.test/v1")

    result = await generator.generate_video(
        "extend this shot",
        "sora-2-pro",
        source_video={"url": "data:video/mp4;base64,c291cmNl"},
        video_input_strategy="video_extension",
        video_extension_count=2,
        storyboard_segments=["first continuation", "second continuation"],
        seconds="8",
    )

    assert result["continuation_strategy"] == "last_frame_bridge_chain"
    assert result["video_extension_applied"] == 2


@pytest.mark.asyncio
async def test_openai_video_generator_uses_local_enhanced_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run_sync_inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _fake_enhance(*args, **kwargs):
        assert kwargs["model_hint"] == "gpt-5.4-mini"
        assert kwargs["thinking_level"] == "high"
        assert kwargs["operation"] == "text_to_video"
        return "cinematic enhanced video prompt"

    monkeypatch.setattr(openai_video_generator, "run_in_sdk_thread", _run_sync_inline)
    monkeypatch.setattr(openai_video_generator, "enhance_openai_video_prompt", _fake_enhance, raising=False)

    generator = VideoGenerator(api_key="sk-test", base_url="https://api.openai.test/v1")
    fake_videos = _FakeVideos()
    generator.client.videos = fake_videos

    result = await generator.generate_video(
        "make a product launch teaser",
        "sora-2-pro",
        enhance_prompt=True,
        enhance_prompt_model="gpt-5.4-mini",
        enhance_prompt_thinking_level="high",
        seconds="8",
    )

    call_name, payload = fake_videos.calls[0]
    assert call_name == "create"
    assert payload["prompt"] == "cinematic enhanced video prompt"
    assert result["enhanced_prompt"] == "cinematic enhanced video prompt"


@pytest.mark.asyncio
async def test_openai_video_extension_enhances_storyboard_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    enhance_calls: list[dict] = []

    async def _fake_enhance(_client, prompt, **kwargs):
        enhance_calls.append({"prompt": prompt, "operation": kwargs["operation"]})
        return f"enhanced::{prompt}"

    async def _fake_chain(**kwargs):
        assert kwargs["prompt"] == "enhanced::extend this shot"
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

    monkeypatch.setattr(openai_video_generator, "enhance_openai_video_prompt", _fake_enhance, raising=False)
    monkeypatch.setattr(openai_video_generator, "run_last_frame_video_extension_chain", _fake_chain)

    generator = VideoGenerator(api_key="sk-test", base_url="https://api.openai.test/v1")
    result = await generator.generate_video(
        "extend this shot",
        "sora-2-pro",
        source_video={"url": "data:video/mp4;base64,c291cmNl"},
        video_input_strategy="video_extension",
        video_extension_count=2,
        storyboard_segments=["first continuation", "second continuation"],
        enhance_prompt=True,
        enhance_prompt_model="gpt-5.4-mini",
        seconds="8",
    )

    assert [call["prompt"] for call in enhance_calls] == [
        "extend this shot",
        "first continuation",
        "second continuation",
    ]
    assert {call["operation"] for call in enhance_calls} == {"video_extension"}
    assert result["enhanced_prompt"] == "enhanced::extend this shot"
    assert result["enhanced_storyboard_segments"] == [
        "enhanced::first continuation",
        "enhanced::second continuation",
    ]
