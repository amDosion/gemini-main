"""Thorough unit tests for the Gemini ``shared`` package.

Covers three modules:
  * ``app.services.gemini.shared.config``   - config models, env loading, validation, context
  * ``app.services.gemini.shared.adapters`` - legacy <-> official SDK adapters
  * ``app.services.gemini.shared.utils``    - MIME / validation / retry / transform helpers

These tests exercise real branch behavior (happy paths, error paths, edge cases).
Only external boundaries are faked: the "legacy service" objects passed to adapters,
the filesystem (via pytest ``tmp_path``), and environment variables (via monkeypatch).

Several tests are *characterization* tests for pre-existing bugs in the source. They
assert the current (buggy) behavior so the bug is documented and pinned without
modifying source under test:

  - ``LegacyToOfficialAdapter.adapt_chat_response`` calls ``usage_metadata.get(...)``
    but the official SDK coerces a dict into a pydantic model without ``.get`` ->
    raises ``AttributeError`` whenever usage metadata is present.
  - ``OfficialToLegacyAdapter.generate_content`` references a bare ``Content`` name
    (instead of ``genai_types.Content``) -> ``NameError`` for list-of-Content input.
  - ``OfficialToLegacyAdapter.upload_file`` defaults ``create_time``/``update_time``
    to ``''`` which fails pydantic datetime validation when the legacy response
    omits valid ISO timestamps.
"""

import pytest

from app.services.gemini.shared import config as config_mod
from app.services.gemini.shared import utils as utils_mod
from app.services.gemini.shared import adapters as adapters_mod
from app.services.gemini.shared.config import (
    GeminiConfig,
    ApiConfig,
    ConfigContext,
    load_config_from_env,
    get_default_config,
    validate_config,
    get_global_config,
    set_global_config,
)
from app.services.gemini.shared.adapters import (
    LegacyToOfficialAdapter,
    OfficialToLegacyAdapter,
    create_legacy_adapter,
    create_official_adapter,
)
from google.genai import types as genai_types


# ---------------------------------------------------------------------------
# Test doubles (external boundary only)
# ---------------------------------------------------------------------------
class FakeLegacyService:
    """In-memory stand-in for the legacy GoogleService.

    Records the last chat/upload call so tests can assert the translation done
    by ``OfficialToLegacyAdapter`` without any real network or SDK.
    """

    def __init__(self, chat_response=None, upload_response=None):
        self._chat_response = chat_response if chat_response is not None else {"choices": []}
        self._upload_response = upload_response if upload_response is not None else {}
        self.chat_calls = []
        self.upload_calls = []

    async def chat(self, messages, model, **kwargs):
        self.chat_calls.append({"messages": messages, "model": model, "kwargs": kwargs})
        return self._chat_response

    async def upload_file(self, file_path, display_name, mime_type):
        self.upload_calls.append(
            {"file_path": file_path, "display_name": display_name, "mime_type": mime_type}
        )
        return self._upload_response


VALID_TS = "2024-01-01T00:00:00Z"


# ===========================================================================
# config.py
# ===========================================================================
class TestConfigModels:
    def test_default_geminiconfig_nested_defaults(self):
        cfg = GeminiConfig()
        assert cfg.api.location == "us-central1"
        assert cfg.api.default_chat_model == "gemini-2.5-flash"
        assert cfg.http.api_version == "v1beta"
        assert cfg.http.retry.attempts == 3
        assert 429 in cfg.http.retry.http_status_codes
        assert cfg.performance.max_connections == 100
        assert cfg.logging.level == "INFO"
        assert cfg.enable_official_sdk is True
        assert "image/png" in cfg.allowed_file_types

    def test_retry_status_codes_are_independent_lists(self):
        # default_factory must not share mutable state across instances
        a = GeminiConfig()
        b = GeminiConfig()
        a.http.retry.http_status_codes.append(418)
        assert 418 not in b.http.retry.http_status_codes


class TestLoadConfigFromEnv:
    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        for var in (
            "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_PROJECT", "GOOGLE_CLOUD_PROJECT",
            "GEMINI_LOCATION", "GOOGLE_CLOUD_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS",
            "GEMINI_API_VERSION", "GEMINI_TIMEOUT", "GEMINI_BASE_URL",
            "GEMINI_ENABLE_OFFICIAL_SDK", "GEMINI_ENABLE_LEGACY_FALLBACK",
            "GEMINI_LOG_LEVEL", "GEMINI_LOG_REQUESTS",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_empty_env_returns_defaults(self):
        cfg = load_config_from_env()
        assert cfg.api.api_key is None
        assert cfg.api.project is None
        assert cfg.enable_official_sdk is True

    def test_gemini_api_key_takes_precedence_over_google(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "primary")
        monkeypatch.setenv("GOOGLE_API_KEY", "fallback")
        cfg = load_config_from_env()
        assert cfg.api.api_key == "primary"

    def test_google_api_key_used_when_gemini_absent(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "fallback-only")
        cfg = load_config_from_env()
        assert cfg.api.api_key == "fallback-only"

    def test_project_location_credentials_loaded(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        monkeypatch.setenv("GEMINI_LOCATION", "europe-west1")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/creds.json")
        cfg = load_config_from_env()
        assert cfg.api.project == "proj-123"
        assert cfg.api.location == "europe-west1"
        assert cfg.api.credentials_path == "/path/creds.json"

    def test_http_overrides(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_VERSION", "v1")
        monkeypatch.setenv("GEMINI_TIMEOUT", "5000")
        monkeypatch.setenv("GEMINI_BASE_URL", "https://proxy.example")
        cfg = load_config_from_env()
        assert cfg.http.api_version == "v1"
        assert cfg.http.timeout == 5000
        assert cfg.http.base_url == "https://proxy.example"

    def test_invalid_timeout_is_warned_and_keeps_default(self, monkeypatch):
        monkeypatch.setenv("GEMINI_TIMEOUT", "not-a-number")
        cfg = load_config_from_env()
        # default 30000 retained because int() raised ValueError
        assert cfg.http.timeout == 30000

    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("1", True), ("yes", True),
        ("false", False), ("0", False), ("no", False), ("garbage", False),
    ])
    def test_feature_flag_truthiness(self, monkeypatch, raw, expected):
        monkeypatch.setenv("GEMINI_ENABLE_OFFICIAL_SDK", raw)
        cfg = load_config_from_env()
        assert cfg.enable_official_sdk is expected

    def test_legacy_fallback_flag(self, monkeypatch):
        monkeypatch.setenv("GEMINI_ENABLE_LEGACY_FALLBACK", "no")
        cfg = load_config_from_env()
        assert cfg.enable_legacy_fallback is False

    def test_log_level_uppercased_and_log_requests(self, monkeypatch):
        monkeypatch.setenv("GEMINI_LOG_LEVEL", "debug")
        monkeypatch.setenv("GEMINI_LOG_REQUESTS", "yes")
        cfg = load_config_from_env()
        assert cfg.logging.level == "DEBUG"
        assert cfg.logging.enable_request_logging is True

    def test_get_default_config_delegates_to_env_loader(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "abc")
        cfg = get_default_config()
        assert cfg.api.api_key == "abc"


class TestValidateConfig:
    def test_missing_key_and_project(self):
        errors = validate_config(GeminiConfig())
        assert any("api_key or project" in e for e in errors)

    def test_api_key_only_is_valid(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        assert validate_config(cfg) == []

    def test_project_without_location_reports_error(self):
        cfg = GeminiConfig(api=ApiConfig(project="p", location=""))
        errors = validate_config(cfg)
        assert any("location is required" in e for e in errors)

    def test_non_positive_timeout(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        cfg.http.timeout = 0
        assert any("timeout must be positive" in e for e in validate_config(cfg))

    def test_non_positive_connect_timeout(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        cfg.performance.connect_timeout = -1
        assert any("connect_timeout must be positive" in e for e in validate_config(cfg))

    def test_non_positive_file_size(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        cfg.max_file_size_mb = 0
        assert any("max_file_size_mb must be positive" in e for e in validate_config(cfg))

    def test_non_positive_rpm(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        cfg.performance.requests_per_minute = 0
        assert any("requests_per_minute must be positive" in e for e in validate_config(cfg))

    def test_multiple_errors_accumulate(self):
        cfg = GeminiConfig()  # no key/project
        cfg.http.timeout = 0
        cfg.max_file_size_mb = -5
        errors = validate_config(cfg)
        assert len(errors) >= 3


class TestConfigContext:
    def test_create_with_explicit_config_no_vertex(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        ctx = ConfigContext.create(cfg)
        assert ctx.is_vertex_ai is False
        assert ctx.is_official_sdk is True
        assert ctx.should_use_official_sdk() is True
        assert ctx.should_fallback_to_legacy() is True

    def test_create_detects_vertex_when_project_present(self):
        cfg = GeminiConfig(api=ApiConfig(project="p"))
        ctx = ConfigContext.create(cfg)
        assert ctx.is_vertex_ai is True

    def test_create_with_none_uses_default(self, monkeypatch):
        monkeypatch.delenv("GEMINI_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        ctx = ConfigContext.create(None)
        assert isinstance(ctx.config, GeminiConfig)

    def test_base_url_prefers_explicit_base_url(self):
        cfg = GeminiConfig(api=ApiConfig(project="p"))
        cfg.http.base_url = "https://override.example"
        ctx = ConfigContext.create(cfg)
        assert ctx.get_api_base_url() == "https://override.example"

    def test_base_url_vertex_branch(self):
        cfg = GeminiConfig(api=ApiConfig(project="p"))
        ctx = ConfigContext.create(cfg)
        assert ctx.get_api_base_url() == cfg.api.vertex_api_base

    def test_base_url_gemini_branch(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        ctx = ConfigContext.create(cfg)
        assert ctx.get_api_base_url() == cfg.api.gemini_api_base

    @pytest.mark.parametrize("task,attr", [
        ("chat", "default_chat_model"),
        ("image", "default_image_model"),
        ("embedding", "default_embedding_model"),
        ("unknown-task", "default_chat_model"),  # falls back to chat
    ])
    def test_get_default_model(self, task, attr):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"))
        ctx = ConfigContext.create(cfg)
        assert ctx.get_default_model(task) == getattr(cfg.api, attr)

    def test_should_use_official_sdk_reflects_flag(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"), enable_official_sdk=False)
        ctx = ConfigContext.create(cfg)
        assert ctx.should_use_official_sdk() is False

    def test_should_fallback_reflects_flag(self):
        cfg = GeminiConfig(api=ApiConfig(api_key="k"), enable_legacy_fallback=False)
        ctx = ConfigContext.create(cfg)
        assert ctx.should_fallback_to_legacy() is False


class TestGlobalConfig:
    def test_get_global_config_lazily_initializes(self, monkeypatch):
        # reset module global, then ensure a value is produced
        monkeypatch.setattr(config_mod, "_global_config", None, raising=False)
        cfg = get_global_config()
        assert isinstance(cfg, GeminiConfig)
        # second call returns the same cached instance
        assert get_global_config() is cfg

    def test_set_global_config_overrides(self, monkeypatch):
        monkeypatch.setattr(config_mod, "_global_config", None, raising=False)
        custom = GeminiConfig(api=ApiConfig(api_key="custom"))
        set_global_config(custom)
        assert get_global_config() is custom
        assert get_global_config().api.api_key == "custom"


# ===========================================================================
# utils.py
# ===========================================================================
class TestValidateApiKey:
    def test_canonical_google_key(self):
        assert utils_mod.validate_api_key("AIza" + "b" * 35) is True

    def test_aiza_prefix_wrong_length_fails_first_check(self):
        # 'AIzaShort' does not match the 39-char rule and is too short for the generic rule
        assert utils_mod.validate_api_key("AIzaShort") is False

    def test_generic_alnum_min_length(self):
        assert utils_mod.validate_api_key("a" * 20) is True

    def test_generic_with_dashes_and_underscores(self):
        assert utils_mod.validate_api_key("abc-def_" + "g" * 15) is True

    def test_too_short_generic(self):
        assert utils_mod.validate_api_key("short") is False

    def test_symbols_rejected(self):
        assert utils_mod.validate_api_key("!!!" + "a" * 20) is False

    @pytest.mark.parametrize("bad", [None, "", 12345, b"bytes"])
    def test_non_string_inputs(self, bad):
        assert utils_mod.validate_api_key(bad) is False


class TestValidateMimeType:
    def test_exact_match(self):
        assert utils_mod.validate_mime_type("text/plain", ["text/plain"]) is True

    def test_wildcard_match(self):
        assert utils_mod.validate_mime_type("image/png", ["image/*"]) is True

    def test_no_match(self):
        assert utils_mod.validate_mime_type("application/pdf", ["image/*", "text/plain"]) is False

    def test_empty_mime(self):
        assert utils_mod.validate_mime_type("", ["image/*"]) is False

    def test_empty_allowed_list(self):
        assert utils_mod.validate_mime_type("image/png", []) is False


class TestDetectMimeType:
    def test_missing_file_returns_none(self):
        assert utils_mod.detect_mime_type("/definitely/not/here.png") is None

    def test_known_extension_via_mimetypes(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("hello")
        assert utils_mod.detect_mime_type(f) == "text/plain"

    def test_unknown_extension_falls_back_to_octet_stream(self, tmp_path):
        f = tmp_path / "thing.zzzunknown"
        f.write_bytes(b"data")
        result = utils_mod.detect_mime_type(f)
        # mimetypes returns None for an unknown extension -> manual map default
        assert result == "application/octet-stream"

    def test_custom_extension_map_entry(self, tmp_path):
        # .mov resolves to video/quicktime either via mimetypes or the manual map
        f = tmp_path / "clip.mov"
        f.write_bytes(b"data")
        assert utils_mod.detect_mime_type(f) == "video/quicktime"


class TestValidateFileSize:
    def test_within_limit(self, tmp_path):
        f = tmp_path / "small.bin"
        f.write_bytes(b"0" * 100)
        assert utils_mod.validate_file_size(f, max_size_mb=1) is True

    def test_exceeds_limit(self, tmp_path):
        f = tmp_path / "big.bin"
        f.write_bytes(b"0" * (2 * 1024 * 1024))
        assert utils_mod.validate_file_size(f, max_size_mb=1) is False

    def test_missing_file(self):
        assert utils_mod.validate_file_size("/no/such/file") is False


class TestHashAndBase64:
    def test_calculate_file_hash_sha256(self, tmp_path):
        f = tmp_path / "h.bin"
        f.write_bytes(b"abc")
        import hashlib
        assert utils_mod.calculate_file_hash(f) == hashlib.sha256(b"abc").hexdigest()

    def test_calculate_file_hash_md5(self, tmp_path):
        f = tmp_path / "h.bin"
        f.write_bytes(b"abc")
        import hashlib
        assert utils_mod.calculate_file_hash(f, algorithm="md5") == hashlib.md5(b"abc").hexdigest()

    def test_base64_roundtrip(self):
        original = b"\x00\x01binary\xff"
        encoded = utils_mod.encode_base64(original)
        assert isinstance(encoded, str)
        assert utils_mod.decode_base64(encoded) == original


class TestSanitizeFilename:
    def test_replaces_unsafe_chars(self):
        assert utils_mod.sanitize_filename('a<>:"/\\|?*b') == "a_________b"

    def test_strips_leading_trailing_dots_and_spaces(self):
        assert utils_mod.sanitize_filename("  .name.  ") == "name"

    def test_empty_becomes_placeholder(self):
        assert utils_mod.sanitize_filename("   ...  ") == "unnamed_file"

    def test_long_name_truncated_keeping_extension(self):
        result = utils_mod.sanitize_filename("x" * 300 + ".txt")
        assert len(result) <= 255
        assert result.endswith(".txt")


class TestFormatErrorMessage:
    def test_with_context(self):
        msg = utils_mod.format_error_message(ValueError("boom"), context="loading")
        assert msg == "loading: ValueError: boom"

    def test_without_context(self):
        msg = utils_mod.format_error_message(KeyError("k"))
        assert msg.startswith("KeyError:")


class TestListAndDictHelpers:
    def test_chunk_list_even(self):
        assert utils_mod.chunk_list([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_chunk_list_uneven(self):
        assert utils_mod.chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_chunk_empty(self):
        assert utils_mod.chunk_list([], 3) == []

    def test_deep_merge_nested(self):
        merged = utils_mod.deep_merge_dicts(
            {"a": {"b": 1, "x": 9}, "c": 2},
            {"a": {"d": 3}, "c": 4},
        )
        assert merged == {"a": {"b": 1, "x": 9, "d": 3}, "c": 4}

    def test_deep_merge_does_not_mutate_inputs(self):
        d1 = {"a": {"b": 1}}
        d2 = {"a": {"c": 2}}
        utils_mod.deep_merge_dicts(d1, d2)
        assert d1 == {"a": {"b": 1}}
        assert d2 == {"a": {"c": 2}}

    def test_deep_merge_scalar_overrides_dict(self):
        merged = utils_mod.deep_merge_dicts({"a": {"b": 1}}, {"a": 5})
        assert merged == {"a": 5}


class TestTruncateText:
    def test_shorter_than_max_unchanged(self):
        assert utils_mod.truncate_text("hi", 10) == "hi"

    def test_exactly_max_unchanged(self):
        assert utils_mod.truncate_text("hello", 5) == "hello"

    def test_truncates_with_suffix(self):
        assert utils_mod.truncate_text("hello world", 8) == "hello..."

    def test_custom_suffix(self):
        assert utils_mod.truncate_text("abcdef", 4, suffix="!") == "abc!"


class TestIsUrl:
    @pytest.mark.parametrize("url", [
        "https://example.com",
        "http://example.com/path?q=1",
        "http://localhost:8080",
        "https://127.0.0.1:9000/x",
        "HTTP://EXAMPLE.COM",
    ])
    def test_valid_urls(self, url):
        assert utils_mod.is_url(url) is True

    @pytest.mark.parametrize("text", [
        "not a url",
        "ftp://example.com",
        "example.com",
        "",
        "http://",
    ])
    def test_invalid_urls(self, text):
        assert utils_mod.is_url(text) is False


class TestExtractModelName:
    def test_models_prefix(self):
        assert utils_mod.extract_model_name("models/gemini-2.5-flash") == "gemini-2.5-flash"

    def test_publishers_prefix(self):
        assert utils_mod.extract_model_name("publishers/google/models/gemini-1.5") == "gemini-1.5"

    def test_plain_name_unchanged(self):
        assert utils_mod.extract_model_name("gemini-2.5-flash") == "gemini-2.5-flash"

    def test_path_without_models_keyword_takes_last_segment(self):
        # after stripping no known prefix, '/' present but no 'models' -> last part
        assert utils_mod.extract_model_name("foo/bar/baz") == "baz"

    def test_projects_prefix_with_models_segment(self):
        result = utils_mod.extract_model_name("projects/p/locations/l/models/my-model")
        assert result == "my-model"


class TestRetryWithBackoff:
    async def test_async_success_after_retries(self):
        attempts = {"n": 0}

        async def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise ValueError("transient")
            return "done"

        result = await utils_mod.retry_with_backoff(
            flaky, max_attempts=5, initial_delay=0.001, jitter=False
        )
        assert result == "done"
        assert attempts["n"] == 3

    async def test_sync_function_supported(self):
        def double(x):
            return x * 2

        result = await utils_mod.retry_with_backoff(double, 21, max_attempts=2, initial_delay=0.001)
        assert result == 42

    async def test_exhausts_and_raises_last_exception(self):
        async def always_fail():
            raise KeyError("nope")

        with pytest.raises(KeyError):
            await utils_mod.retry_with_backoff(
                always_fail, max_attempts=3, initial_delay=0.001, jitter=False
            )

    async def test_non_matching_exception_raised_immediately(self):
        attempts = {"n": 0}

        async def wrong_type():
            attempts["n"] += 1
            raise TypeError("bad")

        with pytest.raises(TypeError):
            await utils_mod.retry_with_backoff(
                wrong_type, max_attempts=5, retry_on=[ValueError], initial_delay=0.001
            )
        # should not retry on a non-matching exception type
        assert attempts["n"] == 1

    async def test_jitter_branch_executes(self):
        attempts = {"n": 0}

        async def flaky():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        result = await utils_mod.retry_with_backoff(
            flaky, max_attempts=3, initial_delay=0.001, jitter=True
        )
        assert result == "ok"


# ===========================================================================
# adapters.py
# ===========================================================================
class TestLegacyToOfficialAdapterChatRequest:
    def _adapter(self):
        return LegacyToOfficialAdapter(official_client=object())

    def test_string_content_messages(self):
        out = self._adapter().adapt_chat_request(
            [{"role": "user", "content": "hello"}], model="gemini-2.5-flash"
        )
        assert out["model"] == "gemini-2.5-flash"
        assert len(out["contents"]) == 1
        content = out["contents"][0]
        assert content.role == "user"
        assert content.parts[0].text == "hello"

    def test_missing_role_defaults_to_user(self):
        out = self._adapter().adapt_chat_request([{"content": "hi"}], model="m")
        assert out["contents"][0].role == "user"

    def test_list_content_with_strings_and_text_dicts(self):
        out = self._adapter().adapt_chat_request(
            [{"role": "user", "content": ["a", {"text": "b"}]}], model="m"
        )
        parts = out["contents"][0].parts
        texts = [p.text for p in parts]
        assert texts == ["a", "b"]

    def test_list_content_image_url_dict_is_skipped(self):
        out = self._adapter().adapt_chat_request(
            [{"role": "user", "content": [{"image_url": "http://x/y.png"}]}], model="m"
        )
        # image_url branch is a no-op (pass) -> no parts produced
        assert out["contents"][0].parts == []

    def test_non_str_non_list_content_stringified(self):
        out = self._adapter().adapt_chat_request(
            [{"role": "user", "content": 12345}], model="m"
        )
        assert out["contents"][0].parts[0].text == "12345"

    def test_config_parameter_mapping(self):
        out = self._adapter().adapt_chat_request(
            [{"role": "user", "content": "hi"}],
            model="m",
            temperature=0.3,
            max_tokens=128,
            top_p=0.9,
            top_k=7,
            stop=["END"],
        )
        cfg = out["config"]
        assert cfg.temperature == 0.3
        assert cfg.max_output_tokens == 128
        assert cfg.top_p == 0.9
        assert cfg.top_k == 7
        assert cfg.stop_sequences == ["END"]

    def test_config_defaults_when_no_kwargs(self):
        out = self._adapter().adapt_chat_request([{"content": "hi"}], model="m")
        assert out["config"].temperature is None
        assert out["config"].max_output_tokens is None


class TestLegacyToOfficialAdapterChatResponse:
    def _adapter(self):
        return LegacyToOfficialAdapter(official_client=object())

    def test_extracts_text_with_no_usage_metadata(self):
        resp = genai_types.GenerateContentResponse(
            candidates=[
                genai_types.Candidate(
                    content=genai_types.Content(
                        role="model",
                        parts=[genai_types.Part(text="a"), genai_types.Part(text="b")],
                    ),
                    finish_reason="STOP",
                )
            ]
        )
        legacy = self._adapter().adapt_chat_response(resp)
        assert legacy["choices"][0]["message"]["content"] == "ab"
        assert legacy["choices"][0]["message"]["role"] == "assistant"
        # finish_reason comes through as the SDK enum
        assert legacy["choices"][0]["finish_reason"] == genai_types.FinishReason.STOP
        # usage falsy -> empty dict branch
        assert legacy["usage"] == {}

    def test_empty_candidates_yields_empty_content(self):
        resp = genai_types.GenerateContentResponse(candidates=[])
        legacy = self._adapter().adapt_chat_response(resp)
        assert legacy["choices"][0]["message"]["content"] == ""
        assert legacy["choices"][0]["finish_reason"] is None

    def test_usage_metadata_present_raises_attribute_error_characterization(self):
        # CHARACTERIZATION of a real bug: the source calls usage_metadata.get(...),
        # but the SDK coerces the dict to a pydantic model without a .get method.
        resp = genai_types.GenerateContentResponse(
            candidates=[
                genai_types.Candidate(
                    content=genai_types.Content(role="model", parts=[genai_types.Part(text="x")]),
                    finish_reason="STOP",
                )
            ],
            usage_metadata={"total_token_count": 10},
        )
        with pytest.raises(AttributeError):
            self._adapter().adapt_chat_response(resp)


class TestLegacyToOfficialAdapterFiles:
    def _adapter(self):
        return LegacyToOfficialAdapter(official_client=object())

    def test_upload_request_with_all_fields(self):
        out = self._adapter().adapt_file_upload_request(
            "/tmp/a.png", display_name="Pic", mime_type="image/png"
        )
        assert out["file"] == "/tmp/a.png"
        assert out["config"].display_name == "Pic"
        assert out["config"].mime_type == "image/png"

    def test_upload_request_minimal(self):
        out = self._adapter().adapt_file_upload_request("/tmp/a.png")
        assert out["file"] == "/tmp/a.png"
        assert out["config"].display_name is None
        assert out["config"].mime_type is None

    def test_upload_response_mapping(self):
        f = genai_types.File(
            name="files/y",
            display_name="dn",
            mime_type="image/png",
            size_bytes=5,
            uri="uri",
            state="ACTIVE",
            create_time=None,
            update_time=None,
            expiration_time=None,
        )
        out = self._adapter().adapt_file_upload_response(f)
        assert out["name"] == "files/y"
        assert out["display_name"] == "dn"
        assert out["mime_type"] == "image/png"
        assert out["size_bytes"] == 5
        assert out["uri"] == "uri"
        assert out["state"] == genai_types.FileState.ACTIVE


class TestOfficialToLegacyAdapterGenerateContent:
    async def test_string_contents_path(self):
        legacy = FakeLegacyService(
            chat_response={
                "choices": [
                    {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "STOP"}
                ],
                "usage": {"total_token_count": 7},
            }
        )
        adapter = OfficialToLegacyAdapter(legacy)
        resp = await adapter.generate_content("m", "hi there", None)
        # legacy service received a single user message
        assert legacy.chat_calls[0]["messages"] == [{"role": "user", "content": "hi there"}]
        assert resp.candidates[0].content.parts[0].text == "hello"
        assert resp.candidates[0].content.role == "model"

    async def test_config_translated_to_legacy_kwargs(self):
        legacy = FakeLegacyService(chat_response={"choices": []})
        adapter = OfficialToLegacyAdapter(legacy)
        cfg = genai_types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=64,
            top_p=0.8,
            top_k=3,
            stop_sequences=["STOP"],
        )
        await adapter.generate_content("m", "prompt", cfg)
        kwargs = legacy.chat_calls[0]["kwargs"]
        assert kwargs == {
            "temperature": 0.4,
            "max_tokens": 64,
            "top_p": 0.8,
            "top_k": 3,
            "stop": ["STOP"],
        }

    async def test_empty_choices_returns_no_candidates(self):
        legacy = FakeLegacyService(chat_response={"choices": []})
        adapter = OfficialToLegacyAdapter(legacy)
        resp = await adapter.generate_content("m", "x", None)
        assert resp.candidates == []

    async def test_list_of_content_triggers_nameerror_characterization(self):
        # CHARACTERIZATION of a real bug: the source references bare ``Content``
        # instead of ``genai_types.Content`` when iterating a list of contents.
        legacy = FakeLegacyService()
        adapter = OfficialToLegacyAdapter(legacy)
        contents = [genai_types.Content(role="user", parts=[genai_types.Part(text="hi")])]
        with pytest.raises(NameError):
            await adapter.generate_content("m", contents, None)


class TestOfficialToLegacyAdapterUploadFile:
    async def test_upload_with_valid_timestamps(self):
        legacy = FakeLegacyService(
            upload_response={
                "name": "files/x",
                "display_name": "d",
                "mime_type": "image/png",
                "size_bytes": 10,
                "uri": "u",
                "state": "ACTIVE",
                "create_time": VALID_TS,
                "update_time": VALID_TS,
            }
        )
        adapter = OfficialToLegacyAdapter(legacy)
        cfg = genai_types.UploadFileConfig(display_name="d", mime_type="image/png")
        out = await adapter.upload_file("/tmp/a.png", cfg)
        assert out.name == "files/x"
        assert out.state == genai_types.FileState.ACTIVE
        # legacy received the path + config-derived names
        assert legacy.upload_calls[0]["file_path"] == "/tmp/a.png"
        assert legacy.upload_calls[0]["display_name"] == "d"
        assert legacy.upload_calls[0]["mime_type"] == "image/png"

    async def test_bytes_input_passes_none_file_path(self):
        legacy = FakeLegacyService(
            upload_response={
                "name": "files/x",
                "mime_type": "image/png",
                "size_bytes": 1,
                "uri": "u",
                "state": "ACTIVE",
                "create_time": VALID_TS,
                "update_time": VALID_TS,
            }
        )
        adapter = OfficialToLegacyAdapter(legacy)
        await adapter.upload_file(b"raw-bytes", None)
        assert legacy.upload_calls[0]["file_path"] is None
        assert legacy.upload_calls[0]["display_name"] is None

    async def test_upload_missing_timestamps_raises_validation_error_characterization(self):
        # CHARACTERIZATION of a real bug: defaults create_time/update_time to ''
        # which fails pydantic datetime validation in the current SDK.
        from pydantic import ValidationError

        legacy = FakeLegacyService(
            upload_response={
                "name": "files/x",
                "mime_type": "image/png",
                "size_bytes": 1,
                "uri": "u",
                "state": "ACTIVE",
                # no create_time / update_time -> source default '' is invalid
            }
        )
        adapter = OfficialToLegacyAdapter(legacy)
        with pytest.raises(ValidationError):
            await adapter.upload_file("/tmp/a.png", None)


class TestAdapterFactories:
    def test_create_legacy_adapter(self):
        adapter = create_legacy_adapter(official_client="client")
        assert isinstance(adapter, LegacyToOfficialAdapter)
        assert adapter.official_client == "client"

    def test_create_official_adapter(self):
        legacy = FakeLegacyService()
        adapter = create_official_adapter(legacy)
        assert isinstance(adapter, OfficialToLegacyAdapter)
        assert adapter.legacy_service is legacy


def test_module_imports_exist():
    # sanity: the public symbols the package __init__ re-exports are importable
    assert callable(adapters_mod.create_legacy_adapter)
    assert callable(utils_mod.detect_mime_type)
    assert callable(config_mod.get_default_config)
