from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import json
import hashlib
import logging

from ...services.common.interactions_manager import get_interactions_manager
from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.credential_manager import get_provider_credentials

logger = logging.getLogger(__name__)

# 导入 RateLimitError 以处理配额限制错误
try:
    from google.genai._interactions import RateLimitError as GoogleRateLimitError
except ImportError:
    # 如果导入失败，定义一个占位符类
    class GoogleRateLimitError(Exception):
        pass

router = APIRouter(prefix="/api/research/stream", tags=["research-stream"])


class StreamStartRequest(BaseModel):
    prompt: str
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True
    stream: bool = True  # ✅ 是否流式返回（默认 True）
    research_mode: Optional[str] = "vertex-ai"  # 工作模式 'vertex-ai' | 'gemini-api'
    agent_config: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    file_search_store_names: Optional[List[str]] = None  # 支持文档搜索


@router.post("/start")
async def start_streaming_research(
    request_body: StreamStartRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """Start streaming research task"""
    
    # 从数据库获取 Google Provider 的 API Key
    try:
        api_key, _ = await get_provider_credentials(
            provider="google",
            db=db,
            user_id=user_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Research Stream] Failed to get provider credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider credentials: {str(e)}"
        )
    
    # 检查工作模式
    research_mode = request_body.research_mode or 'vertex-ai'
    logger.info(f"[Research Stream] 工作模式: {research_mode} (request_body.research_mode = {request_body.research_mode})")
    
    # ✅ 根据文档：Deep Research Agent 只能通过 Interactions API 使用
    # ✅ 但 Interactions API 可以通过标准 Gemini API Key 访问（vertexai=False）
    # ✅ 也可以通过 Vertex AI 配置访问（vertexai=True）
    
    # 确定是否使用 Vertex AI
    use_vertexai = (research_mode == 'vertex-ai')
    
    if research_mode == 'gemini-api':
        logger.info(f"[Research Stream] ✅ 使用 Gemini API 模式（Interactions API + 标准 API Key，不依赖 Vertex AI 配额）")
    else:
        logger.info(f"[Research Stream] ⚠️ 使用 Vertex AI 模式（Interactions API + Vertex AI 配置，需要配额）")
    
    try:
        # 使用 InteractionsManager
        # 注意：即使使用 Gemini API 模式，也使用 Interactions API，只是 vertexai=False
        manager = get_interactions_manager(db=db, default_vertexai=use_vertexai)
        
        # 如果提供了 file_search_store_names，构建 file_search tool
        tools = request_body.tools or []
        if request_body.file_search_store_names:
            file_search_tool = {
                "type": "file_search",
                "file_search_store_names": request_body.file_search_store_names
            }
            tools.append(file_search_tool)
        
        # ✅ 检查是否需要流式响应
        if request_body.stream:
            # 流式模式：直接返回流式响应
            logger.info(f"[Research Stream] 使用流式模式（stream=True）")
            
            async def event_generator():
                try:
                    async for event in manager.stream_interaction(
                        input=request_body.prompt,
                        api_key=api_key,
                        agent=request_body.agent,
                        tools=tools if tools else None,
                        agent_config=request_body.agent_config,
                        vertexai=use_vertexai,  # ✅ 根据 research_mode 决定是否使用 Vertex AI
                        user_id=user_id if use_vertexai else None,  # 只在 Vertex AI 模式下传递 user_id
                        system_instruction=None
                    ):
                        yield f"data: {json.dumps(event)}\n\n"
                except Exception as e:
                    logger.error(f"[Research Stream] Stream error: {e}", exc_info=True)
                    error_event = {
                        "event_type": "error",
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e)
                        }
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # 非流式模式：创建交互并返回 ID
            result = await manager.create_interaction(
                input=request_body.prompt,
                api_key=api_key,
                agent=request_body.agent,
                background=True,  # 异步执行，立即返回
                tools=tools if tools else None,
                agent_config=request_body.agent_config,  # 传递 agent_config
                vertexai=use_vertexai,  # ✅ 根据 research_mode 决定是否使用 Vertex AI
                user_id=user_id if use_vertexai else None  # 只在 Vertex AI 模式下传递 user_id（用于从数据库获取配置）
            )
            
            # 从返回的字典获取 ID
            interaction_id = result.get('id')
            
            if not interaction_id:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get interaction_id"
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
            detail={
                "error": "QUOTA_EXCEEDED",
                "message": detail_message,
                "type": "RateLimitError",
                "suggestions": [
                    "在 Google Cloud Console 申请更高的配额",
                    "等待配额重置后重试",
                    "参考: https://cloud.google.com/docs/quotas/help/request_increase"
                ],
                "raw_error": error_message[:500]  # 限制长度
            }
        )
    except Exception as e:
        logger.error(f"[Research Stream] Failed to create interaction: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create interaction: {type(e).__name__}: {str(e)}")



@router.get("/{interaction_id}")
async def stream_research_events(
    interaction_id: str,
    last_event_id: str = Query(""),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Stream research events via SSE"""
    
    logger.info(f"[SSE] 收到流式请求: interaction_id={interaction_id}, last_event_id={last_event_id}")
    
    # 从数据库获取 Google Provider 的 API Key
    try:
        api_key, _ = await get_provider_credentials(
            provider="google",
            db=db,
            user_id=user_id
        )
        logger.info(f"[SSE] 认证成功，API Key长度: {len(api_key)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SSE] Failed to get provider credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get provider credentials: {str(e)}"
        )

    async def event_generator():
        try:
            # ✅ 注意：stream_existing_interaction 需要知道原始交互使用的模式
            # ✅ 但这里我们无法知道，所以使用默认模式（Vertex AI）
            # ✅ 如果原始交互是在 Gemini API 模式下创建的，可能需要传递 vertexai=False
            # TODO: 可以考虑在创建交互时保存 research_mode，然后在 stream_existing_interaction 时使用
            logger.info(f"[SSE] 初始化InteractionsManager（默认 Vertex AI）...")
            manager = get_interactions_manager(db=db, default_vertexai=True)

            logger.info(f"[SSE] 开始流式传输: interaction_id={interaction_id}")
            event_count = 0

            async for event_data in manager.stream_existing_interaction(
                api_key=api_key,
                interaction_id=interaction_id,
                last_event_id=last_event_id if last_event_id else None,
                vertexai=True,  # ✅ 默认使用 Vertex AI（如果原始交互是在 Gemini API 模式下创建的，可能需要改为 False）
                user_id=user_id  # 传递 user_id 以便从数据库获取 Vertex AI 配置
            ):
                event_count += 1
                
                # 调试：记录 content.delta 事件的详细信息
                if event_data.get('event_type') == 'content.delta':
                    delta_info = event_data.get('delta', {})
                    logger.info(f"[SSE] content.delta #{event_count}: type={delta_info.get('type')}, has_text={('text' in delta_info)}, has_content={('content' in delta_info)}")
                
                logger.debug(f"[SSE] 事件#{event_count}: {event_data.get('event_type')}")
                yield f"data: {json.dumps(event_data)}\n\n"

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
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as e:
            logger.error(f"[SSE] 流式传输错误: {type(e).__name__}: {str(e)}", exc_info=True)
            error_data = {
                "event_type": "error",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
