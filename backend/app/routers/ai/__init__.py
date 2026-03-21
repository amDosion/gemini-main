"""
AI 功能路由模块
"""
from .embedding import router as embedding_router
from .research import router as research_router
from .research_stream import router as research_stream_router
from .interactions import router as interactions_router
from .multi_agent import router as multi_agent_router

__all__ = ["embedding_router", "research_router", "research_stream_router", "interactions_router", "multi_agent_router"]
