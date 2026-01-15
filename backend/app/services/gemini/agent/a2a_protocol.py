"""
A2A Protocol Handler - A2A 协议处理器

提供：
- 消息格式解析（A2A JSON Schema）
- 任务生命周期管理（submitted -> working -> completed）
- 事件队列处理
- 协议转换（A2A <-> Agent 格式）
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import A2ATask, A2AEvent

logger = logging.getLogger(__name__)


class A2AProtocolHandler:
    """
    A2A 协议处理器
    
    负责：
    - 消息格式解析
    - 任务生命周期管理
    - 事件队列处理
    - 协议转换
    """
    
    def __init__(self, db: Session):
        """
        初始化 A2A 协议处理器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[A2AProtocolHandler] Initialized")
    
    async def create_task(
        self,
        user_id: str,
        agent_id: str,
        task_id: str,
        context_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建 A2A 任务
        
        Args:
            user_id: 用户 ID
            agent_id: 智能体 ID
            task_id: A2A 任务 ID
            context_id: A2A 上下文 ID
            metadata: 任务元数据（可选）
            
        Returns:
            任务信息
        """
        now = int(time.time() * 1000)
        
        task = A2ATask(
            user_id=user_id,
            agent_id=agent_id,
            task_id=task_id,
            context_id=context_id,
            status="submitted",
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        logger.info(f"[A2AProtocolHandler] Created task {task_id} for user {user_id}")
        return task.to_dict()
    
    async def update_task_status(
        self,
        user_id: str,
        task_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            status: 新状态（submitted/working/completed/failed）
            metadata: 任务元数据（可选）
            
        Returns:
            是否更新成功
        """
        task = self.db.query(A2ATask).filter(
            A2ATask.task_id == task_id,
            A2ATask.user_id == user_id
        ).first()
        
        if task:
            task.status = status
            task.updated_at = int(time.time() * 1000)
            if metadata:
                task.metadata_json = json.dumps(metadata)
            self.db.commit()
            logger.info(f"[A2AProtocolHandler] Updated task {task_id} status to {status}")
            return True
        
        return False
    
    async def add_event(
        self,
        task_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加事件到事件队列
        
        Args:
            task_id: 任务 ID
            event_type: 事件类型
            event_data: 事件数据（可选）
            
        Returns:
            事件信息
        """
        now = int(time.time() * 1000)
        
        event = A2AEvent(
            task_id=task_id,
            event_type=event_type,
            event_data_json=json.dumps(event_data) if event_data else None,
            created_at=now
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        logger.info(f"[A2AProtocolHandler] Added event {event.id} of type {event_type} to task {task_id}")
        return event.to_dict()
    
    async def get_task(
        self,
        user_id: str,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取任务
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            
        Returns:
            任务信息，如果不存在则返回 None
        """
        task = self.db.query(A2ATask).filter(
            A2ATask.task_id == task_id,
            A2ATask.user_id == user_id
        ).first()
        
        if task:
            return task.to_dict()
        return None
    
    async def get_events(
        self,
        task_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取任务的事件列表
        
        Args:
            task_id: 任务 ID
            limit: 返回结果数量限制
            
        Returns:
            事件列表
        """
        events = self.db.query(A2AEvent).filter(
            A2AEvent.task_id == task_id
        ).order_by(A2AEvent.created_at.asc()).limit(limit).all()
        
        return [event.to_dict() for event in events]
    
    def parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 A2A 消息格式
        
        Args:
            message: A2A 消息（JSON）
            
        Returns:
            解析后的消息
        """
        # 简化实现：直接返回消息
        # 实际应该验证 A2A JSON Schema
        return message
    
    def convert_to_agent_format(self, a2a_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 A2A 消息格式转换为 Agent 格式
        
        Args:
            a2a_message: A2A 消息
            
        Returns:
            Agent 格式消息
        """
        # 简化实现：提取用户输入
        return {
            "input": a2a_message.get("input", ""),
            "context": a2a_message.get("context", {})
        }
    
    def convert_to_a2a_format(self, agent_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 Agent 响应格式转换为 A2A 格式
        
        Args:
            agent_response: Agent 响应
            
        Returns:
            A2A 格式响应
        """
        # 简化实现：包装为 A2A 格式
        return {
            "output": agent_response.get("output", ""),
            "artifacts": agent_response.get("artifacts", []),
            "status": "completed"
        }
