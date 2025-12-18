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
    from .routers import health, storage, browse, pdf, embedding, dashscope_proxy
    from .routers.profiles import router as profiles_router
    from .routers.sessions import router as sessions_router
    from .routers.personas import router as personas_router
    from .routers.image_expand import router as image_expand_router
    API_ROUTES_AVAILABLE = True
    logger.info(f"{LOG_PREFIXES['info']} API routes imported via relative import")
except ImportError:
    try:
        from routers import health, storage, browse, pdf, embedding, dashscope_proxy
        from routers.profiles import router as profiles_router
        from routers.sessions import router as sessions_router
        from routers.personas import router as personas_router
        from routers.image_expand import router as image_expand_router
        API_ROUTES_AVAILABLE = True
        logger.info(f"{LOG_PREFIXES['info']} API routes imported via absolute import (routers)")
    except ImportError:
        try:
            # 从项目根目录启动时的导入路径
            from backend.app.routers import health, storage, browse, pdf, embedding, dashscope_proxy
            from backend.app.routers.profiles import router as profiles_router
            from backend.app.routers.sessions import router as sessions_router
            from backend.app.routers.personas import router as personas_router
            from backend.app.routers.image_expand import router as image_expand_router
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
logger.info(f"Upload Worker Pool Available: {'[YES]' if WORKER_POOL_AVAILABLE else '[NO]'}")
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
        "embedding_available": EMBEDDING_AVAILABLE,
        "upload_worker_pool_available": WORKER_POOL_AVAILABLE
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,
        "embedding": EMBEDDING_AVAILABLE,
        "upload_worker_pool": WORKER_POOL_AVAILABLE,
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
            try:
                from backend.app.services.browser import web_search
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
