"""Coverage-focused, behavior-asserting tests for two Google media surfaces.

Targets
-------
* ``app.services.gemini.coordinators.video_generation_coordinator`` — the
  GEN-mode routing coordinator that decides between Gemini API / Vertex AI Veo,
  resolves credentials fail-closed, maps params, dispatches generate / delete /
  download, and chains video extensions.
* ``app.services.gemini.vertexai.imagen_vertex_ai`` — the Vertex AI Imagen /
  Gemini-image generator (config resolution, param mapping, dispatch, error
  handling, RAI filtering).

Strategy
--------
The real SUT logic runs end to end. Only true external boundaries are faked:
the Google GenAI SDK ``client.models`` object (``generate_images`` /
``generate_content`` / ``list``) and the underlying video services. The SUT's
own routing, validation, param mapping, and error mapping run for real.

These assert real behavior: which runtime is selected, which kwargs the SDK
receives, which exception type / message surfaces, response shapes, and the
fail-closed credential contract — not coverage padding.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from app.services.gemini.coordinators.video_generation_coordinator import (
    VideoGenerationCoordinator,
)
from app.services.gemini.http_options import HttpOptions, HttpRetryOptions
from app.services.gemini.vertexai.imagen_vertex_ai import (
    DEFAULT_GENERATE_MODEL,
    GENERATE_CONTENT_MODELS,
    VertexAIImageGenerator,
)
from app.services.gemini.base.imagen_common import (
    APIError,
    ContentPolicyError,
    ParameterValidationError,
    VALID_ASPECT_RATIOS,
    VALID_IMAGE_SIZES,
)


VERTEX_CREDENTIALS_JSON = '{"type":"service_account","project_id":"p","private_key":"k"}'


# --------------------------------------------------------------------------- #
# Helpers / fakes
# --------------------------------------------------------------------------- #
def _vertex_config() -> Dict[str, Any]:
    return {
        "api_mode": "vertex_ai",
        "vertex_ai_project_id": "test-project",
        "vertex_ai_location": "us-central1",
        "vertex_ai_credentials_json": VERTEX_CREDENTIALS_JSON,
    }


class _RecordingService:
    """Stand-in for a video generation service with recordable async methods."""

    def __init__(self, result: Optional[Dict[str, Any]] = None) -> None:
        self.result = (
            result
            if result is not None
            else {"url": "data:video/mp4;base64,AAAA", "mime_type": "video/mp4"}
        )
        self.generate_calls: List[Dict[str, Any]] = []
        self.delete_calls: List[Dict[str, Any]] = []
        self.download_calls: List[Dict[str, Any]] = []

    async def generate_video(self, *, prompt, model, **kwargs):
        self.generate_calls.append({"prompt": prompt, "model": model, **kwargs})
        return dict(self.result)

    async def delete_video(self, **kwargs):
        self.delete_calls.append(dict(kwargs))
        return {"deleted": True}

    async def download_video_asset(self, **kwargs):
        self.download_calls.append(dict(kwargs))
        return {"video_bytes": b"video-bytes", "mime_type": "video/mp4"}


def _coordinator_with_config(config: Dict[str, Any]) -> VideoGenerationCoordinator:
    coord = VideoGenerationCoordinator()
    coord._config = dict(config)
    return coord


# --------------------------------------------------------------------------- #
# Coordinator: config resolution from environment (no DB)
# --------------------------------------------------------------------------- #
def test_load_config_from_env_gemini_default(monkeypatch):
    for var in (
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GCP_PROJECT_ID",
        "GOOGLE_CLOUD_LOCATION",
        "GCP_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

    coord = VideoGenerationCoordinator()

    assert coord._config["api_mode"] == "gemini_api"
    assert coord._config["gemini_api_key"] == "env-key"
    assert coord._config["vertex_ai_location"] == "us-central1"
    assert coord._has_gemini_api_key() is True


def test_load_config_from_env_vertex_mode(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-x")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    coord = VideoGenerationCoordinator()

    assert coord._config["api_mode"] == "vertex_ai"
    assert coord._config["vertex_ai_project_id"] == "proj-x"
    assert coord._config["vertex_ai_location"] == "europe-west4"


def test_provided_api_key_takes_priority_over_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")
    coord = VideoGenerationCoordinator(api_key="explicit-key")
    assert coord._config["gemini_api_key"] == "explicit-key"


# --------------------------------------------------------------------------- #
# Coordinator: normalization / extraction helpers (param mapping)
# --------------------------------------------------------------------------- #
def test_normalize_video_extension_count_variants():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._normalize_video_extension_count({}) == 0
    assert coord._normalize_video_extension_count({"video_extension_count": "3"}) == 3
    assert coord._normalize_video_extension_count({"videoExtensionCount": 2}) == 2


def test_normalize_video_extension_count_rejects_negative_and_garbage():
    coord = VideoGenerationCoordinator(api_key="k")
    with pytest.raises(ValueError):
        coord._normalize_video_extension_count({"video_extension_count": -1})
    with pytest.raises(ValueError):
        coord._normalize_video_extension_count({"video_extension_count": "abc"})


def test_base_duration_seconds_defaults_and_parsing():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._base_duration_seconds({}) == 8
    assert coord._base_duration_seconds({"seconds": "12"}) == 12
    assert coord._base_duration_seconds({"duration_seconds": 0}) == 8
    assert coord._base_duration_seconds({"seconds": "bad"}) == 8


def test_normalize_storyboard_segments_handles_strings_lists_and_dicts():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._normalize_storyboard_segments({}) == []
    assert coord._normalize_storyboard_segments({"storyboard_segments": "single"}) == ["single"]
    assert coord._normalize_storyboard_segments({"storyboard_segments": "   "}) == []
    assert coord._normalize_storyboard_segments({"storyboard_segments": 42}) == []
    parsed = coord._normalize_storyboard_segments(
        {"storyboardSegments": ["a", {"prompt": "b"}, {"text": "c"}]}
    )
    assert parsed == ["a", "b", "c"]


def test_request_has_source_video_and_uri_extraction():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._request_has_source_video({}) is False
    assert coord._request_has_source_video({"source_video": "  "}) is False
    assert coord._request_has_source_video({"source_video": "gs://bucket/v.mp4"}) is True
    assert coord._request_has_source_video({"sourceVideo": {"url": "x"}}) is True

    assert (
        coord._extract_source_video_uri({"source_video": "gs://bucket/v.mp4"})
        == "gs://bucket/v.mp4"
    )
    assert (
        coord._extract_source_video_uri({"source_video": {"gcs_uri": "gs://b/v.mp4"}})
        == "gs://b/v.mp4"
    )
    assert coord._extract_source_video_uri({"source_video": {"raw": "files/abc"}}) == "files/abc"
    assert coord._extract_source_video_uri({}) == ""


def test_source_video_native_detection():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._source_video_is_vertex_native({"source_video": "gs://b/v.mp4"}) is True
    assert coord._source_video_is_vertex_native({"source_video": "files/abc"}) is False
    assert coord._source_video_is_gemini_native({"source_video": "files/abc"}) is True
    assert (
        coord._source_video_is_gemini_native(
            {"source_video": "https://generativelanguage.googleapis.com/v1/files/abc"}
        )
        is True
    )
    assert coord._source_video_is_gemini_native({"source_video": "gs://b/v.mp4"}) is False


def test_request_uses_last_frame_bridge_truthy_variants():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._request_uses_last_frame_bridge({"use_last_frame_bridge": True}) is True
    assert coord._request_uses_last_frame_bridge({"continue_from_last_frame": 1}) is True
    assert coord._request_uses_last_frame_bridge({"continueFromLastFrame": "yes"}) is True
    assert coord._request_uses_last_frame_bridge({"use_last_frame_bridge": False}) is False
    assert coord._request_uses_last_frame_bridge({}) is False


def test_request_has_video_mask_detection():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._request_has_video_mask({"video_mask_image": "data:..."}) is True
    assert coord._request_has_video_mask({"maskImage": {"url": "x"}}) is True
    assert coord._request_has_video_mask({"mask_image": "  "}) is False
    assert coord._request_has_video_mask({}) is False


def test_request_resolution_normalization():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._request_resolution({"resolution": "4k"}) == "4k"
    assert coord._request_resolution({"image_resolution": "1080p"}) == "1080p"


def test_vertex_runtime_ready_and_extension_support():
    ready = _coordinator_with_config(_vertex_config())
    assert ready._vertex_runtime_ready() is True
    assert ready._vertex_supports_video_extension("veo-3.1-generate-001") is True
    assert ready._vertex_supports_video_extension("imagen-3.0") is False

    not_ready = _coordinator_with_config({"api_mode": "vertex_ai"})
    assert not_ready._vertex_runtime_ready() is False


def test_gemini_api_supports_video_extension_matrix():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._gemini_api_supports_video_extension("veo-3.1-generate-001") is True
    assert coord._gemini_api_supports_video_extension("veo-3.0-fast-generate-preview") is True
    assert coord._gemini_api_supports_video_extension("veo-2.0-generate-001") is False


# --------------------------------------------------------------------------- #
# Coordinator: API-mode routing (the big branch surface)
# --------------------------------------------------------------------------- #
def test_select_api_mode_no_source_returns_configured_mode():
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    assert coord._select_api_mode_for_request("veo-3.1-generate-001", {}) == "gemini_api"


def test_select_api_mode_mask_edit_routes_to_vertex_when_ready():
    coord = _coordinator_with_config(_vertex_config())
    kwargs = {"video_mask_image": "data:image/png;base64,AAA"}
    assert coord._select_api_mode_for_request("veo-2.0-generate-001", kwargs) == "vertex_ai"


def test_select_api_mode_non_native_source_forces_last_frame_bridge():
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    kwargs = {"source_video": "data:video/mp4;base64,QUJD"}
    mode = coord._select_api_mode_for_request("veo-3.1-generate-001", kwargs)
    assert mode == "gemini_api"
    assert kwargs["use_last_frame_bridge"] is True


def test_select_api_mode_gs_source_routes_to_vertex_when_supported():
    coord = _coordinator_with_config(_vertex_config())
    kwargs = {"source_video": "gs://bucket/v.mp4"}
    mode = coord._select_api_mode_for_request("veo-3.1-generate-001", kwargs)
    assert mode == "vertex_ai"
    assert "use_last_frame_bridge" not in kwargs


def test_select_api_mode_gs_source_falls_back_to_bridge_when_unsupported_model():
    coord = _coordinator_with_config(_vertex_config())
    kwargs = {"source_video": "gs://bucket/v.mp4"}
    mode = coord._select_api_mode_for_request("unknown-model-x", kwargs)
    # unknown model not in VEO_VIDEO_MODELS extension set -> bridge fallback
    assert mode == "vertex_ai"
    assert kwargs["use_last_frame_bridge"] is True


def test_select_api_mode_gemini_files_source_routes_to_gemini_api():
    coord = _coordinator_with_config({"api_mode": "vertex_ai", "gemini_api_key": "k"})
    kwargs = {"source_video": "files/abc123"}
    mode = coord._select_api_mode_for_request("veo-3.1-generate-001", kwargs)
    assert mode == "gemini_api"


def test_select_api_mode_gemini_files_source_bridge_when_no_key():
    coord = _coordinator_with_config({"api_mode": "vertex_ai"})
    kwargs = {"source_video": "files/abc123"}
    mode = coord._select_api_mode_for_request("veo-3.1-generate-001", kwargs)
    assert mode == "vertex_ai"
    assert kwargs["use_last_frame_bridge"] is True


def test_select_api_mode_vertex_config_supported_model_stays_vertex():
    config = dict(_vertex_config())
    config["gemini_api_key"] = "k"
    coord = _coordinator_with_config(config)
    # generic (non gs:// non files/) source so we go through configured-mode branch.
    # veo-3.1 IS a vertex-extension capable model -> stays on configured vertex.
    kwargs = {"source_video": "https://example.test/v.mp4"}
    mode = coord._select_api_mode_for_request("veo-3.1-generate-001", kwargs)
    assert mode == "vertex_ai"


def test_select_api_mode_vertex_config_unknown_model_bridge_fallback():
    config = dict(_vertex_config())
    config["gemini_api_key"] = "k"
    coord = _coordinator_with_config(config)
    kwargs = {"source_video": "https://example.test/v.mp4"}
    # unknown model: neither vertex nor gemini extension capable -> bridge, stays vertex.
    mode = coord._select_api_mode_for_request("unknown-model-x", kwargs)
    assert mode == "vertex_ai"
    assert kwargs.get("use_last_frame_bridge") is True


def test_select_api_mode_gemini_config_unsupported_model_bridge_fallback():
    config = dict(_vertex_config())
    config["api_mode"] = "gemini_api"
    coord = _coordinator_with_config(config)
    kwargs = {"source_video": "https://example.test/v.mp4"}
    # unknown model is neither gemini-extension nor vertex-extension capable -> bridge.
    mode = coord._select_api_mode_for_request("unknown-model-x", kwargs)
    assert mode == "gemini_api"
    assert kwargs.get("use_last_frame_bridge") is True


# --------------------------------------------------------------------------- #
# Coordinator: error-classification predicates
# --------------------------------------------------------------------------- #
def test_should_runtime_fallback_to_gemini_api_requires_key_and_marker():
    with_key = _coordinator_with_config({"gemini_api_key": "k"})
    assert with_key._should_runtime_fallback_to_gemini_api(
        Exception("Service agents are being provisioned")
    ) is True
    assert with_key._should_runtime_fallback_to_gemini_api(Exception("random error")) is False

    without_key = _coordinator_with_config({})
    assert without_key._should_runtime_fallback_to_gemini_api(
        Exception("output storage uri is required")
    ) is False


def test_should_retry_with_last_frame_bridge_markers():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._should_retry_with_last_frame_bridge(Exception("Internal error")) is True
    assert coord._should_retry_with_last_frame_bridge(
        Exception("did not return any generated videos")
    ) is True
    assert coord._should_retry_with_last_frame_bridge(Exception("permission denied")) is False


def test_should_retry_transient_generation_error_markers():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._should_retry_transient_generation_error(Exception("503 Service Unavailable")) is True
    assert coord._should_retry_transient_generation_error(Exception("Resource exhausted, retry")) is True
    assert coord._should_retry_transient_generation_error(Exception("'code': 8 high load")) is True
    assert coord._should_retry_transient_generation_error(Exception("Deadline exceeded")) is True
    assert coord._should_retry_transient_generation_error(Exception("bad request")) is False


# --------------------------------------------------------------------------- #
# Coordinator: source-video continuation kwargs builders
# --------------------------------------------------------------------------- #
def test_build_source_video_from_result_prefers_provider_refs():
    coord = VideoGenerationCoordinator(api_key="k")
    payload = coord._build_source_video_from_result(
        {
            "provider_file_name": "files/abc",
            "provider_file_uri": "https://x/files/abc",
            "gcs_uri": "gs://b/v.mp4",
            "mime_type": "video/mp4",
        }
    )
    assert payload["provider_file_name"] == "files/abc"
    assert payload["gcs_uri"] == "gs://b/v.mp4"
    assert payload["mime_type"] == "video/mp4"


def test_build_source_video_from_result_url_only_non_base64():
    coord = VideoGenerationCoordinator(api_key="k")
    payload = coord._build_source_video_from_result({"url": "https://cdn/v.mp4"})
    assert payload == {"url": "https://cdn/v.mp4", "mime_type": "video/mp4"}


def test_build_source_video_from_result_base64_url_excluded_from_payload_but_url_returned():
    coord = VideoGenerationCoordinator(api_key="k")
    # A base64 data URL is NOT promoted into the structured provider payload
    # (it is excluded by the ``not is_base64_url`` guard), but the fallback
    # ``if url:`` branch still returns a minimal {url, mime_type} dict.
    payload = coord._build_source_video_from_result({"url": "data:video/mp4;base64,QUJD"})
    assert payload == {"url": "data:video/mp4;base64,QUJD", "mime_type": "video/mp4"}


def test_build_source_video_from_result_empty_returns_none():
    coord = VideoGenerationCoordinator(api_key="k")
    assert coord._build_source_video_from_result({}) is None


def test_build_continuation_kwargs_strips_inputs_and_requires_asset():
    coord = VideoGenerationCoordinator(api_key="k")
    base = {
        "seconds": 8,
        "source_image": {"url": "x"},
        "video_mask_image": "y",
        "video_extension_count": 2,
        "use_last_frame_bridge": True,
    }
    result = {"gcs_uri": "gs://b/v.mp4", "mime_type": "video/mp4"}
    out = coord._build_continuation_kwargs(base, result)
    assert out["source_video"]["gcs_uri"] == "gs://b/v.mp4"
    assert "source_image" not in out
    assert "video_mask_image" not in out
    assert "video_extension_count" not in out
    assert "use_last_frame_bridge" not in out
    # base untouched (immutability of caller input)
    assert base["source_image"] == {"url": "x"}


def test_build_continuation_kwargs_raises_without_provider_asset():
    coord = VideoGenerationCoordinator(api_key="k")
    # An empty result yields no source video asset -> hard error.
    with pytest.raises(ValueError, match="provider-backed video asset"):
        coord._build_continuation_kwargs({}, {})


def test_build_last_frame_bridge_continuation_kwargs_sets_source_image():
    coord = VideoGenerationCoordinator(api_key="k")
    out = coord._build_last_frame_bridge_continuation_kwargs(
        {"seconds": 8, "source_video": "gs://x", "video_extension_count": 3},
        {"url": "data:image/png;base64,QUJD", "mime_type": "image/png"},
    )
    assert out["source_image"]["mime_type"] == "image/png"
    assert "source_video" not in out
    assert "video_extension_count" not in out


# --------------------------------------------------------------------------- #
# Coordinator: get_service construction + fallback
# --------------------------------------------------------------------------- #
def test_create_gemini_api_service_requires_key():
    coord = _coordinator_with_config({"api_mode": "gemini_api"})
    coord._provided_api_key = None
    with pytest.raises(ValueError, match="Google API key"):
        coord._create_gemini_api_service()


def test_create_vertex_service_requires_project_and_creds():
    coord = _coordinator_with_config({"api_mode": "vertex_ai"})
    with pytest.raises(ValueError, match="project_id and credentials_json"):
        coord._create_vertex_service()


def test_get_service_caches_and_falls_back_to_gemini(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "vertex_ai", "gemini_api_key": "k"})

    gemini_service = _RecordingService()

    def _boom():
        raise RuntimeError("vertex init failed")

    monkeypatch.setattr(coord, "_create_vertex_service", _boom)
    monkeypatch.setattr(coord, "_create_gemini_api_service", lambda: gemini_service)

    service = coord.get_service(api_mode_override="vertex_ai")
    assert service is gemini_service
    # cached under gemini_api now
    assert coord.get_service(api_mode_override="gemini_api") is gemini_service


def test_get_service_gemini_failure_propagates(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api"})

    def _boom():
        raise ValueError("no key")

    monkeypatch.setattr(coord, "_create_gemini_api_service", _boom)
    with pytest.raises(ValueError, match="no key"):
        coord.get_service(api_mode_override="gemini_api")


def test_get_current_api_mode_reflects_service_type(monkeypatch):
    from app.services.gemini.vertexai.video_generation_service import (
        VertexAIVideoGenerationService,
    )

    coord = _coordinator_with_config({"api_mode": "vertex_ai"})
    fake_vertex = VertexAIVideoGenerationService.__new__(VertexAIVideoGenerationService)
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: fake_vertex)
    assert coord.get_current_api_mode() == "vertex_ai"

    coord2 = _coordinator_with_config({"api_mode": "gemini_api"})
    monkeypatch.setattr(coord2, "get_service", lambda *a, **k: _RecordingService())
    assert coord2.get_current_api_mode() == "gemini_api"


# --------------------------------------------------------------------------- #
# Coordinator: delete_video / download_video_asset dispatch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_video_routes_provider_file_name_to_gemini(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    service = _RecordingService()
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    result = await coord.delete_video(provider_file_name="files/abc")
    assert result["coordinator_api_mode"] == "gemini_api"
    assert service.delete_calls[0]["provider_file_name"] == "files/abc"


@pytest.mark.asyncio
async def test_delete_video_routes_gcs_uri_to_vertex(monkeypatch):
    coord = _coordinator_with_config(_vertex_config())
    service = _RecordingService()
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    result = await coord.delete_video(gcs_uri="gs://bucket/v.mp4")
    assert result["coordinator_api_mode"] == "vertex_ai"
    assert service.delete_calls[0]["gcs_uri"] == "gs://bucket/v.mp4"


@pytest.mark.asyncio
async def test_delete_video_requires_identifier():
    coord = VideoGenerationCoordinator(api_key="k")
    with pytest.raises(ValueError, match="requires provider_file_name or gcs_uri"):
        await coord.delete_video()


@pytest.mark.asyncio
async def test_delete_video_raises_when_runtime_unavailable(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: SimpleNamespace())
    with pytest.raises(ValueError, match="deletion runtime is unavailable"):
        await coord.delete_video(provider_file_name="files/abc")


@pytest.mark.asyncio
async def test_download_video_asset_routes_to_gemini(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    service = _RecordingService()
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    result = await coord.download_video_asset(
        provider_file_name="files/abc", mime_type="video/mp4"
    )
    assert result["coordinator_api_mode"] == "gemini_api"
    assert service.download_calls[0]["provider_file_name"] == "files/abc"


@pytest.mark.asyncio
async def test_download_video_asset_routes_gcs_to_vertex(monkeypatch):
    coord = _coordinator_with_config(_vertex_config())
    service = _RecordingService()
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    result = await coord.download_video_asset(provider_file_uri="gs://bucket/v.mp4")
    assert result["coordinator_api_mode"] == "vertex_ai"
    assert service.download_calls[0]["gcs_uri"] == "gs://bucket/v.mp4"


@pytest.mark.asyncio
async def test_download_video_asset_requires_identifier():
    coord = VideoGenerationCoordinator(api_key="k")
    with pytest.raises(ValueError, match="requires provider_file_name or gcs_uri"):
        await coord.download_video_asset()


# --------------------------------------------------------------------------- #
# Coordinator: _download_result_video_bytes paths
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_download_result_video_bytes_data_url():
    coord = VideoGenerationCoordinator(api_key="k")
    # base64 of b"hi" is "aGk="
    data, mime = await coord._download_result_video_bytes(
        {"url": "data:video/mp4;base64,aGk="}
    )
    assert data == b"hi"
    assert mime == "video/mp4"


@pytest.mark.asyncio
async def test_download_result_video_bytes_requires_dict():
    coord = VideoGenerationCoordinator(api_key="k")
    with pytest.raises(ValueError, match="generation result payload"):
        await coord._download_result_video_bytes("not-a-dict")


@pytest.mark.asyncio
async def test_download_result_video_bytes_no_asset_raises():
    coord = VideoGenerationCoordinator(api_key="k")
    with pytest.raises(ValueError, match="downloadable video asset"):
        await coord._download_result_video_bytes({"mime_type": "video/mp4"})


@pytest.mark.asyncio
async def test_download_result_video_bytes_provider_asset(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")

    async def _fake_wait(result):
        return None

    async def _fake_download(**kwargs):
        return {"video_bytes": b"binary", "mime_type": "video/mp4"}

    monkeypatch.setattr(coord, "_wait_for_gemini_video_asset_ready", _fake_wait)
    monkeypatch.setattr(coord, "download_video_asset", _fake_download)

    data, mime = await coord._download_result_video_bytes(
        {"provider_file_name": "files/abc", "mime_type": "video/mp4"}
    )
    assert data == b"binary"
    assert mime == "video/mp4"


@pytest.mark.asyncio
async def test_download_result_video_bytes_provider_asset_bad_payload(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")

    async def _fake_wait(result):
        return None

    async def _fake_download(**kwargs):
        return {"video_bytes": "not-bytes"}

    monkeypatch.setattr(coord, "_wait_for_gemini_video_asset_ready", _fake_wait)
    monkeypatch.setattr(coord, "download_video_asset", _fake_download)

    with pytest.raises(RuntimeError, match="unsupported payload"):
        await coord._download_result_video_bytes(
            {"provider_file_uri": "https://x/files/abc"}
        )


# --------------------------------------------------------------------------- #
# Coordinator: _wait_for_gemini_video_asset_ready gating
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_wait_for_gemini_video_asset_ready_skips_non_gemini():
    coord = VideoGenerationCoordinator(api_key="k")
    # Not a dict -> returns immediately.
    assert await coord._wait_for_gemini_video_asset_ready("x") is None
    # vertex result -> skip.
    assert (
        await coord._wait_for_gemini_video_asset_ready(
            {"coordinator_api_mode": "vertex_ai", "provider_file_name": "files/abc"}
        )
        is None
    )


@pytest.mark.asyncio
async def test_wait_for_gemini_video_asset_ready_invokes_service(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")
    calls: List[Dict[str, Any]] = []

    async def _wait(**kwargs):
        calls.append(kwargs)

    service = SimpleNamespace(wait_until_video_asset_processed=_wait)
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    await coord._wait_for_gemini_video_asset_ready(
        {"coordinator_api_mode": "gemini_api", "provider_file_name": "files/abc"}
    )
    assert calls and calls[0]["provider_file_name"] == "files/abc"


# --------------------------------------------------------------------------- #
# Coordinator: _generate_single_video dispatch + retry/fallback
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_generate_single_video_happy_path(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    service = _RecordingService({"url": "data:video/mp4;base64,AAAA", "mime_type": "video/mp4"})
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    result = await coord._generate_single_video(
        "prompt", "veo-3.1-generate-001", {}, selected_api_mode="gemini_api"
    )
    assert result["coordinator_api_mode"] == "gemini_api"
    assert service.generate_calls[0]["prompt"] == "prompt"


@pytest.mark.asyncio
async def test_generate_single_video_retries_transient_then_succeeds(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})

    class _FlakyService:
        def __init__(self):
            self.calls = 0

        async def generate_video(self, *, prompt, model, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("503 service unavailable")
            return {"url": "ok", "mime_type": "video/mp4"}

    service = _FlakyService()
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    sleeps: List[float] = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(
        "app.services.gemini.coordinators.video_generation_coordinator.asyncio.sleep",
        _fake_sleep,
    )

    result = await coord._generate_single_video(
        "p", "veo-3.1-generate-001", {}, selected_api_mode="gemini_api"
    )
    assert result["url"] == "ok"
    assert service.calls == 2
    assert sleeps  # a backoff delay was applied


@pytest.mark.asyncio
async def test_generate_single_video_vertex_runtime_fallback_to_gemini(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "vertex_ai", "gemini_api_key": "k"})

    vertex_service = _RecordingService()

    async def _vertex_fail(*, prompt, model, **kwargs):
        raise RuntimeError("Service agents are being provisioned")

    vertex_service.generate_video = _vertex_fail  # type: ignore[assignment]
    gemini_service = _RecordingService({"url": "gemini-ok", "mime_type": "video/mp4"})

    def _get_service(api_mode_override=None):
        return gemini_service if api_mode_override == "gemini_api" else vertex_service

    monkeypatch.setattr(coord, "get_service", _get_service)

    result = await coord._generate_single_video(
        "p", "veo-3.1-generate-001", {}, selected_api_mode="vertex_ai"
    )
    assert result["service_fallback"] == "vertex_to_gemini_api"
    assert result["coordinator_api_mode"] == "gemini_api"


@pytest.mark.asyncio
async def test_generate_single_video_reraises_unhandled(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})

    class _BadService:
        async def generate_video(self, *, prompt, model, **kwargs):
            raise ValueError("hard validation failure")

    monkeypatch.setattr(coord, "get_service", lambda *a, **k: _BadService())
    with pytest.raises(ValueError, match="hard validation failure"):
        await coord._generate_single_video(
            "p", "veo-3.1-generate-001", {}, selected_api_mode="gemini_api"
        )


# --------------------------------------------------------------------------- #
# Coordinator: top-level generate_video (no extension) end to end
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_generate_video_no_extension_applies_storyboard_metadata(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    service = _RecordingService(
        {"url": "data:video/mp4;base64,AAAA", "mime_type": "video/mp4", "filename": "v.mp4"}
    )
    monkeypatch.setattr(coord, "get_service", lambda *a, **k: service)

    result = await coord.generate_video(
        "a calm beach scene",
        "veo-3.1-generate-001",
        seconds=8,
        resolution="720p",
        aspect_ratio="16:9",
    )
    assert result["prompt"] == "a calm beach scene"
    assert "storyboard_prompt" in result
    assert result["coordinator_api_mode"] == "gemini_api"
    # storyboard metadata stamped
    assert "generate_audio" in result


@pytest.mark.asyncio
async def test_generate_video_base_segment_failure_wrapped(monkeypatch):
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})

    async def _fail(*args, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(coord, "_generate_single_video", _fail)
    with pytest.raises(RuntimeError, match="Google video base segment failed"):
        await coord.generate_video("p", "veo-3.1-generate-001", seconds=8)


# --------------------------------------------------------------------------- #
# Coordinator: ffmpeg concat helpers
# --------------------------------------------------------------------------- #
def test_concatenate_single_segment_returns_bytes_without_ffmpeg():
    coord = VideoGenerationCoordinator(api_key="k")
    out = coord._concatenate_video_segments_sync([(b"only", "video/mp4")], 1.0)
    assert out == b"only"


def test_concatenate_empty_segments_raises():
    coord = VideoGenerationCoordinator(api_key="k")
    with pytest.raises(ValueError, match="at least one segment"):
        coord._concatenate_video_segments_sync([], 1.0)


def test_concatenate_requires_ffmpeg_for_multi_segment(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")
    monkeypatch.setattr(
        "app.services.gemini.coordinators.video_generation_coordinator.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(RuntimeError, match="ffmpeg is required"):
        coord._concatenate_video_segments_sync(
            [(b"a", "video/mp4"), (b"b", "video/mp4")], 1.0
        )


def test_concat_list_line_format(tmp_path):
    coord = VideoGenerationCoordinator(api_key="k")
    p = tmp_path / "segment-000.mp4"
    line = coord._concat_list_line(p)
    assert line.startswith("file '")
    assert line.endswith("'\n")


# ========================================================================== #
# VertexAIImageGenerator
# ========================================================================== #
def _make_imagen_generator() -> VertexAIImageGenerator:
    return VertexAIImageGenerator(
        project_id="proj",
        location="us-central1",
        credentials_json=VERTEX_CREDENTIALS_JSON,
    )


def test_imagen_init_validates_service_account_json():
    gen = _make_imagen_generator()
    assert gen.project_id == "proj"
    assert gen.credentials_info["type"] == "service_account"


def test_imagen_init_rejects_non_service_account_json():
    with pytest.raises(ValueError, match="missing 'type' field or not a service account"):
        VertexAIImageGenerator("p", "l", '{"type":"user"}')


def test_imagen_init_rejects_malformed_json():
    with pytest.raises(ValueError, match="Invalid JSON format"):
        VertexAIImageGenerator("p", "l", "{not json")


def test_imagen_validate_parameters_accepts_defaults():
    gen = _make_imagen_generator()
    gen.validate_parameters()  # all defaults valid


def test_imagen_validate_parameters_rejects_bad_aspect_ratio():
    gen = _make_imagen_generator()
    with pytest.raises(ParameterValidationError, match="Invalid aspect_ratio"):
        gen.validate_parameters(aspect_ratio="99:1")


def test_imagen_validate_parameters_rejects_bad_image_size():
    gen = _make_imagen_generator()
    with pytest.raises(ParameterValidationError, match="Invalid image_size"):
        gen.validate_parameters(image_size="9K")


def test_imagen_validate_parameters_rejects_bad_number_of_images():
    gen = _make_imagen_generator()
    with pytest.raises(ParameterValidationError, match="number_of_images"):
        gen.validate_parameters(number_of_images=9)
    with pytest.raises(ParameterValidationError, match="number_of_images"):
        gen.validate_parameters(number_of_images="2")


def test_imagen_build_config_defaults_and_clamping():
    gen = _make_imagen_generator()
    config = gen._build_config(
        number_of_images=99, aspect_ratio="16:9", model="imagen-3.0-generate-002"
    )
    assert config.number_of_images == 4  # clamped to max 4
    assert config.aspect_ratio == "16:9"


def test_imagen_build_config_passes_image_size_for_supported_model():
    gen = _make_imagen_generator()
    config = gen._build_config(image_size="2K", model="imagen-3.0-generate-002")
    assert getattr(config, "image_size", None) == "2K"


def test_imagen_build_config_skips_image_size_for_unsupported_model():
    gen = _make_imagen_generator()
    config = gen._build_config(image_size="2K", model="imagen-4.0-generate-001")
    assert getattr(config, "image_size", None) in (None, "")


def test_imagen_build_config_adds_jpeg_compression_quality():
    gen = _make_imagen_generator()
    config = gen._build_config(output_mime_type="image/jpeg", output_compression_quality=80)
    assert getattr(config, "output_compression_quality", None) == 80


def test_imagen_build_config_passes_enhance_prompt_flag():
    gen = _make_imagen_generator()
    config = gen._build_config(enhance_prompt=False)
    assert getattr(config, "enhance_prompt", None) is False


def test_imagen_get_capabilities_uses_fallback_when_dynamic_fails(monkeypatch):
    gen = _make_imagen_generator()
    monkeypatch.setattr(
        gen, "get_supported_models", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    caps = gen.get_capabilities()
    assert caps["api_type"] == "vertex_ai"
    assert caps["max_images"] == 4
    assert "imagen-3.0-generate-002" in caps["supported_models"]
    assert caps["supported_aspect_ratios"] == VALID_ASPECT_RATIOS
    assert caps["image_sizes"] == VALID_IMAGE_SIZES


def test_imagen_get_capabilities_uses_dynamic_models(monkeypatch):
    gen = _make_imagen_generator()
    monkeypatch.setattr(gen, "get_supported_models", lambda: ["imagen-3.0-generate-002"])
    caps = gen.get_capabilities()
    assert caps["supported_models"] == ["imagen-3.0-generate-002"]


def test_generate_content_models_membership():
    # param-mapping contract: the dispatch set must include Gemini image + Veo models.
    assert "gemini-2.5-flash-image" in GENERATE_CONTENT_MODELS
    assert "veo-3.1-generate-preview" in GENERATE_CONTENT_MODELS
    assert DEFAULT_GENERATE_MODEL == "imagen-3.0-generate-002"


# ---- Imagen generate dispatch (generate_images path) ---- #
class _FakeImagenImage:
    def __init__(self, image_bytes: bytes = b"png-bytes"):
        self.image_bytes = image_bytes

    def save(self, path):
        with open(path, "wb") as fh:
            fh.write(self.image_bytes)


class _FakeGeneratedImage:
    def __init__(
        self,
        image_bytes: Optional[bytes] = b"png-bytes",
        rai_reason: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
    ):
        self.rai_filtered_reason = rai_reason
        self.image = _FakeImagenImage(image_bytes) if image_bytes is not None else None
        self.enhanced_prompt = enhanced_prompt


class _FakeImagenResponse:
    def __init__(self, generated_images):
        self.generated_images = generated_images


class _FakeGeminiPart:
    def __init__(self, data: bytes):
        self.inline_data = SimpleNamespace(data=data)


class _FakeGeminiCandidate:
    def __init__(self, parts):
        self.content = SimpleNamespace(parts=parts)


class _FakeGeminiResponse:
    def __init__(self, candidates):
        self.candidates = candidates


class _FakeModels:
    def __init__(self, *, images_response=None, content_response=None, models_list=None):
        self._images_response = images_response
        self._content_response = content_response
        self._models_list = models_list or []
        self.generate_images_calls: List[Dict[str, Any]] = []
        self.generate_content_calls: List[Dict[str, Any]] = []

    def generate_images(self, **kwargs):
        self.generate_images_calls.append(kwargs)
        return self._images_response

    def generate_content(self, **kwargs):
        self.generate_content_calls.append(kwargs)
        return self._content_response

    def list(self):
        return self._models_list


def _inject_fake_client(gen: VertexAIImageGenerator, models: _FakeModels) -> None:
    gen._client = SimpleNamespace(models=models)
    gen._initialized = True


@pytest.mark.asyncio
async def test_imagen_generate_image_imagen_path_returns_results():
    gen = _make_imagen_generator()
    models = _FakeModels(
        images_response=_FakeImagenResponse(
            [_FakeGeneratedImage(b"img1", enhanced_prompt="enhanced text")]
        )
    )
    _inject_fake_client(gen, models)

    results = await gen.generate_image(
        "a cat", "imagen-3.0-generate-002", number_of_images=1, image_style="oil painting"
    )
    assert len(results) == 1
    assert results[0]["mime_type"] == "image/png"
    assert results[0]["enhanced_prompt"] == "enhanced text"
    assert results[0]["url"].startswith("data:image/png;base64,")
    # style applied to effective prompt
    assert "style: oil painting" in models.generate_images_calls[0]["prompt"]


@pytest.mark.asyncio
async def test_imagen_generate_image_imagen_no_images_raises_api_error():
    gen = _make_imagen_generator()
    models = _FakeModels(images_response=_FakeImagenResponse([]))
    _inject_fake_client(gen, models)

    with pytest.raises(APIError, match="No images generated"):
        await gen.generate_image("x", "imagen-3.0-generate-002")


@pytest.mark.asyncio
async def test_imagen_generate_image_imagen_sdk_error_wrapped():
    gen = _make_imagen_generator()

    class _ExplodingModels(_FakeModels):
        def generate_images(self, **kwargs):
            raise RuntimeError("vertex sdk down")

    _inject_fake_client(gen, _ExplodingModels())

    with pytest.raises(APIError) as exc_info:
        await gen.generate_image("x", "imagen-3.0-generate-002")
    assert exc_info.value.api_type == "vertex_ai"
    assert "vertex sdk down" in str(exc_info.value)


def test_imagen_process_response_filters_rai_then_raises_content_policy():
    gen = _make_imagen_generator()
    response = _FakeImagenResponse([_FakeGeneratedImage(rai_reason="blocked by policy")])
    with pytest.raises(ContentPolicyError, match="blocked by policy"):
        gen._process_response(response)


def test_imagen_process_response_no_valid_images_raises_api_error():
    gen = _make_imagen_generator()
    # generated image with image=None -> skipped, no RAI -> APIError
    img = _FakeGeneratedImage(image_bytes=None)
    response = _FakeImagenResponse([img])
    with pytest.raises(APIError, match="No valid images"):
        gen._process_response(response)


def test_imagen_process_response_extracts_enhanced_prompt_and_temp_cleanup():
    gen = _make_imagen_generator()
    response = _FakeImagenResponse(
        [_FakeGeneratedImage(b"abc", enhanced_prompt="rewritten prompt")]
    )
    results = gen._process_response(response, output_mime_type="image/png")
    assert len(results) == 1
    assert results[0]["enhanced_prompt"] == "rewritten prompt"
    assert results[0]["index"] == 0


# ---- Gemini generate_content image path ---- #
@pytest.mark.asyncio
async def test_imagen_generate_image_gemini_path_extracts_inline_data():
    gen = _make_imagen_generator()
    candidate = _FakeGeminiCandidate([_FakeGeminiPart(b"gemini-img")])
    models = _FakeModels(content_response=_FakeGeminiResponse([candidate]))
    _inject_fake_client(gen, models)

    results = await gen.generate_image("a dog", "gemini-2.5-flash-image", number_of_images=1)
    assert len(results) == 1
    assert results[0]["mime_type"] == "image/png"
    assert results[0]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_imagen_generate_image_gemini_path_no_candidates_raises():
    gen = _make_imagen_generator()
    models = _FakeModels(content_response=_FakeGeminiResponse([]))
    _inject_fake_client(gen, models)

    with pytest.raises(APIError, match="No images generated from Gemini"):
        await gen.generate_image("x", "gemini-2.5-flash-image", number_of_images=1)


@pytest.mark.asyncio
async def test_imagen_generate_image_gemini_path_applies_style_for_multiple():
    gen = _make_imagen_generator()
    candidate = _FakeGeminiCandidate([_FakeGeminiPart(b"img")])
    models = _FakeModels(content_response=_FakeGeminiResponse([candidate]))
    _inject_fake_client(gen, models)

    # Public API caps number_of_images at 4 (validate_parameters).
    results = await gen.generate_image(
        "a fox",
        "gemini-2.5-flash-image",
        number_of_images=3,
        image_style="watercolor",
    )
    assert len(results) == 3
    assert (
        "style: watercolor"
        in models.generate_content_calls[0]["contents"][0].parts[0].text
    )


@pytest.mark.asyncio
async def test_imagen_generate_with_gemini_clamps_count_to_eight():
    # The internal generate_content loop clamps number_of_images into [1, 8].
    gen = _make_imagen_generator()
    candidate = _FakeGeminiCandidate([_FakeGeminiPart(b"img")])
    models = _FakeModels(content_response=_FakeGeminiResponse([candidate]))
    _inject_fake_client(gen, models)

    results = await gen._generate_with_gemini(
        "gemini-2.5-flash-image", "a fox", number_of_images=20
    )
    assert len(results) == 8
    assert len(models.generate_content_calls) == 8


@pytest.mark.asyncio
async def test_imagen_generate_image_gemini_sdk_error_wrapped():
    gen = _make_imagen_generator()

    class _ExplodingModels(_FakeModels):
        def generate_content(self, **kwargs):
            raise RuntimeError("gemini content failure")

    _inject_fake_client(gen, _ExplodingModels())
    with pytest.raises(APIError) as exc_info:
        await gen.generate_image("x", "gemini-2.5-flash-image", number_of_images=1)
    assert "gemini content failure" in str(exc_info.value)


# ---- get_supported_models filtering ---- #
def test_imagen_get_supported_models_filters_and_sorts():
    gen = _make_imagen_generator()
    models_list = [
        SimpleNamespace(name="publishers/google/models/imagen-3.0-generate-002"),
        SimpleNamespace(name="publishers/google/models/imagen-3.0-capability-001"),  # excluded
        SimpleNamespace(name="publishers/google/models/gemini-2.5-flash-image"),
        SimpleNamespace(name="publishers/google/models/veo-3.1-generate-001"),
        SimpleNamespace(name="publishers/google/models/image-segmentation-001"),  # excluded
        SimpleNamespace(name="publishers/google/models/imagegeneration"),
        SimpleNamespace(name="publishers/google/models/virtual-try-on-001"),  # excluded
    ]
    fake_models = _FakeModels(models_list=models_list)
    _inject_fake_client(gen, fake_models)

    supported = gen.get_supported_models()
    assert "imagen-3.0-generate-002" in supported
    assert "gemini-2.5-flash-image" in supported
    assert "veo-3.1-generate-001" in supported
    assert "imagegeneration" in supported
    assert "imagen-3.0-capability-001" not in supported
    assert "image-segmentation-001" not in supported
    assert "virtual-try-on-001" not in supported
    # sorted output
    assert supported == sorted(supported)


def test_imagen_get_supported_models_fallback_on_list_error():
    gen = _make_imagen_generator()

    class _ExplodingModels(_FakeModels):
        def list(self):
            raise RuntimeError("list failed")

    _inject_fake_client(gen, _ExplodingModels())
    supported = gen.get_supported_models()
    # static fallback list
    assert "imagen-3.0-generate-002" in supported
    assert "veo-3.1-generate-001" in supported


# ========================================================================== #
# Coordinator: HTTP option builders (param mapping / timeout policy)
# ========================================================================== #
def test_build_prompt_enhance_http_options_from_dict_input():
    coord = VideoGenerationCoordinator(
        api_key="k",
        http_options={"api_version": "v1beta", "timeout": 30000, "headers": {"x": "1"}},
    )
    options = coord._build_prompt_enhance_http_options()
    assert options.api_version == "v1beta"
    assert options.headers == {"x": "1"}
    assert options.timeout is None  # enhancement disables the 30s default
    assert options.use_default_timeout is False


def test_build_video_generation_http_options_extends_short_timeout():
    coord = VideoGenerationCoordinator(
        api_key="k",
        http_options=HttpOptions(timeout=1000),
    )
    options = coord._build_video_generation_http_options()
    # short timeouts are bumped to the long video floor (>= 300000 ms)
    assert options.timeout >= 300000


def test_build_video_generation_http_options_defaults_when_no_options():
    coord = VideoGenerationCoordinator(api_key="k")
    options = coord._build_video_generation_http_options()
    assert options.timeout >= 300000
    assert options.use_default_timeout is False


# ========================================================================== #
# Coordinator: local prompt enhancement
# ========================================================================== #
@pytest.mark.asyncio
async def test_enhance_prompt_locally_returns_none_without_key():
    coord = _coordinator_with_config({"api_mode": "gemini_api"})
    coord._provided_api_key = None
    result = await coord._enhance_prompt_locally(prompt="rewrite me")
    assert result is None


@pytest.mark.asyncio
async def test_enhance_prompt_locally_swallows_pool_errors(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")

    def _boom():
        raise RuntimeError("pool unavailable")

    monkeypatch.setattr(
        "app.services.gemini.coordinators.video_generation_coordinator.get_client_pool",
        _boom,
    )
    # Failure inside the enhancement path is non-fatal -> returns None.
    result = await coord._enhance_prompt_locally(prompt="rewrite me", model_hint="gemini-2.5-flash")
    assert result is None


@pytest.mark.asyncio
async def test_enhance_prompt_locally_returns_text(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")

    class _FakeClient:
        class models:  # noqa: N801 - mimic SDK attribute shape
            @staticmethod
            def generate_content(**kwargs):
                return SimpleNamespace(text="ENHANCED PROMPT", parts=None)

    class _FakePool:
        def get_client(self, **kwargs):
            return _FakeClient()

    monkeypatch.setattr(
        "app.services.gemini.coordinators.video_generation_coordinator.get_client_pool",
        lambda: _FakePool(),
    )
    result = await coord._enhance_prompt_locally(
        prompt="rewrite me", model_hint="gemini-2.5-flash"
    )
    assert result == "ENHANCED PROMPT"


# ========================================================================== #
# Coordinator: prepare prompt for runtime (storyboard, no enhancement)
# ========================================================================== #
@pytest.mark.asyncio
async def test_prepare_prompt_for_runtime_vertex_builds_storyboard():
    coord = _coordinator_with_config(_vertex_config())
    payload = await coord._prepare_prompt_for_runtime(
        prompt="a product hero shot",
        model="veo-3.1-generate-001",
        request_kwargs={"seconds": 8},
        extension_count=0,
        selected_api_mode="vertex_ai",
    )
    assert payload["effective_prompt"]
    assert payload["storyboard_prompt"]
    assert payload["enhanced_prompt"] is None
    assert payload["prompt_enhancement"] is None
    assert isinstance(payload["extension_prompts"], list)


@pytest.mark.asyncio
async def test_prepare_prompt_for_runtime_gemini_no_enhance_pops_flags():
    coord = _coordinator_with_config({"api_mode": "gemini_api", "gemini_api_key": "k"})
    request_kwargs = {"seconds": 8, "enhance_prompt": False}
    payload = await coord._prepare_prompt_for_runtime(
        prompt="a beach",
        model="veo-3.1-generate-001",
        request_kwargs=request_kwargs,
        extension_count=0,
        selected_api_mode="gemini_api",
    )
    # gemini_api path strips the enhance flags from request kwargs
    assert "enhance_prompt" not in request_kwargs
    assert payload["enhanced_prompt"] is None


# ========================================================================== #
# Coordinator: _build_last_frame_source_image_from_video_bytes
# ========================================================================== #
@pytest.mark.asyncio
async def test_build_last_frame_source_image_from_video_bytes(monkeypatch):
    coord = VideoGenerationCoordinator(api_key="k")

    def _fake_extract(loaded):
        return SimpleNamespace(image_bytes=b"frame", mime_type="image/png")

    monkeypatch.setattr(
        "app.services.gemini.coordinators.video_generation_coordinator.extract_last_frame_image",
        _fake_extract,
    )
    source_image = await coord._build_last_frame_source_image_from_video_bytes(
        b"video", "video/mp4"
    )
    assert source_image["mime_type"] == "image/png"
    assert source_image["url"].startswith("data:image/png;base64,")


# ========================================================================== #
# Coordinator: gemini-native video-extension chain (official, non-bridge)
# ========================================================================== #
class _GeminiExtensionCoordinator(VideoGenerationCoordinator):
    """Drives the official (non-bridge) gemini_api video-extension chain."""

    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self._config = {"api_mode": "gemini_api", "gemini_api_key": "test-key"}
        self.requests: List[Dict[str, Any]] = []
        self.selected_modes: List[Optional[str]] = []

    async def _wait_for_gemini_video_asset_ready(self, _result):
        return None

    async def _generate_single_video(self, prompt, model, request_kwargs, *, selected_api_mode=None):
        self.requests.append(dict(request_kwargs))
        self.selected_modes.append(selected_api_mode)
        index = len(self.requests) - 1
        return {
            "url": f"https://generativelanguage.googleapis.com/v1/files/out-{index}",
            "mime_type": "video/mp4",
            "filename": "veo-3.1-generate-preview-720p.mp4",
            "duration_seconds": 8,
            "job_id": f"job-{index}",
            "model": model,
            "provider_platform": "developer_api",
            "provider_file_name": f"files/out-{index}",
            "provider_file_uri": f"https://generativelanguage.googleapis.com/v1/files/out-{index}",
        }


@pytest.mark.asyncio
async def test_generate_video_gemini_native_official_extension_chain():
    coord = _GeminiExtensionCoordinator()

    result = await coord.generate_video(
        "continuous 720p product video",
        "veo-3.1-generate-001",
        resolution="720p",
        aspect_ratio="16:9",
        seconds=8,
        video_extension_count=2,
        source_video="files/seed-asset",
    )

    # base + 2 extensions = 3 generate calls
    assert len(coord.requests) == 3
    assert coord.selected_modes == ["gemini_api", "gemini_api", "gemini_api"]
    # continuation kwargs carry the previous segment's provider asset forward
    assert coord.requests[1]["source_video"]["provider_file_name"] == "files/out-0"
    assert coord.requests[2]["source_video"]["provider_file_name"] == "files/out-1"
    assert result["continuation_strategy"] == "video_extension_chain"
    assert result["video_extension_count"] == 2
    assert result["video_extension_applied"] == 2
    assert result["total_duration_seconds"] == 22


# ========================================================================== #
# Coordinator: DB-backed config resolution (success + exception fallback)
# ========================================================================== #
class _QueryResult:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, rows_by_model):
        self._rows = rows_by_model

    def query(self, model):
        return _QueryResult(self._rows.get(model))


def test_load_config_db_success_resolves_vertex_and_api_key(monkeypatch):
    from cryptography.fernet import Fernet

    from app.core.encryption import encrypt_data
    from app.models.db_models import ConfigProfile, UserSettings, VertexAIConfig
    from app.services.gemini.coordinators import _config_cache

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    _config_cache.clear_config_cache()

    creds_cipher = encrypt_data(VERTEX_CREDENTIALS_JSON)
    api_key_cipher = encrypt_data("AIzaPlaintextKey")

    db = _FakeDB(
        {
            VertexAIConfig: SimpleNamespace(
                api_mode="vertex_ai",
                vertex_ai_project_id="proj-db",
                vertex_ai_location="us-east1",
                vertex_ai_credentials_json=creds_cipher,
            ),
            UserSettings: SimpleNamespace(active_profile_id="profile-1"),
            ConfigProfile: SimpleNamespace(
                provider_id="google",
                api_key=api_key_cipher,
                updated_at=0,
                id="profile-1",
            ),
        }
    )
    try:
        coord = VideoGenerationCoordinator(user_id="u-db", db=db)
        assert coord._config["api_mode"] == "vertex_ai"
        assert coord._config["vertex_ai_project_id"] == "proj-db"
        assert coord._config["vertex_ai_location"] == "us-east1"
        # decrypted, not ciphertext
        assert coord._config["vertex_ai_credentials_json"] == VERTEX_CREDENTIALS_JSON
        assert coord._config["gemini_api_key"] == "AIzaPlaintextKey"
    finally:
        _config_cache.clear_config_cache()


def test_load_config_db_exception_falls_back_to_env(monkeypatch):
    from app.services.gemini.coordinators import _config_cache

    _config_cache.clear_config_cache()
    monkeypatch.setenv("GOOGLE_API_KEY", "env-fallback-key")
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    class _ExplodingDB:
        def query(self, *a, **k):
            raise RuntimeError("db connection lost")

    coord = VideoGenerationCoordinator(user_id="u-db", db=_ExplodingDB())
    # falls back to environment-derived config
    assert coord._config["gemini_api_key"] == "env-fallback-key"
    assert coord._config["api_mode"] == "gemini_api"
    _config_cache.clear_config_cache()


# ========================================================================== #
# Coordinator: extension segment prompt construction (audio enabled)
# ========================================================================== #
def test_build_extension_segment_prompts_audio_enabled_uses_narration():
    coord = VideoGenerationCoordinator(api_key="k")
    prompts = coord._build_extension_segment_prompts(
        prompt="hair clip product video",
        request_kwargs={
            "seconds": 8,
            "generate_audio": True,
            "storyboard_segments": ["8-15s: ocean detail macro"],
        },
        extension_count=1,
    )
    assert len(prompts) == 1
    # audio-enabled path includes presenter narration guidance
    assert "presenter-style product narration" in prompts[0]
    assert "8-15s: ocean detail macro" in prompts[0]
    assert "extension segment 1 of 1" in prompts[0]


def test_build_extension_segment_prompts_empty_when_no_segments():
    coord = VideoGenerationCoordinator(api_key="k")
    prompts = coord._build_extension_segment_prompts(
        prompt="base",
        request_kwargs={"seconds": 8, "storyboard_segments": ["   ", ""]},
        extension_count=2,
    )
    assert prompts == []


# ========================================================================== #
# Coordinator: last-frame-bridge extension chain through generate_video
# ========================================================================== #
class _BridgeChainCoordinator(VideoGenerationCoordinator):
    """Drives the high-resolution last-frame-bridge extension chain."""

    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.prompts: List[str] = []
        self.requests: List[Dict[str, Any]] = []
        self.segment_payloads: List[Any] = []
        self.trim_seconds: Optional[float] = None

    async def _generate_single_video(self, prompt, model, request_kwargs, *, selected_api_mode=None):
        self.prompts.append(prompt)
        self.requests.append(dict(request_kwargs))
        index = len(self.requests) - 1
        return {
            "url": f"data:video/mp4;base64,c2Vn{index}",
            "mime_type": "video/mp4",
            "filename": "veo-3.1-generate-preview-4k.mp4",
            "duration_seconds": 8,
            "job_id": f"job-{index}",
            "model": model,
        }

    async def _download_result_video_bytes(self, result):
        return f"video-{result['job_id']}".encode("utf-8"), "video/mp4"

    async def _build_last_frame_source_image_from_video_bytes(self, video_bytes, mime_type):
        return {"url": "data:image/png;base64," + video_bytes.hex(), "mime_type": "image/png"}

    async def _concatenate_video_segments(self, segments, *, continuation_trim_seconds):
        self.segment_payloads = list(segments)
        self.trim_seconds = continuation_trim_seconds
        return b"joined-bridge-video"


@pytest.mark.asyncio
async def test_generate_video_4k_bridge_chain_joins_segments():
    coord = _BridgeChainCoordinator()

    result = await coord.generate_video(
        "a continuous 4k product video",
        "veo-3.1-generate-preview",
        resolution="4k",
        aspect_ratio="16:9",
        seconds=8,
        video_extension_count=2,
    )

    # base + 2 extension segments
    assert len(coord.requests) == 3
    assert "source_image" in coord.requests[1]
    assert "source_image" in coord.requests[2]
    assert len(coord.segment_payloads) == 3
    assert coord.trim_seconds == 1.0
    assert result["continuation_strategy"] == "last_frame_bridge_chain"
    assert result["video_extension_count"] == 2
    assert result["segment_count"] == 3
    # base64-joined output replaces provider asset refs
    assert "provider_file_name" not in result
    assert result["url"].startswith("data:video/mp4;base64,")
