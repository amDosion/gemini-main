"""
FastAPI Backend for Gemini Chat Application

This backend provides API endpoints for browser automation, web scraping,
and PDF structured data extraction to be used with the Gemini AI frontend.
"""

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

# Import logger and progress tracker
try:
    from .core.logger import setup_logger, LOG_PREFIXES
    from .services.progress_tracker import progress_tracker
    logger = setup_logger("main")
except ImportError:
    from core.logger import setup_logger, LOG_PREFIXES
    from services.progress_tracker import progress_tracker
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
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Database initialization failed: {e}")
except Exception as e:
    logger.warning(f"{LOG_PREFIXES['warning']} Database initialization failed: {e}")

# Import API routers
try:
    from .routers import health, storage, browse, pdf, embedding, dashscope_proxy
    from .routers.profiles import router as profiles_router
    from .routers.sessions import router as sessions_router
    from .routers.personas import router as personas_router
    from .routers.image_expand import router as image_expand_router
    API_ROUTES_AVAILABLE = True
except ImportError as e:
    try:
        # Fallback: try importing from app.routers
        from app.routers import health, storage, browse, pdf, embedding, dashscope_proxy
        from app.routers.profiles import router as profiles_router
        from app.routers.sessions import router as sessions_router
        from app.routers.personas import router as personas_router
        from app.routers.image_expand import router as image_expand_router
        API_ROUTES_AVAILABLE = True
    except ImportError as e2:
        logger.warning(f"{LOG_PREFIXES['warning']} Could not import API routes module: {e2}")
        logger.info(f"{LOG_PREFIXES['info']} Original error was: {e}")
        API_ROUTES_AVAILABLE = False

# Create FastAPI app
app = FastAPI(
    title="Gemini Chat Backend",
    description="Backend API for browser automation and web scraping",
    version="1.0.0"
)

# ============================================================================
# Celery Worker 自动启动/关闭管理
# ============================================================================

# 全局变量：存储 Celery Worker 进程
celery_worker_process = None

@app.on_event("startup")
async def startup_celery_worker():
    """
    FastAPI 启动时自动启动 Celery Worker
    """
    global celery_worker_process

    try:
        logger.info("=" * 60)
        logger.info(f"{LOG_PREFIXES['info']} 正在启动 Celery Worker...")
        logger.info("=" * 60)

        # 检测操作系统并选择合适的 pool 模式
        is_windows = platform.system() == 'Windows'
        pool_mode = 'solo' if is_windows else 'prefork'

        logger.info(f"{LOG_PREFIXES['info']} 检测到操作系统: {platform.system()}")
        logger.info(f"{LOG_PREFIXES['info']} 使用 pool 模式: {pool_mode}")

        # 构建 Celery 启动命令
        celery_cmd = [
            sys.executable,  # 使用当前 Python 解释器
            "-m", "celery",
            "-A", "app.core.celery_app",
            "worker",
            "--loglevel=info",
            f"--pool={pool_mode}",
            "--queues=upload_queue"  # 明确指定队列
        ]

        if not is_windows:
            celery_cmd.append("--concurrency=3")

        # 设置正确的工作目录和环境变量
        import os
        current_dir = os.getcwd()
        backend_dir = os.path.join(current_dir, 'backend') if 'backend' not in current_dir else current_dir
        
        # 设置 PYTHONPATH 确保模块可以被找到
        env = os.environ.copy()
        env['PYTHONPATH'] = backend_dir
        
        logger.info(f"{LOG_PREFIXES['info']} Celery 工作目录: {backend_dir}")
        logger.info(f"{LOG_PREFIXES['info']} Celery 命令: {' '.join(celery_cmd)}")

        # 启动 Celery Worker 进程
        celery_worker_process = subprocess.Popen(
            celery_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # 行缓冲
            cwd=backend_dir,  # 设置正确的工作目录
            env=env  # 设置环境变量
        )

        # 等待一小段时间检查进程是否正常启动
        import time
        time.sleep(2)
        
        if celery_worker_process.poll() is None:
            logger.info(f"{LOG_PREFIXES['success']} ✅ Celery Worker 已启动 (PID: {celery_worker_process.pid})")
            logger.info(f"{LOG_PREFIXES['info']} 并发数: 3, 队列: upload_queue")
            
            # 读取一些初始输出来检查启动状态
            try:
                # 非阻塞读取输出
                import select
                if hasattr(select, 'select'):  # Unix系统
                    ready, _, _ = select.select([celery_worker_process.stdout], [], [], 1)
                    if ready:
                        output = celery_worker_process.stdout.readline()
                        if output:
                            logger.info(f"{LOG_PREFIXES['info']} Celery Worker 输出: {output.strip()}")
                else:  # Windows系统
                    # Windows下简单检查进程状态
                    pass
            except Exception as e:
                logger.warning(f"{LOG_PREFIXES['warning']} 无法读取 Celery Worker 输出: {e}")
                
        else:
            # 进程已经退出，读取错误信息
            stdout, stderr = celery_worker_process.communicate()
            logger.error(f"{LOG_PREFIXES['error']} ❌ Celery Worker 启动失败")
            logger.error(f"{LOG_PREFIXES['error']} 标准输出: {stdout}")
            logger.error(f"{LOG_PREFIXES['error']} 错误输出: {stderr}")
            celery_worker_process = None

        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} ❌ Celery Worker 启动失败: {e}")
        logger.warning(f"{LOG_PREFIXES['warning']} 文件上传任务将无法处理，请手动启动 Celery Worker")
        import traceback
        logger.error(f"{LOG_PREFIXES['error']} 详细错误: {traceback.format_exc()}")


@app.on_event("shutdown")
async def shutdown_celery_worker():
    """
    FastAPI 关闭时优雅停止 Celery Worker
    """
    global celery_worker_process

    if celery_worker_process:
        try:
            logger.info("=" * 60)
            logger.info(f"{LOG_PREFIXES['info']} 正在停止 Celery Worker...")
            logger.info("=" * 60)

            # 发送终止信号
            celery_worker_process.terminate()

            # 等待进程结束（最多10秒）
            try:
                celery_worker_process.wait(timeout=10)
                logger.info(f"{LOG_PREFIXES['success']} ✅ Celery Worker 已优雅停止")
            except subprocess.TimeoutExpired:
                # 如果超时，强制杀死进程
                logger.warning(f"{LOG_PREFIXES['warning']} Celery Worker 未能及时停止，强制终止...")
                celery_worker_process.kill()
                celery_worker_process.wait()
                logger.info(f"{LOG_PREFIXES['info']} Celery Worker 已强制终止")

            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} ❌ 停止 Celery Worker 时出错: {e}")


# 注册退出处理器（作为备份机制）
def cleanup_celery():
    """确保程序异常退出时也能停止 Celery Worker"""
    global celery_worker_process
    if celery_worker_process and celery_worker_process.poll() is None:
        logger.info(f"{LOG_PREFIXES['info']} [退出处理器] 停止 Celery Worker...")
        celery_worker_process.terminate()
        try:
            celery_worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            celery_worker_process.kill()

atexit.register(cleanup_celery)

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
    logger.info(f"{LOG_PREFIXES['info']} API routes registered (profiles, sessions, personas, storage, image_expand)")
else:
    logger.warning(f"{LOG_PREFIXES['warning']} API routes not available")

# Log module availability on startup
logger.info("=" * 60)
logger.info(">>> Gemini Chat Backend Starting...")
logger.info("=" * 60)
logger.info(f"Selenium Available: {'[YES]' if SELENIUM_AVAILABLE else '[NO]'}")
logger.info(f"PDF Extraction Available: {'[YES]' if PDF_EXTRACTION_AVAILABLE else '[NO]'}")
logger.info(f"Embedding Service Available: {'[YES]' if EMBEDDING_AVAILABLE else '[NO]'}")
logger.info("=" * 60)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class BrowseRequest(BaseModel):
    """Request model for browse endpoint"""
    url: str
    operation_id: Optional[str] = None  # Optional operation ID for progress tracking

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "operation_id": "optional-unique-id"
            }
        }


class BrowseResponse(BaseModel):
    """Response model for browse endpoint"""
    markdown: str
    title: str
    screenshot: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "markdown": "Page content in markdown format...",
                "title": "Example Page",
                "screenshot": "base64_encoded_image_data..."
            }
        }


# ============================================================================
# Helper Functions
# ============================================================================

def extract_title_from_html(html_content: str) -> str:
    """
    Extract title from HTML content using simple parsing.
    Falls back to a default title if not found.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()
    except Exception as e:
        print(f"Error extracting title: {e}")

    return "Web Page"


def html_to_markdown(html_content: str) -> str:
    """
    Convert HTML content to Markdown format.
    """
    try:
        from markdownify import markdownify as md
        markdown_text = md(html_content, heading_style="ATX")
        return markdown_text
    except ImportError:
        # Fallback: Just extract text without markdown formatting
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text()
    except Exception as e:
        print(f"Error converting to markdown: {e}")
        return html_content


def take_screenshot_selenium(url: str) -> Optional[str]:
    """
    Take a screenshot of a webpage using Selenium and return as base64.
    """
    if not SELENIUM_AVAILABLE:
        return None

    try:
        import base64
        from io import BytesIO
        from PIL import Image
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # Create driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            # Navigate to URL
            driver.get(url)

            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Take screenshot
            screenshot_png = driver.get_screenshot_as_png()

            # Convert to JPEG and resize for efficiency
            img = Image.open(BytesIO(screenshot_png))

            # Resize to max 1280 width while maintaining aspect ratio
            max_width = 1280
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to JPEG
            buffer = BytesIO()
            img.convert('RGB').save(buffer, format='JPEG', quality=85)

            # Encode to base64
            screenshot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return screenshot_base64

        finally:
            driver.quit()

    except Exception as e:
        print(f"Error taking screenshot: {e}")
        return None


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Gemini Chat Backend API",
        "selenium_available": SELENIUM_AVAILABLE,
        "pdf_extraction_available": PDF_EXTRACTION_AVAILABLE,
        "embedding_available": EMBEDDING_AVAILABLE
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,
        "embedding": EMBEDDING_AVAILABLE,
        "version": "1.0.0"
    }


@app.get("/api/browse/progress/{operation_id}")
async def browse_progress_stream(operation_id: str, request: Request):
    """
    Server-Sent Events endpoint for real-time browse progress updates.
    
    Args:
        operation_id: Unique identifier for the browse operation
        request: FastAPI request object (for disconnect detection)
    
    Returns:
        StreamingResponse with SSE events
    """
    async def event_generator():
        # Subscribe to progress updates
        queue = await progress_tracker.subscribe(operation_id)
        
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for next progress update (with timeout)
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    yield f"data: {json.dumps(message)}\n\n"
                    
                    # If operation completed or errored, stop streaming
                    if message.get("status") in ["completed", "error"]:
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
                    
        finally:
            # Unsubscribe when done
            await progress_tracker.unsubscribe(operation_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/api/browse", response_model=BrowseResponse)
async def browse_webpage(request: BrowseRequest):
    """
    Browse a webpage and return its content as markdown along with a screenshot.

    This endpoint:
    1. Fetches the webpage content
    2. Extracts the title
    3. Converts HTML to Markdown
    4. Takes a screenshot (if Selenium is available)

    Args:
        request: BrowseRequest containing the URL to browse

    Returns:
        BrowseResponse with markdown content, title, and optional screenshot

    Raises:
        HTTPException: If the URL cannot be accessed or processed
    """
    url = request.url
    operation_id = request.operation_id or str(uuid.uuid4())
    logger.info(f"{LOG_PREFIXES['request']} Received browse request for URL: {url} (operation_id: {operation_id})")

    try:
        # Send initial progress
        await progress_tracker.send_progress(
            operation_id,
            step="Starting",
            status="in_progress",
            details=f"Preparing to browse {url}",
            progress=0
        )
        
        # Method 1: Try using Selenium first (gets dynamic content + screenshot)
        if SELENIUM_AVAILABLE:
            try:
                logger.info(f"{LOG_PREFIXES['selenium']} Attempting to browse with Selenium: {url}")
                
                await progress_tracker.send_progress(
                    operation_id,
                    step="Initializing Browser",
                    status="in_progress",
                    details="Starting Selenium WebDriver",
                    progress=10
                )

                # Get page content using Selenium
                await progress_tracker.send_progress(
                    operation_id,
                    step="Loading Page",
                    status="in_progress",
                    details=f"Navigating to {url}",
                    progress=30
                )
                
                content = selenium_browse(url, steps=[
                    {"action": "wait", "seconds": 2}
                ])

                # Extract title (we need to get it from the original HTML)
                await progress_tracker.send_progress(
                    operation_id,
                    step="Extracting Content",
                    status="in_progress",
                    details="Parsing page content",
                    progress=50
                )
                
                import requests
                from bs4 import BeautifulSoup

                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                title = extract_title_from_html(response.text)

                # Convert content to markdown
                markdown_content = content  # selenium_browse already returns text

                # Take screenshot
                logger.info(f"{LOG_PREFIXES['screenshot']} Taking screenshot...")
                await progress_tracker.send_progress(
                    operation_id,
                    step="Taking Screenshot",
                    status="in_progress",
                    details="Capturing page screenshot",
                    progress=70
                )
                
                screenshot_base64 = take_screenshot_selenium(url)

                logger.info(f"{LOG_PREFIXES['success']} Successfully browsed with Selenium: {url}")
                
                await progress_tracker.send_progress(
                    operation_id,
                    step="Finalizing",
                    status="in_progress",
                    details="Preparing response",
                    progress=90
                )
                
                await progress_tracker.send_complete(operation_id)
                
                return BrowseResponse(
                    markdown=markdown_content,
                    title=title,
                    screenshot=screenshot_base64
                )

            except Exception as selenium_error:
                logger.warning(f"{LOG_PREFIXES['warning']} Selenium error: {selenium_error}, falling back to requests")
                await progress_tracker.send_progress(
                    operation_id,
                    step="Fallback to Simple Mode",
                    status="in_progress",
                    details="Selenium failed, using simple HTTP request",
                    progress=20
                )

        # Method 2: Fallback to simple requests + BeautifulSoup
        logger.info(f"{LOG_PREFIXES['webpage']} Browsing with requests (no Selenium): {url}")
        
        await progress_tracker.send_progress(
            operation_id,
            step="Fetching Page",
            status="in_progress",
            details=f"Downloading {url}",
            progress=40
        )

        import requests
        from bs4 import BeautifulSoup

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()

        # Extract title
        await progress_tracker.send_progress(
            operation_id,
            step="Processing Content",
            status="in_progress",
            details="Extracting and converting content",
            progress=60
        )
        
        title = extract_title_from_html(response.text)

        # Convert to markdown
        markdown_content = html_to_markdown(response.text)

        # Truncate if too long (max 50000 chars)
        if len(markdown_content) > 50000:
            logger.warning(f"Content truncated from {len(markdown_content)} to 50000 characters")
            markdown_content = markdown_content[:50000] + "\n\n[Content truncated...]"

        logger.info(f"{LOG_PREFIXES['success']} Successfully browsed with requests: {url}")
        
        await progress_tracker.send_progress(
            operation_id,
            step="Finalizing",
            status="in_progress",
            details="Preparing response",
            progress=90
        )
        
        await progress_tracker.send_complete(operation_id)
        
        return BrowseResponse(
            markdown=markdown_content,
            title=title,
            screenshot=None  # No screenshot without Selenium
        )

    except requests.exceptions.Timeout:
        logger.error(f"{LOG_PREFIXES['error']} Timeout while accessing {url}")
        await progress_tracker.send_error(operation_id, f"Timeout while accessing {url}")
        raise HTTPException(
            status_code=504,
            detail=f"Timeout while accessing {url}"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"{LOG_PREFIXES['error']} Request error accessing {url}: {str(e)}")
        await progress_tracker.send_error(operation_id, f"Request error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Error accessing {url}: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"{LOG_PREFIXES['error']} Internal server error while browsing {url}")
        await progress_tracker.send_error(operation_id, f"Internal error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Additional Endpoints (for future expansion)
# ============================================================================

@app.post("/api/search")
async def web_search_endpoint(query: str):
    """
    Web search endpoint (placeholder for future implementation)
    """
    try:
        from .services.browser import web_search
        result = web_search(query)
        return {"results": result}
    except ImportError:
        try:
            from services.browser import web_search
            result = web_search(query)
            return {"results": result}
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Web search functionality is not available. Please install required dependencies."
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PDF Extraction Endpoints
# ============================================================================

@app.get("/api/pdf/templates")
async def get_pdf_templates():
    """
    Get available PDF extraction templates.

    Returns:
        List of available templates with their metadata
    """
    if not PDF_EXTRACTION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF extraction functionality is not available. Please install required dependencies."
        )

    try:
        templates = get_available_templates()
        return {
            "success": True,
            "templates": templates
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching templates: {str(e)}"
        )


@app.post("/api/pdf/extract")
async def extract_pdf_data(
    file: UploadFile = File(...),
    template_type: str = Form(...),
    api_key: str = Form(...),
    additional_instructions: str = Form("")
):
    """
    Extract structured data from a PDF document.

    Args:
        file: PDF file to process
        template_type: Type of template to use ('invoice', 'form', 'receipt', 'contract')
        api_key: Google AI API key for Gemini
        additional_instructions: Optional additional extraction instructions

    Returns:
        Extracted structured data

    Raises:
        HTTPException: If PDF extraction fails or is not available
    """
    if not PDF_EXTRACTION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF extraction functionality is not available. Please install required dependencies."
        )

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    try:
        # Read PDF file
        pdf_bytes = await file.read()

        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )

        # Extract structured data
        result = await extract_structured_data_from_pdf(
            pdf_bytes=pdf_bytes,
            template_type=template_type,
            api_key=api_key,
            additional_instructions=additional_instructions
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )


# ============================================================================
# Document Embedding / RAG Endpoints
# ============================================================================

class AddDocumentRequest(BaseModel):
    """Request model for adding a document to the vector store"""
    user_id: str
    filename: str
    content: str
    api_key: str
    chunk_size: int = 500
    chunk_overlap: int = 100


class SearchRequest(BaseModel):
    """Request model for semantic search"""
    user_id: str
    query: str
    api_key: str
    top_k: int = 3


@app.post("/api/embedding/add-document")
async def add_document(request: AddDocumentRequest):
    """
    Add a document to the user's vector store.

    The document will be chunked and embedded for later retrieval.
    """
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available"
        )

    try:
        result = await rag_service.add_document(
            user_id=request.user_id,
            filename=request.filename,
            content=request.content,
            api_key=request.api_key,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding document: {str(e)}"
        )


@app.post("/api/embedding/search")
async def search_documents(request: SearchRequest):
    """
    Search for document chunks similar to the query.

    Returns the most relevant chunks from the user's vector store.
    """
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available"
        )

    try:
        results = rag_service.search_similar_chunks(
            user_id=request.user_id,
            query=request.query,
            api_key=request.api_key,
            top_k=request.top_k
        )
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching documents: {str(e)}"
        )


@app.get("/api/embedding/documents/{user_id}")
async def get_user_documents(user_id: str):
    """
    Get all documents for a user.
    """
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available"
        )

    try:
        documents = rag_service.get_user_documents(user_id)
        stats = rag_service.get_stats(user_id)
        return {
            "success": True,
            "documents": documents,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching documents: {str(e)}"
        )


@app.delete("/api/embedding/document/{user_id}/{document_id}")
async def delete_document(user_id: str, document_id: str):
    """
    Delete a specific document from the user's vector store.
    """
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available"
        )

    try:
        success = rag_service.remove_document(user_id, document_id)
        if success:
            return {"success": True, "message": "Document deleted"}
        else:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting document: {str(e)}"
        )


@app.delete("/api/embedding/documents/{user_id}")
async def clear_user_documents(user_id: str):
    """
    Clear all documents for a user.
    """
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not available"
        )

    try:
        rag_service.clear_user_documents(user_id)
        return {"success": True, "message": "All documents cleared"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing documents: {str(e)}"
        )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
