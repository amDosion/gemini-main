"""OpenAI-compatible adapter implementation."""

import logging
from typing import Any, Dict, List

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class OpenAILLMAdapter(LLMAdapter):
    """Adapter for OpenAIService and OpenAI-compatible providers."""

    def __init__(self, openai_service: Any):
        self.service = openai_service

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
            final_messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            response = await self.service.chat(
                messages=final_messages,
                model=model_id,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._normalize(response)
        except Exception as exc:
            logger.error(f"[OpenAILLMAdapter] Chat failed: {exc}")
            raise

    def _normalize(self, response: Dict[str, Any]) -> Dict[str, Any]:
        text = ""
        if isinstance(response, dict):
            text = response.get("content", "") or response.get("text", "") or ""
        elif isinstance(response, str):
            text = response

        return {
            "text": text,
            "usage": response.get("usage", {}) if isinstance(response, dict) else {},
        }
