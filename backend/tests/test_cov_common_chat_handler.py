"""Coverage-focused tests for ``app.services.gemini.common.chat_handler``.

Strategy
--------
``ChatHandler`` orchestrates the google-genai SDK. We exercise the *real*
handler logic and only fake the SDK boundary:

* ``get_client_pool`` (imported into the module namespace) is replaced with a
  fake that returns a fake client whose ``models``/``aio.chats`` produce the
  chunk objects the handler iterates.
* ``run_in_sdk_thread`` is replaced with a thin shim that just calls the
  function (the handler only uses it to offload the blocking SDK call).
* ``MessageConverter`` / ``ConfigBuilder`` / ``ResponseParser`` are the
  collaborators converting message <-> SDK shapes; for the non-streaming path
  we let the real ones run where cheap and patch where they need network.
* Lazy imports inside ``stream_chat`` (``browser.AVAILABLE_TOOLS``,
  ``mcp.mcp_manager.get_mcp_manager``, ``app.routers.storage`` upload) are
  patched at their source modules.

Everything else — message normalization, streaming assembly, the function-call
loop, dedup, tool-result chunking, browser-progress emission, error mapping —
runs for real. Assertions check real chunk shapes, status/finish reasons,
usage propagation, and error/permission branches.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List

import pytest

from app.services.gemini.common import chat_handler as ch_mod
from app.services.gemini.common import message_converter as mc_mod
from app.services.gemini.common.chat_handler import ChatHandler
from app.services.gemini.common.message_converter import (
    MessageConverter,
    decode_inline_attachment_bytes,
    is_allowed_provider_file_uri,
    normalize_inline_base64_payload,
    validate_inline_base64_payload,
)
from app.services.common.errors import (
    APIKeyError,
    ModelNotFoundError,
    OperationError,
)


def test_provider_file_uri_allowlist_rejects_local_and_unknown_schemes():
    assert is_allowed_provider_file_uri("files/abc") is True
    assert is_allowed_provider_file_uri("gs://bucket/object.png") is True
    assert is_allowed_provider_file_uri(
        "https://generativelanguage.googleapis.com/v1beta/files/abc"
    ) is True

    for raw in (
        "file:///etc/passwd",
        "/etc/passwd",
        r"C:\Users\me\secret.png",
        "https://evil.example/files/abc",
        "https://www.googleapis.com/v1/files/abc",
        "https://generativelanguage.googleapis.com/other/files/abc",
        "ftp://host/files/abc",
        "files/",
        "gs://bucket",
    ):
        assert is_allowed_provider_file_uri(raw) is False


def test_message_converter_rejects_unsafe_file_uri_attachment():
    part = MessageConverter._build_attachment_part(
        {"fileUri": "file:///etc/passwd", "mimeType": "image/png"}
    )
    assert part is None


def test_message_converter_allows_provider_file_uri_attachment():
    part = MessageConverter._build_attachment_part(
        {"fileUri": "gs://bucket/object.png", "mimeType": "image/png"}
    )
    assert part == {
        "file_data": {
            "file_uri": "gs://bucket/object.png",
            "mime_type": "image/png",
        }
    }


def test_message_converter_file_uri_log_redacts_query(caplog):
    uri = "https://generativelanguage.googleapis.com/v1beta/files/abc?token=secret"

    with caplog.at_level(logging.INFO, logger="app.services.gemini.common.message_converter"):
        MessageConverter._build_attachment_part(
            {"fileUri": uri, "mimeType": "image/png"}
        )

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://generativelanguage.googleapis.com path_len=17 query_params=1 fragment=no" in log_text
    assert uri not in log_text
    assert "secret" not in log_text


def test_inline_base64_payload_limit_rejects_before_decode(monkeypatch):
    monkeypatch.setattr(mc_mod, "MAX_INLINE_ATTACHMENT_BYTES", 3)

    raw = base64.b64encode(b"abcd").decode()

    with pytest.raises(ValueError, match="attachment too large"):
        normalize_inline_base64_payload(raw, source="attachment")

    with pytest.raises(ValueError, match="attachment too large"):
        decode_inline_attachment_bytes(raw, source="attachment")


def test_inline_base64_payload_validation_rejects_malformed_data():
    with pytest.raises(ValueError, match="invalid attachment base64 payload"):
        validate_inline_base64_payload("not valid base64!", source="attachment")


def test_message_converter_rejects_oversized_inline_attachment(monkeypatch):
    monkeypatch.setattr(mc_mod, "MAX_INLINE_ATTACHMENT_BYTES", 3)
    raw = base64.b64encode(b"abcd").decode()

    assert MessageConverter._build_attachment_part(
        {"url": f"data:image/png;base64,{raw}", "mimeType": "image/png"}
    ) is None
    assert MessageConverter._build_attachment_part(
        {"base64Data": raw, "mimeType": "image/png"}
    ) is None


def test_message_converter_rejects_invalid_inline_attachment():
    assert MessageConverter._build_attachment_part(
        {"base64Data": "not valid base64!", "mimeType": "image/png"}
    ) is None


# --------------------------------------------------------------------------- #
# Fake SDK chunk / response objects
# --------------------------------------------------------------------------- #
class FakePart:
    """Mimics a google-genai content Part."""

    def __init__(self, *, text=None, thought=None, function_call=None):
        if text is not None:
            self.text = text
        if thought is not None:
            self.thought = thought
        if function_call is not None:
            self.function_call = function_call


class FakeFunctionCall:
    def __init__(self, name=None, args=None, call_id=None):
        self.name = name
        self.args = args
        self.id = call_id


class FakeContent:
    def __init__(self, parts):
        self.parts = parts


class FakeUsage:
    def __init__(self, prompt=0, completion=0, total=0):
        self.prompt_token_count = prompt
        self.candidates_token_count = completion
        self.total_token_count = total


class FakeCandidate:
    def __init__(self, *, parts=None, finish_reason=None):
        if parts is not None:
            self.content = FakeContent(parts)
        else:
            self.content = None
        self.finish_reason = finish_reason


class FakeChunk:
    """A streaming chunk. Attributes only set when provided to exercise the
    handler's ``hasattr`` guards."""

    def __init__(self, *, text=None, candidates=None, usage=None,
                 function_calls=None):
        if text is not None:
            self.text = text
        if candidates is not None:
            self.candidates = candidates
        if usage is not None:
            self.usage_metadata = usage
        if function_calls is not None:
            self.function_calls = function_calls


# --------------------------------------------------------------------------- #
# Fake genai client + pool
# --------------------------------------------------------------------------- #
class _FakeModels:
    def __init__(self, *, gen_response=None, gen_error=None, stream_chunks=None,
                 stream_error=None):
        self._gen_response = gen_response
        self._gen_error = gen_error
        self._stream_chunks = stream_chunks or []
        self._stream_error = stream_error

    def generate_content(self, *, model, contents, config):
        if self._gen_error is not None:
            raise self._gen_error
        return self._gen_response

    def generate_content_stream(self, *, model, contents, config):
        if self._stream_error is not None:
            raise self._stream_error
        return iter(self._stream_chunks)


class _FakeAsyncChat:
    def __init__(self, batches):
        # batches: list of lists of FakeChunk, one per send_message_stream call
        self._batches = list(batches)
        self.sent_messages: List[Any] = []

    async def send_message_stream(self, *, message):
        self.sent_messages.append(message)
        batch = self._batches.pop(0) if self._batches else []

        async def _gen():
            for c in batch:
                yield c

        return _gen()


class _FakeAioChats:
    def __init__(self, async_chat):
        self._async_chat = async_chat
        self.create_kwargs: Dict[str, Any] = {}

    def create(self, *, model, config, history):
        self.create_kwargs = {"model": model, "config": config, "history": history}
        return self._async_chat


class _FakeAio:
    def __init__(self, async_chat):
        self.chats = _FakeAioChats(async_chat)


class FakeClient:
    def __init__(self, *, models=None, async_chat=None):
        self.models = models
        self.aio = _FakeAio(async_chat) if async_chat is not None else None


class FakePool:
    def __init__(self, client):
        self._client = client
        self.get_client_kwargs: Dict[str, Any] = {}

    def get_client(self, **kwargs):
        self.get_client_kwargs = kwargs
        return self._client


@pytest.fixture()
def patch_pool(monkeypatch):
    """Return a helper that installs a FakePool returning the given client."""

    def _install(client):
        pool = FakePool(client)
        monkeypatch.setattr(ch_mod, "get_client_pool", lambda: pool)
        return pool

    return _install


@pytest.fixture(autouse=True)
def _fast_sdk_thread(monkeypatch):
    """Run the SDK call inline instead of offloading to the thread pool."""

    async def _runner(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(ch_mod, "run_in_sdk_thread", _runner)


async def _collect(agen):
    return [item async for item in agen]


# --------------------------------------------------------------------------- #
# Static helper tests
# --------------------------------------------------------------------------- #
class TestJsonCompatible:
    def test_primitives_pass_through(self):
        assert ChatHandler._to_json_compatible(None) is None
        assert ChatHandler._to_json_compatible("s") == "s"
        assert ChatHandler._to_json_compatible(3) == 3
        assert ChatHandler._to_json_compatible(True) is True

    def test_nested_list_and_dict(self):
        out = ChatHandler._to_json_compatible({"a": [1, {"b": 2}]})
        assert out == {"a": [1, {"b": 2}]}
        # non-str keys are stringified
        assert ChatHandler._to_json_compatible({1: "x"}) == {"1": "x"}

    def test_model_dump_object(self):
        class M:
            def model_dump(self):
                return {"k": "v"}

        assert ChatHandler._to_json_compatible(M()) == {"k": "v"}

    def test_to_dict_object(self):
        class T:
            def to_dict(self):
                return {"t": 1}

        assert ChatHandler._to_json_compatible(T()) == {"t": 1}

    def test_dict_method_object(self):
        class D:
            def dict(self):
                return {"d": 2}

        assert ChatHandler._to_json_compatible(D()) == {"d": 2}

    def test_plain_object_uses_vars(self):
        class P:
            def __init__(self):
                self.x = 1

        assert ChatHandler._to_json_compatible(P()) == {"x": 1}

    def test_model_dump_failure_falls_through_to_str(self):
        class Bad:
            __slots__ = ()

            def model_dump(self):
                raise RuntimeError("boom")

        # no to_dict/dict/__dict__ → str fallback
        out = ChatHandler._to_json_compatible(Bad())
        assert isinstance(out, str)

    def test_to_dict_failure_then_str_fallback(self):
        class Bad:
            __slots__ = ()

            def to_dict(self):
                raise RuntimeError("boom")

        out = ChatHandler._to_json_compatible(Bad())
        assert isinstance(out, str)

    def test_dict_failure_then_str_fallback(self):
        class Bad:
            __slots__ = ()

            def dict(self):
                raise RuntimeError("boom")

        out = ChatHandler._to_json_compatible(Bad())
        assert isinstance(out, str)


class TestPreviewText:
    def test_string_truncation(self):
        assert ChatHandler._to_preview_text("abcdef", limit=3) == "abc"

    def test_json_serialization(self):
        assert ChatHandler._to_preview_text({"x": 1}, limit=100) == '{"x": 1}'

    def test_non_serializable_falls_back_to_str(self):
        obj = object()
        out = ChatHandler._to_preview_text(obj, limit=200)
        assert isinstance(out, str)
        assert "object" in out


class TestFunctionCallExtraction:
    def test_name_from_attr(self):
        fc = FakeFunctionCall(name="  do_thing  ")
        assert ChatHandler._extract_function_call_name(fc) == "do_thing"

    def test_name_from_dict(self):
        assert ChatHandler._extract_function_call_name({"name": "x"}) == "x"

    def test_name_missing(self):
        assert ChatHandler._extract_function_call_name(FakeFunctionCall(name="")) is None
        assert ChatHandler._extract_function_call_name({}) is None

    def test_args_dict(self):
        assert ChatHandler._extract_function_call_args(FakeFunctionCall(args={"a": 1})) == {"a": 1}

    def test_args_from_dict_arguments_key(self):
        assert ChatHandler._extract_function_call_args({"arguments": {"q": "x"}}) == {"q": "x"}

    def test_args_none_returns_empty(self):
        assert ChatHandler._extract_function_call_args(FakeFunctionCall(args=None)) == {}

    def test_args_non_dict_iterable_coerced(self):
        # list of pairs is coercible to dict
        assert ChatHandler._extract_function_call_args(FakeFunctionCall(args=[("a", 1)])) == {"a": 1}

    def test_args_uncoercible_returns_empty(self):
        assert ChatHandler._extract_function_call_args(FakeFunctionCall(args=123)) == {}

    def test_id_from_attr_and_dict(self):
        assert ChatHandler._extract_function_call_id(FakeFunctionCall(call_id=" c1 ")) == "c1"
        assert ChatHandler._extract_function_call_id({"id": "c2"}) == "c2"
        assert ChatHandler._extract_function_call_id(FakeFunctionCall(call_id="")) is None
        assert ChatHandler._extract_function_call_id({}) is None


class TestDedupKey:
    def test_uses_call_id_when_present(self):
        assert ChatHandler._build_function_call_dedup_key("n", {"a": 1}, "cid") == "id:cid"

    def test_signature_when_no_id_is_stable(self):
        k1 = ChatHandler._build_function_call_dedup_key("n", {"a": 1, "b": 2}, None)
        k2 = ChatHandler._build_function_call_dedup_key("n", {"b": 2, "a": 1}, None)
        assert k1 == k2  # sort_keys → order independent
        assert k1.startswith("sig:n:")

    def test_signature_handles_unserializable_args(self):
        key = ChatHandler._build_function_call_dedup_key("n", {"x": object()}, None)
        assert key.startswith("sig:n:")


class TestBrowserHelpers:
    def test_is_browser_tool_name(self):
        assert ChatHandler._is_browser_tool_name("web_search")
        assert ChatHandler._is_browser_tool_name("READ_WEBPAGE")
        assert ChatHandler._is_browser_tool_name("selenium_browse")
        assert not ChatHandler._is_browser_tool_name("calc")
        assert not ChatHandler._is_browser_tool_name(None)

    def test_build_browser_operation_id_normalizes(self):
        oid = ChatHandler._build_browser_operation_id(
            user_id="u1", call_id="c1", tool_name="Web_Search"
        )
        assert oid == "browser:u1:web_search:c1"

    def test_build_browser_operation_id_defaults(self):
        oid = ChatHandler._build_browser_operation_id(user_id=None, call_id="", tool_name="")
        assert oid == "browser:anonymous:browser:call"

    async def test_emit_progress_noop_without_operation_id(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            ch_mod.progress_tracker, "send_progress",
            lambda **k: called.append(k),
        )
        await ChatHandler._emit_browser_progress(None, step="s", details="d", progress=1)
        assert called == []

    async def test_emit_complete_fail_progress(self, monkeypatch):
        events: List[str] = []

        async def _send_progress(**kwargs):
            events.append("progress")

        async def _send_complete(operation_id, result=None):
            events.append("complete")

        async def _send_error(operation_id, error):
            events.append("error")

        monkeypatch.setattr(ch_mod.progress_tracker, "send_progress", _send_progress)
        monkeypatch.setattr(ch_mod.progress_tracker, "send_complete", _send_complete)
        monkeypatch.setattr(ch_mod.progress_tracker, "send_error", _send_error)

        await ChatHandler._emit_browser_progress("op", step="s", details="d", progress=10)
        await ChatHandler._complete_browser_progress("op")
        await ChatHandler._fail_browser_progress("op", "err")
        # noops with None
        await ChatHandler._complete_browser_progress(None)
        await ChatHandler._fail_browser_progress(None, "x")
        assert events == ["progress", "complete", "error"]


class TestAttachmentPart:
    def test_file_uri_priority(self):
        part = ChatHandler._build_attachment_part(
            {"fileUri": "files/abc", "mimeType": "image/png"}
        )
        assert part is not None
        assert part.file_data.file_uri == "files/abc"

    def test_unsafe_file_uri_rejected(self):
        assert ChatHandler._build_attachment_part(
            {"fileUri": "file:///etc/passwd", "mimeType": "image/png"}
        ) is None

    def test_data_url_in_url_field(self):
        raw = base64.b64encode(b"PNGDATA").decode()
        part = ChatHandler._build_attachment_part(
            {"url": f"data:image/jpeg;base64,{raw}", "mimeType": "image/png"}
        )
        assert part is not None  # built from inline bytes

    def test_base64data_as_data_url(self):
        raw = base64.b64encode(b"x").decode()
        part = ChatHandler._build_attachment_part(
            {"base64Data": f"data:image/webp;base64,{raw}"}
        )
        assert part is not None

    def test_base64data_pure_string(self):
        raw = base64.b64encode(b"hello").decode()
        part = ChatHandler._build_attachment_part(
            {"base64Data": raw, "mimeType": "image/gif"}
        )
        assert part is not None

    def test_oversized_inline_data_rejected(self, monkeypatch):
        monkeypatch.setattr(mc_mod, "MAX_INLINE_ATTACHMENT_BYTES", 3)
        raw = base64.b64encode(b"abcd").decode()

        assert ChatHandler._build_attachment_part(
            {"url": f"data:image/png;base64,{raw}", "mimeType": "image/png"}
        ) is None
        assert ChatHandler._build_attachment_part(
            {"base64Data": raw, "mimeType": "image/png"}
        ) is None

    def test_invalid_base64data_rejected(self):
        assert ChatHandler._build_attachment_part(
            {"base64Data": "not valid base64!", "mimeType": "image/png"}
        ) is None

    def test_no_usable_data_returns_none(self):
        assert ChatHandler._build_attachment_part({"mimeType": "image/png"}) is None

    def test_non_data_url_ignored(self):
        # http url is not base64 → falls through and returns None
        assert ChatHandler._build_attachment_part({"url": "http://example.com/a.png"}) is None


# --------------------------------------------------------------------------- #
# _convert_error branches
# --------------------------------------------------------------------------- #
class _GenAIError(Exception):
    """Stand-in whose __module__ starts with google.genai.errors."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


_GenAIError.__module__ = "google.genai.errors"


class TestConvertError:
    def setup_method(self):
        self.handler = ChatHandler(api_key="k")

    def test_non_google_error_returned_unchanged(self):
        err = ValueError("plain")
        assert self.handler._convert_error(err, "m", "chat") is err

    def test_400_api_key(self):
        err = _GenAIError("Invalid API key provided", status_code=400)
        out = self.handler._convert_error(err, "m", "chat")
        assert isinstance(out, APIKeyError)

    def test_400_invalid_request_raises_typeerror_latent_bug(self):
        # NOTE: This documents a latent bug — the handler calls
        # ``InvalidRequestError(message=..., context=..., original_error=...)``
        # but that class' ctor accepts ``validation_errors`` (not ``message``),
        # so building the InvalidRequestError raises TypeError. We assert the
        # *real* current behavior rather than the intended mapping.
        err = _GenAIError("bad body", status_code=400)
        with pytest.raises(TypeError):
            self.handler._convert_error(err, "m", "chat")

    def test_404_model_not_found(self):
        err = _GenAIError("model gemini-x not found", status_code=404)
        out = self.handler._convert_error(err, "m", "chat")
        assert isinstance(out, ModelNotFoundError)

    def test_404_generic_resource_raises_typeerror_latent_bug(self):
        # Same latent bug as the 400 generic branch: InvalidRequestError is
        # constructed with an unsupported ``message`` kwarg.
        err = _GenAIError("missing resource", status_code=404)
        with pytest.raises(TypeError):
            self.handler._convert_error(err, "m", "chat")

    def test_429_rate_limit_recoverable(self):
        err = _GenAIError("too many", status_code=429)
        out = self.handler._convert_error(err, "m", "chat")
        assert isinstance(out, OperationError)
        assert out.recoverable is True

    def test_500_recoverable_operation_error(self):
        err = _GenAIError("server boom", status_code=500)
        out = self.handler._convert_error(err, "m", "chat")
        assert isinstance(out, OperationError)
        assert out.recoverable is True

    def test_no_status_code_non_recoverable(self):
        err = _GenAIError("weird")  # no status_code attr
        out = self.handler._convert_error(err, "m", "chat")
        assert isinstance(out, OperationError)
        assert not out.recoverable


# --------------------------------------------------------------------------- #
# chat() non-streaming path
# --------------------------------------------------------------------------- #
class TestChat:
    async def test_success_returns_parsed_result(self, patch_pool, monkeypatch):
        parsed = {
            "content": "hi",
            "role": "model",
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            "model": "gemini-pro",
            "finish_reason": "stop",
        }
        monkeypatch.setattr(ch_mod.MessageConverter, "build_contents", lambda m: [{"x": 1}])
        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config", lambda **k: {})
        monkeypatch.setattr(
            ch_mod.ResponseParser, "parse_generate_content_response",
            lambda resp, model: parsed,
        )
        client = FakeClient(models=_FakeModels(gen_response=object()))
        pool = patch_pool(client)

        handler = ChatHandler(api_key="k", use_vertex=True, project="p", location="us")
        out = await handler.chat([{"role": "user", "content": "hello"}], "gemini-pro")

        assert out == parsed
        # client pool received the handler's auth params
        assert pool.get_client_kwargs["api_key"] == "k"
        assert pool.get_client_kwargs["vertexai"] is True
        assert pool.get_client_kwargs["project"] == "p"

    async def test_error_is_converted(self, patch_pool, monkeypatch):
        monkeypatch.setattr(ch_mod.MessageConverter, "build_contents", lambda m: [])
        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config", lambda **k: {})
        err = _GenAIError("Invalid API key", status_code=400)
        client = FakeClient(models=_FakeModels(gen_error=err))
        patch_pool(client)

        handler = ChatHandler(api_key="bad")
        with pytest.raises(APIKeyError):
            await handler.chat([{"role": "user", "content": "x"}], "gemini-pro")

    async def test_plain_error_propagates(self, patch_pool, monkeypatch):
        monkeypatch.setattr(ch_mod.MessageConverter, "build_contents", lambda m: [])
        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config", lambda **k: {})
        client = FakeClient(models=_FakeModels(gen_error=RuntimeError("nope")))
        patch_pool(client)
        handler = ChatHandler(api_key="k")
        with pytest.raises(RuntimeError, match="nope"):
            await handler.chat([{"role": "user", "content": "x"}], "m")


# --------------------------------------------------------------------------- #
# stream_chat_sse()
# --------------------------------------------------------------------------- #
class TestStreamChatSSE:
    def _patch_converters(self, monkeypatch):
        monkeypatch.setattr(ch_mod.MessageConverter, "build_contents", lambda m: [])
        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config", lambda **k: {})

    async def test_text_chunks_and_done(self, patch_pool, monkeypatch):
        self._patch_converters(monkeypatch)
        chunks = [
            FakeChunk(text="Hello "),
            FakeChunk(
                candidates=[FakeCandidate(parts=[FakePart(text="World")], finish_reason=None)]
            ),
            FakeChunk(usage=FakeUsage(prompt=5, completion=7, total=12),
                      candidates=[FakeCandidate(parts=[], finish_reason=None)]),
        ]
        client = FakeClient(models=_FakeModels(stream_chunks=chunks))
        patch_pool(client)
        handler = ChatHandler(api_key="k")

        out = await _collect(handler.stream_chat_sse([{"role": "user", "content": "hi"}], "m"))

        contents = [c for c in out if c["chunk_type"] == "content"]
        assert [c["content"] for c in contents] == ["Hello ", "World"]
        done = out[-1]
        assert done["chunk_type"] == "done"
        assert done["prompt_tokens"] == 5
        assert done["total_tokens"] == 12

    async def test_finish_reason_lowercased(self, patch_pool, monkeypatch):
        self._patch_converters(monkeypatch)

        class _FR:
            @staticmethod
            def lower():
                return "length"

        chunks = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="x")], finish_reason=_FR)])]
        client = FakeClient(models=_FakeModels(stream_chunks=chunks))
        patch_pool(client)
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat_sse([{"role": "user", "content": "hi"}], "m"))
        assert out[-1]["finish_reason"] == "length"

    async def test_stream_error_yields_error_chunk(self, patch_pool, monkeypatch):
        self._patch_converters(monkeypatch)
        client = FakeClient(models=_FakeModels(stream_error=RuntimeError("stream boom")))
        patch_pool(client)
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat_sse([{"role": "user", "content": "hi"}], "m"))
        assert len(out) == 1
        assert out[0]["chunk_type"] == "error"
        assert "stream boom" in out[0]["error"]


# --------------------------------------------------------------------------- #
# stream_chat_with_typewriter_effect()
# --------------------------------------------------------------------------- #
async def _noop_sleep(_delay):
    return None


class TestTypewriter:
    async def test_emits_per_character_then_done(self, monkeypatch):
        handler = ChatHandler(api_key="k")

        async def _fake_chat(messages, model, **kwargs):
            return {
                "content": "ab",
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                "finish_reason": "stop",
            }

        monkeypatch.setattr(handler, "chat", _fake_chat)
        monkeypatch.setattr(ch_mod.asyncio, "sleep", _noop_sleep)

        out = await _collect(
            handler.stream_chat_with_typewriter_effect(
                [{"role": "user", "content": "x"}], "m", delay=0
            )
        )
        chars = [c["content"] for c in out if c["chunk_type"] == "content"]
        assert chars == ["a", "b"]
        assert out[-1]["chunk_type"] == "done"
        assert out[-1]["total_tokens"] == 3

    async def test_error_path_yields_error_chunk(self, monkeypatch):
        handler = ChatHandler(api_key="k")

        async def _boom(messages, model, **kwargs):
            raise RuntimeError("chat failed")

        monkeypatch.setattr(handler, "chat", _boom)
        out = await _collect(
            handler.stream_chat_with_typewriter_effect([{"role": "user", "content": "x"}], "m")
        )
        assert out[0]["chunk_type"] == "error"
        assert "chat failed" in out[0]["error"]


# --------------------------------------------------------------------------- #
# stream_chat() — the async function-call loop
# --------------------------------------------------------------------------- #
def _patch_stream_config(monkeypatch):
    monkeypatch.setattr(
        ch_mod.ConfigBuilder, "build_generate_config_with_tools",
        lambda **k: {"_cfg": True},
    )


def _install_async_client(patch_pool, batches):
    async_chat = _FakeAsyncChat(batches)
    client = FakeClient(async_chat=async_chat)
    pool = patch_pool(client)
    return client, async_chat, pool


def _silence_progress(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(ch_mod.progress_tracker, "send_progress", _noop)
    monkeypatch.setattr(ch_mod.progress_tracker, "send_complete", _noop)
    monkeypatch.setattr(ch_mod.progress_tracker, "send_error", _noop)


class TestStreamChatValidation:
    async def test_empty_messages_yields_error(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        _install_async_client(patch_pool, [[]])
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([], "m"))
        assert out[0]["chunk_type"] == "error"
        assert "non-empty list" in out[0]["error"]

    async def test_bad_model_yields_error(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        _install_async_client(patch_pool, [[]])
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], ""))
        assert out[0]["chunk_type"] == "error"
        assert "model must be" in out[0]["error"]


class TestStreamChatContent:
    async def test_content_and_reasoning_chunks(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        chunk = FakeChunk(
            candidates=[FakeCandidate(
                parts=[
                    FakePart(text="thinking...", thought=True),
                    FakePart(text="answer"),
                ],
                finish_reason=1,
            )],
            usage=FakeUsage(prompt=3, completion=4, total=7),
        )
        _, async_chat, _ = _install_async_client(patch_pool, [[chunk]])
        handler = ChatHandler(api_key="k")

        messages = [
            {"role": "user", "content": "old"},
            {"role": "model", "content": "prev"},
            {"role": "user", "content": "now"},
        ]
        out = await _collect(handler.stream_chat(messages, "gemini-2.0-flash"))

        kinds = [c["chunk_type"] for c in out]
        assert "reasoning" in kinds
        assert "content" in kinds
        reasoning = next(c for c in out if c["chunk_type"] == "reasoning")
        assert reasoning["content"] == "thinking..."
        content = next(c for c in out if c["chunk_type"] == "content")
        assert content["content"] == "answer"
        done = out[-1]
        assert done["chunk_type"] == "done"
        assert done["finish_reason"] == "stop"
        assert done["total_tokens"] == 7
        # exactly one batch consumed
        assert len(async_chat._batches) == 0
        # current message content is the plain string of the last message
        assert async_chat.sent_messages[0] == "now"

    async def test_attachments_build_multimodal_parts(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        chunk = FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])
        _, async_chat, _ = _install_async_client(patch_pool, [[chunk]])
        handler = ChatHandler(api_key="k")
        raw = base64.b64encode(b"img").decode()
        messages = [{
            "role": "user",
            "content": "describe",
            "attachments": [{"base64Data": raw, "mimeType": "image/png"}],
        }]
        out = await _collect(handler.stream_chat(messages, "m"))
        assert out[-1]["chunk_type"] == "done"
        # message was a list of parts (attachment part + text part)
        sent = async_chat.sent_messages[0]
        assert isinstance(sent, list)
        assert len(sent) == 2

    async def test_top_level_error_yields_error_chunk(self, monkeypatch):
        _patch_stream_config(monkeypatch)

        class _BadPool:
            def get_client(self, **kwargs):
                raise RuntimeError("client init failed")

        monkeypatch.setattr(ch_mod, "get_client_pool", lambda: _BadPool())
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m"))
        assert out[-1]["chunk_type"] == "error"
        assert "client init failed" in out[-1]["error"]


class TestStreamChatFunctionCalls:
    async def test_browser_tool_success_with_progress(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        # iteration 1: a function_call; iteration 2: plain content (loop exit)
        fc = FakeFunctionCall(name="web_search", args={"query": "cats"}, call_id="c1")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="done")], finish_reason=1)])]
        _, async_chat, _ = _install_async_client(patch_pool, [batch1, batch2])

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS",
            {"web_search": lambda **kw: "search results text"},
            raising=False,
        )
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(
            handler.stream_chat([{"role": "user", "content": "find cats"}], "m", user_id="u1")
        )

        types_seen = [c["chunk_type"] for c in out]
        assert "tool_call" in types_seen
        assert "tool_result" in types_seen
        tool_call = next(c for c in out if c["chunk_type"] == "tool_call")
        assert tool_call["tool_name"] == "web_search"
        assert tool_call["browser_operation_id"].startswith("browser:u1:web_search:")
        tool_result = next(c for c in out if c["chunk_type"] == "tool_result")
        assert "search results text" in tool_result["tool_result"]
        # second batch sent function_response parts back to model
        assert isinstance(async_chat.sent_messages[1], list)
        assert out[-1]["chunk_type"] == "done"

    async def test_function_call_args_are_summarized_in_logs(self, patch_pool, monkeypatch, caplog):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(
            name="web_search",
            args={"query": "private query secret-token"},
            call_id="call-secret-token",
        )
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="done")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        import app.services.gemini.common.browser as browser_mod

        monkeypatch.setattr(
            browser_mod,
            "AVAILABLE_TOOLS",
            {"web_search": lambda **kw: "search results text"},
            raising=False,
        )
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        with caplog.at_level(logging.INFO, logger="app.services.gemini.common.chat_handler"):
            out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m"))

        tool_call = next(c for c in out if c["chunk_type"] == "tool_call")
        assert tool_call["tool_args"]["query"] == "private query secret-token"

        records = [
            record
            for record in caplog.records
            if record.name == "app.services.gemini.common.chat_handler"
        ]
        assert records
        assert all(record.exc_info is None for record in records)
        log_text = "\n".join(record.getMessage() for record in records)
        assert "<redacted function_args; length=" in log_text
        assert "<redacted function_call_id; length=" in log_text
        assert "secret-token" not in log_text

    async def test_async_tool_and_dict_result_with_error(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="read_webpage", args={"url": "http://x"}, call_id="c2")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        async def _async_tool(**kw):
            return {"error": "page blocked"}

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"read_webpage": _async_tool}, raising=False
        )
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(
            handler.stream_chat([{"role": "user", "content": "read"}], "m", user_id="u1")
        )
        tool_result = next(c for c in out if c["chunk_type"] == "tool_result")
        assert tool_result["tool_error"] == "page blocked"

    async def test_dict_result_with_output_and_screenshot_upload(self, patch_pool, monkeypatch):
        """selenium_browse returns dict with content + screenshot; upload path runs."""
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="selenium_browse", args={"url": "http://x"}, call_id="s1")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        screenshot_b64 = base64.b64encode(b"PNGBYTES").decode()

        async def _selenium(**kw):
            # user_id is injected by the handler for selenium_browse
            assert kw.get("user_id") == "u1"
            return {"content": "page text", "screenshot": screenshot_b64}

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"selenium_browse": _selenium}, raising=False
        )

        # patch storage upload to succeed
        import app.routers.storage as storage_mod

        async def _upload(*, content, filename, content_type, user_id):
            assert user_id == "u1"
            return {"success": True, "url": "https://cdn/screenshot.png"}

        monkeypatch.setattr(storage_mod, "upload_to_active_storage_async", _upload, raising=False)
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(
            handler.stream_chat([{"role": "user", "content": "browse"}], "m", user_id="u1")
        )
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert tr["screenshot_url"] == "https://cdn/screenshot.png"
        assert "page text" in tr["tool_result"]

    async def test_screenshot_upload_failure_falls_back_to_base64(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="selenium_browse", args={"url": "http://x"}, call_id="s2")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        small_b64 = base64.b64encode(b"tiny").decode()

        async def _selenium(**kw):
            return {"content": "txt", "screenshot": small_b64}

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"selenium_browse": _selenium}, raising=False
        )
        import app.routers.storage as storage_mod

        async def _upload(*, content, filename, content_type, user_id):
            return {"success": False, "error": "quota"}

        monkeypatch.setattr(storage_mod, "upload_to_active_storage_async", _upload, raising=False)
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(
            handler.stream_chat([{"role": "user", "content": "browse"}], "m", user_id="u1")
        )
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        # upload failed and screenshot small → base64 fallback embedded
        assert tr.get("screenshot") == small_b64

    async def test_screenshot_upload_raises_is_swallowed(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="selenium_browse", args={"url": "http://x"}, call_id="s4")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        b64 = base64.b64encode(b"shot").decode()

        async def _selenium(**kw):
            return {"content": "txt", "screenshot": b64}

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"selenium_browse": _selenium}, raising=False
        )
        import app.routers.storage as storage_mod

        async def _upload(*, content, filename, content_type, user_id):
            raise RuntimeError("storage exploded")

        monkeypatch.setattr(storage_mod, "upload_to_active_storage_async", _upload, raising=False)
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        # upload error is logged but does not crash the stream
        out = await _collect(
            handler.stream_chat([{"role": "user", "content": "x"}], "m", user_id="u1")
        )
        assert out[-1]["chunk_type"] == "done"
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert "txt" in tr["tool_result"]

    async def test_screenshot_without_user_id_uses_base64(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="selenium_browse", args={"url": "http://x"}, call_id="s3")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        small_b64 = base64.b64encode(b"tiny").decode()

        def _selenium(**kw):
            return {"content": "txt", "screenshot": small_b64}

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"selenium_browse": _selenium}, raising=False
        )
        _silence_progress(monkeypatch)
        handler = ChatHandler(api_key="k")
        # no user_id → no upload, base64 used directly
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m"))
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert tr.get("screenshot") == small_b64

    async def test_tool_raises_exception_yields_error_result(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="web_search", args={"query": "x"}, call_id="c3")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        def _boom(**kw):
            raise ValueError("tool exploded")

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"web_search": _boom}, raising=False
        )
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(
            handler.stream_chat([{"role": "user", "content": "x"}], "m", user_id="u1")
        )
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert "tool exploded" in tr["tool_error"]

    async def test_unknown_function_yields_error_result(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="nonexistent_tool", args={}, call_id="c4")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="fin")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(browser_mod, "AVAILABLE_TOOLS", {}, raising=False)
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m"))
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert "Unknown function" in tr["tool_error"]

    async def test_direct_function_calls_path(self, patch_pool, monkeypatch):
        """chunk.function_calls (not via candidates.parts) also detected."""
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="web_search", args={"q": "1"}, call_id="d1")
        batch1 = [FakeChunk(
            candidates=[FakeCandidate(parts=[], finish_reason=1)],
            function_calls=[fc],
        )]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS", {"web_search": lambda **kw: "r"}, raising=False
        )
        _silence_progress(monkeypatch)
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m", user_id="u"))
        assert any(c["chunk_type"] == "tool_call" for c in out)

    async def test_duplicate_function_calls_deduped(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="web_search", args={"q": "1"}, call_id="dup")
        # same call appears twice in the same stream
        batch1 = [FakeChunk(candidates=[FakeCandidate(
            parts=[FakePart(function_call=fc), FakePart(function_call=fc)],
            finish_reason=1,
        )])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        import app.services.gemini.common.browser as browser_mod
        calls = []
        monkeypatch.setattr(
            browser_mod, "AVAILABLE_TOOLS",
            {"web_search": lambda **kw: calls.append(1) or "r"},
            raising=False,
        )
        _silence_progress(monkeypatch)
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m", user_id="u"))
        tool_calls = [c for c in out if c["chunk_type"] == "tool_call"]
        assert len(tool_calls) == 1  # deduped
        assert len(calls) == 1


class TestStreamChatMCP:
    async def test_preloaded_declarations_and_mcp_tool_call(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="mcp_tool", args={"a": 1}, call_id="m1")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])

        # browser tools empty so the MCP branch is taken
        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(browser_mod, "AVAILABLE_TOOLS", {}, raising=False)

        class _MCPResult:
            success = True
            is_error = False
            error = None
            result = {"data": "mcp output"}

        class _MCPManager:
            async def call_tool(self, *, session_id, tool_name, arguments):
                return _MCPResult()

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m",
            mcp_session_id="sess-1",
            additional_function_declarations=[
                {"name": "mcp_tool", "description": "d", "parameters": {}}
            ],
        ))
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert tr["tool_name"] == "mcp_tool"
        assert "mcp output" in tr["tool_result"]

    async def test_mcp_tool_returns_error_result(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="mcp_tool", args={}, call_id="m1b")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(browser_mod, "AVAILABLE_TOOLS", {}, raising=False)

        class _MCPResult:
            success = False
            is_error = True
            error = "mcp tool error text"
            result = None

        class _MCPManager:
            async def call_tool(self, *, session_id, tool_name, arguments):
                return _MCPResult()

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m",
            mcp_session_id="sess-1",
            additional_function_declarations=[{"name": "mcp_tool", "parameters": {}}],
        ))
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert tr["tool_error"] == "mcp tool error text"

    async def test_mcp_tool_call_raises(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(name="mcp_tool", args={}, call_id="m2")
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(browser_mod, "AVAILABLE_TOOLS", {}, raising=False)

        class _MCPManager:
            async def call_tool(self, *, session_id, tool_name, arguments):
                raise RuntimeError("mcp down")

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m",
            mcp_session_id="sess-1",
            additional_function_declarations=[{"name": "mcp_tool", "parameters": {}}],
        ))
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert "mcp down" in tr["tool_error"]

    async def test_mcp_tool_failure_log_is_summarized(self, patch_pool, monkeypatch, caplog):
        _patch_stream_config(monkeypatch)
        fc = FakeFunctionCall(
            name="mcp_tool",
            args={"apiKey": "secret-token"},
            call_id="mcp-call-secret-token",
        )
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(function_call=fc)], finish_reason=1)])]
        batch2 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1, batch2])
        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(browser_mod, "AVAILABLE_TOOLS", {}, raising=False)

        class _MCPManager:
            async def call_tool(self, *, session_id, tool_name, arguments):
                raise RuntimeError("mcp echoed secret-token")

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())
        _silence_progress(monkeypatch)

        handler = ChatHandler(api_key="k")
        with caplog.at_level(logging.ERROR, logger="app.services.gemini.common.chat_handler"):
            out = await _collect(handler.stream_chat(
                [{"role": "user", "content": "x"}], "m",
                mcp_session_id="sess-1",
                additional_function_declarations=[{"name": "mcp_tool", "parameters": {}}],
            ))
        tr = next(c for c in out if c["chunk_type"] == "tool_result")
        assert "secret-token" in tr["tool_error"]

        records = [
            record
            for record in caplog.records
            if record.name == "app.services.gemini.common.chat_handler"
        ]
        assert records
        assert all(record.exc_info is None for record in records)
        log_text = "\n".join(record.getMessage() for record in records)
        assert "<redacted mcp_function_error; length=" in log_text
        assert "secret-token" not in log_text

    async def test_mcp_session_load_tools_path(self, patch_pool, monkeypatch):
        """No preloaded declarations: tools fetched via get_gemini_tools."""
        _patch_stream_config(monkeypatch)
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="hi")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1])
        import app.services.gemini.common.browser as browser_mod
        monkeypatch.setattr(browser_mod, "AVAILABLE_TOOLS", {}, raising=False)

        class _MCPManager:
            async def get_gemini_tools(self, session_id):
                return [{"function_declarations": [{"name": "t1", "description": "d", "parameters": {}}]}]

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())

        captured = {}

        def _cfg(**k):
            captured.update(k)
            return {}

        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config_with_tools", _cfg)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m", mcp_session_id="sess-9",
        ))
        assert out[-1]["chunk_type"] == "done"
        # declarations from MCP were forwarded into config builder
        decls = captured.get("additional_function_declarations")
        assert decls and decls[0]["name"] == "t1"

    async def test_mcp_load_failure_is_swallowed(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="hi")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1])

        class _MCPManager:
            async def get_gemini_tools(self, session_id):
                raise RuntimeError("mcp load failed")

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m", mcp_session_id="sess-x",
        ))
        # despite MCP failure, the stream still completes
        assert out[-1]["chunk_type"] == "done"

    async def test_preloaded_declarations_skip_invalid_entries(self, patch_pool, monkeypatch):
        """Non-dict / nameless preloaded declarations are skipped."""
        _patch_stream_config(monkeypatch)
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="hi")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1])

        captured = {}

        def _cfg(**k):
            captured.update(k)
            return {}

        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config_with_tools", _cfg)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m",
            additional_function_declarations=[
                "not-a-dict",                       # skipped (not dict)
                {"description": "no name"},         # skipped (no name)
                {"name": 123},                       # skipped (name not str)
                {"name": "good_tool", "parameters": {}},  # kept
            ],
        ))
        assert out[-1]["chunk_type"] == "done"
        decls = captured.get("additional_function_declarations")
        assert [d["name"] for d in decls] == ["good_tool"]

    async def test_preloaded_with_session_gets_manager(self, patch_pool, monkeypatch):
        """Preloaded declarations + session id → manager fetched for tool calls."""
        _patch_stream_config(monkeypatch)
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="hi")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1])

        import app.services.mcp.mcp_manager as mcp_mod
        sentinel = object()
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: sentinel)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m",
            mcp_session_id="sess-7",
            additional_function_declarations=[{"name": "t", "parameters": {}}],
        ))
        assert out[-1]["chunk_type"] == "done"

    async def test_preloaded_manager_fetch_failure_swallowed(self, patch_pool, monkeypatch):
        _patch_stream_config(monkeypatch)
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="hi")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1])

        import app.services.mcp.mcp_manager as mcp_mod

        def _boom():
            raise RuntimeError("manager down")

        monkeypatch.setattr(mcp_mod, "get_mcp_manager", _boom)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m",
            mcp_session_id="sess-7",
            additional_function_declarations=[{"name": "t", "parameters": {}}],
        ))
        # manager fetch failure is logged but stream completes
        assert out[-1]["chunk_type"] == "done"

    async def test_mcp_load_skips_invalid_tool_groups(self, patch_pool, monkeypatch):
        """get_gemini_tools returns malformed entries that must be skipped."""
        _patch_stream_config(monkeypatch)
        batch1 = [FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="hi")], finish_reason=1)])]
        _install_async_client(patch_pool, [batch1])

        class _MCPManager:
            async def get_gemini_tools(self, session_id):
                return [
                    "not-a-dict",  # skipped
                    {"function_declarations": [
                        "bad-decl",           # skipped (not dict)
                        {"description": "x"},  # skipped (no name)
                        {"name": "ok", "parameters": {}},  # kept
                    ]},
                ]

        import app.services.mcp.mcp_manager as mcp_mod
        monkeypatch.setattr(mcp_mod, "get_mcp_manager", lambda: _MCPManager())

        captured = {}

        def _cfg(**k):
            captured.update(k)
            return {}

        monkeypatch.setattr(ch_mod.ConfigBuilder, "build_generate_config_with_tools", _cfg)

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat(
            [{"role": "user", "content": "x"}], "m", mcp_session_id="sess-3",
        ))
        assert out[-1]["chunk_type"] == "done"
        decls = captured.get("additional_function_declarations")
        assert [d["name"] for d in decls] == ["ok"]


class TestStreamChatChunkExtractionGuards:
    async def test_candidate_access_error_is_swallowed(self, patch_pool, monkeypatch):
        """A chunk whose candidate parts raise on access hits the warning path
        but the stream still completes."""
        _patch_stream_config(monkeypatch)

        class _ExplodingCandidates(list):
            def __getitem__(self, idx):
                raise RuntimeError("candidate access boom")

        bad_chunk = FakeChunk(candidates=_ExplodingCandidates([1]))
        good_chunk = FakeChunk(candidates=[FakeCandidate(parts=[FakePart(text="ok")], finish_reason=1)])
        _install_async_client(patch_pool, [[bad_chunk, good_chunk]])

        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m"))
        # warnings logged internally; stream finishes with the good chunk's text
        contents = [c["content"] for c in out if c["chunk_type"] == "content"]
        assert "ok" in contents
        assert out[-1]["chunk_type"] == "done"

    async def test_usage_extraction_error_is_swallowed(self, patch_pool, monkeypatch):
        """usage_metadata whose attribute access raises is tolerated."""
        _patch_stream_config(monkeypatch)

        class _BadUsage:
            @property
            def prompt_token_count(self):
                raise RuntimeError("usage boom")

        chunk = FakeChunk(
            candidates=[FakeCandidate(parts=[FakePart(text="x")], finish_reason=1)],
            usage=_BadUsage(),
        )
        _install_async_client(patch_pool, [[chunk]])
        handler = ChatHandler(api_key="k")
        out = await _collect(handler.stream_chat([{"role": "user", "content": "x"}], "m"))
        # usage stays at defaults (0) since extraction failed
        assert out[-1]["chunk_type"] == "done"
        assert out[-1]["prompt_tokens"] == 0
