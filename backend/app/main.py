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
import subprocess
import sys
import atexit
import platform
import signal
from pathlib import Path

# Import logger and progress tracker
try:
    from .core.logger import setup_logger, LOG_PREFIXES
    from .services.common.progress_tracker import progress_tracker
    logger = setup_logger("main")
except ImportError:
    try:
        from core.logger import setup_logger, LOG_PREFIXES
        from services.common.progress_tracker import progress_tracker
        logger = setup_logger("main")
    except ImportError:
        # 从项目根目录启动时的导入路径
        from backend.app.core.logger import setup_logger, LOG_PREFIXES
        from backend.app.services.common.progress_tracker import progress_tracker
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
    key_service_process: subprocess.Popen | None = None

    # Startup
    # ✅ 自动启动 Key Service（方案 D：Client 进程 + Key Service）
    # 如果启动失败，会自动回退到文件存储（向后兼容）
    try:
        import os
        # 检查是否应该启动 Key Service（可通过环境变量控制）
        auto_start_key_service = os.getenv('AUTO_START_KEY_SERVICE', 'true').lower() == 'true'
        
        if auto_start_key_service:
            # 启动 Key Service 子进程
            try:
                # 获取 Python 解释器路径
                python_exe = sys.executable
                
                # 计算项目根目录
                # 从 backend/app/main.py 向上查找项目根目录
                current_file = Path(__file__).resolve()
                
                # 尝试从 backend/app/main.py 向上 2 级（项目根目录）
                project_root = current_file.parents[2]  # backend/app/main.py -> 项目根目录
                key_service_path = project_root / 'backend' / 'services' / 'key_service' / 'main.py'
                
                # 如果不存在，尝试从 backend 目录的父目录（兼容 uvicorn app.main:app 方式）
                if not key_service_path.exists():
                    backend_dir = current_file.parents[1]  # backend/app/main.py -> backend/app -> backend
                    project_root = backend_dir.parent  # backend -> 项目根目录
                    key_service_path = project_root / 'backend' / 'services' / 'key_service' / 'main.py'
                
                if not key_service_path.exists():
                    logger.warning(f"{LOG_PREFIXES['warning']} Key Service 模块未找到: {key_service_path}，将使用文件存储")
                    key_service_process = None
                else:
                    key_service_module = 'backend.services.key_service.main'
                    
                    # 设置环境变量，确保 Python 能找到 backend 模块
                    env = os.environ.copy()
                    # 将项目根目录添加到 PYTHONPATH
                    pythonpath = env.get('PYTHONPATH', '')
                    if pythonpath:
                        pythonpath = f"{project_root}{os.pathsep}{pythonpath}"
                    else:
                        pythonpath = str(project_root)
                    env['PYTHONPATH'] = pythonpath
                    
                    logger.debug(f"[KeyService] 项目根目录: {project_root}")
                    logger.debug(f"[KeyService] PYTHONPATH: {pythonpath}")
                    logger.debug(f"[KeyService] Key Service 路径: {key_service_path}")
                    
                    # 启动 Key Service 子进程
                    key_service_process = subprocess.Popen(
                        [python_exe, '-m', key_service_module],
                        cwd=str(project_root),
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == 'Windows' else 0
                    )
                
                # 等待 Key Service 启动（最多等待 3 秒）
                if key_service_process:
                    import time
                    max_wait = 3.0
                    wait_interval = 0.1
                    waited = 0.0
                    
                    while waited < max_wait:
                        if key_service_process.poll() is not None:
                            # 进程已退出，启动失败
                            stderr_output = key_service_process.stderr.read().decode('utf-8', errors='ignore') if key_service_process.stderr else ''
                            logger.warning(
                                f"{LOG_PREFIXES['warning']} Key Service 启动失败，将使用文件存储: {stderr_output[:200]}"
                            )
                            key_service_process = None
                            break
                    
                        # 检查 Key Service 是否已就绪（检查 Socket 文件或端口文件）
                        from .core.key_service_client import KEY_SERVICE_CLIENT_SOCKET
                        import platform as plat
                        
                        is_ready = False
                        if plat.system() == 'Windows':
                            port_file = KEY_SERVICE_CLIENT_SOCKET.parent / "gemini_key_service_client.port"
                            if port_file.exists():
                                is_ready = True
                        else:
                            if KEY_SERVICE_CLIENT_SOCKET.exists():
                                is_ready = True
                        
                        if is_ready:
                            logger.info(f"{LOG_PREFIXES['success']} Key Service 已自动启动（进程 ID: {key_service_process.pid}）")
                            break
                        
                        time.sleep(wait_interval)
                        waited += wait_interval
                    
                    if waited >= max_wait and key_service_process and key_service_process.poll() is None:
                        # 超时但进程仍在运行，假设启动成功（可能启动较慢）
                        logger.info(f"{LOG_PREFIXES['info']} Key Service 正在启动（进程 ID: {key_service_process.pid}），稍后会自动连接...")
                
            except Exception as e:
                logger.warning(f"{LOG_PREFIXES['warning']} 无法自动启动 Key Service，将使用文件存储: {e}")
                if key_service_process:
                    try:
                        key_service_process.terminate()
                        key_service_process.wait(timeout=2)
                    except:
                        pass
                key_service_process = None
        
        # 初始化 Key Service Client（尝试连接 Key Service 或回退到文件存储）
        try:
            from .core.key_service_client import initialize_key_service_client
            client_token = os.getenv('KEY_SERVICE_CLIENT_TOKEN', 'default_token_change_me')
            initialize_key_service_client(client_token)
            # 日志已在 initialize_key_service_client 中输出
        except Exception as e:
            logger.warning(f"{LOG_PREFIXES['warning']} Key Service Client initialization failed (will use file storage): {e}")
            
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Key Service 自动启动失败，将使用文件存储: {e}")
        if key_service_process:
            try:
                key_service_process.terminate()
            except:
                pass
        key_service_process = None
    
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
            logger.warning(
                f"{LOG_PREFIXES['warning']} Some providers have invalid configurations: "
                f"{', '.join(invalid_providers)}"
            )
        else:
            logger.info(f"{LOG_PREFIXES['success']} All provider configurations validated successfully")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Failed to validate provider configurations: {e}")
        logger.error("WARNING: Application will continue but some providers may not work correctly!")
    
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

    # 将 key_service_process 保存到 app.state，以便在 shutdown 时访问
    app.state.key_service_process = key_service_process

    yield

    # Shutdown
    # 从 app.state 获取 key_service_process
    key_service_process = getattr(app.state, 'key_service_process', None)
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

    # ✅ 停止 Key Service 子进程（如果已启动）
    if key_service_process:
        logger.info(f"{LOG_PREFIXES['info']} 正在停止 Key Service（进程 ID: {key_service_process.pid}）...")
        try:
            if platform.system() == 'Windows':
                # Windows 使用 terminate
                key_service_process.terminate()
            else:
                # Unix/Linux 发送 SIGTERM
                key_service_process.send_signal(signal.SIGTERM)
            
            # 等待进程结束（最多等待 5 秒）
            try:
                key_service_process.wait(timeout=5)
                logger.info(f"{LOG_PREFIXES['success']} Key Service 已停止")
            except subprocess.TimeoutExpired:
                # 超时，强制终止
                logger.warning(f"{LOG_PREFIXES['warning']} Key Service 未在 5 秒内停止，强制终止...")
                key_service_process.kill()
                key_service_process.wait()
                logger.info(f"{LOG_PREFIXES['success']} Key Service 已强制停止")
        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} 停止 Key Service 时出错: {e}")

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
logger.info("=" * 60)
logger.info(">>> Gemini Chat Backend Starting...")
logger.info("=" * 60)
logger.info(f"Selenium Available: {'[YES]' if SELENIUM_AVAILABLE else '[NO]'}")
logger.info(f"PDF Extraction Available: {'[YES]' if PDF_EXTRACTION_AVAILABLE else '[NO]'}")
logger.info(f"Embedding Service Available: {'[YES]' if EMBEDDING_AVAILABLE else '[NO]'}")
logger.info(f"Upload Worker Pool Available: {'[YES]' if WORKER_POOL_AVAILABLE else '[NO]'}")
logger.info(f"Router Registry Available: {'[YES]' if ROUTER_REGISTRY_AVAILABLE else '[NO]'}")
logger.info("=" * 60)

# Configure CORS
# 注意：使用 httpOnly Cookie 时，allow_origins 不能为 "*"
import os
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:21573,http://127.0.0.1:21573").split(",")
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
    uvicorn.run(app, host="0.0.0.0", port=21574, reload=True)
