"""
系统路由模块
"""
from .health import router as health_router
from .metrics import router as metrics_router
from .dashscope_proxy import router as dashscope_proxy_router
from .file_search import router as file_search_router

__all__ = ["health_router", "metrics_router", "dashscope_proxy_router", "file_search_router"]
