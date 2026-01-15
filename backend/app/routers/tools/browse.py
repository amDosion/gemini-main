"""Browse routes - Web browsing and content extraction"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Callable
import asyncio
import uuid
import json

from ...core.dependencies import require_current_user

router = APIRouter(prefix="/api", tags=["browse"])

# ==================== Browser Session Management ====================

@router.post("/browser/stop")
async def stop_browser_session(
    user_id: str = Depends(require_current_user)
):
    """
    停止用户的浏览器会话。
    当用户点击停止按钮时调用，以关闭该用户的 Selenium 浏览器实例。
    """
    try:

        from ...services.gemini.browser import close_driver
        close_driver(user_id=user_id)

        if _logger:
            _logger.info(f"[Browse] Browser session stopped for user: {user_id}")
        return {"success": True, "message": f"Browser session closed for user {user_id}"}
    except Exception as e:
        if _logger:
            _logger.error(f"[Browse] Failed to stop browser session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser/sessions")
async def get_browser_sessions(
    user_id: str = Depends(require_current_user)
):
    """
    获取活跃的浏览器会话信息（仅供管理员调试使用）。
    """
    try:

        from ...services.gemini.browser import get_active_sessions
        sessions = get_active_sessions()

        if _logger:
            _logger.info(f"[Browse] Browser sessions queried by user: {user_id}")
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        if _logger:
            _logger.error(f"[Browse] Failed to get browser sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Service references (set in main.py)
_selenium_browse = None
_read_webpage = None
_web_search = None
_SELENIUM_AVAILABLE = False
_progress_tracker = None
_logger = None
_LOG_PREFIXES = None


def set_browser_service(
    browse_func: Callable,
    read_func: Callable,
    search_func: Callable,
    available: bool,
    progress_tracker=None,
    logger=None,
    log_prefixes=None
):
    """
    设置浏览器服务引用
    
    Args:
        browse_func: selenium_browse 函数
        read_func: read_webpage 函数
        search_func: web_search 函数
        available: Selenium 是否可用
        progress_tracker: 进度追踪器实例
        logger: 日志记录器实例
        log_prefixes: 日志前缀字典
    """
    global _selenium_browse, _read_webpage, _web_search, _SELENIUM_AVAILABLE
    global _progress_tracker, _logger, _LOG_PREFIXES
    _selenium_browse = browse_func
    _read_webpage = read_func
    _web_search = search_func
    _SELENIUM_AVAILABLE = available
    _progress_tracker = progress_tracker
    _logger = logger
    _LOG_PREFIXES = log_prefixes


# ============================================================================
# Request/Response Models
# ============================================================================

class BrowseRequest(BaseModel):
    """Request model for browse endpoint"""
    url: str
    operation_id: Optional[str] = None

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
    if not _SELENIUM_AVAILABLE:
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

@router.get("/browse/progress/{operation_id}")
async def browse_progress_stream(operation_id: str, request: Request):
    """
    Server-Sent Events endpoint for real-time browse progress updates.
    
    Args:
        operation_id: Unique identifier for the browse operation
        request: FastAPI request object (for disconnect detection)
    
    Returns:
        StreamingResponse with SSE events
    """
    if not _progress_tracker:
        raise HTTPException(status_code=503, detail="Progress tracking not available")
    
    async def event_generator():
        # Subscribe to progress updates
        queue = await _progress_tracker.subscribe(operation_id)
        
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
            await _progress_tracker.unsubscribe(operation_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/browse", response_model=BrowseResponse)
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
    
    if _logger and _LOG_PREFIXES:
        _logger.info(f"{_LOG_PREFIXES['request']} Received browse request for URL: {url} (operation_id: {operation_id})")

    try:
        # Send initial progress
        if _progress_tracker:
            await _progress_tracker.send_progress(
                operation_id,
                step="Starting",
                status="in_progress",
                details=f"Preparing to browse {url}",
                progress=0
            )
        
        # Method 1: Try using Selenium first (gets dynamic content + screenshot)
        if _SELENIUM_AVAILABLE and _selenium_browse:
            try:
                if _logger and _LOG_PREFIXES:
                    _logger.info(f"{_LOG_PREFIXES['selenium']} Attempting to browse with Selenium: {url}")
                
                if _progress_tracker:
                    await _progress_tracker.send_progress(
                        operation_id,
                        step="Initializing Browser",
                        status="in_progress",
                        details="Starting Selenium WebDriver",
                        progress=10
                    )

                # Get page content using Selenium
                if _progress_tracker:
                    await _progress_tracker.send_progress(
                        operation_id,
                        step="Loading Page",
                        status="in_progress",
                        details=f"Navigating to {url}",
                        progress=30
                    )
                
                content = _selenium_browse(url, steps=[
                    {"action": "wait", "seconds": 2}
                ])

                # Extract title (we need to get it from the original HTML)
                if _progress_tracker:
                    await _progress_tracker.send_progress(
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
                if _logger and _LOG_PREFIXES:
                    _logger.info(f"{_LOG_PREFIXES['screenshot']} Taking screenshot...")
                
                if _progress_tracker:
                    await _progress_tracker.send_progress(
                        operation_id,
                        step="Taking Screenshot",
                        status="in_progress",
                        details="Capturing page screenshot",
                        progress=70
                    )
                
                screenshot_base64 = take_screenshot_selenium(url)

                if _logger and _LOG_PREFIXES:
                    _logger.info(f"{_LOG_PREFIXES['success']} Successfully browsed with Selenium: {url}")
                
                if _progress_tracker:
                    await _progress_tracker.send_progress(
                        operation_id,
                        step="Finalizing",
                        status="in_progress",
                        details="Preparing response",
                        progress=90
                    )
                    await _progress_tracker.send_complete(operation_id)
                
                return BrowseResponse(
                    markdown=markdown_content,
                    title=title,
                    screenshot=screenshot_base64
                )

            except Exception as selenium_error:
                if _logger and _LOG_PREFIXES:
                    _logger.warning(f"{_LOG_PREFIXES['warning']} Selenium error: {selenium_error}, falling back to requests")
                
                if _progress_tracker:
                    await _progress_tracker.send_progress(
                        operation_id,
                        step="Fallback to Simple Mode",
                        status="in_progress",
                        details="Selenium failed, using simple HTTP request",
                        progress=20
                    )

        # Method 2: Fallback to simple requests + BeautifulSoup
        if _logger and _LOG_PREFIXES:
            _logger.info(f"{_LOG_PREFIXES['webpage']} Browsing with requests (no Selenium): {url}")
        
        if _progress_tracker:
            await _progress_tracker.send_progress(
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
        if _progress_tracker:
            await _progress_tracker.send_progress(
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
            if _logger:
                _logger.warning(f"Content truncated from {len(markdown_content)} to 50000 characters")
            markdown_content = markdown_content[:50000] + "\n\n[Content truncated...]"

        if _logger and _LOG_PREFIXES:
            _logger.info(f"{_LOG_PREFIXES['success']} Successfully browsed with requests: {url}")
        
        if _progress_tracker:
            await _progress_tracker.send_progress(
                operation_id,
                step="Finalizing",
                status="in_progress",
                details="Preparing response",
                progress=90
            )
            await _progress_tracker.send_complete(operation_id)
        
        return BrowseResponse(
            markdown=markdown_content,
            title=title,
            screenshot=None  # No screenshot without Selenium
        )

    except Exception as e:
        import requests
        
        if isinstance(e, requests.exceptions.Timeout):
            if _logger and _LOG_PREFIXES:
                _logger.error(f"{_LOG_PREFIXES['error']} Timeout while accessing {url}")
            if _progress_tracker:
                await _progress_tracker.send_error(operation_id, f"Timeout while accessing {url}")
            raise HTTPException(
                status_code=504,
                detail=f"Timeout while accessing {url}"
            )
        elif isinstance(e, requests.exceptions.RequestException):
            if _logger and _LOG_PREFIXES:
                _logger.error(f"{_LOG_PREFIXES['error']} Request error accessing {url}: {str(e)}")
            if _progress_tracker:
                await _progress_tracker.send_error(operation_id, f"Request error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error accessing {url}: {str(e)}"
            )
        else:
            if _logger and _LOG_PREFIXES:
                _logger.exception(f"{_LOG_PREFIXES['error']} Internal server error while browsing {url}")
            if _progress_tracker:
                await _progress_tracker.send_error(operation_id, f"Internal error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )


@router.post("/search")
async def web_search_endpoint(query: str):
    """
    Web search endpoint
    
    Args:
        query: Search query string
        
    Returns:
        Search results
        
    Raises:
        HTTPException: If search service is not available or fails
    """
    if not _web_search:
        raise HTTPException(
            status_code=503,
            detail="Web search functionality is not available. Please install required dependencies."
        )
    
    try:
        result = _web_search(query)
        return {"results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
