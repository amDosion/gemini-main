#!/usr/bin/env python3
"""
Streaming Response Timeout Test Script

Tests:
1. Streaming response behavior with 30-second timeout detection
2. Different attachment sources (manual upload, canvas, cross-mode)
3. Auto-restart backend if stuck

Usage:
    cd backend
    python scripts/test_streaming_timeout.py
"""

import sys
import os
import json
import time
import asyncio
import subprocess
import signal
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Color output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.END}")


def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.CYAN}[INFO] {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")


# Configuration
BACKEND_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 30
HEALTH_CHECK_TIMEOUT = 5

# Sample base64 image (1x1 red pixel PNG)
SAMPLE_BASE64_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


class BackendManager:
    """Manages backend process lifecycle"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    async def is_running(self) -> bool:
        """Check if backend is running via health check"""
        try:
            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                # Try root endpoint first (returns {"status": "ok", ...})
                response = await client.get(f"{BACKEND_URL}/")
                if response.status_code == 200:
                    return True
                # Fallback to /api/health
                response = await client.get(f"{BACKEND_URL}/api/health")
                return response.status_code == 200
        except Exception:
            return False

    async def wait_for_startup(self, max_wait: int = 30) -> bool:
        """Wait for backend to start"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if await self.is_running():
                return True
            await asyncio.sleep(1)
        return False

    def start(self) -> bool:
        """Start the backend"""
        print_info("Starting backend...")
        try:
            # Use uvicorn to start
            self.process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=self.backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            return True
        except Exception as e:
            print_error(f"Failed to start backend: {e}")
            return False

    def stop(self):
        """Stop the backend"""
        print_info("Stopping backend...")
        if self.process:
            try:
                if os.name == 'nt':
                    # Windows
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    # Unix
                    self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                print_warning(f"Error stopping backend: {e}")
            finally:
                self.process = None

    async def restart(self) -> bool:
        """Restart the backend"""
        print_warning("Restarting backend due to timeout...")
        self.stop()
        await asyncio.sleep(2)  # Wait for cleanup
        if self.start():
            return await self.wait_for_startup()
        return False


class StreamingTestClient:
    """Test client for streaming API"""

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def test_streaming_with_timeout(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        timeout_seconds: int = TIMEOUT_SECONDS
    ) -> Dict[str, Any]:
        """
        Test streaming endpoint with timeout detection

        Returns:
            {
                "success": bool,
                "timeout": bool,
                "first_chunk_time": float,  # seconds until first chunk
                "total_time": float,
                "chunks_received": int,
                "has_image": bool,
                "error": str or None
            }
        """
        result = {
            "success": False,
            "timeout": False,
            "first_chunk_time": None,
            "total_time": 0,
            "chunks_received": 0,
            "has_image": False,
            "error": None,
            "response_text": ""
        }

        start_time = time.time()
        first_chunk_received = False

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{BACKEND_URL}{endpoint}",
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status_code != 200:
                        result["error"] = f"HTTP {response.status_code}"
                        return result

                    async for line in response.aiter_lines():
                        current_time = time.time()
                        elapsed = current_time - start_time

                        # Check timeout (30 seconds without first chunk, or 30 seconds between chunks)
                        if not first_chunk_received and elapsed > timeout_seconds:
                            result["timeout"] = True
                            result["error"] = f"Timeout: No response in {timeout_seconds}s"
                            return result

                        if line.startswith("data: "):
                            result["chunks_received"] += 1

                            if not first_chunk_received:
                                first_chunk_received = True
                                result["first_chunk_time"] = elapsed
                                print_info(f"First chunk received after {elapsed:.2f}s")

                            try:
                                data = json.loads(line[6:])

                                # Check for image in response
                                if data.get("attachments"):
                                    result["has_image"] = True
                                    print_success("Image detected in response!")

                                # Accumulate text
                                if data.get("text"):
                                    result["response_text"] += data["text"]

                                # Check for completion
                                if data.get("chunk_type") == "done":
                                    result["success"] = True
                                    break

                                # Check for error
                                if data.get("error"):
                                    result["error"] = data["error"]
                                    break

                            except json.JSONDecodeError:
                                pass

                        # Reset timeout check for subsequent chunks
                        start_time = current_time

        except asyncio.TimeoutError:
            result["timeout"] = True
            result["error"] = "Connection timeout"
        except Exception as e:
            result["error"] = str(e)

        result["total_time"] = time.time() - start_time
        return result


async def get_test_token() -> Optional[str]:
    """Get a test token for API calls"""
    # Check environment variable first
    token = os.environ.get("TEST_TOKEN")
    if token:
        print_success("Using TEST_TOKEN from environment")
        return token

    # Try to get token from database (user might have one stored)
    try:
        from app.core.database import get_db
        from app.models.db_models import User

        db = next(get_db())
        user = db.query(User).filter(User.status == 'active').first()
        if user and user.access_token:
            print_success(f"Using stored token for user: {user.email}")
            db.close()
            return user.access_token
        db.close()
        print_info(f"Found user {user.email if user else 'none'} but no stored token")
    except Exception as e:
        print_warning(f"Could not get token from database: {e}")

    print_warning("Could not get test token")
    print_info("Please set TEST_TOKEN environment variable")
    print_info("Or login via browser first to store access_token in database")

    return None


async def test_scenario_1_manual_upload(token: str):
    """Test scenario 1: Manual upload attachment with base64 data"""
    print_header("Scenario 1: Manual Upload Attachment (Base64)")

    payload = {
        "modelId": "gemini-2.0-flash-exp",
        "prompt": "Describe this image briefly",
        "attachments": [
            {
                "id": "test-att-1",
                "mimeType": "image/png",
                "name": "test.png",
                "url": f"data:image/png;base64,{SAMPLE_BASE64_IMAGE}"
            }
        ],
        "options": {
            "imageAspectRatio": "1:1",
            "imageResolution": "1K",
            "numberOfImages": 1,
            "enableThinking": False,
            "enhancePrompt": False,
            "frontendSessionId": f"test-session-{int(time.time())}",
            "sessionId": f"test-session-{int(time.time())}",
            "messageId": f"test-msg-{int(time.time())}"
        }
    }

    print_info(f"Payload options: {json.dumps(payload['options'], indent=2)}")

    client = StreamingTestClient(token=token)
    result = await client.test_streaming_with_timeout(
        "/api/modes/google/image-chat-edit",
        payload,
        timeout_seconds=TIMEOUT_SECONDS
    )

    print_test_result("Manual Upload (Base64)", result)
    return result


async def test_scenario_2_http_url(token: str):
    """Test scenario 2: HTTP URL attachment (canvas/cross-mode)"""
    print_header("Scenario 2: HTTP URL Attachment (Canvas/Cross-mode)")

    # Use a publicly accessible test image
    payload = {
        "modelId": "gemini-2.0-flash-exp",
        "prompt": "Make this image brighter",
        "attachments": [
            {
                "id": "test-att-2",
                "mimeType": "image/png",
                "name": "test-http.png",
                "url": "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"
            }
        ],
        "options": {
            "imageAspectRatio": "1:1",
            "imageResolution": "1K",
            "numberOfImages": 1,
            "enableThinking": False,
            "enhancePrompt": False,
            "frontendSessionId": f"test-session-http-{int(time.time())}",
            "sessionId": f"test-session-http-{int(time.time())}",
            "messageId": f"test-msg-http-{int(time.time())}"
        }
    }

    print_info(f"Testing with HTTP URL: {payload['attachments'][0]['url'][:50]}...")

    client = StreamingTestClient(token=token)
    result = await client.test_streaming_with_timeout(
        "/api/modes/google/image-chat-edit",
        payload,
        timeout_seconds=TIMEOUT_SECONDS
    )

    print_test_result("HTTP URL (Canvas/Cross-mode)", result)
    return result


async def test_scenario_3_no_attachment(token: str):
    """Test scenario 3: No attachment (text-only prompt)"""
    print_header("Scenario 3: No Attachment (Text-only)")

    payload = {
        "modelId": "gemini-2.0-flash-exp",
        "prompt": "Generate an image of a sunset over mountains",
        "attachments": [],
        "options": {
            "imageAspectRatio": "1:1",
            "imageResolution": "1K",
            "numberOfImages": 1,
            "enableThinking": False,
            "enhancePrompt": False,
            "frontendSessionId": f"test-session-noatt-{int(time.time())}",
            "sessionId": f"test-session-noatt-{int(time.time())}",
            "messageId": f"test-msg-noatt-{int(time.time())}"
        }
    }

    print_info("Testing without attachments (text-to-image)")

    client = StreamingTestClient(token=token)
    result = await client.test_streaming_with_timeout(
        "/api/modes/google/image-chat-edit",
        payload,
        timeout_seconds=TIMEOUT_SECONDS
    )

    print_test_result("No Attachment (Text-only)", result)
    return result


async def test_scenario_4_missing_image_params(token: str):
    """Test scenario 4: Missing image_aspect_ratio and image_resolution (bug scenario)"""
    print_header("Scenario 4: Missing Image Params (Bug Scenario)")

    payload = {
        "modelId": "gemini-2.0-flash-exp",
        "prompt": "Describe this image",
        "attachments": [
            {
                "id": "test-att-4",
                "mimeType": "image/png",
                "name": "test.png",
                "url": f"data:image/png;base64,{SAMPLE_BASE64_IMAGE}"
            }
        ],
        "options": {
            # Intentionally omit imageAspectRatio and imageResolution
            "numberOfImages": 1,
            "enableThinking": False,
            "enhancePrompt": False,
            "frontendSessionId": f"test-session-noparam-{int(time.time())}",
            "sessionId": f"test-session-noparam-{int(time.time())}",
            "messageId": f"test-msg-noparam-{int(time.time())}"
        }
    }

    print_warning("Testing WITHOUT imageAspectRatio and imageResolution (BUG SCENARIO)")
    print_info("If the bug exists, this should return text-only (no image)")

    client = StreamingTestClient(token=token)
    result = await client.test_streaming_with_timeout(
        "/api/modes/google/image-chat-edit",
        payload,
        timeout_seconds=TIMEOUT_SECONDS
    )

    print_test_result("Missing Image Params", result)

    # Analyze result for bug
    if result["success"] and not result["has_image"]:
        print_error("BUG CONFIRMED: Response has no image when image params are missing!")
    elif result["success"] and result["has_image"]:
        print_success("No bug: Image generated even without explicit params")

    return result


def print_test_result(scenario_name: str, result: Dict[str, Any]):
    """Print formatted test result"""
    print()
    print(f"{Colors.CYAN}Result for {scenario_name}:{Colors.END}")
    print(f"  Success: {result['success']}")
    print(f"  Timeout: {result['timeout']}")
    print(f"  First chunk time: {result['first_chunk_time']:.2f}s" if result['first_chunk_time'] else "  First chunk time: N/A")
    print(f"  Total time: {result['total_time']:.2f}s")
    print(f"  Chunks received: {result['chunks_received']}")
    print(f"  Has image: {result['has_image']}")
    if result['error']:
        print(f"  Error: {result['error']}")
    if result['response_text']:
        preview = result['response_text'][:100] + "..." if len(result['response_text']) > 100 else result['response_text']
        print(f"  Response preview: {preview}")
    print()


async def main():
    """Main test function"""
    print(f"\n{Colors.BOLD}Streaming Response Timeout Test{Colors.END}")
    print(f"Timeout threshold: {TIMEOUT_SECONDS} seconds")
    print(f"Backend URL: {BACKEND_URL}")
    print()

    backend = BackendManager()

    # Check if backend is running
    print_info("Checking backend status...")
    if not await backend.is_running():
        print_warning("Backend is not running")
        print_info("Please start the backend manually with: cd backend && uvicorn app.main:app --reload")
        print_info("Or set BACKEND_AUTO_START=1 to enable auto-start")

        if os.environ.get("BACKEND_AUTO_START") == "1":
            if backend.start():
                if await backend.wait_for_startup():
                    print_success("Backend started successfully")
                else:
                    print_error("Backend failed to start")
                    return
            else:
                print_error("Could not start backend")
                return
        else:
            print_error("Backend not running. Exiting.")
            return

    print_success("Backend is running")

    # Get authentication token
    print_info("Getting authentication token...")
    token = await get_test_token()
    if not token:
        print_error("Could not get authentication token")
        print_info("Please either:")
        print_info("  1. Set TEST_TOKEN environment variable")
        print_info("  2. Create a test user with: admin/admin123")
        return

    # Run tests
    results = {}

    try:
        # Test 1: Manual upload
        results["manual_upload"] = await test_scenario_1_manual_upload(token)

        # Check for timeout and restart if needed
        if results["manual_upload"]["timeout"]:
            print_warning("Test 1 timed out, restarting backend...")
            if os.environ.get("BACKEND_AUTO_START") == "1":
                await backend.restart()
            else:
                print_error("Please restart the backend manually")
                return

        await asyncio.sleep(2)  # Brief pause between tests

        # Test 2: HTTP URL
        results["http_url"] = await test_scenario_2_http_url(token)

        if results["http_url"]["timeout"]:
            print_warning("Test 2 timed out")
            if os.environ.get("BACKEND_AUTO_START") == "1":
                await backend.restart()

        await asyncio.sleep(2)

        # Test 3: No attachment
        results["no_attachment"] = await test_scenario_3_no_attachment(token)

        if results["no_attachment"]["timeout"]:
            print_warning("Test 3 timed out")

        await asyncio.sleep(2)

        # Test 4: Bug scenario
        results["missing_params"] = await test_scenario_4_missing_image_params(token)

    except KeyboardInterrupt:
        print_warning("\nTest interrupted by user")

    # Summary
    print_header("Test Summary")

    total = len(results)
    passed = sum(1 for r in results.values() if r["success"])
    timeouts = sum(1 for r in results.values() if r["timeout"])
    with_images = sum(1 for r in results.values() if r["has_image"])

    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}")
    print(f"  Timeouts: {timeouts}")
    print(f"  Tests with images: {with_images}")
    print()

    for name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if result["success"] else f"{Colors.RED}FAIL{Colors.END}"
        timeout_flag = f" {Colors.YELLOW}(TIMEOUT){Colors.END}" if result["timeout"] else ""
        image_flag = f" {Colors.GREEN}[IMG]{Colors.END}" if result["has_image"] else ""
        print(f"  [{status}] {name}{timeout_flag}{image_flag}")

    print()

    # Analysis
    print_header("Analysis")

    if results.get("missing_params", {}).get("success") and not results.get("missing_params", {}).get("has_image"):
        print_error("BUG CONFIRMED: When imageAspectRatio/imageResolution are missing, API returns text only")
        print()
        print(f"{Colors.YELLOW}Root Cause:{Colors.END}")
        print("  1. Frontend sends request without image params")
        print("  2. Backend edit_config = {} (empty dict)")
        print("  3. Empty dict is falsy: config = None")
        print("  4. send_config not created")
        print("  5. Chat uses default config without response_modalities=[TEXT, IMAGE]")
        print()
        print(f"{Colors.GREEN}Recommended Fix:{Colors.END}")
        print("  Ensure send_config is always created with response_modalities")
    elif timeouts > 0:
        print_warning("Some tests timed out - possible streaming issue")
        print()
        print(f"{Colors.YELLOW}Possible Causes:{Colors.END}")
        print("  1. Backend is stuck processing the request")
        print("  2. Google API is slow or unresponsive")
        print("  3. Network issues")
        print()
        print(f"{Colors.GREEN}Recommended Action:{Colors.END}")
        print("  Check backend logs for errors or stuck processes")
    else:
        print_success("All tests passed - normal flow is working")

    print()


if __name__ == "__main__":
    asyncio.run(main())
