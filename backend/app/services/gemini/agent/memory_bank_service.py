"""
Memory Bank Service - Memory Bank 服务层

提供：
- VertexAiMemoryBankService：使用 Vertex AI Memory Bank API
- InMemoryMemoryService：内存记忆服务（用于测试）
- 记忆创建、检索、更新、删除
- 会话记忆管理
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import AgentMemoryBank, AgentMemory, AgentMemorySession

logger = logging.getLogger(__name__)


class BaseMemoryService:
    """
    Memory Service 基类
    
    定义 Memory Service 的通用接口
    """
    
    def __init__(self, db: Session):
        """
        初始化 Memory Service
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
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
        raise NotImplementedError
    
    async def search_memory(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            user_id: 用户 ID
            query: 搜索查询
            memory_bank_id: Memory Bank ID（可选）
            limit: 返回结果数量限制
            
        Returns:
            匹配的记忆列表
        """
        raise NotImplementedError
    
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
        raise NotImplementedError
    
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
        raise NotImplementedError
    
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
        raise NotImplementedError


class InMemoryMemoryService(BaseMemoryService):
    """
    内存记忆服务 - 用于测试和开发
    
    将所有记忆存储在内存中，不持久化到 Vertex AI
    """
    
    def __init__(self, db: Session):
        """
        初始化内存记忆服务
        
        Args:
            db: 数据库会话
        """
        super().__init__(db)
        self._memories: Dict[str, List[Dict[str, Any]]] = {}  # {user_id: [memory, ...]}
        logger.info("InMemoryMemoryService initialized")
    
    async def add_session_to_memory(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        将会话添加到记忆库（内存版本）
        
        从数据库读取会话消息，转换为记忆
        """
        # 从数据库读取会话消息（简化实现）
        # 实际应该从 MessageIndex + MessagesGeneric 读取
        memories = []
        
        # 创建记忆记录
        memory = {
            "id": f"memory_{int(time.time() * 1000)}",
            "user_id": user_id,
            "session_id": session_id,
            "content": f"Session {session_id} conversation",
            "created_at": int(time.time() * 1000)
        }
        
        if user_id not in self._memories:
            self._memories[user_id] = []
        self._memories[user_id].append(memory)
        memories.append(memory)
        
        logger.info(f"[InMemoryMemoryService] Added session {session_id} to memory for user {user_id}")
        return memories
    
    async def search_memory(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆（内存版本）
        
        使用简单的关键词匹配
        """
        if user_id not in self._memories:
            return []
        
        # 简单的关键词匹配
        query_lower = query.lower()
        matches = []
        
        for memory in self._memories[user_id]:
            if query_lower in memory.get("content", "").lower():
                matches.append(memory)
        
        # 按创建时间排序，返回最新的
        matches.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return matches[:limit]
    
    async def create_memory(
        self,
        user_id: str,
        content: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建记忆（内存版本）
        """
        memory_id = f"memory_{int(time.time() * 1000)}"
        memory = {
            "id": memory_id,
            "user_id": user_id,
            "memory_bank_id": memory_bank_id,
            "session_id": session_id,
            "content": content,
            "metadata": metadata or {},
            "created_at": int(time.time() * 1000)
        }
        
        if user_id not in self._memories:
            self._memories[user_id] = []
        self._memories[user_id].append(memory)
        
        logger.info(f"[InMemoryMemoryService] Created memory {memory_id} for user {user_id}")
        return memory
    
    async def get_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取记忆（内存版本）
        """
        if user_id not in self._memories:
            return None
        
        for memory in self._memories[user_id]:
            if memory.get("id") == memory_id:
                return memory
        
        return None
    
    async def delete_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> bool:
        """
        删除记忆（内存版本）
        """
        if user_id not in self._memories:
            return False
        
        for i, memory in enumerate(self._memories[user_id]):
            if memory.get("id") == memory_id:
                del self._memories[user_id][i]
                logger.info(f"[InMemoryMemoryService] Deleted memory {memory_id} for user {user_id}")
                return True
        
        return False


class VertexAiMemoryBankService(BaseMemoryService):
    """
    Vertex AI Memory Bank 服务
    
    使用 Vertex AI Memory Bank API 进行持久化记忆存储
    """
    
    def __init__(
        self,
        db: Session,
        project: Optional[str] = None,
        location: Optional[str] = None,
        agent_engine_id: Optional[str] = None
    ):
        """
        初始化 Vertex AI Memory Bank 服务
        
        Args:
            db: 数据库会话
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            agent_engine_id: Agent Engine ID（可选）
        """
        super().__init__(db)
        self.project = project
        self.location = location or "us-central1"
        self.agent_engine_id = agent_engine_id
        
        # 延迟导入 Vertex AI 相关模块
        try:
            import vertexai
            from google.adk.memory import VertexAiMemoryBankService as ADKMemoryBankService
            
            self._vertexai_available = True
            self._vertexai_client = None
            self._adk_service = None
            
            if project:
                vertexai.init(project=project, location=self.location)
                self._vertexai_client = vertexai.Client(project=project, location=self.location)
                
                if agent_engine_id:
                    self._adk_service = ADKMemoryBankService(
                        agent_engine_id=agent_engine_id,
                        project=project,
                        location=self.location
                    )
        except ImportError:
            self._vertexai_available = False
            logger.warning("[VertexAiMemoryBankService] Vertex AI SDK not available, using database-only mode")
        
        logger.info(f"[VertexAiMemoryBankService] Initialized (project={project}, location={self.location})")
    
    async def add_session_to_memory(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        将会话添加到记忆库
        
        使用 Vertex AI Memory Bank 生成记忆
        """
        # 获取或创建 Memory Bank
        memory_bank = await self._get_or_create_memory_bank(user_id, memory_bank_id)
        
        if not self._vertexai_available or not self._adk_service:
            # 回退到数据库存储
            logger.warning("[VertexAiMemoryBankService] Vertex AI not available, using database-only mode")
            return await self._add_session_to_memory_db(user_id, session_id, memory_bank.id)
        
        try:
            # 使用 ADK Memory Bank Service 生成记忆
            # 注意：这里需要实际的 Session 对象，简化实现
            # 实际应该从数据库读取会话消息并转换为 ADK Session 格式
            
            # 从数据库读取会话消息
            from ....models.db_models import MessageIndex, MessagesGeneric
            
            messages = self.db.query(MessageIndex).filter(
                MessageIndex.session_id == session_id,
                MessageIndex.user_id == user_id
            ).order_by(MessageIndex.seq).all()
            
            if not messages:
                logger.warning(f"[VertexAiMemoryBankService] No messages found for session {session_id}")
                return []
            
            # 转换为 ADK Session 格式（简化实现）
            # 实际应该使用 ADK Session Service 来获取完整的 Session 对象
            
            # 调用 ADK Memory Bank Service
            # memories = await self._adk_service.add_session_to_memory(session)
            
            # 简化实现：直接存储到数据库
            return await self._add_session_to_memory_db(user_id, session_id, memory_bank.id)
            
        except Exception as e:
            logger.error(f"[VertexAiMemoryBankService] Error adding session to memory: {e}", exc_info=True)
            # 回退到数据库存储
            return await self._add_session_to_memory_db(user_id, session_id, memory_bank.id)
    
    async def _add_session_to_memory_db(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: str
    ) -> List[Dict[str, Any]]:
        """
        将会话添加到记忆库（数据库版本）
        """
        from ...models.db_models import MessageIndex, MessagesGeneric
        
        messages = self.db.query(MessageIndex).filter(
            MessageIndex.session_id == session_id,
            MessageIndex.user_id == user_id
        ).order_by(MessageIndex.seq).all()
        
        memories = []
        now = int(time.time() * 1000)
        
        # 将消息内容合并为记忆
        content_parts = []
        for msg_idx in messages:
            msg = self.db.query(MessagesGeneric).filter(
                MessagesGeneric.id == msg_idx.id
            ).first()
            if msg:
                content_parts.append(f"{msg.role}: {msg.content}")
        
        if content_parts:
            content = "\n".join(content_parts)
            
            # 创建记忆记录
            memory = AgentMemory(
                user_id=user_id,
                memory_bank_id=memory_bank_id,
                session_id=session_id,
                content=content,
                created_at=now,
                updated_at=now
            )
            
            self.db.add(memory)
            self.db.commit()
            self.db.refresh(memory)
            
            memories.append(memory.to_dict())
            logger.info(f"[VertexAiMemoryBankService] Created memory {memory.id} for session {session_id}")
        
        return memories
    
    async def search_memory(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        使用 Vertex AI Memory Bank 搜索，回退到数据库搜索
        """
        # 获取 Memory Bank
        memory_bank = await self._get_or_create_memory_bank(user_id, memory_bank_id)
        
        if not self._vertexai_available or not self._adk_service:
            # 回退到数据库搜索
            return await self._search_memory_db(user_id, query, memory_bank.id, limit)
        
        try:
            # 使用 ADK Memory Bank Service 搜索
            # results = await self._adk_service.search_memory(query, limit=limit)
            
            # 简化实现：使用数据库搜索
            return await self._search_memory_db(user_id, query, memory_bank.id, limit)
            
        except Exception as e:
            logger.error(f"[VertexAiMemoryBankService] Error searching memory: {e}", exc_info=True)
            # 回退到数据库搜索
            return await self._search_memory_db(user_id, query, memory_bank.id, limit)
    
    async def _search_memory_db(
        self,
        user_id: str,
        query: str,
        memory_bank_id: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆（数据库版本）
        
        使用简单的文本匹配
        """
        memories = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.memory_bank_id == memory_bank_id,
            AgentMemory.content.ilike(f"%{query}%")
        ).order_by(AgentMemory.created_at.desc()).limit(limit).all()
        
        return [memory.to_dict() for memory in memories]
    
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
        """
        # 获取或创建 Memory Bank
        memory_bank = await self._get_or_create_memory_bank(user_id, memory_bank_id)
        
        now = int(time.time() * 1000)
        
        # 创建记忆记录
        memory = AgentMemory(
            user_id=user_id,
            memory_bank_id=memory_bank.id,
            session_id=session_id,
            content=content,
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        
        logger.info(f"[VertexAiMemoryBankService] Created memory {memory.id} for user {user_id}")
        return memory.to_dict()
    
    async def get_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取记忆
        """
        memory = self.db.query(AgentMemory).filter(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id
        ).first()
        
        if memory:
            return memory.to_dict()
        return None
    
    async def delete_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> bool:
        """
        删除记忆
        """
        memory = self.db.query(AgentMemory).filter(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id
        ).first()
        
        if memory:
            self.db.delete(memory)
            self.db.commit()
            logger.info(f"[VertexAiMemoryBankService] Deleted memory {memory_id} for user {user_id}")
            return True
        
        return False
    
    async def _get_or_create_memory_bank(
        self,
        user_id: str,
        memory_bank_id: Optional[str] = None
    ) -> AgentMemoryBank:
        """
        获取或创建 Memory Bank
        
        Args:
            user_id: 用户 ID
            memory_bank_id: Memory Bank ID（可选）
            
        Returns:
            AgentMemoryBank 实例
        """
        if memory_bank_id:
            memory_bank = self.db.query(AgentMemoryBank).filter(
                AgentMemoryBank.id == memory_bank_id,
                AgentMemoryBank.user_id == user_id
            ).first()
            
            if memory_bank:
                return memory_bank
        
        # 创建新的 Memory Bank
        now = int(time.time() * 1000)
        memory_bank = AgentMemoryBank(
            user_id=user_id,
            name=f"Memory Bank {now}",
            created_at=now,
            updated_at=now
        )
        
        # 如果 Vertex AI 可用，创建实际的 Memory Bank
        if self._vertexai_available and self._vertexai_client:
            try:
                # 创建 Agent Engine（如果还没有）
                if not self.agent_engine_id:
                    agent_engine = self._vertexai_client.agent_engines.create(
                        config={
                            "context_spec": {
                                "memory_bank_config": {
                                    "generation_config": {
                                        "model": f"projects/{self.project}/locations/{self.location}/publishers/google/models/gemini-2.5-flash"
                                    }
                                }
                            }
                        }
                    )
                    self.agent_engine_id = agent_engine.api_resource.name.split("/")[-1]
                
                memory_bank.vertex_memory_bank_id = self.agent_engine_id
            except Exception as e:
                logger.warning(f"[VertexAiMemoryBankService] Failed to create Vertex AI Memory Bank: {e}")
        
        self.db.add(memory_bank)
        self.db.commit()
        self.db.refresh(memory_bank)
        
        logger.info(f"[VertexAiMemoryBankService] Created memory bank {memory_bank.id} for user {user_id}")
        return memory_bank
