"""
Live API Handler - Live API 处理器

提供：
- query()：标准查询（同步）
- stream_query()：服务器端流式查询
- bidi_stream_query()：双向流式查询（WebSocket/SSE）
- 用户中断处理
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator, List
from sqlalchemy.orm import Session

from ....services.llm import ProviderCredentialsResolver
from ....services.agent.adk_builtin_tools import build_adk_builtin_tools
from ....services.common.provider_factory import ProviderFactory
from ....models.db_models import AgentRegistry
from .adk_agent import ADKAgent
from .adk_runner import ADKRunner

logger = logging.getLogger(__name__)


class LiveAPIHandler:
    """
    Live API 处理器

    负责：
    - 标准查询（同步）
    - 流式查询（服务器推送）
    - 双向流式查询（WebSocket）
    - 用户中断处理
    """

    def __init__(self, db: Session):
        """
        初始化 Live API 处理器

        Args:
            db: 数据库会话
        """
        self.db = db
        self._credentials_resolver = ProviderCredentialsResolver()
        logger.info("[LiveAPIHandler] Initialized")

    async def _resolve_provider_api_key(self, provider_id: str, user_id: str) -> str:
        api_key, _ = await self._credentials_resolver.resolve(
            provider_id=provider_id,
            db=self.db,
            user_id=user_id,
        )
        return str(api_key or "").strip()

    @staticmethod
    def _build_live_session_id(user_id: str, agent_id: Optional[str]) -> str:
        suffix = str(agent_id or "default").strip()[:24] or "default"
        return f"live-{user_id}-{suffix}-{int(time.time() * 1000)}"

    @staticmethod
    def _extract_stream_text(chunk: Dict[str, Any]) -> str:
        if not isinstance(chunk, dict):
            return str(chunk or "")
        for key in ("text", "content", "chunk", "delta", "output"):
            value = chunk.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                nested_text = value.get("text")
                if isinstance(nested_text, str) and nested_text.strip():
                    return nested_text
        return ""

    async def _get_agent(self, user_id: str, agent_id: str) -> AgentRegistry:
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == str(agent_id or "").strip(),
            AgentRegistry.user_id == user_id,
            AgentRegistry.status == "active",
        ).first()
        if not agent:
            raise ValueError(f"agent not found: {agent_id}")
        return agent

    @staticmethod
    def _is_adk_agent(agent: AgentRegistry) -> bool:
        agent_type = str(getattr(agent, "agent_type", "") or "").strip().lower()
        provider_id = str(getattr(agent, "provider_id", "") or "").strip().lower()
        return agent_type in {"adk", "google-adk"} and provider_id.startswith("google")

    async def _chat_with_provider(
        self,
        *,
        user_id: str,
        provider_id: str,
        model_id: str,
        input_data: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        api_key = await self._resolve_provider_api_key(provider_id, user_id)
        service = ProviderFactory.create(
            provider=provider_id,
            api_key=api_key,
            user_id=user_id,
            db=self.db,
        )

        kwargs: Dict[str, Any] = {}
        if str(system_prompt or "").strip():
            kwargs["system_prompt"] = system_prompt
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        if max_tokens is not None:
            kwargs["max_tokens"] = int(max_tokens)

        response = await service.chat(
            messages=[{"role": "user", "content": str(input_data or "")}],
            model=model_id,
            **kwargs,
        )
        text = str(response.get("text") or response.get("output") or "").strip()
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        return {
            "output": text,
            "usage": usage,
            "raw": response,
        }

    async def _stream_with_provider(
        self,
        *,
        user_id: str,
        provider_id: str,
        model_id: str,
        input_data: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        api_key = await self._resolve_provider_api_key(provider_id, user_id)
        service = ProviderFactory.create(
            provider=provider_id,
            api_key=api_key,
            user_id=user_id,
            db=self.db,
        )

        kwargs: Dict[str, Any] = {}
        if str(system_prompt or "").strip():
            kwargs["system_prompt"] = system_prompt
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        if max_tokens is not None:
            kwargs["max_tokens"] = int(max_tokens)

        final_buffer: List[str] = []
        stream_method = getattr(service, "stream_chat", None)
        if callable(stream_method):
            async for chunk in stream_method(
                messages=[{"role": "user", "content": str(input_data or "")}],
                model=model_id,
                **kwargs,
            ):
                chunk_text = self._extract_stream_text(chunk if isinstance(chunk, dict) else {"text": str(chunk or "")})
                if chunk_text:
                    final_buffer.append(chunk_text)
                    yield {
                        "chunk": chunk_text,
                        "status": "streaming",
                    }
            yield {
                "status": "completed",
                "output": "".join(final_buffer).strip(),
            }
            return

        # Provider 不支持流式时回退
        result = await self._chat_with_provider(
            user_id=user_id,
            provider_id=provider_id,
            model_id=model_id,
            input_data=input_data,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        full_text = str(result.get("output") or "")
        words = [word for word in full_text.split(" ") if word]
        if not words:
            yield {"status": "completed", "output": full_text}
            return
        for idx, word in enumerate(words):
            suffix = " " if idx < len(words) - 1 else ""
            yield {
                "chunk": f"{word}{suffix}",
                "progress": f"{idx + 1}/{len(words)}",
                "status": "streaming",
            }
        yield {
            "status": "completed",
            "output": full_text,
        }

    async def _query_with_adk_agent(
        self,
        *,
        user_id: str,
        agent: AgentRegistry,
        input_data: str,
    ) -> Dict[str, Any]:
        provider_id = str(agent.provider_id or "google").strip() or "google"
        model_id = str(agent.model_id or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        api_key = await self._resolve_provider_api_key(provider_id, user_id)

        adk_agent = ADKAgent(
            db=self.db,
            model=model_id,
            name=str(agent.name or "Live ADK Agent"),
            instruction=str(agent.system_prompt or "You are a helpful assistant."),
            tools=build_adk_builtin_tools(),
        )
        if not adk_agent.is_available:
            raise RuntimeError("google.adk SDK is not available in current runtime")

        session_id = self._build_live_session_id(user_id=user_id, agent_id=str(agent.id or ""))
        runner = ADKRunner(
            db=self.db,
            agent_id=str(agent.id or ""),
            app_name="gemini-live-api",
            adk_agent=adk_agent,
        )
        response = await runner.run_once(
            user_id=user_id,
            session_id=session_id,
            input_data=str(input_data or ""),
            google_api_key=api_key,
            run_config={
                "max_llm_calls": 120,
                "custom_metadata": {
                    "channel": "live_api",
                    "agent_id": str(agent.id or ""),
                },
            },
        )
        return {
            "output": str(response.get("text") or ""),
            "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
            "session_id": session_id,
            "invocation_id": str(response.get("invocation_id") or "").strip(),
            "event_count": int(response.get("event_count") or 0),
        }

    async def _stream_with_adk_agent(
        self,
        *,
        user_id: str,
        agent: AgentRegistry,
        input_data: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider_id = str(agent.provider_id or "google").strip() or "google"
        model_id = str(agent.model_id or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        api_key = await self._resolve_provider_api_key(provider_id, user_id)

        adk_agent = ADKAgent(
            db=self.db,
            model=model_id,
            name=str(agent.name or "Live ADK Agent"),
            instruction=str(agent.system_prompt or "You are a helpful assistant."),
            tools=build_adk_builtin_tools(),
        )
        if not adk_agent.is_available:
            raise RuntimeError("google.adk SDK is not available in current runtime")

        session_id = self._build_live_session_id(user_id=user_id, agent_id=str(agent.id or ""))
        runner = ADKRunner(
            db=self.db,
            agent_id=str(agent.id or ""),
            app_name="gemini-live-api",
            adk_agent=adk_agent,
        )

        final_text = ""
        final_usage: Dict[str, Any] = {}
        final_invocation_id = ""
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            input_data=str(input_data or ""),
            google_api_key=api_key,
            run_config={
                "response_modalities": ["TEXT"],
                "max_llm_calls": 120,
                "custom_metadata": {
                    "channel": "live_api",
                    "agent_id": str(agent.id or ""),
                },
            },
            close_queue=True,
            max_events=240,
        ):
            invocation_id = str(event.get("invocation_id") or "").strip()
            if invocation_id:
                final_invocation_id = invocation_id

            event_type = str(event.get("type") or "").strip()
            if event_type == "error":
                yield {
                    "status": "failed",
                    "error": str(event.get("error") or "ADK stream failed"),
                    "session_id": session_id,
                }
                return

            actions = event.get("actions") if isinstance(event.get("actions"), dict) else {}
            function_calls = event.get("function_calls") if isinstance(event.get("function_calls"), list) else []
            function_responses = (
                event.get("function_responses") if isinstance(event.get("function_responses"), list) else []
            )
            long_running_tool_ids = event.get("long_running_tool_ids") or []
            if actions or function_calls or function_responses or long_running_tool_ids:
                yield {
                    "type": "action",
                    "actions": actions,
                    "function_calls": function_calls,
                    "function_responses": function_responses,
                    "long_running_tool_ids": long_running_tool_ids,
                    "invocation_id": invocation_id,
                    "partial": bool(event.get("partial")),
                    "turn_complete": bool(event.get("turn_complete")),
                    "session_id": session_id,
                }

            if event_type == "final" or bool(event.get("is_final")):
                final_event_text = str(event.get("content") or "").strip()
                if final_event_text:
                    final_text = final_event_text
                if isinstance(event.get("usage"), dict):
                    final_usage = event.get("usage") or {}
                yield {
                    "status": "completed",
                    "output": final_text,
                    "usage": final_usage,
                    "invocation_id": invocation_id,
                    "session_id": session_id,
                }
                return

            if event_type in {"chunk", "live_event", "content"}:
                chunk_text = str(event.get("content") or "")
                if chunk_text:
                    final_text += chunk_text
                    yield {
                        "chunk": chunk_text,
                        "status": "streaming",
                        "invocation_id": invocation_id,
                        "partial": bool(event.get("partial")),
                        "session_id": session_id,
                    }

        yield {
            "status": "completed",
            "output": final_text,
            "usage": final_usage,
            "invocation_id": final_invocation_id,
            "session_id": session_id,
        }

    async def query(
        self,
        user_id: str,
        input_data: str,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        标准查询（同步）

        Args:
            user_id: 用户 ID
            input_data: 输入数据
            agent_id: 智能体 ID（可选）

        Returns:
            完整响应
        """
        input_text = str(input_data or "").strip()
        if not input_text:
            raise ValueError("input is required")

        if agent_id:
            agent = await self._get_agent(user_id=user_id, agent_id=agent_id)
            if self._is_adk_agent(agent):
                result = await self._query_with_adk_agent(
                    user_id=user_id,
                    agent=agent,
                    input_data=input_text,
                )
                return {
                    "output": result.get("output") or "",
                    "status": "completed",
                    "runtime": "adk",
                    "agent_id": str(agent.id or ""),
                    "agent_name": str(agent.name or ""),
                    "model": str(agent.model_id or ""),
                    "session_id": result.get("session_id"),
                    "invocation_id": result.get("invocation_id"),
                    "usage": result.get("usage") if isinstance(result.get("usage"), dict) else {},
                    "event_count": int(result.get("event_count") or 0),
                }

            provider_id = str(agent.provider_id or "google").strip() or "google"
            model_id = str(agent.model_id or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            result = await self._chat_with_provider(
                user_id=user_id,
                provider_id=provider_id,
                model_id=model_id,
                input_data=input_text,
                system_prompt=str(agent.system_prompt or ""),
                temperature=float(agent.temperature) if agent.temperature is not None else None,
                max_tokens=int(agent.max_tokens) if agent.max_tokens is not None else None,
            )
            return {
                "output": result.get("output") or "",
                "status": "completed",
                "runtime": "adapter",
                "agent_id": str(agent.id or ""),
                "agent_name": str(agent.name or ""),
                "model": f"{provider_id}/{model_id}",
                "usage": result.get("usage") if isinstance(result.get("usage"), dict) else {},
            }

        # 未指定 agent 时：默认走 Google 文本模型
        default_provider = "google"
        default_model = "gemini-2.5-flash"
        result = await self._chat_with_provider(
            user_id=user_id,
            provider_id=default_provider,
            model_id=default_model,
            input_data=input_text,
        )
        return {
            "output": result.get("output") or "",
            "status": "completed",
            "runtime": "adapter",
            "model": f"{default_provider}/{default_model}",
            "usage": result.get("usage") if isinstance(result.get("usage"), dict) else {},
        }

    async def stream_query(
        self,
        user_id: str,
        input_data: str,
        agent_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        服务器端流式查询

        Args:
            user_id: 用户 ID
            input_data: 输入数据
            agent_id: 智能体 ID（可选）

        Yields:
            增量响应块
        """
        input_text = str(input_data or "").strip()
        if not input_text:
            yield {"status": "failed", "error": "input is required"}
            return

        if agent_id:
            agent = await self._get_agent(user_id=user_id, agent_id=agent_id)
            if self._is_adk_agent(agent):
                async for event in self._stream_with_adk_agent(
                    user_id=user_id,
                    agent=agent,
                    input_data=input_text,
                ):
                    yield event
                return

            provider_id = str(agent.provider_id or "google").strip() or "google"
            model_id = str(agent.model_id or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            async for event in self._stream_with_provider(
                user_id=user_id,
                provider_id=provider_id,
                model_id=model_id,
                input_data=input_text,
                system_prompt=str(agent.system_prompt or ""),
                temperature=float(agent.temperature) if agent.temperature is not None else None,
                max_tokens=int(agent.max_tokens) if agent.max_tokens is not None else None,
            ):
                yield event
            return

        async for event in self._stream_with_provider(
            user_id=user_id,
            provider_id="google",
            model_id="gemini-2.5-flash",
            input_data=input_text,
        ):
            yield event

    async def bidi_stream_query(
        self,
        user_id: str,
        queue: asyncio.Queue,
        agent_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        双向流式查询

        Args:
            user_id: 用户 ID
            queue: 消息队列（用于接收用户输入）
            agent_id: 智能体 ID（可选）

        Yields:
            响应块
        """
        logger.info("[LiveAPIHandler] Bidi stream session started for user %s", user_id)

        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                if not isinstance(message, dict):
                    message = {"input": str(message or "")}

                user_input = str(message.get("input") or "").strip()
                request_agent_id = str(message.get("agent_id") or "").strip() or agent_id

                if user_input.lower() in ("exit", "quit"):
                    yield {"output": "Goodbye!", "status": "completed"}
                    break

                if not user_input:
                    yield {"status": "failed", "error": "input is required"}
                    continue

                async for event in self.stream_query(
                    user_id=user_id,
                    input_data=user_input,
                    agent_id=request_agent_id,
                ):
                    yield event

            except asyncio.TimeoutError:
                yield {"type": "heartbeat"}
            except Exception as e:
                logger.error("[LiveAPIHandler] Error in bidi stream: %s", e, exc_info=True)
                yield {"error": str(e), "status": "failed"}
                break
