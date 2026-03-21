"""
GenAI Agent Service - 基于 Gemini API 和 genai SDK 的智能体实现

提供：
- GenAIAgentService: 主服务类
- ResearchAgent: 研究智能体实现
- AdvancedResearchAgent: 高级研究智能体（支持多轮对话和思考过程）
- ToolManager: 工具集成管理
- StreamHandler: 流式事件处理
- AdvancedFeatures: 高级功能模块
"""

from .service import GenAIAgentService
from .research_agent import ResearchAgent
from .tools import ToolManager
from .stream_handler import StreamHandler
from .advanced_features import AdvancedResearchAgent, ConversationState, EventType

__all__ = [
    'GenAIAgentService',
    'ResearchAgent',
    'AdvancedResearchAgent',
    'ToolManager',
    'StreamHandler',
    'ConversationState',
    'EventType',
]
