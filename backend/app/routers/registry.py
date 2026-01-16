"""
路由注册模块

统一管理所有 API 路由的注册，便于维护和扩展。
所有路由注册逻辑集中在此文件中，添加新路由时只需修改此文件。
"""

from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

# 导入所有路由模块
from .core import chat, modes
from .system import health_router, metrics_router, dashscope_proxy_router, file_search_router
from .storage import storage_router
from .tools import (
    browse_router, pdf_router, code_execution_router, 
    memory_bank_router, a2a_router, live_api_router, adk_router
)
from .ai import (
    embedding_router, research_router, research_stream_router,
    interactions_router, multi_agent_router
)
from .user import (
    profiles_router, sessions_router, personas_router, init_router
)
from .models import (
    models_router, providers_router, ollama_models_router, vertex_ai_config_router
)
# 特殊提供商路由已统一到 core/chat.py 和 core/modes.py
# from .providers import google_chat_router, tongyi_image_router

# 认证路由（可选）
try:
    from .auth import router as auth_router
    AUTH_ROUTER_AVAILABLE = True
except ImportError:
    AUTH_ROUTER_AVAILABLE = False
    auth_router = None


def register_routers(app: FastAPI):
    """
    注册所有 API 路由
    
    Args:
        app: FastAPI 应用实例
    """
    
    # ==================== 系统路由 ====================
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(dashscope_proxy_router)
    app.include_router(file_search_router)
    
    # ==================== 存储路由 ====================
    app.include_router(storage_router)
    
    # ==================== 工具路由 ====================
    app.include_router(browse_router)
    app.include_router(pdf_router)
    app.include_router(code_execution_router)
    app.include_router(memory_bank_router)
    app.include_router(a2a_router)
    app.include_router(live_api_router)
    
    # ==================== AI 功能路由 ====================
    app.include_router(embedding_router)
    app.include_router(research_router)
    app.include_router(research_stream_router)
    app.include_router(interactions_router)
    
    # Multi-Agent API 路由（必须在 chat 路由之前注册，避免路径冲突）
    try:
        app.include_router(multi_agent_router)
        logger.info("Multi-Agent router registered successfully")
        # 验证路由是否注册
        template_routes = [r for r in app.routes if hasattr(r, 'path') and 'workflows/templates' in r.path and 'GET' in str(r.methods)]
        if template_routes:
            logger.info(f"Template routes registered: {len(template_routes)} routes found")
        else:
            logger.warning("WARNING: Template routes not found after registration!")
    except Exception as e:
        logger.error(f"Failed to register multi_agent_router: {e}", exc_info=True)
    
    # ADK 路由
    try:
        app.include_router(adk_router)
    except Exception as e:
        logger.error(f"Failed to register adk_router: {e}", exc_info=True)
    
    # ==================== 用户路由 ====================
    app.include_router(profiles_router)
    app.include_router(sessions_router)
    app.include_router(personas_router)
    app.include_router(init_router)
    
    # ==================== 模型管理路由 ====================
    app.include_router(models_router)
    app.include_router(providers_router)
    app.include_router(ollama_models_router)
    app.include_router(vertex_ai_config_router)
    
    # ==================== 核心路由（统一入口，放在最后以确保优先级）====================
    app.include_router(chat)  # 统一聊天路由 /api/modes/{provider}/chat
    app.include_router(modes)  # 统一模式路由 /api/modes/{provider}/{mode}
    
    # ==================== 认证路由（可选）====================
    if AUTH_ROUTER_AVAILABLE and auth_router:
        app.include_router(auth_router)
        logger.info("Auth router registered")
    else:
        logger.warning("Auth router not available")
    
    logger.info(
        "API routes registered (core: chat, modes; "
        "system: health, metrics, dashscope_proxy, file_search; "
        "storage; "
        "tools: browse, pdf, code_execution, memory_bank, a2a, live_api, adk; "
        "ai: embedding, research, research_stream, interactions, multi_agent; "
        "user: profiles, sessions, personas, init; "
        "models: models, providers, ollama_models, vertex_ai_config)"
    )


def register_service_dependencies(
    app: FastAPI,
    selenium_available: bool = False,
    pdf_extraction_available: bool = False,
    embedding_available: bool = False,
    worker_pool_available: bool = False,
    selenium_browse=None,
    read_webpage=None,
    web_search=None,
    progress_tracker=None,
    extract_structured_data_from_pdf=None,
    get_available_templates=None,
    rag_service=None,
    logger_instance=None,
    log_prefixes=None
):
    """
    注册服务依赖（在路由注册后调用）
    
    用于设置路由所需的外部服务引用，如浏览器服务、PDF 服务等。
    
    Args:
        app: FastAPI 应用实例
        selenium_available: Selenium 浏览器服务是否可用
        pdf_extraction_available: PDF 提取服务是否可用
        embedding_available: 向量嵌入服务是否可用
        worker_pool_available: 工作池是否可用
        selenium_browse: Selenium 浏览函数
        read_webpage: 网页读取函数
        web_search: 网页搜索函数
        progress_tracker: 进度跟踪器
        extract_structured_data_from_pdf: PDF 结构化数据提取函数
        get_available_templates: 获取可用模板函数
        rag_service: RAG 服务实例
        logger_instance: 日志记录器实例
        log_prefixes: 日志前缀字典
    """
    # Set service availability flags for health check endpoint
    from .system.health import set_availability
    set_availability(
        selenium=selenium_available,
        pdf=pdf_extraction_available,
        embedding=embedding_available,
        worker_pool=worker_pool_available
    )
    if logger_instance:
        logger_instance.info(f"{log_prefixes['info'] if log_prefixes else ''} Service availability flags updated for health endpoint")
    
    # Set browser service references for browse router
    if selenium_browse or read_webpage or web_search:
        from .tools.browse import set_browser_service
        set_browser_service(
            browse_func=selenium_browse if selenium_available else None,
            read_func=read_webpage if selenium_available else None,
            search_func=web_search,
            available=selenium_available,
            progress_tracker=progress_tracker,
            logger=logger_instance,
            log_prefixes=log_prefixes
        )
        if logger_instance:
            logger_instance.info(f"{log_prefixes['info'] if log_prefixes else ''} Browser service references set for browse router")
    
    # Set PDF service references for pdf router
    if extract_structured_data_from_pdf or get_available_templates:
        from .tools.pdf import set_pdf_service
        set_pdf_service(
            extract_func=extract_structured_data_from_pdf if pdf_extraction_available else None,
            templates_func=get_available_templates if pdf_extraction_available else None,
            available=pdf_extraction_available
        )
        if logger_instance:
            logger_instance.info(f"{log_prefixes['info'] if log_prefixes else ''} PDF service references set for pdf router")
    
    # Set embedding service references for embedding router
    if rag_service:
        from .ai.embedding import set_embedding_service
        set_embedding_service(
            service=rag_service if embedding_available else None,
            available=embedding_available
        )
        if logger_instance:
            logger_instance.info(f"{log_prefixes['info'] if log_prefixes else ''} Embedding service references set for embedding router")
