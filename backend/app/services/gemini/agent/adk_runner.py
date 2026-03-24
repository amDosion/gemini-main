"""
ADK Runner - ADK 执行器

提供：
- 基于官方 google.adk Runner.run_async 的执行路径
- 事件流解析（chunk/final/error/action）
- ADK 会话落库与复用
- 官方高级运行参数（run_config/state_delta/invocation_id）
- 会话 rewind、列表与快照
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, AsyncGenerator, Iterable

from sqlalchemy.orm import Session

from ....models.db_models import ADKSession
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)

ADK_RUN_CONFIG_ALLOWED_KEYS = frozenset(
    {
        "custom_metadata",
        "max_llm_calls",
        "max_output_tokens",
        "response_modalities",
        "streaming_mode",
        "support_cfc",
        "temperature",
        "top_p",
    }
)

ADK_RUN_CONFIG_BUDGET_RULES: Dict[str, Dict[str, Any]] = {
    "max_llm_calls": {"kind": "int", "min": 1, "max": 500},
    "temperature": {"kind": "float", "min": 0.0, "max": 2.0},
    "top_p": {"kind": "float", "min": 0.0, "max": 1.0},
    "max_output_tokens": {"kind": "int", "min": 1, "max": 8192},
}


def _stable_signature_payload(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except Exception:
        return json.dumps(
            str(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def compute_adk_accuracy_signals(
    *,
    content: Optional[str],
    actions: Optional[Dict[str, Any]] = None,
    long_running_tool_ids: Optional[List[str]] = None,
) -> Dict[str, str]:
    normalized_content = str(content or "").strip()
    normalized_actions = actions if isinstance(actions, dict) else {}
    normalized_tool_ids = sorted(
        str(item).strip()
        for item in (long_running_tool_ids or [])
        if str(item).strip()
    )

    response_signature = hashlib.sha256(
        _stable_signature_payload({"content": normalized_content}).encode("utf-8")
    ).hexdigest()
    action_signature = hashlib.sha256(
        _stable_signature_payload(
            {
                "actions": normalized_actions,
                "long_running_tool_ids": normalized_tool_ids,
            }
        ).encode("utf-8")
    ).hexdigest()
    return {
        "response_signature": response_signature,
        "action_signature": action_signature,
    }


def _validate_adk_run_config_budget_ranges(run_config: Dict[str, Any]) -> None:
    for key, rule in ADK_RUN_CONFIG_BUDGET_RULES.items():
        if key not in run_config:
            continue
        raw_value = run_config.get(key)
        kind = str(rule.get("kind") or "float")
        minimum = float(rule.get("min") or 0)
        maximum = float(rule.get("max") or 0)

        if kind == "int":
            if not isinstance(raw_value, int) or isinstance(raw_value, bool):
                raise ValueError(
                    f"invalid run_config budget for {key}: {raw_value!r}. "
                    f"Expected integer in [{int(minimum)}, {int(maximum)}]"
                )
            numeric_value = float(raw_value)
        else:
            if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
                raise ValueError(
                    f"invalid run_config budget for {key}: {raw_value!r}. "
                    f"Expected number in [{minimum}, {maximum}]"
                )
            numeric_value = float(raw_value)

        if numeric_value < minimum or numeric_value > maximum:
            if kind == "int":
                range_text = f"[{int(minimum)}, {int(maximum)}]"
            else:
                range_text = f"[{minimum}, {maximum}]"
            raise ValueError(
                f"invalid run_config budget for {key}: {raw_value!r}. "
                f"Expected value in {range_text}"
            )


def validate_adk_run_config_allowlist(run_config: Optional[Any]) -> Optional[Any]:
    """
    Validate run_config keys against backend allowlist.

    Unknown keys are rejected with explicit errors to keep endpoint behavior stable.
    """
    if run_config is None:
        return None

    if isinstance(run_config, dict):
        unknown_keys = sorted(
            str(key)
            for key in run_config.keys()
            if not isinstance(key, str) or key not in ADK_RUN_CONFIG_ALLOWED_KEYS
        )
        if unknown_keys:
            allowed_keys = ", ".join(sorted(ADK_RUN_CONFIG_ALLOWED_KEYS))
            invalid_keys = ", ".join(unknown_keys)
            raise ValueError(
                f"invalid run_config keys: {invalid_keys}. "
                f"Allowed keys: {allowed_keys}"
            )
        _validate_adk_run_config_budget_ranges(run_config)
        return run_config

    # Keep ADK RunConfig instance compatibility when SDK is available.
    if hasattr(run_config, "model_dump"):
        try:
            payload = run_config.model_dump()
        except Exception as exc:
            raise ValueError(f"invalid run_config object: {exc}") from exc
        return validate_adk_run_config_allowlist(payload)

    raise ValueError("run_config must be an object")


class ADKRunner:
    """
    ADK Runner 封装。

    - 优先使用官方 google.adk 运行；
    - ADK 不可用时 fail-closed 返回结构化错误；
    - 会话元数据写入 adk_sessions 便于审计与排障。
    """

    _google_api_key_lock: asyncio.Lock = asyncio.Lock()
    _runtime_cache_lock = threading.Lock()
    _runtime_session_services: Dict[str, Any] = {}
    _runtime_memory_services: Dict[str, Any] = {}

    def __init__(
        self,
        db: Session,
        agent_id: str,
        memory_manager: Optional[MemoryManager] = None,
        app_name: Optional[str] = None,
        adk_agent: Optional[Any] = None,
    ):
        self.db = db
        self.agent_id = str(agent_id or "").strip()
        self.memory_manager = memory_manager
        self.app_name = str(app_name or "gemini-multi-agent").strip()

        self._adk_available = False
        self._adk_runner = None
        self._adk_agent = None
        self._adk_app = None
        self._session_service = None
        self._memory_service = None
        self._Content = None
        self._Part = None
        self._Blob = None
        self._LiveRequestQueueClass = None
        self._LiveRequestClass = None
        self._RunnerClass = None
        self._RunConfigClass = None
        self._AppClass = None

        try:
            from google.adk.runners import Runner as ADKRunnerClass
            from google.adk.apps import App as ADKAppClass
            from google.adk.sessions import InMemorySessionService as ADKInMemorySessionService
            from google.adk.memory import InMemoryMemoryService as ADKInMemoryMemoryService
            from google.adk.agents.live_request_queue import LiveRequestQueue, LiveRequest
            from google.adk.agents.run_config import RunConfig
            from google.genai.types import Content, Part, Blob

            self._adk_available = True
            self._RunnerClass = ADKRunnerClass
            self._RunConfigClass = RunConfig
            self._AppClass = ADKAppClass
            self._Content = Content
            self._Part = Part
            self._Blob = Blob
            self._LiveRequestQueueClass = LiveRequestQueue
            self._LiveRequestClass = LiveRequest

            runtime_key = f"{self.app_name}:{self.agent_id}"
            self._session_service = self._get_or_create_runtime_service(
                cache=self._runtime_session_services,
                runtime_key=runtime_key,
                factory=ADKInMemorySessionService,
            )
            self._memory_service = None
            if not memory_manager:
                self._memory_service = self._get_or_create_runtime_service(
                    cache=self._runtime_memory_services,
                    runtime_key=runtime_key,
                    factory=ADKInMemoryMemoryService,
                )
        except Exception:
            self._adk_available = False
            logger.warning("[ADKRunner] ADK SDK not available, strict fail-closed mode enabled", exc_info=True)

        if adk_agent is not None and self._adk_available:
            self.set_agent(adk_agent)

        logger.info(
            "[ADKRunner] Initialized agent_id=%s app_name=%s adk_available=%s",
            self.agent_id,
            self.app_name,
            self._adk_available,
        )

    @property
    def is_available(self) -> bool:
        return bool(self._adk_available and self._adk_runner is not None)

    @classmethod
    def _get_google_api_key_lock(cls) -> asyncio.Lock:
        return cls._google_api_key_lock

    @classmethod
    def _get_or_create_runtime_service(
        cls,
        *,
        cache: Dict[str, Any],
        runtime_key: str,
        factory: Any,
    ) -> Any:
        with cls._runtime_cache_lock:
            existing = cache.get(runtime_key)
            if existing is not None:
                return existing
            created = factory()
            cache[runtime_key] = created
            return created

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _attach_accuracy_signals(payload: Dict[str, Any]) -> Dict[str, Any]:
        signals = compute_adk_accuracy_signals(
            content=str(payload.get("content") or ""),
            actions=payload.get("actions") if isinstance(payload.get("actions"), dict) else {},
            long_running_tool_ids=payload.get("long_running_tool_ids")
            if isinstance(payload.get("long_running_tool_ids"), list)
            else [],
        )
        payload.update(signals)
        return payload

    def _build_runtime_unavailable_error(
        self,
        *,
        stage: str,
        session_id: str,
        detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        message = str(detail or "").strip() or "ADK runtime is unavailable for this request."
        return {
            "type": "error",
            "error": message,
            "error_code": "ADK_RUNTIME_UNAVAILABLE",
            "stage": str(stage or "").strip() or "run",
            "hint": "Ensure google.adk SDK and runtime dependencies are installed and configured.",
            "retryable": False,
            "is_final": True,
            "session_id": session_id,
        }

    @staticmethod
    def _safe_json_loads(raw: Optional[str], default: Any = None) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default

    @staticmethod
    def _serialize_structured(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, list, dict)):
            return value
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                pass
        if hasattr(value, "dict"):
            try:
                return value.dict()
            except Exception:
                pass
        raw_dict = getattr(value, "__dict__", None)
        if isinstance(raw_dict, dict):
            return {key: item for key, item in raw_dict.items() if not str(key).startswith("_")}
        return str(value)

    @staticmethod
    def _preview(value: Any, limit: int = 240) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit]}..."

    def _build_run_config(self, run_config: Optional[Any]) -> Optional[Any]:
        if run_config is None:
            return None
        validated_run_config = validate_adk_run_config_allowlist(run_config)
        if self._RunConfigClass is None:
            return validated_run_config
        if isinstance(run_config, self._RunConfigClass):
            return run_config
        if isinstance(validated_run_config, dict):
            try:
                return self._RunConfigClass.model_validate(validated_run_config)
            except Exception as exc:
                raise ValueError(f"invalid run_config: {exc}") from exc
        raise ValueError("run_config must be a dict or ADK RunConfig instance")

    def _coerce_adk_agent(self, adk_agent: Any) -> Any:
        if adk_agent is None:
            return None
        if self._AppClass is not None and isinstance(adk_agent, self._AppClass):
            return getattr(adk_agent, "root_agent", None)
        if hasattr(adk_agent, "get_adk_agent"):
            try:
                return adk_agent.get_adk_agent()
            except Exception:
                logger.warning("[ADKRunner] Failed to fetch wrapped ADK agent", exc_info=True)
                return None
        return adk_agent

    def _coerce_adk_app(self, adk_agent: Any, coerced_agent: Any) -> Any:
        if adk_agent is None:
            return None
        if self._AppClass is not None and isinstance(adk_agent, self._AppClass):
            return adk_agent
        if hasattr(adk_agent, "get_adk_app"):
            try:
                app = adk_agent.get_adk_app()
                if app is not None:
                    return app
            except Exception:
                logger.warning("[ADKRunner] Failed to fetch wrapped ADK app", exc_info=True)
        if self._AppClass is None or coerced_agent is None:
            return None
        return self._AppClass(
            name=self.app_name,
            root_agent=coerced_agent,
        )

    def set_agent(self, adk_agent: Any) -> None:
        if not self._adk_available:
            return
        coerced = self._coerce_adk_agent(adk_agent)
        if coerced is None:
            raise ValueError("set_agent requires a valid ADK agent instance")

        self._adk_agent = coerced
        self._adk_app = self._coerce_adk_app(adk_agent, coerced)
        runner_kwargs: Dict[str, Any] = {
            "session_service": self._session_service,
            "memory_service": self._memory_service,
            "auto_create_session": True,
        }
        if self._adk_app is not None:
            # Official ADK recommended initialization path: Runner(app=App(...)).
            runner_kwargs["app"] = self._adk_app
            runner_kwargs["app_name"] = self.app_name
        else:
            runner_kwargs["app_name"] = self.app_name
            runner_kwargs["agent"] = self._adk_agent

        self._adk_runner = self._RunnerClass(**runner_kwargs)  # type: ignore[misc]

    @contextmanager
    def _temporary_google_api_key(self, google_api_key: Optional[str]):
        if not google_api_key:
            yield
            return

        key = str(google_api_key or "").strip()
        previous = os.environ.get("GOOGLE_API_KEY")
        os.environ["GOOGLE_API_KEY"] = key
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = previous

    async def _ensure_adk_session(self, user_id: str, session_id: str) -> None:
        if not self._session_service:
            return
        existing = await self._maybe_await(
            self._session_service.get_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
        )
        if existing is not None:
            return
        await self._maybe_await(
            self._session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
        )

    @staticmethod
    def _normalize_role(value: Any, *, default: str = "user") -> str:
        role = str(value or "").strip().lower()
        if not role:
            return default
        if role in {"human"}:
            return "user"
        if role in {"assistant"}:
            return "model"
        return role

    def _build_part_from_dict(self, payload: Dict[str, Any]) -> Any:
        if self._Part is None:
            raise RuntimeError("ADK Part type is unavailable")
        if hasattr(self._Part, "model_validate"):
            try:
                return self._Part.model_validate(payload)
            except Exception as exc:
                raise ValueError(f"invalid part payload: {exc}") from exc
        try:
            return self._Part(**payload)  # type: ignore[misc]
        except Exception as exc:
            raise ValueError(f"invalid part payload: {exc}") from exc

    def _build_new_message(
        self,
        *,
        input_data: Optional[str],
        input_message: Optional[Dict[str, Any]],
    ) -> Any:
        if self._Content is None or self._Part is None:
            raise RuntimeError("ADK content types are unavailable")

        if isinstance(input_message, dict):
            role = self._normalize_role(input_message.get("role"), default="user")
            raw_parts = input_message.get("parts")
            if raw_parts is None:
                text = str(input_message.get("text") or input_data or "").strip()
                raw_parts = [{"text": text}] if text else []
            if not isinstance(raw_parts, list) or not raw_parts:
                raise ValueError("input_message.parts must be a non-empty list")

            parts: List[Any] = []
            for idx, raw_part in enumerate(raw_parts):
                if isinstance(raw_part, str):
                    raw_part = {"text": raw_part}
                if not isinstance(raw_part, dict):
                    raise ValueError(f"input_message.parts[{idx}] must be an object")
                part = self._build_part_from_dict(raw_part)
                parts.append(part)

            return self._Content(role=role, parts=parts)  # type: ignore[misc]

        text = str(input_data or "").strip()
        if not text:
            raise ValueError("input is required")
        return self._Content(  # type: ignore[misc]
            role="user",
            parts=[self._Part(text=text)],  # type: ignore[misc]
        )

    @staticmethod
    def _extract_input_preview(
        *,
        input_data: Optional[str],
        input_message: Optional[Dict[str, Any]],
    ) -> str:
        text = str(input_data or "").strip()
        if text:
            return text
        if not isinstance(input_message, dict):
            return ""
        raw_parts = input_message.get("parts")
        if not isinstance(raw_parts, list):
            direct_text = str(input_message.get("text") or "").strip()
            return direct_text
        previews: List[str] = []
        for part in raw_parts:
            if isinstance(part, str):
                chunk = part.strip()
                if chunk:
                    previews.append(chunk)
                continue
            if not isinstance(part, dict):
                continue
            part_text = str(part.get("text") or "").strip()
            if part_text:
                previews.append(part_text)
                continue
            function_response = part.get("function_response")
            if isinstance(function_response, dict):
                previews.append("[function_response]")
        return "\n".join(previews).strip()

    def _extract_event_function_calls(self, event: Any) -> List[Dict[str, Any]]:
        content = getattr(event, "content", None)
        if content is None:
            return []

        parts: Iterable[Any] = getattr(content, "parts", None) or []
        calls: List[Dict[str, Any]] = []
        for part in parts:
            function_call = getattr(part, "function_call", None)
            if not function_call and isinstance(part, dict):
                function_call = part.get("function_call")
            if not function_call:
                continue

            payload = self._serialize_structured(function_call) or {}
            if not isinstance(payload, dict):
                continue
            calls.append(
                {
                    "id": str(payload.get("id") or "").strip(),
                    "name": str(payload.get("name") or "").strip(),
                    "args": payload.get("args") if isinstance(payload.get("args"), dict) else {},
                    "will_continue": bool(payload.get("will_continue"))
                    if payload.get("will_continue") is not None
                    else None,
                }
            )
        return calls

    def _extract_event_function_responses(self, event: Any) -> List[Dict[str, Any]]:
        content = getattr(event, "content", None)
        if content is None:
            return []

        parts: Iterable[Any] = getattr(content, "parts", None) or []
        responses: List[Dict[str, Any]] = []
        for part in parts:
            function_response = getattr(part, "function_response", None)
            if not function_response and isinstance(part, dict):
                function_response = part.get("function_response")
            if not function_response:
                continue

            payload = self._serialize_structured(function_response) or {}
            if not isinstance(payload, dict):
                continue
            responses.append(
                {
                    "id": str(payload.get("id") or "").strip(),
                    "name": str(payload.get("name") or "").strip(),
                    "response": payload.get("response")
                    if isinstance(payload.get("response"), dict)
                    else payload.get("response"),
                    "will_continue": bool(payload.get("will_continue"))
                    if payload.get("will_continue") is not None
                    else None,
                }
            )
        return responses

    def _count_event_inline_data_parts(self, event: Any) -> int:
        content = getattr(event, "content", None)
        if content is None:
            return 0
        parts: Iterable[Any] = getattr(content, "parts", None) or []
        count = 0
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if not inline_data and isinstance(part, dict):
                inline_data = part.get("inline_data")
            if inline_data is not None:
                count += 1
        return count

    def _extract_event_actions(self, event: Any) -> Dict[str, Any]:
        actions = getattr(event, "actions", None)
        if actions is None:
            return {}

        payload = self._serialize_structured(actions) or {}
        if not isinstance(payload, dict):
            return {}

        picked: Dict[str, Any] = {}
        for key in (
            "requested_tool_confirmations",
            "requested_auth_configs",
            "transfer_to_agent",
            "escalate",
            "end_of_agent",
            "rewind_before_invocation_id",
            "state_delta",
            "artifact_delta",
            "agent_state",
        ):
            value = payload.get(key)
            if value in (None, "", [], {}):
                continue
            picked[key] = value
        return picked

    def _extract_event_long_running_tools(self, event: Any) -> List[str]:
        raw_ids = getattr(event, "long_running_tool_ids", None)
        if raw_ids is None:
            return []
        if isinstance(raw_ids, set):
            return sorted(str(item) for item in raw_ids if str(item).strip())
        if isinstance(raw_ids, (list, tuple)):
            return [str(item) for item in raw_ids if str(item).strip()]
        return [str(raw_ids)] if str(raw_ids).strip() else []

    def _extract_event_text(self, event: Any) -> str:
        content = getattr(event, "content", None)
        if content is None:
            return ""

        parts: Iterable[Any] = getattr(content, "parts", None) or []
        chunks: List[str] = []
        for part in parts:
            text = getattr(part, "text", None)
            if not text and isinstance(part, dict):
                text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
                continue

            function_call = getattr(part, "function_call", None)
            if not function_call and isinstance(part, dict):
                function_call = part.get("function_call")
            if function_call:
                name = getattr(function_call, "name", None)
                if not name and isinstance(function_call, dict):
                    name = function_call.get("name")
                chunks.append(f"[tool_call] {self._preview(name)}")
                continue

            function_response = getattr(part, "function_response", None)
            if not function_response and isinstance(part, dict):
                function_response = part.get("function_response")
            if function_response:
                payload = self._serialize_structured(function_response)
                chunks.append(f"[tool_result] {self._preview(payload)}")

        return "\n".join(chunk for chunk in chunks if chunk).strip()

    def _attach_event_extras(
        self,
        *,
        payload: Dict[str, Any],
        event: Any,
        invocation_id: str,
        actions: Dict[str, Any],
        long_running_tool_ids: List[str],
    ) -> Dict[str, Any]:
        if invocation_id:
            payload["invocation_id"] = invocation_id
        if actions:
            payload["actions"] = actions
        if long_running_tool_ids:
            payload["long_running_tool_ids"] = long_running_tool_ids

        function_calls = self._extract_event_function_calls(event)
        if function_calls:
            payload["function_calls"] = function_calls
        function_responses = self._extract_event_function_responses(event)
        if function_responses:
            payload["function_responses"] = function_responses
        return payload

    def _convert_event(self, event: Any) -> Optional[Dict[str, Any]]:
        invocation_id = str(getattr(event, "invocation_id", "") or "").strip()
        actions = self._extract_event_actions(event)
        long_running_tool_ids = self._extract_event_long_running_tools(event)
        function_calls = self._extract_event_function_calls(event)
        function_responses = self._extract_event_function_responses(event)

        error_message = str(getattr(event, "error_message", "") or "").strip()
        if error_message:
            payload: Dict[str, Any] = {
                "type": "error",
                "error": error_message,
                "error_code": str(getattr(event, "error_code", "") or "").strip(),
            }
            return self._attach_event_extras(
                payload=payload,
                event=event,
                invocation_id=invocation_id,
                actions=actions,
                long_running_tool_ids=long_running_tool_ids,
            )

        text = self._extract_event_text(event)
        author = str(getattr(event, "author", "") or "").strip()
        usage = self._serialize_structured(getattr(event, "usage_metadata", None)) or {}
        is_final = False
        try:
            if callable(getattr(event, "is_final_response", None)):
                is_final = bool(event.is_final_response())
        except Exception:
            is_final = False

        if is_final:
            payload = {
                "type": "final",
                "content": text,
                "author": author,
                "usage": usage if isinstance(usage, dict) else {},
                "is_final": True,
            }
            return self._attach_event_extras(
                payload=payload,
                event=event,
                invocation_id=invocation_id,
                actions=actions,
                long_running_tool_ids=long_running_tool_ids,
            )

        text_lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        only_tool_markers = bool(text_lines) and all(
            line.startswith("[tool_call]") or line.startswith("[tool_result]")
            for line in text_lines
        )

        if text and not (only_tool_markers and (actions or function_calls or function_responses)):
            payload = {
                "type": "chunk",
                "content": text,
                "author": author,
                "usage": usage if isinstance(usage, dict) else {},
                "is_final": False,
            }
            return self._attach_event_extras(
                payload=payload,
                event=event,
                invocation_id=invocation_id,
                actions=actions,
                long_running_tool_ids=long_running_tool_ids,
            )

        if actions or long_running_tool_ids or invocation_id or function_calls or function_responses:
            payload = {"type": "action", "is_final": False}
            return self._attach_event_extras(
                payload=payload,
                event=event,
                invocation_id=invocation_id,
                actions=actions,
                long_running_tool_ids=long_running_tool_ids,
            )

        return None

    def _build_live_blob_payload(self, payload: Dict[str, Any]) -> Any:
        if self._Blob is None:
            raise RuntimeError("ADK Blob type is unavailable")

        if hasattr(self._Blob, "model_validate"):
            try:
                return self._Blob.model_validate(payload)
            except Exception as exc:
                raise ValueError(f"invalid live blob payload: {exc}") from exc
        try:
            return self._Blob(**payload)  # type: ignore[misc]
        except Exception as exc:
            raise ValueError(f"invalid live blob payload: {exc}") from exc

    def _coerce_live_request(
        self,
        *,
        item: Dict[str, Any],
        default_role: str = "user",
    ) -> Any:
        if self._LiveRequestClass is None:
            raise RuntimeError("ADK LiveRequest type is unavailable")

        activity_start_aliases = {"activity_start", "activity-start", "start"}
        activity_end_aliases = {"activity_end", "activity-end", "end"}
        alias_values = [
            str(item.get("kind") or "").strip().lower(),
            str(item.get("type") or "").strip().lower(),
        ]
        has_activity_start = "activity_start" in item or any(
            value in activity_start_aliases for value in alias_values
        )
        has_activity_end = "activity_end" in item or any(
            value in activity_end_aliases for value in alias_values
        )
        if has_activity_start and has_activity_end:
            raise ValueError("live request cannot include both activity_start and activity_end")

        if any(key in item for key in ("content", "blob", "activity_start", "activity_end", "close")):
            if hasattr(self._LiveRequestClass, "model_validate"):
                return self._LiveRequestClass.model_validate(item)
            return self._LiveRequestClass(**item)  # type: ignore[misc]

        kind = str(item.get("kind") or item.get("type") or "text").strip().lower()
        if kind in {"activity_start", "activity-start", "start"}:
            return self._LiveRequestClass(activity_start={})
        if kind in {"activity_end", "activity-end", "end"}:
            return self._LiveRequestClass(activity_end={})
        if kind in {"close", "stop"}:
            return self._LiveRequestClass(close=True)

        if kind in {"realtime", "blob", "audio", "image"}:
            blob_payload = item.get("blob")
            if not isinstance(blob_payload, dict):
                mime_type = str(item.get("mime_type") or item.get("mimeType") or "").strip()
                if not mime_type:
                    raise ValueError("live blob request requires mime_type")
                raw_data = item.get("data")
                if isinstance(raw_data, str):
                    data = raw_data
                elif isinstance(raw_data, (bytes, bytearray)):
                    data = base64.b64encode(bytes(raw_data)).decode("ascii")
                else:
                    raise ValueError("live blob request requires base64 data")
                blob_payload = {"mime_type": mime_type, "data": data}
            blob = self._build_live_blob_payload(blob_payload)
            return self._LiveRequestClass(blob=blob)

        if kind in {"function_response", "tool_response"}:
            function_response = item.get("function_response")
            if not isinstance(function_response, dict):
                raise ValueError("function_response request requires function_response object")
            content = self._build_new_message(
                input_data=None,
                input_message={
                    "role": item.get("role", default_role),
                    "parts": [{"function_response": function_response}],
                },
            )
            return self._LiveRequestClass(content=content)

        # default text/content request
        text = str(item.get("text") or item.get("input") or "").strip()
        if not text:
            raise ValueError("text live request requires text")
        content = self._build_new_message(
            input_data=None,
            input_message={
                "role": item.get("role", default_role),
                "parts": [{"text": text}],
            },
        )
        return self._LiveRequestClass(content=content)

    def _enqueue_live_requests(
        self,
        *,
        live_request_queue: Any,
        input_data: Optional[str],
        live_requests: Optional[List[Dict[str, Any]]],
        close_queue: bool,
    ) -> None:
        normalized_requests = live_requests if isinstance(live_requests, list) else []
        for idx, item in enumerate(normalized_requests):
            if not isinstance(item, dict):
                raise ValueError(f"live_requests[{idx}] must be an object")
            request_obj = self._coerce_live_request(item=item)
            live_request_queue.send(request_obj)

        if not normalized_requests and str(input_data or "").strip():
            request_obj = self._coerce_live_request(item={"kind": "text", "text": str(input_data or "")})
            live_request_queue.send(request_obj)

        if close_queue:
            live_request_queue.close()

    def _convert_live_event(self, event: Any) -> Optional[Dict[str, Any]]:
        payload = self._convert_event(event)
        if payload is None:
            payload = {"type": "live_event", "is_final": False}

        partial = bool(getattr(event, "partial", False))
        turn_complete = bool(getattr(event, "turn_complete", False))
        interrupted = bool(getattr(event, "interrupted", False))

        payload["partial"] = partial
        payload["turn_complete"] = turn_complete
        payload["interrupted"] = interrupted

        inline_data_parts = self._count_event_inline_data_parts(event)
        if inline_data_parts:
            payload["inline_data_parts"] = inline_data_parts

        input_transcription = self._serialize_structured(getattr(event, "input_transcription", None))
        if input_transcription:
            payload["input_transcription"] = input_transcription
        output_transcription = self._serialize_structured(getattr(event, "output_transcription", None))
        if output_transcription:
            payload["output_transcription"] = output_transcription
        resumption_update = self._serialize_structured(
            getattr(event, "live_session_resumption_update", None)
        )
        if resumption_update:
            payload["live_session_resumption_update"] = resumption_update

        if turn_complete and not payload.get("is_final"):
            payload["is_final"] = True
            if str(payload.get("type") or "") in {"chunk", "action", "live_event"}:
                payload["type"] = "final"

        if not payload.get("content"):
            text = self._extract_event_text(event)
            if text:
                payload["content"] = text

        if bool(payload.get("is_final")):
            return self._attach_accuracy_signals(payload)
        return payload

    async def run(
        self,
        user_id: str,
        session_id: str,
        input_data: Optional[str] = None,
        input_message: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        google_api_key: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
        state_delta: Optional[Dict[str, Any]] = None,
        invocation_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        运行智能体（流式）。

        Args:
            user_id: 用户 ID
            session_id: 会话 ID（业务侧）
            input_data: 用户输入（文本）
            input_message: 结构化消息（兼容 ADK Content parts）
            tools: 预留字段（兼容旧调用方）
            google_api_key: Google API Key（仅 ADK 路径需要）
            run_config: ADK RunConfig 配置（官方字段）
            state_delta: 本次调用附带的状态增量
            invocation_id: 可选，用于续跑同一次 invocation
        """
        _ = tools
        await self._get_or_create_session(user_id=user_id, session_id=session_id)

        if not self._adk_available or not self._adk_runner:
            yield self._build_runtime_unavailable_error(
                stage="run",
                session_id=session_id,
            )
            return

        lock = self._get_google_api_key_lock() if google_api_key else None
        if lock:
            async with lock:
                async for event in self._run_adk_stream(
                    user_id=user_id,
                    session_id=session_id,
                    input_data=input_data,
                    input_message=input_message,
                    google_api_key=google_api_key,
                    run_config=run_config,
                    state_delta=state_delta,
                    invocation_id=invocation_id,
                ):
                    yield event
            return

        async for event in self._run_adk_stream(
            user_id=user_id,
            session_id=session_id,
            input_data=input_data,
            input_message=input_message,
            google_api_key=google_api_key,
            run_config=run_config,
            state_delta=state_delta,
            invocation_id=invocation_id,
        ):
            yield event

    async def _run_adk_stream(
        self,
        user_id: str,
        session_id: str,
        input_data: Optional[str],
        input_message: Optional[Dict[str, Any]],
        google_api_key: Optional[str],
        run_config: Optional[Dict[str, Any]],
        state_delta: Optional[Dict[str, Any]],
        invocation_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            await self._ensure_adk_session(user_id=user_id, session_id=session_id)
            new_message = self._build_new_message(
                input_data=input_data,
                input_message=input_message,
            )
            adk_run_config = self._build_run_config(run_config)

            final_text = ""
            usage: Dict[str, Any] = {}
            author = ""
            chunk_buffer: List[str] = []
            final_invocation_id = str(invocation_id or "").strip()
            final_actions: Dict[str, Any] = {}
            final_long_running_tools: List[str] = []

            with self._temporary_google_api_key(google_api_key):
                run_kwargs: Dict[str, Any] = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "new_message": new_message,
                    "run_config": adk_run_config,
                }
                normalized_invocation_id = str(invocation_id or "").strip()
                if normalized_invocation_id:
                    run_kwargs["invocation_id"] = normalized_invocation_id
                if isinstance(state_delta, dict) and state_delta:
                    run_kwargs["state_delta"] = state_delta

                async for raw_event in self._adk_runner.run_async(**run_kwargs):  # type: ignore[union-attr]
                    parsed_event = self._convert_event(raw_event)
                    if not parsed_event:
                        continue

                    raw_invocation_id = str(parsed_event.get("invocation_id") or "").strip()
                    if raw_invocation_id:
                        final_invocation_id = raw_invocation_id
                    raw_actions = parsed_event.get("actions")
                    if isinstance(raw_actions, dict) and raw_actions:
                        final_actions = raw_actions
                    raw_long_running = parsed_event.get("long_running_tool_ids")
                    if isinstance(raw_long_running, list) and raw_long_running:
                        final_long_running_tools = raw_long_running

                    event_type = str(parsed_event.get("type") or "").strip()
                    if event_type == "error":
                        yield parsed_event
                        continue
                    if event_type == "chunk":
                        chunk = str(parsed_event.get("content") or "").strip()
                        if chunk:
                            chunk_buffer.append(chunk)
                            yield parsed_event
                        continue
                    if event_type == "action":
                        yield parsed_event
                        continue
                    if event_type == "final":
                        final_text = str(parsed_event.get("content") or "").strip()
                        if isinstance(parsed_event.get("usage"), dict):
                            usage = parsed_event.get("usage") or {}
                        author = str(parsed_event.get("author") or "").strip()

            if not final_text:
                final_text = "\n".join(chunk_buffer).strip()

            final_payload: Dict[str, Any] = {
                "type": "content",
                "content": final_text,
                "is_final": True,
                "author": author,
                "usage": usage,
                "session_id": session_id,
            }
            if final_invocation_id:
                final_payload["invocation_id"] = final_invocation_id
            if final_actions:
                final_payload["actions"] = final_actions
            if final_long_running_tools:
                final_payload["long_running_tool_ids"] = final_long_running_tools
            yield self._attach_accuracy_signals(final_payload)

            await self._get_or_create_session(
                user_id=user_id,
                session_id=session_id,
                extra_metadata={
                    "last_invocation_id": final_invocation_id or None,
                    "last_run_config": run_config if isinstance(run_config, dict) else None,
                    "last_state_delta": state_delta if isinstance(state_delta, dict) else None,
                    "last_long_running_tool_ids": final_long_running_tools or None,
                },
            )
        except ValueError as exc:
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "ADK_INVALID_REQUEST",
                "stage": "run",
                "hint": "Check input payload schema and run_config values.",
                "retryable": False,
                "is_final": True,
                "invalid_request": True,
                "session_id": session_id,
            }
        except Exception as exc:
            logger.error("[ADKRunner] Error running ADK agent: %s", exc, exc_info=True)
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "ADK_RUN_FAILED",
                "stage": "run",
                "hint": "Check ADK runtime logs and provider credentials.",
                "retryable": False,
                "is_final": True,
                "session_id": session_id,
            }

    async def run_live(
        self,
        *,
        user_id: str,
        session_id: str,
        input_data: Optional[str] = None,
        live_requests: Optional[List[Dict[str, Any]]] = None,
        google_api_key: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
        close_queue: bool = True,
        max_events: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        await self._get_or_create_session(user_id=user_id, session_id=session_id)

        if not self._adk_available or not self._adk_runner:
            yield self._build_runtime_unavailable_error(
                stage="run_live",
                session_id=session_id,
            )
            return
        if self._LiveRequestQueueClass is None:
            yield self._build_runtime_unavailable_error(
                stage="run_live",
                session_id=session_id,
                detail="ADK LiveRequestQueue is unavailable",
            )
            return

        lock = self._get_google_api_key_lock() if google_api_key else None
        if lock:
            async with lock:
                async for event in self._run_adk_live_stream(
                    user_id=user_id,
                    session_id=session_id,
                    input_data=input_data,
                    live_requests=live_requests,
                    google_api_key=google_api_key,
                    run_config=run_config,
                    close_queue=close_queue,
                    max_events=max_events,
                ):
                    yield event
            return

        async for event in self._run_adk_live_stream(
            user_id=user_id,
            session_id=session_id,
            input_data=input_data,
            live_requests=live_requests,
            google_api_key=google_api_key,
            run_config=run_config,
            close_queue=close_queue,
            max_events=max_events,
        ):
            yield event

    async def _run_adk_live_stream(
        self,
        *,
        user_id: str,
        session_id: str,
        input_data: Optional[str],
        live_requests: Optional[List[Dict[str, Any]]],
        google_api_key: Optional[str],
        run_config: Optional[Dict[str, Any]],
        close_queue: bool,
        max_events: Optional[int],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            await self._ensure_adk_session(user_id=user_id, session_id=session_id)
            live_queue = self._LiveRequestQueueClass()  # type: ignore[misc]
            self._enqueue_live_requests(
                live_request_queue=live_queue,
                input_data=input_data,
                live_requests=live_requests,
                close_queue=close_queue,
            )
            adk_run_config = self._build_run_config(run_config)

            event_count = 0
            final_invocation_id = ""
            final_actions: Dict[str, Any] = {}
            final_long_running_tools: List[str] = []

            with self._temporary_google_api_key(google_api_key):
                async for raw_event in self._adk_runner.run_live(  # type: ignore[union-attr]
                    user_id=user_id,
                    session_id=session_id,
                    live_request_queue=live_queue,
                    run_config=adk_run_config,
                ):
                    parsed = self._convert_live_event(raw_event)
                    if not parsed:
                        continue
                    event_count += 1

                    invocation_id = str(parsed.get("invocation_id") or "").strip()
                    if invocation_id:
                        final_invocation_id = invocation_id
                    raw_actions = parsed.get("actions")
                    if isinstance(raw_actions, dict) and raw_actions:
                        final_actions = raw_actions
                    raw_long_running = parsed.get("long_running_tool_ids")
                    if isinstance(raw_long_running, list) and raw_long_running:
                        final_long_running_tools = raw_long_running

                    yield parsed

                    if isinstance(max_events, int) and max_events > 0 and event_count >= max_events:
                        break

            await self._get_or_create_session(
                user_id=user_id,
                session_id=session_id,
                extra_metadata={
                    "last_invocation_id": final_invocation_id or None,
                    "last_run_config": run_config if isinstance(run_config, dict) else None,
                    "last_long_running_tool_ids": final_long_running_tools or None,
                    "last_actions": final_actions or None,
                    "last_live_event_count": event_count,
                },
            )
        except ValueError as exc:
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "ADK_INVALID_REQUEST",
                "stage": "run_live",
                "hint": "Check live_requests payload schema and run_config values.",
                "retryable": False,
                "is_final": True,
                "invalid_request": True,
                "session_id": session_id,
            }
        except Exception as exc:
            logger.error("[ADKRunner] Error running ADK live stream: %s", exc, exc_info=True)
            yield {
                "type": "error",
                "error": str(exc),
                "error_code": "ADK_RUN_LIVE_FAILED",
                "stage": "run_live",
                "hint": "Check ADK live runtime setup and request payload.",
                "retryable": False,
                "is_final": True,
                "session_id": session_id,
            }

    async def run_once(
        self,
        user_id: str,
        session_id: str,
        input_data: Optional[str] = None,
        input_message: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        google_api_key: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
        state_delta: Optional[Dict[str, Any]] = None,
        invocation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        非流式封装：消费 run() 并返回最终文本。
        """
        final_text = ""
        usage: Dict[str, Any] = {}
        event_count = 0
        final_invocation_id = str(invocation_id or "").strip()
        final_actions: Dict[str, Any] = {}
        long_running_tool_ids: List[str] = []
        response_signature = ""
        action_signature = ""

        async for event in self.run(
            user_id=user_id,
            session_id=session_id,
            input_data=input_data,
            input_message=input_message,
            tools=tools,
            google_api_key=google_api_key,
            run_config=run_config,
            state_delta=state_delta,
            invocation_id=invocation_id,
        ):
            event_count += 1
            if str(event.get("type") or "") == "error":
                if bool(event.get("invalid_request")):
                    raise ValueError(str(event.get("error") or "invalid adk request"))
                raise RuntimeError(str(event.get("error") or "ADK runner failed"))

            raw_invocation = str(event.get("invocation_id") or "").strip()
            if raw_invocation:
                final_invocation_id = raw_invocation
            if isinstance(event.get("actions"), dict) and event.get("actions"):
                final_actions = event.get("actions") or {}
            raw_long_running = event.get("long_running_tool_ids")
            if isinstance(raw_long_running, list) and raw_long_running:
                long_running_tool_ids = raw_long_running
            raw_response_signature = str(event.get("response_signature") or "").strip()
            if raw_response_signature:
                response_signature = raw_response_signature
            raw_action_signature = str(event.get("action_signature") or "").strip()
            if raw_action_signature:
                action_signature = raw_action_signature

            if bool(event.get("is_final")):
                final_text = str(event.get("content") or "").strip()
                if isinstance(event.get("usage"), dict):
                    usage = event.get("usage") or {}

        if not response_signature or not action_signature:
            generated_signals = compute_adk_accuracy_signals(
                content=final_text,
                actions=final_actions,
                long_running_tool_ids=long_running_tool_ids,
            )
            if not response_signature:
                response_signature = generated_signals["response_signature"]
            if not action_signature:
                action_signature = generated_signals["action_signature"]

        return {
            "text": final_text,
            "usage": usage,
            "event_count": event_count,
            "session_id": session_id,
            "invocation_id": final_invocation_id,
            "actions": final_actions,
            "long_running_tool_ids": long_running_tool_ids,
            "response_signature": response_signature,
            "action_signature": action_signature,
        }

    async def rewind(
        self,
        *,
        user_id: str,
        session_id: str,
        rewind_before_invocation_id: str,
        google_api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_target = str(rewind_before_invocation_id or "").strip()
        if not normalized_target:
            raise ValueError("rewind_before_invocation_id is required")
        if not self._adk_available or not self._adk_runner:
            raise RuntimeError("ADK runner is unavailable; cannot rewind")

        await self._get_or_create_session(user_id=user_id, session_id=session_id)
        await self._ensure_adk_session(user_id=user_id, session_id=session_id)

        lock = self._get_google_api_key_lock() if google_api_key else None
        if lock:
            async with lock:
                with self._temporary_google_api_key(google_api_key):
                    await self._maybe_await(
                        self._adk_runner.rewind_async(  # type: ignore[union-attr]
                            user_id=user_id,
                            session_id=session_id,
                            rewind_before_invocation_id=normalized_target,
                        )
                    )
        else:
            with self._temporary_google_api_key(google_api_key):
                await self._maybe_await(
                    self._adk_runner.rewind_async(  # type: ignore[union-attr]
                        user_id=user_id,
                        session_id=session_id,
                        rewind_before_invocation_id=normalized_target,
                    )
                )

        await self._get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            extra_metadata={"last_rewind_before_invocation_id": normalized_target},
        )
        return {
            "ok": True,
            "user_id": user_id,
            "session_id": session_id,
            "rewind_before_invocation_id": normalized_target,
        }

    def _serialize_session_snapshot(self, session_obj: Any) -> Dict[str, Any]:
        payload = self._serialize_structured(session_obj) or {}
        if not isinstance(payload, dict):
            return {"raw": payload}

        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        return {
            "session_id": str(payload.get("id") or ""),
            "app_name": str(payload.get("app_name") or payload.get("appName") or ""),
            "user_id": str(payload.get("user_id") or payload.get("userId") or ""),
            "state": payload.get("state") if isinstance(payload.get("state"), dict) else {},
            "event_count": len(events),
            "last_update_time": payload.get("last_update_time") or payload.get("lastUpdateTime"),
            "events": events,
        }

    async def list_sessions(self, *, user_id: str) -> List[Dict[str, Any]]:
        db_sessions = self.db.query(ADKSession).filter(
            ADKSession.user_id == user_id,
            ADKSession.agent_id == self.agent_id,
        ).order_by(ADKSession.last_used_at.desc()).all()

        merged: Dict[str, Dict[str, Any]] = {}
        for db_row in db_sessions:
            payload = db_row.to_dict()
            session_id = str(payload.get("session_id") or "").strip()
            if not session_id:
                continue
            merged[session_id] = {
                "session_id": session_id,
                "created_at": payload.get("created_at"),
                "last_used_at": payload.get("last_used_at"),
                "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
                "runtime_available": False,
            }

        if self._session_service:
            try:
                response = await self._maybe_await(
                    self._session_service.list_sessions(app_name=self.app_name, user_id=user_id)
                )
                sessions = getattr(response, "sessions", None) or []
                for runtime_session in sessions:
                    snapshot = self._serialize_session_snapshot(runtime_session)
                    session_id = str(snapshot.get("session_id") or "").strip()
                    if not session_id:
                        continue
                    current = merged.get(session_id, {"session_id": session_id})
                    current.update({
                        "runtime_available": True,
                        "runtime_event_count": snapshot.get("event_count"),
                        "runtime_last_update_time": snapshot.get("last_update_time"),
                        "runtime_state": snapshot.get("state") or {},
                    })
                    merged[session_id] = current
            except Exception:
                logger.warning("[ADKRunner] list_sessions from ADK session service failed", exc_info=True)

        ordered = sorted(
            merged.values(),
            key=lambda item: int(item.get("last_used_at") or 0),
            reverse=True,
        )
        return ordered

    async def get_session_snapshot(self, *, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None

        db_row = self.db.query(ADKSession).filter(
            ADKSession.user_id == user_id,
            ADKSession.agent_id == self.agent_id,
            ADKSession.session_id == normalized_session_id,
        ).first()
        if db_row is None:
            return None

        payload = db_row.to_dict()
        snapshot: Dict[str, Any] = {
            "session_id": normalized_session_id,
            "created_at": payload.get("created_at"),
            "last_used_at": payload.get("last_used_at"),
            "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            "runtime_available": False,
            "runtime_state": {},
            "runtime_event_count": 0,
            "events": [],
        }

        if self._session_service:
            try:
                runtime_session = await self._maybe_await(
                    self._session_service.get_session(
                        app_name=self.app_name,
                        user_id=user_id,
                        session_id=normalized_session_id,
                    )
                )
                if runtime_session is not None:
                    serialized_runtime = self._serialize_session_snapshot(runtime_session)
                    snapshot.update({
                        "runtime_available": True,
                        "runtime_state": serialized_runtime.get("state") or {},
                        "runtime_event_count": serialized_runtime.get("event_count") or 0,
                        "runtime_last_update_time": serialized_runtime.get("last_update_time"),
                        "events": serialized_runtime.get("events") or [],
                    })
            except Exception:
                logger.warning("[ADKRunner] get_session_snapshot from ADK session service failed", exc_info=True)

        return snapshot

    async def _get_or_create_session(
        self,
        user_id: str,
        session_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = self.db.query(ADKSession).filter(
            ADKSession.user_id == user_id,
            ADKSession.agent_id == self.agent_id,
            ADKSession.session_id == session_id,
        ).first()

        now = int(time.time() * 1000)
        if session:
            metadata = self._safe_json_loads(session.metadata_json, {}) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            metadata.update({
                "app_name": self.app_name,
                "adk_available": bool(self._adk_available),
            })
            if isinstance(extra_metadata, dict):
                for key, value in extra_metadata.items():
                    if value is not None:
                        metadata[key] = value
            session.metadata_json = json.dumps(metadata, ensure_ascii=False)
            session.last_used_at = now
            self.db.commit()
            return session.to_dict()

        initial_metadata: Dict[str, Any] = {
            "app_name": self.app_name,
            "adk_available": bool(self._adk_available),
        }
        if isinstance(extra_metadata, dict):
            for key, value in extra_metadata.items():
                if value is not None:
                    initial_metadata[key] = value

        session = ADKSession(
            user_id=user_id,
            agent_id=self.agent_id,
            session_id=session_id,
            metadata_json=json.dumps(initial_metadata, ensure_ascii=False),
            created_at=now,
            last_used_at=now,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info("[ADKRunner] Created session %s for user %s", session_id, user_id)
        return session.to_dict()
