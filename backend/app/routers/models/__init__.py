"""
模型管理路由模块
"""
from .models import router as models_router
from .providers import router as providers_router
from .ollama_models import router as ollama_models_router
from .vertex_ai_config import router as vertex_ai_config_router

__all__ = ["models_router", "providers_router", "ollama_models_router", "vertex_ai_config_router"]
