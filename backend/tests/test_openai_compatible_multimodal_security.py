import base64

import pytest

from app.services.common import openai_compatible_multimodal as mm
from app.services.grok.chat_handler import ChatHandler as GrokChatHandler
from app.services.openai.chat_handler import ChatHandler as OpenAIChatHandler


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "/etc/passwd",
        r"C:\Users\secret\image.png",
        "http://127.0.0.1:8000/private.png",
        "http://127.1/private.png",
        "http://localhost/private.png",
        "http://metadata.google.internal/latest/meta-data.png",
        "http://100.100.100.200/latest/meta-data.png",
    ],
)
def test_multimodal_attachments_drop_local_and_private_image_refs(handler_cls, url):
    parts = handler_cls._normalize_multimodal_content(
        "describe",
        [{"url": url, "mime_type": "image/png"}],
    )

    assert parts == [{"type": "text", "text": "describe"}]


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_list_content_drops_unsafe_image_url(handler_cls):
    parts = handler_cls._normalize_multimodal_content(
        [
            {"type": "text", "text": "look"},
            {"type": "image_url", "image_url": {"url": "http://169.254.169.254/a.png"}},
        ],
        [{"url": "https://cdn.example.com/safe.png", "mime_type": "image/png"}],
    )

    assert {"type": "text", "text": "look"} in parts
    assert {
        "type": "image_url",
        "image_url": {"url": "https://cdn.example.com/safe.png"},
    } in parts
    assert all("169.254.169.254" not in str(part) for part in parts)


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_list_content_without_attachments_still_drops_unsafe_image_url(handler_cls):
    parts = handler_cls._normalize_multimodal_content(
        [
            {"type": "text", "text": "look"},
            {"type": "image_url", "image_url": {"url": "file:///etc/passwd"}},
        ],
        [],
    )

    assert parts == [{"type": "text", "text": "look"}]


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_list_content_keeps_safe_image_url_without_extension(handler_cls):
    url = "https://cdn.example.com/render?id=123"

    parts = handler_cls._normalize_multimodal_content(
        [{"type": "image_url", "image_url": {"url": url}}],
        [{"url": "https://cdn.example.com/safe.png", "mime_type": "image/png"}],
    )

    assert {"type": "image_url", "image_url": {"url": url}} in parts


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_list_content_without_attachments_keeps_safe_image_url(handler_cls):
    url = "https://cdn.example.com/render?id=123"

    parts = handler_cls._normalize_multimodal_content(
        [{"type": "image_url", "image_url": {"url": url}}],
        [],
    )

    assert parts == [{"type": "image_url", "image_url": {"url": url}}]


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_raw_base64_attachment_is_wrapped_as_data_url(handler_cls):
    raw = base64.b64encode(b"image-bytes").decode("ascii")

    parts = handler_cls._normalize_multimodal_content(
        "describe",
        [{"base64Data": raw, "mimeType": "image/webp"}],
    )

    assert parts == [
        {"type": "text", "text": "describe"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/webp;base64,{raw}"},
        },
    ]


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_rejects_oversized_image_reference(handler_cls, monkeypatch):
    monkeypatch.setattr(mm, "MAX_IMAGE_REFERENCE_CHARS", 32)

    parts = handler_cls._normalize_multimodal_content(
        "describe",
        [{"url": "data:image/png;base64," + ("A" * 64)}],
    )

    assert parts == [{"type": "text", "text": "describe"}]


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
@pytest.mark.parametrize(
    "url",
    [
        "data:image/png;base64,not-valid!",
        "data:text/plain;base64,aGVsbG8=",
        "data:image/png,raw-bytes",
    ],
)
def test_multimodal_rejects_malformed_data_image_url(handler_cls, url):
    parts = handler_cls._normalize_multimodal_content(
        "describe",
        [{"url": url, "mime_type": "image/png"}],
    )

    assert parts == [{"type": "text", "text": "describe"}]


@pytest.mark.parametrize("handler_cls", [OpenAIChatHandler, GrokChatHandler])
def test_multimodal_normalizes_whitespace_in_data_image_url(handler_cls):
    parts = handler_cls._normalize_multimodal_content(
        "describe",
        [{"url": "data:image/PNG;base64,YW Jj ZA=="}],
    )

    assert parts == [
        {"type": "text", "text": "describe"},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,YWJjZA=="},
        },
    ]
