"""
Gemini Developer API implementation for Veo video generation.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from ..base.video_common import (
    DEFAULT_ASPECT_RATIO,
    build_filename,
    build_resolution_map,
    extract_provider_video_asset_ref,
    extract_source_video_uri_ref,
    load_mask_image,
    load_reference_images,
    load_source_image,
    load_source_video,
    normalize_gemini_file_name,
    normalize_aspect_ratio,
    normalize_duration_seconds,
    normalize_model,
    normalize_video_mask_mode,
    normalize_resolution,
    normalize_video_extension_duration_seconds,
    to_data_url,
    validate_generation_constraints,
)
from ..base.video_frame_bridge import extract_last_frame_image
from ..base.video_storyboard import normalize_generate_audio, normalize_person_generation
from ..client_pool import get_client_pool

logger = logging.getLogger(__name__)

try:
    from google.genai import types as genai_types

    GENAI_AVAILABLE = True
except ImportError:
    genai_types = None
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")

DEFAULT_POLL_INTERVAL_SECONDS = 10.0
DEFAULT_POLL_TIMEOUT_SECONDS = 900.0
DEFAULT_FILE_READY_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_FILE_READY_TIMEOUT_SECONDS = 300.0


class GeminiAPIVideoGenerationService:
    """
    Veo video generation via the Gemini Developer API.

    Official flow:
    - `client.models.generate_videos(...)`
    - poll with `client.operations.get(...)`
    - download bytes with `client.files.download(...)`
    """

    def __init__(
        self,
        api_key: str,
        *,
        http_options: Any = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
        file_ready_poll_interval_seconds: float = DEFAULT_FILE_READY_POLL_INTERVAL_SECONDS,
        file_ready_timeout_seconds: float = DEFAULT_FILE_READY_TIMEOUT_SECONDS,
    ) -> None:
        if not GENAI_AVAILABLE:
            raise RuntimeError("google.genai is not installed. Install google-genai before using Veo.")

        self.api_key = api_key
        self.http_options = http_options
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.poll_timeout_seconds = float(poll_timeout_seconds)
        self.file_ready_poll_interval_seconds = float(file_ready_poll_interval_seconds)
        self.file_ready_timeout_seconds = float(file_ready_timeout_seconds)
        self._client = None

    def _ensure_initialized(self) -> None:
        if self._client is not None:
            return
        pool = get_client_pool()
        pooled_client = pool.get_client(
            api_key=self.api_key,
            vertexai=False,
            http_options=self.http_options,
        )
        self._client = pooled_client

    async def generate_video(
        self,
        prompt: str,
        model: str,
        **kwargs,
    ) -> Dict[str, Any]:
        self._ensure_initialized()

        normalized_model = normalize_model(model)
        aspect_ratio = normalize_aspect_ratio(kwargs.get("aspect_ratio") or kwargs.get("image_aspect_ratio"))
        resolution = normalize_resolution(kwargs.get("resolution") or kwargs.get("image_resolution"))
        duration_seconds = normalize_duration_seconds(kwargs.get("seconds"), kwargs.get("duration_seconds"))
        negative_prompt = str(kwargs.get("negative_prompt") or "").strip() or None
        enhance_prompt = kwargs.get("enhance_prompt")
        generate_audio = normalize_generate_audio(kwargs.get("generate_audio") or kwargs.get("generateAudio"))
        person_generation = normalize_person_generation(
            kwargs.get("person_generation") or kwargs.get("personGeneration")
        )
        seed = kwargs.get("seed")
        last_frame_bridge = bool(
            kwargs.get("use_last_frame_bridge")
            or kwargs.get("continue_from_last_frame")
            or kwargs.get("continueFromLastFrame")
        )
        raw_source_video = (
            kwargs.get("source_video")
            or kwargs.get("sourceVideo")
            or kwargs.get("continuation_video")
            or kwargs.get("continuationVideo")
        )
        source_video_uri = extract_source_video_uri_ref(raw_source_video)
        source_video = None if source_video_uri else await load_source_video(raw_source_video)
        explicit_source_image = await load_source_image(
            kwargs.get("source_image")
            or kwargs.get("sourceImage")
            or kwargs.get("start_frame_image")
            or kwargs.get("startFrameImage")
        )
        mask_image = await load_mask_image(
            kwargs.get("video_mask_image")
            or kwargs.get("videoMaskImage")
            or kwargs.get("mask_image")
            or kwargs.get("maskImage")
            or kwargs.get("reference_images")
        )
        video_mask_mode = normalize_video_mask_mode(
            kwargs.get("video_mask_mode")
            or kwargs.get("videoMaskMode")
            or kwargs.get("mask_mode")
            or kwargs.get("maskMode")
            or kwargs.get("edit_mode")
            or kwargs.get("editMode")
        )
        last_frame_image = await load_source_image(
            kwargs.get("last_frame_image")
            or kwargs.get("lastFrameImage")
        )

        loaded_references = await load_reference_images(kwargs.get("reference_images"))
        source_image = explicit_source_image
        if source_image is None and loaded_references:
            source_image = loaded_references[0]
            extra_reference_images = loaded_references[1:]
        else:
            extra_reference_images = loaded_references

        bridged_from_last_frame = False
        if source_video and last_frame_bridge:
            source_image = extract_last_frame_image(source_video)
            source_video = None
            bridged_from_last_frame = True

        if source_video and source_image:
            raise ValueError("Google video generation does not support source video and source image at the same time.")
        duration_seconds = normalize_video_extension_duration_seconds(
            duration_seconds,
            model=normalized_model,
            has_source_video=bool(source_video or source_video_uri),
        )
        validate_generation_constraints(
            model=normalized_model,
            api_mode="gemini_api",
            resolution=resolution,
            duration_seconds=duration_seconds,
            has_source_video=bool(source_video or source_video_uri),
            reference_image_count=len(extra_reference_images),
        )

        if source_video and extra_reference_images:
            raise ValueError(
                "Google video continuation does not support reference images in the same request."
            )
        if mask_image and not source_video:
            raise ValueError("Google video edit mask currently requires a source video.")
        if mask_image and not video_mask_mode:
            raise ValueError("Google video edit mask requires video_mask_mode/edit_mode.")
        if mask_image:
            raise ValueError("Google video edit mask currently requires Vertex AI with veo-2.0-generate-001.")

        source_payload = genai_types.GenerateVideosSource(prompt=prompt or None)
        if source_image:
            source_payload.image = genai_types.Image(
                image_bytes=source_image.image_bytes,
                mime_type=source_image.mime_type,
            )
        if source_video_uri:
            # Gemini Developer API video extension rejects `encoding` for Veo 3.1.
            # The python-genai SDK maps Video.mime_type -> encoding for mldev requests,
            # so URI-based continuation must omit mime_type here.
            source_payload.video = genai_types.Video(uri=source_video_uri.uri)
        elif source_video:
            source_payload.video = genai_types.Video(
                video_bytes=source_video.video_bytes,
                mime_type=source_video.mime_type,
            )

        config_kwargs: Dict[str, Any] = {
            "number_of_videos": 1,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        if not (source_video or source_video_uri):
            config_kwargs["duration_seconds"] = duration_seconds
        if negative_prompt:
            config_kwargs["negative_prompt"] = negative_prompt
        if enhance_prompt is not None and (bool(enhance_prompt) or not normalized_model.startswith("veo-3")):
            config_kwargs["enhance_prompt"] = bool(enhance_prompt)
        if generate_audio is not None:
            config_kwargs["generate_audio"] = bool(generate_audio)
        if person_generation:
            config_kwargs["person_generation"] = getattr(genai_types.PersonGeneration, person_generation, person_generation)
        if isinstance(seed, int) and seed >= 0:
            config_kwargs["seed"] = seed
        if last_frame_image:
            config_kwargs["last_frame"] = genai_types.Image(
                image_bytes=last_frame_image.image_bytes,
                mime_type=last_frame_image.mime_type,
            )
        if mask_image and video_mask_mode:
            config_kwargs["mask"] = genai_types.VideoGenerationMask(
                image=genai_types.Image(
                    image_bytes=mask_image.image_bytes,
                    mime_type=mask_image.mime_type,
                ),
                mask_mode=video_mask_mode,
            )
        if extra_reference_images:
            config_kwargs["reference_images"] = [
                genai_types.VideoGenerationReferenceImage(
                    image=genai_types.Image(
                        image_bytes=item.image_bytes,
                        mime_type=item.mime_type,
                    ),
                    reference_type=item.reference_type or "ASSET",
                )
                for item in extra_reference_images
            ]

        logger.info(
            "[GeminiAPIVideoGenerationService] Generating video: model=%s, aspect_ratio=%s, resolution=%s, duration=%ss, has_image=%s, has_video=%s, extra_refs=%s",
            normalized_model,
            aspect_ratio,
            resolution,
            duration_seconds,
            bool(source_image),
            bool(source_video or source_video_uri),
            len(extra_reference_images),
        )

        operation = await asyncio.to_thread(
            self._client.models.generate_videos,
            model=normalized_model,
            source=source_payload,
            config=genai_types.GenerateVideosConfig(**config_kwargs),
        )
        operation = await self._wait_for_operation(operation)
        response = getattr(operation, "result", None) or getattr(operation, "response", None)
        generated_video = self._extract_generated_video(response)
        asset_ref = extract_provider_video_asset_ref(getattr(generated_video, "video", None))
        mime_type = getattr(generated_video.video, "mime_type", None) or "video/mp4"
        resolved_asset_uri = asset_ref.provider_file_uri or asset_ref.provider_file_name or asset_ref.gcs_uri
        if resolved_asset_uri:
            url = resolved_asset_uri
        else:
            video_bytes = await self._download_video_bytes(generated_video)
            url = to_data_url(video_bytes, mime_type)

        return {
            "url": url,
            "mime_type": mime_type,
            "filename": build_filename(normalized_model, resolution, aspect_ratio),
            "duration_seconds": duration_seconds,
            "duration": duration_seconds,
            "video_size": build_resolution_map(resolution, aspect_ratio),
            "job_id": getattr(operation, "name", None),
            "model": normalized_model,
            "provider_platform": "developer_api",
            "continued_from_video": bool(source_video or source_video_uri),
            "continued_from_last_frame": bridged_from_last_frame,
            "video_mask_mode": video_mask_mode,
            "provider_file_name": asset_ref.provider_file_name,
            "provider_file_uri": asset_ref.provider_file_uri,
            "gcs_uri": asset_ref.gcs_uri,
            "generate_audio": generate_audio,
            "person_generation": person_generation.lower() if person_generation else None,
            "continuation_strategy": (
                "last_frame_bridge"
                if bridged_from_last_frame
                else ("video_extension" if (source_video or source_video_uri) else "none")
            ),
        }

    async def download_video_asset(
        self,
        *,
        provider_file_name: Optional[str] = None,
        provider_file_uri: Optional[str] = None,
        mime_type: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        self._ensure_initialized()
        normalized_name = normalize_gemini_file_name(provider_file_name or provider_file_uri)
        if not normalized_name:
            raise ValueError("Gemini Developer API video download requires provider_file_name/provider_file_uri (files/...).")

        resolved_mime_type = str(mime_type or "").strip() or "video/mp4"
        try:
            file_obj = await self._client.aio.files.get(name=normalized_name)
            file_mime_type = str(getattr(file_obj, "mime_type", None) or "").strip()
            if file_mime_type:
                resolved_mime_type = file_mime_type
        except Exception:
            file_obj = normalized_name

        data = await self._client.aio.files.download(file=file_obj)
        if isinstance(data, bytearray):
            binary = bytes(data)
        elif isinstance(data, bytes):
            binary = data
        else:
            raise RuntimeError("Gemini Developer API returned an unsupported video download payload.")

        return {
            "video_bytes": binary,
            "mime_type": resolved_mime_type,
            "provider_platform": "developer_api",
            "provider_file_name": normalized_name,
            "provider_file_uri": provider_file_uri or normalized_name,
        }

    async def delete_video(
        self,
        *,
        provider_file_name: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        self._ensure_initialized()
        normalized_name = str(provider_file_name or "").strip()
        if not normalized_name:
            raise ValueError("Gemini Developer API video deletion requires provider_file_name (files/...).")
        await self._client.aio.files.delete(name=normalized_name)
        return {
            "deleted": True,
            "provider_platform": "developer_api",
            "provider_file_name": normalized_name,
        }

    async def wait_until_video_asset_processed(
        self,
        *,
        provider_file_name: Optional[str] = None,
        provider_file_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_initialized()
        normalized_name = normalize_gemini_file_name(provider_file_name or provider_file_uri)
        if not normalized_name:
            raise ValueError("Gemini Developer API video readiness check requires provider_file_name/provider_file_uri (files/...).")

        loop = asyncio.get_running_loop()
        start = loop.time()
        last_state = "STATE_UNSPECIFIED"

        while True:
            file_obj = await self._client.aio.files.get(name=normalized_name)
            state = getattr(file_obj, "state", None)
            state_value = getattr(state, "value", state)
            normalized_state = str(state_value or "STATE_UNSPECIFIED").strip().upper()
            last_state = normalized_state

            if normalized_state == "ACTIVE":
                return {
                    "provider_file_name": normalized_name,
                    "provider_file_uri": getattr(file_obj, "uri", None) or provider_file_uri or normalized_name,
                    "state": normalized_state,
                }
            if normalized_state == "FAILED":
                error = getattr(file_obj, "error", None)
                raise RuntimeError(f"Gemini video asset processing failed for {normalized_name}: {error}")
            if loop.time() - start > self.file_ready_timeout_seconds:
                raise TimeoutError(
                    f"Timed out waiting for Gemini video asset {normalized_name} to become ACTIVE (last state={last_state})."
                )
            await asyncio.sleep(self.file_ready_poll_interval_seconds)

    async def _wait_for_operation(self, operation: Any) -> Any:
        start = asyncio.get_running_loop().time()
        current = operation
        while not getattr(current, "done", False):
            if asyncio.get_running_loop().time() - start > self.poll_timeout_seconds:
                raise TimeoutError("Timed out waiting for Gemini video generation to finish.")
            await asyncio.sleep(self.poll_interval_seconds)
            current = await asyncio.to_thread(self._client.operations.get, current)

        error = getattr(current, "error", None)
        if error:
            raise RuntimeError(f"Gemini video generation failed: {error}")
        return current

    def _extract_generated_video(self, response: Any) -> Any:
        if isinstance(response, dict):
            generated_videos: List[Any] = list(
                response.get("generated_videos")
                or response.get("generatedVideos")
                or response.get("videos")
                or []
            )
        else:
            generated_videos = list(
                getattr(response, "generated_videos", None)
                or getattr(response, "generatedVideos", None)
                or getattr(response, "videos", None)
                or []
            )
        if not generated_videos:
            raise RuntimeError("Gemini video generation did not return any generated videos.")
        generated = generated_videos[0]
        if isinstance(generated, dict) and generated.get("video") is not None:
            return SimpleNamespace(video=generated.get("video"))
        if isinstance(generated, dict) and any(
            key in generated for key in ("uri", "video_bytes", "videoBytes", "name")
        ):
            return SimpleNamespace(video=generated)
        if not getattr(generated, "video", None):
            raise RuntimeError("Gemini video generation response is missing the generated video payload.")
        return generated

    async def _download_video_bytes(self, generated_video: Any) -> bytes:
        video = generated_video.video
        if getattr(video, "video_bytes", None):
            return bytes(video.video_bytes)
        if isinstance(video, dict):
            raw_bytes = video.get("video_bytes") or video.get("videoBytes")
            if raw_bytes:
                return bytes(raw_bytes)
        data = await asyncio.to_thread(self._client.files.download, file=video)
        if getattr(video, "video_bytes", None):
            return bytes(video.video_bytes)
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, bytes):
            return data
        raise RuntimeError("Gemini Developer API returned an unsupported video download payload.")
