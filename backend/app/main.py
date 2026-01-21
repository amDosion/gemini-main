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
import subprocess
import sys
import atexit
import platform
import signal
from pathlib import Path

# 导入统一的环境变量加载模块（确保 .env 文件已加载，必须在其他导入之前）
from .core.env_loader import _ENV_LOADED  # noqa: F401

# Import logger and progress tracker
try:
    from .core.logger import setup_logger, LOG_PREFIXES
    from .services.common.progress_tracker import progress_tracker
    # Root logger is already configured in logger.py module import
    logger = setup_logger("main")
except ImportError:
    try:
        from core.logger import setup_logger, LOG_PREFIXES
        from services.common.progress_tracker import progress_tracker
        # Root logger is already configured in logger.py module import
        logger = setup_logger("main")
    except ImportError:
        # 从项目根目录启动时的导入路径
        from backend.app.core.logger import setup_logger, LOG_PREFIXES
        from backend.app.services.common.progress_tracker import progress_tracker
        # Root logger is already configured in logger.py module import
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
    from .services.gemini.browser import read_webpage, selenium_browse, SELENIUM_AVAILABLE
except ImportError:
    try:
        # Fall back to absolute import (when run directly: python main.py)
        from services.gemini.browser import read_webpage, selenium_browse, SELENIUM_AVAILABLE
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.gemini.browser import read_webpage, selenium_browse, SELENIUM_AVAILABLE
        except ImportError as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Could not import browser module: {e}")
            logger.info("Install browser dependencies with: pip install selenium webdriver-manager beautifulsoup4")
            SELENIUM_AVAILABLE = False
            # Define fallback functions to prevent NameError
            def read_webpage(*args, **kwargs):
                raise RuntimeError("Browser module not available")
            def selenium_browse(*args, **kwargs):
                raise RuntimeError("Browser module not available")

# PDF extractor module import (now in gemini directory)
try:
    # Try relative import first (when run as module: python -m backend.app.main)
    from .services.gemini.pdf_extractor import (
        extract_structured_data_from_pdf,
        get_available_templates
    )
    PDF_EXTRACTION_AVAILABLE = True
except ImportError:
    try:
        # Fall back to absolute import (when run directly: python main.py)
        from services.gemini.pdf_extractor import (
            extract_structured_data_from_pdf,
            get_available_templates
        )
        PDF_EXTRACTION_AVAILABLE = True
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.gemini.pdf_extractor import (
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
    from .services.common.embedding_service import rag_service
    EMBEDDING_AVAILABLE = True
except ImportError:
    try:
        # Fall back to absolute import (when run directly: python main.py)
        from services.common.embedding_service import rag_service
        EMBEDDING_AVAILABLE = True
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.common.embedding_service import rag_service
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

# Import router registry (统一路由注册)
try:
    from .routers.registry import register_routers, register_service_dependencies
    ROUTER_REGISTRY_AVAILABLE = True
    logger.info(f"{LOG_PREFIXES['info']} Router registry imported via relative import")
except ImportError:
    try:
        from routers.registry import register_routers, register_service_dependencies
        ROUTER_REGISTRY_AVAILABLE = True
        logger.info(f"{LOG_PREFIXES['info']} Router registry imported via absolute import (routers)")
    except ImportError:
        try:
            from backend.app.routers.registry import register_routers, register_service_dependencies
            ROUTER_REGISTRY_AVAILABLE = True
            logger.info(f"{LOG_PREFIXES['info']} Router registry imported via backend.app.routers")
        except ImportError as e:
            logger.error(f"{LOG_PREFIXES['error']} Could not import router registry: {e}", exc_info=True)
            import traceback
            logger.error(f"{LOG_PREFIXES['error']} Import traceback:\n{traceback.format_exc()}")
            ROUTER_REGISTRY_AVAILABLE = False

# Import upload worker pool
try:
    from .services.common.upload_worker_pool import worker_pool
    WORKER_POOL_AVAILABLE = True
    logger.info(f"{LOG_PREFIXES['info']} Worker pool imported via relative import")
except ImportError:
    try:
        from services.common.upload_worker_pool import worker_pool
        WORKER_POOL_AVAILABLE = True
        logger.info(f"{LOG_PREFIXES['info']} Worker pool imported via absolute import (services)")
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.services.common.upload_worker_pool import worker_pool
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
    cleanup_task: asyncio.Task | None = None

    # ✅ 确保日志配置在应用启动时生效（Uvicorn 启动后可能覆盖配置）
    try:
        from .core.logger import setup_root_logger, ensure_service_loggers
        # 重新配置根 logger（防止 Uvicorn 覆盖）
        setup_root_logger()
        # 确保所有服务 logger 配置正确
        ensure_service_loggers()
        logger.info(f"{LOG_PREFIXES['success']} Logger configuration ensured in lifespan")
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Failed to ensure logger configuration: {e}")

    # ✅ 初始化密钥（从 .env 文件读取）
    try:
        from .core.encryption import EncryptionKeyManager
        from .core.jwt_utils import JWTSecretManager
        
        # 确保 ENCRYPTION_KEY 已读取（从 .env 文件）
        encryption_key = EncryptionKeyManager.get_or_create_key()
        # 显示前 8 个字符和后 4 个字符，中间用 ... 代替
        masked_key = f"{encryption_key[:8]}...{encryption_key[-4:]}" if len(encryption_key) > 12 else encryption_key
        logger.info(f"{LOG_PREFIXES['success']} ENCRYPTION_KEY 已初始化（长度: {len(encryption_key)}, 值: {masked_key}）")
        
        # 确保 JWT_SECRET_KEY 已读取（从 .env 文件）
        jwt_secret = JWTSecretManager.get_or_create_secret()
        # 显示前 8 个字符和后 4 个字符，中间用 ... 代替
        masked_secret = f"{jwt_secret[:8]}...{jwt_secret[-4:]}" if len(jwt_secret) > 12 else jwt_secret
        logger.info(f"{LOG_PREFIXES['success']} JWT_SECRET_KEY 已初始化（长度: {len(jwt_secret)}, 值: {masked_secret}）")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} 密钥初始化失败: {e}")
        raise
    
    # ✅ 初始化系统配置
    try:
        from .core.database import SessionLocal
        from .services.common.system_config_service import initialize_system_configs
        db = SessionLocal()
        try:
            initialize_system_configs(db)
            logger.info(f"{LOG_PREFIXES['success']} System configuration initialized")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Failed to initialize system config: {e}")
    
    # ✅ TASK-002: 初始化全局 Redis 连接池
    try:
        from .services.common.redis_queue_service import GlobalRedisConnectionPool
        global_redis_pool = GlobalRedisConnectionPool.get_instance()
        await global_redis_pool.initialize()
        logger.info(f"{LOG_PREFIXES['success']} Global Redis connection pool initialized")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Failed to initialize global Redis connection pool: {e}")
        logger.error("WARNING: Application will continue but Redis operations may fail!")
        import traceback
        traceback.print_exc()
    
    # ✅ 启动时清理过期的 refresh_tokens
    try:
        from .core.database import SessionLocal
        from .models.db_models import RefreshToken
        from datetime import datetime, timezone, timedelta
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            # 删除已过期或已撤销超过 7 天的记录
            cleanup_threshold = now - timedelta(days=7)
            deleted_count = db.query(RefreshToken).filter(
                (RefreshToken.expires_at < now) |
                (
                    (RefreshToken.revoked_at.isnot(None)) &
                    (RefreshToken.revoked_at < cleanup_threshold)
                )
            ).delete()
            db.commit()
            if deleted_count > 0:
                logger.info(f"{LOG_PREFIXES['success']} Cleaned up {deleted_count} expired/revoked refresh tokens on startup")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Failed to cleanup refresh tokens: {e}")
    
    # ✅ 启动定期清理任务（每 24 小时清理一次）
    async def _periodic_cleanup_tokens():
        """定期清理过期的 refresh_tokens"""
        # 首次等待 1 小时后再开始清理（避免启动时立即执行）
        await asyncio.sleep(60 * 60)  # 1 小时
        
        while True:
            try:
                from .core.database import SessionLocal
                from .models.db_models import RefreshToken
                from datetime import datetime, timezone, timedelta
                db = SessionLocal()
                try:
                    now = datetime.now(timezone.utc)
                    cleanup_threshold = now - timedelta(days=7)
                    deleted_count = db.query(RefreshToken).filter(
                        (RefreshToken.expires_at < now) |
                        (
                            (RefreshToken.revoked_at.isnot(None)) &
                            (RefreshToken.revoked_at < cleanup_threshold)
                        )
                    ).delete()
                    db.commit()
                    if deleted_count > 0:
                        logger.info(f"{LOG_PREFIXES['info']} Periodic cleanup: removed {deleted_count} expired/revoked refresh tokens")
                finally:
                    db.close()
                
                # 等待 24 小时后再次清理
                await asyncio.sleep(24 * 60 * 60)  # 24 小时
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"{LOG_PREFIXES['error']} Periodic token cleanup failed: {e}")
                # 出错后等待 1 小时再重试
                await asyncio.sleep(60 * 60)
    
    # 启动后台清理任务
    cleanup_task = asyncio.create_task(_periodic_cleanup_tokens())
    logger.info(f"{LOG_PREFIXES['success']} Periodic refresh token cleanup task started")
    # Validate provider configurations
    logger.info(f"{LOG_PREFIXES['info']} Validating provider configurations...")
    try:
        from .services.common.provider_config import ProviderConfig
        validation_results = ProviderConfig.validate_all_configs()
        invalid_providers = [p for p, valid in validation_results.items() if not valid]
        if invalid_providers:
            warning_msg = f"{LOG_PREFIXES['warning']} Some providers have invalid configurations: {', '.join(invalid_providers)}"
            logger.warning(warning_msg)
        else:
            logger.info(f"{LOG_PREFIXES['success']} All provider configurations validated successfully")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Failed to validate provider configurations: {e}")
        logger.error("WARNING: Application will continue but some providers may not work correctly!")
    
    if WORKER_POOL_AVAILABLE:
        logger.info(f"{LOG_PREFIXES['info']} Starting upload worker pool (on-demand mode)...")
        try:
            await worker_pool.start()
            logger.info(f"{LOG_PREFIXES['success']} Upload worker pool started successfully (on-demand mode)")

            # 启动后验证（按需调用模式）
            # 注意：按需调用模式下，如果没有 pending 任务，Worker 不会启动
            # 所以不再检查 _workers 列表，只检查基础设施是否就绪
            logger.warning(f"{LOG_PREFIXES['success']} Worker pool startup verification passed (on-demand mode)")
            logger.info(f"{LOG_PREFIXES['info']} Workers will start on-demand when tasks are submitted")

        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Failed to start upload worker pool: {e}")
            logger.error("WARNING: Application will continue but async uploads will NOT work!")
            import traceback
            traceback.print_exc()
            # 不抛出异常，允许应用继续启动（但异步上传将不可用）
    else:
        logger.warning(f"{LOG_PREFIXES['warning']} Upload worker pool not available, async uploads will not work")

    # 后台守护：确保 WorkerPool 的 reconciler 在运行（按需调用模式）
    # 注意：按需调用模式下，Worker 会按需启动/退出，不需要检查 Worker 是否在运行
    # 只需要确保 reconciler 在运行，以便恢复可能遗漏的任务
    if WORKER_POOL_AVAILABLE:
        async def _worker_pool_supervisor():
            backoff_s = 1.0
            while True:
                try:
                    # 按需调用模式下，只需检查 reconciler 是否在运行
                    # 如果 reconciler 停止了，重新启动 worker pool
                    if worker_pool._reconciler is None or worker_pool._reconciler.done():
                        logger.warning(f"{LOG_PREFIXES['warning']} Worker pool reconciler not running; restarting pool...")
                        try:
                            await worker_pool.stop()
                        except Exception as e:
                            logger.error(f"{LOG_PREFIXES['error']} Error stopping worker pool: {e}")

                        await worker_pool.start()
                        logger.info(f"{LOG_PREFIXES['success']} Worker pool restarted by supervisor (on-demand mode)")
                        backoff_s = 1.0

                    await asyncio.sleep(30.0)  # 按需模式下，检查间隔可以更长
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"{LOG_PREFIXES['error']} Worker pool supervisor error: {e}")
                    await asyncio.sleep(backoff_s)
                    backoff_s = min(backoff_s * 2.0, 60.0)

        supervisor_task = asyncio.create_task(_worker_pool_supervisor())

    # Browser session cleanup background task
    browser_cleanup_task: asyncio.Task | None = None
    if SELENIUM_AVAILABLE:
        async def _browser_session_cleanup():
            """Periodically clean up idle browser sessions"""
            while True:
                try:
                    await asyncio.sleep(60.0)  # Check every minute
                    from .services.gemini.browser import cleanup_idle_sessions
                    cleanup_idle_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"{LOG_PREFIXES['error']} Browser session cleanup error: {e}")

        browser_cleanup_task = asyncio.create_task(_browser_session_cleanup())
        logger.info(f"{LOG_PREFIXES['info']} Browser session cleanup task started")


    yield

    # Shutdown
    # ✅ 停止定期清理任务
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    
    if browser_cleanup_task:
        browser_cleanup_task.cancel()
        await asyncio.gather(browser_cleanup_task, return_exceptions=True)

    # Close all browser sessions
    if SELENIUM_AVAILABLE:
        try:
            from .services.gemini.browser import close_all_drivers
            close_all_drivers()
            logger.info(f"{LOG_PREFIXES['success']} All browser sessions closed on shutdown")
        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Error closing browser sessions: {e}")

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
    
    # ✅ TASK-002: 关闭全局 Redis 连接池
    try:
        from .services.common.redis_queue_service import GlobalRedisConnectionPool
        global_redis_pool = GlobalRedisConnectionPool.get_instance()
        await global_redis_pool.close()
        logger.info(f"{LOG_PREFIXES['success']} Global Redis connection pool closed")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Error closing global Redis connection pool: {e}")

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
            from .services.gemini.browser import web_search
        except ImportError:
            try:
                from services.gemini.browser import web_search
            except ImportError:
                try:
                    from backend.app.services.gemini.browser import web_search
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

# Configure CORS
# 注意：使用 httpOnly Cookie 时，allow_origins 不能为 "*"
# 环境变量已通过 env_loader 统一加载，直接使用 os.getenv 即可
import os
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:21573,http://127.0.0.1:21573").split(",")

# ✅ 启用响应压缩（GZip），减少 API 响应体积
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # 只压缩大于 1KB 的响应
)

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
    # 确保日志配置在 uvicorn 启动前完成
    # uvicorn 默认会配置自己的日志，但我们的根 logger 配置应该仍然有效
    # 使用 log_config=None 让 uvicorn 使用默认配置，但我们的根 logger 会处理所有子 logger
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=21574, 
        reload=True,
        log_level="info"  # 确保 uvicorn 使用 info 级别
    )
