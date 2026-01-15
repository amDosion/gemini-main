"""
Memory Bank API Router - Memory Bank API 路由

提供：
- POST /api/memory-bank/sessions：创建会话
- POST /api/memory-bank/memories：创建记忆
- GET /api/memory-bank/memories：检索记忆
- DELETE /api/memory-bank/memories/{memory_id}：删除记忆
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...services.gemini.agent.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory-bank", tags=["memory-bank"])


# ==================== Request/Response Models ====================

class CreateMemoryBankRequest(BaseModel):
    """创建 Memory Bank 请求"""
    name: Optional[str] = None


class CreateMemoryRequest(BaseModel):
    """创建记忆请求"""
    content: str
    memory_bank_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchMemoriesRequest(BaseModel):
    """搜索记忆请求"""
    query: str
    memory_bank_id: Optional[str] = None
    session_id: Optional[str] = None
    time_range: Optional[Dict[str, int]] = None
    limit: int = 10


class CreateMemorySessionRequest(BaseModel):
    """创建 Memory Bank 会话请求"""
    memory_bank_id: str
    session_id: str
    metadata: Optional[Dict[str, Any]] = None


# ==================== API Endpoints ====================

@router.post("/banks")
async def create_memory_bank(
    request: CreateMemoryBankRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建 Memory Bank
    
    Returns:
        Memory Bank 信息
    """
    try:
        
        manager = MemoryManager(db=db)
        memory_bank = await manager.get_or_create_memory_bank(
            user_id=user_id,
            name=request.name
        )
        
        return memory_bank
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error creating memory bank: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/banks")
async def list_memory_banks(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    列出用户的所有 Memory Bank
    
    Returns:
        Memory Bank 列表
    """
    try:
        
        manager = MemoryManager(db=db)
        memory_banks = await manager.list_memory_banks(user_id=user_id)
        
        return {"memory_banks": memory_banks}
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error listing memory banks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions")
async def create_memory_session(
    request_body: CreateMemorySessionRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建 Memory Bank 会话
    
    Returns:
        会话信息
    """
    try:
        
        manager = MemoryManager(db=db)
        session = await manager.create_memory_session(
            user_id=user_id,
            memory_bank_id=request_body.memory_bank_id,
            session_id=request_body.session_id,
            metadata=request_body.metadata
        )
        
        return session
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error creating memory session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_memory_session(
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取 Memory Bank 会话
    
    Returns:
        会话信息
    """
    try:
        
        manager = MemoryManager(db=db)
        session = await manager.get_memory_session(
            user_id=user_id,
            session_id=session_id
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Memory Bank API] Error getting memory session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories")
async def create_memory(
    request_body: CreateMemoryRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建记忆
    
    Returns:
        记忆信息
    """
    try:
        
        manager = MemoryManager(db=db)
        memory = await manager.create_memory(
            user_id=user_id,
            content=request_body.content,
            memory_bank_id=request_body.memory_bank_id,
            session_id=request_body.session_id,
            metadata=request_body.metadata
        )
        
        return memory
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error creating memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/search")
async def search_memories(
    request_body: SearchMemoriesRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    搜索记忆
    
    Returns:
        匹配的记忆列表
    """
    try:
        
        manager = MemoryManager(db=db)
        memories = await manager.search_memories(
            user_id=user_id,
            query=request_body.query,
            memory_bank_id=request_body.memory_bank_id,
            session_id=request_body.session_id,
            time_range=request_body.time_range,
            limit=request_body.limit
        )
        
        return {"memories": memories, "count": len(memories)}
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error searching memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories")
async def list_memories(
    memory_bank_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    列出记忆
    
    Returns:
        记忆列表
    """
    try:
        
        manager = MemoryManager(db=db)
        memories = await manager.list_memories(
            user_id=user_id,
            memory_bank_id=memory_bank_id,
            session_id=session_id,
            limit=limit
        )
        
        return {"memories": memories, "count": len(memories)}
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error listing memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取记忆
    
    Returns:
        记忆信息
    """
    try:
        
        manager = MemoryManager(db=db)
        memory = await manager.get_memory(
            user_id=user_id,
            memory_id=memory_id
        )
        
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return memory
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Memory Bank API] Error getting memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    删除记忆
    
    Returns:
        删除结果
    """
    try:
        manager = MemoryManager(db=db)
        success = await manager.delete_memory(
            user_id=user_id,
            memory_id=memory_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"success": True, "message": "Memory deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Memory Bank API] Error deleting memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/add-to-memory")
async def add_session_to_memory(
    session_id: str,
    memory_bank_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    将会话添加到记忆库
    
    Returns:
        生成的记忆列表
    """
    try:
        
        manager = MemoryManager(db=db)
        memories = await manager.add_session_to_memory(
            user_id=user_id,
            session_id=session_id,
            memory_bank_id=memory_bank_id
        )
        
        return {"memories": memories, "count": len(memories)}
        
    except Exception as e:
        logger.error(f"[Memory Bank API] Error adding session to memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
