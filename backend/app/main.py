"""
FastAPI Backend for Gemini Chat Application

This backend provides API endpoints for browser automation, web scraping,
and PDF structured data extraction to be used with the Gemini AI frontend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
import asyncio
import uuid
import json
import sys
import atexit
import platform
import signal
import os
from pathlib import Path

# 导入统一的环境变量加载模块（确保 .env 文件已加载，必须在其他导入之前）
from .core.env_loader import _ENV_LOADED  # noqa: F401

# 导入统一的 import loader
from .core.import_loader import safe_import, create_fallback_function, create_fallback_class

# Import logger and progress tracker
from .core.logger import setup_logger, LOG_PREFIXES
from .services.common.progress_tracker import progress_tracker
logger = setup_logger("main")

# ============================================================================
# Module Imports with Unified Fallback Strategy
# ============================================================================

# Browser module
browser_result = safe_import(
    'services.gemini.common.browser',
    attr_names=['read_webpage', 'selenium_browse', 'SELENIUM_AVAILABLE'],
    fallback_values={
        'SELENIUM_AVAILABLE': False,
        'read_webpage': create_fallback_function("Browser module not available"),
        'selenium_browse': create_fallback_function("Browser module not available")
    },
    warning_message="Could not import browser module",
    info_message="Install browser dependencies with: pip install selenium webdriver-manager beautifulsoup4"
)
read_webpage = browser_result['read_webpage']
selenium_browse = browser_result['selenium_browse']
SELENIUM_AVAILABLE = browser_result['SELENIUM_AVAILABLE']

# PDF extractor module
pdf_result = safe_import(
    'services.gemini.common.pdf_extractor',
    attr_names=['extract_structured_data_from_pdf', 'get_available_templates'],
    fallback_values={
        'extract_structured_data_from_pdf': create_fallback_function("PDF extraction module not available"),
        'get_available_templates': create_fallback_function("PDF extraction module not available")
    },
    warning_message="Could not import PDF extraction module",
    info_message="Install PDF extraction dependencies with: pip install google-generativeai PyPDF2"
)
extract_structured_data_from_pdf = pdf_result['extract_structured_data_from_pdf']
get_available_templates = pdf_result['get_available_templates']
PDF_EXTRACTION_AVAILABLE = pdf_result.success

# Embedding service module
embedding_result = safe_import(
    'services.common.embedding_service',
    attr_names=['rag_service'],
    fallback_values={
        'rag_service': create_fallback_class("Embedding service not available")()
    },
    warning_message="Could not import embedding service",
    info_message="Install embedding dependencies with: pip install chromadb google-generativeai"
)
rag_service = embedding_result['rag_service']
EMBEDDING_AVAILABLE = embedding_result.success

# Database initialization
db_result = safe_import(
    'core.database',
    attr_names=['Base', 'engine']
)
models_result = safe_import(
    'models',
    attr_names=['ConfigProfile', 'UserSettings', 'ChatSession', 'Persona']
)

if db_result.success and models_result.success:
    try:
        Base = db_result['Base']
        engine = db_result['engine']
        Base.metadata.create_all(bind=engine)
        logger.info(f"{LOG_PREFIXES['info']} Database tables initialized")
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Database initialization failed: {e}")
else:
    logger.warning(f"{LOG_PREFIXES['warning']} Could not import database or models")

# Router registry (统一路由注册)
router_registry_result = safe_import(
    'routers.registry',
    attr_names=['register_routers', 'register_service_dependencies'],
    fallback_values={
        'register_routers': None,
        'register_service_dependencies': None
    },
    warning_message="Could not import router registry"
)
register_routers = router_registry_result.get('register_routers')
register_service_dependencies = router_registry_result.get('register_service_dependencies')
ROUTER_REGISTRY_AVAILABLE = router_registry_result.success
if ROUTER_REGISTRY_AVAILABLE:
    logger.info(f"{LOG_PREFIXES['info']} Router registry imported successfully")

# Upload worker pool
worker_result = safe_import(
    'services.common.upload_worker_pool',
    attr_names=['worker_pool'],
    fallback_values={'worker_pool': None},
    warning_message="Could not import upload worker pool"
)
worker_pool = worker_result.get('worker_pool')
WORKER_POOL_AVAILABLE = worker_result.success
if WORKER_POOL_AVAILABLE:
    logger.info(f"{LOG_PREFIXES['info']} Worker pool imported successfully")

# Case conversion middleware (camelCase <-> snake_case 自动转换)
middleware_result = safe_import(
    'middleware.case_conversion_middleware',
    attr_names=['CaseConversionMiddleware'],
    fallback_values={'CaseConversionMiddleware': None},
    warning_message="Could not import case conversion middleware"
)
CaseConversionMiddleware = middleware_result.get('CaseConversionMiddleware')
CASE_CONVERSION_MIDDLEWARE_AVAILABLE = middleware_result.success

# ============================================================================
# Application Lifespan (使用模块化的 lifespan 管理)
# ============================================================================

lifespan_result = safe_import(
    'core.lifespan',
    attr_names=['create_lifespan'],
    fallback_values={'create_lifespan': None}
)
create_lifespan_func = lifespan_result.get('create_lifespan')

if create_lifespan_func:
    # 使用模块化的 lifespan
    lifespan = create_lifespan_func(
        worker_pool=worker_pool if WORKER_POOL_AVAILABLE else None,
        worker_pool_available=WORKER_POOL_AVAILABLE,
        selenium_available=SELENIUM_AVAILABLE,
        log_prefixes=LOG_PREFIXES
    )
else:
    # Fallback: 如果导入失败，创建一个空的 lifespan
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.warning(f"{LOG_PREFIXES['warning']} Lifespan module not available, using empty lifespan")
        yield

# 旧的内联 lifespan 函数已被模块化，以下代码已移至：
# - backend/app/core/startup_tasks.py - 启动任务
# - backend/app/core/cleanup_tasks.py - 清理任务
# - backend/app/core/worker_supervisor.py - Worker 监督
# - backend/app/core/shutdown_tasks.py - 关闭任务
# - backend/app/core/lifespan.py - 协调器

# ============================================================================
# FastAPI Application
# ============================================================================

# Create FastAPI app with lifespan
app = FastAPI(
    title="Gemini Chat Backend",
    description="Backend API for browser automation and web scraping",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# Exception Handlers
# ============================================================================

exception_handlers_result = safe_import(
    'core.exception_handlers',
    attr_names=['register_exception_handlers'],
    fallback_values={'register_exception_handlers': None}
)
register_exception_handlers_func = exception_handlers_result.get('register_exception_handlers')
if register_exception_handlers_func:
    register_exception_handlers_func(app)

# Import auth router
try:
    from .routers.auth import router as auth_router
    AUTH_ROUTER_AVAILABLE = True
except ImportError:
    try:
        from routers.auth import router as auth_router
        AUTH_ROUTER_AVAILABLE = True
    except ImportError:
        try:
            from backend.app.routers.auth import router as auth_router
            AUTH_ROUTER_AVAILABLE = True
        except ImportError:
            AUTH_ROUTER_AVAILABLE = False
            logger.warning(f"{LOG_PREFIXES['warning']} Auth router not available")

# 确保服务 logger 配置正确（在路由注册之前）
try:
    from .core.logger import ensure_service_loggers
    ensure_service_loggers()
    logger.info(f"{LOG_PREFIXES['info']} Service loggers configured")
except Exception as e:
    logger.warning(f"{LOG_PREFIXES['warning']} Failed to configure service loggers: {e}")

# Register all API routes (统一注册)
if ROUTER_REGISTRY_AVAILABLE:
    try:
        register_routers(app)
        
        # Register service dependencies (设置路由所需的外部服务引用)
        # 获取 web_search 函数
        try:
            from .services.gemini.common.browser import web_search
        except ImportError:
            try:
                from services.gemini.common.browser import web_search
            except ImportError:
                try:
                    from backend.app.services.gemini.common.browser import web_search
                except ImportError:
                    web_search = None
        
        register_service_dependencies(
            app=app,
            selenium_available=SELENIUM_AVAILABLE,
            pdf_extraction_available=PDF_EXTRACTION_AVAILABLE,
            embedding_available=EMBEDDING_AVAILABLE,
            worker_pool_available=WORKER_POOL_AVAILABLE,
            selenium_browse=selenium_browse if SELENIUM_AVAILABLE else None,
            read_webpage=read_webpage if SELENIUM_AVAILABLE else None,
            web_search=web_search,
            progress_tracker=progress_tracker,
            extract_structured_data_from_pdf=extract_structured_data_from_pdf if PDF_EXTRACTION_AVAILABLE else None,
            get_available_templates=get_available_templates if PDF_EXTRACTION_AVAILABLE else None,
            rag_service=rag_service if EMBEDDING_AVAILABLE else None,
            logger_instance=logger,
            log_prefixes=LOG_PREFIXES
        )
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Failed to register routes: {e}", exc_info=True)
        import traceback
        logger.error(f"{LOG_PREFIXES['error']} Registration traceback:\n{traceback.format_exc()}")
else:
    logger.error(f"{LOG_PREFIXES['error']} Router registry not available, routes will not be registered!")

# Log module availability on startup
startup_separator = "=" * 60
logger.info(startup_separator)
logger.info(">>> Gemini Chat Backend Starting...")
logger.info(startup_separator)
selenium_status = '[YES]' if SELENIUM_AVAILABLE else '[NO]'
logger.info(f"Selenium Available: {selenium_status}")
pdf_status = '[YES]' if PDF_EXTRACTION_AVAILABLE else '[NO]'
logger.info(f"PDF Extraction Available: {pdf_status}")
embedding_status = '[YES]' if EMBEDDING_AVAILABLE else '[NO]'
logger.info(f"Embedding Service Available: {embedding_status}")
worker_status = '[YES]' if WORKER_POOL_AVAILABLE else '[NO]'
logger.info(f"Upload Worker Pool Available: {worker_status}")
router_status = '[YES]' if ROUTER_REGISTRY_AVAILABLE else '[NO]'
logger.info(f"Router Registry Available: {router_status}")
logger.info(startup_separator)

# ============================================================================
# Request Logging Middleware - REMOVED (Debug code should not be in production)
# ============================================================================

# ============================================================================
# Middleware Configuration
# ============================================================================

middleware_config_result = safe_import(
    'core.middleware_config',
    attr_names=['configure_middlewares'],
    fallback_values={'configure_middlewares': None}
)
configure_middlewares_func = middleware_config_result.get('configure_middlewares')
if configure_middlewares_func:
    configure_middlewares_func(
        app=app,
        case_conversion_middleware=CaseConversionMiddleware,
        case_conversion_available=CASE_CONVERSION_MIDDLEWARE_AVAILABLE,
        log_prefixes=LOG_PREFIXES
    )

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from .core.config import settings
    # 确保日志配置在 uvicorn 启动前完成
    # uvicorn 默认会配置自己的日志，但我们的根 logger 配置应该仍然有效
    # 使用 log_config=None 让 uvicorn 使用默认配置，但我们的根 logger 会处理所有子 logger
    uvicorn.run(
        app, 
        host=settings.host, 
        port=settings.port, 
        reload=True,
        log_level="info"  # 确保 uvicorn 使用 info 级别
    )
