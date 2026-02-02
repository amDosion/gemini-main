#!/usr/bin/env python3
"""
Simple Config Flow Test - No Backend Required

Test the configuration logic without needing the backend to be running.
This script tests:
1. edit_config building logic
2. send_config building logic
3. Simulates what happens in different scenarios

Usage:
    cd backend
    python scripts/test_config_flow_simple.py
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


def simulate_edit_image_call(kwargs):
    """
    Simulate the edit_image() method's edit_config building logic
    Source: conversational_image_edit_service.py Line 1163-1181
    """
    # This is the exact logic from the source code
    edit_config = {}
    if 'image_aspect_ratio' in kwargs:
        edit_config['image_aspect_ratio'] = kwargs['image_aspect_ratio']
    if 'image_resolution' in kwargs:
        edit_config['image_resolution'] = kwargs['image_resolution']
    if 'enhance_prompt' in kwargs:
        edit_config['enhance_prompt'] = kwargs['enhance_prompt']
    if 'enhance_prompt_model' in kwargs:
        edit_config['enhance_prompt_model'] = kwargs['enhance_prompt_model']
    if 'enable_thinking' in kwargs:
        edit_config['enable_thinking'] = kwargs['enable_thinking']

    # This is the problematic line
    config = edit_config if edit_config else None

    return edit_config, config


def simulate_send_config_building(config, has_genai_types=True):
    """
    Simulate the _send_edit_message_internal() send_config building logic
    Source: conversational_image_edit_service.py Line 739-768
    """
    send_config = None

    # This is the exact logic from the source code
    if config and has_genai_types:
        image_config_dict = {}
        if config.get('image_aspect_ratio'):
            image_config_dict['aspect_ratio'] = config['image_aspect_ratio']
        if config.get('image_resolution'):
            image_config_dict['image_size'] = config['image_resolution']

        if image_config_dict:
            # send_config would be created
            send_config = {
                'response_modalities': ['TEXT', 'IMAGE'],
                'thinking_config': None,
                'image_config': image_config_dict,
                'automatic_function_calling': {'disable': True}
            }

    return send_config


def test_scenario(name, kwargs, expected_has_send_config):
    """Test a specific scenario"""
    print(f"\n{Colors.CYAN}Scenario: {name}{Colors.END}")
    print(f"  kwargs = {json.dumps(kwargs, indent=4)}")

    # Step 1: edit_config building
    edit_config, config = simulate_edit_image_call(kwargs)
    print(f"  edit_config = {edit_config}")
    print(f"  bool(edit_config) = {bool(edit_config)}")
    print(f"  config (passed to send_edit_message) = {config}")

    # Step 2: send_config building
    send_config = simulate_send_config_building(config)
    print(f"  send_config = {send_config}")

    # Check result
    has_send_config = send_config is not None
    if has_send_config == expected_has_send_config:
        if has_send_config:
            print_success(f"send_config is created (as expected)")
            print_success(f"response_modalities = {send_config.get('response_modalities')}")
        else:
            print_warning(f"send_config is None (as expected - BUG REPRODUCED)")
    else:
        print_error(f"Unexpected result! has_send_config={has_send_config}, expected={expected_has_send_config}")

    return has_send_config == expected_has_send_config


def main():
    """Main test function"""
    print(f"\n{Colors.BOLD}Simple Config Flow Test{Colors.END}")
    print("Testing the configuration logic that causes the image-only-text bug")
    print()

    results = []

    # Test 1: Normal case - with image parameters
    print_header("Test 1: Normal Case (with image parameters)")
    kwargs1 = {
        'frontend_session_id': 'test-session',
        'image_aspect_ratio': '1:1',
        'image_resolution': '4K'
    }
    results.append(test_scenario(
        "Frontend sends image_aspect_ratio and image_resolution",
        kwargs1,
        expected_has_send_config=True
    ))

    # Test 2: Bug case - without image parameters
    print_header("Test 2: BUG Case (without image parameters)")
    kwargs2 = {
        'frontend_session_id': 'test-session'
        # NOTE: No image_aspect_ratio or image_resolution!
    }
    results.append(test_scenario(
        "Frontend does NOT send image_aspect_ratio/image_resolution",
        kwargs2,
        expected_has_send_config=False  # This is the bug!
    ))

    # Test 3: Partial case - only aspect ratio
    print_header("Test 3: Partial Case (only aspect ratio)")
    kwargs3 = {
        'frontend_session_id': 'test-session',
        'image_aspect_ratio': '16:9'
        # No image_resolution
    }
    results.append(test_scenario(
        "Frontend sends only image_aspect_ratio",
        kwargs3,
        expected_has_send_config=True  # Should still work
    ))

    # Test 4: With other options but no image params
    print_header("Test 4: Other Options (no image params)")
    kwargs4 = {
        'frontend_session_id': 'test-session',
        'enhance_prompt': True,
        'enable_thinking': False
    }
    results.append(test_scenario(
        "Frontend sends other options but no image params",
        kwargs4,
        expected_has_send_config=False  # BUG - enhance_prompt doesn't help
    ))

    # Summary
    print_header("Summary")

    passed = sum(results)
    total = len(results)

    print(f"\n{Colors.BOLD}Results: {passed}/{total} scenarios behaved as expected{Colors.END}")
    print()

    print(f"{Colors.YELLOW}Key Findings:{Colors.END}")
    print()
    print("1. When kwargs has NO image_aspect_ratio AND NO image_resolution:")
    print("   - edit_config = {} (empty dict)")
    print("   - bool({}) = False")
    print("   - config = None (due to 'edit_config if edit_config else None')")
    print("   - send_config = None (due to 'if config and genai_types:')")
    print()
    print("2. When send_config = None:")
    print("   - chat.send_message(message) uses chat's default config")
    print("   - If default config doesn't have response_modalities=[TEXT, IMAGE]")
    print("   - API returns text only, no images!")
    print()
    print(f"{Colors.RED}This is the ROOT CAUSE of the bug described in{Colors.END}")
    print(f"{Colors.RED}IMAGE_EDIT_NO_IMAGE_ANALYSIS.md{Colors.END}")
    print()
    print(f"{Colors.GREEN}Recommended Fix:{Colors.END}")
    print("Modify _send_edit_message_internal() to ALWAYS create send_config")
    print("with response_modalities=[TEXT, IMAGE], regardless of whether")
    print("config contains image parameters or not.")


if __name__ == "__main__":
    main()
