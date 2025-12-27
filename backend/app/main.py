"""
FastAPI Backend for Gemini Chat Application

This backend provides API endpoints for browser automation, web scraping,
and PDF structured data extraction to be used with the Gemini AI frontend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
import asyncio
import uuid
import json

# Import logger and progress tracker
try:
    from .core.logger import setup_logger, LOG_PREFIXES
    from .services.progress_tracker import progress_tracker
    logger = setup_logger("main")
except ImportError:
    try:
        from core.logger import setup_logger, LOG_PREFIXES
        from services.progress_tracker import progress_tracker
        logger = setup_logger("main")
    except ImportError:
        # 从项目根目录启动时的导入路径
        from backend.app.core.logger import setup_logger, LOG_PREFIXES
        from backend.app.services.progress_tracker import progress_tracker
        logger = setup_logger("main")

# ============================================================================
# Module Imports with Fallback Strategy
# ============================================================================
# This application supports two execution methods:
# 1. As a module: python -m backend.app.main (from workspace root)
# 2. Direct execution: python main.py (from backend/app directory)
#
# We use relative imports (with dot notation) as the primary method, which is
# the Python best practice for package-internal imports. For direct execution
# compatibility, we fall back to absolute imports if relative imports fail.
# ============================================================================

# Browser module import
try:
    # Try relative import first (when run as module: python -m backend.app.main)
    from .services.browser import read_webpage, selenium_browse, SELENIUM_AVAILABLE
except ImportError:
    try:
        # Fall back to absolute import (when run directly: python main.py)
        from services.browser import read_webpage, selenium_browse, SELENIUM_AVAILABLE
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.browser import read_webpage, selenium_browse, SELENIUM_AVAILABLE
        except ImportError as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Could not import browser module: {e}")
            logger.info("Install browser dependencies with: pip install selenium webdriver-manager beautifulsoup4")
            SELENIUM_AVAILABLE = False
            # Define fallback functions to prevent NameError
            def read_webpage(*args, **kwargs):
                raise RuntimeError("Browser module not available")
            def selenium_browse(*args, **kwargs):
                raise RuntimeError("Browser module not available")

# PDF extractor module import
try:
    # Try relative import first (when run as module: python -m backend.app.main)
    from .services.pdf_extractor import (
        extract_structured_data_from_pdf,
        get_available_templates
    )
    PDF_EXTRACTION_AVAILABLE = True
except ImportError:
    try:
        # Fall back to absolute import (when run directly: python main.py)
        from services.pdf_extractor import (
            extract_structured_data_from_pdf,
            get_available_templates
        )
        PDF_EXTRACTION_AVAILABLE = True
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.pdf_extractor import (
                extract_structured_data_from_pdf,
                get_available_templates
            )
            PDF_EXTRACTION_AVAILABLE = True
        except ImportError as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Could not import PDF extraction module: {e}")
            logger.info("Install PDF extraction dependencies with: pip install google-generativeai PyPDF2")
            PDF_EXTRACTION_AVAILABLE = False
            # Define fallback functions to prevent NameError
            def extract_structured_data_from_pdf(*args, **kwargs):
                raise RuntimeError("PDF extraction module not available")
            def get_available_templates(*args, **kwargs):
                raise RuntimeError("PDF extraction module not available")

# Embedding service module import
try:
    # Try relative import first (when run as module: python -m backend.app.main)
    from .services.embedding_service import rag_service
    EMBEDDING_AVAILABLE = True
except ImportError:
    try:
        # Fall back to absolute import (when run directly: python main.py)
        from services.embedding_service import rag_service
        EMBEDDING_AVAILABLE = True
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.embedding_service import rag_service
            EMBEDDING_AVAILABLE = True
        except ImportError as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Could not import embedding service: {e}")
            logger.info("Install embedding dependencies with: pip install chromadb google-generativeai")
            EMBEDDING_AVAILABLE = False
            # Define fallback object to prevent NameError
            class _DummyRAGService:
                def __getattr__(self, name):
                    raise RuntimeError("Embedding service not available")
            rag_service = _DummyRAGService()

# Initialize database tables on startup
try:
    from .core.database import Base, engine
    from .models import ConfigProfile, UserSettings, ChatSession, Persona, History
    Base.metadata.create_all(bind=engine)
    logger.info(f"{LOG_PREFIXES['info']} Database tables initialized")
except ImportError:
    try:
        from core.database import Base, engine
        from models import ConfigProfile, UserSettings, ChatSession, Persona, History
        Base.metadata.create_all(bind=engine)
        logger.info(f"{LOG_PREFIXES['info']} Database tables initialized")
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.core.database import Base, engine
            from backend.app.models import ConfigProfile, UserSettings, ChatSession, Persona, History
            Base.metadata.create_all(bind=engine)
            logger.info(f"{LOG_PREFIXES['info']} Database tables initialized")
        except Exception as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Database initialization failed: {e}")
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Database initialization failed: {e}")
except Exception as e:
    logger.warning(f"{LOG_PREFIXES['warning']} Database initialization failed: {e}")

# Import API routers
try:
    from .routers import health, storage, browse, pdf, embedding, dashscope_proxy, research, research_stream, metrics, interactions, file_search
    from .routers.profiles import router as profiles_router
    from .routers.sessions import router as sessions_router
    from .routers.personas import router as personas_router
    from .routers.image_expand import router as image_expand_router
    from .routers.tryon import router as tryon_router
    API_ROUTES_AVAILABLE = True
    logger.info(f"{LOG_PREFIXES['info']} API routes imported via relative import")
except ImportError:
    try:
        from routers import health, storage, browse, pdf, embedding, dashscope_proxy, research, research_stream, metrics, interactions, file_search
        from routers.profiles import router as profiles_router
        from routers.sessions import router as sessions_router
        from routers.personas import router as personas_router
        from routers.image_expand import router as image_expand_router
        from routers.tryon import router as tryon_router
        API_ROUTES_AVAILABLE = True
        logger.info(f"{LOG_PREFIXES['info']} API routes imported via absolute import (routers)")
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.routers import health, storage, browse, pdf, embedding, dashscope_proxy, research, research_stream, metrics, interactions, file_search
            from backend.app.routers.profiles import router as profiles_router
            from backend.app.routers.sessions import router as sessions_router
            from backend.app.routers.personas import router as personas_router
            from backend.app.routers.image_expand import router as image_expand_router
            from backend.app.routers.tryon import router as tryon_router
            API_ROUTES_AVAILABLE = True
            logger.info(f"{LOG_PREFIXES['info']} API routes imported via backend.app.routers")
        except ImportError as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Could not import API routes module: {e}")
            API_ROUTES_AVAILABLE = False

# Import upload worker pool
try:
    from .services.upload_worker_pool import worker_pool
    WORKER_POOL_AVAILABLE = True
    logger.info(f"{LOG_PREFIXES['info']} Worker pool imported via relative import")
except ImportError:
    try:
        from services.upload_worker_pool import worker_pool
        WORKER_POOL_AVAILABLE = True
        logger.info(f"{LOG_PREFIXES['info']} Worker pool imported via absolute import (services)")
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.upload_worker_pool import worker_pool
            WORKER_POOL_AVAILABLE = True
            logger.info(f"{LOG_PREFIXES['info']} Worker pool imported via backend.app.services")
        except ImportError as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Could not import upload worker pool: {e}")
            WORKER_POOL_AVAILABLE = False

# ============================================================================
# Application Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时:
    - 启动 Redis 队列 Worker 池（5个并发 Worker）
    - 执行崩溃恢复（重新入队未完成的任务）

    关闭时:
    - 优雅停止 Worker 池（等待当前任务完成）
    """
    supervisor_task: asyncio.Task | None = None

    # Startup
    if WORKER_POOL_AVAILABLE:
        logger.info(f"{LOG_PREFIXES['info']} Starting upload worker pool...")
        try:
            await worker_pool.start()
            logger.info(f"{LOG_PREFIXES['success']} Upload worker pool started successfully")

            # 启动后验证
            await asyncio.sleep(1)  # 等待 Workers 初始化

            if not worker_pool._running:
                raise RuntimeError("Worker pool started but _running flag is False")

            if len(worker_pool._workers) == 0:
                raise RuntimeError("Worker pool started but no workers are running")

            logger.warning(f"{LOG_PREFIXES['success']} Worker pool startup verification passed")

        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Failed to start upload worker pool: {e}")
            logger.error("WARNING: Application will continue but async uploads will NOT work!")
            import traceback
            traceback.print_exc()
            # 不抛出异常，允许应用继续启动（但异步上传将不可用）
    else:
        logger.warning(f"{LOG_PREFIXES['warning']} Upload worker pool not available, async uploads will not work")

    # 后台守护：如果 WorkerPool 启动失败/运行中断，自动重试启动（避免只能靠重启服务）
    if WORKER_POOL_AVAILABLE:
        async def _worker_pool_supervisor():
            backoff_s = 1.0
            while True:
                try:
                    # 1) 如果标记为 running，但所有 worker task 都已结束，视为失活，重启
                    if worker_pool._running:
                        alive = sum(1 for t in worker_pool._workers if not t.done())
                        if alive == 0 and len(worker_pool._workers) > 0:
                            logger.error(
                                f"{LOG_PREFIXES['error']} Worker pool has no alive workers; restarting..."
                            )
                            try:
                                await worker_pool.stop()
                            except Exception as e:
                                logger.error(f"{LOG_PREFIXES['error']} Error stopping dead worker pool: {e}")

                    # 2) 未运行则尝试启动
                    if not worker_pool._running:
                        logger.warning(f"{LOG_PREFIXES['warning']} Worker pool not running; retrying start...")
                        await worker_pool.start()
                        logger.info(f"{LOG_PREFIXES['success']} Worker pool started by supervisor")
                        backoff_s = 1.0

                    await asyncio.sleep(5.0)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"{LOG_PREFIXES['error']} Worker pool supervisor error: {e}")
                    await asyncio.sleep(backoff_s)
                    backoff_s = min(backoff_s * 2.0, 30.0)

        supervisor_task = asyncio.create_task(_worker_pool_supervisor())

    yield

    # Shutdown
    if supervisor_task:
        supervisor_task.cancel()
        await asyncio.gather(supervisor_task, return_exceptions=True)

    if WORKER_POOL_AVAILABLE:
        logger.info(f"{LOG_PREFIXES['info']} Stopping upload worker pool...")
        try:
            await worker_pool.stop()
            logger.info(f"{LOG_PREFIXES['success']} Upload worker pool stopped gracefully")
        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Error stopping upload worker pool: {e}")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Gemini Chat Backend",
    description="Backend API for browser automation and web scraping",
    version="1.0.0",
    lifespan=lifespan
)

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

# Register API routes
if API_ROUTES_AVAILABLE:
    app.include_router(health.router)
    app.include_router(storage.router)
    app.include_router(browse.router)
    app.include_router(pdf.router)
    app.include_router(embedding.router)
    app.include_router(dashscope_proxy.router)
    app.include_router(profiles_router)
    app.include_router(sessions_router)
    app.include_router(personas_router)
    app.include_router(image_expand_router)
    app.include_router(tryon_router)
    app.include_router(research.router)
    app.include_router(research_stream.router)
    app.include_router(file_search.router)
    app.include_router(metrics.router)
    app.include_router(interactions.router)
    logger.info(f"{LOG_PREFIXES['info']} API routes registered (health, storage, browse, pdf, embedding, profiles, sessions, personas, image_expand, tryon, dashscope_proxy, research, research_stream, file_search, metrics, interactions)")

    # Set service availability flags for health check endpoint
    health.set_availability(
        selenium=SELENIUM_AVAILABLE,
        pdf=PDF_EXTRACTION_AVAILABLE,
        embedding=EMBEDDING_AVAILABLE,
        worker_pool=WORKER_POOL_AVAILABLE
    )
    logger.info(f"{LOG_PREFIXES['info']} Service availability flags updated for health endpoint")
    
    # Set browser service references for browse router
    try:
        from .services.browser import web_search
    except ImportError:
        try:
            from services.browser import web_search
        except ImportError:
            try:
                from backend.app.services.browser import web_search
            except ImportError:
                web_search = None
    
    browse.set_browser_service(
        browse_func=selenium_browse if SELENIUM_AVAILABLE else None,
        read_func=read_webpage if SELENIUM_AVAILABLE else None,
        search_func=web_search,
        available=SELENIUM_AVAILABLE,
        progress_tracker=progress_tracker,
        logger=logger,
        log_prefixes=LOG_PREFIXES
    )
    logger.info(f"{LOG_PREFIXES['info']} Browser service references set for browse router")
    
    # Set PDF service references for pdf router
    pdf.set_pdf_service(
        extract_func=extract_structured_data_from_pdf if PDF_EXTRACTION_AVAILABLE else None,
        templates_func=get_available_templates if PDF_EXTRACTION_AVAILABLE else None,
        available=PDF_EXTRACTION_AVAILABLE
    )
    logger.info(f"{LOG_PREFIXES['info']} PDF service references set for pdf router")
    
    # Set embedding service references for embedding router
    embedding.set_embedding_service(
        service=rag_service if EMBEDDING_AVAILABLE else None,
        available=EMBEDDING_AVAILABLE
    )
    logger.info(f"{LOG_PREFIXES['info']} Embedding service references set for embedding router")

# Register auth router
if AUTH_ROUTER_AVAILABLE:
    app.include_router(auth_router)
    logger.info(f"{LOG_PREFIXES['info']} Auth router registered")
else:
    logger.warning(f"{LOG_PREFIXES['warning']} API routes not available")

# Log module availability on startup
logger.info("=" * 60)
logger.info(">>> Gemini Chat Backend Starting...")
logger.info("=" * 60)
logger.info(f"Selenium Available: {'[YES]' if SELENIUM_AVAILABLE else '[NO]'}")
logger.info(f"PDF Extraction Available: {'[YES]' if PDF_EXTRACTION_AVAILABLE else '[NO]'}")
logger.info(f"Embedding Service Available: {'[YES]' if EMBEDDING_AVAILABLE else '[NO]'}")
logger.info(f"Upload Worker Pool Available: {'[YES]' if WORKER_POOL_AVAILABLE else '[NO]'}")
logger.info("=" * 60)

# Configure CORS
# 注意：使用 httpOnly Cookie 时，allow_origins 不能为 "*"
import os
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # 生产环境必须指定具体域名
    allow_credentials=True,  # 允许 Cookie
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
)






# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
