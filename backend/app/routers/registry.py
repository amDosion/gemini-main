"""
路由注册模块

统一管理所有 API 路由的注册，便于维护和扩展。
所有路由注册逻辑集中在此文件中，添加新路由时只需修改此文件。
"""

from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

from ..core.config import settings

# 导入所有路由模块
from .core import chat, modes, attachments
from .auth_boundary import include_router_with_auth_boundary
from .system import health_router, dashscope_proxy_router, file_search_router, system_admin_router
from .storage import storage_router
from .tools import (
    browse_router, pdf_router, live_api_router, table_analysis_router, batch_jobs_router
)
from .ai import (
    embedding_router, research_router, research_stream_router,
    interactions_router, multi_agent_router
)
from .ai.workflows import router as workflows_router
from .user import (
    profiles_router, sessions_router, personas_router, init_router, mcp_config_router
)
from .models import (
    models_router, providers_router, ollama_models_router, vertex_ai_config_router
)
# 虚拟试衣走统一路由 /api/modes/{provider}/virtual-try-on，不单独注册 tryon 路由
# 特殊提供商路由已统一到 core/chat.py 和 core/modes.py
# from .providers import google_chat_router, tongyi_image_router

# 认证路由（可选）
try:
    from .auth import router as auth_router
    AUTH_ROUTER_AVAILABLE = True
except ImportError as e:
    import traceback
    logger.error(f"[Registry] Failed to import auth router: {e}")
    logger.error(f"[Registry] Traceback: {traceback.format_exc()}")
    AUTH_ROUTER_AVAILABLE = False
    auth_router = None
except Exception as e:
    import traceback
    logger.error(f"[Registry] Unexpected error importing auth router: {e}")
    logger.error(f"[Registry] Traceback: {traceback.format_exc()}")
    AUTH_ROUTER_AVAILABLE = False
    auth_router = None


def register_routers(app: FastAPI):
    """
    注册所有 API 路由
    
    Args:
        app: FastAPI 应用实例
    """
    
    logger.info("Global auth boundary enabled: %s", settings.enable_global_auth_boundary)

    # ==================== 系统路由 ====================
    include_router_with_auth_boundary(app, health_router)
    include_router_with_auth_boundary(app, dashscope_proxy_router)
    include_router_with_auth_boundary(app, file_search_router)
    include_router_with_auth_boundary(app, system_admin_router)
    
    # ==================== 存储路由 ====================
    include_router_with_auth_boundary(app, storage_router)
    
    # ==================== 工具路由 ====================
    include_router_with_auth_boundary(app, browse_router)
    include_router_with_auth_boundary(app, pdf_router)
    include_router_with_auth_boundary(app, live_api_router)
    include_router_with_auth_boundary(app, table_analysis_router)
    include_router_with_auth_boundary(app, batch_jobs_router)
    
    # ==================== AI 功能路由 ====================
    include_router_with_auth_boundary(app, embedding_router)
    include_router_with_auth_boundary(app, research_router)
    include_router_with_auth_boundary(app, research_stream_router)
    include_router_with_auth_boundary(app, interactions_router)
    
    # Multi-Agent API 路由（必须在 chat 路由之前注册，避免路径冲突）
    try:
        include_router_with_auth_boundary(app, multi_agent_router)
        logger.info("Multi-Agent router registered successfully")
    except Exception as e:
        logger.error(f"Failed to register multi_agent_router: {e}", exc_info=True)
    
    # Workflow Engine API 路由 (Phase 1)
    try:
        include_router_with_auth_boundary(app, workflows_router)
        logger.info("Workflows router registered successfully")
        template_routes = [
            route
            for route in app.routes
            if hasattr(route, "path")
            and str(getattr(route, "path", "")).startswith("/api/workflows/templates")
        ]
        if template_routes:
            logger.info(f"Workflow template routes registered: {len(template_routes)}")
        else:
            logger.warning("Workflow template routes not found after workflows router registration")
    except Exception as e:
        logger.error(f"Failed to register workflows_router: {e}", exc_info=True)
    
    
    # ==================== 用户路由 ====================
    include_router_with_auth_boundary(app, profiles_router)
    include_router_with_auth_boundary(app, sessions_router)
    include_router_with_auth_boundary(app, personas_router)
    include_router_with_auth_boundary(app, init_router)
    include_router_with_auth_boundary(app, mcp_config_router)
    
    # ==================== 模型管理路由 ====================
    include_router_with_auth_boundary(app, models_router)
    include_router_with_auth_boundary(app, providers_router)
    include_router_with_auth_boundary(app, ollama_models_router)
    include_router_with_auth_boundary(app, vertex_ai_config_router)
    
    # ==================== 核心路由（统一入口，放在最后以确保优先级）====================
    include_router_with_auth_boundary(app, chat)  # 统一聊天路由 /api/modes/{provider}/chat
    include_router_with_auth_boundary(app, modes)  # 统一模式路由 /api/modes/{provider}/{mode}
    include_router_with_auth_boundary(app, attachments.router)  # 附件路由 /api/temp-images/{attachment_id}, /api/attachments/*
    
    # ==================== 认证路由（可选）====================
    if AUTH_ROUTER_AVAILABLE and auth_router:
        include_router_with_auth_boundary(app, auth_router)
        logger.info("✅ Auth router registered successfully")
        # 验证路由是否注册
        auth_routes = [r for r in app.routes if hasattr(r, 'path') and '/api/auth' in r.path]
        if auth_routes:
            logger.info(f"   Registered {len(auth_routes)} auth routes:")
            for route in auth_routes[:5]:  # 只显示前5个
                logger.info(f"   - {route.methods if hasattr(route, 'methods') else 'N/A'} {route.path if hasattr(route, 'path') else 'N/A'}")
        else:
            logger.warning("   ⚠️  WARNING: No auth routes found after registration!")
    else:
        logger.warning("⚠️  Auth router not available (AUTH_ROUTER_AVAILABLE=%s, auth_router=%s)", 
                      AUTH_ROUTER_AVAILABLE, auth_router is not None)
    
    logger.info(
        "API routes registered (core: chat, modes; "
        "system: health, dashscope_proxy, file_search, system_admin; "
        "storage; "
        "tools: browse, pdf, live_api, table_analysis, batch_jobs; "
        "ai: embedding, research, research_stream, interactions, multi_agent; "
        "user: profiles, sessions, personas, init, mcp_config; "
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
