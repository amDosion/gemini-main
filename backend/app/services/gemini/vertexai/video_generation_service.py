"""
Vertex AI implementation for Veo video generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from ..base.video_common import (
    DEFAULT_ASPECT_RATIO,
    LoadedSourceVideo,
    build_filename,
    build_resolution_map,
    extract_provider_video_asset_ref,
    extract_source_video_uri_ref,
    load_mask_image,
    load_reference_images,
    load_source_image,
    load_source_video,
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
    from google.cloud import storage
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest

    GENAI_AVAILABLE = True
except ImportError:
    genai_types = None
    storage = None
    service_account = None
    GoogleAuthRequest = None
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")

DEFAULT_POLL_INTERVAL_SECONDS = 10.0
DEFAULT_POLL_TIMEOUT_SECONDS = 900.0


class VertexAIVideoGenerationService:
    """
    Veo video generation via Vertex AI.

    Official flow:
    - `client.models.generate_videos(...)`
    - poll with `client.operations.get(...)`
    - prefer inline `video.video_bytes`
    - fallback to authenticated GCS download if Vertex returns a `gs://` URI
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        credentials_json: str,
        *,
        http_options: Any = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
        output_gcs_uri: Optional[str] = None,
        output_bucket_name: Optional[str] = None,
    ) -> None:
        if not GENAI_AVAILABLE:
            raise RuntimeError("google.genai is not installed. Install google-genai before using Veo.")

        self.project_id = project_id
        self.location = location or "us-central1"
        self.credentials_json = credentials_json
        self.http_options = http_options
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.poll_timeout_seconds = float(poll_timeout_seconds)
        self.output_gcs_uri = str(output_gcs_uri or "").strip()
        self.output_bucket_name = str(output_bucket_name or "").strip()
        self._client = None
        self._credentials = None
        self._storage_client = None

    def _ensure_initialized(self) -> None:
        if self._client is not None:
            return
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(self.credentials_json),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        pool = get_client_pool()
        pooled_client = pool.get_client(
            api_key=None,
            vertexai=True,
            project=self.project_id,
            location=self.location,
            credentials=credentials,
            http_options=self.http_options,
        )
        self._client = pooled_client
        self._credentials = credentials

    def _get_storage_client(self):
        if storage is None:
            raise RuntimeError("google-cloud-storage is required for Vertex AI video output downloads.")
        if self._storage_client is not None:
            return self._storage_client
        self._storage_client = storage.Client(project=self.project_id, credentials=self._credentials)
        return self._storage_client

    def _sanitize_bucket_name(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9-]", "-", str(value or "").strip().lower())
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
        return normalized[:63].strip("-")

    def _resolve_output_bucket_name(self) -> str:
        configured_bucket = (
            self.output_bucket_name
            or os.getenv("GOOGLE_VIDEO_OUTPUT_BUCKET")
            or os.getenv("GOOGLE_VIDEO_GENERATION_OUTPUT_BUCKET")
            or os.getenv("VERTEX_VIDEO_OUTPUT_BUCKET")
        )
        if configured_bucket:
            sanitized = self._sanitize_bucket_name(configured_bucket)
            if sanitized:
                return sanitized

        derived = self._sanitize_bucket_name(f"{self.project_id}-veo-video-output")
        if not derived:
            raise RuntimeError("Unable to derive a valid GCS bucket name for Vertex AI video output.")
        return derived

    def _ensure_output_bucket(self):
        client = self._get_storage_client()
        bucket_name = self._resolve_output_bucket_name()
        bucket = client.bucket(bucket_name)
        if bucket.exists():
            return bucket

        bucket.location = self.location or "us-central1"
        client.create_bucket(bucket)
        logger.info(
            "[VertexAIVideoGenerationService] Created output bucket for Vertex video generation: %s",
            bucket_name,
        )
        return bucket

    def _build_output_gcs_uri(self) -> str:
        configured_uri = (
            self.output_gcs_uri
            or os.getenv("GOOGLE_VIDEO_OUTPUT_GCS_URI")
            or os.getenv("GOOGLE_VIDEO_GENERATION_OUTPUT_GCS_URI")
            or os.getenv("VERTEX_VIDEO_OUTPUT_GCS_URI")
        )
        if isinstance(configured_uri, str) and configured_uri.startswith("gs://"):
            return configured_uri.rstrip("/")

        bucket = self._ensure_output_bucket()
        return f"gs://{bucket.name}/veo-generated/{uuid.uuid4().hex}"

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
        if source_video_uri and last_frame_bridge and source_video_uri.uri.startswith("gs://"):
            source_video = await self._load_vertex_source_video_from_uri(
                source_video_uri.uri,
                source_video_uri.mime_type,
            )
            source_video_uri = None
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
            api_mode="vertex_ai",
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

        source_payload = genai_types.GenerateVideosSource(prompt=prompt or None)
        if source_image:
            source_payload.image = genai_types.Image(
                image_bytes=source_image.image_bytes,
                mime_type=source_image.mime_type,
            )
        if source_video_uri:
            source_payload.video = genai_types.Video(
                uri=source_video_uri.uri,
                mime_type=source_video_uri.mime_type or "video/mp4",
            )
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
        config_kwargs["output_gcs_uri"] = self._build_output_gcs_uri()
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
            "[VertexAIVideoGenerationService] Generating video: model=%s, aspect_ratio=%s, resolution=%s, duration=%ss, has_image=%s, has_video=%s, extra_refs=%s, output_gcs_uri=%s",
            normalized_model,
            aspect_ratio,
            resolution,
            duration_seconds,
            bool(source_image),
            bool(source_video or source_video_uri),
            len(extra_reference_images),
            config_kwargs["output_gcs_uri"],
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
        mime_type = (
            getattr(getattr(generated_video, "video", None), "mime_type", None)
            or "video/mp4"
        )
        resolved_asset_uri = asset_ref.gcs_uri or asset_ref.provider_file_uri or asset_ref.provider_file_name
        if resolved_asset_uri:
            url = resolved_asset_uri
        else:
            video_bytes, mime_type = await self._resolve_video_payload(generated_video)
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
            "provider_platform": "vertex_ai",
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
        gcs_uri: Optional[str] = None,
        provider_file_uri: Optional[str] = None,
        mime_type: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        self._ensure_initialized()
        target_uri = str(gcs_uri or provider_file_uri or "").strip()
        if not target_uri.startswith("gs://"):
            raise ValueError("Vertex AI video download requires a gs:// URI.")
        binary = await self._download_gcs_video(target_uri)
        resolved_mime_type = str(mime_type or "video/mp4").strip() or "video/mp4"
        return {
            "video_bytes": binary,
            "mime_type": resolved_mime_type,
            "provider_platform": "vertex_ai",
            "gcs_uri": target_uri,
            "provider_file_uri": provider_file_uri or target_uri,
        }

    async def delete_video(
        self,
        *,
        gcs_uri: Optional[str] = None,
        provider_file_uri: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        self._ensure_initialized()
        target_uri = str(gcs_uri or provider_file_uri or "").strip()
        if not target_uri.startswith("gs://"):
            raise ValueError("Vertex AI video deletion requires a gs:// URI.")
        bucket_name, object_name = self._parse_gcs_uri(target_uri)
        bucket = self._get_storage_client().bucket(bucket_name)
        bucket.blob(object_name).delete()
        return {
            "deleted": True,
            "provider_platform": "vertex_ai",
            "gcs_uri": target_uri,
        }

    async def _wait_for_operation(self, operation: Any) -> Any:
        start = asyncio.get_running_loop().time()
        current = operation
        while not getattr(current, "done", False):
            if asyncio.get_running_loop().time() - start > self.poll_timeout_seconds:
                raise TimeoutError("Timed out waiting for Vertex AI video generation to finish.")
            await asyncio.sleep(self.poll_interval_seconds)
            current = await asyncio.to_thread(self._client.operations.get, current)

        error = getattr(current, "error", None)
        if error:
            raise RuntimeError(f"Vertex AI video generation failed: {error}")
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
            raise RuntimeError("Vertex AI video generation did not return any generated videos.")
        generated = generated_videos[0]
        video_payload = self._extract_video_payload(generated)
        if video_payload is None:
            raise RuntimeError("Vertex AI video generation response is missing the generated video payload.")
        if getattr(generated, "video", None) is not None:
            return generated
        if isinstance(generated, dict) and generated.get("video") is not None:
            return SimpleNamespace(video=generated.get("video"))
        return SimpleNamespace(video=video_payload)

    async def _resolve_video_payload(self, generated_video: Any) -> Tuple[bytes, str]:
        video = self._extract_video_payload(generated_video)
        if video is None:
            raise RuntimeError("Vertex AI video generation response is missing the generated video payload.")
        mime_type = (
            getattr(video, "mime_type", None)
            or (video.get("mime_type") if isinstance(video, dict) else None)
            or (video.get("mimeType") if isinstance(video, dict) else None)
            or "video/mp4"
        )
        video_bytes = getattr(video, "video_bytes", None)
        if video_bytes is None and isinstance(video, dict):
            video_bytes = video.get("video_bytes") or video.get("videoBytes")
        if video_bytes:
            return bytes(video_bytes), mime_type

        uri = str(
            getattr(video, "uri", None)
            or (video.get("uri") if isinstance(video, dict) else "")
            or (video.get("gcs_uri") if isinstance(video, dict) else "")
            or (video.get("gcsUri") if isinstance(video, dict) else "")
            or ""
        ).strip()
        if uri.startswith("gs://"):
            return await self._download_gcs_video(uri), mime_type

        raise RuntimeError("Vertex AI did not return inline video bytes or a downloadable gs:// URI.")

    def _extract_video_payload(self, generated_video: Any) -> Optional[Any]:
        if generated_video is None:
            return None
        video = getattr(generated_video, "video", None)
        if video is not None:
            return video
        if isinstance(generated_video, dict):
            if generated_video.get("video") is not None:
                return generated_video.get("video")
            if any(
                key in generated_video
                for key in ("uri", "video_bytes", "videoBytes", "gcs_uri", "gcsUri")
            ):
                return generated_video
        return None

    async def _load_vertex_source_video_from_uri(self, uri: str, mime_type: Optional[str]) -> LoadedSourceVideo:
        return LoadedSourceVideo(
            video_bytes=await self._download_gcs_video(uri),
            mime_type=str(mime_type or "video/mp4").strip() or "video/mp4",
        )

    async def _download_gcs_video(self, gcs_uri: str) -> bytes:
        bucket, object_name = self._parse_gcs_uri(gcs_uri)
        self._credentials.refresh(GoogleAuthRequest())
        token = self._credentials.token
        url = f"https://storage.googleapis.com/download/storage/v1/b/{bucket}/o/{quote(object_name, safe='')}?alt=media"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content

    def _parse_gcs_uri(self, uri: str) -> Tuple[str, str]:
        trimmed = uri.removeprefix("gs://")
        parts = trimmed.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid Vertex AI video GCS URI: {uri}")
        return parts[0], parts[1]
