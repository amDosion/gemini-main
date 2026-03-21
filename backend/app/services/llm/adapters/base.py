"""LLM Adapter base class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMAdapter(ABC):
    """Unified adapter contract for provider LLM clients."""

    @abstractmethod
    async def chat(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Run non-streaming chat completion."""
        ...
