from fastapi import APIRouter, HTTPException, Query, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging
from uuid import uuid4

from ...services.common.interactions_manager import get_interactions_manager
from ...services.common.model_capabilities import is_deep_research_model
from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...services.llm import ProviderCredentialsResolver
from ...utils.sse import create_sse_response, encode_sse_data

logger = logging.getLogger(__name__)

# 导入 RateLimitError 以处理配额限制错误
try:
    from google.genai._interactions import RateLimitError as GoogleRateLimitError
except ImportError:
    # 如果导入失败，定义一个占位符类
    class GoogleRateLimitError(Exception):
        pass

router = APIRouter(prefix="/api/research/stream", tags=["research-stream"])
credentials_resolver = ProviderCredentialsResolver()
DEEP_RESEARCH_ALLOWED_TOOL_TYPES = {"google_search", "file_search", "code_execution"}
DEEP_RESEARCH_MAX_TOOLS = 8
DEEP_RESEARCH_MAX_STORE_NAMES = 20
DEEP_RESEARCH_MAX_STORE_NAME_LEN = 160
DEEP_RESEARCH_CLIENT_POLICY = {
    "idle_timeout_ms": 180000,
    "watchdog_interval_ms": 5000,
    "max_recovery_attempts": 8,
}


def _normalize_optional_int(
    value: Any,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except Exception as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return parsed


def _normalize_store_names(raw_values: Any, *, field_name: str) -> List[str]:
    if raw_values is None:
        return []
    if not isinstance(raw_values, list):
        raise ValueError(f"{field_name} must be a list of strings")

    normalized: List[str] = []
    seen = set()
    for raw in raw_values:
        name = str(raw or "").strip()
        if not name:
            continue
        if len(name) > DEEP_RESEARCH_MAX_STORE_NAME_LEN:
            raise ValueError(
                f"{field_name} contains item longer than {DEEP_RESEARCH_MAX_STORE_NAME_LEN} characters"
            )
        if name in seen:
            continue
        seen.add(name)
        normalized.append(name)
        if len(normalized) >= DEEP_RESEARCH_MAX_STORE_NAMES:
            break
    return normalized


def _normalize_metadata_filter(raw_filter: Any) -> Optional[Dict[str, Any]]:
    if raw_filter is None:
        return None
    if not isinstance(raw_filter, dict):
        raise ValueError("file_search.metadata_filter must be an object")

    def sanitize(value: Any, depth: int) -> Any:
        if depth > 4:
            raise ValueError("file_search.metadata_filter nesting is too deep")
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            if len(value) > 50:
                raise ValueError("file_search.metadata_filter list is too long")
            return [sanitize(item, depth + 1) for item in value]
        if isinstance(value, dict):
            normalized_obj: Dict[str, Any] = {}
            for key, val in value.items():
                normalized_key = str(key or "").strip()
                if not normalized_key:
                    continue
                normalized_obj[normalized_key] = sanitize(val, depth + 1)
            return normalized_obj
        raise ValueError("file_search.metadata_filter only supports JSON-serializable values")

    return sanitize(raw_filter, 0)


def _normalize_deep_research_tools(
    *,
    requested_tools: Optional[List[Dict[str, Any]]],
    file_search_store_names: Optional[List[str]],
) -> List[Dict[str, Any]]:
    if requested_tools is not None and not isinstance(requested_tools, list):
        raise ValueError("tools must be an array")

    normalized_tools: List[Dict[str, Any]] = []
    if isinstance(requested_tools, list):
        if len(requested_tools) > DEEP_RESEARCH_MAX_TOOLS:
            raise ValueError(f"tools can include at most {DEEP_RESEARCH_MAX_TOOLS} entries")
        for idx, tool in enumerate(requested_tools):
            if not isinstance(tool, dict):
                raise ValueError(f"tools[{idx}] must be an object")
            tool_type = str(tool.get("type") or "").strip().lower()
            if not tool_type:
                raise ValueError(f"tools[{idx}].type is required")
            if tool_type not in DEEP_RESEARCH_ALLOWED_TOOL_TYPES:
                raise ValueError(
                    f"tools[{idx}].type '{tool_type}' is not allowed. "
                    f"Allowed: {sorted(DEEP_RESEARCH_ALLOWED_TOOL_TYPES)}"
                )

            normalized_tool: Dict[str, Any] = {"type": tool_type}
            if tool_type == "file_search":
                stores = _normalize_store_names(
                    tool.get("file_search_store_names") or tool.get("fileSearchStoreNames"),
                    field_name=f"tools[{idx}].file_search_store_names",
                )
                if stores:
                    normalized_tool["file_search_store_names"] = stores
                top_k = _normalize_optional_int(
                    tool.get("top_k") if tool.get("top_k") is not None else tool.get("topK"),
                    field_name=f"tools[{idx}].top_k",
                    minimum=1,
                    maximum=100,
                )
                if top_k is not None:
                    normalized_tool["top_k"] = top_k
                metadata_filter = _normalize_metadata_filter(
                    tool.get("metadata_filter")
                    if tool.get("metadata_filter") is not None
                    else tool.get("metadataFilter")
                )
                if metadata_filter is not None:
                    normalized_tool["metadata_filter"] = metadata_filter
            normalized_tools.append(normalized_tool)

    external_store_names = _normalize_store_names(
        file_search_store_names,
        field_name="file_search_store_names",
    )
    if external_store_names:
        merged = list(external_store_names)
        file_search_tool = next((tool for tool in normalized_tools if tool.get("type") == "file_search"), None)
        if file_search_tool:
            existing = file_search_tool.get("file_search_store_names")
            existing_values = existing if isinstance(existing, list) else []
            merged = _normalize_store_names(existing_values + external_store_names, field_name="file_search_store_names")
            file_search_tool["file_search_store_names"] = merged
        else:
            normalized_tools.append(
                {
                    "type": "file_search",
                    "file_search_store_names": merged,
                }
            )

    if not normalized_tools:
        # 默认开启 Google 搜索，避免“空工具集”导致 Deep Research 能力降级。
        normalized_tools = [{"type": "google_search"}]
    return normalized_tools


def _build_error_detail(
    code: str,
    message: str,
    *,
    details: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "trace_id": uuid4().hex,
        "retryable": retryable,
    }


class StreamStartRequest(BaseModel):
    prompt: str
    agent: str = Field(min_length=1)
    background: bool = True
    stream: bool = False  # 默认两段式：/start 拿 ID + /{interaction_id} SSE
    previous_interaction_id: Optional[str] = None
    agent_config: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    file_search_store_names: Optional[List[str]] = None  # 支持文档搜索

    model_config = ConfigDict(extra="forbid")


class StreamActionRequest(BaseModel):
    agent: str = Field(min_length=1)
    previous_interaction_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    result: Any
    name: Optional[str] = None
    is_error: bool = False

    model_config = ConfigDict(extra="forbid")


@router.get("/policy")
async def get_deep_research_stream_policy(
    user_id: str = Depends(require_current_user),
):
    """返回 Deep Research 客户端恢复策略（由后端统一下发）。"""
    _ = user_id
    return dict(DEEP_RESEARCH_CLIENT_POLICY)


@router.post("/start")
async def start_streaming_research(
    request_body: StreamStartRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """Start streaming research task"""
    
    # 从数据库获取 Google Provider 的 API Key
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Research Stream] Failed to get provider credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "CREDENTIALS_RESOLVE_FAILED",
                "Failed to get provider credentials",
                details={"error": str(e), "operation": "start"},
                retryable=True,
            ),
        )
    
    # Deep Research 严格契约：显式传入专用 Agent + background=True
    agent_id = request_body.agent.strip()
    if not is_deep_research_model("google", agent_id):
        raise HTTPException(
            status_code=400,
            detail=_build_error_detail(
                "INVALID_DEEP_RESEARCH_AGENT",
                "Selected agent does not support Deep Research",
                details={"agent": agent_id},
                retryable=False,
            ),
        )
    if not request_body.background:
        raise HTTPException(
            status_code=400,
            detail=_build_error_detail(
                "INVALID_DEEP_RESEARCH_CONTRACT",
                "Deep Research requires background=true",
                retryable=False,
            ),
        )

    try:
        # 使用 InteractionsManager（Deep Research 强制 Gemini API）
        manager = get_interactions_manager(db=db, default_vertexai=False)

        try:
            normalized_tools = _normalize_deep_research_tools(
                requested_tools=request_body.tools,
                file_search_store_names=request_body.file_search_store_names,
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=400,
                detail=_build_error_detail(
                    "INVALID_DEEP_RESEARCH_TOOLS",
                    str(ve),
                    details={
                        "allowed_tool_types": sorted(DEEP_RESEARCH_ALLOWED_TOOL_TYPES),
                    },
                    retryable=False,
                ),
            ) from ve
        
        # ✅ 检查是否需要流式响应
        if request_body.stream:
            # 流式模式：直接返回流式响应
            logger.info(f"[Research Stream] 使用流式模式（stream=True）")
            
            async def event_generator():
                try:
                    async for event in manager.stream_interaction(
                        input=request_body.prompt,
                        api_key=api_key,
                        agent=agent_id,
                        previous_interaction_id=request_body.previous_interaction_id,
                        tools=normalized_tools,
                        agent_config=request_body.agent_config,
                        vertexai=False,
                        user_id=None,
                        system_instruction=None
                    ):
                        yield encode_sse_data(
                            event,
                            camel_case=True,
                            event_id=event.get("event_id") if isinstance(event, dict) else None,
                        )
                except GoogleRateLimitError as e:
                    error_message = str(e)
                    logger.warning(f"[Research Stream] Quota limit exceeded during streaming: {error_message}")

                    detail_message = "API 配额已用尽"
                    if "quota_limit_value" in error_message and "'0'" in error_message:
                        detail_message = "Deep Research Agent 配额为 0，需要在 Google Cloud Console 申请配额"

                    error_event = {
                        "event_type": "error",
                        "error": {
                            "type": "RateLimitError",
                            "code": 429,
                            "message": detail_message,
                            "suggestions": [
                                "在 Google Cloud Console 申请更高的配额",
                                "等待配额重置后重试",
                                "参考: https://cloud.google.com/docs/quotas/help/request_increase"
                            ],
                            "raw_error": error_message[:500],
                        }
                    }
                    yield encode_sse_data(error_event, camel_case=True)
                except Exception as e:
                    logger.error(f"[Research Stream] Stream error: {e}", exc_info=True)
                    error_event = {
                        "event_type": "error",
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e)
                        }
                    }
                    yield encode_sse_data(error_event, camel_case=True)
            
            return create_sse_response(event_generator(), heartbeat_interval=15.0)
        else:
            # 非流式模式：创建交互并返回 ID
            result = await manager.create_interaction(
                input=request_body.prompt,
                api_key=api_key,
                agent=agent_id,
                background=True,  # 异步执行，立即返回
                tools=normalized_tools,
                agent_config=request_body.agent_config,  # 传递 agent_config
                previous_interaction_id=request_body.previous_interaction_id,
                store=True,
                vertexai=False,
                user_id=None
            )
            
            # 从返回的字典获取 ID
            interaction_id = result.get('id')
            
            if not interaction_id:
                raise HTTPException(
                    status_code=500,
                    detail=_build_error_detail(
                        "INTERACTION_CREATE_FAILED",
                        "Failed to get interaction_id",
                        details={"operation": "start"},
                        retryable=True,
                    ),
                )
            
            return {"interaction_id": interaction_id}
        
    except GoogleRateLimitError as e:
        # 处理配额限制错误（429）
        error_message = str(e)
        logger.warning(f"[Research Stream] Quota limit exceeded: {error_message}")
        
        # 提取配额信息
        detail_message = "API 配额已用尽"
        if "quota_limit_value" in error_message and "'0'" in error_message:
            detail_message = "Deep Research Agent 配额为 0，需要在 Google Cloud Console 申请配额"
        
        raise HTTPException(
            status_code=429,
            detail=_build_error_detail(
                "QUOTA_EXCEEDED",
                detail_message,
                details={
                    "type": "RateLimitError",
                    "suggestions": [
                        "在 Google Cloud Console 申请更高的配额",
                        "等待配额重置后重试",
                        "参考: https://cloud.google.com/docs/quotas/help/request_increase"
                    ],
                    "raw_error": error_message[:500],
                },
                retryable=True,
            ),
        )
    except Exception as e:
        logger.error(f"[Research Stream] Failed to create interaction: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "INTERACTION_CREATE_FAILED",
                "Failed to create interaction",
                details={"error_type": type(e).__name__, "error": str(e)},
                retryable=True,
            ),
        )


@router.post("/action")
async def submit_required_action(
    request_body: StreamActionRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """Submit function_result for a requires_action interaction and continue research."""
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Research Stream] Failed to get provider credentials for action: {e}")
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "CREDENTIALS_RESOLVE_FAILED",
                "Failed to get provider credentials",
                details={"error": str(e), "operation": "action"},
                retryable=True,
            ),
        )

    function_result_input: Dict[str, Any] = {
        "type": "function_result",
        "call_id": request_body.call_id,
        "result": request_body.result,
    }
    if request_body.name:
        function_result_input["name"] = request_body.name
    if request_body.is_error:
        function_result_input["is_error"] = True

    try:
        agent_id = request_body.agent.strip()
        if not is_deep_research_model("google", agent_id):
            raise HTTPException(
                status_code=400,
                detail=_build_error_detail(
                    "INVALID_DEEP_RESEARCH_AGENT",
                    "Selected agent does not support Deep Research",
                    details={"agent": agent_id},
                    retryable=False,
                ),
            )

        manager = get_interactions_manager(db=db, default_vertexai=False)
        result = await manager.create_interaction(
            input=[function_result_input],
            api_key=api_key,
            agent=agent_id,
            background=True,
            previous_interaction_id=request_body.previous_interaction_id,
            store=True,
            vertexai=False,
            user_id=None,
        )

        interaction_id = result.get("id")
        if not interaction_id:
            raise HTTPException(
                status_code=500,
                detail=_build_error_detail(
                    "INTERACTION_CREATE_FAILED",
                    "Failed to get interaction_id from action continuation",
                    retryable=True,
                ),
            )

        return {"interaction_id": interaction_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Research Stream] Failed to submit required action: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "REQUIRED_ACTION_SUBMIT_FAILED",
                "Failed to submit required action",
                details={"error_type": type(e).__name__, "error": str(e)},
                retryable=True,
            ),
        )



@router.get("/{interaction_id}")
async def stream_research_events(
    interaction_id: str,
    last_event_id_header: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    last_event_id_query: Optional[str] = Query(default=None, alias="last_event_id"),
    include_input: bool = Query(False),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Stream research events via SSE"""

    last_event_id = (last_event_id_header or last_event_id_query or "").strip()
    
    logger.info(
        "[SSE] 收到流式请求: interaction_id=%s, last_event_id=%s, include_input=%s",
        interaction_id,
        last_event_id,
        include_input,
    )
    
    # 从数据库获取 Google Provider 的 API Key
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
        logger.info(f"[SSE] 认证成功，API Key长度: {len(api_key)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SSE] Failed to get provider credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "CREDENTIALS_RESOLVE_FAILED",
                "Failed to get provider credentials",
                details={"error": str(e), "operation": "stream"},
                retryable=True,
            ),
        )

    async def event_generator():
        try:
            logger.info("[SSE] 初始化InteractionsManager（Deep Research 固定 Gemini API）...")
            manager = get_interactions_manager(db=db, default_vertexai=False)

            logger.info(f"[SSE] 开始流式传输: interaction_id={interaction_id}")
            event_count = 0

            async for event_data in manager.stream_existing_interaction(
                api_key=api_key,
                interaction_id=interaction_id,
                last_event_id=last_event_id if last_event_id else None,
                include_input=include_input,
                vertexai=False,
                user_id=None
            ):
                event_count += 1
                
                # 调试：记录 content.delta 事件的详细信息
                if event_data.get('event_type') == 'content.delta':
                    delta_info = event_data.get('delta', {})
                    logger.info(f"[SSE] content.delta #{event_count}: type={delta_info.get('type')}, has_text={('text' in delta_info)}, has_content={('content' in delta_info)}")
                
                logger.debug(f"[SSE] 事件#{event_count}: {event_data.get('event_type')}")
                yield encode_sse_data(
                    event_data,
                    camel_case=True,
                    event_id=event_data.get("event_id"),
                )

                if event_data.get("event_type") in ["interaction.complete", "error"]:
                    logger.info(f"[SSE] 流式传输结束: {event_data.get('event_type')}, 共{event_count}个事件")
                    break

            if event_count == 0:
                logger.warning(f"[SSE] 未收到任何事件: interaction_id={interaction_id}")

        except GoogleRateLimitError as e:
            # 处理配额限制错误（429）
            error_message = str(e)
            logger.warning(f"[SSE] Quota limit exceeded during streaming: {error_message}")
            
            detail_message = "API 配额已用尽"
            if "quota_limit_value" in error_message and "'0'" in error_message:
                detail_message = "Deep Research Agent 配额为 0，需要在 Google Cloud Console 申请配额"
            
            error_data = {
                "event_type": "error",
                "error": {
                    "type": "RateLimitError",
                    "code": 429,
                    "message": detail_message,
                    "suggestions": [
                        "在 Google Cloud Console 申请更高的配额",
                        "等待配额重置后重试",
                        "参考: https://cloud.google.com/docs/quotas/help/request_increase"
                    ]
                }
            }
            yield encode_sse_data(error_data, camel_case=True)
        except Exception as e:
            logger.error(f"[SSE] 流式传输错误: {type(e).__name__}: {str(e)}", exc_info=True)
            error_data = {
                "event_type": "error",
                "error": _build_error_detail(
                    "INTERACTION_STREAM_FAILED",
                    "Stream failed",
                    details={"error_type": type(e).__name__, "error": str(e)},
                    retryable=True,
                ),
            }
            yield encode_sse_data(error_data, camel_case=True)

    return create_sse_response(event_generator(), heartbeat_interval=15.0)


@router.get("/status/{interaction_id}")
async def get_streaming_research_status(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """Get interaction status for SSE recovery/finalization."""
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Research Stream] Failed to get provider credentials for status: {e}")
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "CREDENTIALS_RESOLVE_FAILED",
                "Failed to get provider credentials",
                details={"error": str(e), "operation": "status"},
                retryable=True,
            ),
        )

    try:
        manager = get_interactions_manager(db=db, default_vertexai=False)
        result = await manager.get_interaction_status_async(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=False,
            user_id=None,
        )
        return {
            "interaction_id": result.get("id", interaction_id),
            "status": result.get("status"),
            "outputs": result.get("outputs") or [],
            "error": result.get("error"),
        }
    except Exception as e:
        logger.error(
            f"[Research Stream] Failed to get interaction status {interaction_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "INTERACTION_STATUS_FAILED",
                "Failed to get interaction status",
                details={"interaction_id": interaction_id, "error_type": type(e).__name__, "error": str(e)},
                retryable=True,
            ),
        )


@router.post("/cancel/{interaction_id}")
async def cancel_streaming_research(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """Cancel an in-flight Deep Research interaction."""
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Research Stream] Failed to get provider credentials for cancel: {e}")
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "CREDENTIALS_RESOLVE_FAILED",
                "Failed to get provider credentials",
                details={"error": str(e), "operation": "cancel"},
                retryable=True,
            ),
        )

    try:
        manager = get_interactions_manager(db=db, default_vertexai=False)
        result = await manager.cancel_interaction(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=False,
        )
        return {
            "interaction_id": result.get("id", interaction_id),
            "status": result.get("status", "cancelled"),
        }
    except Exception as e:
        logger.error(f"[Research Stream] Failed to cancel interaction {interaction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "INTERACTION_CANCEL_FAILED",
                "Failed to cancel interaction",
                details={"interaction_id": interaction_id, "error_type": type(e).__name__, "error": str(e)},
                retryable=True,
            ),
        )
