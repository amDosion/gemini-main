"""
Browser Tools for Gemini AI Integration

This module provides browser automation and web interaction tools that can be used
with Google's Gemini AI model. It includes functions for:
- Web searching
- Reading webpage content
- Interactive browser automation using Selenium

Based on Google Gemini Cookbook: Browser_as_a_tool.ipynb
"""

import os
import time
import json
import base64
import requests
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

# Markdown conversion for cleaner output
try:
    import markdownify
    MARKDOWNIFY_AVAILABLE = True
except ImportError:
    MARKDOWNIFY_AVAILABLE = False
    print("Warning: markdownify not available. Install with: pip install markdownify")

# Import logger from core module
try:
    from ...core.logger import setup_logger, LOG_PREFIXES
    logger = setup_logger("browser")
except ImportError:
    # Fallback for standalone execution
    import logging
    logger = logging.getLogger("browser")
    LOG_PREFIXES = {
        'search': '[SEARCH]', 'webpage': '[PAGE]', 'selenium': '[BROWSER]',
        'screenshot': '[SCREENSHOT]', 'success': '[OK]', 'error': '[ERROR]',
        'warning': '[WARN]', 'info': '[INFO]', 'startup': '[START]',
        'request': '[REQUEST]', 'action': '[ACTION]', 'navigate': '[NAV]',
    }

# Optional Selenium imports - only needed if using selenium_browse
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: Selenium not available. Install with: pip install selenium webdriver-manager")


# ============================================================================
# Web Search Tool
# ============================================================================

def web_search(query: str) -> str:
    """
    Perform a web search and return formatted JSON string results.

    Args:
        query: The search query string

    Returns:
        A JSON string containing search results (title/url/snippet)
    """
    logger.info(f"{LOG_PREFIXES['search']} Executing web_search for: '{query}'")
    clean_query = (query or "").strip()
    if not clean_query:
        return json.dumps([], ensure_ascii=False, indent=2)

    def _normalize_result_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            uddg = parse_qs(parsed.query).get("uddg")
            if uddg:
                return unquote(uddg[0])
        return url

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": clean_query, "kl": "us-en"},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        entries: List[Dict[str, str]] = []
        seen_urls = set()
        for link in soup.select("a.result__a, a.result-link"):
            title = link.get_text(" ", strip=True)
            raw_url = (link.get("href") or "").strip()
            normalized_url = _normalize_result_url(raw_url).strip()
            if not title or not normalized_url:
                continue
            if normalized_url in seen_urls:
                continue

            container = link.find_parent(class_="result")
            snippet_el = container.select_one(".result__snippet") if container else None
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            entries.append(
                {
                    "title": title,
                    "url": normalized_url,
                    "snippet": snippet,
                }
            )
            seen_urls.add(normalized_url)
            if len(entries) >= 8:
                break

        if not entries:
            logger.warning(
                "%s No results parsed for query: %s",
                LOG_PREFIXES["warning"],
                clean_query,
            )
        return json.dumps(entries, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("%s web_search failed: %s", LOG_PREFIXES["error"], e, exc_info=True)
        return json.dumps(
            [{
                "title": f"Search failed for query: {clean_query}",
                "url": "",
                "snippet": str(e),
            }],
            ensure_ascii=False,
            indent=2,
        )


# ============================================================================
# Webpage Reading Tool
# ============================================================================

def read_webpage(url: str, max_length: int = 50000) -> str:
    """
    Reads the content of a given URL and returns its content as Markdown.

    This function fetches the HTML content, converts it to Markdown format
    for better readability by the AI model.

    Args:
        url: The URL of the webpage to read
        max_length: Maximum length of text to return (default: 50000 characters)

    Returns:
        The extracted content in Markdown format, or an error message
    """
    logger.info(f"{LOG_PREFIXES['webpage']} Executing read_webpage for: '{url}'")

    try:
        # Set a user agent to avoid being blocked by some websites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Convert HTML to Markdown if markdownify is available
        if MARKDOWNIFY_AVAILABLE:
            content = markdownify.markdownify(response.text, heading_style="ATX")
        else:
            # Fallback to plain text extraction
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove script and style elements
            for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
                script_or_style.extract()
            # Get text, strip whitespace, and format
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = '\n'.join(chunk for chunk in chunks if chunk)

        # Truncate if too long
        if len(content) > max_length:
            logger.warning(f"Content truncated from {len(content)} to {max_length} characters")
            content = content[:max_length] + f"\n\n[Content truncated at {max_length} characters]"

        logger.info(f"{LOG_PREFIXES['success']} Successfully read webpage: {url} ({len(content)} characters)")
        return content

    except requests.exceptions.Timeout:
        error_msg = f"Error: Request timeout while reading webpage {url}"
        logger.error(error_msg)
        return error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Error reading webpage {url}: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred while reading {url}: {str(e)}"
        logger.exception(error_msg)
        return error_msg


# ============================================================================
# Selenium Browser Automation (User-Scoped Sessions)
# ============================================================================

import threading
from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserBrowserSession:
    """Represents a user's browser session"""
    driver: Any  # webdriver.Chrome
    user_id: str
    created_at: datetime
    last_used: datetime


# User-scoped WebDriver instances: {user_id: UserBrowserSession}
_user_drivers: Dict[str, UserBrowserSession] = {}
_drivers_lock = threading.Lock()

# Session timeout in seconds (close idle sessions after 10 minutes)
SESSION_TIMEOUT_SECONDS = 600


def create_browser_driver() -> Optional[webdriver.Chrome]:
    """
    Initializes and returns a WebDriver for headless Chrome.

    Returns:
        A Chrome WebDriver instance, or None if initialization fails
    """
    if not SELENIUM_AVAILABLE:
        logger.error(f"{LOG_PREFIXES['error']} Selenium is not available. Please install it first.")
        return None

    try:
        logger.info(f"{LOG_PREFIXES['startup']} Initializing Chrome WebDriver...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run Chrome in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Automatically download and manage chromedriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        logger.info(f"{LOG_PREFIXES['success']} Chrome WebDriver initialized successfully")
        return driver

    except Exception as e:
        logger.exception(f"{LOG_PREFIXES['error']} Error initializing WebDriver: {e}")
        return None


def get_driver(user_id: str = "default") -> Optional[webdriver.Chrome]:
    """
    Gets or creates a WebDriver instance for a specific user.

    Args:
        user_id: The user's ID (for session isolation)

    Returns:
        The user's Chrome WebDriver instance
    """
    with _drivers_lock:
        # Check if user already has a session
        if user_id in _user_drivers:
            session = _user_drivers[user_id]
            session.last_used = datetime.now()
            logger.info(f"{LOG_PREFIXES['info']} Reusing browser session for user: {user_id}")
            return session.driver

        # Create new session for user
        driver = create_browser_driver()
        if driver:
            _user_drivers[user_id] = UserBrowserSession(
                driver=driver,
                user_id=user_id,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            logger.info(f"{LOG_PREFIXES['info']} Created new browser session for user: {user_id}")
        return driver


def close_driver(user_id: str = "default"):
    """
    Closes and cleans up the WebDriver instance for a specific user.

    Args:
        user_id: The user's ID whose session should be closed
    """
    with _drivers_lock:
        if user_id in _user_drivers:
            session = _user_drivers[user_id]
            try:
                session.driver.quit()
                logger.info(f"{LOG_PREFIXES['success']} Selenium WebDriver closed for user: {user_id}")
            except Exception as e:
                logger.error(f"{LOG_PREFIXES['error']} Error closing WebDriver for user {user_id}: {e}")
            finally:
                del _user_drivers[user_id]
        else:
            logger.warning(f"{LOG_PREFIXES['warning']} No browser session found for user: {user_id}")


def close_all_drivers():
    """
    Closes all user browser sessions. Used for cleanup on shutdown.
    """
    with _drivers_lock:
        for user_id in list(_user_drivers.keys()):
            session = _user_drivers[user_id]
            try:
                session.driver.quit()
                logger.info(f"{LOG_PREFIXES['success']} Selenium WebDriver closed for user: {user_id}")
            except Exception as e:
                logger.error(f"{LOG_PREFIXES['error']} Error closing WebDriver for user {user_id}: {e}")
        _user_drivers.clear()
        logger.info(f"{LOG_PREFIXES['info']} All browser sessions closed")


def cleanup_idle_sessions():
    """
    Closes browser sessions that have been idle for too long.
    Should be called periodically (e.g., via a background task).
    """
    with _drivers_lock:
        now = datetime.now()
        expired_users = []

        for user_id, session in _user_drivers.items():
            idle_seconds = (now - session.last_used).total_seconds()
            if idle_seconds > SESSION_TIMEOUT_SECONDS:
                expired_users.append(user_id)
                logger.info(f"{LOG_PREFIXES['info']} Session expired for user {user_id} (idle {idle_seconds:.0f}s)")

        for user_id in expired_users:
            session = _user_drivers[user_id]
            try:
                session.driver.quit()
            except Exception as e:
                logger.error(f"{LOG_PREFIXES['error']} Error closing expired session for {user_id}: {e}")
            del _user_drivers[user_id]

        if expired_users:
            logger.info(f"{LOG_PREFIXES['info']} Cleaned up {len(expired_users)} idle browser session(s)")


def get_active_sessions() -> Dict[str, dict]:
    """
    Returns information about active browser sessions.
    Useful for debugging and monitoring.
    """
    with _drivers_lock:
        return {
            user_id: {
                "created_at": session.created_at.isoformat(),
                "last_used": session.last_used.isoformat(),
                "idle_seconds": (datetime.now() - session.last_used).total_seconds()
            }
            for user_id, session in _user_drivers.items()
        }


def selenium_browse(
    url: str,
    steps: Optional[List[Dict[str, Any]]] = None,
    max_length: int = 50000,
    capture_screenshot: bool = True,
    auto_scroll: bool = True,
    scroll_pause: float = 1.0,
    max_scrolls: int = 10,
    user_id: str = "default"
) -> Dict[str, Any]:
    """
    Navigates to a URL using Selenium and optionally performs interactive steps,
    then returns the page content as Markdown and optionally a screenshot.

    Supported steps:
    - {'action': 'click', 'by': 'id', 'value': 'element_id'}
    - {'action': 'send_keys', 'by': 'name', 'value': 'input_name', 'keys': 'text_to_type'}
    - {'action': 'wait', 'seconds': 2}
    - {'action': 'scroll_to_end'}
    - {'action': 'scroll_to_element', 'by': 'id', 'value': 'element_id'}

    Args:
        url: The URL to navigate to
        steps: Optional list of interaction steps to perform
        max_length: Maximum length of text to return
        capture_screenshot: Whether to capture a screenshot (default: True)
        auto_scroll: Whether to automatically scroll to load lazy content (default: True)
        scroll_pause: Seconds to wait between scrolls for content to load (default: 1.0)
        max_scrolls: Maximum number of scroll iterations to prevent infinite scrolling (default: 10)
        user_id: User ID for session isolation (default: "default")

    Returns:
        Dict containing:
        - content: The page content as Markdown
        - screenshot: Base64-encoded PNG screenshot (if capture_screenshot=True)
        - error: Error message if any
    """
    logger.info(f"{LOG_PREFIXES['selenium']} Executing selenium_browse for: '{url}' (user: {user_id})")
    if steps:
        logger.debug(f"Steps to perform: {steps}")

    result = {"content": "", "screenshot": None, "error": None}

    if not SELENIUM_AVAILABLE:
        result["error"] = "Error: Selenium is not available. Please install selenium and webdriver-manager."
        logger.error(f"{LOG_PREFIXES['error']} {result['error']}")
        return result

    driver = get_driver(user_id=user_id)

    if driver is None:
        result["error"] = "Error: Selenium WebDriver not initialized. Please check setup."
        logger.error(f"{LOG_PREFIXES['error']} {result['error']}")
        return result

    try:
        # Set window size for better screenshots (2x high for capturing more content)
        driver.set_window_size(1024, 2048)

        # Navigate to the URL
        logger.info(f"{LOG_PREFIXES['navigate']} Navigating to: {url}")
        driver.get(url)

        # Wait for the page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Additional wait for dynamic content
        time.sleep(2)

        # Auto-scroll to load lazy content (infinite scroll, lazy loading images, etc.)
        if auto_scroll:
            logger.info(f"{LOG_PREFIXES['action']} Auto-scrolling to load lazy content...")
            last_height = driver.execute_script("return document.body.scrollHeight")

            for scroll_count in range(max_scrolls):
                # Scroll down by viewport height
                driver.execute_script("window.scrollBy(0, window.innerHeight);")
                time.sleep(scroll_pause)

                # Calculate new scroll height
                new_height = driver.execute_script("return document.body.scrollHeight")
                current_position = driver.execute_script("return window.pageYOffset + window.innerHeight")

                logger.debug(f"  Scroll {scroll_count + 1}/{max_scrolls}: position={current_position}, total_height={new_height}")

                # Check if we've reached the bottom
                if current_position >= new_height:
                    logger.info(f"{LOG_PREFIXES['success']} Reached bottom of page after {scroll_count + 1} scrolls")
                    break

                # Check if page height hasn't changed (no new content loaded)
                if new_height == last_height:
                    # Try one more scroll to be sure
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause)
                    final_height = driver.execute_script("return document.body.scrollHeight")
                    if final_height == new_height:
                        logger.info(f"{LOG_PREFIXES['success']} No more content to load after {scroll_count + 1} scrolls")
                        break

                last_height = new_height

            # Scroll back to top for screenshot
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

        # Perform the steps if provided
        if steps:
            logger.info(f"{LOG_PREFIXES['action']} Performing {len(steps)} interaction step(s)")
            for i, step in enumerate(steps, 1):
                action = step.get('action', '').lower()
                logger.debug(f"Step {i}/{len(steps)}: {action}")

                if action == 'click':
                    by = getattr(By, step['by'].upper())
                    value = step['value']
                    logger.debug(f"  Clicking element: {step['by']}={value}")
                    element = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((by, value))
                    )
                    element.click()
                    time.sleep(1)  # Small delay for page to react

                elif action == 'send_keys':
                    by = getattr(By, step['by'].upper())
                    value = step['value']
                    keys = step['keys']
                    logger.debug(f"  Sending keys to element: {step['by']}={value}")
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((by, value))
                    )
                    element.clear()
                    element.send_keys(keys)
                    time.sleep(1)

                elif action == 'wait':
                    seconds = step.get('seconds', 1)
                    logger.debug(f"  Waiting {seconds} second(s)")
                    time.sleep(seconds)

                elif action == 'scroll_to_end':
                    logger.debug("  Scrolling to end of page")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Give time for content to load

                elif action == 'scroll_to_element':
                    by = getattr(By, step['by'].upper())
                    value = step['value']
                    logger.debug(f"  Scrolling to element: {step['by']}={value}")
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((by, value))
                    )
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    time.sleep(1)

                else:
                    logger.warning(f"{LOG_PREFIXES['warning']} Unknown action '{action}' in step: {step}")

        # Capture full-page screenshot if requested
        if capture_screenshot:
            try:
                # Get full page dimensions
                total_width = driver.execute_script("return Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, document.body.offsetWidth, document.documentElement.offsetWidth, document.body.clientWidth, document.documentElement.clientWidth);")
                total_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, document.body.offsetHeight, document.documentElement.offsetHeight, document.body.clientHeight, document.documentElement.clientHeight);")

                # Limit max dimensions to prevent memory issues (max 16384px which is common browser limit)
                max_dimension = 16384
                total_width = min(total_width, max_dimension)
                total_height = min(total_height, max_dimension)

                logger.info(f"{LOG_PREFIXES['screenshot']} Capturing full-page screenshot: {total_width}x{total_height}")

                # Save original window size
                original_size = driver.get_window_size()

                # Resize window to full page dimensions
                driver.set_window_size(total_width, total_height)
                time.sleep(0.5)  # Small delay for resize to take effect

                # Scroll to top to capture from beginning
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.3)

                # Capture screenshot
                screenshot_data = driver.get_screenshot_as_base64()
                result["screenshot"] = screenshot_data

                # Restore original window size
                driver.set_window_size(original_size['width'], original_size['height'])

                logger.info(f"{LOG_PREFIXES['screenshot']} Full-page screenshot captured successfully")
            except Exception as e:
                logger.warning(f"{LOG_PREFIXES['warning']} Failed to capture full-page screenshot: {e}")
                # Fallback to regular screenshot
                try:
                    screenshot_data = driver.get_screenshot_as_base64()
                    result["screenshot"] = screenshot_data
                    logger.info(f"{LOG_PREFIXES['screenshot']} Fallback viewport screenshot captured")
                except Exception as e2:
                    logger.warning(f"{LOG_PREFIXES['warning']} Failed to capture fallback screenshot: {e2}")

        # Convert page content to Markdown
        if MARKDOWNIFY_AVAILABLE:
            content = markdownify.markdownify(driver.page_source, heading_style="ATX")
        else:
            # Fallback to plain text extraction
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
                script_or_style.extract()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = '\n'.join(chunk for chunk in chunks if chunk)

        # Truncate if too long
        if len(content) > max_length:
            logger.warning(f"Content truncated from {len(content)} to {max_length} characters")
            content = content[:max_length] + f"\n\n[Content truncated at {max_length} characters]"

        result["content"] = content
        logger.info(f"{LOG_PREFIXES['success']} Successfully browsed with Selenium: {url} ({len(content)} characters)")
        return result

    except Exception as e:
        result["error"] = f"Error during selenium_browse for {url}: {str(e)}"
        logger.exception(f"{LOG_PREFIXES['error']} {result['error']}")
        return result


# ============================================================================
# Tool Declarations for Gemini Integration
# ============================================================================

def get_tool_declarations():
    """
    Returns the tool declarations for use with Google's Gemini AI.

    This function provides the schema definitions that tell the Gemini model
    about available browser tools and how to use them.

    Returns:
        A list of tool declaration dictionaries
    """
    return [
        {
            "name": "web_search",
            "description": "Perform a web search and return a list of formatted search results (title and URL). Useful for finding information on the internet about current events, news, or specific topics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "read_webpage",
            "description": "Read the main text content of a given URL. Useful for summarizing articles, extracting information from specific pages, or reading documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to read"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum length of text to return (default: 50000)",
                        "default": 50000
                    }
                },
                "required": ["url"]
            }
        },
        {
            "name": "selenium_browse",
            "description": "Navigate to a URL using a headless browser (Selenium) with automatic scrolling to load lazy content. Captures screenshots and returns page content as Markdown. Useful for dynamic pages, JavaScript-heavy sites, infinite scroll pages, or those requiring user interaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to"
                    },
                    "steps": {
                        "type": "array",
                        "description": "Optional list of interaction steps to perform on the page",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "Action to perform: 'click', 'send_keys', 'wait', 'scroll_to_end', or 'scroll_to_element'"
                                },
                                "by": {
                                    "type": "string",
                                    "description": "Element locator strategy: 'id', 'name', 'xpath', 'css_selector', 'class_name', 'tag_name', 'link_text', 'partial_link_text'"
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Element locator value (e.g., 'my_button_id', '//button[@class=\"submit\"]')"
                                },
                                "keys": {
                                    "type": "string",
                                    "description": "Text to send (for 'send_keys' action)"
                                },
                                "seconds": {
                                    "type": "integer",
                                    "description": "Seconds to wait (for 'wait' action)"
                                }
                            },
                            "required": ["action"]
                        }
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum length of text to return (default: 50000)",
                        "default": 50000
                    },
                    "auto_scroll": {
                        "type": "boolean",
                        "description": "Whether to automatically scroll the page to load lazy content like infinite scroll or lazy-loaded images (default: true)",
                        "default": True
                    },
                    "scroll_pause": {
                        "type": "number",
                        "description": "Seconds to wait between scrolls for content to load (default: 1.0)",
                        "default": 1.0
                    },
                    "max_scrolls": {
                        "type": "integer",
                        "description": "Maximum number of scroll iterations to prevent infinite scrolling (default: 10)",
                        "default": 10
                    }
                },
                "required": ["url"]
            }
        }
    ]


# ============================================================================
# Available Tools Dictionary
# ============================================================================

AVAILABLE_TOOLS = {
    'web_search': web_search,
    'read_webpage': read_webpage,
    'selenium_browse': selenium_browse
}


# ============================================================================
# Utility Functions
# ============================================================================

def execute_tool(tool_name: str, **kwargs) -> str:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        **kwargs: Arguments to pass to the tool function

    Returns:
        The result of the tool execution
    """
    if tool_name not in AVAILABLE_TOOLS:
        return f"Error: Tool '{tool_name}' not found. Available tools: {list(AVAILABLE_TOOLS.keys())}"

    try:
        tool_func = AVAILABLE_TOOLS[tool_name]
        result = tool_func(**kwargs)
        return result
    except Exception as e:
        return f"Error executing tool '{tool_name}': {str(e)}"


# ============================================================================
# Cleanup
# ============================================================================

def cleanup():
    """
    Clean up resources (close browser, etc.)
    
    注意：此函数在模块卸载时调用，会关闭所有用户的浏览器会话
    """
    close_all_drivers()  # ✅ 使用 close_all_drivers() 而不是 close_driver()，避免警告


# Auto-cleanup on module unload
import atexit
atexit.register(cleanup)


# ============================================================================
# Example Usage (for testing)
# ============================================================================

if __name__ == "__main__":
    print("Testing Browser Tools\n")
    print("=" * 80)

    # Test 1: Web Search
    print("\n1. Testing web_search:")
    print("-" * 80)
    result = web_search("latest news on AI")
    print(result)

    # Test 2: Read Webpage
    print("\n2. Testing read_webpage:")
    print("-" * 80)
    result = read_webpage("https://example.com")
    print(result[:500] + "..." if len(result) > 500 else result)

    # Test 3: Selenium Browse (if available)
    if SELENIUM_AVAILABLE:
        print("\n3. Testing selenium_browse:")
        print("-" * 80)
        result = selenium_browse(
            "https://example.com",
            steps=[{"action": "wait", "seconds": 2}]
        )
        print(result[:500] + "..." if len(result) > 500 else result)
    else:
        print("\n3. Selenium not available - skipping test")

    print("\n" + "=" * 80)
    print("Testing complete!")

    # Cleanup
    cleanup()
