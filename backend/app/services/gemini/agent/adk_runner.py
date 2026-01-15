"""
ADK Runner - ADK 执行器

提供：
- Runner 类封装
- 事件流处理
- 工具执行协调
- 会话和记忆服务集成
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from sqlalchemy.orm import Session

from ....models.db_models import ADKSession
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class ADKRunner:
    """
    ADK Runner 封装
    
    负责：
    - 事件流处理
    - 工具执行协调
    - 会话和记忆服务集成
    """
    
    def __init__(
        self,
        db: Session,
        agent_id: str,
        memory_manager: Optional[MemoryManager] = None
    ):
        """
        初始化 ADK Runner
        
        Args:
            db: 数据库会话
            agent_id: 智能体 ID
            memory_manager: Memory Manager 实例（可选）
        """
        self.db = db
        self.agent_id = agent_id
        self.memory_manager = memory_manager
        
        # 延迟导入 ADK 相关模块
        try:
            from google.adk.runners import Runner as ADKRunnerClass
            from google.adk.sessions import InMemorySessionService
            from google.adk.memory import InMemoryMemoryService
            
            self._adk_available = True
            self._adk_runner = None
            self._session_service = InMemorySessionService()
            self._memory_service = InMemoryMemoryService() if not memory_manager else None
        except ImportError:
            self._adk_available = False
            logger.warning("[ADKRunner] ADK SDK not available, using simplified mode")
        
        logger.info(f"[ADKRunner] Initialized for agent {agent_id}")
    
    async def run(
        self,
        user_id: str,
        session_id: str,
        input_data: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        运行智能体（流式）
        
        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            input_data: 输入数据
            tools: 工具列表（可选）
            
        Yields:
            事件流
        """
        # 获取或创建 ADK 会话
        session = await self._get_or_create_session(user_id, session_id)
        
        if not self._adk_available or not self._adk_runner:
            # 简化实现：直接返回结果
            yield {
                "type": "content",
                "content": f"Response to: {input_data}",
                "is_final": True
            }
            return
        
        try:
            # 使用 ADK Runner 运行
            # 注意：这里需要实际的 ADK Agent 和 Runner 实例
            # 简化实现：模拟事件流
            from google.genai.types import Content, Part
            
            content = Content(role="user", parts=[Part(text=input_data)])
            
            # 实际应该调用：events = self._adk_runner.run(user_id=user_id, session_id=session_id, new_message=content)
            # 这里简化实现
            yield {
                "type": "content",
                "content": f"Response to: {input_data}",
                "is_final": True
            }
            
        except Exception as e:
            logger.error(f"[ADKRunner] Error running agent: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _get_or_create_session(
        self,
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        获取或创建 ADK 会话
        
        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            
        Returns:
            会话信息
        """
        session = self.db.query(ADKSession).filter(
            ADKSession.user_id == user_id,
            ADKSession.agent_id == self.agent_id,
            ADKSession.session_id == session_id
        ).first()
        
        if session:
            # 更新最后使用时间
            session.last_used_at = int(time.time() * 1000)
            self.db.commit()
            return session.to_dict()
        
        # 创建新会话
        now = int(time.time() * 1000)
        session = ADKSession(
            user_id=user_id,
            agent_id=self.agent_id,
            session_id=session_id,
            created_at=now,
            last_used_at=now
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"[ADKRunner] Created session {session_id} for user {user_id}")
        return session.to_dict()
