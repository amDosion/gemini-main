#!/usr/bin/env python3
"""Quick API test to see error details"""

import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db
from app.models.db_models import User

# Get token
db = next(get_db())
user = db.query(User).filter(User.status == 'active').first()
token = user.access_token if user else None
db.close()

if not token:
    print("No token found")
    sys.exit(1)

print(f"Using token for: {user.email}")

# Sample base64 image (1x1 red pixel PNG)
SAMPLE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

# Test request
payload = {
    "modelId": "gemini-2.0-flash-exp-image-generation",
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
        # "imageAspectRatio": "1:1",  # Disabled - not supported by this model
        # "imageResolution": "1K",     # Disabled - not supported by this model
        "numberOfImages": 1,
        "enableThinking": False,
        "enhancePrompt": False,
        "frontendSessionId": f"quick-test-{int(__import__('time').time())}",
        "sessionId": f"quick-test-{int(__import__('time').time())}",
        "messageId": f"msg-test-{int(__import__('time').time())}"
    }
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

print(f"\nSending request to: http://localhost:8000/api/modes/google/image-chat-edit")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(
        "http://localhost:8000/api/modes/google/image-chat-edit",
        json=payload,
        headers=headers,
        timeout=30
    )

    print(f"\nStatus: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print(f"\nResponse body:")
    print(response.text[:2000] if len(response.text) > 2000 else response.text)

except Exception as e:
    print(f"Error: {e}")
