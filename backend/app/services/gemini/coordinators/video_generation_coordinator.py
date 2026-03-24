"""
Coordinator for selecting Gemini API or Vertex AI Veo video generation.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..base.video_common import (
    VEO31_EXTENSION_OUTPUT_ADDED_SECONDS,
    normalize_gemini_file_name,
    normalize_model,
)
from ..base.video_storyboard import (
    build_storyboard_prompt,
    build_subtitle_artifacts,
    estimate_storyboard_total_duration,
    normalize_generate_audio,
    normalize_person_generation,
    normalize_storyboard_shot_seconds,
    normalize_subtitle_language,
    normalize_subtitle_mode,
)
from ..client_pool import get_client_pool
from ...common.google_model_catalog import VEO_VIDEO_MODELS
from ..geminiapi.video_generation_service import GeminiAPIVideoGenerationService
from ..vertexai.video_generation_service import VertexAIVideoGenerationService

logger = logging.getLogger(__name__)

_LOCAL_ENHANCE_PROMPT_FALLBACK_MODEL = "gemini-2.5-pro"
_LOCAL_ENHANCE_MODEL_BLOCKLIST = ("veo", "imagen", "tts", "embedding", "transcribe")


class VideoGenerationCoordinator:
    """
    Mirrors the existing GEN-mode routing pattern:
    - load user VertexAIConfig if present
    - choose gemini_api or vertex_ai
    - lazily instantiate the matching video service
    """

    def __init__(
        self,
        *,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        api_key: Optional[str] = None,
        http_options: Any = None,
    ) -> None:
        self._user_id = user_id
        self._db = db
        self._provided_api_key = api_key
        self._http_options = http_options
        self._config = self._load_config()
        self._service_cache: Dict[str, Any] = {}

    def _has_gemini_api_key(self) -> bool:
        return bool(str(self._config.get("gemini_api_key") or self._provided_api_key or "").strip())

    def _normalize_model_name(self, model: Optional[str]) -> str:
        try:
            return normalize_model(model).lower()
        except Exception:
            return str(model or "").strip().split("/")[-1].lower()

    def _request_has_source_video(self, kwargs: Dict[str, Any]) -> bool:
        source_value = self._extract_source_video_value(kwargs)
        if isinstance(source_value, str):
            return bool(source_value.strip())
        if isinstance(source_value, dict):
            return bool(source_value)
        return False

    def _normalize_video_extension_count(self, kwargs: Dict[str, Any]) -> int:
        raw_value = kwargs.get("video_extension_count")
        if raw_value is None:
            raw_value = kwargs.get("videoExtensionCount")
        if raw_value is None:
            return 0
        try:
            candidate = int(str(raw_value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported Google video extension count: {raw_value}") from exc
        if candidate < 0:
            raise ValueError(f"Unsupported Google video extension count: {raw_value}")
        return candidate

    def _normalized_storyboard_options(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        subtitle_mode = normalize_subtitle_mode(kwargs.get("subtitle_mode") or kwargs.get("subtitleMode"))
        subtitle_language = normalize_subtitle_language(
            kwargs.get("subtitle_language") or kwargs.get("subtitleLanguage")
        )
        return {
            "shot_seconds": normalize_storyboard_shot_seconds(
                kwargs.get("storyboard_shot_seconds") or kwargs.get("storyboardShotSeconds")
            ),
            "storyboard_prompt": str(
                kwargs.get("storyboard_prompt") or kwargs.get("storyboardPrompt") or ""
            ).strip() or None,
            "subtitle_mode": subtitle_mode,
            "subtitle_language": subtitle_language,
            "subtitle_script": str(kwargs.get("subtitle_script") or kwargs.get("subtitleScript") or "").strip() or None,
            "tracked_feature": str(kwargs.get("tracked_feature") or kwargs.get("trackedFeature") or "").strip() or None,
            "tracking_overlay_text": str(
                kwargs.get("tracking_overlay_text") or kwargs.get("trackingOverlayText") or ""
            ).strip() or None,
            "generate_audio": normalize_generate_audio(kwargs.get("generate_audio") or kwargs.get("generateAudio")),
            "person_generation": normalize_person_generation(
                kwargs.get("person_generation") or kwargs.get("personGeneration")
            ),
        }

    def _build_storyboard_prompt(
        self,
        *,
        prompt: str,
        request_kwargs: Dict[str, Any],
        extension_count: int,
    ) -> str:
        storyboard = self._normalized_storyboard_options(request_kwargs)
        total_duration_seconds = estimate_storyboard_total_duration(
            base_duration_seconds=int(str(request_kwargs.get("seconds") or request_kwargs.get("duration_seconds") or 8)),
            extension_count=extension_count,
            extension_added_seconds=VEO31_EXTENSION_OUTPUT_ADDED_SECONDS,
        )
        return build_storyboard_prompt(
            prompt=prompt,
            total_duration_seconds=total_duration_seconds,
            shot_duration_seconds=storyboard["shot_seconds"],
            storyboard_prompt=storyboard["storyboard_prompt"],
            generate_audio=storyboard["generate_audio"],
            subtitle_script=storyboard["subtitle_script"],
            tracked_feature=storyboard["tracked_feature"],
            tracking_overlay_text=storyboard["tracking_overlay_text"],
        )

    def _resolve_local_enhance_prompt_model(self, model_hint: Optional[str]) -> str:
        candidate = str(model_hint or "").strip()
        lowered = candidate.lower()
        if candidate and "gemini" in lowered and not any(token in lowered for token in _LOCAL_ENHANCE_MODEL_BLOCKLIST):
            return candidate
        return _LOCAL_ENHANCE_PROMPT_FALLBACK_MODEL

    async def _enhance_prompt_locally(
        self,
        *,
        prompt: str,
        model_hint: Optional[str] = None,
    ) -> Optional[str]:
        api_key = str(self._config.get("gemini_api_key") or self._provided_api_key or "").strip()
        if not api_key:
            return None

        text_model = self._resolve_local_enhance_prompt_model(model_hint)
        system_prompt = (
            "You are a Veo prompt enhancer. Rewrite the request into a cinematic, production-ready video prompt. "
            "Preserve all explicit timing, shot structure, product facts, subtitles, tracking instructions, continuity constraints, "
            "and required scene transitions. Return only the final enhanced prompt."
        )
        user_prompt = (
            "Rewrite this video-generation prompt so it is more visually specific, direct, and generation-ready while keeping every "
            "hard constraint intact:\n\n"
            f"{prompt}"
        )
        try:
            pool = get_client_pool()
            pooled_client = pool.get_client(
                api_key=api_key,
                vertexai=False,
                http_options=self._http_options,
            )
            client = pooled_client
            response = client.models.generate_content(
                model=text_model,
                contents=f"{system_prompt}\n\n{user_prompt}",
            )
            enhanced = str(getattr(response, "text", "") or "").strip()
            if enhanced:
                logger.info(
                    "[VideoGenerationCoordinator] Generated local enhanced video prompt with model=%s (len=%s)",
                    text_model,
                    len(enhanced),
                )
                return enhanced
        except Exception as exc:
            logger.warning(
                "[VideoGenerationCoordinator] Local video prompt enhancement failed; falling back to storyboard prompt: %s",
                exc,
            )
        return None

    async def _prepare_prompt_for_runtime(
        self,
        *,
        prompt: str,
        model: str,
        request_kwargs: Dict[str, Any],
        extension_count: int,
        selected_api_mode: str,
    ) -> Dict[str, Optional[str]]:
        storyboard_prompt = self._build_storyboard_prompt(
            prompt=prompt,
            request_kwargs=request_kwargs,
            extension_count=extension_count,
        )
        enhance_requested = bool(request_kwargs.get("enhance_prompt") or request_kwargs.get("enhancePrompt"))
        enhanced_prompt: Optional[str] = None

        if selected_api_mode == "gemini_api":
            request_kwargs.pop("enhance_prompt", None)
            request_kwargs.pop("enhancePrompt", None)
            if enhance_requested:
                enhanced_prompt = await self._enhance_prompt_locally(
                    prompt=storyboard_prompt,
                    model_hint=request_kwargs.get("enhance_prompt_model") or request_kwargs.get("enhancePromptModel"),
                )

        return {
            "storyboard_prompt": storyboard_prompt,
            "effective_prompt": enhanced_prompt or storyboard_prompt,
            "enhanced_prompt": enhanced_prompt,
        }

    def _apply_storyboard_metadata(
        self,
        result: Dict[str, Any],
        *,
        request_kwargs: Dict[str, Any],
        extension_count: int,
    ) -> Dict[str, Any]:
        storyboard = self._normalized_storyboard_options(request_kwargs)
        total_duration_seconds = int(
            result.get("total_duration_seconds")
            or result.get("duration_seconds")
            or request_kwargs.get("seconds")
            or request_kwargs.get("duration_seconds")
            or 8
        )
        filename = str(result.get("filename") or "generated-video.mp4")
        filename_stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        subtitle_artifacts = build_subtitle_artifacts(
            prompt=str(result.get("enhanced_prompt") or result.get("prompt") or ""),
            total_duration_seconds=total_duration_seconds,
            shot_duration_seconds=storyboard["shot_seconds"],
            subtitle_mode=storyboard["subtitle_mode"],
            subtitle_language=storyboard["subtitle_language"],
            subtitle_script=storyboard["subtitle_script"],
            tracked_feature=storyboard["tracked_feature"],
            tracking_overlay_text=storyboard["tracking_overlay_text"],
            filename_stem=filename_stem,
        )
        result["storyboard_shot_seconds"] = storyboard["shot_seconds"]
        result["subtitle_mode"] = storyboard["subtitle_mode"]
        result["subtitle_language"] = storyboard["subtitle_language"]
        result["tracked_feature"] = storyboard["tracked_feature"]
        result["tracking_overlay_text"] = storyboard["tracking_overlay_text"]
        result["generate_audio"] = storyboard["generate_audio"]
        if storyboard["person_generation"]:
            result["person_generation"] = storyboard["person_generation"].lower()
        if subtitle_artifacts:
            result["sidecar_files"] = subtitle_artifacts
            result["subtitle_attachment_formats"] = [artifact["format"] for artifact in subtitle_artifacts]
        if extension_count > 0:
            result["video_extension_count"] = extension_count
        return result

    def _extract_source_video_value(self, kwargs: Dict[str, Any]) -> Any:
        for key in ("source_video", "sourceVideo", "continuation_video", "continuationVideo"):
            value = kwargs.get(key)
            if value is not None:
                return value
        return None

    def _source_video_requires_last_frame_bridge(self, kwargs: Dict[str, Any]) -> bool:
        source_value = self._extract_source_video_value(kwargs)
        if isinstance(source_value, str):
            candidate = source_value.strip().lower()
            if not candidate:
                return False
            return candidate.startswith("data:")
        if not isinstance(source_value, dict):
            return False

        raw_source = source_value.get("raw", source_value)
        if isinstance(raw_source, str):
            candidate = raw_source.strip().lower()
            return bool(candidate) and candidate.startswith("data:")

        for key in ("url", "videoUrl", "video_url", "raw_url", "rawUrl", "temp_url", "tempUrl"):
            value = raw_source.get(key) if isinstance(raw_source, dict) else None
            if isinstance(value, str) and value.strip():
                return value.strip().lower().startswith("data:")
        return False

    def _request_uses_last_frame_bridge(self, kwargs: Dict[str, Any]) -> bool:
        for key in ("use_last_frame_bridge", "continue_from_last_frame", "continueFromLastFrame"):
            value = kwargs.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value != 0
            if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}:
                return True
        return False

    def _request_has_video_mask(self, kwargs: Dict[str, Any]) -> bool:
        for key in ("video_mask_image", "videoMaskImage", "mask_image", "maskImage"):
            value = kwargs.get(key)
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, dict) and value:
                return True
        return False

    def _extract_source_video_uri(self, kwargs: Dict[str, Any]) -> str:
        source_value = self._extract_source_video_value(kwargs)
        if isinstance(source_value, str):
            return source_value.strip()
        if not isinstance(source_value, dict):
            return ""

        raw_source = source_value.get("raw", source_value)
        if isinstance(raw_source, str):
            return raw_source.strip()
        if not isinstance(raw_source, dict):
            return ""

        for key in (
            "provider_file_uri",
            "providerFileUri",
            "gcs_uri",
            "gcsUri",
            "file_uri",
            "fileUri",
            "uri",
            "url",
            "videoUrl",
            "video_url",
            "raw_url",
            "rawUrl",
            "temp_url",
            "tempUrl",
        ):
            value = raw_source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _build_source_video_from_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        provider_file_uri = str(
            result.get("provider_file_uri")
            or result.get("providerFileUri")
            or ""
        ).strip()
        provider_file_name = str(
            result.get("provider_file_name")
            or result.get("providerFileName")
            or ""
        ).strip()
        gcs_uri = str(result.get("gcs_uri") or result.get("gcsUri") or "").strip()
        file_uri = str(result.get("file_uri") or result.get("fileUri") or "").strip()
        url = str(result.get("url") or "").strip()
        mime_type = str(result.get("mime_type") or result.get("mimeType") or "video/mp4").strip() or "video/mp4"

        payload: Dict[str, Any] = {"mime_type": mime_type}
        if provider_file_name:
            payload["provider_file_name"] = provider_file_name
        if provider_file_uri:
            payload["provider_file_uri"] = provider_file_uri
        if gcs_uri:
            payload["gcs_uri"] = gcs_uri
        if file_uri:
            payload["file_uri"] = file_uri
        if url and not url.startswith("data:"):
            payload["url"] = url

        if len(payload) > 1:
            return payload
        if url:
            return {"url": url, "mime_type": mime_type}
        return None

    def _build_continuation_kwargs(self, base_kwargs: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        next_source_video = self._build_source_video_from_result(result)
        if not next_source_video:
            raise ValueError("Google video extension requires a provider-backed video asset from the previous generation result.")

        next_kwargs = dict(base_kwargs)
        next_kwargs["source_video"] = next_source_video
        next_kwargs.pop("sourceVideo", None)
        next_kwargs.pop("continuation_video", None)
        next_kwargs.pop("continuationVideo", None)
        next_kwargs.pop("source_image", None)
        next_kwargs.pop("sourceImage", None)
        next_kwargs.pop("start_frame_image", None)
        next_kwargs.pop("startFrameImage", None)
        next_kwargs.pop("last_frame_image", None)
        next_kwargs.pop("lastFrameImage", None)
        next_kwargs.pop("reference_images", None)
        next_kwargs.pop("video_mask_image", None)
        next_kwargs.pop("videoMaskImage", None)
        next_kwargs.pop("mask_image", None)
        next_kwargs.pop("maskImage", None)
        next_kwargs.pop("use_last_frame_bridge", None)
        next_kwargs.pop("continue_from_last_frame", None)
        next_kwargs.pop("continueFromLastFrame", None)
        next_kwargs.pop("video_extension_count", None)
        next_kwargs.pop("videoExtensionCount", None)
        return next_kwargs

    def _source_video_is_vertex_native(self, kwargs: Dict[str, Any]) -> bool:
        uri = self._extract_source_video_uri(kwargs)
        return uri.startswith("gs://")

    def _source_video_is_gemini_native(self, kwargs: Dict[str, Any]) -> bool:
        uri = self._extract_source_video_uri(kwargs)
        normalized = uri.lower()
        return bool(uri) and (
            normalized.startswith("files/")
            or normalized.startswith("https://generativelanguage.googleapis.com/")
            or (normalized.startswith("https://") and "/files/" in normalized)
        )

    def _vertex_runtime_ready(self) -> bool:
        return bool(
            str(self._config.get("vertex_ai_project_id") or "").strip()
            and str(self._config.get("vertex_ai_credentials_json") or "").strip()
        )

    def _vertex_supports_video_extension(self, model: Optional[str]) -> bool:
        normalized_model = self._normalize_model_name(model)
        return normalized_model in {item.lower() for item in VEO_VIDEO_MODELS}

    def _gemini_api_supports_video_extension(self, model: Optional[str]) -> bool:
        normalized_model = self._normalize_model_name(model)
        return normalized_model in {
            "veo-3.0-generate-preview",
            "veo-3.0-fast-generate-preview",
            "veo-3.0-generate-001",
            "veo-3.0-fast-generate-001",
            "veo-3.1-generate-preview",
            "veo-3.1-fast-generate-preview",
            "veo-3.1-generate-001",
            "veo-3.1-fast-generate-001",
        }

    def _select_api_mode_for_request(self, model: Optional[str], kwargs: Dict[str, Any]) -> str:
        configured_mode = str(self._config.get("api_mode") or "gemini_api").strip().lower()
        if self._request_has_video_mask(kwargs) and self._vertex_runtime_ready():
            if configured_mode != "vertex_ai":
                logger.info(
                    "[VideoGenerationCoordinator] Routing Google video edit to Vertex AI because mask editing requires Vertex runtime."
                )
            return "vertex_ai"
        if self._request_has_source_video(kwargs) and self._source_video_requires_last_frame_bridge(kwargs):
            kwargs["use_last_frame_bridge"] = True
            logger.info(
                "[VideoGenerationCoordinator] Falling back to last-frame bridge because the source video is not in an SDK-native URI form."
            )
            return configured_mode

        if not self._request_has_source_video(kwargs) or self._request_uses_last_frame_bridge(kwargs):
            return configured_mode

        source_is_vertex_native = self._source_video_is_vertex_native(kwargs)
        source_is_gemini_native = self._source_video_is_gemini_native(kwargs)
        vertex_supports_extension = self._vertex_supports_video_extension(model)
        gemini_supports_extension = self._gemini_api_supports_video_extension(model)

        if source_is_vertex_native:
            if vertex_supports_extension and self._vertex_runtime_ready():
                if configured_mode != "vertex_ai":
                    logger.info(
                        "[VideoGenerationCoordinator] Routing Google video continuation to Vertex AI because source video is a gs:// asset."
                    )
                return "vertex_ai"
            kwargs["use_last_frame_bridge"] = True
            logger.info(
                "[VideoGenerationCoordinator] Falling back to last-frame bridge because source video is a gs:// asset but model=%s/config cannot use Vertex video extension.",
                model,
            )
            return configured_mode

        if source_is_gemini_native:
            if gemini_supports_extension and self._has_gemini_api_key():
                if configured_mode != "gemini_api":
                    logger.info(
                        "[VideoGenerationCoordinator] Routing Google video continuation to Gemini API because source video is a Gemini Files asset."
                    )
                return "gemini_api"
            kwargs["use_last_frame_bridge"] = True
            logger.info(
                "[VideoGenerationCoordinator] Falling back to last-frame bridge because source video is a Gemini Files asset but Gemini API continuation is unavailable for model=%s.",
                model,
            )
            return configured_mode

        if configured_mode == "vertex_ai":
            if vertex_supports_extension:
                return configured_mode
            if self._has_gemini_api_key() and gemini_supports_extension:
                logger.info(
                    "[VideoGenerationCoordinator] Routing Google video continuation to Gemini API because model=%s is not Vertex video-extension capable.",
                    model,
                )
                return "gemini_api"
            kwargs["use_last_frame_bridge"] = True
            logger.info(
                "[VideoGenerationCoordinator] Falling back to last-frame bridge because model=%s cannot use direct video extension on the configured runtime.",
                model,
            )
            return configured_mode

        if configured_mode == "gemini_api":
            if gemini_supports_extension:
                return configured_mode
            if vertex_supports_extension and self._vertex_runtime_ready():
                logger.info(
                    "[VideoGenerationCoordinator] Routing Google video continuation to Vertex AI because model=%s requires Vertex video-extension handling.",
                    model,
                )
                return "vertex_ai"
            kwargs["use_last_frame_bridge"] = True
            logger.info(
                "[VideoGenerationCoordinator] Falling back to last-frame bridge because model=%s cannot use direct video extension on Gemini API.",
                model,
            )
        return configured_mode

    def _should_runtime_fallback_to_gemini_api(self, exc: Exception) -> bool:
        if not self._has_gemini_api_key():
            return False
        message = str(exc or "").lower()
        markers = (
            "service agents are being provisioned",
            "cloud storage file provided",
            "output storage uri is required",
        )
        return any(marker in message for marker in markers)

    def _should_retry_with_last_frame_bridge(self, exc: Exception) -> bool:
        message = str(exc or "").lower()
        markers = (
            "internal error",
            "did not return any generated videos",
            "missing the generated video payload",
            "temporarily unavailable",
        )
        return any(marker in message for marker in markers)

    def _should_retry_transient_generation_error(self, exc: Exception) -> bool:
        message = str(exc or "").lower()
        markers = (
            "code': 13",
            '"code": 13',
            "internal server issue",
            "please try again in a few minutes",
            "503 service unavailable",
            "service unavailable",
            "temporarily unavailable",
            "deadline exceeded",
            "resource exhausted",
            "try again later",
        )
        return any(marker in message for marker in markers)

    def _load_config(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {}

        if self._user_id and self._db:
            try:
                from ....models.db_models import ConfigProfile, UserSettings, VertexAIConfig
                from ....core.encryption import decrypt_data, is_encrypted

                vertex_config = self._db.query(VertexAIConfig).filter(
                    VertexAIConfig.user_id == self._user_id
                ).first()
                if vertex_config:
                    config["api_mode"] = vertex_config.api_mode or "gemini_api"
                    config["vertex_ai_project_id"] = vertex_config.vertex_ai_project_id
                    config["vertex_ai_location"] = vertex_config.vertex_ai_location or "us-central1"
                    raw_credentials = vertex_config.vertex_ai_credentials_json
                    if raw_credentials:
                        config["vertex_ai_credentials_json"] = (
                            decrypt_data(raw_credentials) if is_encrypted(raw_credentials) else raw_credentials
                        )

                if self._provided_api_key:
                    config["gemini_api_key"] = self._provided_api_key
                else:
                    active_profile_id = None
                    settings_row = self._db.query(UserSettings).filter(
                        UserSettings.user_id == self._user_id
                    ).first()
                    if settings_row and getattr(settings_row, "active_profile_id", None):
                        active_profile_id = str(settings_row.active_profile_id or "").strip() or None

                    google_profile = None
                    if active_profile_id:
                        active_google_profile = self._db.query(ConfigProfile).filter(
                            ConfigProfile.user_id == self._user_id,
                            ConfigProfile.id == active_profile_id,
                        ).first()
                        if active_google_profile:
                            provider_id = str(active_google_profile.provider_id or "").strip().lower()
                            if provider_id.startswith("google"):
                                google_profile = active_google_profile

                    if google_profile is None:
                        google_profile = self._db.query(ConfigProfile).filter(
                            ConfigProfile.user_id == self._user_id,
                            ConfigProfile.provider_id.like("google%"),
                        ).order_by(ConfigProfile.updated_at.desc()).first()
                    if google_profile and google_profile.api_key:
                        key = google_profile.api_key
                        if is_encrypted(key):
                            key = decrypt_data(key, silent=True)
                        config["gemini_api_key"] = key

                if config:
                    return config
            except Exception as exc:
                logger.warning("[VideoGenerationCoordinator] Failed to load DB config, falling back to env: %s", exc)

        config["api_mode"] = "vertex_ai" if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true" else "gemini_api"
        config["gemini_api_key"] = self._provided_api_key or os.getenv("GOOGLE_API_KEY")
        config["vertex_ai_project_id"] = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
        config["vertex_ai_location"] = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GCP_LOCATION", "us-central1")
        config["vertex_ai_credentials_json"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        return config

    def _create_vertex_service(self) -> VertexAIVideoGenerationService:
        project_id = self._config.get("vertex_ai_project_id")
        location = self._config.get("vertex_ai_location") or "us-central1"
        credentials_json = self._config.get("vertex_ai_credentials_json")
        if not project_id or not credentials_json:
            raise ValueError("Vertex AI video generation requires project_id and credentials_json.")
        return VertexAIVideoGenerationService(
            project_id=project_id,
            location=location,
            credentials_json=credentials_json,
            http_options=self._http_options,
        )

    def _create_gemini_api_service(self) -> GeminiAPIVideoGenerationService:
        api_key = self._config.get("gemini_api_key") or self._provided_api_key
        if not api_key:
            raise ValueError("Gemini API video generation requires a Google API key.")
        return GeminiAPIVideoGenerationService(
            api_key=api_key,
            http_options=self._http_options,
        )

    def get_service(self, api_mode_override: Optional[str] = None) -> Any:
        api_mode = str(api_mode_override or self._config.get("api_mode") or "gemini_api").strip().lower()
        if api_mode in self._service_cache:
            return self._service_cache[api_mode]

        try:
            if api_mode == "vertex_ai":
                service = self._create_vertex_service()
            else:
                service = self._create_gemini_api_service()
            self._service_cache[api_mode] = service
            return service
        except Exception as exc:
            if api_mode == "vertex_ai":
                logger.warning("[VideoGenerationCoordinator] Vertex AI video init failed, falling back to Gemini API: %s", exc)
                service = self._create_gemini_api_service()
                self._service_cache["gemini_api"] = service
                return service
            raise

    async def _wait_for_gemini_video_asset_ready(self, result: Dict[str, Any]) -> None:
        if not isinstance(result, dict):
            return

        coordinator_api_mode = str(result.get("coordinator_api_mode") or "").strip().lower()
        provider_platform = str(result.get("provider_platform") or "").strip().lower()
        if coordinator_api_mode != "gemini_api" and provider_platform != "developer_api":
            return

        provider_file_name = str(
            result.get("provider_file_name")
            or result.get("providerFileName")
            or ""
        ).strip()
        provider_file_uri = str(
            result.get("provider_file_uri")
            or result.get("providerFileUri")
            or ""
        ).strip()
        if not provider_file_name and not provider_file_uri:
            return

        service = self.get_service(api_mode_override="gemini_api")
        wait_until_ready = getattr(service, "wait_until_video_asset_processed", None)
        if wait_until_ready is None or not callable(wait_until_ready):
            return
        await wait_until_ready(
            provider_file_name=provider_file_name or None,
            provider_file_uri=provider_file_uri or None,
        )

    async def _generate_single_video(
        self,
        prompt: str,
        model: str,
        request_kwargs: Dict[str, Any],
        *,
        selected_api_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        selected_api_mode = selected_api_mode or self._select_api_mode_for_request(model, request_kwargs)
        service = self.get_service(api_mode_override=selected_api_mode)
        transient_attempt = 0
        while True:
            last_error: Optional[Exception] = None
            try:
                result = await service.generate_video(prompt=prompt, model=model, **request_kwargs)
                break
            except Exception as exc:
                last_error = exc
                if transient_attempt < 1 and self._should_retry_transient_generation_error(exc):
                    transient_attempt += 1
                    logger.warning(
                        "[VideoGenerationCoordinator] Retrying transient Google video generation failure (%s/1): %s",
                        transient_attempt,
                        exc,
                    )
                    await asyncio.sleep(2.0)
                    continue
            if (
                selected_api_mode == "vertex_ai"
                and self._request_has_source_video(request_kwargs)
                and not self._request_uses_last_frame_bridge(request_kwargs)
                and self._source_video_is_vertex_native(request_kwargs)
                and last_error is not None
                and self._should_retry_with_last_frame_bridge(last_error)
            ):
                logger.warning(
                    "[VideoGenerationCoordinator] Vertex video extension failed, retrying via last-frame bridge: %s",
                    last_error,
                )
                retry_kwargs = dict(request_kwargs)
                retry_kwargs["use_last_frame_bridge"] = True
                result = await service.generate_video(prompt=prompt, model=model, **retry_kwargs)
                if isinstance(result, dict):
                    result.setdefault("service_fallback", "vertex_video_extension_to_last_frame_bridge")
                    result.setdefault("coordinator_api_mode", selected_api_mode)
                return result
            if (
                selected_api_mode == "vertex_ai"
                and last_error is not None
                and self._should_runtime_fallback_to_gemini_api(last_error)
            ):
                logger.warning(
                    "[VideoGenerationCoordinator] Vertex runtime failed, retrying Google video generation via Gemini API: %s",
                    last_error,
                )
                service = self.get_service(api_mode_override="gemini_api")
                retry_kwargs = dict(request_kwargs)
                retry_kwargs.pop("use_last_frame_bridge", None)
                result = await service.generate_video(prompt=prompt, model=model, **retry_kwargs)
                if isinstance(result, dict):
                    result.setdefault("service_fallback", "vertex_to_gemini_api")
                    result.setdefault("coordinator_api_mode", "gemini_api")
                return result
            if last_error is not None:
                raise last_error
            raise RuntimeError("Google video generation failed without a captured exception.")

        if isinstance(result, dict):
            result.setdefault("coordinator_api_mode", selected_api_mode)
        return result

    async def generate_video(self, prompt: str, model: str, **kwargs) -> Dict[str, Any]:
        request_kwargs = dict(kwargs)
        extension_count = self._normalize_video_extension_count(request_kwargs)
        selected_api_mode = self._select_api_mode_for_request(model, request_kwargs)
        prepared_prompt_payload = await self._prepare_prompt_for_runtime(
            prompt=prompt,
            model=model,
            request_kwargs=request_kwargs,
            extension_count=extension_count,
            selected_api_mode=selected_api_mode,
        )
        prepared_prompt = str(prepared_prompt_payload.get("effective_prompt") or prompt)
        enhanced_prompt = prepared_prompt_payload.get("enhanced_prompt")
        storyboard_prompt = str(prepared_prompt_payload.get("storyboard_prompt") or prepared_prompt)
        result = await self._generate_single_video(
            prepared_prompt,
            model,
            request_kwargs,
            selected_api_mode=selected_api_mode,
        )
        if extension_count <= 0:
            if isinstance(result, dict):
                result.setdefault("prompt", prompt)
                result.setdefault("storyboard_prompt", storyboard_prompt)
                if enhanced_prompt:
                    result["enhanced_prompt"] = enhanced_prompt
                    result.setdefault("prompt_enhancement_strategy", "local_llm")
                return self._apply_storyboard_metadata(
                    result,
                    request_kwargs=request_kwargs,
                    extension_count=extension_count,
                )
            return result

        current_result = result
        generated_job_ids = [result.get("job_id")] if isinstance(result, dict) and result.get("job_id") else []
        base_duration_seconds = int(result.get("duration_seconds") or request_kwargs.get("seconds") or 0)

        for _ in range(extension_count):
            if isinstance(current_result, dict):
                await self._wait_for_gemini_video_asset_ready(current_result)
            continuation_kwargs = self._build_continuation_kwargs(request_kwargs, current_result)
            current_result = await self._generate_single_video(
                prepared_prompt,
                model,
                continuation_kwargs,
                selected_api_mode=selected_api_mode,
            )
            job_id = current_result.get("job_id") if isinstance(current_result, dict) else None
            if job_id:
                generated_job_ids.append(job_id)

        if isinstance(current_result, dict):
            current_result["video_extension_count"] = extension_count
            current_result["video_extension_applied"] = extension_count
            if base_duration_seconds > 0:
                current_result["total_duration_seconds"] = (
                    base_duration_seconds + extension_count * VEO31_EXTENSION_OUTPUT_ADDED_SECONDS
                )
            if generated_job_ids:
                current_result["extension_job_ids"] = generated_job_ids
            current_result["continuation_strategy"] = "video_extension_chain"
            current_result.setdefault("prompt", prompt)
            current_result.setdefault("storyboard_prompt", storyboard_prompt)
            if enhanced_prompt:
                current_result["enhanced_prompt"] = enhanced_prompt
                current_result.setdefault("prompt_enhancement_strategy", "local_llm")
            return self._apply_storyboard_metadata(
                current_result,
                request_kwargs=request_kwargs,
                extension_count=extension_count,
            )
        return current_result

    async def delete_video(self, **kwargs) -> Dict[str, Any]:
        provider_file_uri = str(kwargs.get("provider_file_uri") or kwargs.get("providerFileUri") or "").strip()
        gcs_uri = str(kwargs.get("gcs_uri") or kwargs.get("gcsUri") or "").strip()
        provider_file_name = str(kwargs.get("provider_file_name") or kwargs.get("providerFileName") or "").strip()
        if not provider_file_name:
            provider_file_name = normalize_gemini_file_name(provider_file_uri) or ""
        if not gcs_uri and provider_file_uri.startswith("gs://"):
            gcs_uri = provider_file_uri
        request_kwargs = dict(kwargs)

        if provider_file_name:
            service = self.get_service(api_mode_override="gemini_api")
            delete_video = getattr(service, "delete_video", None)
            if delete_video is None or not callable(delete_video):
                raise ValueError("Gemini API video deletion runtime is unavailable.")
            request_kwargs.pop("provider_file_name", None)
            request_kwargs.pop("providerFileName", None)
            result = await delete_video(provider_file_name=provider_file_name, **request_kwargs)
            if isinstance(result, dict):
                result.setdefault("coordinator_api_mode", "gemini_api")
            return result

        if gcs_uri.startswith("gs://"):
            service = self.get_service(api_mode_override="vertex_ai")
            delete_video = getattr(service, "delete_video", None)
            if delete_video is None or not callable(delete_video):
                raise ValueError("Vertex AI video deletion runtime is unavailable.")
            request_kwargs.pop("gcs_uri", None)
            request_kwargs.pop("gcsUri", None)
            request_kwargs.pop("provider_file_uri", None)
            request_kwargs.pop("providerFileUri", None)
            result = await delete_video(gcs_uri=gcs_uri, **request_kwargs)
            if isinstance(result, dict):
                result.setdefault("coordinator_api_mode", "vertex_ai")
            return result

        raise ValueError("Google video deletion requires provider_file_name or gcs_uri/provider_file_uri.")

    async def download_video_asset(self, **kwargs) -> Dict[str, Any]:
        provider_file_uri = str(kwargs.get("provider_file_uri") or kwargs.get("providerFileUri") or "").strip()
        gcs_uri = str(kwargs.get("gcs_uri") or kwargs.get("gcsUri") or "").strip()
        provider_file_name = str(kwargs.get("provider_file_name") or kwargs.get("providerFileName") or "").strip()
        mime_type = str(kwargs.get("mime_type") or kwargs.get("mimeType") or "").strip() or "video/mp4"
        if not provider_file_name:
            provider_file_name = normalize_gemini_file_name(provider_file_uri) or ""
        if not gcs_uri and provider_file_uri.startswith("gs://"):
            gcs_uri = provider_file_uri
        request_kwargs = dict(kwargs)

        if provider_file_name:
            service = self.get_service(api_mode_override="gemini_api")
            download_video_asset = getattr(service, "download_video_asset", None)
            if download_video_asset is None or not callable(download_video_asset):
                raise ValueError("Gemini API video download runtime is unavailable.")
            request_kwargs.pop("provider_file_name", None)
            request_kwargs.pop("providerFileName", None)
            request_kwargs.pop("provider_file_uri", None)
            request_kwargs.pop("providerFileUri", None)
            request_kwargs.pop("mime_type", None)
            request_kwargs.pop("mimeType", None)
            result = await download_video_asset(
                provider_file_name=provider_file_name,
                provider_file_uri=provider_file_uri or provider_file_name,
                mime_type=mime_type,
                **request_kwargs,
            )
            if isinstance(result, dict):
                result.setdefault("coordinator_api_mode", "gemini_api")
            return result

        if gcs_uri.startswith("gs://"):
            service = self.get_service(api_mode_override="vertex_ai")
            download_video_asset = getattr(service, "download_video_asset", None)
            if download_video_asset is None or not callable(download_video_asset):
                raise ValueError("Vertex AI video download runtime is unavailable.")
            request_kwargs.pop("gcs_uri", None)
            request_kwargs.pop("gcsUri", None)
            request_kwargs.pop("provider_file_uri", None)
            request_kwargs.pop("providerFileUri", None)
            request_kwargs.pop("mime_type", None)
            request_kwargs.pop("mimeType", None)
            result = await download_video_asset(
                gcs_uri=gcs_uri,
                provider_file_uri=provider_file_uri or gcs_uri,
                mime_type=mime_type,
                **request_kwargs,
            )
            if isinstance(result, dict):
                result.setdefault("coordinator_api_mode", "vertex_ai")
            return result

        raise ValueError("Google video download requires provider_file_name or gcs_uri/provider_file_uri.")

    def get_current_api_mode(self) -> str:
        service = self.get_service()
        if isinstance(service, VertexAIVideoGenerationService):
            return "vertex_ai"
        return "gemini_api"
