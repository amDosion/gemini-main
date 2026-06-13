"""Tongyi/DashScope OutfitAnyone virtual try-on service."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import time
from typing import Any, Dict
from urllib.parse import unquote

import httpx

from ...utils.log_sanitization import summarize_url_for_log
from ..storage.local_provider import DEFAULT_LOCAL_URL_PREFIX, resolve_local_public_file_path
from .base import DASHSCOPE_BASE_URL
from .file_upload import upload_bytes_to_dashscope_async, upload_to_dashscope_async

logger = logging.getLogger(__name__)

TRYON_ENDPOINT = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/image2image/image-synthesis"
TASK_ENDPOINT = f"{DASHSCOPE_BASE_URL}/api/v1/tasks"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}


def is_tongyi_tryon_model(model_id: str) -> bool:
    return str(model_id or "").strip().lower() == "aitryon-plus"


class TongyiVirtualTryOnService:
    """DashScope OutfitAnyone-Plus async task wrapper."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        poll_timeout: float = 600.0,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    async def virtual_tryon(
        self,
        reference_images: Dict[str, Any],
        *,
        model: str = "aitryon-plus",
        resolution: Any = -1,
        restore_face: bool = True,
        **_: Any,
    ) -> Dict[str, Any]:
        if not is_tongyi_tryon_model(model):
            raise ValueError(f"Unsupported Tongyi virtual try-on model: {model}")

        person_url, garment_url = self._extract_person_and_garment(reference_images)
        person_url = await self._ensure_provider_url(person_url, model)
        garment_url = await self._ensure_provider_url(garment_url, model)

        payload = {
            "model": model,
            "input": {
                "person_image_url": person_url,
                "top_garment_url": garment_url,
            },
            "parameters": {
                "resolution": self._normalize_resolution(resolution),
                "restore_face": bool(restore_face),
            },
        }
        logger.info("[TongyiTryOn] Creating try-on task: model=%s", model)
        task_response = await self._post_task(payload)
        task_id = self._extract_task_id(task_response)
        result = await self._poll_task(task_id)
        output = result.get("output") if isinstance(result.get("output"), dict) else {}
        if str(output.get("task_status") or "").upper() != "SUCCEEDED":
            message = output.get("message") or output.get("code") or "try-on task did not succeed"
            raise RuntimeError(f"Tongyi virtual try-on failed: {message}")

        output_url = str(output.get("image_url") or "").strip()
        if not output_url:
            raise RuntimeError("Tongyi virtual try-on succeeded without image_url")

        return {
            "url": output_url,
            "mime_type": "image/jpeg",
            "filename": f"{task_id}.jpg",
            "task_id": task_id,
            "model": model,
        }

    def _extract_person_and_garment(self, reference_images: Dict[str, Any]) -> tuple[str, str]:
        raw = reference_images.get("raw")
        raw_items = raw if isinstance(raw, list) else [raw] if raw else []
        person = self._extract_url(raw_items[0]) if len(raw_items) >= 1 else ""
        garment = (
            self._extract_url(reference_images.get("clothing"))
            or self._extract_url(reference_images.get("garment"))
            or self._extract_url(reference_images.get("top_garment"))
            or (self._extract_url(raw_items[1]) if len(raw_items) >= 2 else "")
        )
        if not person or not garment:
            raise ValueError("Tongyi virtual try-on requires two images: person first, garment second.")
        return person, garment

    @staticmethod
    def _extract_url(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("url") or value.get("temp_url") or value.get("file_uri") or "").strip()
        return str(value or "").strip()

    async def _ensure_provider_url(self, url: str, model: str) -> str:
        if url.startswith(("http://", "https://", "oss://")):
            return url
        if url.startswith(f"{DEFAULT_LOCAL_URL_PREFIX}/"):
            local_path = resolve_local_public_file_path(url) or resolve_local_public_file_path(unquote(url))
            if not local_path or not local_path.exists() or not local_path.is_file():
                raise RuntimeError(
                    "Tongyi virtual try-on local image file not found: "
                    f"{summarize_url_for_log(url)}"
                )
            mime_type = mimetypes.guess_type(local_path.name)[0] or "image/png"
            extension = mimetypes.guess_extension(mime_type) or ".png"
            upload = await upload_bytes_to_dashscope_async(
                local_path.read_bytes(),
                f"tryon-{int(time.time() * 1000)}{extension}",
                self.api_key,
                model=model,
            )
            if not upload.success or not upload.oss_url:
                raise RuntimeError(f"Tongyi virtual try-on image upload failed: {upload.error}")
            return upload.oss_url
        upload = await upload_to_dashscope_async(url, self.api_key, model=model)
        if not upload.success or not upload.oss_url:
            raise RuntimeError(f"Tongyi virtual try-on image upload failed: {upload.error}")
        return upload.oss_url

    @staticmethod
    def _normalize_resolution(value: Any) -> int:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            parsed = -1
        return parsed if parsed in {-1, 1024, 1280} else -1

    async def _post_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
            "X-DashScope-OssResourceResolve": "enable",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(TRYON_ENDPOINT, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"DashScope try-on API error {response.status_code}: {response.text}")
        return response.json()

    @staticmethod
    def _extract_task_id(response: Dict[str, Any]) -> str:
        output = response.get("output") if isinstance(response.get("output"), dict) else {}
        task_id = str(output.get("task_id") or "").strip()
        if not task_id:
            raise RuntimeError(f"DashScope try-on response missing task_id: {response}")
        return task_id

    async def _poll_task(self, task_id: str) -> Dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                response = await client.get(f"{TASK_ENDPOINT}/{task_id}", headers=headers)
                if response.status_code >= 400:
                    raise RuntimeError(f"DashScope try-on poll error {response.status_code}: {response.text}")
                data = response.json()
                output = data.get("output") if isinstance(data.get("output"), dict) else {}
                status = str(output.get("task_status") or "").upper()
                if status in TERMINAL_STATUSES:
                    return data
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Tongyi virtual try-on task timed out: {task_id}")
                await asyncio.sleep(self.poll_interval)
