"""
Memory Manager - 记忆管理器

提供：
- 记忆池管理
- 记忆检索策略（相关性、时间范围）
- 记忆治理（自定义主题、访问控制）
"""

import logging
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import AgentMemoryBank, AgentMemory, AgentMemorySession
from .memory_bank_service import BaseMemoryService, VertexAiMemoryBankService, InMemoryMemoryService

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器
    
    负责：
    - 记忆池管理（多个 Memory Bank 实例）
    - 记忆检索策略（相关性、时间范围、主题过滤）
    - 记忆治理（访问控制、数据清理）
    """
    
    def __init__(
        self,
        db: Session,
        memory_service: Optional[BaseMemoryService] = None,
        use_vertex_ai: bool = True,
        project: Optional[str] = None,
        location: Optional[str] = None
    ):
        """
        初始化记忆管理器
        
        Args:
            db: 数据库会话
            memory_service: Memory Service 实例（可选）
            use_vertex_ai: 是否使用 Vertex AI Memory Bank
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
        """
        self.db = db
        
        if memory_service:
            self.memory_service = memory_service
        elif use_vertex_ai:
            self.memory_service = VertexAiMemoryBankService(
                db=db,
                project=project,
                location=location
            )
        else:
            self.memory_service = InMemoryMemoryService(db=db)
        
        logger.info(f"[MemoryManager] Initialized (use_vertex_ai={use_vertex_ai})")
    
    async def get_or_create_memory_bank(
        self,
        user_id: str,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取或创建 Memory Bank
        
        Args:
            user_id: 用户 ID
            name: Memory Bank 名称（可选）
            
        Returns:
            Memory Bank 信息
        """
        # 查找用户现有的 Memory Bank
        memory_bank = self.db.query(AgentMemoryBank).filter(
            AgentMemoryBank.user_id == user_id
        ).first()
        
        if memory_bank:
            return memory_bank.to_dict()
        
        # 创建新的 Memory Bank
        now = int(time.time() * 1000)
        memory_bank = AgentMemoryBank(
            user_id=user_id,
            name=name or f"Memory Bank {now}",
            created_at=now,
            updated_at=now
        )
        
        self.db.add(memory_bank)
        self.db.commit()
        self.db.refresh(memory_bank)
        
        logger.info(f"[MemoryManager] Created memory bank {memory_bank.id} for user {user_id}")
        return memory_bank.to_dict()
    
    async def create_memory(
        self,
        user_id: str,
        content: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建记忆
        
        Args:
            user_id: 用户 ID
            content: 记忆内容
            memory_bank_id: Memory Bank ID（可选）
            session_id: 会话 ID（可选）
            metadata: 记忆元数据（可选）
            
        Returns:
            创建的记忆信息
        """
        return await self.memory_service.create_memory(
            user_id=user_id,
            content=content,
            memory_bank_id=memory_bank_id,
            session_id=session_id,
            metadata=metadata
        )
    
    async def search_memories(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        time_range: Optional[Dict[str, int]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            user_id: 用户 ID
            query: 搜索查询
            memory_bank_id: Memory Bank ID（可选）
            session_id: 会话 ID（可选，用于过滤）
            time_range: 时间范围（可选，{"start": timestamp, "end": timestamp}）
            limit: 返回结果数量限制
            
        Returns:
            匹配的记忆列表
        """
        # 基础搜索
        memories = await self.memory_service.search_memory(
            user_id=user_id,
            query=query,
            memory_bank_id=memory_bank_id,
            limit=limit * 2  # 获取更多结果以便过滤
        )
        
        # 应用过滤
        filtered = []
        for memory in memories:
            # 会话过滤
            if session_id and memory.get("sessionId") != session_id:
                continue
            
            # 时间范围过滤
            if time_range:
                created_at = memory.get("createdAt", 0)
                if time_range.get("start") and created_at < time_range["start"]:
                    continue
                if time_range.get("end") and created_at > time_range["end"]:
                    continue
            
            filtered.append(memory)
            
            if len(filtered) >= limit:
                break
        
        logger.info(f"[MemoryManager] Found {len(filtered)} memories for query: {query}")
        return filtered
    
    async def get_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取记忆
        
        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            
        Returns:
            记忆信息，如果不存在则返回 None
        """
        return await self.memory_service.get_memory(user_id, memory_id)
    
    async def delete_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> bool:
        """
        删除记忆
        
        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            
        Returns:
            是否删除成功
        """
        return await self.memory_service.delete_memory(user_id, memory_id)
    
    async def add_session_to_memory(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        将会话添加到记忆库
        
        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            memory_bank_id: Memory Bank ID（可选）
            
        Returns:
            生成的记忆列表
        """
        return await self.memory_service.add_session_to_memory(
            user_id=user_id,
            session_id=session_id,
            memory_bank_id=memory_bank_id
        )
    
    async def create_memory_session(
        self,
        user_id: str,
        memory_bank_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建 Memory Bank 会话
        
        Args:
            user_id: 用户 ID
            memory_bank_id: Memory Bank ID
            session_id: 会话 ID
            metadata: 会话元数据（可选）
            
        Returns:
            会话信息
        """
        now = int(time.time() * 1000)
        
        # 检查是否已存在
        existing = self.db.query(AgentMemorySession).filter(
            AgentMemorySession.user_id == user_id,
            AgentMemorySession.memory_bank_id == memory_bank_id,
            AgentMemorySession.session_id == session_id
        ).first()
        
        if existing:
            # 更新最后使用时间
            existing.last_used_at = now
            if metadata:
                import json
                existing.metadata_json = json.dumps(metadata)
            self.db.commit()
            self.db.refresh(existing)
            return existing.to_dict()
        
        # 创建新会话
        import json
        session = AgentMemorySession(
            user_id=user_id,
            memory_bank_id=memory_bank_id,
            session_id=session_id,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now,
            last_used_at=now
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"[MemoryManager] Created memory session {session.id} for user {user_id}")
        return session.to_dict()
    
    async def get_memory_session(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Memory Bank 会话
        
        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            
        Returns:
            会话信息，如果不存在则返回 None
        """
        session = self.db.query(AgentMemorySession).filter(
            AgentMemorySession.user_id == user_id,
            AgentMemorySession.session_id == session_id
        ).first()
        
        if session:
            # 更新最后使用时间
            session.last_used_at = int(time.time() * 1000)
            self.db.commit()
            return session.to_dict()
        
        return None
    
    async def list_memory_banks(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        列出用户的所有 Memory Bank
        
        Args:
            user_id: 用户 ID
            
        Returns:
            Memory Bank 列表
        """
        memory_banks = self.db.query(AgentMemoryBank).filter(
            AgentMemoryBank.user_id == user_id
        ).order_by(AgentMemoryBank.created_at.desc()).all()
        
        return [mb.to_dict() for mb in memory_banks]
    
    async def list_memories(
        self,
        user_id: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        列出记忆
        
        Args:
            user_id: 用户 ID
            memory_bank_id: Memory Bank ID（可选）
            session_id: 会话 ID（可选）
            limit: 返回结果数量限制
            
        Returns:
            记忆列表
        """
        query = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id
        )
        
        if memory_bank_id:
            query = query.filter(AgentMemory.memory_bank_id == memory_bank_id)
        
        if session_id:
            query = query.filter(AgentMemory.session_id == session_id)
        
        memories = query.order_by(AgentMemory.created_at.desc()).limit(limit).all()
        
        return [memory.to_dict() for memory in memories]
