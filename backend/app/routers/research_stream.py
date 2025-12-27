from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import hashlib

from ..services.interactions_service import InteractionsService

router = APIRouter(prefix="/api/research/stream", tags=["research-stream"])


class StreamStartRequest(BaseModel):
    prompt: str
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True
    stream: bool = True
    agent_config: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    file_search_store_names: Optional[List[str]] = None  # 新增：支持文档搜索


@router.post("/start")
async def start_streaming_research(
    request: StreamStartRequest,
    authorization: str = Header(None),
):
    """Start streaming research task"""
    
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    api_key = authorization.split(' ')[1]
    
    try:
        # 使用 InteractionsService 替代直接 SDK 调用
        service = InteractionsService(api_key=api_key)
        
        # 如果提供了 file_search_store_names，构建 file_search tool
        tools = request.tools or []
        if request.file_search_store_names:
            file_search_tool = {
                "type": "file_search",
                "file_search_store_names": request.file_search_store_names
            }
            tools.append(file_search_tool)
        
        # 调用 InteractionsService.create_interaction()
        interaction = await service.create_interaction(
            agent=request.agent,
            input=request.prompt,
            background=True,  # 异步执行，立即返回
            tools=tools if tools else None,
            agent_config=request.agent_config,  # 传递 agent_config
            store=True  # 启用状态存储，支持多轮追问
        )
        
        # 直接从返回的 Interaction 对象获取 ID
        interaction_id = interaction.id
        
        if not interaction_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to get interaction_id"
            )
        
        return {"interaction_id": interaction_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{interaction_id}")
async def stream_research_events(
    interaction_id: str,
    last_event_id: str = Query(""),
    authorization: str = Query(None)
):
    """Stream research events via SSE"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"[SSE] 收到流式请求: interaction_id={interaction_id}, last_event_id={last_event_id}")

    if not authorization or not authorization.startswith('Bearer '):
        logger.error(f"[SSE] 认证失败: authorization={authorization}")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization parameter"
        )

    try:
        api_key = authorization.split(' ')[1]
        logger.info(f"[SSE] 认证成功，API Key长度: {len(api_key)}")
    except IndexError:
        logger.error(f"[SSE] 无法解析authorization参数: {authorization}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format"
        )

    async def event_generator():
        try:
            logger.info(f"[SSE] 初始化InteractionsService...")
            service = InteractionsService(api_key=api_key)

            logger.info(f"[SSE] 开始流式传输: interaction_id={interaction_id}")
            event_count = 0

            async for event_data in service.stream_interaction(
                interaction_id=interaction_id,
                last_event_id=last_event_id if last_event_id else None
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
