"""
Agent Executor - 智能体执行器

提供：
- AgentExecutor 基类
- 任务执行逻辑
- 错误处理和恢复
- 会话管理
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .a2a_protocol import A2AProtocolHandler

logger = logging.getLogger(__name__)


class AgentExecutor:
    """
    智能体执行器基类
    
    负责：
    - 任务执行逻辑
    - 错误处理和恢复
    - 会话管理
    """
    
    def __init__(self, db: Session, agent_id: str):
        """
        初始化智能体执行器
        
        Args:
            db: 数据库会话
            agent_id: 智能体 ID
        """
        self.db = db
        self.agent_id = agent_id
        self.a2a_handler = A2AProtocolHandler(db=db)
        logger.info(f"[AgentExecutor] Initialized for agent {agent_id}")
    
    async def execute(
        self,
        user_id: str,
        task_id: str,
        context_id: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            context_id: 上下文 ID
            input_data: 输入数据
            
        Returns:
            执行结果
        """
        # 创建任务
        task = await self.a2a_handler.create_task(
            user_id=user_id,
            agent_id=self.agent_id,
            task_id=task_id,
            context_id=context_id
        )
        
        # 更新任务状态为 working
        await self.a2a_handler.update_task_status(
            user_id=user_id,
            task_id=task_id,
            status="working"
        )
        
        try:
            # 执行任务逻辑（子类实现）
            result = await self._execute_task(input_data)
            
            # 更新任务状态为 completed
            await self.a2a_handler.update_task_status(
                user_id=user_id,
                task_id=task_id,
                status="completed",
                metadata={"result": result}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[AgentExecutor] Error executing task {task_id}: {e}", exc_info=True)
            
            # 更新任务状态为 failed
            await self.a2a_handler.update_task_status(
                user_id=user_id,
                task_id=task_id,
                status="failed",
                metadata={"error": str(e)}
            )
            
            raise
    
    async def _execute_task(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务逻辑（子类实现）
        
        Args:
            input_data: 输入数据
            
        Returns:
            执行结果
        """
        raise NotImplementedError
    
    async def cancel(
        self,
        user_id: str,
        task_id: str
    ) -> bool:
        """
        取消任务
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            
        Returns:
            是否取消成功
        """
        # 更新任务状态
        return await self.a2a_handler.update_task_status(
            user_id=user_id,
            task_id=task_id,
            status="cancelled"
        )
