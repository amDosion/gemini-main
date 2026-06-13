"""Browse routes - Web browsing and content extraction"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from typing import Any, Optional, Callable
import asyncio
import uuid
import json
import logging

import httpx

from ...core.dependencies import require_admin, require_current_user

logger = logging.getLogger(__name__)
from ...utils.log_sanitization import (
    redact_exact_value_in_log_text,
    summarize_text_for_log,
    summarize_url_for_log,
)
from ...utils.url_security import validate_outbound_http_url
from ...utils.sse import encode_sse_data

router = APIRouter(prefix="/api", tags=["browse"])
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"


class BrowserStopResponse(BaseModel):
    success: bool
    message: str = Field(max_length=640, pattern=NO_CONTROL_CHARS_PATTERN)


class BrowserSessionsResponse(BaseModel):
    sessions: list[dict[str, Any]] = Field(max_length=10_000)
    count: int = Field(ge=0, le=10_000)


class WebSearchResponse(BaseModel):
    results: JsonValue


# Module-level lazy httpx.AsyncClient for the browse route. Reusing a single
# client avoids tearing down TCP/TLS handshakes per request and keeps the
# event loop free of blocking ``requests`` work.
_http_client: Optional[httpx.AsyncClient] = None
_http_client_lock = asyncio.Lock()


async def _get_async_http_client() -> httpx.AsyncClient:
    """Lazy initializer for the module-level ``httpx.AsyncClient``.

    Using a lazy initializer avoids import-time side effects (which can
    interact poorly with multi-worker process pools) while still ensuring
    only a single client is created per worker.
    """
    global _http_client
    if _http_client is None:
        async with _http_client_lock:
            if _http_client is None:
                _http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    return _http_client

# ==================== Browser Session Management ====================

@router.post("/browser/stop", response_model=BrowserStopResponse)
async def stop_browser_session(
    user_id: str = Depends(require_current_user)
):
    """
    停止用户的浏览器会话。
    当用户点击停止按钮时调用，以关闭该用户的 Selenium 浏览器实例。
    """
    try:

        from ...services.gemini.common.browser import close_driver
        close_driver(user_id=user_id)

        if _logger:
            _logger.info(f"[Browse] Browser session stopped for user: {user_id}")
        return {"success": True, "message": f"Browser session closed for user {user_id}"}
    except Exception as e:
        if _logger:
            _logger.error(
                "[Browse] Failed to stop browser session: %s",
                summarize_text_for_log(e, label="error"),
            )
        raise HTTPException(status_code=500, detail="Failed to stop browser session")


@router.get("/browser/sessions", response_model=BrowserSessionsResponse)
async def get_browser_sessions(
    user_id: str = Depends(require_admin)
):
    """
    获取活跃的浏览器会话信息（仅供管理员调试使用）。
    """
    try:

        from ...services.gemini.common.browser import get_active_sessions
        sessions = get_active_sessions()

        if _logger:
            _logger.info(f"[Browse] Browser sessions queried by user: {user_id}")
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        if _logger:
            _logger.error(
                "[Browse] Failed to get browser sessions: %s",
                summarize_text_for_log(e, label="error"),
            )
        raise HTTPException(status_code=500, detail="Failed to get browser sessions")

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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com",
                "operation_id": "optional-unique-id",
            }
        }
    )


class BrowseResponse(BaseModel):
    """Response model for browse endpoint"""
    markdown: str
    title: str
    screenshot: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "markdown": "Page content in markdown format...",
                "title": "Example Page",
                "screenshot": "base64_encoded_image_data...",
            }
        }
    )


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
        logger.debug(f"Error extracting title: {e}")

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
        logger.debug(f"Error converting to markdown: {e}")
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
        logger.info(
            "Error taking screenshot: %s",
            summarize_text_for_log(e, label="error"),
        )
        return None


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/browse/progress/{operation_id}",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-sent browse progress events",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "maxLength": 1_000_000,
                    }
                }
            },
        }
    },
)
async def browse_progress_stream(operation_id: str, request: Request, user_id: str = Depends(require_current_user)):
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
                    
                    # Format as SSE. SSE is middleware-passthrough, so camelCase
                    # the frame here (snake_case operation_id -> operationId) so the
                    # frontend never converts. (Was raw json.dumps -> dropped updates.)
                    yield encode_sse_data(message, camel_case=True)
                    
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
async def browse_webpage(
    request: BrowseRequest,
    user_id: str = Depends(require_current_user)
):
    """
    Browse a webpage and return its content as markdown along with a screenshot.

    This endpoint:
    1. Fetches the webpage content
    2. Extracts the title
    3. Converts HTML to Markdown
    4. Takes a screenshot (if Selenium is available)

    Args:
        request: BrowseRequest containing the URL to browse
        user_id: User ID (自动注入，从认证 token 中提取)

    Returns:
        BrowseResponse with markdown content, title, and optional screenshot

    Raises:
        HTTPException: If the URL cannot be accessed or processed
    """
    url = request.url
    operation_id = request.operation_id or str(uuid.uuid4())

    # Validate URL to prevent SSRF
    validate_outbound_http_url(url)
    log_url = summarize_url_for_log(url)

    if _logger and _LOG_PREFIXES:
        _logger.info(f"{_LOG_PREFIXES['request']} Received browse request for URL: {log_url} (operation_id: {operation_id}, user: {user_id})")

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
                    _logger.info(f"{_LOG_PREFIXES['selenium']} Attempting to browse with Selenium: {log_url} (user: {user_id})")
                
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
                
                # ✅ 传递 user_id 以实现会话隔离
                content = await asyncio.to_thread(_selenium_browse, url, steps=[
                    {"action": "wait", "seconds": 2}
                ], user_id=user_id)

                # Extract title (we need to get it from the original HTML)
                if _progress_tracker:
                    await _progress_tracker.send_progress(
                        operation_id,
                        step="Extracting Content",
                        status="in_progress",
                        details="Parsing page content",
                        progress=50
                    )
                
                from bs4 import BeautifulSoup

                client = await _get_async_http_client()
                response = await client.get(
                    url,
                    timeout=10.0,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    },
                )
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
                    _logger.info(f"{_LOG_PREFIXES['success']} Successfully browsed with Selenium: {log_url}")
                
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
                    safe_selenium_error = redact_exact_value_in_log_text(
                        selenium_error,
                        url,
                        log_url,
                    )
                    _logger.warning(f"{_LOG_PREFIXES['warning']} Selenium error: {safe_selenium_error}, falling back to requests")
                
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
            _logger.info(f"{_LOG_PREFIXES['webpage']} Browsing with requests (no Selenium): {log_url}")
        
        if _progress_tracker:
            await _progress_tracker.send_progress(
                operation_id,
                step="Fetching Page",
                status="in_progress",
                details=f"Downloading {url}",
                progress=40
            )

        from bs4 import BeautifulSoup

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        client = await _get_async_http_client()
        response = await client.get(url, timeout=10.0, headers=headers)
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
            _logger.info(f"{_LOG_PREFIXES['success']} Successfully browsed with requests: {log_url}")
        
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
        if isinstance(e, httpx.TimeoutException):
            if _logger and _LOG_PREFIXES:
                _logger.error(f"{_LOG_PREFIXES['error']} Timeout while accessing {log_url}")
            if _progress_tracker:
                await _progress_tracker.send_error(operation_id, f"Timeout while accessing {url}")
            raise HTTPException(
                status_code=504,
                detail=f"Timeout while accessing {url}"
            )
        elif isinstance(e, (httpx.RequestError, httpx.HTTPStatusError)):
            if _logger and _LOG_PREFIXES:
                safe_error = redact_exact_value_in_log_text(e, url, log_url)
                _logger.error(f"{_LOG_PREFIXES['error']} Request error accessing {log_url}: {safe_error}")
            if _progress_tracker:
                await _progress_tracker.send_error(operation_id, f"Request error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error accessing {url}: {str(e)}"
            )
        else:
            if _logger and _LOG_PREFIXES:
                _logger.error(
                    "%s Internal server error while browsing %s: %s",
                    _LOG_PREFIXES["error"],
                    log_url,
                    summarize_text_for_log(e, label="error"),
                )
            if _progress_tracker:
                await _progress_tracker.send_error(operation_id, "Internal error while browsing")
            raise HTTPException(
                status_code=500,
                detail="Internal server error while browsing"
            )


@router.post("/search", response_model=WebSearchResponse)
async def web_search_endpoint(
    query: str = Query(..., min_length=1, max_length=4096, pattern=NO_CONTROL_CHARS_PATTERN),
    user_id: str = Depends(require_current_user),
):
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
        logger.error(
            "[Browse] Web search failed: %s",
            summarize_text_for_log(e, label="error"),
        )
        raise HTTPException(status_code=500, detail="Web search failed")
