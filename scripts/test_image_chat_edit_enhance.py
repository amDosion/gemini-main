#!/usr/bin/env python
"""
Test script for two-stage enhanced prompt in image-chat-edit.

Usage:
  python scripts/test_image_chat_edit_enhance.py \
    --image "path/to/image.png" \
    --prompt "Make the sky more dramatic" \
    --model "gemini-3-pro-image-preview" \
    --session-id "test-session-001" \
    --message-id "msg-001"

Env:
  API_BASE_URL (default: http://localhost:8000)
  AUTH_TOKEN   (optional, bearer token)
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
from urllib import request


def build_data_url(image_path: str) -> str:
    mime, _ = mimetypes.guess_type(image_path)
    if not mime:
        mime = "image/png"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}", mime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--prompt", required=True, help="Edit instruction")
    parser.add_argument("--model", default="gemini-3-pro-image-preview", help="Model ID")
    parser.add_argument("--session-id", default="test-session-001", help="Frontend session id")
    parser.add_argument("--message-id", default="msg-001", help="Message id")
    parser.add_argument("--provider", default="google", help="Provider id")
    parser.add_argument("--mode", default="image-chat-edit", help="Mode")
    args = parser.parse_args()

    data_url, mime = build_data_url(args.image)

    payload = {
        "modelId": args.model,
        "prompt": args.prompt,
        "attachments": [
            {
                "id": "att-local-001",
                "name": os.path.basename(args.image),
                "mimeType": mime,
                "base64Data": data_url,
            }
        ],
        "options": {
            "enhancePrompt": True,
            "enableThinking": True,
            "imageAspectRatio": "1:1",
            "imageResolution": "1K",
            "numberOfImages": 1,
            "sessionId": args.session_id,
            "message_id": args.message_id,
        },
    }

    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    url = f"{base_url}/api/modes/{args.provider}/{args.mode}"

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    token = os.environ.get("AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            print("Status:", resp.status)
            print(body)
    except Exception as e:
        print("Request failed:", e)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
