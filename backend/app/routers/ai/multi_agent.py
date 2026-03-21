"""
Multi-Agent API Router - 多智能体系统 API 路由

提供：
- POST /api/multi-agent/orchestrate：兼容编排入口（deprecated，推荐改用 provider mode）
- GET /api/multi-agent/agents：列出可用智能体
- POST /api/multi-agent/agents/register：注册智能体
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session
import logging
import time
import threading
import uuid
import os
import json
import base64
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from ...core.config import settings
from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.credential_manager import get_provider_credentials
from ...models.db_models import AgentRegistry, MessageAttachment
from ...services.gemini.agent.adk_runtime_contract import (
    ADKRuntimeErrorCode,
    build_adk_runtime_http_exception,
    is_adk_runtime_fallback_allowed,
    normalize_adk_runtime_strategy,
)
from ...services.gemini.agent.orchestrator import Orchestrator
from ...services.gemini.agent.agent_registry import AgentRegistryService
from ...services.gemini.agent.adk_agent import ADKAgent
from ...services.agent.adk_builtin_tools import (
    SHEET_STAGE_PROTOCOL_VERSION,
    build_adk_builtin_tools,
    build_sheet_stage_envelope,
    normalize_sheet_artifact_ref,
    normalize_sheet_stage,
    validate_sheet_artifact_binding,
    validate_sheet_export_precheck,
)
from ...services.agent.sheet_policy_hooks import (
    apply_row_level_policy_hook,
    assert_stage_row_level_policy_pair,
)
from ...services.agent.export_policy import enforce_sheet_export_constraint
from ...services.agent.adk_artifact_service import (
    ADKArtifactBindingError,
    ADKArtifactLineageError,
    ADKArtifactNotFoundError,
    ADKArtifactService,
    ADKArtifactSessionError,
)
from ...services.agent.workflow_runtime_store import create_workflow_runtime_store
from ...services.gemini.agent.adk_runner import (
    ADKRunner,
    compute_adk_accuracy_signals,
    validate_adk_run_config_allowlist,
)
from ...services.gemini.agent.memory_manager import MemoryManager
from ...services.gemini.agent.memory_bank_service import VertexAiMemoryBankService
from ...services.common.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)

try:
    from ...services.agent.sheet_stage_protocol_service import (
        SheetStageProtocolError,
        execute_sheet_stage_protocol_request,
        get_default_sheet_stage_artifact_service,
        get_default_sheet_stage_runtime_store,
    )
except ModuleNotFoundError:  # pragma: no cover - stub-only tests may blank package paths
    class SheetStageProtocolError(Exception):
        def __init__(self, *args, status_code: int = 500, detail: Any = None, **kwargs):
            super().__init__(*args)
            self.status_code = int(status_code)
            self.detail = detail

    execute_sheet_stage_protocol_request = None  # type: ignore[assignment]

    def get_default_sheet_stage_runtime_store():
        return create_workflow_runtime_store()

    def get_default_sheet_stage_artifact_service():
        return ADKArtifactService(
            runtime_store=get_default_sheet_stage_runtime_store(),
            namespace="sheet-stage",
        )

try:
    from ...services.gemini.agent.orchestrator import (
        classify_orchestration_http_exception as _classify_orchestration_http_exception,
    )
except Exception:
    _classify_orchestration_http_exception = None

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])
ADK_REQUEST_CONFIRMATION_FUNCTION_NAME = "adk_request_confirmation"
ADK_CONFIRM_NONCE_REPLAY_WINDOW_SECONDS = 30 * 60
ADK_CONFIRM_NONCE_MAX_CACHE_SIZE = 50000
ADK_CONFIRM_TICKET_MAX_TTL_SECONDS = 30 * 60
ADK_CONFIRM_TICKET_MAX_FUTURE_SKEW_MS = 60 * 1000
LEGACY_ORCHESTRATE_REPLACEMENT_PATH = "/api/modes/{provider}/multi-agent"
LEGACY_ORCHESTRATE_RUNTIME_KIND = "google-adk"
LEGACY_ORCHESTRATE_PROVIDER_SCOPE = "google"
_ADK_CONFIRM_NONCE_LOCK = threading.Lock()
_ADK_CONFIRM_USED_NONCES: Dict[str, int] = {}
_SHEET_STAGE_LOCK = threading.Lock()
_SHEET_STAGE_MAX_SESSION_CACHE_SIZE = 2000
_SHEET_STAGE_SESSIONS: Dict[str, Dict[str, Any]] = {}
_sheet_stage_runtime_store = get_default_sheet_stage_runtime_store()
_sheet_stage_artifact_service = get_default_sheet_stage_artifact_service()


# ==================== Health Check Endpoint ====================

@router.get("/health")
async def health_check():
    """健康检查端点，用于验证路由是否正常工作"""
    return {"status": "ok", "message": "Multi-Agent API is working"}


# ==================== Request/Response Models ====================

class OrchestrateRequest(BaseModel):
    """编排任务请求"""
    task: str
    agent_ids: Optional[List[str]] = None
    mode: Optional[str] = None  # 模式：coordinator, sequential, parallel, default
    workflow_config: Optional[Dict[str, Any]] = None  # 工作流配置（用于 sequential/parallel 模式）


class RegisterAgentRequest(BaseModel):
    """注册智能体请求"""
    name: str
    agent_type: str
    agent_card: Optional[Dict[str, Any]] = None
    endpoint_url: Optional[str] = None
    tools: Optional[List[str]] = None  # 工具名称列表
    mcp_session_id: Optional[str] = None  # MCP 会话 ID（用于加载 MCP 工具）


class ADKRunRequest(BaseModel):
    """ADK 运行请求"""
    input: Optional[str] = None
    input_message: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    run_config: Optional[Dict[str, Any]] = None
    state_delta: Optional[Dict[str, Any]] = None
    invocation_id: Optional[str] = None


class ADKLiveRunRequest(BaseModel):
    """ADK live 运行请求"""
    input: Optional[str] = None
    session_id: Optional[str] = None
    run_config: Optional[Dict[str, Any]] = None
    live_requests: Optional[List[Dict[str, Any]]] = None
    close_queue: Optional[bool] = True
    max_events: Optional[int] = 200


class ADKToolConfirmationRequest(BaseModel):
    """ADK 工具确认恢复请求"""
    model_config = ConfigDict(populate_by_name=True)

    function_call_id: str = Field(..., alias="functionCallId")
    confirmed: Optional[bool] = False
    hint: Optional[str] = None
    payload: Optional[Any] = None
    invocation_id: Optional[str] = Field(default=None, alias="invocationId")
    nonce: Optional[str] = None
    approval_ticket: Optional[Dict[str, Any]] = Field(default=None, alias="approvalTicket")
    # 兼容历史前端字段（BE-601），用于物化 approval_ticket 对象。
    ticket: Optional[Any] = None
    confirmation_ticket: Optional[Any] = Field(default=None, alias="confirmationTicket")
    nonce_expires_at: Optional[Any] = Field(default=None, alias="nonceExpiresAt")
    nonce_expiry: Optional[Any] = Field(default=None, alias="nonceExpiry")
    tenant_id: Optional[str] = Field(default=None, alias="tenantId")
    ticket_timestamp_ms: Optional[Any] = Field(default=None, alias="ticketTimestampMs")
    ticket_ttl_seconds: Optional[Any] = Field(default=None, alias="ticketTtlSeconds")
    run_config: Optional[Dict[str, Any]] = Field(default=None, alias="runConfig")


class ADKRewindRequest(BaseModel):
    """ADK rewind 请求"""
    model_config = ConfigDict(populate_by_name=True)

    rewind_before_invocation_id: str = Field(..., alias="rewindBeforeInvocationId")


class ADKSessionMemoryIndexRequest(BaseModel):
    """会话记忆索引请求"""
    memory_bank_id: Optional[str] = None
    project: Optional[str] = None
    location: Optional[str] = None
    agent_engine_id: Optional[str] = None


class ADKMemorySearchRequest(BaseModel):
    """记忆搜索请求"""
    query: str
    memory_bank_id: Optional[str] = None
    limit: Optional[int] = 10
    project: Optional[str] = None
    location: Optional[str] = None
    agent_engine_id: Optional[str] = None


def _normalize_provider_id(value: Any) -> str:
    return str(value or "").strip().lower()


def _build_adk_session_id(agent_id: str) -> str:
    safe_agent = "".join(ch for ch in str(agent_id or "") if ch.isalnum() or ch in {"-", "_"})[:32] or "agent"
    return f"adk-{safe_agent}-{int(time.time() * 1000)}"


def _pick_first_value(payload: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _pick_first_text(payload: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        text = str(payload.get(key) or "").strip()
        if text:
            return text
    return ""


def _parse_ticket_timestamp_ms(raw_value: Any) -> int:
    if isinstance(raw_value, bool):
        raise ValueError("invalid ticket timestamp")
    if isinstance(raw_value, (int, float)):
        numeric = int(raw_value)
    else:
        text = str(raw_value or "").strip()
        if not text:
            raise ValueError("missing ticket timestamp")
        try:
            numeric = int(float(text))
        except Exception as exc:
            raise ValueError("invalid ticket timestamp") from exc
    if numeric < 10_000_000_000:
        numeric *= 1000
    if numeric <= 0:
        raise ValueError("invalid ticket timestamp")
    return numeric


def _parse_ticket_ttl_seconds(raw_value: Any) -> int:
    if isinstance(raw_value, bool):
        raise ValueError("invalid ticket ttl")
    if isinstance(raw_value, (int, float)):
        ttl_seconds = int(raw_value)
    else:
        text = str(raw_value or "").strip()
        if not text:
            raise ValueError("missing ticket ttl")
        try:
            ttl_seconds = int(float(text))
        except Exception as exc:
            raise ValueError("invalid ticket ttl") from exc
    if ttl_seconds <= 0 or ttl_seconds > ADK_CONFIRM_TICKET_MAX_TTL_SECONDS:
        raise ValueError(
            f"invalid ticket ttl: expected 1..{ADK_CONFIRM_TICKET_MAX_TTL_SECONDS} seconds"
        )
    return ttl_seconds


def _parse_legacy_expiry_timestamp_ms(raw_value: Any) -> int:
    if raw_value is None:
        raise ValueError("missing nonce expiry")
    if isinstance(raw_value, bool):
        raise ValueError("invalid nonce expiry")
    if isinstance(raw_value, (int, float)):
        return _parse_ticket_timestamp_ms(raw_value)

    text = str(raw_value or "").strip()
    if not text:
        raise ValueError("missing nonce expiry")
    try:
        return _parse_ticket_timestamp_ms(text)
    except Exception:
        pass

    iso_text = text
    if iso_text.endswith("Z"):
        iso_text = f"{iso_text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(iso_text)
    except Exception as exc:
        raise ValueError("invalid nonce expiry") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    timestamp_ms = int(parsed.timestamp() * 1000)
    if timestamp_ms <= 0:
        raise ValueError("invalid nonce expiry")
    return timestamp_ms


def _coerce_approval_ticket_legacy_object(raw_value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    text = str(raw_value or "").strip()
    if not text:
        return None
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"ticket": text}


def _materialize_approval_ticket_from_request(
    *,
    request_body: ADKToolConfirmationRequest,
    user_id: str,
    session_id: str,
    function_call_id: str,
) -> Optional[Dict[str, Any]]:
    if isinstance(request_body.approval_ticket, dict):
        return dict(request_body.approval_ticket)

    legacy_ticket = _coerce_approval_ticket_legacy_object(request_body.confirmation_ticket)
    if legacy_ticket is None:
        legacy_ticket = _coerce_approval_ticket_legacy_object(request_body.ticket)
    if legacy_ticket is None:
        return None

    now_ms = int(time.time() * 1000)
    approval_ticket = dict(legacy_ticket)
    approval_ticket.setdefault("session_id", str(session_id or "").strip())
    approval_ticket.setdefault("function_call_id", str(function_call_id or "").strip())

    invocation_id = str(request_body.invocation_id or "").strip()
    if invocation_id:
        approval_ticket.setdefault("invocation_id", invocation_id)

    tenant_id = str(request_body.tenant_id or "").strip() or str(user_id or "").strip()
    if tenant_id:
        approval_ticket.setdefault("tenant_id", tenant_id)

    nonce = str(request_body.nonce or "").strip()
    if nonce:
        approval_ticket.setdefault("nonce", nonce)

    if request_body.ticket_timestamp_ms is not None:
        approval_ticket.setdefault("timestamp_ms", request_body.ticket_timestamp_ms)
    if request_body.ticket_ttl_seconds is not None:
        approval_ticket.setdefault("ttl_seconds", request_body.ticket_ttl_seconds)

    if _pick_first_value(approval_ticket, ["timestamp_ms", "timestampMs", "issued_at_ms", "issuedAtMs", "timestamp", "issued_at"]) is None:
        legacy_expiry_raw = request_body.nonce_expires_at
        if legacy_expiry_raw is None or str(legacy_expiry_raw).strip() == "":
            legacy_expiry_raw = request_body.nonce_expiry
        if legacy_expiry_raw is not None and str(legacy_expiry_raw).strip() != "":
            expires_at_ms = _parse_legacy_expiry_timestamp_ms(legacy_expiry_raw)
            remaining_seconds = int((expires_at_ms - now_ms + 999) // 1000)
            if remaining_seconds > ADK_CONFIRM_TICKET_MAX_TTL_SECONDS:
                remaining_seconds = ADK_CONFIRM_TICKET_MAX_TTL_SECONDS
            if remaining_seconds > 0:
                approval_ticket.setdefault("timestamp_ms", now_ms)
                approval_ticket.setdefault("ttl_seconds", remaining_seconds)
            else:
                approval_ticket.setdefault("timestamp_ms", expires_at_ms - 1000)
                approval_ticket.setdefault("ttl_seconds", 1)

    return approval_ticket


def _build_confirm_nonce_cache_key(
    *,
    tenant_id: str,
    session_id: str,
    function_call_id: str,
    invocation_id: str,
    nonce: str,
) -> str:
    return "|".join(
        [
            str(tenant_id or "").strip(),
            str(session_id or "").strip(),
            str(function_call_id or "").strip(),
            str(invocation_id or "").strip(),
            str(nonce or "").strip(),
        ]
    )


def _prune_confirm_nonce_cache_locked(now_ms: int) -> None:
    expired_keys = [key for key, expires_at in _ADK_CONFIRM_USED_NONCES.items() if expires_at <= now_ms]
    for key in expired_keys:
        _ADK_CONFIRM_USED_NONCES.pop(key, None)

    overflow = len(_ADK_CONFIRM_USED_NONCES) - ADK_CONFIRM_NONCE_MAX_CACHE_SIZE
    if overflow > 0:
        for key, _expires_at in sorted(_ADK_CONFIRM_USED_NONCES.items(), key=lambda item: item[1])[:overflow]:
            _ADK_CONFIRM_USED_NONCES.pop(key, None)


def _consume_confirm_nonce_or_raise(
    *,
    tenant_id: str,
    session_id: str,
    function_call_id: str,
    invocation_id: str,
    nonce: str,
    expires_at_ms: int,
) -> None:
    now_ms = int(time.time() * 1000)
    normalized_expires_at_ms = max(
        int(expires_at_ms),
        now_ms + ADK_CONFIRM_NONCE_REPLAY_WINDOW_SECONDS * 1000,
    )
    cache_key = _build_confirm_nonce_cache_key(
        tenant_id=tenant_id,
        session_id=session_id,
        function_call_id=function_call_id,
        invocation_id=invocation_id,
        nonce=nonce,
    )

    with _ADK_CONFIRM_NONCE_LOCK:
        _prune_confirm_nonce_cache_locked(now_ms)
        if cache_key in _ADK_CONFIRM_USED_NONCES and _ADK_CONFIRM_USED_NONCES[cache_key] > now_ms:
            raise HTTPException(status_code=409, detail="confirm nonce replay detected")
        _ADK_CONFIRM_USED_NONCES[cache_key] = normalized_expires_at_ms


def _validate_confirm_tool_security_or_raise(
    *,
    request_body: ADKToolConfirmationRequest,
    user_id: str,
    session_id: str,
    function_call_id: str,
) -> Dict[str, Any]:
    if request_body.confirmed is not True:
        raise HTTPException(status_code=403, detail="confirm-tool requires explicit confirmed=true")

    nonce = str(request_body.nonce or "").strip()
    try:
        approval_ticket = _materialize_approval_ticket_from_request(
            request_body=request_body,
            user_id=user_id,
            session_id=session_id,
            function_call_id=function_call_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=f"invalid approval_ticket timing: {exc}") from exc
    if not nonce or approval_ticket is None:
        raise HTTPException(status_code=403, detail="approval_ticket and nonce are required (approval_ticket object)")

    ticket_session_id = _pick_first_text(approval_ticket, ["session_id", "sessionId"])
    ticket_function_call_id = _pick_first_text(
        approval_ticket,
        ["function_call_id", "functionCallId", "id", "call_id", "callId"],
    )
    ticket_invocation_id = _pick_first_text(approval_ticket, ["invocation_id", "invocationId"])
    ticket_tenant_id = _pick_first_text(
        approval_ticket,
        ["tenant_id", "tenantId", "tenant", "user_id", "userId"],
    )
    ticket_nonce = _pick_first_text(approval_ticket, ["nonce"])

    if not ticket_session_id or not ticket_function_call_id or not ticket_invocation_id or not ticket_tenant_id:
        raise HTTPException(
            status_code=403,
            detail="invalid approval_ticket: missing session/function_call/invocation/tenant binding",
        )

    request_invocation_id = str(request_body.invocation_id or "").strip()
    if not request_invocation_id:
        raise HTTPException(status_code=403, detail="invocation_id is required for confirm-tool binding")

    if ticket_session_id != str(session_id or "").strip():
        raise HTTPException(status_code=403, detail="approval ticket session binding mismatch")
    if ticket_function_call_id != str(function_call_id or "").strip():
        raise HTTPException(status_code=403, detail="approval ticket function_call binding mismatch")
    if ticket_invocation_id != request_invocation_id:
        raise HTTPException(status_code=403, detail="approval ticket invocation binding mismatch")
    if ticket_tenant_id != str(user_id or "").strip():
        raise HTTPException(status_code=403, detail="approval ticket tenant binding mismatch")
    if ticket_nonce and ticket_nonce != nonce:
        raise HTTPException(status_code=403, detail="approval ticket nonce mismatch")

    ticket_timestamp_raw = _pick_first_value(
        approval_ticket,
        ["timestamp_ms", "timestampMs", "issued_at_ms", "issuedAtMs", "timestamp", "issued_at"],
    )
    ticket_ttl_raw = _pick_first_value(approval_ticket, ["ttl_seconds", "ttlSeconds", "ttl"])
    try:
        ticket_timestamp_ms = _parse_ticket_timestamp_ms(ticket_timestamp_raw)
        ticket_ttl_seconds = _parse_ticket_ttl_seconds(ticket_ttl_raw)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=f"invalid approval_ticket timing: {exc}") from exc

    now_ms = int(time.time() * 1000)
    if ticket_timestamp_ms > now_ms + ADK_CONFIRM_TICKET_MAX_FUTURE_SKEW_MS:
        raise HTTPException(status_code=403, detail="approval ticket timestamp is in the future")

    expires_at_ms = ticket_timestamp_ms + ticket_ttl_seconds * 1000
    if now_ms >= expires_at_ms:
        raise HTTPException(status_code=403, detail="approval ticket expired")

    _consume_confirm_nonce_or_raise(
        tenant_id=ticket_tenant_id,
        session_id=ticket_session_id,
        function_call_id=ticket_function_call_id,
        invocation_id=ticket_invocation_id,
        nonce=nonce,
        expires_at_ms=expires_at_ms,
    )
    return {
        "nonce": nonce,
        "tenant_id": ticket_tenant_id,
        "invocation_id": ticket_invocation_id,
        "expires_at_ms": expires_at_ms,
    }


async def _resolve_user_agent_or_404(db: Session, user_id: str, agent_id: str) -> AgentRegistry:
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == str(agent_id or "").strip(),
        AgentRegistry.user_id == user_id,
        AgentRegistry.status == "active",
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return agent


def _ensure_adk_google_agent(agent: AgentRegistry) -> None:
    agent_type = str(getattr(agent, "agent_type", "") or "").strip().lower()
    provider_id = _normalize_provider_id(getattr(agent, "provider_id", ""))
    if agent_type not in {"adk", "google-adk"}:
        raise HTTPException(
            status_code=400,
            detail="Runtime endpoints currently require agent_type=adk/google-adk",
        )
    if not provider_id.startswith("google"):
        raise HTTPException(
            status_code=400,
            detail="Runtime endpoints currently require Google provider",
        )


async def _create_adk_runner_for_agent(
    *,
    db: Session,
    user_id: str,
    agent: AgentRegistry,
    require_runtime: bool = True,
) -> tuple[ADKRunner, str]:
    provider_id = str(agent.provider_id or "google").strip() or "google"
    model_id = str(agent.model_id or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    api_key = ""
    adk_agent: Optional[ADKAgent] = None

    if require_runtime:
        api_key, _ = await get_provider_credentials(provider_id, db, user_id)
        builtin_tools = build_adk_builtin_tools()
        adk_agent = ADKAgent(
            db=db,
            model=model_id,
            name=str(agent.name or "ADK Agent"),
            instruction=str(agent.system_prompt or "You are a helpful assistant."),
            tools=builtin_tools,
        )
        if not adk_agent.is_available:
            raise HTTPException(status_code=503, detail="google.adk SDK is unavailable in current runtime")

    runner = ADKRunner(
        db=db,
        agent_id=str(agent.id or ""),
        app_name="gemini-multi-agent-adk",
        adk_agent=adk_agent,
    )
    if require_runtime and not runner.is_available:
        raise HTTPException(status_code=503, detail="google.adk runner is unavailable in current runtime")

    return runner, str(api_key or "").strip()


def _build_memory_manager(
    *,
    db: Session,
    project: Optional[str],
    location: Optional[str],
    agent_engine_id: Optional[str],
) -> MemoryManager:
    if project or location or agent_engine_id:
        memory_service = VertexAiMemoryBankService(
            db=db,
            project=project,
            location=location,
            agent_engine_id=agent_engine_id,
        )
        return MemoryManager(
            db=db,
            memory_service=memory_service,
            use_vertex_ai=True,
            project=project,
            location=location,
        )

    return MemoryManager(db=db, use_vertex_ai=True)


def _attach_legacy_orchestrate_route_meta(result: Any, *, mode: str) -> Dict[str, Any]:
    route_meta = {
        "entrypoint": "legacy-orchestrate",
        "legacy": True,
        "status": "deprecated",
        "provider_neutral": False,
        "runtime_kind": LEGACY_ORCHESTRATE_RUNTIME_KIND,
        "provider_scope": LEGACY_ORCHESTRATE_PROVIDER_SCOPE,
        "official_orchestration": True,
        "supports_provider_switch": False,
        "mode": str(mode or "default").strip() or "default",
        "recommended_entrypoint": "provider-mode",
        "recommended_path_template": LEGACY_ORCHESTRATE_REPLACEMENT_PATH,
    }

    if isinstance(result, dict):
        payload = dict(result)
        existing_meta = payload.get("route_meta")
        if isinstance(existing_meta, dict):
            route_meta = {
                **route_meta,
                **existing_meta,
            }
        payload["route_meta"] = route_meta
        return payload

    return {
        "result": result,
        "route_meta": route_meta,
    }


def _apply_legacy_orchestrate_response_headers(response: Response) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Warning"] = (
        '299 gemini-main "Deprecated legacy multi-agent endpoint; '
        f'use {LEGACY_ORCHESTRATE_REPLACEMENT_PATH}"'
    )
    response.headers["X-Legacy-Entrypoint"] = "legacy-orchestrate"
    response.headers["X-Replacement-Path-Template"] = LEGACY_ORCHESTRATE_REPLACEMENT_PATH
    response.headers["X-Runtime-Kind"] = LEGACY_ORCHESTRATE_RUNTIME_KIND
    response.headers["X-Provider-Scope"] = LEGACY_ORCHESTRATE_PROVIDER_SCOPE


def _sanitize_adk_name(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = fallback
    # ADK app/agent 名称限制较严格，统一做轻量清洗。
    normalized = "".join(ch if (ch.isalnum() or ch in {"_", "-"}) else "_" for ch in raw).strip("_")
    return normalized[:80] or fallback


_EXCEL_ALLOWED_SUFFIXES = {".xlsx", ".xls", ".csv", ".tsv"}
_EXCEL_LEGACY_PATH_ENV = "EXCEL_WORKFLOW_ALLOW_LEGACY_FILE_PATH"
_EXCEL_ALLOWED_ROOTS_ENV = "EXCEL_WORKFLOW_ALLOWED_ROOTS"


def _resolve_excel_project_base() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "backend":
            return parent.parent.resolve()
    return current.parent.resolve()


_EXCEL_PROJECT_BASE = _resolve_excel_project_base()


def _is_truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_excel_local_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = _EXCEL_PROJECT_BASE / candidate
    return candidate.resolve()


def _resolve_excel_allowed_roots() -> List[Path]:
    raw = str(os.getenv(_EXCEL_ALLOWED_ROOTS_ENV, "") or "").strip()
    parsed_roots: List[Path] = []
    if raw:
        for item in raw.split(","):
            text = str(item or "").strip()
            if not text:
                continue
            try:
                parsed_roots.append(_resolve_excel_local_path(text))
            except Exception:
                continue
    if parsed_roots:
        return parsed_roots

    defaults = [
        _EXCEL_PROJECT_BASE,
        (_EXCEL_PROJECT_BASE / "tmp").resolve(),
        Path("/tmp"),
        Path("/private/tmp"),
    ]
    unique_defaults: List[Path] = []
    seen: set[str] = set()
    for root in defaults:
        marker = str(root)
        if marker in seen:
            continue
        seen.add(marker)
        unique_defaults.append(root)
    return unique_defaults


def _is_path_within_roots(candidate: Path, roots: List[Path]) -> bool:
    for root in roots:
        if candidate == root or root in candidate.parents:
            return True
    return False


def _validate_excel_reference_suffix(file_ref: str) -> None:
    raw = str(file_ref or "").strip()
    if not raw or raw.startswith("data:"):
        return
    parsed = urlparse(raw)
    path_text = parsed.path if parsed.scheme else raw
    suffix = Path(path_text).suffix.lower()
    if suffix and suffix not in _EXCEL_ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {suffix}. "
                f"Supported: {sorted(_EXCEL_ALLOWED_SUFFIXES)}"
            ),
        )


def _resolve_legacy_excel_path(file_path: str) -> str:
    raw = str(file_path or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="file_path is empty")

    if not _is_truthy_env(_EXCEL_LEGACY_PATH_ENV, default=False):
        raise HTTPException(
            status_code=400,
            detail=(
                "file_path is disabled by default. "
                "Use attachment_id or file_url; "
                f"set {_EXCEL_LEGACY_PATH_ENV}=true only for trusted local environments."
            ),
        )

    candidate = _resolve_excel_local_path(raw)

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {candidate}")

    if candidate.suffix.lower() not in _EXCEL_ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {candidate.suffix}. "
                f"Supported: {sorted(_EXCEL_ALLOWED_SUFFIXES)}"
            ),
        )

    roots = _resolve_excel_allowed_roots()
    if not _is_path_within_roots(candidate, roots):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Path is outside allowed roots: {candidate}. "
                f"Configure {_EXCEL_ALLOWED_ROOTS_ENV} to permit trusted directories."
            ),
        )
    return str(candidate)


def _resolve_excel_attachment_reference(db: Session, user_id: str, attachment_id: str) -> str:
    normalized_attachment_id = str(attachment_id or "").strip()
    if not normalized_attachment_id:
        raise HTTPException(status_code=400, detail="attachment_id is empty")

    attachment = db.query(MessageAttachment).filter(
        MessageAttachment.id == normalized_attachment_id,
        MessageAttachment.user_id == user_id,
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    candidate_refs = [
        str(getattr(attachment, "file_uri", "") or "").strip(),
        str(getattr(attachment, "url", "") or "").strip(),
        str(getattr(attachment, "temp_url", "") or "").strip(),
    ]
    for ref in candidate_refs:
        if not ref:
            continue
        lower = ref.lower()
        if lower.startswith("blob:"):
            continue
        if lower.startswith("file://") or ref.startswith("/"):
            continue
        if lower.startswith(("http://", "https://", "data:")):
            _validate_excel_reference_suffix(ref)
            return ref

    raise HTTPException(
        status_code=422,
        detail=(
            "Attachment has no usable excel file reference. "
            "Expected file_uri/url/temp_url with http(s) or data URL."
        ),
    )


def _resolve_excel_file_reference(
    *,
    db: Session,
    user_id: str,
    attachment_id: Optional[str],
    file_url: Optional[str],
    file_path: Optional[str],
) -> str:
    if attachment_id and str(attachment_id).strip():
        return _resolve_excel_attachment_reference(db=db, user_id=user_id, attachment_id=str(attachment_id))

    normalized_url = str(file_url or "").strip()
    if normalized_url:
        lower = normalized_url.lower()
        if lower.startswith(("http://", "https://", "data:")):
            _validate_excel_reference_suffix(normalized_url)
            return normalized_url
        raise HTTPException(
            status_code=400,
            detail="file_url only supports http/https/data URL for excel workflow",
        )

    normalized_path = str(file_path or "").strip()
    if normalized_path:
        return _resolve_legacy_excel_path(normalized_path)

    raise HTTPException(
        status_code=400,
        detail="One of attachment_id, file_url, file_path is required",
    )


_SHEET_STAGE_ALLOWED_PREVIOUS: Dict[str, set[str]] = {
    "ingest": {"", "ingest"},
    "profile": {"ingest", "profile"},
    "query": {"profile", "query"},
    "export": {"query", "export"},
}
_SHEET_STAGE_INPUT_ARTIFACT_KEY: Dict[str, str] = {
    "profile": "sheet/ingest",
    "query": "sheet/profile",
    "export": "sheet/query",
}
_SHEET_STAGE_OUTPUT_ARTIFACT_KEY: Dict[str, str] = {
    "ingest": "sheet/ingest",
    "profile": "sheet/profile",
    "query": "sheet/query",
    "export": "sheet/export",
}


def _extract_sheet_artifact_tenant_binding(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _pick_first_text(
        value,
        [
            "artifact_tenant_id",
            "artifactTenantId",
            "tenant_id",
            "tenantId",
            "tenant",
            "user_id",
            "userId",
        ],
    )


def _authorize_sheet_artifact_ref_or_raise(
    *,
    stage: str,
    session_id: str,
    user_id: str,
    raw_artifact_ref: Any,
    normalized_artifact_ref: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_session_id = str(session_id or "").strip()
    artifact_session_id = str(normalized_artifact_ref.get("artifact_session_id") or "").strip()
    if artifact_session_id != normalized_session_id:
        _raise_sheet_stage_http_error(
            status_code=400,
            stage=stage,
            session_id=normalized_session_id,
            message="artifact reference is bound to another session",
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )

    expected_tenant_id = str(user_id or "").strip()
    artifact_tenant_id = _extract_sheet_artifact_tenant_binding(raw_artifact_ref)
    if artifact_tenant_id and artifact_tenant_id != expected_tenant_id:
        _raise_sheet_stage_http_error(
            status_code=403,
            stage=stage,
            session_id=normalized_session_id,
            message="artifact reference is bound to another tenant",
            error_code="SHEET_STAGE_ARTIFACT_FORBIDDEN",
        )

    return normalized_artifact_ref


def _ensure_sheet_stage_artifact_fresh_or_raise(
    *,
    session_state: Dict[str, Any],
    stage: str,
    session_id: str,
    artifact_ref: Dict[str, Any],
) -> None:
    artifact_key = str(artifact_ref.get("artifact_key") or "").strip()
    artifact_version = int(artifact_ref.get("artifact_version") or 0)
    with _SHEET_STAGE_LOCK:
        artifact_versions = session_state.get("artifact_versions")
        latest_version = int((artifact_versions or {}).get(artifact_key) or 0) if isinstance(artifact_versions, dict) else 0

    if latest_version <= 0:
        _raise_sheet_stage_http_error(
            status_code=404,
            stage=stage,
            session_id=session_id,
            message=f"artifact key not found: {artifact_key}",
            error_code="SHEET_STAGE_ARTIFACT_NOT_FOUND",
        )

    if artifact_version != latest_version:
        _raise_sheet_stage_http_error(
            status_code=409,
            stage=stage,
            session_id=session_id,
            message=(
                "stale artifact reference "
                f"({artifact_key}@{artifact_version}; latest={latest_version})"
            ),
            error_code="SHEET_STAGE_ARTIFACT_STALE",
        )


def _prune_sheet_stage_sessions_locked() -> None:
    overflow = len(_SHEET_STAGE_SESSIONS) - _SHEET_STAGE_MAX_SESSION_CACHE_SIZE
    if overflow <= 0:
        return
    ordered = sorted(
        _SHEET_STAGE_SESSIONS.items(),
        key=lambda item: int(item[1].get("updated_at_ms") or 0),
    )
    for session_id, _state in ordered[:overflow]:
        _SHEET_STAGE_SESSIONS.pop(session_id, None)


def _new_sheet_stage_session_state(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": str(user_id or "").strip(),
        "current_stage": "",
        "artifact_versions": {},
        "artifacts": {},
        "history": [],
        "updated_at_ms": int(time.time() * 1000),
    }


def _build_sheet_stage_session_id() -> str:
    return _sheet_stage_artifact_service.build_session_id()


def _build_sheet_stage_failure_detail(
    *,
    stage: str,
    session_id: str,
    message: str,
    error_code: str = "SHEET_STAGE_FAILED",
) -> Dict[str, Any]:
    normalized_stage = str(stage or "").strip().lower()
    if normalized_stage not in _SHEET_STAGE_OUTPUT_ARTIFACT_KEY:
        normalized_stage = "ingest"
    normalized_session_id = str(session_id or "").strip() or "pending"
    return build_sheet_stage_envelope(
        stage=normalized_stage,
        status="failed",
        session_id=normalized_session_id,
        protocol_version=SHEET_STAGE_PROTOCOL_VERSION,
        error={
            "code": str(error_code or "SHEET_STAGE_FAILED"),
            "message": str(message or "sheet stage failed"),
        },
    )


def _raise_sheet_stage_http_error(
    *,
    status_code: int,
    stage: str,
    session_id: str,
    message: str,
    error_code: str = "SHEET_STAGE_FAILED",
) -> None:
    detail = _build_sheet_stage_failure_detail(
        stage=stage,
        session_id=session_id,
        message=message,
        error_code=error_code,
    )
    raise HTTPException(status_code=int(status_code), detail=detail)


async def _resolve_sheet_stage_session(
    *,
    requested_session_id: Optional[str],
    user_id: str,
    stage: str,
    invocation_id: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    normalized_stage = str(stage or "").strip().lower()
    normalized_session_id = str(requested_session_id or "").strip()
    try:
        return await _sheet_stage_artifact_service.resolve_sheet_stage_session(
            requested_session_id=normalized_session_id,
            user_id=user_id,
            stage=normalized_stage,
            invocation_id=invocation_id,
        )
    except ADKArtifactBindingError as exc:
        message = str(exc)
        if "another user" in message:
            _raise_sheet_stage_http_error(
                status_code=403,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_FORBIDDEN",
            )
        _raise_sheet_stage_http_error(
            status_code=409,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=message,
            error_code="SHEET_STAGE_SESSION_BINDING_MISMATCH",
        )
    except ADKArtifactSessionError as exc:
        message = str(exc)
        if "invocation_id binding not found" in message:
            _raise_sheet_stage_http_error(
                status_code=409,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_BINDING_MISMATCH",
            )
        if "required for non-ingest" in message:
            _raise_sheet_stage_http_error(
                status_code=400,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_REQUIRED",
            )
        if "not found" in message:
            _raise_sheet_stage_http_error(
                status_code=404,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_NOT_FOUND",
            )
        _raise_sheet_stage_http_error(
            status_code=409,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=message,
            error_code="SHEET_STAGE_SESSION_BINDING_MISMATCH",
        )


def _ensure_sheet_stage_transition_or_raise(
    *,
    session_state: Dict[str, Any],
    stage: str,
    session_id: str,
) -> None:
    current_stage = str(session_state.get("current_stage") or "").strip().lower()
    allowed_previous = _SHEET_STAGE_ALLOWED_PREVIOUS.get(stage, set())
    if current_stage not in allowed_previous:
        _raise_sheet_stage_http_error(
            status_code=409,
            stage=stage,
            session_id=session_id,
            message=(
                "invalid stage transition "
                f"({current_stage or '<empty>'} -> {stage})"
            ),
            error_code="SHEET_STAGE_TRANSITION_INVALID",
        )


async def _store_sheet_stage_artifact(
    *,
    session_state: Dict[str, Any],
    session_id: str,
    stage: str,
    artifact_key: str,
    payload: Dict[str, Any],
    parent_artifact_ref: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        return await _sheet_stage_artifact_service.store_sheet_stage_artifact(
            session_state=session_state,
            session_id=session_id,
            stage=stage,
            artifact_key=artifact_key,
            payload=payload,
            parent_artifact_ref=parent_artifact_ref,
        )
    except ValueError as exc:
        _raise_sheet_stage_http_error(
            status_code=400,
            stage=stage,
            session_id=session_id,
            message=str(exc),
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )


async def _load_sheet_stage_artifact_or_raise(
    *,
    stage: str,
    session_id: str,
    user_id: str,
    artifact_ref: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        return await _sheet_stage_artifact_service.load_sheet_stage_artifact(
            session_id=session_id,
            user_id=user_id,
            artifact_ref=artifact_ref,
        )
    except ADKArtifactNotFoundError as exc:
        _raise_sheet_stage_http_error(
            status_code=404,
            stage=stage,
            session_id=session_id,
            message=str(exc),
            error_code="SHEET_STAGE_ARTIFACT_VERSION_NOT_FOUND",
        )
    except ADKArtifactBindingError as exc:
        _raise_sheet_stage_http_error(
            status_code=403,
            stage=stage,
            session_id=session_id,
            message=str(exc),
            error_code="SHEET_STAGE_ARTIFACT_FORBIDDEN",
        )


def _resolve_sheet_analyze_tool() -> Callable[..., Dict[str, Any]]:
    for tool in build_adk_builtin_tools():
        if getattr(tool, "__name__", "") == "sheet_analyze":
            return tool
    raise RuntimeError("sheet_analyze tool is unavailable")


def _build_sheet_ingest_kwargs(
    *,
    request_body: "SheetStageProtocolRequest",
    db: Session,
    user_id: str,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "file_name": str(request_body.file_name or "sheet.csv"),
        "file_format": request_body.file_format,
        "csv_encoding": str(request_body.csv_encoding or "utf-8"),
        "sheet_name": request_body.sheet_name,
        "sample_rows": int(request_body.sample_rows or 5),
        "export_format": "json",
        "tenant_id": str(user_id or ""),
        "resource_tenant_id": str(user_id or ""),
    }

    if str(request_body.content or "").strip():
        kwargs["content"] = str(request_body.content or "")
        kwargs["content_encoding"] = str(request_body.content_encoding or "plain")
        return kwargs

    if str(request_body.data_url or "").strip():
        kwargs["data_url"] = str(request_body.data_url or "")
        return kwargs

    if str(request_body.file_url or "").strip():
        kwargs["file_url"] = str(request_body.file_url or "")
        return kwargs

    file_reference = _resolve_excel_file_reference(
        db=db,
        user_id=user_id,
        attachment_id=request_body.attachment_id,
        file_url=request_body.file_url,
        file_path=request_body.file_path,
    )
    normalized_reference = str(file_reference or "").strip()
    lower_reference = normalized_reference.lower()
    if lower_reference.startswith("data:"):
        kwargs["data_url"] = normalized_reference
    elif lower_reference.startswith(("http://", "https://")):
        kwargs["file_url"] = normalized_reference
    else:
        local_path = Path(normalized_reference)
        payload_bytes = local_path.read_bytes()
        kwargs["content"] = base64.b64encode(payload_bytes).decode("ascii")
        kwargs["content_encoding"] = "base64"
        if not str(request_body.file_name or "").strip():
            kwargs["file_name"] = local_path.name or kwargs["file_name"]
    return kwargs


def _build_profile_payload_from_ingest(ingest_payload: Dict[str, Any]) -> Dict[str, Any]:
    analysis = ingest_payload.get("analysis")
    normalized_analysis = analysis if isinstance(analysis, dict) else {}
    summary = normalized_analysis.get("summary")
    normalized_summary = summary if isinstance(summary, dict) else {}

    columns = normalized_analysis.get("columns")
    normalized_columns = columns if isinstance(columns, list) else []
    column_names: List[str] = []
    for item in normalized_columns:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("column") or "").strip()
            if name:
                column_names.append(name)

    row_count = int(normalized_summary.get("row_count") or 0)
    column_count = int(normalized_summary.get("column_count") or len(column_names))
    return {
        "summary": {
            "row_count": row_count,
            "column_count": column_count,
        },
        "columns": column_names,
        "source": {
            "file_name": str(ingest_payload.get("file_name") or ""),
            "file_format": str(ingest_payload.get("file_format") or ""),
            "source_type": str(ingest_payload.get("source_type") or ""),
        },
    }


def _build_query_payload(
    *,
    profile_payload: Dict[str, Any],
    query_text: str,
) -> Dict[str, Any]:
    summary = profile_payload.get("summary")
    normalized_summary = summary if isinstance(summary, dict) else {}
    row_count = int(normalized_summary.get("row_count") or 0)
    column_count = int(normalized_summary.get("column_count") or 0)
    answer = (
        f"Query '{query_text}' executed on profiled sheet "
        f"({row_count} rows, {column_count} columns)."
    )
    return {
        "query": query_text,
        "answer": answer,
        "summary": {
            "row_count": row_count,
            "column_count": column_count,
        },
        "columns": profile_payload.get("columns") if isinstance(profile_payload.get("columns"), list) else [],
    }


def _build_export_payload(
    *,
    query_payload: Dict[str, Any],
    user_id: str,
    export_format: str,
) -> Dict[str, Any]:
    normalized_export_format = str(export_format or "markdown").strip().lower()
    if normalized_export_format not in {"json", "markdown"}:
        normalized_export_format = "markdown"

    summary = query_payload.get("summary")
    normalized_summary = summary if isinstance(summary, dict) else {}
    precheck = validate_sheet_export_precheck(
        tenant_id=str(user_id or "").strip(),
        resource_tenant_id=str(user_id or "").strip(),
        payload_bytes=b"",
        analysis={
            "summary": normalized_summary,
            "columns": query_payload.get("columns") if isinstance(query_payload.get("columns"), list) else [],
            "query": query_payload.get("query"),
            "answer": query_payload.get("answer"),
        },
    )

    if normalized_export_format == "json":
        rendered = json.dumps(query_payload, ensure_ascii=False, sort_keys=True)
    else:
        rendered = (
            "# Sheet Query Result\n\n"
            f"- Query: {query_payload.get('query')}\n"
            f"- Answer: {query_payload.get('answer')}\n"
            f"- Rows: {normalized_summary.get('row_count')}\n"
            f"- Columns: {normalized_summary.get('column_count')}\n"
        )
    return {
        "export_format": normalized_export_format,
        "rendered": rendered,
        "export_precheck": precheck,
    }


async def _try_execute_official_adk_orchestration(
    *,
    db: Session,
    user_id: str,
    mode: str,
    task: str,
    workflow_config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    sub_agents_cfg = workflow_config.get("sub_agents")
    if not isinstance(sub_agents_cfg, list) or not sub_agents_cfg:
        return None

    ordered_agent_ids: List[str] = []
    for item in sub_agents_cfg:
        if not isinstance(item, dict):
            return None
        agent_id = str(item.get("agent_id") or "").strip()
        if not agent_id:
            return None
        ordered_agent_ids.append(agent_id)

    db_agents = db.query(AgentRegistry).filter(
        AgentRegistry.user_id == user_id,
        AgentRegistry.status == "active",
        AgentRegistry.id.in_(ordered_agent_ids),
    ).all()
    if len(db_agents) != len(set(ordered_agent_ids)):
        return None

    agent_map = {str(agent.id or "").strip(): agent for agent in db_agents}
    ordered_agents: List[AgentRegistry] = []
    for agent_id in ordered_agent_ids:
        matched = agent_map.get(agent_id)
        if not matched:
            return None
        ordered_agents.append(matched)

    # 仅在“全部为 Google ADK Agent”时走官方 ADK 编排；
    # 否则返回 None，由上层 runtime 合同决定是否允许 fallback。
    for agent in ordered_agents:
        agent_type = str(getattr(agent, "agent_type", "") or "").strip().lower()
        provider_id = _normalize_provider_id(getattr(agent, "provider_id", ""))
        if agent_type not in {"adk", "google-adk"} or not provider_id.startswith("google"):
            return None

    try:
        from google.adk.agents import (
            LlmAgent as ADKLlmAgent,
            SequentialAgent as ADKSequentialAgent,
            ParallelAgent as ADKParallelAgent,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"google.adk SDK unavailable for official orchestration: {exc}") from exc

    primary_provider_id = str(ordered_agents[0].provider_id or "google").strip() or "google"
    api_key, _ = await get_provider_credentials(primary_provider_id, db, user_id)
    if not str(api_key or "").strip():
        raise HTTPException(status_code=400, detail=f"Missing API key for provider: {primary_provider_id}")

    adk_builtin_tools = build_adk_builtin_tools()
    sub_agents = []
    for index, (cfg, db_agent) in enumerate(zip(sub_agents_cfg, ordered_agents)):
        model_id = str(db_agent.model_id or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        instruction = str(db_agent.system_prompt or "You are a helpful assistant.").strip() or "You are a helpful assistant."
        configured_name = (
            cfg.get("agent_name")
            or cfg.get("agentName")
            or db_agent.name
            or f"{mode}_agent_{index + 1}"
        )
        adk_name = _sanitize_adk_name(configured_name, fallback=f"{mode}_agent_{index + 1}")
        sub_agents.append(
            ADKLlmAgent(
                name=adk_name,
                model=model_id,
                instruction=instruction,
                tools=adk_builtin_tools,
            )
        )

    workflow_name = _sanitize_adk_name(
        workflow_config.get("name") or f"{mode}_workflow",
        fallback=f"{mode}_workflow",
    )
    if mode == "sequential":
        root_agent = ADKSequentialAgent(
            name=workflow_name,
            sub_agents=sub_agents,
        )
    elif mode == "parallel":
        root_agent = ADKParallelAgent(
            name=workflow_name,
            sub_agents=sub_agents,
        )
    else:
        return None

    runtime_agent_id = f"{mode}-official-{uuid.uuid4().hex[:12]}"
    session_id = _build_adk_session_id(agent_id=runtime_agent_id)
    runner = ADKRunner(
        db=db,
        agent_id=runtime_agent_id,
        app_name="gemini-multi-agent-orchestrate",
        adk_agent=root_agent,
    )
    if not runner.is_available:
        raise HTTPException(status_code=503, detail="google.adk runner unavailable for official orchestration")

    response = await runner.run_once(
        user_id=user_id,
        session_id=session_id,
        input_data=str(task or ""),
        google_api_key=str(api_key or "").strip(),
        run_config={
            "max_llm_calls": 120,
            "custom_metadata": {
                "channel": "multi-agent-orchestrate",
                "mode": mode,
                "official_adk": True,
            },
        },
    )
    return {
        "success": True,
        "mode": mode,
        "runtime": "adk-official",
        "output": str(response.get("text") or ""),
        "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
        "session_id": response.get("session_id"),
        "invocation_id": str(response.get("invocation_id") or "").strip(),
        "event_count": int(response.get("event_count") or 0),
        "response_signature": str(response.get("response_signature") or ""),
        "action_signature": str(response.get("action_signature") or ""),
        "agents": [
            {
                "id": str(agent.id or ""),
                "name": str(agent.name or ""),
                "provider_id": str(agent.provider_id or ""),
                "model_id": str(agent.model_id or ""),
            }
            for agent in ordered_agents
        ],
    }


async def _execute_explicit_legacy_orchestration(
    *,
    db: Session,
    user_id: str,
    mode: str,
    task: str,
    workflow_config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    sub_agents_cfg = workflow_config.get("sub_agents")
    if not isinstance(sub_agents_cfg, list) or not sub_agents_cfg:
        return None

    normalized_sub_agents: List[Dict[str, Any]] = []
    for index, item in enumerate(sub_agents_cfg):
        if not isinstance(item, dict):
            return None
        agent_id = str(item.get("agent_id") or "").strip()
        if not agent_id:
            return None
        agent_name = str(
            item.get("agent_name")
            or item.get("agentName")
            or f"{mode}_agent_{index + 1}"
        ).strip() or f"{mode}_agent_{index + 1}"
        normalized_sub_agents.append(
            {
                **item,
                "agent_id": agent_id,
                "agent_name": agent_name,
            }
        )

    workflow_name = _sanitize_adk_name(
        workflow_config.get("name") or f"{mode}_workflow",
        fallback=f"{mode}_workflow",
    )
    agent_registry = AgentRegistryService(db=db)
    execution_result: Dict[str, Any]
    output_payload: Any = None

    if mode == "sequential":
        from ...services.gemini.agent.sequential_agent import SequentialAgent

        legacy_agent = SequentialAgent(
            name=workflow_name,
            sub_agents=normalized_sub_agents,
            agent_registry=agent_registry,
            google_service=None,
            tool_registry=None,
        )
        execution_result = await legacy_agent.execute(
            user_id=user_id,
            initial_input=str(task or ""),
            context=workflow_config,
        )
        output_payload = execution_result.get("final_output")
        if output_payload in (None, ""):
            output_payload = execution_result.get("session_state") or execution_result
    elif mode == "parallel":
        from ...services.gemini.agent.parallel_agent import ParallelAgent

        legacy_agent = ParallelAgent(
            name=workflow_name,
            sub_agents=normalized_sub_agents,
            agent_registry=agent_registry,
            google_service=None,
            tool_registry=None,
        )
        execution_result = await legacy_agent.execute(
            user_id=user_id,
            shared_input=str(task or ""),
            context=workflow_config,
        )
        output_payload = execution_result.get("results")
        if output_payload in (None, "", {}):
            output_payload = execution_result
    else:
        return None

    if isinstance(output_payload, str):
        output_text = output_payload.strip()
    else:
        output_text = json.dumps(
            output_payload if output_payload is not None else execution_result,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    legacy_actions: Dict[str, Any] = {}
    if isinstance(execution_result.get("errors"), dict) and execution_result.get("errors"):
        legacy_actions["legacy_errors"] = execution_result.get("errors")
    signatures = compute_adk_accuracy_signals(
        content=output_text,
        actions=legacy_actions,
        long_running_tool_ids=[],
    )
    return {
        "success": bool(execution_result.get("success")) if isinstance(execution_result, dict) else True,
        "mode": mode,
        "runtime": "legacy-explicit-policy",
        "output": output_text,
        "usage": {},
        "session_id": None,
        "invocation_id": "",
        "event_count": 0,
        "response_signature": signatures["response_signature"],
        "action_signature": signatures["action_signature"],
        "agents": [
            {
                "id": str(item.get("agent_id") or ""),
                "name": str(item.get("agent_name") or ""),
                "provider_id": "",
                "model_id": "",
            }
            for item in normalized_sub_agents
        ],
    }


def _resolve_adk_orchestration_runtime_contract() -> Dict[str, Any]:
    try:
        contract = settings.adk_runtime_contract
        runtime_strategy = normalize_adk_runtime_strategy(
            contract.get("runtime_strategy"),
            reject_invalid=True,
        )
    except ValueError as exc:
        strict_mode = bool(getattr(settings, "adk_strict_mode", False))
        raw_runtime_strategy = str(getattr(settings, "adk_runtime_strategy_raw", "") or "").strip().lower()
        raise build_adk_runtime_http_exception(
            status_code=409,
            error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
            message="Invalid ADK runtime strategy configuration.",
            runtime_strategy=raw_runtime_strategy or "official_or_legacy",
            strict_mode=strict_mode,
            fallback_allowed=False,
            mode="orchestrate",
            cause=str(exc),
        ) from exc

    strict_mode = bool(contract.get("strict_mode"))
    fallback_allowed = is_adk_runtime_fallback_allowed(
        runtime_strategy=runtime_strategy,
        strict_mode=strict_mode,
    )
    return {
        "runtime_strategy": runtime_strategy,
        "strict_mode": strict_mode,
        "fallback_allowed": fallback_allowed,
    }


def _classify_orchestration_http_error(exc: HTTPException) -> Dict[str, Any]:
    if callable(_classify_orchestration_http_exception):
        try:
            classified = _classify_orchestration_http_exception(exc)
            if isinstance(classified, dict):
                return classified
        except Exception:
            logger.warning("[Multi-Agent API] classify_orchestration_http_exception failed", exc_info=True)

    status_code = int(exc.status_code)
    cause = str(exc.detail or "").strip() or "orchestration request failed"
    if 400 <= status_code < 500:
        return {
            "status_code": status_code,
            "error_code": ADKRuntimeErrorCode.ADK_INVALID_REQUEST,
            "message": "Orchestration request/configuration is invalid.",
            "cause": cause,
        }
    return {
        "status_code": status_code if status_code >= 500 else 503,
        "error_code": ADKRuntimeErrorCode.ADK_RUNTIME_UNAVAILABLE,
        "message": "Official ADK runtime is unavailable for orchestration.",
        "cause": cause,
    }


async def _execute_orchestration_with_runtime_contract(
    *,
    db: Session,
    user_id: str,
    mode: str,
    task: str,
    workflow_config: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_contract = _resolve_adk_orchestration_runtime_contract()
    runtime_strategy_raw = str(runtime_contract.get("runtime_strategy") or "").strip()
    strict_mode = bool(runtime_contract.get("strict_mode"))
    try:
        runtime_strategy = normalize_adk_runtime_strategy(
            runtime_strategy_raw,
            default="official_or_legacy",
            reject_invalid=True,
        )
    except ValueError as exc:
        raise build_adk_runtime_http_exception(
            status_code=409,
            error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
            message="Invalid ADK runtime strategy contract.",
            runtime_strategy=runtime_strategy_raw or "official_or_legacy",
            strict_mode=strict_mode,
            fallback_allowed=False,
            mode=mode,
            cause=str(exc),
        ) from exc

    expected_fallback_allowed = is_adk_runtime_fallback_allowed(
        runtime_strategy=runtime_strategy,
        strict_mode=strict_mode,
    )
    raw_fallback_allowed = runtime_contract.get("fallback_allowed")
    if raw_fallback_allowed is not None and bool(raw_fallback_allowed) != bool(expected_fallback_allowed):
        raise build_adk_runtime_http_exception(
            status_code=409,
            error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
            message="Invalid ADK runtime strategy contract fallback flag.",
            runtime_strategy=runtime_strategy,
            strict_mode=strict_mode,
            fallback_allowed=expected_fallback_allowed,
            mode=mode,
            cause=(
                "fallback_allowed mismatch: "
                f"contract={bool(raw_fallback_allowed)} expected={bool(expected_fallback_allowed)}"
            ),
        )
    fallback_allowed = bool(expected_fallback_allowed)

    try:
        official_result = await _try_execute_official_adk_orchestration(
            db=db,
            user_id=user_id,
            mode=mode,
            task=task,
            workflow_config=workflow_config,
        )
    except HTTPException as exc:
        classified = _classify_orchestration_http_error(exc)
        raise build_adk_runtime_http_exception(
            status_code=int(classified.get("status_code") or 503),
            error_code=classified.get("error_code") or ADKRuntimeErrorCode.ADK_RUNTIME_UNAVAILABLE,
            message=str(classified.get("message") or "Official ADK runtime is unavailable for orchestration."),
            runtime_strategy=runtime_strategy,
            strict_mode=strict_mode,
            fallback_allowed=fallback_allowed,
            mode=mode,
            cause=str(classified.get("cause") or exc.detail),
        ) from exc

    if official_result is not None:
        return official_result

    if strict_mode:
        raise build_adk_runtime_http_exception(
            status_code=409,
            error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
            message="Strict runtime forbids implicit legacy orchestration degradation.",
            runtime_strategy=runtime_strategy,
            strict_mode=strict_mode,
            fallback_allowed=fallback_allowed,
            mode=mode,
        )

    if runtime_strategy == "official_only":
        raise build_adk_runtime_http_exception(
            status_code=409,
            error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
            message="Runtime strategy official_only requires official ADK-compatible agents.",
            runtime_strategy=runtime_strategy,
            strict_mode=strict_mode,
            fallback_allowed=fallback_allowed,
            mode=mode,
        )

    if runtime_strategy == "allow_legacy" and fallback_allowed:
        legacy_result = await _execute_explicit_legacy_orchestration(
            db=db,
            user_id=user_id,
            mode=mode,
            task=task,
            workflow_config=workflow_config,
        )
        if legacy_result is not None:
            return legacy_result

    raise build_adk_runtime_http_exception(
        status_code=409,
        error_code=ADKRuntimeErrorCode.ADK_FALLBACK_FORBIDDEN,
        message="Legacy fallback output is forbidden by the runtime contract in this entrypoint.",
        runtime_strategy=runtime_strategy,
        strict_mode=strict_mode,
        fallback_allowed=fallback_allowed,
        mode=mode,
    )


# ==================== API Endpoints ====================

@router.post(
    "/orchestrate",
    deprecated=True,
    summary="Legacy multi-agent orchestrator (compatibility only)",
)
async def orchestrate(
    request_body: OrchestrateRequest,
    response: Response,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    编排多智能体任务（兼容入口，推荐改用 provider mode）
    
    使用智能任务分解（如果可用）：
    - 自动分解任务为子任务
    - 智能匹配代理
    - 考虑依赖关系和负载均衡
    
    Returns:
        聚合结果
    """
    try:
        _apply_legacy_orchestrate_response_headers(response)
        
        # 尝试获取 GoogleService 用于智能任务分解
        google_service = None
        try:
            # 使用统一凭证管理器获取 API Key（自动解密）
            api_key, base_url = await get_provider_credentials('google', db, user_id)
            google_service = ProviderFactory.create(
                provider='google',
                api_key=api_key,
                user_id=user_id,
                db=db
            )
        except Exception as e:
            logger.warning(f"[Multi-Agent API] Failed to create GoogleService for smart decomposition: {e}")
            # 继续使用简单任务分解
        
        # 根据模式选择执行方式
        mode = request_body.mode or "default"
        runtime_contract = _resolve_adk_orchestration_runtime_contract()
        strict_mode = bool(runtime_contract.get("strict_mode"))
        
        if mode == "coordinator":
            # Legacy Google runtime Coordinator/Dispatcher Pattern
            from ...services.gemini.agent.coordinator_agent import CoordinatorAgent
            from ...services.gemini.agent.agent_registry import AgentRegistryService
            
            agent_registry = AgentRegistryService(db=db)
            coordinator = CoordinatorAgent(
                google_service=google_service,
                agent_registry=agent_registry,
                model="gemini-2.0-flash-exp"
            )
            
            result = await coordinator.coordinate(
                user_id=user_id,
                task=request_body.task,
                context=request_body.workflow_config
            )
            
            return _attach_legacy_orchestrate_route_meta(result, mode=mode)
            
        elif mode == "sequential":
            # Legacy Google runtime Sequential Pipeline Pattern
            if not request_body.workflow_config or "sub_agents" not in request_body.workflow_config:
                raise HTTPException(
                    status_code=400,
                    detail="Sequential mode requires workflow_config with sub_agents"
                )
            result = await _execute_orchestration_with_runtime_contract(
                db=db,
                user_id=user_id,
                mode="sequential",
                task=request_body.task,
                workflow_config=request_body.workflow_config,
            )
            return _attach_legacy_orchestrate_route_meta(result, mode=mode)
            
        elif mode == "parallel":
            # Legacy Google runtime Parallel Fan-Out/Gather Pattern
            if not request_body.workflow_config or "sub_agents" not in request_body.workflow_config:
                raise HTTPException(
                    status_code=400,
                    detail="Parallel mode requires workflow_config with sub_agents"
                )
            result = await _execute_orchestration_with_runtime_contract(
                db=db,
                user_id=user_id,
                mode="parallel",
                task=request_body.task,
                workflow_config=request_body.workflow_config,
            )
            return _attach_legacy_orchestrate_route_meta(result, mode=mode)
            
        else:
            # Default mode: 使用 legacy Google runtime Orchestrator（智能任务分解 + 执行图）
            if strict_mode and google_service is None:
                raise build_adk_runtime_http_exception(
                    status_code=503,
                    error_code=ADKRuntimeErrorCode.ADK_RUNTIME_UNAVAILABLE,
                    message="Strict runtime requires official orchestration dependencies.",
                    runtime_strategy=str(runtime_contract.get("runtime_strategy") or "official_or_legacy"),
                    strict_mode=True,
                    fallback_allowed=bool(runtime_contract.get("fallback_allowed")),
                    mode="default",
                    cause="Google orchestration service unavailable",
                )
            orchestrator = Orchestrator(
                db=db,
                google_service=google_service,
                use_smart_decomposition=google_service is not None,
                strict_runtime=strict_mode,
            )

            try:
                result = await orchestrator.orchestrate(
                    user_id=user_id,
                    task=request_body.task,
                    agent_ids=request_body.agent_ids
                )
            except RuntimeError as exc:
                cause = str(exc or "").strip()
                runtime_strategy = str(runtime_contract.get("runtime_strategy") or "official_or_legacy")
                fallback_allowed = bool(runtime_contract.get("fallback_allowed"))
                if "ORCHESTRATOR_NO_DEGRADE" not in cause:
                    if not strict_mode:
                        raise
                    raise build_adk_runtime_http_exception(
                        status_code=409,
                        error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
                        message="Strict runtime orchestration failed and forbids implicit legacy degradation.",
                        runtime_strategy=runtime_strategy,
                        strict_mode=True,
                        fallback_allowed=fallback_allowed,
                        mode="default",
                        cause=cause or "Strict runtime orchestration failed",
                    ) from exc
                raise build_adk_runtime_http_exception(
                    status_code=409,
                    error_code=ADKRuntimeErrorCode.ADK_STRATEGY_VIOLATION,
                    message="Strict runtime forbids implicit legacy orchestration degradation.",
                    runtime_strategy=runtime_strategy,
                    strict_mode=strict_mode,
                    fallback_allowed=fallback_allowed,
                    mode="default",
                    cause=cause or "ORCHESTRATOR_NO_DEGRADE",
                ) from exc
            
            return _attach_legacy_orchestrate_route_meta(result, mode=mode)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error orchestrating task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents(
    agent_type: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    列出可用智能体
    
    Returns:
        智能体列表
    """
    try:
        
        registry = AgentRegistryService(db=db)
        agents = await registry.list_agents(
            user_id=user_id,
            agent_type=agent_type
        )
        
        return {"agents": agents, "count": len(agents)}
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error listing agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/register")
async def register_agent(
    request_body: RegisterAgentRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    注册智能体
    
    Returns:
        注册的智能体信息
    """
    try:
        
        registry = AgentRegistryService(db=db)
        agent = await registry.register_agent(
            user_id=user_id,
            name=request_body.name,
            agent_type=request_body.agent_type,
            agent_card=request_body.agent_card,
            endpoint_url=request_body.endpoint_url,
            tools=request_body.tools,
            mcp_session_id=request_body.mcp_session_id
        )
        
        return agent
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error registering agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Runtime API (primary alias + legacy ADK compatibility) ====================

@router.post("/agents/{agent_id}/runtime/run")
@router.post(
    "/adk/agents/{agent_id}/run",
    deprecated=True,
    summary="Legacy ADK runtime run endpoint (compatibility only)",
)
async def adk_run_agent(
    agent_id: str,
    request_body: ADKRunRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    运行指定 Agent runtime（当前实现为 Google ADK，非流式）。
    """
    try:
        has_text_input = bool(str(request_body.input or "").strip())
        has_structured_input = isinstance(request_body.input_message, dict)
        if not has_text_input and not has_structured_input:
            raise HTTPException(status_code=400, detail="input or input_message is required")

        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)
        validated_run_config = validate_adk_run_config_allowlist(request_body.run_config)

        runner, api_key = await _create_adk_runner_for_agent(db=db, user_id=user_id, agent=agent)
        session_id = str(request_body.session_id or "").strip() or _build_adk_session_id(agent_id=agent_id)

        response = await runner.run_once(
            user_id=user_id,
            session_id=session_id,
            input_data=str(request_body.input or "") if has_text_input else None,
            input_message=request_body.input_message if has_structured_input else None,
            google_api_key=api_key,
            run_config=validated_run_config,
            state_delta=request_body.state_delta,
            invocation_id=request_body.invocation_id,
        )

        return {
            "status": "completed",
            "agent_id": str(agent.id or ""),
            "agent_name": str(agent.name or ""),
            "provider_id": str(agent.provider_id or ""),
            "model_id": str(agent.model_id or ""),
            "session_id": session_id,
            "invocation_id": str(response.get("invocation_id") or ""),
            "output": str(response.get("text") or ""),
            "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
            "event_count": int(response.get("event_count") or 0),
            "actions": response.get("actions") if isinstance(response.get("actions"), dict) else {},
            "long_running_tool_ids": response.get("long_running_tool_ids") or [],
            "response_signature": str(response.get("response_signature") or ""),
            "action_signature": str(response.get("action_signature") or ""),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[Multi-Agent API] ADK run failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/runtime/run-live")
@router.post(
    "/adk/agents/{agent_id}/run-live",
    deprecated=True,
    summary="Legacy ADK runtime live endpoint (compatibility only)",
)
async def adk_run_live_agent(
    agent_id: str,
    request_body: ADKLiveRunRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    执行 Agent runtime live 请求序列（当前实现为 Google ADK，非 WebSocket 汇总返回）。
    """
    try:
        has_text_input = bool(str(request_body.input or "").strip())
        has_live_requests = isinstance(request_body.live_requests, list) and len(request_body.live_requests) > 0
        if not has_text_input and not has_live_requests:
            raise HTTPException(status_code=400, detail="input or live_requests is required")

        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)
        validated_run_config = validate_adk_run_config_allowlist(request_body.run_config)

        runner, api_key = await _create_adk_runner_for_agent(db=db, user_id=user_id, agent=agent)
        session_id = str(request_body.session_id or "").strip() or _build_adk_session_id(agent_id=agent_id)
        max_events = int(request_body.max_events or 0)
        if max_events <= 0:
            max_events = 200

        events: List[Dict[str, Any]] = []
        output_chunks: List[str] = []
        output_chunk_seen: set[str] = set()
        final_contents: List[str] = []
        final_content_seen: set[str] = set()
        final_invocation_id = ""
        final_actions: Dict[str, Any] = {}
        final_long_running_tool_ids: List[str] = []
        long_running_seen: set[str] = set()
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            input_data=str(request_body.input or "") if has_text_input else None,
            live_requests=request_body.live_requests if has_live_requests else None,
            google_api_key=api_key,
            run_config=validated_run_config,
            close_queue=bool(request_body.close_queue is not False),
            max_events=max_events,
        ):
            events.append(event)
            if str(event.get("type") or "") == "error":
                error_text = str(event.get("error") or "ADK live run failed")
                if bool(event.get("invalid_request")):
                    raise HTTPException(status_code=400, detail=error_text)
                raise RuntimeError(error_text)

            invocation_id = str(event.get("invocation_id") or "").strip()
            if invocation_id:
                final_invocation_id = invocation_id
            if isinstance(event.get("actions"), dict) and event.get("actions"):
                final_actions = event.get("actions") or {}
            raw_long_running = event.get("long_running_tool_ids")
            if isinstance(raw_long_running, list) and raw_long_running:
                for item in raw_long_running:
                    normalized_tool_id = str(item).strip()
                    if not normalized_tool_id or normalized_tool_id in long_running_seen:
                        continue
                    long_running_seen.add(normalized_tool_id)
                    final_long_running_tool_ids.append(normalized_tool_id)
            content = str(event.get("content") or "").strip()
            if content:
                content_key = "|".join(
                    [
                        str(event.get("type") or "").strip().lower(),
                        str(event.get("invocation_id") or "").strip(),
                        content,
                    ]
                )
                is_final_event = bool(event.get("is_final")) or str(event.get("type") or "").strip().lower() == "final"
                if is_final_event:
                    if content_key not in final_content_seen:
                        final_content_seen.add(content_key)
                        final_contents.append(content)
                elif content_key not in output_chunk_seen:
                    output_chunk_seen.add(content_key)
                    output_chunks.append(content)

        if final_contents:
            output_text = "\n".join(item for item in final_contents if item).strip()
        else:
            output_text = "\n".join(chunk for chunk in output_chunks if chunk).strip()
        accuracy_signals = compute_adk_accuracy_signals(
            content=output_text,
            actions=final_actions,
            long_running_tool_ids=final_long_running_tool_ids,
        )

        return {
            "status": "completed",
            "agent_id": str(agent.id or ""),
            "agent_name": str(agent.name or ""),
            "provider_id": str(agent.provider_id or ""),
            "model_id": str(agent.model_id or ""),
            "session_id": session_id,
            "invocation_id": final_invocation_id,
            "events": events,
            "event_count": len(events),
            "output": output_text,
            "actions": final_actions,
            "long_running_tool_ids": final_long_running_tool_ids,
            "response_signature": accuracy_signals["response_signature"],
            "action_signature": accuracy_signals["action_signature"],
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[Multi-Agent API] ADK run_live failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/runtime/sessions/{session_id}/confirm-tool")
@router.post(
    "/adk/agents/{agent_id}/sessions/{session_id}/confirm-tool",
    deprecated=True,
    summary="Legacy ADK confirm-tool endpoint (compatibility only)",
)
async def confirm_adk_tool_call(
    agent_id: str,
    session_id: str,
    request_body: ADKToolConfirmationRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    提交工具确认结果并恢复 runtime 执行。
    """
    try:
        function_call_id = str(request_body.function_call_id or "").strip()
        if not function_call_id:
            raise HTTPException(status_code=400, detail="function_call_id is required")

        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)
        validated_run_config = validate_adk_run_config_allowlist(request_body.run_config)
        _validate_confirm_tool_security_or_raise(
            request_body=request_body,
            user_id=user_id,
            session_id=session_id,
            function_call_id=function_call_id,
        )

        runner, api_key = await _create_adk_runner_for_agent(db=db, user_id=user_id, agent=agent)

        confirmation_response: Dict[str, Any] = {
            "confirmed": True,
        }
        if str(request_body.hint or "").strip():
            confirmation_response["hint"] = str(request_body.hint or "").strip()
        if request_body.payload is not None:
            confirmation_response["payload"] = request_body.payload

        input_message = {
            "role": "user",
            "parts": [
                {
                    "function_response": {
                        "id": function_call_id,
                        "name": ADK_REQUEST_CONFIRMATION_FUNCTION_NAME,
                        "response": confirmation_response,
                    }
                }
            ],
        }

        response = await runner.run_once(
            user_id=user_id,
            session_id=session_id,
            input_data=None,
            input_message=input_message,
            google_api_key=api_key,
            run_config=validated_run_config,
            invocation_id=request_body.invocation_id,
        )

        return {
            "status": "completed",
            "agent_id": str(agent.id or ""),
            "agent_name": str(agent.name or ""),
            "provider_id": str(agent.provider_id or ""),
            "model_id": str(agent.model_id or ""),
            "session_id": session_id,
            "invocation_id": str(response.get("invocation_id") or ""),
            "output": str(response.get("text") or ""),
            "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
            "event_count": int(response.get("event_count") or 0),
            "actions": response.get("actions") if isinstance(response.get("actions"), dict) else {},
            "long_running_tool_ids": response.get("long_running_tool_ids") or [],
            "response_signature": str(response.get("response_signature") or ""),
            "action_signature": str(response.get("action_signature") or ""),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[Multi-Agent API] ADK tool confirmation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/runtime/sessions")
@router.get(
    "/adk/agents/{agent_id}/sessions",
    deprecated=True,
    summary="Legacy ADK session list endpoint (compatibility only)",
)
async def list_adk_agent_sessions(
    agent_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    列出当前用户在该 Agent runtime 下的会话。
    """
    try:
        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)
        runner, _ = await _create_adk_runner_for_agent(
            db=db,
            user_id=user_id,
            agent=agent,
            require_runtime=False,
        )
        sessions = await runner.list_sessions(user_id=user_id)
        return {
            "agent_id": str(agent.id or ""),
            "sessions": sessions,
            "count": len(sessions),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Multi-Agent API] ADK list sessions failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/runtime/sessions/{session_id}")
@router.get(
    "/adk/agents/{agent_id}/sessions/{session_id}",
    deprecated=True,
    summary="Legacy ADK session detail endpoint (compatibility only)",
)
async def get_adk_agent_session(
    agent_id: str,
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    获取单个 Agent runtime 会话快照。
    """
    try:
        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)
        runner, _ = await _create_adk_runner_for_agent(
            db=db,
            user_id=user_id,
            agent=agent,
            require_runtime=False,
        )
        snapshot = await runner.get_session_snapshot(user_id=user_id, session_id=session_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return {
            "agent_id": str(agent.id or ""),
            "session": snapshot,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Multi-Agent API] ADK get session failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/runtime/sessions/{session_id}/rewind")
@router.post(
    "/adk/agents/{agent_id}/sessions/{session_id}/rewind",
    deprecated=True,
    summary="Legacy ADK rewind endpoint (compatibility only)",
)
async def rewind_adk_agent_session(
    agent_id: str,
    session_id: str,
    request_body: ADKRewindRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    将 runtime 会话 rewind 到指定 invocation 之前。
    """
    try:
        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)
        runner, api_key = await _create_adk_runner_for_agent(db=db, user_id=user_id, agent=agent)
        result = await runner.rewind(
            user_id=user_id,
            session_id=session_id,
            rewind_before_invocation_id=request_body.rewind_before_invocation_id,
            google_api_key=api_key,
        )
        return {
            "status": "rewound",
            "agent_id": str(agent.id or ""),
            **result,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[Multi-Agent API] ADK rewind failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/runtime/sessions/{session_id}/memory/index")
@router.post(
    "/adk/agents/{agent_id}/sessions/{session_id}/memory/index",
    deprecated=True,
    summary="Legacy ADK memory index endpoint (compatibility only)",
)
async def index_adk_session_memory(
    agent_id: str,
    session_id: str,
    request_body: ADKSessionMemoryIndexRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    将会话写入 Memory Bank（Vertex Memory + DB 快照）。
    """
    try:
        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)

        memory_manager = _build_memory_manager(
            db=db,
            project=request_body.project,
            location=request_body.location,
            agent_engine_id=request_body.agent_engine_id,
        )
        memories = await memory_manager.add_session_to_memory(
            user_id=user_id,
            session_id=session_id,
            memory_bank_id=request_body.memory_bank_id,
        )
        return {
            "status": "indexed",
            "agent_id": str(agent.id or ""),
            "session_id": session_id,
            "memories": memories,
            "count": len(memories),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Multi-Agent API] ADK memory index failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/runtime/memory/search")
@router.post(
    "/adk/agents/{agent_id}/memory/search",
    deprecated=True,
    summary="Legacy ADK memory search endpoint (compatibility only)",
)
async def search_adk_memory(
    agent_id: str,
    request_body: ADKMemorySearchRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    搜索 Memory Bank 记忆（优先 Vertex，回退 DB）。
    """
    try:
        query = str(request_body.query or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")

        agent = await _resolve_user_agent_or_404(db=db, user_id=user_id, agent_id=agent_id)
        _ensure_adk_google_agent(agent)

        memory_manager = _build_memory_manager(
            db=db,
            project=request_body.project,
            location=request_body.location,
            agent_engine_id=request_body.agent_engine_id,
        )
        limit = int(request_body.limit or 10)
        if limit <= 0:
            limit = 10

        memories = await memory_manager.search_memories(
            user_id=user_id,
            query=query,
            memory_bank_id=request_body.memory_bank_id,
            limit=limit,
        )
        return {
            "agent_id": str(agent.id or ""),
            "query": query,
            "memories": memories,
            "count": len(memories),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Multi-Agent API] ADK memory search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Workflow Templates API ====================

class ImageEditWorkflowRequest(BaseModel):
    """图像编辑工作流请求"""
    image_url: str
    edit_prompt: str
    edit_mode: Optional[str] = None


class ExcelAnalysisWorkflowRequest(BaseModel):
    """Excel 分析工作流请求"""
    attachment_id: Optional[str] = None
    file_url: Optional[str] = None
    file_path: Optional[str] = None  # 兼容旧接口，默认禁用（需显式开启环境变量）
    analysis_type: Optional[str] = "comprehensive"
    cleaning_rules: Optional[Dict[str, Any]] = None


class SheetStageProtocolRequest(BaseModel):
    """Sheet stage protocol v1 请求。"""
    model_config = ConfigDict(populate_by_name=True)

    protocol_version: Optional[str] = Field(default=SHEET_STAGE_PROTOCOL_VERSION, alias="protocolVersion")
    stage: str
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    invocation_id: Optional[str] = Field(default=None, alias="invocationId")
    artifact: Optional[Dict[str, Any]] = None
    attachment_id: Optional[str] = Field(default=None, alias="attachmentId")
    file_url: Optional[str] = Field(default=None, alias="fileUrl")
    file_path: Optional[str] = Field(default=None, alias="filePath")
    file_name: Optional[str] = Field(default="sheet.csv", alias="fileName")
    file_format: Optional[str] = Field(default=None, alias="fileFormat")
    data_url: Optional[str] = Field(default=None, alias="dataUrl")
    content: Optional[str] = None
    content_encoding: Optional[str] = Field(default="plain", alias="contentEncoding")
    csv_encoding: Optional[str] = Field(default="utf-8", alias="csvEncoding")
    sheet_name: Optional[Any] = Field(default=0, alias="sheetName")
    sample_rows: Optional[int] = Field(default=5, alias="sampleRows")
    query: Optional[str] = None
    export_format: Optional[str] = Field(default="markdown", alias="exportFormat")


def _resolve_sheet_stage_from_artifact_key(artifact_key: str) -> str:
    candidate_stage = str(artifact_key or "").strip().split("/", 1)[-1].lower()
    if candidate_stage in _SHEET_STAGE_OUTPUT_ARTIFACT_KEY:
        return candidate_stage
    return "ingest"


@router.post("/workflows/excel-analysis/stage")
async def execute_sheet_stage_protocol(
    request_body: SheetStageProtocolRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    执行 sheet stage protocol v1（ingest/profile/query/export）。
    """
    requested_stage = str(request_body.stage or "").strip().lower()
    requested_session_id = str(request_body.session_id or "").strip()
    try:
        protocol_executor = execute_sheet_stage_protocol_request
        if protocol_executor is None:
            from ...services.agent.sheet_stage_protocol_service import (
                execute_sheet_stage_protocol_request as protocol_executor,
            )

        return await protocol_executor(
            request_body=request_body,
            user_id=user_id,
            artifact_service=_sheet_stage_artifact_service,
            resolve_file_reference=lambda attachment_id, file_url, file_path: _resolve_excel_file_reference(
                db=db,
                user_id=user_id,
                attachment_id=attachment_id,
                file_url=file_url,
                file_path=file_path,
            ),
        )
    except HTTPException:
        raise
    except SheetStageProtocolError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ValueError as exc:
        _raise_sheet_stage_http_error(
            status_code=400,
            stage=requested_stage,
            session_id=requested_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )
    except PermissionError as exc:
        _raise_sheet_stage_http_error(
            status_code=403,
            stage=requested_stage,
            session_id=requested_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_FORBIDDEN",
        )
    except Exception as exc:
        logger.error("[Multi-Agent API] Sheet stage protocol failed: %s", exc, exc_info=True)
        _raise_sheet_stage_http_error(
            status_code=500,
            stage=requested_stage,
            session_id=requested_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_INTERNAL_ERROR",
        )


@router.get("/workflows/excel-analysis/stage/lineage")
async def query_sheet_stage_artifact_lineage(
    session_id: str = Query(..., alias="sessionId"),
    artifact_key: str = Query(..., alias="artifactKey"),
    artifact_version: int = Query(..., alias="artifactVersion"),
    protocol_version: str = Query(SHEET_STAGE_PROTOCOL_VERSION, alias="protocolVersion"),
    user_id: str = Depends(require_current_user),
):
    normalized_session_id = str(session_id or "").strip()
    normalized_stage = _resolve_sheet_stage_from_artifact_key(artifact_key)
    try:
        normalized_protocol_version = str(protocol_version or "").strip() or SHEET_STAGE_PROTOCOL_VERSION
        if normalized_protocol_version != SHEET_STAGE_PROTOCOL_VERSION:
            _raise_sheet_stage_http_error(
                status_code=400,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=(
                    "unsupported protocol_version: "
                    f"{normalized_protocol_version} (expected {SHEET_STAGE_PROTOCOL_VERSION})"
                ),
                error_code="SHEET_STAGE_PROTOCOL_UNSUPPORTED",
            )

        lineage = await _sheet_stage_artifact_service.query_sheet_artifact_lineage(
            session_id=normalized_session_id,
            user_id=user_id,
            artifact_key=artifact_key,
            artifact_version=artifact_version,
        )
        artifact_ref = normalize_sheet_artifact_ref(
            {
                "artifact_key": artifact_key,
                "artifact_version": artifact_version,
                "artifact_session_id": normalized_session_id,
            },
            required=True,
        )
        return build_sheet_stage_envelope(
            stage=normalized_stage,
            status="completed",
            session_id=normalized_session_id,
            protocol_version=SHEET_STAGE_PROTOCOL_VERSION,
            artifact=artifact_ref,
            data={"lineage": lineage},
        )
    except HTTPException:
        raise
    except ADKArtifactSessionError as exc:
        _raise_sheet_stage_http_error(
            status_code=404,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_SESSION_NOT_FOUND",
        )
    except ADKArtifactBindingError as exc:
        _raise_sheet_stage_http_error(
            status_code=403,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_ARTIFACT_FORBIDDEN",
        )
    except (ADKArtifactLineageError, ADKArtifactNotFoundError) as exc:
        _raise_sheet_stage_http_error(
            status_code=404,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_LINEAGE_NOT_FOUND",
        )
    except ValueError as exc:
        _raise_sheet_stage_http_error(
            status_code=400,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )
    except Exception as exc:
        logger.error("[Multi-Agent API] Sheet stage lineage query failed: %s", exc, exc_info=True)
        _raise_sheet_stage_http_error(
            status_code=500,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=str(exc),
            error_code="SHEET_STAGE_INTERNAL_ERROR",
        )


@router.post("/workflows/image-edit")
async def execute_image_edit_workflow(
    request_body: ImageEditWorkflowRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    执行图像编辑工作流
    
    Returns:
        编辑结果和质量报告
    """
    try:
        # 预检查 Google 凭证（保持旧行为：未配置时快速失败）
        await get_provider_credentials("google", db, user_id)

        # 创建并执行工作流（统一走 WorkflowEngine 单内核）
        from ...services.gemini.agent.workflows.image_edit_workflow import ImageEditWorkflow

        workflow = ImageEditWorkflow(
            db=db,
            user_id=user_id
        )

        result = await workflow.execute(
            image_url=request_body.image_url,
            edit_prompt=request_body.edit_prompt,
            edit_mode=request_body.edit_mode
        )

        return result

    except Exception as e:
        logger.error(f"[Multi-Agent API] Error executing image edit workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/excel-analysis")
async def execute_excel_analysis_workflow(
    request_body: ExcelAnalysisWorkflowRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    执行 Excel 分析工作流
    
    Returns:
        分析报告和可视化结果
    """
    try:
        # 预检查 Google 凭证（保持旧行为：未配置时快速失败）
        await get_provider_credentials(
            "google",
            db,
            user_id,
        )

        file_reference = _resolve_excel_file_reference(
            db=db,
            user_id=user_id,
            attachment_id=request_body.attachment_id,
            file_url=request_body.file_url,
            file_path=request_body.file_path,
        )

        # 创建并执行工作流
        from ...services.gemini.agent.workflows.excel_analysis_workflow import ExcelAnalysisWorkflow

        workflow = ExcelAnalysisWorkflow(
            db=db,
            user_id=user_id
        )

        result = await workflow.execute(
            file_reference=file_reference,
            analysis_type=request_body.analysis_type,
            cleaning_rules=request_body.cleaning_rules
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error executing Excel analysis workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ADK Samples Template Import API ====================

@router.get("/workflows/adk-samples/templates")
async def list_adk_samples_templates(
    request_obj: Request
):
    """
    列出可用的 ADK samples 模板
    
    Returns:
        可用的 ADK samples 模板列表
    """
    try:
        from ...services.gemini.agent.adk_samples_importer import ADKSamplesImporter
        from ...core.database import SessionLocal
        
        db = SessionLocal()
        try:
            importer = ADKSamplesImporter(db=db)
            templates = await importer.list_available_templates()
            return {"templates": templates, "count": len(templates)}
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error listing ADK samples templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ImportADKSampleRequest(BaseModel):
    """导入 ADK sample 模板请求"""
    template_id: str  # marketing-agency, data-engineering, customer-service, camel
    custom_name: Optional[str] = None  # 自定义模板名称
    is_public: Optional[bool] = False  # snake_case


@router.post("/workflows/adk-samples/import")
async def import_adk_samples_template(
    request_body: ImportADKSampleRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    从 ADK samples 导入模板
    
    Returns:
        导入的模板信息
    """
    try:
        
        from ...services.gemini.agent.adk_samples_importer import ADKSamplesImporter
        
        importer = ADKSamplesImporter(db=db)
        template = await importer.import_template(
            user_id=user_id,
            template_id=request_body.template_id,
            custom_name=request_body.custom_name,
            is_public=request_body.is_public  # 使用 snake_case 字段名
        )
        
        return template
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error importing ADK samples template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/adk-samples/import-all")
async def import_all_adk_samples_templates(
    is_public: bool = False,  # snake_case Query 参数
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    导入所有可用的 ADK samples 模板
    
    Returns:
        导入的模板列表
    """
    try:
        
        from ...services.gemini.agent.adk_samples_importer import ADKSamplesImporter
        
        importer = ADKSamplesImporter(db=db)
        templates = await importer.import_all_templates(
            user_id=user_id,
            is_public=is_public
        )
        
        return {"templates": templates, "count": len(templates)}
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error importing all ADK samples templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
