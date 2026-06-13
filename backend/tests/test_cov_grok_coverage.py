"""Thorough unit tests for Grok chat_handler and image_editor.

Covers request building, param mapping, response parsing, multimodal content
normalization, usage normalization, streaming, and error handling. External
boundaries (the OpenAI-compatible AsyncOpenAI client and httpx) are mocked;
the modules' own logic is exercised directly.
"""
from __future__ import annotations

import base64
import logging
from types import SimpleNamespace
from typing import Any, Dict, List

import httpx
import pytest

from app.services.grok.chat_handler import (
    CHAT_ALLOWED_OPTION_KEYS,
    ChatHandler,
    _filter_allowed_kwargs,
)
from app.services.grok.image_editor import (
    ALLOWED_SIZES,
    ASPECT_RATIO_TO_SIZE,
    DEFAULT_MODEL,
    ImageEditor,
)
from app.services.grok.model_manager import ModelManager

# ---------------------------------------------------------------------------
# Fakes / helpers for the AsyncOpenAI client boundary
# ---------------------------------------------------------------------------

class _FakeCompletions:
    """Captures create() kwargs and returns a preset response or stream."""

    def __init__(self, response: Any = None, stream_chunks: Any = None, error: Exception = None):
        self._response = response
        self._stream_chunks = stream_chunks
        self._error = error
        self.calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if kwargs.get("stream"):
            return _async_iter(self._stream_chunks or [])
        return self._response


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeClient:
    def __init__(self, completions: _FakeCompletions):
        self.chat = _FakeChat(completions)


def _make_handler(response=None, stream_chunks=None, error=None):
    completions = _FakeCompletions(response=response, stream_chunks=stream_chunks, error=error)
    handler = ChatHandler(_FakeClient(completions))
    return handler, completions


def _async_iter(items):
    async def gen():
        for it in items:
            yield it
    return gen()


def _completion(content="hello", finish_reason="stop", usage=None, model="grok-3",
                reasoning_content=None, reasoning=None):
    message_kwargs: Dict[str, Any] = {"content": content}
    if reasoning_content is not None:
        message_kwargs["reasoning_content"] = reasoning_content
    if reasoning is not None:
        message_kwargs["reasoning"] = reasoning
    message = SimpleNamespace(**message_kwargs)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _stream_chunk(content=None, reasoning_content=None, reasoning=None,
                  finish_reason=None, usage=None, no_choices=False):
    delta_kwargs: Dict[str, Any] = {"content": content}
    if reasoning_content is not None:
        delta_kwargs["reasoning_content"] = reasoning_content
    if reasoning is not None:
        delta_kwargs["reasoning"] = reasoning
    delta = SimpleNamespace(**delta_kwargs)
    if no_choices:
        return SimpleNamespace(usage=usage, choices=[])
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(usage=usage, choices=[choice])


# ===========================================================================
# _filter_allowed_kwargs
# ===========================================================================

def test_filter_allowed_kwargs_keeps_only_allowed():
    raw = {
        "temperature": 0.5,
        "max_tokens": 100,
        "enable_thinking": True,   # not allowed
        "unknown": "x",            # not allowed
        "tool_choice": "auto",
    }
    out = _filter_allowed_kwargs(raw)
    assert out == {"temperature": 0.5, "max_tokens": 100, "tool_choice": "auto"}
    assert "enable_thinking" not in out
    assert "unknown" not in out


def test_filter_allowed_kwargs_empty():
    assert _filter_allowed_kwargs({}) == {}


def test_allowed_option_keys_contract():
    for key in ("temperature", "max_tokens", "tools", "tool_choice", "reasoning_effort"):
        assert key in CHAT_ALLOWED_OPTION_KEYS


# ===========================================================================
# _normalize_usage
# ===========================================================================

def test_normalize_usage_none_returns_zeros():
    assert ChatHandler._normalize_usage(None) == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def test_normalize_usage_dict_standard_keys():
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert ChatHandler._normalize_usage(usage) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_normalize_usage_dict_input_output_aliases():
    usage = {"input_tokens": 7, "output_tokens": 3}
    out = ChatHandler._normalize_usage(usage)
    assert out == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}


def test_normalize_usage_object_attributes():
    usage = SimpleNamespace(prompt_tokens=20, completion_tokens=8, total_tokens=28)
    assert ChatHandler._normalize_usage(usage) == {
        "prompt_tokens": 20,
        "completion_tokens": 8,
        "total_tokens": 28,
    }


def test_normalize_usage_object_alias_attributes_and_derived_total():
    usage = SimpleNamespace(input_tokens=4, output_tokens=6)
    out = ChatHandler._normalize_usage(usage)
    assert out == {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10}


def test_normalize_usage_partial_none_values_coerced_to_zero():
    usage = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    out = ChatHandler._normalize_usage(usage)
    assert out == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


# ===========================================================================
# _prepare_messages / multimodal normalization
# ===========================================================================

def test_prepare_messages_skips_non_dict_entries():
    out = ChatHandler._prepare_messages([{"role": "user", "content": "hi"}, "garbage", 42])
    assert out == [{"role": "user", "content": "hi"}]


def test_prepare_messages_passthrough_without_attachments():
    msg = {"role": "user", "content": "plain"}
    out = ChatHandler._prepare_messages([msg])
    assert out == [{"role": "user", "content": "plain"}]
    assert "attachments" not in msg


def test_prepare_messages_with_image_attachment_builds_multimodal():
    msg = {
        "role": "user",
        "content": "describe",
        "attachments": [{"url": "https://x/img.png", "mime_type": "image/png"}],
    }
    out = ChatHandler._prepare_messages([msg])
    content = out[0]["content"]
    assert isinstance(content, list)
    assert {"type": "text", "text": "describe"} in content
    assert {"type": "image_url", "image_url": {"url": "https://x/img.png"}} in content
    assert "attachments" not in out[0]


def test_prepare_messages_empty_attachment_list_is_passthrough():
    msg = {"role": "user", "content": "hi", "attachments": []}
    out = ChatHandler._prepare_messages([msg])
    assert out[0]["content"] == "hi"


def test_normalize_multimodal_no_attachments_returns_content_unchanged():
    sentinel = "original text"
    assert ChatHandler._normalize_multimodal_content(sentinel, []) == sentinel


def test_normalize_multimodal_string_content_with_image():
    parts = ChatHandler._normalize_multimodal_content(
        "look", [{"url": "data:image/png;base64,AAA"}]
    )
    assert parts[0] == {"type": "text", "text": "look"}
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}


def test_normalize_multimodal_list_content_text_and_image_items():
    content = [
        {"type": "text", "text": "  hello  "},
        {"type": "image_url", "image_url": {"url": "https://x/a.jpg"}},
        {"type": "text", "text": "   "},  # whitespace-only dropped
    ]
    parts = ChatHandler._normalize_multimodal_content(
        content, [{"url": "https://y/b.png", "mime_type": "image/png"}]
    )
    assert {"type": "text", "text": "hello"} in parts
    assert {"type": "image_url", "image_url": {"url": "https://x/a.jpg"}} in parts
    assert {"type": "image_url", "image_url": {"url": "https://y/b.png"}} in parts
    assert not any(p.get("text") == "" for p in parts if p["type"] == "text")


def test_normalize_multimodal_list_content_non_dict_item():
    parts = ChatHandler._normalize_multimodal_content(
        ["raw string item"], [{"url": "https://y/b.png", "mime_type": "image/png"}]
    )
    assert {"type": "text", "text": "raw string item"} in parts


def test_normalize_multimodal_non_image_attachment_skipped():
    parts = ChatHandler._normalize_multimodal_content(
        "text", [{"url": "https://x/doc.pdf", "mime_type": "application/pdf"}]
    )
    assert all(p["type"] != "image_url" for p in parts)


def test_normalize_multimodal_empty_content_and_empty_parts_returns_str():
    out = ChatHandler._normalize_multimodal_content(
        "", [{"mime_type": "application/pdf"}]
    )
    assert out == ""


def test_resolve_attachment_url_priority_and_fallback():
    assert ChatHandler._resolve_attachment_url({"url": "  u  "}) == "u"
    assert ChatHandler._resolve_attachment_url({"temp_url": "t"}) == "t"
    assert ChatHandler._resolve_attachment_url({"base64Data": "b64"}) == "b64"
    assert ChatHandler._resolve_attachment_url({}) == ""
    assert ChatHandler._resolve_attachment_url("not a dict") == ""


def test_is_image_attachment_by_mime_and_extension_and_data_uri():
    assert ChatHandler._is_image_attachment({"mime_type": "image/png"}, "whatever")
    assert ChatHandler._is_image_attachment({"mimeType": "image/jpeg"}, "x")
    assert ChatHandler._is_image_attachment({}, "data:image/gif;base64,AAA")
    assert ChatHandler._is_image_attachment({}, "https://x/photo.JPG?token=1")
    assert ChatHandler._is_image_attachment({}, "https://x/clip.png#frag")
    assert not ChatHandler._is_image_attachment({"mime_type": "text/plain"}, "https://x/file.txt")
    assert not ChatHandler._is_image_attachment({}, "https://x/file.bin")


# ===========================================================================
# _build_error_done_chunk
# ===========================================================================

def test_build_error_done_chunk_shape():
    chunk = ChatHandler._build_error_done_chunk()
    assert chunk["chunk_type"] == "done"
    assert chunk["finish_reason"] == "error"
    assert chunk["prompt_tokens"] == 0
    assert chunk["total_tokens"] == 0


# ===========================================================================
# chat() — non-streaming
# ===========================================================================

async def test_chat_builds_request_and_parses_response():
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=4, total_tokens=15)
    handler, completions = _make_handler(
        response=_completion(content="hi there", finish_reason="stop", usage=usage, model="grok-3")
    )
    result = await handler.chat(
        [{"role": "user", "content": "hello"}],
        model="grok-3",
        temperature=0.7,
        unsupported_key="dropped",
    )
    assert result["content"] == "hi there"
    assert result["role"] == "assistant"
    assert result["model"] == "grok-3"
    assert result["finish_reason"] == "stop"
    assert result["usage"]["total_tokens"] == 15
    assert "reasoning_content" not in result

    call = completions.calls[0]
    assert call["model"] == "grok-3"
    assert call["temperature"] == 0.7
    assert "unsupported_key" not in call
    assert call["messages"] == [{"role": "user", "content": "hello"}]


async def test_chat_enable_thinking_maps_to_reasoning_effort_high():
    handler, completions = _make_handler(response=_completion())
    await handler.chat([{"role": "user", "content": "q"}], model="grok-3", enable_thinking=True)
    assert completions.calls[0]["reasoning_effort"] == "high"


async def test_chat_includes_reasoning_content_when_present():
    handler, _ = _make_handler(
        response=_completion(content="ans", reasoning_content="because reasons")
    )
    result = await handler.chat([{"role": "user", "content": "q"}], model="grok-3")
    assert result["reasoning_content"] == "because reasons"


async def test_chat_reasoning_attribute_fallback():
    handler, _ = _make_handler(response=_completion(content="ans", reasoning="alt-reasoning"))
    result = await handler.chat([{"role": "user", "content": "q"}], model="grok-3")
    assert result["reasoning_content"] == "alt-reasoning"


async def test_chat_none_content_and_none_finish_reason_defaults():
    handler, _ = _make_handler(response=_completion(content=None, finish_reason=None, usage=None))
    result = await handler.chat([{"role": "user", "content": "q"}], model="grok-3")
    assert result["content"] == ""
    assert result["finish_reason"] == "stop"
    assert result["usage"]["total_tokens"] == 0


async def test_chat_propagates_client_error(caplog):
    error_text = "boom with secret-token"
    handler, _ = _make_handler(error=RuntimeError(error_text))
    with pytest.raises(RuntimeError, match="boom"):
        with caplog.at_level(logging.ERROR, logger="app.services.grok.chat_handler"):
            await handler.chat([{"role": "user", "content": "q"}], model="grok-3")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# stream_chat()
# ===========================================================================

async def _collect(agen):
    return [c async for c in agen]


async def test_stream_chat_yields_content_and_done_with_usage():
    usage = SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5)
    chunks = [
        _stream_chunk(content="Hel"),
        _stream_chunk(content="lo"),
        _stream_chunk(content=None, finish_reason="stop", usage=usage),
    ]
    handler, completions = _make_handler(stream_chunks=chunks)
    out = await _collect(handler.stream_chat([{"role": "user", "content": "hi"}], model="grok-3"))

    content_chunks = [c for c in out if c["chunk_type"] == "content"]
    assert "".join(c["content"] for c in content_chunks) == "Hello"

    done = out[-1]
    assert done["chunk_type"] == "done"
    assert done["finish_reason"] == "stop"
    assert done["total_tokens"] == 5
    assert done["prompt_tokens"] == 3

    call = completions.calls[0]
    assert call["stream"] is True
    assert call["stream_options"] == {"include_usage": True}


async def test_stream_chat_emits_reasoning_chunk():
    chunks = [
        _stream_chunk(reasoning_content="thinking..."),
        _stream_chunk(content="done"),
        _stream_chunk(content=None, finish_reason="stop"),
    ]
    handler, _ = _make_handler(stream_chunks=chunks)
    out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], model="grok-3"))
    reasoning = [c for c in out if c["chunk_type"] == "reasoning"]
    assert reasoning and reasoning[0]["content"] == "thinking..."


async def test_stream_chat_reasoning_attribute_fallback():
    chunks = [
        _stream_chunk(reasoning="alt-think"),
        _stream_chunk(content=None, finish_reason="stop"),
    ]
    handler, _ = _make_handler(stream_chunks=chunks)
    out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], model="grok-3"))
    reasoning = [c for c in out if c["chunk_type"] == "reasoning"]
    assert reasoning and reasoning[0]["content"] == "alt-think"


async def test_stream_chat_skips_chunks_without_choices():
    chunks = [
        _stream_chunk(no_choices=True),
        _stream_chunk(content="ok"),
        _stream_chunk(content=None, finish_reason="stop"),
    ]
    handler, _ = _make_handler(stream_chunks=chunks)
    out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], model="grok-3"))
    content = [c for c in out if c["chunk_type"] == "content"]
    assert content and content[0]["content"] == "ok"


async def test_stream_chat_no_usage_defaults_to_zeros():
    chunks = [
        _stream_chunk(content="hi"),
        _stream_chunk(content=None, finish_reason="length"),
    ]
    handler, _ = _make_handler(stream_chunks=chunks)
    out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], model="grok-3"))
    done = out[-1]
    assert done["chunk_type"] == "done"
    assert done["finish_reason"] == "length"
    assert done["total_tokens"] == 0
    assert done["prompt_tokens"] == 0


async def test_stream_chat_enable_thinking_maps_reasoning_effort():
    chunks = [_stream_chunk(content=None, finish_reason="stop")]
    handler, completions = _make_handler(stream_chunks=chunks)
    await _collect(
        handler.stream_chat([{"role": "user", "content": "x"}], model="grok-3", enable_thinking=True)
    )
    assert completions.calls[0]["reasoning_effort"] == "high"


async def test_stream_chat_error_yields_error_then_done(caplog):
    error_text = "stream failed with secret-token"
    handler, _ = _make_handler(error=ValueError(error_text))
    with caplog.at_level(logging.ERROR, logger="app.services.grok.chat_handler"):
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], model="grok-3"))

    assert out[0]["chunk_type"] == "error"
    assert out[0]["error"] == "Grok stream chat failed"
    assert out[1]["chunk_type"] == "done"
    assert out[1]["finish_reason"] == "error"

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# ImageEditor — param mapping
# ===========================================================================

def _editor():
    return ImageEditor(api_key="key-123", base_url="http://localhost:8000/v1/")


def test_image_editor_strips_trailing_slash():
    ed = ImageEditor(api_key="k", base_url="http://h/v1///")
    assert ed.base_url == "http://h/v1"


def test_resolve_size_explicit_allowed():
    ed = _editor()
    assert ed._resolve_size({"size": "1280x720"}) == "1280x720"
    assert ed._resolve_size({"image_resolution": "720x1280"}) == "720x1280"


def test_resolve_size_invalid_falls_through_to_aspect_ratio():
    ed = _editor()
    assert ed._resolve_size({"size": "999x999", "aspect_ratio": "16:9"}) == "1280x720"
    assert ed._resolve_size({"image_aspect_ratio": "9:16"}) == "720x1280"


def test_resolve_size_default():
    ed = _editor()
    assert ed._resolve_size({}) == "1024x1024"
    assert ed._resolve_size({"aspect_ratio": "unknown"}) == "1024x1024"


def test_aspect_ratio_table_maps_to_allowed_sizes():
    for size in ASPECT_RATIO_TO_SIZE.values():
        assert size in ALLOWED_SIZES


def test_resolve_n_clamping_and_aliases():
    ed = _editor()
    assert ed._resolve_n({"n": 3}) == 3
    assert ed._resolve_n({"number_of_images": "5"}) == 5
    assert ed._resolve_n({"n": 0}) == 1      # clamped up to 1
    assert ed._resolve_n({"n": 50}) == 10    # clamped down to 10
    assert ed._resolve_n({}) == 1            # default
    assert ed._resolve_n({"n": "abc"}) == 1  # invalid -> default


def test_extract_reference_images_variants():
    ed = _editor()
    assert ed._extract_reference_images({}) == []
    assert ed._extract_reference_images({"reference_images": ["a", "b"]}) == ["a", "b"]
    assert ed._extract_reference_images({"reference_images": {"raw": ["x"]}}) == ["x"]
    assert ed._extract_reference_images({"reference_images": {"raw": "single"}}) == ["single"]
    assert ed._extract_reference_images({"reference_images": {"raw": None}}) == []
    assert ed._extract_reference_images({"reference_images": "lone"}) == ["lone"]


# ===========================================================================
# ImageEditor._load_image_bytes
# ===========================================================================

async def test_load_image_bytes_from_data_uri():
    ed = _editor()
    raw = b"PNGDATA"
    data_uri = "data:image/png;base64," + base64.b64encode(raw).decode()
    assert await ed._load_image_bytes(data_uri) == raw


async def test_load_image_bytes_from_bytes_passthrough():
    ed = _editor()
    assert await ed._load_image_bytes(b"abc") == b"abc"


async def test_load_image_bytes_from_http(monkeypatch):
    ed = _editor()

    # CANON-011: _load_image_bytes now runs the SSRF guard first; this test pins
    # the guarded download mechanics, so pass the (non-resolvable) test host through.
    async def _passthrough(url):
        return url

    monkeypatch.setattr(
        "app.services.grok.image_editor.validate_outbound_http_url_async", _passthrough
    )

    class _Resp:
        content = b"downloaded"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    calls = []

    async def _guarded_get(client, url, *, max_redirects):
        assert isinstance(client, _Client)
        calls.append((url, max_redirects))
        return _Resp(), url

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setattr("app.services.grok.image_editor.get_with_redirect_guard", _guarded_get)
    assert await ed._load_image_bytes("https://x/img.png") == b"downloaded"
    assert calls == [("https://x/img.png", 5)]


async def test_load_image_bytes_unsupported_type_raises():
    ed = _editor()
    with pytest.raises(ValueError, match="Unsupported image source type"):
        await ed._load_image_bytes(12345)


async def test_load_image_bytes_unsupported_string_scheme_raises():
    ed = _editor()
    with pytest.raises(ValueError, match="Unsupported image source type"):
        await ed._load_image_bytes("ftp://x/y.png")


# ===========================================================================
# ImageEditor.edit_image
# ===========================================================================

class _FakePostResponse:
    def __init__(self, json_data, status_code=200, text="error-body"):
        self._json = json_data
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "bad", request=httpx.Request("POST", "http://x"), response=self
            )

    def json(self):
        return self._json


class _FakePostClient:
    """Builds an httpx.AsyncClient replacement; captures post() args."""

    last_call: Dict[str, Any] = {}

    def __init__(self, response: _FakePostResponse):
        self._response = response

    def make(self):
        outer = self

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, data=None, files=None, headers=None):
                _FakePostClient.last_call = {
                    "url": url,
                    "data": data,
                    "files": files,
                    "headers": headers,
                }
                return outer._response

        return _Client


def _patch_post(monkeypatch, response: _FakePostResponse):
    fake = _FakePostClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", fake.make())


async def _patch_load_bytes(monkeypatch, value=b"imgbytes"):
    async def _fake_load(self, source):
        return value
    monkeypatch.setattr(ImageEditor, "_load_image_bytes", _fake_load)


async def test_edit_image_happy_path_builds_form_and_parses_url(monkeypatch):
    ed = _editor()
    await _patch_load_bytes(monkeypatch)
    resp = _FakePostResponse({"data": [{"url": "https://out/1.png", "revised_prompt": "rp"}]})
    _patch_post(monkeypatch, resp)

    results = await ed.edit_image(
        prompt="make it blue",
        reference_images=["https://in/a.png"],
        size="1280x720",
        n=2,
    )
    assert results == [
        {"url": "https://out/1.png", "mime_type": "image/png", "revised_prompt": "rp"}
    ]

    call = _FakePostClient.last_call
    assert call["url"] == "http://localhost:8000/v1/images/edits"
    assert call["headers"]["Authorization"] == "Bearer key-123"
    assert call["data"]["prompt"] == "make it blue"
    assert call["data"]["model"] == DEFAULT_MODEL
    assert call["data"]["n"] == "2"
    assert call["data"]["size"] == "1280x720"
    assert call["data"]["response_format"] == "url"
    assert len(call["files"]) == 1
    assert call["files"][0][0] == "image"


async def test_edit_image_parses_b64_json_into_data_uri(monkeypatch):
    ed = _editor()
    await _patch_load_bytes(monkeypatch)
    resp = _FakePostResponse({"data": [{"b64_json": "QUJD"}]})
    _patch_post(monkeypatch, resp)

    results = await ed.edit_image(prompt="p", reference_images=["https://in/a.png"])
    assert results[0]["url"] == "data:image/png;base64,QUJD"
    assert results[0]["revised_prompt"] == ""


async def test_edit_image_skips_items_without_image(monkeypatch):
    ed = _editor()
    await _patch_load_bytes(monkeypatch)
    resp = _FakePostResponse({"data": [{"nothing": 1}, {"url": "https://out/ok.png"}]})
    _patch_post(monkeypatch, resp)

    results = await ed.edit_image(prompt="p", reference_images=["https://in/a.png"])
    assert len(results) == 1
    assert results[0]["url"] == "https://out/ok.png"


async def test_edit_image_no_references_raises_value_error():
    ed = _editor()
    with pytest.raises(ValueError, match="At least one reference image"):
        await ed.edit_image(prompt="p")


async def test_edit_image_reference_without_url_is_skipped():
    ed = _editor()
    with pytest.raises(ValueError, match="At least one reference image"):
        await ed.edit_image(prompt="p", reference_images=[{"caption": "no url here"}])


async def test_edit_image_load_failure_skips_then_raises(monkeypatch):
    ed = _editor()

    async def _boom(self, source):
        raise RuntimeError("cannot fetch")

    monkeypatch.setattr(ImageEditor, "_load_image_bytes", _boom)
    with pytest.raises(ValueError, match="At least one reference image"):
        await ed.edit_image(prompt="p", reference_images=["https://in/a.png"])


async def test_edit_image_dict_reference_url_keys(monkeypatch):
    ed = _editor()
    captured = {}

    async def _fake_load(self, source):
        captured["source"] = source
        return b"bytes"

    monkeypatch.setattr(ImageEditor, "_load_image_bytes", _fake_load)
    resp = _FakePostResponse({"data": [{"url": "https://out/x.png"}]})
    _patch_post(monkeypatch, resp)

    await ed.edit_image(prompt="p", reference_images=[{"tempUrl": "https://in/from-temp.png"}])
    assert captured["source"] == "https://in/from-temp.png"


async def test_edit_image_empty_data_raises_runtime_error(monkeypatch):
    ed = _editor()
    await _patch_load_bytes(monkeypatch)
    resp = _FakePostResponse({"data": []})
    _patch_post(monkeypatch, resp)

    with pytest.raises(RuntimeError, match="did not contain a usable image"):
        await ed.edit_image(prompt="p", reference_images=["https://in/a.png"])


async def test_edit_image_http_status_error_propagates(monkeypatch, caplog):
    ed = _editor()
    await _patch_load_bytes(monkeypatch)
    response_text = "provider response leaked secret-token"
    resp = _FakePostResponse({"data": []}, status_code=500, text=response_text)
    _patch_post(monkeypatch, resp)

    with caplog.at_level(logging.ERROR, logger="app.services.grok.image_editor"):
        with pytest.raises(httpx.HTTPStatusError):
            await ed.edit_image(prompt="p", reference_images=["https://in/a.png"])

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted provider_error; length={len(response_text)}>" in log_text
    assert "secret-token" not in log_text
    assert response_text not in log_text
    assert all(record.exc_info is None for record in caplog.records)


async def test_edit_image_limits_references_to_16(monkeypatch):
    ed = _editor()
    await _patch_load_bytes(monkeypatch)
    resp = _FakePostResponse({"data": [{"url": "https://out/x.png"}]})
    _patch_post(monkeypatch, resp)

    refs = [f"https://in/{i}.png" for i in range(30)]
    await ed.edit_image(prompt="p", reference_images=refs)
    assert len(_FakePostClient.last_call["files"]) == 16


# ===========================================================================
# ModelManager
# ===========================================================================

class _FakeModelsResponse:
    def __init__(self, json_data=None, status_code=200, text="models-error"):
        self._json = json_data if json_data is not None else {"data": []}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "bad models response",
                request=httpx.Request("GET", "https://grok.example.test/v1/models"),
                response=self,
            )

    def json(self):
        return self._json


class _FakeModelsClient:
    def __init__(self, response: _FakeModelsResponse):
        self._response = response

    def make(self):
        outer = self

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None):
                _FakePostClient.last_call = {"url": url, "headers": headers}
                return outer._response

        return _Client


def _patch_model_get(monkeypatch, response: _FakeModelsResponse):
    fake = _FakeModelsClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", fake.make())


async def test_model_manager_http_error_logs_response_summary(monkeypatch, caplog):
    response_text = "provider models response leaked secret-token"
    _patch_model_get(monkeypatch, _FakeModelsResponse(status_code=502, text=response_text))
    manager = ModelManager(api_key="key-123", base_url="https://grok.example.test/v1")

    with caplog.at_level(logging.ERROR, logger="app.services.grok.model_manager"):
        with pytest.raises(httpx.HTTPStatusError):
            await manager.get_available_models()

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted provider_error; length={len(response_text)}>" in log_text
    assert response_text not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)
