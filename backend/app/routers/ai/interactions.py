"""
Interactions API 路由

提供 Interactions API 的 HTTP 端点
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
import logging
from uuid import uuid4
from sqlalchemy.orm import Session

from ...services.common.interactions_manager import get_interactions_manager
from ...services.common.interactions_event_utils import serialize_usage
from ...services.llm import ProviderCredentialsResolver
from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...utils.sse import create_sse_response, encode_sse_data


router = APIRouter(prefix="/api/interactions", tags=["interactions"])
credentials_resolver = ProviderCredentialsResolver()
logger = logging.getLogger(__name__)


class CreateInteractionRequest(BaseModel):
    """创建交互请求"""
    model: Optional[str] = None
    agent: Optional[str] = None
    input: Union[str, List[Dict[str, Any]]]
    previous_interaction_id: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False
    background: bool = False
    generation_config: Optional[Dict[str, Any]] = None
    system_instruction: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    store: bool = True
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "gemini-2.5-flash",
                "input": "Hello, how are you?",
                "store": True
            }
        }
    )

class InteractionResponse(BaseModel):
    """交互响应"""
    id: str
    model: Optional[str] = None
    agent: Optional[str] = None
    status: str
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "interaction_123",
                "model": "gemini-2.5-flash",
                "status": "completed",
                "outputs": [
                    {
                        "type": "text",
                        "text": "I'm doing well, thank you!"
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 8
                }
            }
        }
    )


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


def _normalize_outputs(outputs: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for output in outputs or []:
        if isinstance(output, dict):
            normalized.append(output)
        elif hasattr(output, "__dict__"):
            normalized.append(dict(output.__dict__))
    return normalized


def _build_interaction_response(
    result: Dict[str, Any],
    *,
    agent: Optional[str] = None,
) -> InteractionResponse:
    return InteractionResponse(
        id=str(result.get("id") or ""),
        model=result.get("model"),
        agent=result.get("agent") or agent,
        status=str(result.get("status") or ""),
        outputs=_normalize_outputs(result.get("outputs")),
        usage=serialize_usage(result.get("usage")) if result.get("usage") else None,
        created_at=result.get("created_at") or datetime.now().isoformat(),
    )


@router.post("/", response_model=InteractionResponse)
async def create_interaction(
    request: CreateInteractionRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    创建新的交互
    
    支持:
    - 简单文本交互
    - 多轮对话 (previous_interaction_id)
    - 工具调用 (tools)
    - 流式响应 (stream)
    - 后台执行 (background)
    """
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
        
        # 使用 InteractionsManager（Vertex AI，企业级）
        manager = get_interactions_manager(db=db, default_vertexai=True)
        
        # 创建交互（使用 Vertex AI，从数据库获取配置）
        result = await manager.create_interaction(
            input=request.input,
            api_key=api_key,
            agent=request.agent or 'deep-research-pro-preview-12-2025',
            background=request.background,
            store=request.store,
            agent_config=None,  # TODO: 支持 generation_config 转换
            system_instruction=request.system_instruction,
            tools=request.tools,
            previous_interaction_id=request.previous_interaction_id,
            vertexai=True,  # 使用 Vertex AI（企业级）
            user_id=user_id  # 传递 user_id 以从数据库获取 Vertex AI 配置
        )
        return _build_interaction_response(
            result,
            agent=request.agent or "deep-research-pro-preview-12-2025",
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_build_error_detail(
                "INVALID_REQUEST",
                str(e),
                details={"operation": "create_interaction"},
                retryable=False,
            ),
        )
    except Exception as e:
        logger.error("[Interactions] create_interaction failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "INTERACTION_CREATE_FAILED",
                "Failed to create interaction",
                details={"error": str(e), "operation": "create_interaction"},
                retryable=True,
            ),
        )


@router.get("/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """获取交互状态"""
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )

        manager = get_interactions_manager(db=db, default_vertexai=True)
        
        # 获取交互状态
        result = await manager.get_interaction_status_async(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=True,  # 使用 Vertex AI（企业级）
            user_id=user_id,
        )
        return _build_interaction_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get interaction {interaction_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "INTERACTION_GET_FAILED",
                "Failed to retrieve interaction",
                details={"interaction_id": interaction_id},
                retryable=True,
            ),
        )


@router.delete("/{interaction_id}")
async def delete_interaction(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """删除交互"""
    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
        
        # 使用 InteractionsManager（Vertex AI，企业级）
        manager = get_interactions_manager(db=db, default_vertexai=True)
        
        # 删除交互
        await manager.delete_interaction(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=True  # 使用 Vertex AI（企业级）
        )
        
        return {"message": "Interaction deleted successfully"}
        
    except Exception as e:
        logger.error("[Interactions] delete_interaction failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "INTERACTION_DELETE_FAILED",
                "Failed to delete interaction",
                details={"interaction_id": interaction_id, "error": str(e)},
                retryable=True,
            ),
        )


@router.get("/{interaction_id}/stream")
async def stream_interaction(
    interaction_id: str,
    last_event_id_header: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    last_event_id_query: Optional[str] = Query(default=None, alias="last_event_id"),
    include_input: bool = Query(False),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    流式获取交互
    
    使用 Server-Sent Events (SSE) 协议
    """
    last_event_id = (last_event_id_header or last_event_id_query or "").strip()

    try:
        api_key, _ = await credentials_resolver.resolve(
            provider_id="google",
            db=db,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Interactions] Failed to resolve credentials: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_build_error_detail(
                "CREDENTIALS_RESOLVE_FAILED",
                "Failed to resolve provider credentials",
                details={"error": str(e)},
                retryable=True,
            ),
        )

    async def event_generator():
        try:
            manager = get_interactions_manager(db=db, default_vertexai=True)
            async for event_data in manager.stream_existing_interaction(
                api_key=api_key,
                interaction_id=interaction_id,
                last_event_id=last_event_id if last_event_id else None,
                include_input=include_input,
                vertexai=True,
                user_id=user_id,
            ):
                yield encode_sse_data(
                    event_data,
                    camel_case=True,
                    event_id=event_data.get("event_id") if isinstance(event_data, dict) else None,
                )
                if isinstance(event_data, dict) and event_data.get("event_type") in {"interaction.complete", "error"}:
                    break
        except Exception as e:
            logger.error("[Interactions] stream_interaction failed: %s", e, exc_info=True)
            error_payload = _build_error_detail(
                "INTERACTION_STREAM_FAILED",
                "Failed to stream interaction",
                details={"interaction_id": interaction_id, "error": str(e)},
                retryable=True,
            )
            yield encode_sse_data(
                {"event_type": "error", "error": error_payload},
                camel_case=True,
            )

    return create_sse_response(event_generator(), heartbeat_interval=15.0)
