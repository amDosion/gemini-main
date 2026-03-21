"""
Live API Router - Live API 路由

提供：
- POST /api/live/query：标准查询
- POST /api/live/stream-query：流式查询（SSE）
- WebSocket /api/live/bidi-stream：双向流式（WebSocket）
"""

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import logging
import asyncio
import json

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.user_context import extract_user_id_from_token
from ...services.gemini.agent.live_api import LiveAPIHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live-api"])


def _resolve_websocket_user_id(websocket: WebSocket) -> Optional[str]:
    """
    从 WebSocket 握手中提取并校验 access token，返回 user_id。

    支持：
    1. Authorization: Bearer <token>
    2. access_token query 参数
    """
    token: Optional[str] = None

    auth_header = websocket.headers.get("authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        token = websocket.query_params.get("access_token")

    if not token:
        return None

    return extract_user_id_from_token(token)


# ==================== Request/Response Models ====================

class QueryRequest(BaseModel):
    """查询请求"""
    input: str
    agent_id: Optional[str] = None


# ==================== API Endpoints ====================

@router.post("/query")
async def query(
    request_body: QueryRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    标准查询（同步）
    
    Returns:
        完整响应
    """
    try:
        
        handler = LiveAPIHandler(db=db)
        result = await handler.query(
            user_id=user_id,
            input_data=request_body.input,
            agent_id=request_body.agent_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[Live API] Error in query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream-query")
async def stream_query(
    request_body: QueryRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    流式查询（SSE）
    
    Returns:
        SSE 流
    """
    async def event_generator():
        try:
            
            handler = LiveAPIHandler(db=db)
            async for chunk in handler.stream_query(
                user_id=user_id,
                input_data=request_body.input,
                agent_id=request_body.agent_id
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.error(f"[Live API] Error in stream query: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.websocket("/bidi-stream")
async def bidi_stream(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    双向流式查询（WebSocket）
    """
    user_id = _resolve_websocket_user_id(websocket)
    if not user_id:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication required"
        )
        return

    await websocket.accept()
    
    handler = LiveAPIHandler(db=db)
    queue = asyncio.Queue()
    
    # 启动接收任务
    async def receive_messages():
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                await queue.put(message)
        except WebSocketDisconnect:
            logger.info(f"[Live API] WebSocket disconnected for user {user_id}")
        except Exception as e:
            logger.error(f"[Live API] Error receiving message: {e}", exc_info=True)
    
    # 启动发送任务
    async def send_responses():
        try:
            async for response in handler.bidi_stream_query(
                user_id=user_id,
                queue=queue
            ):
                await websocket.send_json(response)
        except WebSocketDisconnect:
            logger.info(f"[Live API] WebSocket disconnected for user {user_id}")
        except Exception as e:
            logger.error(f"[Live API] Error sending response: {e}", exc_info=True)
    
    # 并发运行接收和发送
    try:
        await asyncio.gather(
            receive_messages(),
            send_responses()
        )
    except Exception as e:
        logger.error(f"[Live API] Error in bidi stream: {e}", exc_info=True)
    finally:
        await websocket.close()
