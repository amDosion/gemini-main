"""
ADK Integration Helper - ADK 集成辅助函数

提供统一的 ADK Runner 集成点，整合所有服务：
- Memory Bank
- Code Execution
- MCP Tools
- Session Management
"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from sqlalchemy.orm import Session

from .adk_runner import ADKRunner
from .adk_agent import ADKAgent
from .memory_manager import MemoryManager
from .sandbox_manager import SandboxManager

logger = logging.getLogger(__name__)


def create_unified_adk_runner(
    db: Session,
    agent_id: str,
    user_id: str,
    memory_bank_id: Optional[str] = None,
    sandbox_id: Optional[str] = None,
    project: Optional[str] = None,
    location: Optional[str] = None
) -> ADKRunner:
    """
    创建统一的 ADK Runner，整合所有服务
    
    Args:
        db: 数据库会话
        agent_id: 智能体 ID
        user_id: 用户 ID
        memory_bank_id: Memory Bank ID（可选）
        sandbox_id: 沙箱 ID（可选）
        project: Google Cloud 项目 ID（可选）
        location: Google Cloud 位置（可选）
        
    Returns:
        ADKRunner 实例
    """
    # 创建 Memory Manager（如果提供了 memory_bank_id）
    memory_manager = None
    if memory_bank_id:
        memory_manager = MemoryManager(
            db=db,
            use_vertex_ai=bool(project),
            project=project,
            location=location
        )
    
    # 创建 ADK Runner
    runner = ADKRunner(
        db=db,
        agent_id=agent_id,
        memory_manager=memory_manager
    )
    
    logger.info(f"[ADK Integration] Created unified ADK runner for agent {agent_id}")
    return runner


async def execute_with_adk_runner(
    runner: ADKRunner,
    user_id: str,
    session_id: str,
    input_data: str,
    tools: Optional[List[Dict[str, Any]]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    使用 ADK Runner 执行智能体逻辑
    
    Args:
        runner: ADK Runner 实例
        user_id: 用户 ID
        session_id: 会话 ID
        input_data: 输入数据
        tools: 工具列表（可选）
        
    Yields:
        事件流
    """
    async for event in runner.run(
        user_id=user_id,
        session_id=session_id,
        input_data=input_data,
        tools=tools
    ):
        yield event
