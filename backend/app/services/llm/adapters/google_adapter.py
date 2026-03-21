"""Google Gemini adapter implementation."""

import logging
from typing import Any, Dict, List

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class GoogleLLMAdapter(LLMAdapter):
    """Adapter for GoogleService."""

    def __init__(self, google_service: Any):
        self.service = google_service

    async def chat(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        final_messages = list(messages)
        if system_prompt:
            final_messages.insert(
                0,
                {
                    "role": "user",
                    "content": (
                        "[System Instructions]\n"
                        f"{system_prompt}\n"
                        "[End System Instructions]\n\n"
                        "Please follow the above instructions for all subsequent messages."
                    ),
                },
            )
            final_messages.insert(
                1,
                {
                    "role": "model",
                    "content": "Understood. I will follow these instructions.",
                },
            )

        try:
            response = await self.service.chat(
                messages=final_messages,
                model=model_id,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            return self._normalize(response)
        except Exception as exc:
            logger.error(f"[GoogleLLMAdapter] Chat failed: {exc}")
            raise

    def _normalize(self, response: Dict[str, Any]) -> Dict[str, Any]:
        text = ""
        if isinstance(response, dict):
            text = response.get("text", "") or response.get("content", "")
            if not text and "candidates" in response:
                candidates = response["candidates"]
                if candidates and len(candidates) > 0:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(part.get("text", "") for part in parts)
        elif isinstance(response, str):
            text = response

        return {
            "text": text,
            "usage": response.get("usage", {}) if isinstance(response, dict) else {},
        }
