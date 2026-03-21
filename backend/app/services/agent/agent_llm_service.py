"""Agent-facing LLM service.

This module keeps the agent API stable while delegating provider/model routing
and credentials resolution to the shared `services.llm` runtime layer.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..llm.runtime import LLMRuntime


class AgentLLMService:
    """Thin facade used by workflow engine and agent execution."""

    def __init__(self, user_id: str, db: Session):
        self.user_id = user_id
        self.db = db
        self.runtime = LLMRuntime(user_id=user_id, db=db)

    async def chat(
        self,
        provider_id: str,
        model_id: str,
        messages: List[Dict[str, Any]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.runtime.chat(
            provider_id=provider_id,
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            profile_id=profile_id,
        )
