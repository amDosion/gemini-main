"""
Message Converter Module

Handles conversion between standard message format and Google API format.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class MessageConverter:
    """
    Converts messages between standard format and Google API format.
    
    Responsibilities:
    - Convert data structure (content → parts)
    - Handle system messages (merge into first user message)
    - Maintain role names (already correct from router)
    """
    
    @staticmethod
    def build_contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将标准消息格式转换为 Google API 格式（一次性转换）
        
        职责：
        - 转换数据结构（content → parts）
        - 处理 system 消息（合并到第一条用户消息）
        - 不转换角色名称（已经是正确的）
        
        输入格式（来自 Router Layer，已过滤）:
            [{"role": "user"|"model"|"system", "content": str}]
        
        输出格式（Google API）:
            [{"role": "user"|"model", "parts": [{"text": str}]}]
        
        Args:
            messages: 标准消息列表（Router Layer 已过滤）
        
        Returns:
            Google API 格式的消息列表
        
        Raises:
            ValueError: 如果消息列表为空或不包含有效消息
        
        注意：
        - Router Layer 已经过滤了错误消息和空消息
        - Router Layer 保持了原始角色名称（"model"）
        - 此方法只转换结构，不转换角色名称
        - 移除了防御性验证（Router Layer 已保证数据有效）
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")
        
        contents = []
        system_message = None
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            # ✅ 处理 system 消息（合并到第一条用户消息）
            if role == 'system':
                system_message = content
                continue
            
            # ✅ 直接使用 role，不转换（已经是 "model"）
            # 移除了：if role == 'assistant': role = 'model'
            
            # ✅ 构建 SDK 格式的 parts
            parts = [{"text": content}]
            
            # ✅ 如果是第一条用户消息且有 system 消息，将 system 消息前置
            if role == 'user' and system_message and not contents:
                parts[0]["text"] = f"{system_message}\n\n{content}"
                system_message = None
            
            contents.append({
                "role": role,
                "parts": parts
            })
        
        if not contents:
            raise ValueError("No valid messages to convert")
        
        return contents
