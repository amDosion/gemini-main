"""
Stream Handler - 流式事件处理

处理 SSE 事件格式转换
"""

import logging
from typing import Dict, Any, AsyncGenerator

logger = logging.getLogger(__name__)


class StreamHandler:
    """流式事件处理器"""
    
    @staticmethod
    def format_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化事件为 SSE 兼容格式（兼容 _interactions API）
        
        支持的事件类型：
        - interaction.start: 交互开始
        - content.delta: 内容增量（text 或 thought_summary）
        - tool.call: 工具调用
        - tool.result: 工具结果
        - status.update: 状态更新
        - interaction.complete: 交互完成
        - error: 错误
        
        Args:
            event: 原始事件
            
        Returns:
            格式化后的事件（兼容 _interactions API 格式）
        """
        event_type = event.get('event_type', 'unknown')
        
        formatted = {
            'event_type': event_type
        }
        
        # 添加 event_id（如果存在）
        if 'event_id' in event:
            formatted['event_id'] = event['event_id']
        
        # 根据事件类型格式化
        if event_type == 'interaction.start':
            formatted['interaction'] = event.get('interaction', {})
        elif event_type == 'content.delta':
            formatted['delta'] = event.get('delta', {})
        elif event_type == 'tool.call':
            formatted['tool_call'] = event.get('tool_call', {})
        elif event_type == 'tool.result':
            formatted['tool_result'] = event.get('tool_result', {})
        elif event_type == 'thinking':
            formatted['thinking'] = event.get('thinking', '')
        elif event_type == 'status.update':
            formatted['status'] = event.get('status', '')
        elif event_type == 'error':
            formatted['error'] = event.get('error', {})
        elif event_type == 'interaction.complete':
            formatted['interaction'] = event.get('interaction', {})
            formatted['usage'] = event.get('usage', {})
        
        return formatted
    
    @staticmethod
    async def process_stream(
        stream: AsyncGenerator[Dict[str, Any], None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理流式事件
        
        Args:
            stream: 原始事件流
            
        Yields:
            格式化后的事件
        """
        async for event in stream:
            formatted = StreamHandler.format_event(event)
            yield formatted
