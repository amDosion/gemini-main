"""
GenAI Agent 类型定义
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class ResearchMode(str, Enum):
    """研究模式"""
    VERTEX_AI = "vertex-ai"
    GEMINI_API = "gemini-api"


@dataclass
class ResearchConfig:
    """研究配置"""
    thinking_summaries: str = 'auto'  # 'auto' | 'none'
    max_iterations: int = 5
    enable_search: bool = True
    enable_code_execution: bool = False
    enable_file_search: bool = False


@dataclass
class ResearchResult:
    """研究结果"""
    session_id: str
    status: str  # 'in_progress' | 'completed' | 'failed'
    outputs: List[Dict[str, Any]]
    error: Optional[str] = None


@dataclass
class StreamEvent:
    """流式事件"""
    event_type: str  # 'content.delta' | 'tool.call' | 'tool.result' | 'thinking' | 'complete' | 'error'
    delta: Optional[Dict[str, Any]] = None
    tool_call: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    thinking: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
