import pytest
from types import SimpleNamespace

from app.routers.models.models import (
    _merge_tongyi_static_media_models,
    filter_models_by_mode,
)
from app.services.common.mode_controls_catalog import resolve_mode_controls
from app.services.common.model_capabilities import build_model_config
from app.services.common.video_mode_contract import resolve_runtime_mode_controls_schema
from app.services.tongyi import model_manager as tongyi_model_manager
from app.services.tongyi import video_generation as tongyi_video_generation
from app.services.tongyi.video_generation import TongyiVideoGenerationService


def _ids_for_mode(model_ids: list[str], mode: str) -> set[str]:
    models = [build_model_config("tongyi", model_id) for model_id in model_ids]
    return {model.id for model in filter_models_by_mode(models, mode)}


def test_tongyi_video_models_are_exposed_to_video_mode_only() -> None:
    model_ids = [
        "qwen-max",
        "happyhorse-1.0-t2v",
        "happyhorse-1.0-i2v",
        "happyhorse-1.0-r2v",
        "happyhorse-1.0-video-edit",
        "wan2.7-t2v",
        "wan2.7-i2v",
        "wan2.7-r2v",
        "wan2.7-videoedit",
        "wan2.7-video-edit",
    ]

    video_ids = _ids_for_mode(model_ids, "video-gen")
    chat_ids = _ids_for_mode(model_ids, "chat")
    image_gen_ids = _ids_for_mode(model_ids, "image-gen")

    for model_id in model_ids[1:]:
        assert model_id in video_ids
        assert model_id not in chat_ids
        assert model_id not in image_gen_ids


def test_tongyi_static_media_catalog_is_merged_before_video_mode_filtering() -> None:
    merged = _merge_tongyi_static_media_models("tongyi", [])
    video_ids = {model.id for model in filter_models_by_mode(merged, "video-gen")}

    assert video_ids.issuperset(
        {
            "wan2.7-t2v",
            "wan2.7-i2v",
            "wan2.7-r2v",
            "wan2.7-videoedit",
            "happyhorse-1.0-t2v",
            "happyhorse-1.0-i2v",
            "happyhorse-1.0-r2v",
            "happyhorse-1.0-video-edit",
        }
    )


@pytest.mark.asyncio
async def test_tongyi_model_manager_includes_static_media_catalog_when_live_sources_are_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyModelsClient:
        async def list(self):
            return type("ModelsResponse", (), {"data": []})()

    class _FakeAsyncOpenAI:
        def __init__(self, **_: object) -> None:
            self.models = _EmptyModelsClient()

    monkeypatch.setattr(tongyi_model_manager, "AsyncOpenAI", _FakeAsyncOpenAI)
    monkeypatch.setattr(
        tongyi_model_manager.ModelManager,
        "_load_official_models",
        lambda self: [],
    )

    manager = tongyi_model_manager.ModelManager(api_key="test-key")
    models = await manager.get_available_models()
    by_id = {model.id: model for model in models}

    assert by_id["wan2.7-image-pro"].name == "Wan 2.7 Image Pro"
    assert "wan2.7-t2v" in by_id
    assert "happyhorse-1.0-video-edit" in by_id


def test_tongyi_wan27_video_controls_have_distinct_mode_rules() -> None:
    t2v = resolve_mode_controls("tongyi", "video-gen", "wan2.7-t2v")
    i2v = resolve_mode_controls("tongyi", "video-gen", "wan2.7-i2v")
    r2v = resolve_mode_controls("tongyi", "video-gen", "wan2.7-r2v")
    videoedit = resolve_mode_controls("tongyi", "video-gen", "wan2.7-videoedit")
    happyhorse_t2v = resolve_mode_controls("tongyi", "video-gen", "happyhorse-1.0-t2v")
    happyhorse_i2v = resolve_mode_controls("tongyi", "video-gen", "happyhorse-1.0-i2v")
    happyhorse_videoedit = resolve_mode_controls("tongyi", "video-gen", "happyhorse-1.0-video-edit")

    assert t2v is not None
    assert i2v is not None
    assert r2v is not None
    assert videoedit is not None
    assert happyhorse_t2v is not None
    assert happyhorse_i2v is not None
    assert happyhorse_videoedit is not None

    assert [tier["value"] for tier in t2v["resolution_tiers"]] == ["720p", "1080p"]
    assert [ratio["value"] for ratio in t2v["aspect_ratios"]] == ["16:9", "9:16", "1:1", "4:3", "3:4"]
    assert [option["value"] for option in t2v["param_options"]["seconds"]] == ["2", "5", "8", "10", "15"]

    assert [tier["value"] for tier in i2v["resolution_tiers"]] == ["720p", "1080p"]
    assert "aspect_ratio" in set(i2v["constraints"]["unsupported_params"])
    assert [option["value"] for option in i2v["param_options"]["seconds"]] == ["2", "5", "8", "10", "12", "15"]

    assert [option["value"] for option in r2v["param_options"]["seconds"]] == ["2", "5", "8", "10", "15"]
    assert [option["value"] for option in videoedit["param_options"]["seconds"]] == ["0", "2", "5", "8", "10"]
    assert videoedit["defaults"]["seconds"] == "0"
    assert [option["value"] for option in happyhorse_t2v["param_options"]["seconds"]] == ["3", "5", "8", "10", "15"]
    assert [option["value"] for option in happyhorse_i2v["param_options"]["seconds"]] == ["3", "5", "8", "10", "12", "15"]
    assert [option["value"] for option in happyhorse_videoedit["param_options"]["seconds"]] == ["0", "3", "5", "8", "10", "15"]


def test_tongyi_video_contract_labels_are_localized_by_submode() -> None:
    t2v = resolve_runtime_mode_controls_schema(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-t2v",
    )
    i2v = resolve_runtime_mode_controls_schema(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-i2v",
    )
    videoedit = resolve_runtime_mode_controls_schema(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-videoedit",
    )

    assert t2v is not None
    assert i2v is not None
    assert videoedit is not None

    assert [item["label"] for item in t2v["video_contract"]["input_strategies"]] == ["文生视频"]
    assert [item["label"] for item in i2v["video_contract"]["input_strategies"]] == [
        "图生视频",
        "首尾帧生视频",
        "视频延长",
        "延长到尾帧",
    ]
    assert [item["label"] for item in videoedit["video_contract"]["input_strategies"]] == ["视频编辑"]
    assert i2v["video_contract"]["supports"]["video_extension"] is True
    assert i2v["video_contract"]["field_policies"]["storyboard_prompt"]["preferred"] is True
    assert i2v["video_contract"]["extension_duration_matrix"]


def test_tongyi_all_video_submode_contracts_expose_extension_add_on() -> None:
    for model_id in (
        "wan2.7-t2v",
        "wan2.7-i2v",
        "wan2.7-r2v",
        "wan2.7-videoedit",
        "happyhorse-1.0-t2v",
        "happyhorse-1.0-i2v",
        "happyhorse-1.0-r2v",
        "happyhorse-1.0-video-edit",
    ):
        schema = resolve_runtime_mode_controls_schema(
            provider="tongyi",
            mode="video-gen",
            model_id=model_id,
        )
        assert schema is not None
        contract = schema["video_contract"]
        matrix = contract["extension_duration_matrix"]
        positive_counts = [
            option["count"]
            for entry in matrix
            for option in entry["options"]
            if option["count"] > 0
        ]

        assert contract["supports"]["video_extension"] is True, model_id
        assert contract["field_policies"]["storyboard_prompt"]["preferred"] is True, model_id
        assert positive_counts, model_id


class _CapturingVideoService(TongyiVideoGenerationService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key", poll_interval=0)
        self.payload: dict = {}

    async def _post_task(self, payload: dict) -> dict:
        self.payload = payload
        return {"output": {"task_id": "task-123", "task_status": "PENDING"}}

    async def _get_task(self, task_id: str) -> dict:
        return {
            "output": {
                "task_id": task_id,
                "task_status": "SUCCEEDED",
                "video_url": "https://example.test/out.mp4",
            },
            "usage": {"output_video_duration": 5},
        }


@pytest.mark.asyncio
async def test_tongyi_wan27_t2v_payload_matches_video_synthesis_contract() -> None:
    service = _CapturingVideoService()

    result = await service.generate_video(
        "一只小猫在月光下奔跑",
        "wan2.7-t2v",
        aspect_ratio="16:9",
        resolution="1080p",
        seconds="8",
        prompt_extend=True,
        negative_prompt="花朵",
        audio_url="https://example.test/audio.mp3",
        seed=12345,
    )

    assert result["url"] == "https://example.test/out.mp4"
    assert result["mime_type"] == "video/mp4"
    assert service.payload == {
        "model": "wan2.7-t2v",
        "input": {
            "prompt": "一只小猫在月光下奔跑",
            "negative_prompt": "花朵",
            "audio_url": "https://example.test/audio.mp3",
        },
        "parameters": {
            "resolution": "1080P",
            "duration": 8,
            "prompt_extend": True,
            "watermark": False,
            "ratio": "16:9",
            "seed": 12345,
        },
    }


@pytest.mark.asyncio
async def test_tongyi_video_generator_uses_selected_prompt_enhancement_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    optimizer_calls: list[dict] = []

    class _FakeVideoPromptOptimizer:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.closed = False

        async def optimize(self, prompt: str, *, model: str | None = None):
            optimizer_calls.append({"prompt": prompt, "model": model})
            return SimpleNamespace(success=True, optimized_prompt="增强后的视频提示词")

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(tongyi_video_generation, "VideoPromptOptimizer", _FakeVideoPromptOptimizer, raising=False)
    service = _CapturingVideoService()

    result = await service.generate_video(
        "一只小猫在月光下奔跑",
        "wan2.7-t2v",
        aspect_ratio="16:9",
        resolution="1080p",
        seconds="8",
        enhance_prompt=True,
        enhance_prompt_model="qwen-plus",
    )

    assert optimizer_calls == [{"prompt": "一只小猫在月光下奔跑", "model": "qwen-plus"}]
    assert service.payload["input"]["prompt"] == "增强后的视频提示词"
    assert service.payload["parameters"]["prompt_extend"] is False
    assert result["enhanced_prompt"] == "增强后的视频提示词"


@pytest.mark.asyncio
async def test_tongyi_wan27_i2v_uses_first_frame_and_does_not_send_ratio() -> None:
    service = _CapturingVideoService()

    await service.generate_video(
        "让主体自然转身",
        "wan2.7-i2v",
        source_image={"url": "https://example.test/source.png"},
        aspect_ratio="16:9",
        resolution="720p",
        seconds="5",
    )

    assert service.payload["input"]["media"] == [
        {"type": "first_frame", "url": "https://example.test/source.png"}
    ]
    assert service.payload["parameters"]["resolution"] == "720P"
    assert "ratio" not in service.payload["parameters"]


@pytest.mark.asyncio
async def test_tongyi_wan27_i2v_converts_local_frame_media_to_data_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_load_video_bytes_from_source(source, *, fallback_mime_type: str, **_: object):
        assert source == {"url": "/api/storage/local-files/frame.png"}
        assert fallback_mime_type == "image/png"
        return b"frame-bytes", "image/png"

    monkeypatch.setattr(
        tongyi_video_generation,
        "load_video_bytes_from_source",
        _fake_load_video_bytes_from_source,
    )
    service = _CapturingVideoService()

    await service.generate_video(
        "让主体自然转身",
        "wan2.7-i2v",
        source_image={"url": "/api/storage/local-files/frame.png"},
        resolution="720p",
        seconds="5",
    )

    media = service.payload["input"]["media"]
    assert media == [
        {
            "type": "first_frame",
            "url": "data:image/png;base64,ZnJhbWUtYnl0ZXM=",
        }
    ]


@pytest.mark.asyncio
async def test_tongyi_wan27_i2v_video_continuation_uses_first_clip() -> None:
    service = _CapturingVideoService()

    await service.generate_video(
        "继续上一段镜头",
        "wan2.7-i2v",
        source_video={"url": "https://example.test/source.mp4"},
        resolution="720p",
        seconds="12",
    )

    assert service.payload["input"]["media"] == [
        {"type": "first_clip", "url": "https://example.test/source.mp4"}
    ]
    assert service.payload["parameters"]["duration"] == 12
    assert "ratio" not in service.payload["parameters"]


@pytest.mark.asyncio
async def test_tongyi_video_generator_uses_shared_last_frame_chain_for_multi_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_chain(**kwargs):
        assert kwargs["provider_name"] == "tongyi"
        assert kwargs["extension_count"] == 2
        assert kwargs["continuation_model"] == "wan2.7-i2v"
        assert kwargs["segment_seconds"] == 5
        assert kwargs["continuation_trim_seconds"] == 0.0
        assert kwargs["request_kwargs"]["storyboard_segments"] == ["镜头一", "镜头二"]
        return {
            "url": "data:video/mp4;base64,am9pbmVk",
            "mime_type": "video/mp4",
            "filename": "joined.mp4",
            "video_extension_count": 2,
            "video_extension_applied": 2,
            "continuation_strategy": "last_frame_bridge_chain",
        }

    monkeypatch.setattr(tongyi_video_generation, "run_last_frame_video_extension_chain", _fake_chain)
    service = _CapturingVideoService()

    result = await service.generate_video(
        "继续上一段镜头",
        "wan2.7-i2v",
        source_video={"url": "data:video/mp4;base64,c291cmNl"},
        video_extension_count=2,
        storyboard_segments=["镜头一", "镜头二"],
        resolution="720p",
        seconds="5",
    )

    assert result["continuation_strategy"] == "last_frame_bridge_chain"
    assert result["video_extension_applied"] == 2


@pytest.mark.asyncio
async def test_tongyi_video_extension_enhances_storyboard_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    optimizer_calls: list[str] = []

    class _FakeVideoPromptOptimizer:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        async def optimize(self, prompt: str, *, model: str | None = None):
            optimizer_calls.append(prompt)
            return SimpleNamespace(success=True, optimized_prompt=f"增强:{prompt}")

        async def close(self) -> None:
            return None

    async def _fake_chain(**kwargs):
        assert kwargs["prompt"] == "增强:主提示词"
        assert kwargs["request_kwargs"]["storyboard_segments"] == ["增强:镜头一", "增强:镜头二"]
        return {
            "url": "data:video/mp4;base64,am9pbmVk",
            "mime_type": "video/mp4",
            "filename": "joined.mp4",
            "video_extension_count": kwargs["extension_count"],
            "video_extension_applied": kwargs["extension_count"],
            "continuation_strategy": "last_frame_bridge_chain",
        }

    monkeypatch.setattr(tongyi_video_generation, "VideoPromptOptimizer", _FakeVideoPromptOptimizer, raising=False)
    monkeypatch.setattr(tongyi_video_generation, "run_last_frame_video_extension_chain", _fake_chain)
    service = _CapturingVideoService()

    result = await service.generate_video(
        "主提示词",
        "wan2.7-t2v",
        video_extension_count=2,
        storyboard_segments=["镜头一", "镜头二"],
        enhance_prompt=True,
        enhance_prompt_model="qwen-plus",
        resolution="720p",
        seconds="5",
    )

    assert optimizer_calls == ["主提示词", "镜头一", "镜头二"]
    assert result["enhanced_prompt"] == "增强:主提示词"
    assert result["original_storyboard_segments"] == ["镜头一", "镜头二"]
    assert result["enhanced_storyboard_segments"] == ["增强:镜头一", "增强:镜头二"]


@pytest.mark.asyncio
async def test_tongyi_extension_chain_uses_i2v_continuation_for_non_i2v_submodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    async def _fake_chain(**kwargs):
        calls.append(kwargs)
        return {
            "url": "data:video/mp4;base64,am9pbmVk",
            "mime_type": "video/mp4",
            "filename": "joined.mp4",
            "video_extension_count": kwargs["extension_count"],
            "video_extension_applied": kwargs["extension_count"],
            "continuation_strategy": "last_frame_bridge_chain",
        }

    monkeypatch.setattr(tongyi_video_generation, "run_last_frame_video_extension_chain", _fake_chain)
    service = _CapturingVideoService()

    await service.generate_video(
        "先编辑再延长",
        "wan2.7-videoedit",
        source_video={"url": "data:video/mp4;base64,c291cmNl"},
        video_input_strategy="video_edit",
        video_extension_count=1,
        resolution="720p",
        seconds="5",
    )

    assert calls
    assert calls[0]["model"] == "wan2.7-videoedit"
    assert calls[0]["continuation_model"] == "wan2.7-i2v"
    assert calls[0]["treat_source_video_as_existing_base"] is False


@pytest.mark.asyncio
async def test_tongyi_wan27_r2v_and_videoedit_payloads_use_distinct_media_and_duration_rules() -> None:
    r2v_service = _CapturingVideoService()
    await r2v_service.generate_video(
        "参考图像和视频生成新镜头",
        "wan2.7-r2v",
        source_video={"url": "https://example.test/reference.mp4"},
        reference_images={"raw": [{"url": "https://example.test/ref.png"}]},
        aspect_ratio="4:3",
        resolution="1080p",
        seconds="15",
    )

    assert r2v_service.payload["input"]["media"] == [
        {"type": "reference_video", "url": "https://example.test/reference.mp4"},
        {"type": "reference_image", "url": "https://example.test/ref.png"},
    ]
    assert r2v_service.payload["parameters"]["duration"] == 10
    assert r2v_service.payload["parameters"]["ratio"] == "4:3"

    videoedit_service = _CapturingVideoService()
    await videoedit_service.generate_video(
        "将整个画面转换为黏土风格",
        "wan2.7-videoedit",
        source_video={"url": "https://example.test/edit.mp4"},
        reference_images={"raw": [{"url": "https://example.test/clothes.png"}]},
        aspect_ratio="9:16",
        resolution="720p",
        seconds="0",
        seed=777,
    )

    assert videoedit_service.payload["input"]["media"] == [
        {"type": "video", "url": "https://example.test/edit.mp4"},
        {"type": "reference_image", "url": "https://example.test/clothes.png"},
    ]
    assert videoedit_service.payload["parameters"] == {
        "resolution": "720P",
        "prompt_extend": True,
        "watermark": False,
        "ratio": "9:16",
        "seed": 777,
    }
