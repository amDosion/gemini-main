"""
Live API Handler - Live API 处理器

提供：
- query()：标准查询（同步）
- stream_query()：服务器端流式查询
- bidi_stream_query()：双向流式查询（WebSocket/SSE）
- 用户中断处理
"""

import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class LiveAPIHandler:
    """
    Live API 处理器
    
    负责：
    - 标准查询（同步）
    - 流式查询（服务器推送）
    - 双向流式查询（WebSocket）
    - 用户中断处理
    """
    
    def __init__(self, db: Session):
        """
        初始化 Live API 处理器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[LiveAPIHandler] Initialized")
    
    async def query(
        self,
        user_id: str,
        input_data: str,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        标准查询（同步）
        
        Args:
            user_id: 用户 ID
            input_data: 输入数据
            agent_id: 智能体 ID（可选）
            
        Returns:
            完整响应
        """
        # 简化实现：直接返回结果
        # 实际应该调用智能体执行逻辑
        return {
            "output": f"Response to: {input_data}",
            "status": "completed"
        }
    
    async def stream_query(
        self,
        user_id: str,
        input_data: str,
        agent_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        服务器端流式查询
        
        Args:
            user_id: 用户 ID
            input_data: 输入数据
            agent_id: 智能体 ID（可选）
            
        Yields:
            增量响应块
        """
        # 简化实现：模拟流式输出
        words = input_data.split()
        for i, word in enumerate(words):
            yield {
                "chunk": f"{word} ",
                "progress": f"{i+1}/{len(words)}"
            }
            await asyncio.sleep(0.1)
        
        yield {
            "status": "completed",
            "output": f"Response to: {input_data}"
        }
    
    async def bidi_stream_query(
        self,
        user_id: str,
        queue: asyncio.Queue,
        agent_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        双向流式查询
        
        Args:
            user_id: 用户 ID
            queue: 消息队列（用于接收用户输入）
            agent_id: 智能体 ID（可选）
            
        Yields:
            响应块
        """
        logger.info(f"[LiveAPIHandler] Bidi stream session started for user {user_id}")
        
        while True:
            try:
                # 等待消息
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                user_input = message.get("input", "")
                
                # 检查退出命令
                if user_input.lower() in ("exit", "quit"):
                    yield {"output": "Goodbye!"}
                    break
                
                # 处理输入并返回响应
                yield {"output": f"Echo: {user_input}"}
                
            except asyncio.TimeoutError:
                # 超时，发送心跳
                yield {"type": "heartbeat"}
            except Exception as e:
                logger.error(f"[LiveAPIHandler] Error in bidi stream: {e}", exc_info=True)
                yield {"error": str(e)}
                break
