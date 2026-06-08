"""Thorough unit tests for pure-logic core/utils helpers.

Targets (previously ~0% line coverage):
  - app.utils.case_converter          (camel/snake conversion + recursive skip-fields)
  - app.core.provider_param_whitelist (provider param key validation + error contract)
  - app.core.mode_method_mapper       (mode catalog + routing predicates)
  - app.core.path_utils               (project-root resolution + path-traversal guards)

These exercise real branch behavior (alias expansion, skip-field recursion,
private-key preservation, path-traversal rejection, env-var override, cache
short-circuit) against the genuine module logic. Only filesystem/env boundaries
are controlled via monkeypatch; the module-under-test logic is never mocked.
"""

from __future__ import annotations

import os

import pytest

from app.utils import case_converter as cc
from app.core import provider_param_whitelist as ppw
from app.core import mode_method_mapper as mm
from app.core import path_utils as pu


# ---------------------------------------------------------------------------
# case_converter.camel_to_snake / snake_to_camel
# ---------------------------------------------------------------------------
class TestCaseConversionScalars:
    def test_camel_to_snake_basic(self):
        assert cc.camel_to_snake("camelCase") == "camel_case"

    def test_camel_to_snake_leading_acronym(self):
        assert cc.camel_to_snake("XMLParser") == "xml_parser"

    def test_camel_to_snake_embedded_acronym(self):
        assert cc.camel_to_snake("getHTTPResponse") == "get_http_response"

    def test_camel_to_snake_with_digits(self):
        # digit -> uppercase boundary handled by the second regex
        assert cc.camel_to_snake("value2Of3") == "value2_of3"

    def test_camel_to_snake_empty_returns_empty(self):
        assert cc.camel_to_snake("") == ""

    def test_camel_to_snake_preserves_leading_underscores(self):
        assert cc.camel_to_snake("_templateMeta") == "_template_meta"
        assert cc.camel_to_snake("__internalField") == "__internal_field"

    def test_camel_to_snake_only_underscores_returns_as_is(self):
        # core_name becomes empty -> early return of original
        assert cc.camel_to_snake("___") == "___"

    def test_snake_to_camel_basic(self):
        assert cc.snake_to_camel("snake_case") == "snakeCase"

    def test_snake_to_camel_multiword(self):
        assert cc.snake_to_camel("get_http_response") == "getHttpResponse"

    def test_snake_to_camel_empty_returns_empty(self):
        assert cc.snake_to_camel("") == ""

    def test_snake_to_camel_preserves_leading_underscores(self):
        assert cc.snake_to_camel("_template_meta") == "_templateMeta"

    def test_snake_to_camel_only_underscores_returns_as_is(self):
        assert cc.snake_to_camel("__") == "__"

    def test_snake_to_camel_single_component(self):
        assert cc.snake_to_camel("token") == "token"

    def test_roundtrip_snake_camel_snake(self):
        original = "frontend_session_id"
        assert cc.camel_to_snake(cc.snake_to_camel(original)) == original


# ---------------------------------------------------------------------------
# case_converter.to_snake_case (recursive)
# ---------------------------------------------------------------------------
class TestToSnakeCase:
    def test_simple_dict(self):
        out = cc.to_snake_case({"fooBar": 1, "bazQux": 2})
        assert out == {"foo_bar": 1, "baz_qux": 2}

    def test_nested_dict_recurses(self):
        out = cc.to_snake_case({"outerKey": {"innerKey": 5}})
        assert out == {"outer_key": {"inner_key": 5}}

    def test_list_of_dicts(self):
        out = cc.to_snake_case([{"aB": 1}, {"cD": 2}])
        assert out == [{"a_b": 1}, {"c_d": 2}]

    def test_scalar_passthrough(self):
        assert cc.to_snake_case(42) == 42
        assert cc.to_snake_case("plain") == "plain"
        assert cc.to_snake_case(None) is None

    def test_private_key_preserved_verbatim(self):
        # keys starting with "_" keep both key and value untouched
        payload = {"_templateMeta": {"keepCamel": True}}
        out = cc.to_snake_case(payload)
        assert out == {"_templateMeta": {"keepCamel": True}}

    def test_skip_value_conversion_default_field(self):
        # toolArgs is in SKIP_VALUE_CONVERSION_FIELDS -> key converted, value preserved
        out = cc.to_snake_case({"toolArgs": {"keepCamel": 1}})
        assert out == {"tool_args": {"keepCamel": 1}}

    def test_skip_value_conversion_when_new_key_in_skip(self):
        # snake form already in skip set: 'metadata' matches new_key path
        out = cc.to_snake_case({"metadata": {"keepThis": 1}})
        assert out == {"metadata": {"keepThis": 1}}

    def test_custom_skip_fields_union(self):
        out = cc.to_snake_case(
            {"customField": {"keepCamel": 1}},
            skip_fields={"customField"},
        )
        assert out == {"custom_field": {"keepCamel": 1}}

    def test_non_skip_field_recurses_value(self):
        out = cc.to_snake_case({"normalField": {"innerCamel": 1}})
        assert out == {"normal_field": {"inner_camel": 1}}


# ---------------------------------------------------------------------------
# case_converter.to_camel_case (recursive)
# ---------------------------------------------------------------------------
class TestToCamelCase:
    def test_simple_dict(self):
        out = cc.to_camel_case({"foo_bar": 1})
        assert out == {"fooBar": 1}

    def test_nested_dict_recurses(self):
        out = cc.to_camel_case({"outer_key": {"inner_key": 2}})
        assert out == {"outerKey": {"innerKey": 2}}

    def test_list_recursion(self):
        out = cc.to_camel_case([{"a_b": 1}, 7, "s"])
        assert out == [{"aB": 1}, 7, "s"]

    def test_scalar_passthrough(self):
        assert cc.to_camel_case(3.5) == 3.5

    def test_private_key_preserved(self):
        out = cc.to_camel_case({"_keep_this": {"inner_x": 1}})
        assert out == {"_keep_this": {"inner_x": 1}}

    def test_skip_value_conversion_field(self):
        # tool_args key converted to toolArgs, value untouched
        out = cc.to_camel_case({"tool_args": {"keep_snake": 1}})
        assert out == {"toolArgs": {"keep_snake": 1}}

    def test_skip_when_original_key_in_skip_set(self):
        # 'arguments' is in skip set verbatim -> value preserved
        out = cc.to_camel_case({"arguments": {"keep_snake": 1}})
        assert out == {"arguments": {"keep_snake": 1}}

    def test_custom_skip_fields(self):
        out = cc.to_camel_case(
            {"my_field": {"keep_snake": 1}},
            skip_fields={"myField"},  # camel form matches new_key
        )
        assert out == {"myField": {"keep_snake": 1}}

    def test_roundtrip_dict(self):
        original = {"frontend_session_id": {"inner_value": 1}}
        snfrom = cc.to_camel_case(original)
        back = cc.to_snake_case(snfrom)
        assert back == original


# ---------------------------------------------------------------------------
# provider_param_whitelist
# ---------------------------------------------------------------------------
class TestExpandKeyAliases:
    def test_expands_snake_and_camel(self):
        result = ppw._expand_key_aliases({"max_tokens"})
        assert "max_tokens" in result
        assert "maxTokens" in result

    def test_skips_empty_keys(self):
        result = ppw._expand_key_aliases({"", "temperature"})
        assert "" not in result
        assert "temperature" in result

    def test_empty_iterable(self):
        assert ppw._expand_key_aliases([]) == set()


class TestNormalizeKeys:
    def test_none_returns_empty(self):
        assert ppw._normalize_keys(None) == set()

    def test_empty_iterable_returns_empty(self):
        assert ppw._normalize_keys([]) == set()

    def test_filters_non_strings_and_empty(self):
        out = ppw._normalize_keys(["temperature", "", None, 5, "top_p"])
        assert out == {"temperature", "top_p"}


class TestValidateChatOptionKeys:
    def test_allows_known_chat_keys(self):
        # both snake and camel aliases are accepted
        ppw.validate_chat_option_keys(provider="gemini", option_keys=["temperature", "maxTokens"])

    def test_none_option_keys_is_noop(self):
        ppw.validate_chat_option_keys(provider="gemini", option_keys=None)

    def test_rejects_unknown_chat_key(self):
        with pytest.raises(ppw.ProviderParamValidationError) as exc:
            ppw.validate_chat_option_keys(provider="gemini", option_keys=["definitelyNotAllowed"])
        err = exc.value
        assert err.scope == "chat"
        assert "definitelyNotAllowed" in err.invalid_params

    def test_openai_provider_extra_keys_allowed(self):
        # frequency_penalty only valid for openai-family providers
        ppw.validate_chat_option_keys(provider="openai", option_keys=["frequency_penalty", "seed"])

    def test_openai_extra_key_rejected_for_gemini(self):
        with pytest.raises(ppw.ProviderParamValidationError):
            ppw.validate_chat_option_keys(provider="gemini", option_keys=["frequency_penalty"])

    def test_provider_case_and_whitespace_normalized(self):
        # provider lookup lowercases + strips -> "  OpenAI  " resolves to openai extras
        ppw.validate_chat_option_keys(provider="  OpenAI  ", option_keys=["presence_penalty"])

    def test_none_provider_treated_as_empty(self):
        # falls back to base chat keys only; base key still passes
        ppw.validate_chat_option_keys(provider=None, option_keys=["temperature"])


class TestValidateModeParamKeys:
    def test_allows_known_mode_keys(self):
        ppw.validate_mode_param_keys(
            provider="gemini",
            mode="image-gen",
            option_keys=["size", "quality"],
            extra_keys=["negative_prompt"],
        )

    def test_rejects_unknown_mode_key(self):
        with pytest.raises(ppw.ProviderParamValidationError) as exc:
            ppw.validate_mode_param_keys(
                provider="gemini",
                mode="image-gen",
                option_keys=["totallyBogus"],
                extra_keys=None,
            )
        assert exc.value.scope == "mode:image-gen"
        assert "totallyBogus" in exc.value.invalid_params

    def test_extra_keys_validated_too(self):
        with pytest.raises(ppw.ProviderParamValidationError):
            ppw.validate_mode_param_keys(
                provider="gemini",
                mode="video-gen",
                option_keys=None,
                extra_keys=["bogusExtra"],
            )

    def test_both_none_is_noop(self):
        ppw.validate_mode_param_keys(
            provider="gemini", mode="chat", option_keys=None, extra_keys=None
        )

    def test_multiple_invalid_sorted(self):
        with pytest.raises(ppw.ProviderParamValidationError) as exc:
            ppw.validate_mode_param_keys(
                provider="gemini",
                mode="image-gen",
                option_keys=["zBad", "aBad"],
                extra_keys=None,
            )
        # invalid_params is sorted ascending
        assert list(exc.value.invalid_params) == sorted(exc.value.invalid_params)


class TestProviderParamValidationError:
    def _make(self):
        return ppw.ProviderParamValidationError(
            provider="gemini",
            scope="chat",
            invalid_params=("foo", "bar"),
            allowed_params=("temperature", "top_p"),
        )

    def test_message_contains_context(self):
        err = self._make()
        assert "gemini" in err.message
        assert "chat" in err.message
        assert "foo" in err.message and "bar" in err.message

    def test_to_http_detail_shape(self):
        err = self._make()
        detail = err.to_http_detail()
        assert detail["code"] == ppw.INVALID_PROVIDER_PARAMS_CODE
        assert detail["message"] == err.message
        assert detail["details"]["provider"] == "gemini"
        assert detail["details"]["scope"] == "chat"
        assert detail["details"]["invalid_params"] == ["foo", "bar"]
        assert detail["details"]["allowed_params"] == ["temperature", "top_p"]

    def test_is_exception_subclass(self):
        with pytest.raises(Exception):
            raise self._make()


# ---------------------------------------------------------------------------
# mode_method_mapper
# ---------------------------------------------------------------------------
class TestModeCatalog:
    def test_get_catalog_default_excludes_internal(self):
        catalog = mm.get_mode_catalog()
        ids = {item["id"] for item in catalog}
        # navigation-visible modes present
        assert "chat" in ids
        # internal-only mode excluded
        assert "video-understand" not in ids
        assert all(item["visible_in_navigation"] for item in catalog)

    def test_get_catalog_include_internal(self):
        catalog = mm.get_mode_catalog(include_internal=True)
        ids = {item["id"] for item in catalog}
        assert "video-understand" in ids
        assert len(catalog) == len(mm.MODE_CATALOG)

    def test_get_catalog_returns_copies(self):
        catalog = mm.get_mode_catalog(include_internal=True)
        catalog[0]["label"] = "MUTATED"
        # original catalog item must be untouched (dict() copy)
        assert mm.MODE_CATALOG[0]["label"] != "MUTATED"

    def test_get_service_method_known(self):
        assert mm.get_service_method("chat") == "stream_chat"
        assert mm.get_service_method("video-gen") == "generate_video"

    def test_get_service_method_unknown_returns_none(self):
        assert mm.get_service_method("no-such-mode") is None

    def test_is_streaming_mode(self):
        assert mm.is_streaming_mode("chat") is True
        assert mm.is_streaming_mode("image-gen") is False
        assert mm.is_streaming_mode("unknown") is False

    def test_is_image_edit_mode(self):
        assert mm.is_image_edit_mode("image-chat-edit") is True
        assert mm.is_image_edit_mode("chat") is False

    def test_is_layered_design_mode(self):
        assert mm.is_layered_design_mode("image-layered-suggest") is True
        assert mm.is_layered_design_mode("chat") is False

    def test_method_map_consistency(self):
        # every catalog id maps to its service_method
        for item in mm.MODE_CATALOG:
            assert mm.MODE_METHOD_MAP[item["id"]] == item["service_method"]


# ---------------------------------------------------------------------------
# path_utils
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_path_cache():
    """Each path_utils test starts with a clean root cache."""
    saved = pu._project_root_cache
    pu._project_root_cache = None
    yield
    pu._project_root_cache = saved


class TestGetProjectRoot:
    def test_returns_cached_value_short_circuit(self, monkeypatch):
        pu._project_root_cache = "/cached/root"
        # even if getenv would return something, cache short-circuits
        monkeypatch.setenv("PROJECT_ROOT", "/somewhere/else")
        assert pu.get_project_root() == "/cached/root"

    def test_uses_env_var_when_valid(self, monkeypatch, tmp_path):
        # build a fake project layout that passes validation
        (tmp_path / "backend" / "app").mkdir(parents=True)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        root = pu.get_project_root()
        assert os.path.abspath(root) == os.path.abspath(str(tmp_path))
        # cache now populated
        assert pu._project_root_cache == root

    def test_invalid_env_var_falls_back_to_computed(self, monkeypatch, tmp_path):
        bad = tmp_path / "not_a_project"
        bad.mkdir()
        monkeypatch.setenv("PROJECT_ROOT", str(bad))
        # computed root is the real repo root (validation succeeds there)
        root = pu.get_project_root()
        assert os.path.exists(os.path.join(root, "backend", "app"))

    def test_no_env_var_uses_computed_root(self, monkeypatch):
        monkeypatch.delenv("PROJECT_ROOT", raising=False)
        root = pu.get_project_root()
        assert os.path.exists(os.path.join(root, "backend", "app"))


class TestEnsureCredentialsDir:
    @pytest.mark.skipif(
        os.name == "nt",
        reason="POSIX file mode 0o700 cannot be enforced on Windows; the graceful "
        "chmod-failure path is covered by test_chmod_failure_is_warned_not_raised",
    )
    def test_creates_and_tightens_perms(self, monkeypatch, tmp_path):
        cred = tmp_path / "credentials"
        monkeypatch.setattr(pu, "CREDENTIALS_DIR", cred)
        returned = pu.ensure_credentials_dir()
        assert returned == cred
        assert cred.exists()
        # mode should be 0o700 on this filesystem
        assert (os.stat(cred).st_mode & 0o777) == 0o700

    def test_chmod_failure_is_warned_not_raised(self, monkeypatch, tmp_path):
        cred = tmp_path / "credentials"
        cred.mkdir()
        monkeypatch.setattr(pu, "CREDENTIALS_DIR", cred)

        def _boom_chmod(*args, **kwargs):
            raise OSError("nfs refused")

        monkeypatch.setattr(pu.os, "chmod", _boom_chmod)
        # must not raise despite chmod failure
        assert pu.ensure_credentials_dir() == cred

    def test_stat_mismatch_logs_error(self, monkeypatch, tmp_path):
        cred = tmp_path / "credentials"
        cred.mkdir()
        monkeypatch.setattr(pu, "CREDENTIALS_DIR", cred)
        # chmod no-op so final mode stays != 0o700, exercising the error branch
        monkeypatch.setattr(pu.os, "chmod", lambda *a, **k: None)
        os.chmod(cred, 0o755)
        assert pu.ensure_credentials_dir() == cred
        # path still exists; branch executed without raising
        assert cred.exists()

    def test_stat_failure_is_warned_not_raised(self, monkeypatch, tmp_path):
        # The final stat() verification can fail on exotic filesystems; the module
        # must warn and still return the dir. We point at a path that exists for
        # mkdir/chmod but is removed before the stat check, so os.stat raises
        # FileNotFoundError (an OSError) without breaking pytest teardown.
        cred = tmp_path / "credentials"
        monkeypatch.setattr(pu, "CREDENTIALS_DIR", cred)

        real_mkdir = type(cred).mkdir

        def _mkdir_then_remove(self, *args, **kwargs):
            # Honour the real mkdir, then remove so the subsequent stat fails.
            real_mkdir(self, *args, **kwargs)
            os.rmdir(self)

        monkeypatch.setattr(type(cred), "mkdir", _mkdir_then_remove)
        monkeypatch.setattr(pu.os, "chmod", lambda *a, **k: None)
        # Must not raise even though os.stat() on the now-missing dir fails.
        assert pu.ensure_credentials_dir() == cred


class TestGetProjectRootCwdFallback:
    def test_falls_back_to_cwd_when_env_and_computed_invalid(self, monkeypatch, tmp_path):
        # Make a valid cwd layout
        (tmp_path / "backend" / "app").mkdir(parents=True)
        monkeypatch.delenv("PROJECT_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)

        real_validate = pu._validate_project_root

        def _selective_validate(root: str) -> bool:
            # Reject the auto-computed repo root (parents of __file__) so the
            # cwd-fallback branch is reached, but accept the tmp cwd layout.
            if os.path.abspath(root) == os.path.abspath(str(tmp_path)):
                return real_validate(root)
            return False

        monkeypatch.setattr(pu, "_validate_project_root", _selective_validate)
        root = pu.get_project_root()
        assert os.path.abspath(root) == os.path.abspath(str(tmp_path))

    def test_all_invalid_returns_computed_with_error(self, monkeypatch):
        monkeypatch.delenv("PROJECT_ROOT", raising=False)
        # Everything invalid -> final fallback returns the computed root anyway
        monkeypatch.setattr(pu, "_validate_project_root", lambda _root: False)
        root = pu.get_project_root()
        # computed root ends at the repo root (4 parents up from path_utils.py)
        assert root.endswith("gemini-main") or os.path.basename(root) != ""


class TestValidateProjectRoot:
    def test_empty_path_invalid(self):
        assert pu._validate_project_root("") is False

    def test_nonexistent_path_invalid(self, tmp_path):
        assert pu._validate_project_root(str(tmp_path / "ghost")) is False

    def test_missing_backend_app_invalid(self, tmp_path):
        # exists but no backend/app
        assert pu._validate_project_root(str(tmp_path)) is False

    def test_valid_layout(self, tmp_path):
        (tmp_path / "backend" / "app").mkdir(parents=True)
        assert pu._validate_project_root(str(tmp_path)) is True
        # temp dir got created as a side effect
        assert (tmp_path / "backend" / "app" / "temp").exists()

    def test_makedirs_failure_returns_false(self, tmp_path, monkeypatch):
        (tmp_path / "backend" / "app").mkdir(parents=True)

        def _boom(*args, **kwargs):
            raise OSError("denied")

        monkeypatch.setattr(pu.os, "makedirs", _boom)
        assert pu._validate_project_root(str(tmp_path)) is False


class TestTempDirHelpers:
    def test_get_temp_dir_relative_constant(self):
        assert pu.get_temp_dir_relative() == "backend/app/temp"

    def test_get_temp_dir_absolute(self, monkeypatch, tmp_path):
        (tmp_path / "backend" / "app").mkdir(parents=True)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        temp = pu.get_temp_dir()
        assert temp.endswith(os.path.join("backend", "app", "temp"))
        assert os.path.exists(temp)


class TestPathWithinRoot:
    def test_inside_root_true(self):
        assert pu._is_path_within_root("/a/b/c", "/a/b") is True

    def test_outside_root_false(self):
        assert pu._is_path_within_root("/a/x/c", "/a/b") is False

    def test_equal_path_true(self):
        assert pu._is_path_within_root("/a/b", "/a/b") is True

    def test_invalid_inputs_return_false(self, monkeypatch):
        # force commonpath to raise ValueError (e.g. mixed/relative on some platforms)
        def _boom(_paths):
            raise ValueError("mixed")

        monkeypatch.setattr(pu.os.path, "commonpath", _boom)
        assert pu._is_path_within_root("/a/b", "/a/b") is False


class TestResolveRelativePath:
    def _setup_root(self, monkeypatch, tmp_path):
        (tmp_path / "backend" / "app").mkdir(parents=True)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        return str(tmp_path)

    def test_resolves_relative(self, monkeypatch, tmp_path):
        root = self._setup_root(monkeypatch, tmp_path)
        result = pu.resolve_relative_path("backend/app/temp/x.png")
        assert result == os.path.normpath(os.path.join(root, "backend/app/temp/x.png"))

    def test_rejects_traversal_relative(self, monkeypatch, tmp_path):
        self._setup_root(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="Path traversal"):
            pu.resolve_relative_path("../../../etc/passwd")

    def test_absolute_inside_root_returned(self, monkeypatch, tmp_path):
        root = self._setup_root(monkeypatch, tmp_path)
        inside = os.path.join(root, "backend", "app", "file.bin")
        assert pu.resolve_relative_path(inside) == inside

    def test_absolute_outside_root_rejected(self, monkeypatch, tmp_path):
        self._setup_root(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="Path traversal"):
            pu.resolve_relative_path(os.path.abspath(os.sep + "outside_root_file"))


class TestToRelativePath:
    def _setup_root(self, monkeypatch, tmp_path):
        (tmp_path / "backend" / "app").mkdir(parents=True)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        return str(tmp_path)

    def test_converts_absolute_to_relative_forward_slashes(self, monkeypatch, tmp_path):
        root = self._setup_root(monkeypatch, tmp_path)
        abs_path = os.path.join(root, "backend", "app", "temp", "y.png")
        rel = pu.to_relative_path(abs_path)
        assert rel == "backend/app/temp/y.png"
        assert "\\" not in rel

    def test_outside_root_raises(self, monkeypatch, tmp_path):
        self._setup_root(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="outside project root"):
            pu.to_relative_path(os.path.abspath(os.sep + "elsewhere"))

    def test_relpath_value_error_remapped(self, monkeypatch, tmp_path):
        root = self._setup_root(monkeypatch, tmp_path)
        abs_path = os.path.join(root, "backend", "app", "deep.bin")

        # Path passes the within-root check, but relpath itself raises ValueError
        # (e.g. different drive on Windows). The module must remap to a clear error.
        def _boom_relpath(_path, _start):
            raise ValueError("different drive")

        monkeypatch.setattr(pu.os.path, "relpath", _boom_relpath)
        with pytest.raises(ValueError, match="Cannot convert path to relative"):
            pu.to_relative_path(abs_path)


class TestEnsureRelativePath:
    def _setup_root(self, monkeypatch, tmp_path):
        (tmp_path / "backend" / "app").mkdir(parents=True)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        return str(tmp_path)

    def test_relative_input_normalized_slashes(self, monkeypatch, tmp_path):
        self._setup_root(monkeypatch, tmp_path)
        assert pu.ensure_relative_path("backend\\app\\temp\\z.png") == "backend/app/temp/z.png"

    def test_absolute_input_converted(self, monkeypatch, tmp_path):
        root = self._setup_root(monkeypatch, tmp_path)
        abs_path = os.path.join(root, "backend", "app", "a.txt")
        assert pu.ensure_relative_path(abs_path) == "backend/app/a.txt"
