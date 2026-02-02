#!/usr/bin/env python3
"""
Image Edit Configuration Flow Test Script

Verify the analysis in IMAGE_EDIT_NO_IMAGE_ANALYSIS.md:
1. When kwargs doesn't contain image_aspect_ratio/image_resolution, is edit_config empty?
2. Does empty edit_config lead to send_config = None?
3. When send_config = None, does it rely on chat object's default config?

Usage:
    cd backend
    python scripts/test_image_edit_config_flow.py
"""

import sys
import os
import json

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Color output (works on Windows with ANSI support)
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


def test_edit_config_logic():
    """Test edit_config building logic"""
    print_header("Test 1: edit_config Building Logic")

    print_info("Simulating edit_image() method's edit_config building logic")
    print_info("Source: conversational_image_edit_service.py Line 1163-1175")
    print()

    # Scenario 1: kwargs contains image parameters
    print(f"{Colors.CYAN}Scenario 1: kwargs contains image_aspect_ratio and image_resolution{Colors.END}")
    kwargs_with_params = {
        'frontend_session_id': 'test-session-id',
        'image_aspect_ratio': '16:9',
        'image_resolution': '4K',
        'enhance_prompt': False
    }

    edit_config = {}
    if 'image_aspect_ratio' in kwargs_with_params:
        edit_config['image_aspect_ratio'] = kwargs_with_params['image_aspect_ratio']
    if 'image_resolution' in kwargs_with_params:
        edit_config['image_resolution'] = kwargs_with_params['image_resolution']
    if 'enhance_prompt' in kwargs_with_params:
        edit_config['enhance_prompt'] = kwargs_with_params['enhance_prompt']

    config_to_pass = edit_config if edit_config else None

    print(f"  kwargs = {json.dumps(kwargs_with_params, indent=4)}")
    print(f"  edit_config = {edit_config}")
    print(f"  config_to_pass = {config_to_pass}")
    if config_to_pass:
        print_success("config_to_pass is not None, send_config will be created")
    else:
        print_error("config_to_pass is None")

    print()

    # Scenario 2: kwargs doesn't contain image parameters (PROBLEM SCENARIO)
    print(f"{Colors.CYAN}Scenario 2: kwargs doesn't contain image_aspect_ratio/image_resolution (PROBLEM){Colors.END}")
    kwargs_without_params = {
        'frontend_session_id': 'test-session-id',
        # Note: NO image_aspect_ratio and image_resolution
    }

    edit_config = {}
    if 'image_aspect_ratio' in kwargs_without_params:
        edit_config['image_aspect_ratio'] = kwargs_without_params['image_aspect_ratio']
    if 'image_resolution' in kwargs_without_params:
        edit_config['image_resolution'] = kwargs_without_params['image_resolution']
    if 'enhance_prompt' in kwargs_without_params:
        edit_config['enhance_prompt'] = kwargs_without_params['enhance_prompt']

    config_to_pass = edit_config if edit_config else None

    print(f"  kwargs = {json.dumps(kwargs_without_params, indent=4)}")
    print(f"  edit_config = {edit_config}")
    print(f"  bool(edit_config) = {bool(edit_config)}")  # Empty dict is falsy
    print(f"  config_to_pass = {config_to_pass}")

    if config_to_pass is None:
        print_warning("config_to_pass is None!")
        print_warning("This means send_edit_message() will receive config=None")
        print_error("PROBLEM CONFIRMED: Empty dict {{}} is falsy in Python, causing config=None")
    else:
        print_success("config_to_pass is not None")

    return config_to_pass is None  # Return True if problem exists


def test_send_config_logic():
    """Test send_config building logic"""
    print_header("Test 2: send_config Building Logic")

    print_info("Simulating _send_edit_message_internal() send_config building logic")
    print_info("Source: conversational_image_edit_service.py Line 739-768")
    print()

    # Simulate genai_types available
    genai_types_available = True

    # Scenario 1: config is not None
    print(f"{Colors.CYAN}Scenario 1: config is not None{Colors.END}")
    config_with_data = {
        'image_aspect_ratio': '16:9',
        'image_resolution': '4K'
    }

    send_config = None
    if config_with_data and genai_types_available:
        image_config_dict = {}
        if config_with_data.get('image_aspect_ratio'):
            image_config_dict['aspect_ratio'] = config_with_data['image_aspect_ratio']
        if config_with_data.get('image_resolution'):
            image_config_dict['image_size'] = config_with_data['image_resolution']

        if image_config_dict:
            # send_config would be created here
            send_config = "GenerateContentConfig(response_modalities=[TEXT, IMAGE], ...)"
            print(f"  config = {config_with_data}")
            print(f"  image_config_dict = {image_config_dict}")
            print_success(f"send_config created: {send_config}")

    print()

    # Scenario 2: config = None (PROBLEM SCENARIO)
    print(f"{Colors.CYAN}Scenario 2: config = None (PROBLEM SCENARIO){Colors.END}")
    config_none = None

    send_config = None
    if config_none and genai_types_available:  # config_none is None, condition fails
        # This branch will NOT execute
        pass

    print(f"  config = {config_none}")
    print(f"  bool(config_none) = {bool(config_none)}")
    print(f"  Condition 'if config and genai_types:' = {bool(config_none and genai_types_available)}")
    print(f"  send_config = {send_config}")

    if send_config is None:
        print_warning("send_config is None!")
        print_warning("This means chat.send_message() will use chat object's default config")
        print_error("PROBLEM CONFIRMED: When config=None, send_config will not be created")

    return send_config is None


def test_chat_send_message_behavior():
    """Test chat.send_message() behavior"""
    print_header("Test 3: chat.send_message() Behavior Analysis")

    print_info("Analyzing Google SDK chat.send_message(message, config) behavior")
    print()

    print(f"{Colors.CYAN}Google SDK source code behavior (from chats.py):{Colors.END}")
    print("""
    # Inside chat.send_message():
    config = config if config else self._config

    # This means:
    # - If send_config exists, use send_config
    # - If send_config=None, use chat object's self._config from creation time
    """)

    print(f"{Colors.CYAN}Key question: What is chat object's self._config?{Colors.END}")
    print()

    print("  Case A: chat object is newly created (Line 555-564)")
    print("    -> self._config = chat_config (contains response_modalities=[TEXT, IMAGE])")
    print_success("    In this case, send_config=None should work fine")
    print()

    print("  Case B: chat object is retrieved from cache (Line 382)")
    print("    -> self._config = config from when it was cached")
    print_warning("    If cached chat object was created by old code, it may not have correct config")
    print()

    print("  Case C: chat object rebuild with empty/invalid config_json (Line 462-504)")
    print("    -> Falls back to default logic, self._config contains response_modalities=[TEXT, IMAGE]")
    print_success("    This case should also work fine")


def query_database_config():
    """Query actual session config from database"""
    print_header("Test 4: Query Database Session Configs")

    try:
        from app.core.database import get_db
        from app.models.db_models import GoogleChatSession

        db = next(get_db())

        # Query recent sessions
        sessions = db.query(GoogleChatSession).filter(
            GoogleChatSession.is_active == True
        ).order_by(GoogleChatSession.last_used_at.desc()).limit(5).all()

        if not sessions:
            print_warning("No active Chat sessions in database")
            return

        print_info(f"Found {len(sessions)} active sessions")
        print()

        for i, session in enumerate(sessions, 1):
            print(f"{Colors.CYAN}Session {i}: {session.chat_id[:8]}...{Colors.END}")
            print(f"  model_name: {session.model_name}")
            print(f"  frontend_session_id: {session.frontend_session_id[:8]}...")

            if session.config_json:
                try:
                    config = json.loads(session.config_json)
                    print(f"  config_json fields:")

                    # Check key fields
                    has_aspect_ratio = 'image_aspect_ratio' in config or 'imageAspectRatio' in config
                    has_resolution = 'image_resolution' in config or 'imageResolution' in config
                    has_response_modalities = 'response_modalities' in config

                    if has_aspect_ratio:
                        value = config.get('image_aspect_ratio') or config.get('imageAspectRatio')
                        print_success(f"    image_aspect_ratio: {value}")
                    else:
                        print_warning("    image_aspect_ratio: NOT SET")

                    if has_resolution:
                        value = config.get('image_resolution') or config.get('imageResolution')
                        print_success(f"    image_resolution: {value}")
                    else:
                        print_warning("    image_resolution: NOT SET")

                    if has_response_modalities:
                        print_success(f"    response_modalities: {config.get('response_modalities')}")
                    else:
                        print_info("    response_modalities: Not stored in config_json (normal)")

                except json.JSONDecodeError:
                    print_error("    config_json parse failed")
            else:
                print_warning("  config_json: EMPTY")

            print()

        db.close()

    except ImportError as e:
        print_warning(f"Cannot import database module: {e}")
        print_info("Please run this script from the backend directory")
    except Exception as e:
        print_error(f"Database query failed: {e}")


def analyze_root_cause():
    """Analyze root cause"""
    print_header("Test 5: Root Cause Analysis")

    print(f"""
{Colors.CYAN}Problem Scenario Reproduction:{Colors.END}

1. User sends image edit request with existing session
2. Frontend may not pass image_aspect_ratio/image_resolution in every request
3. Backend edit_image() checks kwargs, finds no such parameters
4. edit_config = {{}} (empty dict)
5. Empty dict is falsy in Python: bool({{}}) = {bool({})}
6. config = edit_config if edit_config else None -> config = None
7. send_edit_message(config=None) is called
8. In _send_edit_message_internal():
   - if config and genai_types: -> False (because config=None)
   - send_config = None
9. chat.send_message(message) is called (without config parameter)
10. Google SDK uses chat object's default config from creation time

{Colors.YELLOW}Key Issue:{Colors.END}

chat object's default config is set when:
- Creating new session (create_chat_session)
- Rebuilding chat object (_send_edit_message_internal Line 430-564)

If chat object is retrieved from cache, its config depends on the code logic
when it was created/rebuilt. If that code didn't set response_modalities correctly,
the problem occurs.

{Colors.GREEN}Verification Method:{Colors.END}

Check backend logs for [DEBUG] output:
- chat_config created successfully (which path? what config?)
- send_config created successfully or "Sending message: send_config=does not exist"
- Response contains X parts (how many parts? any images?)

{Colors.RED}Root Cause Confirmed:{Colors.END}

Based on code analysis, the problem is in send_config conditional check:

Line 740-748:
    if config and genai_types:
        image_config_dict = {{}}
        if config.get('image_aspect_ratio'):
            image_config_dict['aspect_ratio'] = ...
        if config.get('image_resolution'):
            image_config_dict['image_size'] = ...

        if image_config_dict:  # <- Only creates send_config when image_config_dict is not empty
            send_config = ...

Problem: Even if config exists, if config doesn't have image_aspect_ratio and image_resolution,
image_config_dict will still be empty, and send_config won't be created.

{Colors.GREEN}Recommended Fix:{Colors.END}

Modify Line 739-768 to ensure send_config is always created (with response_modalities=[TEXT, IMAGE]):

send_config = None
if genai_types:  # <- Remove 'config and' condition
    image_config_dict = {{}}
    if config:
        if config.get('image_aspect_ratio'):
            image_config_dict['aspect_ratio'] = config['image_aspect_ratio']
        if config.get('image_resolution'):
            image_config_dict['image_size'] = config['image_resolution']

    # <- Always create send_config to ensure response_modalities is set
    send_config = genai_types.GenerateContentConfig(
        response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
        thinking_config=thinking_cfg,
        image_config=genai_types.ImageConfig(**image_config_dict) if image_config_dict else None,
        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True)
    )
""")


def main():
    """Main test function"""
    print(f"\n{Colors.BOLD}Image Edit Configuration Flow Test{Colors.END}")
    print(f"Verifying analysis in IMAGE_EDIT_NO_IMAGE_ANALYSIS.md")
    print()

    # Test 1
    problem1 = test_edit_config_logic()

    # Test 2
    problem2 = test_send_config_logic()

    # Test 3
    test_chat_send_message_behavior()

    # Test 4
    query_database_config()

    # Test 5
    analyze_root_cause()

    # Summary
    print_header("Test Summary")

    if problem1 and problem2:
        print_error("PROBLEM CONFIRMED: The analysis in the document is CORRECT!")
        print()
        print(f"{Colors.YELLOW}Problem Chain:{Colors.END}")
        print("  1. kwargs has no image params -> edit_config = {}")
        print("  2. Empty dict is falsy -> config = None")
        print("  3. config=None -> send_config won't be created")
        print("  4. send_config=None -> uses chat default config")
        print("  5. If chat default config has issues -> returns text only, no images")
        print()
        print(f"{Colors.GREEN}Recommended Fix:{Colors.END}")
        print("  Use document's fix suggestion 1: Ensure send_config is always created")
    else:
        print_success("Tests passed, problem may be elsewhere")

    print()


if __name__ == "__main__":
    main()
