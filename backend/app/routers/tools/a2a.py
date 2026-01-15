"""
A2A API Router - A2A 协议 API 路由

提供：
- POST /api/a2a/message/send：发送消息
- GET /api/a2a/message/stream：流式消息
- GET /api/a2a/agents：发现智能体
- GET /api/a2a/agents/{agent_id}/card：获取 Agent Card
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging
import uuid

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...services.gemini.agent.a2a_protocol import A2AProtocolHandler
from ...services.gemini.agent.agent_card import AgentCardManager
from ...services.gemini.agent.agent_executor import AgentExecutor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/a2a", tags=["a2a"])


# ==================== Request/Response Models ====================

class SendMessageRequest(BaseModel):
    """发送消息请求"""
    agent_id: str
    input: str
    context_id: Optional[str] = None


class CreateAgentCardRequest(BaseModel):
    """创建 Agent Card 请求"""
    agent_id: str
    card_data: Dict[str, Any]
    version: str = "1.0.0"


# ==================== API Endpoints ====================

@router.post("/message/send")
async def send_message(
    request_body: SendMessageRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    发送 A2A 消息
    
    Returns:
        任务信息
    """
    try:
        
        handler = A2AProtocolHandler(db=db)
        
        # 生成任务 ID 和上下文 ID
        task_id = str(uuid.uuid4())
        context_id = request_body.context_id or str(uuid.uuid4())
        
        # 创建任务
        task = await handler.create_task(
            user_id=user_id,
            agent_id=request_body.agent_id,
            task_id=task_id,
            context_id=context_id,
            metadata={"input": request_body.input}
        )
        
        # 添加消息事件
        await handler.add_event(
            task_id=task_id,
            event_type="message/send",
            event_data={"input": request_body.input}
        )
        
        return task
        
    except Exception as e:
        logger.error(f"[A2A API] Error sending message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/message/stream/{task_id}")
async def stream_message(
    task_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    流式获取消息事件
    
    Returns:
        事件流（SSE）
    """
    try:
        
        handler = A2AProtocolHandler(db=db)
        
        # 验证任务属于当前用户
        task = await handler.get_task(user_id=user_id, task_id=task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 获取事件列表
        events = await handler.get_events(task_id=task_id)
        
        return {"events": events, "task": task}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[A2A API] Error streaming message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def discover_agents(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    发现智能体
    
    Returns:
        智能体列表
    """
    try:
        
        card_manager = AgentCardManager(db=db)
        cards = card_manager.list_agent_cards(user_id=user_id)
        
        return {"agents": cards}
        
    except Exception as e:
        logger.error(f"[A2A API] Error discovering agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/card")
async def get_agent_card(
    agent_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取 Agent Card
    
    Returns:
        Agent Card 信息
    """
    try:
        
        card_manager = AgentCardManager(db=db)
        card = card_manager.get_agent_card(
            user_id=user_id,
            agent_id=agent_id
        )
        
        if not card:
            raise HTTPException(status_code=404, detail="Agent Card not found")
        
        return card
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[A2A API] Error getting agent card: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/cards")
async def create_agent_card(
    request_body: CreateAgentCardRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建 Agent Card
    
    Returns:
        Agent Card 信息
    """
    try:
        
        card_manager = AgentCardManager(db=db)
        card = card_manager.create_agent_card(
            user_id=user_id,
            agent_id=request_body.agent_id,
            card_data=request_body.card_data,
            version=request_body.version
        )
        
        return card
        
    except Exception as e:
        logger.error(f"[A2A API] Error creating agent card: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取任务
    
    Returns:
        任务信息
    """
    try:
        
        handler = A2AProtocolHandler(db=db)
        task = await handler.get_task(user_id=user_id, task_id=task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[A2A API] Error getting task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
