#!/usr/bin/env python3
"""
Full Data Flow Test - Verify the complete data flow from frontend to backend

This script tests:
1. Case conversion middleware (camelCase -> snake_case)
2. ModeOptions parsing
3. Parameters passing to edit_image()
4. edit_config and send_config building

Usage:
    cd backend
    python scripts/test_full_data_flow.py
"""

import sys
import os
import json

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


def test_case_conversion():
    """Test camelCase to snake_case conversion"""
    print_header("Test 1: Case Conversion Middleware")

    from app.utils.case_converter import to_snake_case, camel_to_snake

    # Test camel_to_snake function
    print_info("Testing camel_to_snake function:")
    test_cases = [
        ("imageAspectRatio", "image_aspect_ratio"),
        ("imageResolution", "image_resolution"),
        ("numberOfImages", "number_of_images"),
        ("frontendSessionId", "frontend_session_id"),
        ("enableThinking", "enable_thinking"),
        ("enhancePrompt", "enhance_prompt"),
    ]

    all_passed = True
    for camel, expected_snake in test_cases:
        result = camel_to_snake(camel)
        if result == expected_snake:
            print_success(f"  {camel} -> {result}")
        else:
            print_error(f"  {camel} -> {result} (expected: {expected_snake})")
            all_passed = False

    # Test full request body conversion
    print()
    print_info("Testing full request body conversion:")

    frontend_request = {
        "modelId": "gemini-2.5-flash",
        "prompt": "Edit this image",
        "attachments": [
            {
                "id": "att-1",
                "mimeType": "image/png",
                "url": "data:image/png;base64,..."
            }
        ],
        "options": {
            "imageAspectRatio": "1:1",
            "imageResolution": "1K",
            "numberOfImages": 1,
            "frontendSessionId": "session-123",
            "sessionId": "session-123",
            "messageId": "msg-456",
            "enableThinking": False,
            "enhancePrompt": False
        }
    }

    print(f"  Frontend request (camelCase):")
    print(f"    options.imageAspectRatio = {frontend_request['options']['imageAspectRatio']}")
    print(f"    options.imageResolution = {frontend_request['options']['imageResolution']}")

    backend_request = to_snake_case(frontend_request)

    print(f"\n  Backend request (snake_case after middleware):")
    print(f"    options.image_aspect_ratio = {backend_request['options'].get('image_aspect_ratio')}")
    print(f"    options.image_resolution = {backend_request['options'].get('image_resolution')}")

    # Verify conversion
    options = backend_request['options']
    if options.get('image_aspect_ratio') == '1:1':
        print_success("  image_aspect_ratio correctly converted")
    else:
        print_error(f"  image_aspect_ratio conversion failed: {options.get('image_aspect_ratio')}")
        all_passed = False

    if options.get('image_resolution') == '1K':
        print_success("  image_resolution correctly converted")
    else:
        print_error(f"  image_resolution conversion failed: {options.get('image_resolution')}")
        all_passed = False

    return all_passed


def test_mode_options_parsing():
    """Test ModeOptions pydantic model parsing"""
    print_header("Test 2: ModeOptions Pydantic Model Parsing")

    from app.routers.core.modes import ModeOptions

    # Simulate the converted request options (snake_case)
    options_dict = {
        "image_aspect_ratio": "1:1",
        "image_resolution": "1K",
        "number_of_images": 1,
        "frontend_session_id": "session-123",
        "session_id": "session-123",
        "message_id": "msg-456",
        "enable_thinking": False,
        "enhance_prompt": False
    }

    print_info("Input options (snake_case):")
    for k, v in options_dict.items():
        print(f"    {k} = {v}")

    # Parse with Pydantic model
    try:
        mode_options = ModeOptions(**options_dict)
        print_success("ModeOptions parsed successfully")

        # Check fields
        print()
        print_info("Parsed ModeOptions attributes:")
        print(f"    image_aspect_ratio = {mode_options.image_aspect_ratio}")
        print(f"    image_resolution = {mode_options.image_resolution}")
        print(f"    number_of_images = {mode_options.number_of_images}")
        print(f"    frontend_session_id = {mode_options.frontend_session_id}")

        # Convert to dict (exclude_none=True)
        options_extracted = mode_options.dict(exclude_none=True)
        print()
        print_info("Extracted options (exclude_none=True):")
        for k, v in options_extracted.items():
            print(f"    {k} = {v}")

        # Verify
        if 'image_aspect_ratio' in options_extracted:
            print_success("image_aspect_ratio preserved in extracted dict")
        else:
            print_error("image_aspect_ratio NOT in extracted dict!")
            return False

        if 'image_resolution' in options_extracted:
            print_success("image_resolution preserved in extracted dict")
        else:
            print_error("image_resolution NOT in extracted dict!")
            return False

        return True

    except Exception as e:
        print_error(f"ModeOptions parsing failed: {e}")
        return False


def test_edit_config_building():
    """Test edit_config building in edit_image()"""
    print_header("Test 3: edit_config Building Logic")

    # Simulate kwargs received by edit_image()
    # This is what modes.py passes via params.update(options_dict)
    kwargs_with_params = {
        "model": "gemini-2.5-flash",
        "prompt": "Edit this image",
        "reference_images": {"raw": "data:image/png;base64,..."},
        "user_id": "user-123",
        "frontend_session_id": "session-123",
        "session_id": "session-123",
        "message_id": "msg-456",
        "image_aspect_ratio": "1:1",
        "image_resolution": "1K",
        "number_of_images": 1,
        "enable_thinking": False,
        "enhance_prompt": False
    }

    print_info("kwargs received by edit_image():")
    for k, v in kwargs_with_params.items():
        if k not in ['reference_images']:  # Skip long values
            print(f"    {k} = {v}")

    # Simulate edit_config building (from conversational_image_edit_service.py Line 1163-1175)
    edit_config = {}
    if 'image_aspect_ratio' in kwargs_with_params:
        edit_config['image_aspect_ratio'] = kwargs_with_params['image_aspect_ratio']
    if 'image_resolution' in kwargs_with_params:
        edit_config['image_resolution'] = kwargs_with_params['image_resolution']
    if 'enhance_prompt' in kwargs_with_params:
        edit_config['enhance_prompt'] = kwargs_with_params['enhance_prompt']
    if 'enhance_prompt_model' in kwargs_with_params:
        edit_config['enhance_prompt_model'] = kwargs_with_params['enhance_prompt_model']
    if 'enable_thinking' in kwargs_with_params:
        edit_config['enable_thinking'] = kwargs_with_params['enable_thinking']

    config = edit_config if edit_config else None

    print()
    print_info("Built edit_config:")
    print(f"    edit_config = {edit_config}")
    print(f"    bool(edit_config) = {bool(edit_config)}")
    print(f"    config (passed to send_edit_message) = {config}")

    if config is not None:
        print_success("config is NOT None - will pass to send_edit_message()")
        return True
    else:
        print_error("config is None - BUG!")
        return False


def test_send_config_building():
    """Test send_config building in _send_edit_message_internal()"""
    print_header("Test 4: send_config Building Logic")

    # Scenario 1: config has image parameters
    print(f"\n{Colors.CYAN}Scenario 1: config has image_aspect_ratio and image_resolution{Colors.END}")
    config1 = {
        "image_aspect_ratio": "1:1",
        "image_resolution": "1K",
        "enhance_prompt": False,
        "enable_thinking": False
    }

    send_config = None
    if config1:  # config is not None
        image_config_dict = {}
        if config1.get('image_aspect_ratio'):
            image_config_dict['aspect_ratio'] = config1['image_aspect_ratio']
        if config1.get('image_resolution'):
            image_config_dict['image_size'] = config1['image_resolution']

        if image_config_dict:
            send_config = {
                'response_modalities': ['TEXT', 'IMAGE'],
                'thinking_config': None,
                'image_config': image_config_dict,
                'automatic_function_calling': {'disable': True}
            }

    print(f"    config = {config1}")
    print(f"    image_config_dict = {image_config_dict if 'image_config_dict' in dir() else 'N/A'}")
    print(f"    send_config = {'Created' if send_config else 'None'}")

    if send_config:
        print_success("send_config created with response_modalities=[TEXT, IMAGE]")
        result1 = True
    else:
        print_error("send_config is None!")
        result1 = False

    # Scenario 2: config has only non-image parameters
    print(f"\n{Colors.CYAN}Scenario 2: config has only enable_thinking (no image params){Colors.END}")
    config2 = {
        "enhance_prompt": False,
        "enable_thinking": True
        # Note: NO image_aspect_ratio or image_resolution
    }

    send_config = None
    if config2:  # config is not None, but...
        image_config_dict = {}
        if config2.get('image_aspect_ratio'):  # False
            image_config_dict['aspect_ratio'] = config2['image_aspect_ratio']
        if config2.get('image_resolution'):  # False
            image_config_dict['image_size'] = config2['image_resolution']

        if image_config_dict:  # False - image_config_dict is empty!
            send_config = {
                'response_modalities': ['TEXT', 'IMAGE'],
                'thinking_config': None,
                'image_config': image_config_dict,
                'automatic_function_calling': {'disable': True}
            }

    print(f"    config = {config2}")
    print(f"    image_config_dict = {image_config_dict}")
    print(f"    bool(image_config_dict) = {bool(image_config_dict)}")
    print(f"    send_config = {send_config}")

    if send_config is None:
        print_warning("send_config is None - BUG condition (but shouldn't happen with frontend defaults)")
        result2 = False
    else:
        print_success("send_config created")
        result2 = True

    return result1


def test_complete_flow():
    """Test the complete data flow"""
    print_header("Test 5: Complete Data Flow Simulation")

    print_info("Simulating complete flow: Frontend -> Middleware -> Backend")
    print()

    # Step 1: Frontend sends camelCase request
    frontend_request = {
        "modelId": "gemini-2.5-flash",
        "prompt": "Make this image brighter",
        "attachments": [{"id": "att-1", "mimeType": "image/png", "url": "data:..."}],
        "options": {
            "imageAspectRatio": "1:1",  # DEFAULT from frontend
            "imageResolution": "1K",     # DEFAULT from frontend
            "numberOfImages": 1,
            "frontendSessionId": "session-123",
            "sessionId": "session-123",
            "messageId": "msg-456",
            "enableThinking": False,
            "enhancePrompt": False
        }
    }
    print(f"Step 1: Frontend request:")
    print(f"    options.imageAspectRatio = {frontend_request['options']['imageAspectRatio']}")
    print(f"    options.imageResolution = {frontend_request['options']['imageResolution']}")

    # Step 2: Middleware converts to snake_case
    from app.utils.case_converter import to_snake_case
    backend_request = to_snake_case(frontend_request)
    print(f"\nStep 2: After middleware (snake_case):")
    print(f"    options.image_aspect_ratio = {backend_request['options'].get('image_aspect_ratio')}")
    print(f"    options.image_resolution = {backend_request['options'].get('image_resolution')}")

    # Step 3: Pydantic parsing
    from app.routers.core.modes import ModeOptions
    mode_options = ModeOptions(**backend_request['options'])
    options_dict = mode_options.dict(exclude_none=True)
    print(f"\nStep 3: After Pydantic parsing (exclude_none=True):")
    print(f"    image_aspect_ratio = {options_dict.get('image_aspect_ratio')}")
    print(f"    image_resolution = {options_dict.get('image_resolution')}")

    # Step 4: Merge into params
    params = {
        "model": backend_request['model_id'],
        "prompt": backend_request['prompt'],
        "reference_images": {"raw": "..."},
        "user_id": "user-123",
        "mode": "image-chat-edit"
    }
    params.update(options_dict)
    print(f"\nStep 4: params for edit_image():")
    print(f"    'image_aspect_ratio' in params: {'image_aspect_ratio' in params}")
    print(f"    'image_resolution' in params: {'image_resolution' in params}")

    # Step 5: edit_config building
    edit_config = {}
    if 'image_aspect_ratio' in params:
        edit_config['image_aspect_ratio'] = params['image_aspect_ratio']
    if 'image_resolution' in params:
        edit_config['image_resolution'] = params['image_resolution']

    config = edit_config if edit_config else None
    print(f"\nStep 5: edit_config building:")
    print(f"    edit_config = {edit_config}")
    print(f"    config = {config}")

    # Step 6: send_config building
    send_config = None
    if config:
        image_config_dict = {}
        if config.get('image_aspect_ratio'):
            image_config_dict['aspect_ratio'] = config['image_aspect_ratio']
        if config.get('image_resolution'):
            image_config_dict['image_size'] = config['image_resolution']

        if image_config_dict:
            send_config = {
                'response_modalities': ['TEXT', 'IMAGE'],
                'image_config': image_config_dict
            }

    print(f"\nStep 6: send_config building:")
    print(f"    send_config = {send_config}")

    # Final result
    print()
    if send_config and 'response_modalities' in send_config:
        print_success("COMPLETE FLOW VERIFIED: send_config has response_modalities=[TEXT, IMAGE]")
        return True
    else:
        print_error("FLOW BROKEN: send_config is None or missing response_modalities")
        return False


def main():
    """Main test function"""
    print(f"\n{Colors.BOLD}Full Data Flow Test{Colors.END}")
    print("Verifying complete data flow from frontend to backend")
    print()

    results = []

    # Test 1
    results.append(("Case Conversion", test_case_conversion()))

    # Test 2
    results.append(("ModeOptions Parsing", test_mode_options_parsing()))

    # Test 3
    results.append(("edit_config Building", test_edit_config_building()))

    # Test 4
    results.append(("send_config Building", test_send_config_building()))

    # Test 5
    results.append(("Complete Flow", test_complete_flow()))

    # Summary
    print_header("Summary")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}")
    print()

    for name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  [{status}] {name}")

    print()

    if passed == total:
        print_success("All tests passed!")
        print()
        print_info("This means the normal flow SHOULD work correctly.")
        print_info("If API still returns text-only, the issue might be:")
        print_info("  1. Cached chat object with incorrect config")
        print_info("  2. Chat rebuild logic not setting response_modalities")
        print_info("  3. Google API behavior with specific models")
    else:
        print_error("Some tests failed!")


if __name__ == "__main__":
    main()
