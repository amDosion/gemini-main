from types import SimpleNamespace

import pytest

from app.services.common.video_mode_contract import apply_video_mode_runtime_overrides
from app.services.common.mode_controls_catalog import resolve_mode_controls
from app.services.gemini.http_options import HttpOptions, HttpRetryOptions
from app.services.gemini.coordinators.video_generation_coordinator import VideoGenerationCoordinator
from app.services.gemini.base.video_common import parse_data_url
from app.services.gemini.geminiapi.video_generation_service import GeminiAPIVideoGenerationService
from app.services.gemini.vertexai.video_generation_service import (
    VertexAIVideoGenerationService,
    normalize_vertex_video_model,
    sanitize_vertex_video_prompt_for_responsible_ai,
)


def test_google_video_contract_for_veo31_keeps_4k_and_official_extension_constraints() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-001")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="vertex_ai",
    )

    resolution_values = [item["value"] for item in runtime_schema["resolution_tiers"]]
    assert resolution_values == ["720p", "1080p", "4k"]
    assert "person_generation" not in runtime_schema["defaults"]
    assert "person_generation" not in runtime_schema["param_options"]
    assert "supports_person_generation" not in runtime_schema["constraints"]
    assert "person_generation" not in runtime_schema["video_contract"]["supports"]
    assert "person_generation" not in runtime_schema["video_contract"]["field_policies"]

    extension_constraints = runtime_schema["video_contract"]["extension_constraints"]
    assert extension_constraints["added_seconds"] == 7
    assert extension_constraints["max_extension_count"] == 4
    assert extension_constraints["max_source_video_seconds"] == 30
    assert extension_constraints["max_output_video_seconds"] == 37
    assert extension_constraints["require_duration_seconds"] == ["8"]
    assert extension_constraints["require_resolution_values"] == ["720p", "1080p", "4k"]


@pytest.mark.asyncio
async def test_vertex_video_generation_does_not_send_person_generation_to_sdk() -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.config = None
            self.source = None

        def generate_videos(self, **kwargs):
            self.config = kwargs["config"]
            self.source = kwargs["source"]
            return SimpleNamespace(name="operations/test-video")

    fake_models = FakeModels()
    service = VertexAIVideoGenerationService(
        project_id="test-project",
        location="us-central1",
        credentials_json="{}",
        output_gcs_uri="gs://test-bucket/veo-test",
    )
    service._client = SimpleNamespace(models=fake_models)

    async def fake_wait_for_operation(operation):
        return SimpleNamespace(name=operation.name, result=SimpleNamespace())

    def fake_extract_generated_video(_response):
        return SimpleNamespace(video=SimpleNamespace(mime_type="video/mp4"))

    async def fake_resolve_video_payload(_generated_video):
        return b"fake-video", "video/mp4"

    service._wait_for_operation = fake_wait_for_operation
    service._extract_generated_video = fake_extract_generated_video
    service._resolve_video_payload = fake_resolve_video_payload

    await service.generate_video(
        "Medium shot of a cute young Asian female model wearing product hair clips.",
        "veo-3.1-generate-preview",
        resolution="4k",
        aspect_ratio="9:16",
        seconds=8,
    )

    assert getattr(fake_models.config, "person_generation", None) is None
    assert "young Asian female" not in getattr(fake_models.source, "prompt", "")
    assert "adult female fashion model" in getattr(fake_models.source, "prompt", "")


def test_vertex_video_prompt_sanitizer_rephrases_common_responsible_ai_triggers() -> None:
    prompt = (
        "20-25s: Medium shot of a cute young Asian female model with a half-up ponytail. "
        "She is winking. 少女感，多巴胺女孩。"
    )

    sanitized = sanitize_vertex_video_prompt_for_responsible_ai(prompt)

    assert "cute young Asian female model" not in sanitized
    assert "winking" not in sanitized
    assert "少女" not in sanitized
    assert "adult female fashion model" in sanitized
    assert "smiling" in sanitized


def test_google_video_contract_for_veo31_gemini_api_keeps_extension_resolution_limited_to_720p() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-001")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="gemini_api",
    )

    extension_constraints = runtime_schema["video_contract"]["extension_constraints"]
    assert extension_constraints["require_resolution_values"] == ["720p"]


def test_google_video_contract_duration_matrix_filters_totals_above_output_limit() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-preview")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="vertex_ai",
    )

    matrix = runtime_schema["video_contract"]["extension_duration_matrix"]
    eight_second_plan = next(item for item in matrix if item["base_seconds"] == "8")
    assert eight_second_plan["options"][-1]["count"] == 4
    assert eight_second_plan["options"][-1]["total_seconds"] == 36

    four_second_plan = next(item for item in matrix if item["base_seconds"] == "4")
    assert four_second_plan["options"][-1]["total_seconds"] <= 37


def test_google_video_contract_for_veo2_disables_extension_but_keeps_mask_edit_path() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-2.0-generate-001")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="gemini_api",
    )
    contract = runtime_schema["video_contract"]

    assert contract["supports"]["video_extension"] is False
    assert contract["supports"]["video_mask_image"] is True


def test_vertex_video_generation_uses_available_stable_model_aliases() -> None:
    assert normalize_vertex_video_model("veo-3.1-generate-preview") == "veo-3.1-generate-001"
    assert normalize_vertex_video_model("veo-3.1-fast-generate-preview") == "veo-3.1-fast-generate-001"
    assert normalize_vertex_video_model("veo-3.1-generate-001") == "veo-3.1-generate-001"


def test_video_prompt_enhancement_uses_chat_edit_model_suitability_rules() -> None:
    coordinator = VideoGenerationCoordinator(api_key="test-key")

    assert coordinator._resolve_local_enhance_prompt_model("gemini-2.5-flash") == "gemini-2.5-flash"
    assert coordinator._resolve_local_enhance_prompt_model("veo-3.1-generate-preview") == "gemini-2.5-pro"
    assert coordinator._resolve_local_enhance_prompt_model("gemini-2.5-flash-image") == "gemini-2.5-pro"


def test_video_prompt_enhancement_uses_chat_edit_timeout_policy() -> None:
    retry_options = HttpRetryOptions(attempts=2)
    coordinator = VideoGenerationCoordinator(
        api_key="test-key",
        http_options=HttpOptions(
            api_version="v1beta",
            base_url="https://example.test",
            headers={"x-test": "1"},
            timeout=30000,
            retry_options=retry_options,
        ),
    )

    options = coordinator._build_prompt_enhance_http_options()

    assert options.api_version == "v1beta"
    assert options.base_url == "https://example.test"
    assert options.headers == {"x-test": "1"}
    assert options.timeout is None
    assert options.retry_options == retry_options
    assert options.use_default_timeout is False


def test_video_generation_uses_long_http_timeout_policy() -> None:
    retry_options = HttpRetryOptions(attempts=2)
    coordinator = VideoGenerationCoordinator(
        api_key="test-key",
        http_options=HttpOptions(
            api_version="v1beta",
            base_url="https://example.test",
            headers={"x-test": "1"},
            timeout=30000,
            retry_options=retry_options,
        ),
    )

    options = coordinator._build_video_generation_http_options()

    assert options.api_version == "v1beta"
    assert options.base_url == "https://example.test"
    assert options.headers == {"x-test": "1"}
    assert options.timeout >= 300000
    assert options.retry_options == retry_options
    assert options.use_default_timeout is False


def test_high_resolution_extension_bridge_policy_uses_official_vertex_when_available() -> None:
    coordinator = VideoGenerationCoordinator(api_key="test-key")

    assert coordinator._should_use_last_frame_bridge_extension_chain(
        {"resolution": "4k"},
        selected_api_mode="gemini_api",
        model="veo-3.1-generate-preview",
    ) is True
    assert coordinator._should_use_last_frame_bridge_extension_chain(
        {"resolution": "1080p"},
        selected_api_mode="gemini_api",
        model="veo-3.1-generate-preview",
    ) is True
    assert coordinator._should_use_last_frame_bridge_extension_chain(
        {"resolution": "720p"},
        selected_api_mode="gemini_api",
        model="veo-3.1-generate-preview",
    ) is False
    assert coordinator._should_use_last_frame_bridge_extension_chain(
        {"resolution": "720p", "use_last_frame_bridge": True}
    ) is True

    vertex_coordinator = VideoGenerationCoordinator()
    vertex_coordinator._config = {
        "api_mode": "vertex_ai",
        "vertex_ai_project_id": "test-project",
        "vertex_ai_credentials_json": "{}",
    }

    assert vertex_coordinator._should_use_last_frame_bridge_extension_chain(
        {"resolution": "4k"},
        selected_api_mode="vertex_ai",
        model="veo-3.1-generate-preview",
    ) is False
    assert vertex_coordinator._should_use_last_frame_bridge_extension_chain(
        {"resolution": "1080p"},
        selected_api_mode="vertex_ai",
        model="veo-3.1-generate-preview",
    ) is False


def test_video_storyboard_preserves_generate_audio_false_and_strips_audio_cues() -> None:
    coordinator = VideoGenerationCoordinator(api_key="test-key")

    storyboard = coordinator._normalized_storyboard_options({"generateAudio": False})
    assert storyboard["generate_audio"] is False
    storyboard = coordinator._normalized_storyboard_options({"generate_audio": False})
    assert storyboard["generate_audio"] is False

    base_prompt = coordinator._build_storyboard_prompt(
        prompt="Product macro shot. Voiceover: say a discount line. 口播讲解：左下角购买。",
        request_kwargs={
            "generateAudio": False,
            "storyboardPrompt": "0-8s: product hero reveal. BGM: upbeat music. 旁白：summer hair clips.",
        },
        extension_count=0,
    )

    assert "Voiceover" not in base_prompt
    assert "口播" not in base_prompt
    assert "BGM" not in base_prompt
    assert "旁白" not in base_prompt
    assert "Visual-only product showcase" in base_prompt


def test_extension_storyboard_segments_strip_audio_cues_when_audio_disabled() -> None:
    coordinator = VideoGenerationCoordinator(api_key="test-key")

    prompts = coordinator._build_extension_segment_prompts(
        prompt="Hair clip product video. Voiceover: introduce the product.",
        request_kwargs={
            "generate_audio": False,
            "seconds": 8,
            "storyboard_segments": [
                "8-15s: ocean detail macro. 口播讲解：第一组是人鱼公主系列。",
            ],
        },
        extension_count=1,
    )

    assert len(prompts) == 1
    assert "Voiceover" not in prompts[0]
    assert "口播" not in prompts[0]
    assert "Visual-only product continuation" in prompts[0]


def test_extension_storyboard_segments_merge_overflow_into_last_available_extension() -> None:
    coordinator = VideoGenerationCoordinator(api_key="test-key")

    prompts = coordinator._build_extension_segment_prompts(
        prompt="Product video.",
        request_kwargs={
            "seconds": 8,
            "storyboard_segments": [
                "5-10s: ocean details.",
                "10-15s: adult model try-on.",
                "15-20s: fruit details.",
                "20-25s: playful styling.",
                "25-30s: final product close-up.",
            ],
        },
        extension_count=4,
    )

    assert len(prompts) == 4
    assert "20-25s: playful styling." in prompts[3]
    assert "25-30s: final product close-up." in prompts[3]


class _BridgeChainCoordinator(VideoGenerationCoordinator):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.requests = []
        self.prompts = []
        self.segment_payloads = []
        self.trim_seconds = None

    async def _generate_single_video(self, prompt, model, request_kwargs, *, selected_api_mode=None):
        self.prompts.append(prompt)
        self.requests.append(dict(request_kwargs))
        index = len(self.requests) - 1
        return {
            "url": f"data:video/mp4;base64,c2VnbWVudC0{index}",
            "mime_type": "video/mp4",
            "filename": "veo-3.1-generate-preview-4k-16x9.mp4",
            "duration_seconds": 8,
            "job_id": f"job-{index}",
            "model": model,
        }

    async def _download_result_video_bytes(self, result):
        return f"video-{result['job_id']}".encode("utf-8"), "video/mp4"

    async def _build_last_frame_source_image_from_video_bytes(self, video_bytes, mime_type):
        return {
            "url": "data:image/png;base64," + video_bytes.hex(),
            "mime_type": "image/png",
        }

    async def _concatenate_video_segments(self, segments, *, continuation_trim_seconds):
        self.segment_payloads = list(segments)
        self.trim_seconds = continuation_trim_seconds
        return b"joined-video"


class _FailingBridgeChainCoordinator(_BridgeChainCoordinator):
    async def _generate_single_video(self, prompt, model, request_kwargs, *, selected_api_mode=None):
        if len(self.requests) == 2:
            raise RuntimeError("Provider RAI filtering returned no video: blocked")
        return await super()._generate_single_video(
            prompt,
            model,
            request_kwargs,
            selected_api_mode=selected_api_mode,
        )


class _OfficialVertexExtensionCoordinator(VideoGenerationCoordinator):
    def __init__(self) -> None:
        super().__init__()
        self._config = {
            "api_mode": "vertex_ai",
            "vertex_ai_project_id": "test-project",
            "vertex_ai_credentials_json": "{}",
        }
        self.requests = []
        self.selected_modes = []

    async def _wait_for_gemini_video_asset_ready(self, _result):
        return None

    async def _generate_single_video(self, prompt, model, request_kwargs, *, selected_api_mode=None):
        self.requests.append(dict(request_kwargs))
        self.selected_modes.append(selected_api_mode)
        index = len(self.requests) - 1
        gcs_uri = f"gs://test-bucket/veo/out-{index}.mp4"
        return {
            "url": gcs_uri,
            "mime_type": "video/mp4",
            "filename": "veo-3.1-generate-preview-4k-16x9.mp4",
            "duration_seconds": 8,
            "video_size": "3840*2160",
            "job_id": f"job-{index}",
            "model": model,
            "provider_platform": "vertex_ai",
            "gcs_uri": gcs_uri,
            "provider_file_uri": gcs_uri,
            "continuation_strategy": "video_extension" if index > 0 else "none",
        }


@pytest.mark.asyncio
async def test_generate_video_4k_extension_returns_joined_bridge_result() -> None:
    coordinator = _BridgeChainCoordinator()

    result = await coordinator.generate_video(
        "make a continuous 4k video",
        "veo-3.1-generate-preview",
        resolution="4k",
        aspect_ratio="16:9",
        seconds=8,
        video_extension_count=2,
    )

    assert len(coordinator.requests) == 3
    assert "source_video" not in coordinator.requests[1]
    assert "source_video" not in coordinator.requests[2]
    assert coordinator.requests[1]["source_image"]["mime_type"] == "image/png"
    assert coordinator.requests[2]["source_image"]["mime_type"] == "image/png"
    assert len(coordinator.segment_payloads) == 3
    assert coordinator.trim_seconds == 1.0

    video_bytes, mime_type = parse_data_url(result["url"])
    assert video_bytes == b"joined-video"
    assert mime_type == "video/mp4"
    assert result["continuation_strategy"] == "last_frame_bridge_chain"
    assert result["video_extension_count"] == 2
    assert result["video_extension_applied"] == 2
    assert result["total_duration_seconds"] == 22
    assert result["segment_count"] == 3
    assert result["video_size"] == "3840*2160"
    assert "provider_file_name" not in result


@pytest.mark.asyncio
async def test_generate_video_vertex_4k_extension_uses_official_video_extension_chain() -> None:
    coordinator = _OfficialVertexExtensionCoordinator()

    result = await coordinator.generate_video(
        "make a continuous 4k product video",
        "veo-3.1-generate-preview",
        resolution="4k",
        aspect_ratio="16:9",
        seconds=8,
        video_extension_count=2,
        source_image={
            "url": "data:image/png;base64,c291cmNl",
            "mime_type": "image/png",
        },
    )

    assert coordinator.selected_modes == ["vertex_ai", "vertex_ai", "vertex_ai"]
    assert len(coordinator.requests) == 3
    assert "use_last_frame_bridge" not in coordinator.requests[0]
    assert "use_last_frame_bridge" not in coordinator.requests[1]
    assert "source_image" in coordinator.requests[0]
    assert "source_image" not in coordinator.requests[1]
    assert coordinator.requests[1]["source_video"]["gcs_uri"] == "gs://test-bucket/veo/out-0.mp4"
    assert coordinator.requests[2]["source_video"]["gcs_uri"] == "gs://test-bucket/veo/out-1.mp4"
    assert result["continuation_strategy"] == "video_extension_chain"
    assert result["video_extension_count"] == 2
    assert result["video_extension_applied"] == 2
    assert result["video_size"] == "3840*2160"


@pytest.mark.asyncio
async def test_generate_video_4k_extension_uses_per_extension_storyboard_prompts() -> None:
    coordinator = _BridgeChainCoordinator()

    result = await coordinator.generate_video(
        "keep the same model identity",
        "veo-3.1-generate-preview",
        resolution="4k",
        aspect_ratio="16:9",
        seconds=8,
        video_extension_count=2,
        storyboard_prompt="base segment: slow push in",
        storyboard_segments=[
            "extension one: side step from the final frame",
            "extension two: editorial close-up from the final frame",
        ],
    )

    assert len(coordinator.prompts) == 3
    assert "base segment: slow push in" in coordinator.prompts[0]
    assert "extension one: side step from the final frame" not in coordinator.prompts[0]
    assert "extension one: side step from the final frame" in coordinator.prompts[1]
    assert "extension two: editorial close-up from the final frame" not in coordinator.prompts[1]
    assert "extension two: editorial close-up from the final frame" in coordinator.prompts[2]
    assert result["storyboard_segments"] == [
        "extension one: side step from the final frame",
        "extension two: editorial close-up from the final frame",
    ]


@pytest.mark.asyncio
async def test_generate_video_4k_extension_reports_failing_storyboard_segment() -> None:
    coordinator = _FailingBridgeChainCoordinator()

    with pytest.raises(RuntimeError) as exc_info:
        await coordinator.generate_video(
            "base segment",
            "veo-3.1-generate-preview",
            resolution="4k",
            aspect_ratio="16:9",
            seconds=8,
            video_extension_count=2,
            storyboard_prompt="base segment",
            storyboard_segments=[
                "extension one: safe product detail",
                "extension two: blocked model shot",
            ],
        )

    message = str(exc_info.value)
    assert "Google video extension segment 2/2 failed" in message
    assert "Provider RAI filtering returned no video: blocked" in message
    assert "extension two: blocked model shot" in message


def test_gemini_api_video_generation_reports_rai_filter_reasons() -> None:
    service = GeminiAPIVideoGenerationService("test-key")

    with pytest.raises(RuntimeError) as exc_info:
        service._extract_generated_video(
            {
                "rai_media_filtered_count": 1,
                "rai_media_filtered_reasons": [
                    "Sorry, we can't create videos from input images containing photorealistic children."
                ],
            }
        )

    message = str(exc_info.value)
    assert "Provider RAI filtering returned no video (1 filtered)" in message
    assert "photorealistic children" in message


@pytest.mark.asyncio
async def test_gemini_api_video_generation_does_not_send_generate_audio_to_sdk() -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.config = None

        def generate_videos(self, **kwargs):
            self.config = kwargs["config"]
            return SimpleNamespace(name="operations/test-video")

    fake_models = FakeModels()
    service = GeminiAPIVideoGenerationService("test-key")
    service._client = SimpleNamespace(models=fake_models)

    async def fake_wait_for_operation(operation):
        return SimpleNamespace(name=operation.name, result=SimpleNamespace())

    def fake_extract_generated_video(_response):
        return SimpleNamespace(video=SimpleNamespace(mime_type="video/mp4"))

    async def fake_download_video_bytes(_generated_video):
        return b"fake-video"

    service._wait_for_operation = fake_wait_for_operation
    service._extract_generated_video = fake_extract_generated_video
    service._download_video_bytes = fake_download_video_bytes

    await service.generate_video(
        "Product-only visual showcase.",
        "veo-3.1-generate-preview",
        resolution="4k",
        aspect_ratio="9:16",
        seconds=8,
        generateAudio=False,
    )

    assert getattr(fake_models.config, "generate_audio", None) is None


@pytest.mark.asyncio
async def test_gemini_api_video_generation_retries_transient_operation_poll_timeout() -> None:
    class FakeOperations:
        def __init__(self) -> None:
            self.calls = 0
            self.poll_timeouts = []

        def get(self, _operation, *, config=None):
            self.calls += 1
            self.poll_timeouts.append(getattr(getattr(config, "http_options", None), "timeout", None))
            if self.calls == 1:
                raise TimeoutError("timed out")
            return SimpleNamespace(done=True)

    operations = FakeOperations()
    service = GeminiAPIVideoGenerationService(
        "test-key",
        poll_interval_seconds=0,
        poll_timeout_seconds=1,
    )
    service._client = SimpleNamespace(operations=operations)

    operation = await service._wait_for_operation(SimpleNamespace(done=False))

    assert operation.done is True
    assert operations.calls == 2
    assert operations.poll_timeouts == [300000, 300000]
