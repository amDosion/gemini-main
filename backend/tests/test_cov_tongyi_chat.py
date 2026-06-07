"""
Coverage tests for backend/app/services/tongyi/chat.py (QwenNativeProvider).

Strategy:
- Mock ONLY the DashScope SDK boundary (Generation.call / MultiModalConversation.call)
  and the dashscope module-level api_key assignment. Everything else is real SUT logic.
- Build fake SDK response objects that mimic the real GenerationResponse /
  MultiModalConversationResponse attribute surface (.status_code, .output, .usage,
  .code, .message) so request building, response parsing, streaming, and error
  mapping are exercised against genuine behavior.

Reference pattern: tests/test_cov_workflows_router.py et al. (mock external
SDK/network boundaries, never the system-under-test).
"""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tongyi import chat as chat_mod
from app.services.tongyi.chat import QwenNativeProvider, is_vision_model
from app.services.common.errors import (
    APIKeyError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError,
    OperationError,
)


# ============================================================
# Fake DashScope SDK response builders
# ============================================================

class _Usage:
    def __init__(self, input_tokens=10, output_tokens=20, total_tokens=None):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens if total_tokens is not None else (input_tokens + output_tokens)


class _Output:
    """Mimics Generation response .output: has .choices, .model, .search_info attrs."""

    def __init__(self, choices, model="qwen-plus", search_info=None):
        self.choices = choices
        self._model = model
        self._search_info = search_info

    @property
    def model(self):
        if self._model is None:
            raise KeyError("model")
        return self._model

    @property
    def search_info(self):
        if self._search_info is None:
            # DashScope raises KeyError on missing attrs; SUT catches it.
            raise KeyError("search_info")
        return self._search_info


class _GenResponse:
    """Mimics DashScope GenerationResponse."""

    def __init__(self, status_code=200, output=None, usage=None, code=None, message=None):
        self.status_code = status_code
        self.output = output
        self.usage = usage
        self.code = code
        self.message = message


def _make_gen_success(content="Hello world", role="assistant",
                      finish_reason="stop", model="qwen-plus",
                      input_tokens=10, output_tokens=20):
    choice = {"message": {"role": role, "content": content}, "finish_reason": finish_reason}
    output = _Output(choices=[choice], model=model)
    usage = _Usage(input_tokens, output_tokens)
    return _GenResponse(status_code=200, output=output, usage=usage)


def _make_gen_error(code="InvalidApiKey", message="bad key"):
    return _GenResponse(status_code=400, output=None, usage=None, code=code, message=message)


# Multimodal responses use dict-style output (output.get("choices"))
def _make_mm_response(content="vision answer", role="assistant", finish_reason="stop",
                      input_tokens=5, output_tokens=7, status_code=200,
                      content_is_list=False):
    if content_is_list:
        msg_content = [{"text": content}, {"image": "ignored"}]
    else:
        msg_content = content
    output = {"choices": [{"message": {"role": role, "content": msg_content},
                           "finish_reason": finish_reason}]}
    usage = _Usage(input_tokens, output_tokens)
    resp = SimpleNamespace(status_code=status_code, output=output, usage=usage,
                           code="InvalidParameter", message="bad")
    return resp


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def provider():
    """Construct a QwenNativeProvider with the dashscope module-level api_key
    assignment and ModelManager mocked. connection_mode defaults to official."""
    with patch.object(chat_mod, "dashscope") as fake_ds, \
         patch.object(chat_mod, "ModelManager") as MM:
        fake_ds.api_key = None
        mm_inst = MagicMock()
        MM.return_value = mm_inst
        p = QwenNativeProvider(api_key="sk-test", connection_mode="official")
        p._mm_inst = mm_inst
    return p


@pytest.fixture
def proxy_provider():
    with patch.object(chat_mod, "dashscope"), patch.object(chat_mod, "ModelManager"):
        return QwenNativeProvider(api_key="sk-test", connection_mode="proxy")


# ============================================================
# is_vision_model
# ============================================================

def test_is_vision_model_known_list():
    assert is_vision_model("qwen-vl-max") is True
    assert is_vision_model("qwen2.5-vl-7b-instruct") is True


def test_is_vision_model_by_keyword_and_suffix():
    assert is_vision_model("custom-vl-model") is True
    assert is_vision_model("Something-VL") is True  # endswith -vl (lowered)
    assert is_vision_model("qwen-plus") is False
    assert is_vision_model("qwen-turbo") is False


# ============================================================
# Construction / metadata
# ============================================================

def test_provider_basic_metadata(provider):
    assert provider.get_provider_name() == "Qwen"
    assert provider.supports_function_calling() is True
    assert provider.connection_mode == "official"
    assert provider.request_id  # generated
    assert provider.max_concurrent == 20


def test_provider_sets_dashscope_api_key():
    with patch.object(chat_mod, "dashscope") as fake_ds, \
         patch.object(chat_mod, "ModelManager"):
        QwenNativeProvider(api_key="sk-key-123")
        assert fake_ds.api_key == "sk-key-123"


def test_provider_with_client_selector_logs_init():
    selector = MagicMock()
    with patch.object(chat_mod, "dashscope"), patch.object(chat_mod, "ModelManager"):
        p = QwenNativeProvider(api_key="k", client_selector=selector, max_concurrent=5)
    assert p.client_selector is selector
    assert p.max_concurrent == 5


# ============================================================
# _should_use_primary_client
# ============================================================

def test_should_use_primary_no_selector_official(provider):
    assert provider._should_use_primary_client() is True


def test_should_use_primary_no_selector_proxy(proxy_provider):
    assert proxy_provider._should_use_primary_client() is False


def test_should_use_primary_advanced_features_force_primary():
    selector = MagicMock()
    with patch.object(chat_mod, "dashscope"), patch.object(chat_mod, "ModelManager"):
        p = QwenNativeProvider(api_key="k", client_selector=selector)
    assert p._should_use_primary_client(enable_search=True) is True
    assert p._should_use_primary_client(plugins=["code_interpreter"]) is True
    assert p._should_use_primary_client(enable_thinking=True) is True
    assert p._should_use_primary_client(model="qwen-long-context") is True
    assert p._should_use_primary_client(model="qwen-max-thinking") is True
    # selector not consulted for advanced features
    selector.select_client.assert_not_called()


def test_should_use_primary_delegates_to_selector():
    # SUT calls selector.select_client(operation_type=..., user_preference=..., **kwargs)
    # where kwargs itself contains operation_type, so the selector must accept that shape.
    calls = []

    class _Selector:
        result = "secondary"

        def select_client(self, operation_type="chat", user_preference=None, **kwargs):
            calls.append(operation_type)
            return self.result

    selector = _Selector()
    with patch.object(chat_mod, "dashscope"), patch.object(chat_mod, "ModelManager"):
        p = QwenNativeProvider(api_key="k", client_selector=selector)
    # Do not pass operation_type explicitly: SUT forwards **kwargs into select_client
    # alongside operation_type=..., so an explicit operation_type would collide.
    assert p._should_use_primary_client(model="qwen-plus") is False
    assert calls == ["chat"]  # defaulted to "chat"
    selector.result = "primary"
    assert p._should_use_primary_client(model="qwen-turbo") is True


# ============================================================
# _sync_chat: request building + success + error mapping
# ============================================================

def test_sync_chat_success_and_basic_params(provider):
    captured = {}

    def fake_call(**params):
        captured.update(params)
        return _make_gen_success(content="hi there")

    with patch.object(chat_mod.Generation, "call", side_effect=fake_call):
        resp = provider._sync_chat(
            messages=[{"role": "user", "content": "hi"}],
            model="qwen-plus",
            temperature=0.7, top_p=0.9, max_tokens=100,
        )
    assert resp.status_code == 200
    assert captured["model"] == "qwen-plus"
    assert captured["result_format"] == "message"
    assert captured["temperature"] == 0.7
    assert captured["top_p"] == 0.9
    assert captured["max_tokens"] == 100
    # no advanced features requested
    assert "enable_search" not in captured
    assert "plugins" not in captured


def test_sync_chat_enable_search_adds_search_options(provider):
    captured = {}

    def fake_call(**params):
        captured.update(params)
        return _make_gen_success()

    with patch.object(chat_mod.Generation, "call", side_effect=fake_call):
        provider._sync_chat(messages=[], model="qwen-plus", enable_search=True)
    assert captured["enable_search"] is True
    assert captured["search_options"]["forced_search"] is True
    assert captured["search_options"]["enable_citation"] is True


def test_sync_chat_plugins_list_converted_to_dict(provider):
    captured = {}
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: (captured.update(p), _make_gen_success())[1]):
        provider._sync_chat(messages=[], model="qwen-plus",
                            plugins=["code_interpreter", "pdf_extracter"])
    assert captured["plugins"] == {
        "code_interpreter": {"enable": True},
        "pdf_extracter": {"enable": True},
    }


def test_sync_chat_plugins_dict_passthrough(provider):
    captured = {}
    plugins = {"code_interpreter": {"enable": True, "timeout": 30}}
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: (captured.update(p), _make_gen_success())[1]):
        provider._sync_chat(messages=[], model="qwen-plus", plugins=plugins)
    assert captured["plugins"] == plugins


def test_sync_chat_proxy_mode_skips_advanced(proxy_provider):
    captured = {}
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: (captured.update(p), _make_gen_success())[1]):
        proxy_provider._sync_chat(messages=[], model="qwen-plus",
                                  enable_search=True, plugins=["code_interpreter"])
    # proxy mode: advanced feature params NOT added
    assert "enable_search" not in captured
    assert "plugins" not in captured


@pytest.mark.parametrize("code,exc", [
    ("InvalidApiKey", APIKeyError),
    ("InvalidAPIKey", APIKeyError),
    ("Throttling.RateQuota", RateLimitError),
    ("Throttling.AllocationQuota", RateLimitError),
    ("InvalidModel", ModelNotFoundError),
    ("UnsupportedModel", ModelNotFoundError),
    ("InvalidParameter", InvalidRequestError),
    ("InvalidInput", InvalidRequestError),
])
def test_sync_chat_error_mapping(provider, code, exc):
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: _make_gen_error(code=code)):
        with pytest.raises(exc):
            provider._sync_chat(messages=[], model="qwen-plus")


def test_sync_chat_unknown_error_code_maps_to_operation_error(provider):
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: _make_gen_error(code="SomethingWeird", message="boom")):
        with pytest.raises(OperationError) as ei:
            provider._sync_chat(messages=[], model="qwen-plus")
    assert "SomethingWeird" in str(ei.value)


def test_sync_chat_sdk_exception_wrapped_as_operation_error(provider):
    with patch.object(chat_mod.Generation, "call", side_effect=RuntimeError("network down")):
        with pytest.raises(OperationError) as ei:
            provider._sync_chat(messages=[], model="qwen-plus")
    assert "network down" in str(ei.value)
    assert ei.value.recoverable is True


def test_sync_chat_provider_error_not_rewrapped(provider):
    # _handle_error raises APIKeyError (a ProviderError); must propagate unchanged.
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: _make_gen_error(code="InvalidApiKey")):
        with pytest.raises(APIKeyError):
            provider._sync_chat(messages=[], model="qwen-plus")


# ============================================================
# _format_response
# ============================================================

def test_format_response_full(provider):
    resp = _make_gen_success(content="answer", model="qwen-max",
                             input_tokens=11, output_tokens=22)
    out = provider._format_response(resp)
    assert out["content"] == "answer"
    assert out["role"] == "assistant"
    assert out["model"] == "qwen-max"
    assert out["finish_reason"] == "stop"
    assert out["usage"] == {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33}


def test_format_response_no_choices_defaults(provider):
    output = _Output(choices=[], model="qwen-plus")
    resp = _GenResponse(status_code=200, output=output, usage=_Usage())
    out = provider._format_response(resp)
    assert out["content"] == ""
    assert out["role"] == "assistant"
    assert out["finish_reason"] == "stop"


def test_format_response_model_keyerror_falls_back(provider):
    choice = {"message": {"role": "assistant", "content": "x"}, "finish_reason": "stop"}
    output = _Output(choices=[choice], model=None)  # .model raises KeyError
    resp = _GenResponse(status_code=200, output=output, usage=_Usage())
    out = provider._format_response(resp)
    assert out["model"] == "qwen"


# ============================================================
# _format_stream_chunk
# ============================================================

def _stream_chunk(content="", reasoning="", finish_reason=None, usage=None, search_info=None):
    msg = {}
    if content:
        msg["content"] = content
    if reasoning:
        msg["reasoning_content"] = reasoning
    choice = {"message": msg, "finish_reason": finish_reason}
    output = _Output(choices=[choice], model="qwen-plus", search_info=search_info)
    return _GenResponse(status_code=200, output=output, usage=usage)


def test_format_stream_chunk_content(provider):
    out = provider._format_stream_chunk(_stream_chunk(content="part"))
    assert out == {"content": "part", "chunk_type": "content"}


def test_format_stream_chunk_reasoning(provider):
    out = provider._format_stream_chunk(_stream_chunk(reasoning="thinking..."))
    assert out["chunk_type"] == "reasoning"
    assert out["content"] == "thinking..."


def test_format_stream_chunk_empty(provider):
    out = provider._format_stream_chunk(_stream_chunk())
    assert out == {"content": "", "chunk_type": "content"}


def test_format_stream_chunk_done_with_usage_and_search(provider):
    usage = _Usage(input_tokens=3, output_tokens=4)
    search_info = {"search_results": [{"title": "a"}, {"title": "b"}]}
    chunk = _stream_chunk(content="final", finish_reason="stop", usage=usage,
                          search_info=search_info)
    out = provider._format_stream_chunk(chunk)
    assert out["chunk_type"] == "done"
    assert out["prompt_tokens"] == 3
    assert out["completion_tokens"] == 4
    assert out["total_tokens"] == 7
    assert out["finish_reason"] == "stop"
    assert out["search_results"] == [{"title": "a"}, {"title": "b"}]


def test_format_stream_chunk_done_without_search_info(provider):
    usage = _Usage(input_tokens=1, output_tokens=1)
    chunk = _stream_chunk(content="final", finish_reason="stop", usage=usage)
    out = provider._format_stream_chunk(chunk)
    assert out["chunk_type"] == "done"
    assert out["search_results"] is None


def test_format_stream_chunk_usage_but_not_stop(provider):
    usage = _Usage(input_tokens=2, output_tokens=2)
    chunk = _stream_chunk(content="mid", finish_reason="length", usage=usage)
    out = provider._format_stream_chunk(chunk)
    # finish_reason present but != stop -> keeps content type, attaches usage + reason
    assert out["chunk_type"] == "content"
    assert out["prompt_tokens"] == 2
    assert out["finish_reason"] == "length"


# ============================================================
# _sync_stream_chat
# ============================================================

def test_sync_stream_chat_yields_chunks_and_builds_params(provider):
    captured = {}
    chunks = [_stream_chunk(content="a"), _stream_chunk(content="b", finish_reason="stop",
                                                         usage=_Usage())]

    def fake_call(**params):
        captured.update(params)
        return iter(chunks)

    with patch.object(chat_mod.Generation, "call", side_effect=fake_call):
        got = list(provider._sync_stream_chat(
            messages=[{"role": "user", "content": "hi"}], model="qwen-plus",
            temperature=0.5, top_p=0.8, max_tokens=64,
            enable_search=True, enable_thinking=True, plugins=["code_interpreter"],
        ))
    assert len(got) == 2
    assert captured["stream"] is True
    assert captured["incremental_output"] is True
    assert captured["enable_search"] is True
    assert captured["enable_thinking"] is True
    assert captured["plugins"] == {"code_interpreter": {"enable": True}}
    assert captured["temperature"] == 0.5


def test_sync_stream_chat_plugins_dict_passthrough(provider):
    captured = {}
    plugins = {"pdf_extracter": {"enable": True}}
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: (captured.update(p), iter([_stream_chunk(content="x")]))[1]):
        list(provider._sync_stream_chat(messages=[], model="qwen-plus", plugins=plugins))
    assert captured["plugins"] == plugins


def test_sync_stream_chat_error_chunk_raises(provider):
    bad = _GenResponse(status_code=400, output=None, code="InvalidApiKey", message="x")

    def fake_call(**params):
        return iter([bad])

    with patch.object(chat_mod.Generation, "call", side_effect=fake_call):
        with pytest.raises(APIKeyError):
            list(provider._sync_stream_chat(messages=[], model="qwen-plus"))


def test_sync_stream_chat_sdk_exception_wrapped(provider):
    with patch.object(chat_mod.Generation, "call", side_effect=ValueError("explode")):
        with pytest.raises(OperationError) as ei:
            list(provider._sync_stream_chat(messages=[], model="qwen-plus"))
    assert "explode" in str(ei.value)


# ============================================================
# Multimodal message normalization
# ============================================================

def test_is_image_like_attachment_variants(provider):
    assert provider._is_image_like_attachment({"mimeType": "image/png"}) is True
    assert provider._is_image_like_attachment({"url": "https://x.com/a.jpg"}) is True
    assert provider._is_image_like_attachment({"url": "data:image/png;base64,AAAA"}) is True
    assert provider._is_image_like_attachment({"url": "oss://bucket/k.webp"}) is True
    assert provider._is_image_like_attachment({"url": "/local/path/pic.png"}) is True
    # any http(s)/oss URL is treated as image-like by the SUT, even .txt
    assert provider._is_image_like_attachment({"url": "https://x.com/file.txt"}) is True
    # local path without an image extension is NOT image-like
    assert provider._is_image_like_attachment({"url": "/local/path/notes.txt"}) is False
    assert provider._is_image_like_attachment({"url": "plain-string-no-scheme.doc"}) is False
    assert provider._is_image_like_attachment({}) is False


def test_guess_image_mime_type(provider):
    assert provider._guess_image_mime_type("x", explicit_mime="image/jpeg") == "image/jpeg"
    assert provider._guess_image_mime_type("data:image/webp;base64,AAA") == "image/webp"
    assert provider._guess_image_mime_type("photo.png") == "image/png"
    assert provider._guess_image_mime_type("unknown.xyz") == "image/png"  # default


def test_local_path_to_data_url_rejects_arbitrary_path(provider, tmp_path):
    # SECURITY (CANON-028): an arbitrary out-of-root local path must NOT be read.
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nDATA")
    assert provider._local_path_to_data_url(str(img)) is None


def test_local_path_to_data_url_reads_allow_rooted(provider, tmp_path, monkeypatch):
    # An allow-rooted local-files reference (resolved by the shared resolver) is read.
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nDATA")
    # svc-providers-5: the multimodal helper moved into the chat_multimodal mixin,
    # so the resolver call site (and patch target) now lives there.
    from app.services.tongyi import chat_multimodal

    monkeypatch.setattr(chat_multimodal, "resolve_local_public_file_path", lambda value: img)
    data_url = provider._local_path_to_data_url("/api/storage/local-files/x.png")
    assert data_url.startswith("data:image/png;base64,")
    assert base64.b64decode(data_url.split(",", 1)[1]) == b"\x89PNG\r\n\x1a\nDATA"


def test_local_path_to_data_url_missing_returns_none(provider, tmp_path):
    assert provider._local_path_to_data_url(str(tmp_path / "nope.png")) is None
    assert provider._local_path_to_data_url("") is None


def test_normalize_multimodal_image_ref_url_passthrough(provider):
    assert provider._normalize_multimodal_image_ref("https://x.com/a.jpg") == "https://x.com/a.jpg"
    assert provider._normalize_multimodal_image_ref("data:image/png;base64,AA") == "data:image/png;base64,AA"
    assert provider._normalize_multimodal_image_ref(None) is None
    assert provider._normalize_multimodal_image_ref("   ") is None


def test_normalize_multimodal_image_ref_dict(provider):
    ref = {"url": "https://x.com/b.png", "mimeType": "image/png"}
    assert provider._normalize_multimodal_image_ref(ref) == "https://x.com/b.png"


def test_normalize_multimodal_image_ref_bare_base64(provider):
    raw = "A" * 200  # long base64-ish, no spaces
    out = provider._normalize_multimodal_image_ref(raw, explicit_mime="image/jpeg")
    assert out.startswith("data:image/jpeg;base64,")


def test_normalize_multimodal_image_ref_plain_text_passthrough(provider):
    assert provider._normalize_multimodal_image_ref("just some text") == "just some text"


def test_coerce_multimodal_messages_string_content(provider):
    out = provider._coerce_multimodal_messages([{"role": "user", "content": "hello"}])
    assert out == [{"role": "user", "content": [{"text": "hello"}]}]


def test_coerce_multimodal_messages_role_model_to_assistant(provider):
    out = provider._coerce_multimodal_messages([{"role": "model", "content": "hi"}])
    assert out[0]["role"] == "assistant"


def test_coerce_multimodal_messages_list_content_with_image_url(provider):
    msg = {"role": "user", "content": [
        {"text": "look"},
        {"image_url": {"url": "https://x.com/c.jpg"}},
    ]}
    out = provider._coerce_multimodal_messages([msg])
    content = out[0]["content"]
    assert {"text": "look"} in content
    assert {"image": "https://x.com/c.jpg"} in content


def test_coerce_multimodal_messages_attachments_prepended(provider):
    msg = {
        "role": "user",
        "content": "describe",
        "attachments": [{"url": "https://x.com/att.png", "mimeType": "image/png"}],
    }
    out = provider._coerce_multimodal_messages([msg])
    content = out[0]["content"]
    # image attachment is inserted at front
    assert content[0] == {"image": "https://x.com/att.png"}
    assert {"text": "describe"} in content


def test_coerce_multimodal_messages_dedup_images(provider):
    msg = {"role": "user", "content": [
        {"image": "https://x.com/d.jpg"},
        {"image": "https://x.com/d.jpg"},
    ]}
    out = provider._coerce_multimodal_messages([msg])
    images = [c for c in out[0]["content"] if "image" in c]
    assert len(images) == 1


def test_coerce_multimodal_messages_empty_content_fallback(provider):
    out = provider._coerce_multimodal_messages([{"role": "user", "content": ""}])
    assert out[0]["content"] == [{"text": ""}]


def test_coerce_multimodal_messages_skips_non_dict(provider):
    out = provider._coerce_multimodal_messages(["not a dict", {"role": "user", "content": "ok"}])
    assert len(out) == 1


# ============================================================
# _sync_multimodal_chat + formatting
# ============================================================

def test_sync_multimodal_chat_success(provider):
    captured = {}

    def fake_call(**params):
        captured.update(params)
        return _make_mm_response(content="a cat")

    with patch.object(chat_mod.MultiModalConversation, "call", side_effect=fake_call):
        resp = provider._sync_multimodal_chat(
            messages=[{"role": "user", "content": [{"text": "x"}]}],
            model="qwen-vl-max", temperature=0.3, top_p=0.5, max_tokens=50,
        )
    assert resp.status_code == 200
    assert captured["model"] == "qwen-vl-max"
    assert captured["temperature"] == 0.3
    assert "result_format" not in captured  # multimodal does not set result_format


def test_sync_multimodal_chat_error_raises(provider):
    bad = _make_mm_response(status_code=400)
    bad.code = "InvalidModel"
    with patch.object(chat_mod.MultiModalConversation, "call", side_effect=lambda **p: bad):
        with pytest.raises(ModelNotFoundError):
            provider._sync_multimodal_chat(messages=[], model="qwen-vl-max")


def test_sync_multimodal_chat_sdk_exception_wrapped(provider):
    with patch.object(chat_mod.MultiModalConversation, "call", side_effect=OSError("io")):
        with pytest.raises(OperationError):
            provider._sync_multimodal_chat(messages=[], model="qwen-vl-max")


def test_format_multimodal_response_string_content(provider):
    resp = _make_mm_response(content="plain", input_tokens=2, output_tokens=3)
    out = provider._format_multimodal_response(resp)
    assert out["content"] == "plain"
    assert out["model"] == "qwen-vl"
    assert out["usage"] == {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}


def test_format_multimodal_response_list_content(provider):
    resp = _make_mm_response(content="partA", content_is_list=True)
    out = provider._format_multimodal_response(resp)
    assert out["content"] == "partA"  # text part extracted, image part ignored


def test_format_multimodal_response_no_choices(provider):
    resp = SimpleNamespace(output={"choices": []}, usage=_Usage(0, 0, 0))
    out = provider._format_multimodal_response(resp)
    assert out["content"] == ""
    assert out["finish_reason"] == "stop"


def test_format_multimodal_stream_chunk_content(provider):
    chunk = SimpleNamespace(
        output={"choices": [{"message": {"content": "hi"}, "finish_reason": None}]},
        usage=None,
    )
    out = provider._format_multimodal_stream_chunk(chunk)
    assert out == {"content": "hi", "chunk_type": "content"}


def test_format_multimodal_stream_chunk_list_content_and_done(provider):
    usage = _Usage(input_tokens=4, output_tokens=6)
    chunk = SimpleNamespace(
        output={"choices": [{"message": {"content": [{"text": "done"}]},
                             "finish_reason": "stop"}]},
        usage=usage,
    )
    out = provider._format_multimodal_stream_chunk(chunk)
    assert out["chunk_type"] == "done"
    assert out["content"] == "done"
    assert out["total_tokens"] == 10


def test_format_multimodal_stream_chunk_usage_not_stop(provider):
    usage = _Usage(input_tokens=1, output_tokens=1)
    chunk = SimpleNamespace(
        output={"choices": [{"message": {"content": "x"}, "finish_reason": "length"}]},
        usage=usage,
    )
    out = provider._format_multimodal_stream_chunk(chunk)
    assert out["chunk_type"] == "content"
    assert out["finish_reason"] == "length"
    assert out["prompt_tokens"] == 1


# ============================================================
# _sync_stream_multimodal_chat
# ============================================================

def test_sync_stream_multimodal_chat_yields(provider):
    captured = {}
    chunk = SimpleNamespace(status_code=200,
                            output={"choices": [{"message": {"content": "z"},
                                                 "finish_reason": None}]},
                            usage=None, code="InvalidModel", message="x")

    def fake_call(**params):
        captured.update(params)
        return iter([chunk])

    with patch.object(chat_mod.MultiModalConversation, "call", side_effect=fake_call):
        got = list(provider._sync_stream_multimodal_chat(
            messages=[], model="qwen-vl-max", temperature=0.2, top_p=0.3, max_tokens=10))
    assert len(got) == 1
    assert captured["stream"] is True
    assert captured["incremental_output"] is True
    assert captured["temperature"] == 0.2


def test_sync_stream_multimodal_chat_error_chunk_raises(provider):
    chunk = SimpleNamespace(status_code=400, output=None, usage=None,
                            code="InvalidParameter", message="bad")
    with patch.object(chat_mod.MultiModalConversation, "call",
                      side_effect=lambda **p: iter([chunk])):
        with pytest.raises(InvalidRequestError):
            list(provider._sync_stream_multimodal_chat(messages=[], model="qwen-vl-max"))


def test_sync_stream_multimodal_chat_sdk_exception_wrapped(provider):
    with patch.object(chat_mod.MultiModalConversation, "call", side_effect=RuntimeError("x")):
        with pytest.raises(OperationError):
            list(provider._sync_stream_multimodal_chat(messages=[], model="qwen-vl-max"))


# ============================================================
# Async chat / stream_chat orchestration (text + vision routing)
# ============================================================

async def test_chat_text_model(provider):
    with patch.object(chat_mod.Generation, "call",
                      side_effect=lambda **p: _make_gen_success(content="textans")):
        out = await provider.chat(messages=[{"role": "user", "content": "hi"}],
                                  model="qwen-plus")
    assert out["content"] == "textans"
    assert out["role"] == "assistant"


async def test_chat_vision_model_routes_multimodal(provider):
    with patch.object(chat_mod.MultiModalConversation, "call",
                      side_effect=lambda **p: _make_mm_response(content="visionans")):
        out = await provider.chat(
            messages=[{"role": "user", "content": "describe",
                       "attachments": [{"url": "https://x.com/a.png", "mimeType": "image/png"}]}],
            model="qwen-vl-max")
    assert out["content"] == "visionans"
    assert out["model"] == "qwen-vl"


async def test_stream_chat_text_model(provider):
    chunks = [_stream_chunk(content="A"),
              _stream_chunk(content="B", finish_reason="stop", usage=_Usage())]
    with patch.object(chat_mod.Generation, "call", side_effect=lambda **p: iter(chunks)):
        collected = [c async for c in provider.stream_chat(
            messages=[{"role": "user", "content": "hi"}], model="qwen-plus")]
    assert collected[0] == {"content": "A", "chunk_type": "content"}
    assert collected[-1]["chunk_type"] == "done"


async def test_stream_chat_vision_model_routes_multimodal(provider):
    chunk = SimpleNamespace(status_code=200,
                            output={"choices": [{"message": {"content": "V"},
                                                 "finish_reason": None}]},
                            usage=None)
    with patch.object(chat_mod.MultiModalConversation, "call",
                      side_effect=lambda **p: iter([chunk])):
        collected = [c async for c in provider.stream_chat(
            messages=[{"role": "user", "content": "x"}], model="qwen-vl-plus")]
    assert collected == [{"content": "V", "chunk_type": "content"}]


# ============================================================
# get_available_models delegates to ModelManager
# ============================================================

async def test_get_available_models_delegates(provider):
    async def fake_models():
        return ["m1", "m2"]
    provider._mm_inst.get_available_models = fake_models
    result = await provider.get_available_models()
    assert result == ["m1", "m2"]
