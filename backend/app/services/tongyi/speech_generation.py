"""Tongyi/DashScope non-realtime text-to-speech service."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .base import DASHSCOPE_BASE_URL

logger = logging.getLogger(__name__)

SPEECH_ENDPOINT = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"


def is_tongyi_speech_model(model_id: str) -> bool:
    model = str(model_id or "").strip().lower()
    if "realtime" in model or model.startswith(("qwen3-tts-vc", "qwen3-tts-vd")):
        return False
    return (
        model.startswith("qwen-tts")
        or model.startswith("qwen3-tts-flash")
        or model.startswith("qwen3-tts-instruct-flash")
    )


class TongyiSpeechGenerationService:
    """DashScope Qwen TTS HTTP wrapper for non-realtime synthesis."""

    def __init__(self, api_key: str, *, timeout: float = 120.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def generate_speech(
        self,
        text: str,
        model: str,
        *,
        voice: str = "Cherry",
        language_type: Optional[str] = None,
        instructions: Optional[str] = None,
        optimize_instructions: Optional[bool] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        if not is_tongyi_speech_model(model):
            raise ValueError(f"Unsupported Tongyi speech model: {model}")
        if not str(text or "").strip():
            raise ValueError("Tongyi speech generation requires non-empty text")

        payload = self._build_payload(
            text=text,
            model=model,
            voice=voice,
            language_type=language_type,
            instructions=instructions,
            optimize_instructions=optimize_instructions,
        )
        logger.info("[TongyiSpeech] Generating speech: model=%s voice=%s", model, voice)
        data = await self._post(payload)
        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        audio_url = self._extract_audio_url(output)
        if not audio_url:
            message = output.get("message") or data.get("message") or "missing output audio url"
            raise RuntimeError(f"Tongyi speech generation failed: {message}")

        return {
            "url": audio_url,
            "mime_type": self._resolve_mime_type(audio_url),
            "format": self._resolve_format(audio_url),
            "model": model,
            "voice": voice,
            "request_id": data.get("request_id"),
        }

    def _build_payload(
        self,
        *,
        text: str,
        model: str,
        voice: str,
        language_type: Optional[str],
        instructions: Optional[str],
        optimize_instructions: Optional[bool],
    ) -> Dict[str, Any]:
        input_payload: Dict[str, Any] = {
            "text": text,
            "voice": voice or "Cherry",
        }
        if language_type:
            input_payload["language_type"] = language_type

        payload: Dict[str, Any] = {
            "model": model,
            "input": input_payload,
        }
        parameters: Dict[str, Any] = {}
        if instructions:
            parameters["instructions"] = instructions
        if optimize_instructions is not None:
            parameters["optimize_instructions"] = bool(optimize_instructions)
        if parameters:
            payload["parameters"] = parameters
        return payload

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(SPEECH_ENDPOINT, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"DashScope speech API error {response.status_code}: {response.text}")
        return response.json()

    @staticmethod
    def _extract_audio_url(output: Dict[str, Any]) -> Optional[str]:
        audio = output.get("audio")
        if isinstance(audio, dict):
            for key in ("url", "audio_url", "audioUrl"):
                value = str(audio.get(key) or "").strip()
                if value:
                    return value
        for key in ("audio_url", "audioUrl", "url"):
            value = str(output.get(key) or "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _resolve_format(url: str) -> str:
        lowered = str(url or "").lower()
        if ".mp3" in lowered or "audio/mpeg" in lowered:
            return "mp3"
        if ".wav" in lowered or "audio/wav" in lowered:
            return "wav"
        if ".ogg" in lowered or "audio/ogg" in lowered:
            return "ogg"
        return "wav"

    @classmethod
    def _resolve_mime_type(cls, url: str) -> str:
        audio_format = cls._resolve_format(url)
        if audio_format == "mp3":
            return "audio/mpeg"
        if audio_format == "ogg":
            return "audio/ogg"
        return "audio/wav"
