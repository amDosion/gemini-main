"""
Gemini Developer API implementation for video understanding.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from ..base.video_common import extract_source_video_uri_ref, load_source_video
from ..client_pool import get_client_pool

logger = logging.getLogger(__name__)

DEFAULT_VIDEO_UNDERSTAND_MODEL = "gemini-2.5-flash"

try:
    from google.genai import types as genai_types

    GENAI_AVAILABLE = True
except ImportError:
    genai_types = None
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start:end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


class GeminiAPIVideoUnderstandingService:
    def __init__(
        self,
        api_key: str,
        *,
        http_options: Any = None,
    ) -> None:
        if not GENAI_AVAILABLE:
            raise RuntimeError("google.genai is not installed. Install google-genai before using Gemini video understanding.")
        self.api_key = api_key
        self.http_options = http_options
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

    def _extract_source_video_uri(self, source_video: Any) -> Optional[str]:
        source_ref = extract_source_video_uri_ref(source_video)
        return source_ref.uri if source_ref else None

    async def understand_video(
        self,
        prompt: str,
        model: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        self._ensure_initialized()

        source_video_input = (
            kwargs.get("source_video")
            or kwargs.get("sourceVideo")
            or kwargs.get("reference_images")
        )
        source_video_ref = extract_source_video_uri_ref(source_video_input)
        source_video_uri = self._extract_source_video_uri(source_video_input)
        source_video = None if source_video_uri else await load_source_video(source_video_input)
        if not source_video_uri and source_video is None:
            raise ValueError("Google video understanding requires a source video.")

        normalized_model = str(model or DEFAULT_VIDEO_UNDERSTAND_MODEL).strip() or DEFAULT_VIDEO_UNDERSTAND_MODEL
        final_prompt = str(prompt or "").strip() or "请分析该视频的主要场景、动作、镜头变化和关键信息。"
        output_format = str(kwargs.get("output_format") or kwargs.get("outputFormat") or "markdown").strip().lower()
        if output_format == "json":
            final_prompt = (
                f"{final_prompt}\n\n"
                "请严格输出 JSON 对象，至少包含 summary, scenes, actions, objects, text, speech 五个字段。"
            )

        if source_video_uri:
            video_part = genai_types.Part.from_uri(
                file_uri=source_video_uri,
                mime_type=str(
                    kwargs.get("mime_type")
                    or kwargs.get("mimeType")
                    or (source_video_ref.mime_type if source_video_ref else None)
                    or "video/mp4"
                ),
            )
        else:
            video_part = genai_types.Part.from_bytes(
                data=source_video.video_bytes,
                mime_type=source_video.mime_type,
            )

        config_kwargs: Dict[str, Any] = {}
        temperature = kwargs.get("temperature")
        if isinstance(temperature, (int, float)):
            config_kwargs["temperature"] = float(temperature)
        max_tokens = kwargs.get("max_tokens") or kwargs.get("max_output_tokens")
        if isinstance(max_tokens, int) and max_tokens > 0:
            config_kwargs["max_output_tokens"] = max_tokens

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=normalized_model,
            contents=[video_part, final_prompt],
            config=genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
        )
        response_text = str(getattr(response, "text", None) or "").strip()
        analysis = _extract_json_object(response_text) if output_format == "json" else {}
        return {
            "text": response_text,
            "analysis": analysis,
            "model": normalized_model,
            "provider_platform": "developer_api",
            "provider_file_uri": source_video_uri,
        }
