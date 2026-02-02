#!/usr/bin/env python3
"""
Cleanup Database Sessions and Run Tests

This script:
1. Clears all Google Chat sessions from the database
2. Clears the in-memory chat object cache
3. Runs the streaming timeout test

Usage:
    cd backend
    python scripts/cleanup_and_test.py
"""

import sys
import os
import asyncio

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


def cleanup_database():
    """Clean up all chat sessions from database"""
    print_header("Step 1: Cleaning Database Sessions")

    try:
        from app.core.database import get_db, engine
        from app.models.db_models import GoogleChatSession, ChatSession
        from sqlalchemy.orm import Session
        from sqlalchemy import text

        db = next(get_db())

        # Count before cleanup
        google_count_before = db.query(GoogleChatSession).count()
        chat_count_before = db.query(ChatSession).count()

        print_info(f"Found {google_count_before} Google Chat sessions")
        print_info(f"Found {chat_count_before} Chat sessions")

        # Delete all Google Chat sessions
        if google_count_before > 0:
            deleted_google = db.query(GoogleChatSession).delete()
            print_success(f"Deleted {deleted_google} Google Chat sessions")
        else:
            print_info("No Google Chat sessions to delete")

        # Optionally delete all Chat sessions (for image-chat-edit mode)
        if chat_count_before > 0:
            # Only delete image-chat-edit related sessions
            deleted_chat = db.query(ChatSession).filter(
                ChatSession.mode.in_(['image-chat-edit', 'image-mask-edit', 'image-gen'])
            ).delete(synchronize_session='fetch')
            print_success(f"Deleted {deleted_chat} image-related Chat sessions")
        else:
            print_info("No Chat sessions to delete")

        # Commit changes
        db.commit()

        # Verify cleanup
        google_count_after = db.query(GoogleChatSession).count()
        chat_count_after = db.query(ChatSession).count()

        print_info(f"After cleanup: {google_count_after} Google Chat sessions, {chat_count_after} Chat sessions")

        db.close()

        print_success("Database cleanup completed")
        return True

    except Exception as e:
        print_error(f"Database cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_cache():
    """Clear in-memory chat object cache"""
    print_header("Step 2: Clearing In-Memory Cache")

    try:
        # Try to import and clear the chat session manager cache
        from app.services.gemini.geminiapi.chat_session_manager import ChatSessionManager

        # The cache is typically stored as a class attribute or module-level dict
        # Check if there's a way to clear it
        manager = ChatSessionManager()

        if hasattr(manager, '_chat_objects_cache'):
            cache_size = len(manager._chat_objects_cache)
            manager._chat_objects_cache.clear()
            print_success(f"Cleared {cache_size} cached chat objects")
        elif hasattr(manager, 'chat_cache'):
            cache_size = len(manager.chat_cache)
            manager.chat_cache.clear()
            print_success(f"Cleared {cache_size} cached chat objects")
        else:
            print_info("No cache found to clear (cache may be per-instance)")

        return True

    except ImportError as e:
        print_warning(f"Could not import ChatSessionManager: {e}")
        print_info("Cache will be cleared when backend restarts")
        return True
    except Exception as e:
        print_error(f"Cache cleanup failed: {e}")
        return False


def show_session_stats():
    """Show current session statistics"""
    print_header("Current Session Statistics")

    try:
        from app.core.database import get_db
        from app.models.db_models import GoogleChatSession, ChatSession

        db = next(get_db())

        # Google Chat Sessions stats
        total_google = db.query(GoogleChatSession).count()
        active_google = db.query(GoogleChatSession).filter(
            GoogleChatSession.is_active == True
        ).count()

        print_info(f"Google Chat Sessions: {total_google} total, {active_google} active")

        # Chat Sessions stats by mode
        from sqlalchemy import func
        mode_counts = db.query(
            ChatSession.mode,
            func.count(ChatSession.id)
        ).group_by(ChatSession.mode).all()

        print_info("Chat Sessions by mode:")
        for mode, count in mode_counts:
            print(f"    {mode or 'unknown'}: {count}")

        db.close()

    except Exception as e:
        print_error(f"Could not get session stats: {e}")


async def run_quick_test():
    """Run a quick API test"""
    print_header("Step 3: Quick API Test")

    try:
        import httpx

        BACKEND_URL = "http://localhost:8000"

        # Check if backend is running
        print_info("Checking backend status...")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{BACKEND_URL}/api/health")
                if response.status_code == 200:
                    print_success("Backend is running")
                else:
                    print_error(f"Backend health check failed: {response.status_code}")
                    return False
        except Exception as e:
            print_error(f"Backend not reachable: {e}")
            print_info("Please start the backend with: uvicorn app.main:app --reload")
            return False

        # Run a simple test
        print_info("Running image edit test with fresh session...")

        # Sample base64 image (1x1 red pixel PNG)
        SAMPLE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

        import time
        session_id = f"clean-test-{int(time.time())}"

        payload = {
            "modelId": "gemini-2.0-flash-exp",
            "prompt": "Describe this image briefly",
            "attachments": [
                {
                    "id": "test-att-1",
                    "mimeType": "image/png",
                    "name": "test.png",
                    "url": f"data:image/png;base64,{SAMPLE_BASE64}"
                }
            ],
            "options": {
                "imageAspectRatio": "1:1",
                "imageResolution": "1K",
                "numberOfImages": 1,
                "enableThinking": False,
                "enhancePrompt": False,
                "frontendSessionId": session_id,
                "sessionId": session_id,
                "messageId": f"msg-{int(time.time())}"
            }
        }

        print_info(f"Test session ID: {session_id}")
        print_info(f"Options: imageAspectRatio={payload['options']['imageAspectRatio']}, imageResolution={payload['options']['imageResolution']}")

        start_time = time.time()
        chunks_received = 0
        has_image = False
        response_text = ""

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{BACKEND_URL}/api/modes/google/image-chat-edit",
                json=payload
            ) as response:
                if response.status_code != 200:
                    print_error(f"API returned {response.status_code}")
                    content = await response.aread()
                    print_error(f"Response: {content.decode()[:500]}")
                    return False

                async for line in response.aiter_lines():
                    elapsed = time.time() - start_time

                    # Timeout check (30 seconds)
                    if elapsed > 30:
                        print_error("TIMEOUT: No response in 30 seconds")
                        return False

                    if line.startswith("data: "):
                        chunks_received += 1
                        try:
                            import json
                            data = json.loads(line[6:])

                            if data.get("attachments"):
                                has_image = True
                                print_success(f"Image detected in response! (chunk {chunks_received})")

                            if data.get("text"):
                                response_text += data["text"]

                            if data.get("chunk_type") == "done":
                                break

                        except:
                            pass

        elapsed = time.time() - start_time
        print_info(f"Test completed in {elapsed:.2f}s")
        print_info(f"Chunks received: {chunks_received}")
        print_info(f"Has image: {has_image}")
        if response_text:
            preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
            print_info(f"Response text: {preview}")

        if has_image:
            print_success("TEST PASSED: Image received in response")
            return True
        else:
            print_warning("TEST WARNING: No image in response (may be expected for description request)")
            return True

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print(f"\n{Colors.BOLD}Database Cleanup and Test Script{Colors.END}")
    print("This script will clean all chat sessions and run a fresh test")
    print()

    # Step 1: Show current stats
    show_session_stats()

    # Step 2: Cleanup database
    if not cleanup_database():
        print_error("Database cleanup failed, aborting")
        return

    # Step 3: Cleanup cache
    cleanup_cache()

    # Step 4: Show stats after cleanup
    show_session_stats()

    # Step 5: Run quick test
    print_warning("Note: Backend must be running for the API test")
    print_info("If backend is not running, start it with: uvicorn app.main:app --reload")
    print()

    # Ask user if they want to run the test
    try:
        response = input("Run API test? (y/n): ").strip().lower()
        if response == 'y':
            asyncio.run(run_quick_test())
        else:
            print_info("Skipping API test")
    except EOFError:
        # Non-interactive mode
        print_info("Non-interactive mode, running API test...")
        asyncio.run(run_quick_test())

    print()
    print_header("Cleanup Complete")
    print_success("Database sessions have been cleared")
    print_info("When you start the backend, all chat sessions will be fresh")
    print_info("This ensures no cached config issues from old sessions")


if __name__ == "__main__":
    main()
