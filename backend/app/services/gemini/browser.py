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
import requests
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

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
    Simulates a web search and returns a string of formatted search results.

    In a real application, you would integrate with a search API (e.g., Google Search API,
    Bing Search API, or SerpAPI). For this example, we'll return simulated results
    based on common queries.

    Args:
        query: The search query string

    Returns:
        A JSON string containing search results with title and URL
    """
    logger.info(f"{LOG_PREFIXES['search']} Executing web_search for: '{query}'")

    # Simulate search results based on common queries
    query_lower = query.lower()

    if "latest news on ai" in query_lower or "ai news" in query_lower:
        return json.dumps([
            {
                "title": "Google I/O 2024: Gemini advancements",
                "url": "https://blog.google/technology/ai/google-gemini-ai-updates-io-2024/"
            },
            {
                "title": "OpenAI announces new features",
                "url": "https://openai.com/blog/latest-updates"
            },
            {
                "title": "AI in healthcare trends",
                "url": "https://www.nature.com/articles/s41591-023-02685-1"
            }
        ], indent=2)

    elif "gemini" in query_lower and ("model" in query_lower or "features" in query_lower):
        return json.dumps([
            {
                "title": "Gemini API Overview",
                "url": "https://ai.google.dev/gemini-api/docs/overview"
            },
            {
                "title": "Gemini 1.5 Pro Release Notes",
                "url": "https://ai.google.dev/gemini-api/docs/release-notes#gemini-1.5-pro"
            },
            {
                "title": "Multimodality with Gemini",
                "url": "https://ai.google.dev/docs/multimodality_overview"
            }
        ], indent=2)

    elif "python" in query_lower and ("web scraping" in query_lower or "scraping" in query_lower):
        return json.dumps([
            {
                "title": "Beautiful Soup Documentation",
                "url": "https://www.crummy.com/software/BeautifulSoup/bs4/doc/"
            },
            {
                "title": "Web Scraping with Python and Requests-HTML",
                "url": "https://realpython.com/web-scraping-with-python/"
            },
            {
                "title": "Selenium Python Bindings",
                "url": "https://selenium-python.readthedocs.io/"
            }
        ], indent=2)

    else:
        # Generic results for any other query
        return json.dumps([
            {
                "title": f"Search Result 1 for: {query}",
                "url": "https://example.com/result1"
            },
            {
                "title": f"Search Result 2 for: {query}",
                "url": "https://example.com/result2"
            },
            {
                "title": f"Search Result 3 for: {query}",
                "url": "https://example.com/result3"
            }
        ], indent=2)


# ============================================================================
# Webpage Reading Tool
# ============================================================================

def read_webpage(url: str, max_length: int = 50000) -> str:
    """
    Reads the content of a given URL and returns its main text.

    This function fetches the HTML content, parses it with BeautifulSoup,
    removes script and style elements, and extracts the main text content.

    Args:
        url: The URL of the webpage to read
        max_length: Maximum length of text to return (default: 50000 characters)

    Returns:
        The extracted text content of the webpage, or an error message
    """
    logger.info(f"{LOG_PREFIXES['webpage']} Executing read_webpage for: '{url}'")

    try:
        # Set a user agent to avoid being blocked by some websites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
            script_or_style.extract()

        # Get text, strip whitespace, and format
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        # Truncate if too long
        if len(text) > max_length:
            logger.warning(f"Content truncated from {len(text)} to {max_length} characters")
            text = text[:max_length] + f"\n\n[Content truncated at {max_length} characters]"
        
        logger.info(f"{LOG_PREFIXES['success']} Successfully read webpage: {url} ({len(text)} characters)")
        return text

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
# Selenium Browser Automation
# ============================================================================

# Global WebDriver instance (optional - can be managed differently)
_global_driver = None


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


def get_driver() -> Optional[webdriver.Chrome]:
    """
    Gets or creates the global WebDriver instance.

    Returns:
        The global Chrome WebDriver instance
    """
    global _global_driver
    if _global_driver is None:
        _global_driver = create_browser_driver()
    return _global_driver


def close_driver():
    """
    Closes and cleans up the global WebDriver instance.
    """
    global _global_driver
    if _global_driver is not None:
        try:
            _global_driver.quit()
            logger.info(f"{LOG_PREFIXES['success']} Selenium WebDriver closed successfully")
        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Error closing WebDriver: {e}")
        finally:
            _global_driver = None


def selenium_browse(url: str, steps: Optional[List[Dict[str, Any]]] = None, max_length: int = 50000) -> str:
    """
    Navigates to a URL using Selenium and optionally performs interactive steps,
    then returns the page content.

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

    Returns:
        The extracted text content after performing all steps, or an error message
    """
    logger.info(f"{LOG_PREFIXES['selenium']} Executing selenium_browse for: '{url}'")
    if steps:
        logger.debug(f"Steps to perform: {steps}")

    if not SELENIUM_AVAILABLE:
        error_msg = "Error: Selenium is not available. Please install selenium and webdriver-manager."
        logger.error(f"{LOG_PREFIXES['error']} {error_msg}")
        return error_msg

    driver = get_driver()

    if driver is None:
        error_msg = "Error: Selenium WebDriver not initialized. Please check setup."
        logger.error(f"{LOG_PREFIXES['error']} {error_msg}")
        return error_msg

    try:
        # Navigate to the URL
        logger.info(f"{LOG_PREFIXES['navigate']} Navigating to: {url}")
        driver.get(url)

        # Wait for the page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

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

        # Extract the page content
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Remove script, style, and navigation elements
        for script_or_style in soup(['script', 'style', 'header', 'footer', 'nav']):
            script_or_style.extract()

        # Get text
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        # Truncate if too long
        if len(text) > max_length:
            logger.warning(f"Content truncated from {len(text)} to {max_length} characters")
            text = text[:max_length] + f"\n\n[Content truncated at {max_length} characters]"

        logger.info(f"{LOG_PREFIXES['success']} Successfully browsed with Selenium: {url} ({len(text)} characters)")
        return text

    except Exception as e:
        error_msg = f"Error during selenium_browse for {url}: {str(e)}"
        logger.exception(f"{LOG_PREFIXES['error']} {error_msg}")
        return error_msg


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
            "description": "Navigate to a URL using a headless browser (Selenium), optionally perform interactive steps (clicks, typing, scrolling), and return the page content. Useful for interacting with dynamic web pages, JavaScript-heavy sites, or those requiring user interaction.",
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
    """
    close_driver()


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
