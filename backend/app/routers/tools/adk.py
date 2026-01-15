"""
ADK API Router - ADK 集成 API 路由

提供：
- POST /api/adk/agents/create：创建 ADK 智能体
- POST /api/adk/agents/{agent_id}/query：查询智能体
- POST /api/adk/agents/{agent_id}/stream-query：流式查询
- WebSocket /api/adk/agents/{agent_id}/bidi-stream：双向流式
"""

from fastapi import APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import logging
import asyncio
import json
import time

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...services.gemini.agent.adk_runner import ADKRunner
from ...services.gemini.agent.adk_agent import ADKAgent
from ...services.gemini.agent.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/adk", tags=["adk"])


# ==================== Request/Response Models ====================

class CreateADKAgentRequest(BaseModel):
    """创建 ADK 智能体请求"""
    name: str
    model: str = "gemini-2.5-flash"
    instruction: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None


class QueryRequest(BaseModel):
    """查询请求"""
    input: str
    session_id: Optional[str] = None


# ==================== API Endpoints ====================

@router.post("/agents/create")
async def create_adk_agent(
    request_body: CreateADKAgentRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建 ADK 智能体
    
    Returns:
        智能体信息
    """
    try:
        
        # 创建 ADK Agent
        agent = ADKAgent(
            db=db,
            model=request_body.model,
            name=request_body.name,
            instruction=request_body.instruction,
            tools=request_body.tools
        )
        
        # 注册智能体（简化实现）
        from ...services.gemini.agent.agent_registry import AgentRegistryService
        registry = AgentRegistryService(db=db)
        registered = await registry.register_agent(
            user_id=user_id,
            name=request_body.name,
            agent_type="adk"
        )
        
        return {
            "agent_id": registered["id"],
            "name": request_body.name,
            "model": request_body.model
        }
        
    except Exception as e:
        logger.error(f"[ADK API] Error creating agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/query")
async def query_agent(
    agent_id: str,
    request_body: QueryRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    查询 ADK 智能体
    
    Returns:
        完整响应
    """
    try:
        
        # 创建 ADK Runner
        memory_manager = MemoryManager(db=db)
        runner = ADKRunner(
            db=db,
            agent_id=agent_id,
            memory_manager=memory_manager
        )
        
        session_id = request_body.session_id or f"session_{int(time.time() * 1000)}"
        
        # 运行智能体（收集所有事件）
        result = None
        async for event in runner.run(
            user_id=user_id,
            session_id=session_id,
            input_data=request_body.input
        ):
            if event.get("is_final"):
                result = event
        
        if not result:
            raise HTTPException(status_code=500, detail="No response from agent")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ADK API] Error querying agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/stream-query")
async def stream_query_agent(
    agent_id: str,
    request_body: QueryRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
):
    """
    流式查询 ADK 智能体
    
    Returns:
        SSE 流
    """
    async def event_generator():
        try:
            
            # 创建 ADK Runner
            memory_manager = MemoryManager(db=db)
            runner = ADKRunner(
                db=db,
                agent_id=agent_id,
                memory_manager=memory_manager
            )
            
            session_id = request_body.session_id or f"session_{int(time.time() * 1000)}"
            
            # 运行智能体（流式）
            async for event in runner.run(
                user_id=user_id,
                session_id=session_id,
                input_data=request_body.input
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"[ADK API] Error in stream query: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.websocket("/agents/{agent_id}/bidi-stream")
async def bidi_stream_agent(
    websocket: WebSocket,
    agent_id: str,
    db: Session = Depends(get_db)
):
    """
    双向流式查询 ADK 智能体（WebSocket）
    """
    await websocket.accept()
    
    user_id = websocket.query_params.get("user_id") or "default"
    session_id = websocket.query_params.get("session_id") or f"session_{int(time.time() * 1000)}"
    
    # 创建 ADK Agent
    agent = ADKAgent(db=db, name=f"Agent {agent_id}")
    queue = asyncio.Queue()
    
    # 启动接收任务
    async def receive_messages():
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                await queue.put(message)
        except WebSocketDisconnect:
            logger.info(f"[ADK API] WebSocket disconnected for agent {agent_id}")
        except Exception as e:
            logger.error(f"[ADK API] Error receiving message: {e}", exc_info=True)
    
    # 启动发送任务
    async def send_responses():
        try:
            async for response in agent.bidi_stream_query(queue):
                await websocket.send_json(response)
        except WebSocketDisconnect:
            logger.info(f"[ADK API] WebSocket disconnected for agent {agent_id}")
        except Exception as e:
            logger.error(f"[ADK API] Error sending response: {e}", exc_info=True)
    
    # 并发运行接收和发送
    try:
        await asyncio.gather(
            receive_messages(),
            send_responses()
        )
    except Exception as e:
        logger.error(f"[ADK API] Error in bidi stream: {e}", exc_info=True)
    finally:
        await websocket.close()
