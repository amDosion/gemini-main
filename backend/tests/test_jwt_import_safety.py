"""Regression tests for the jwt-import-safety cluster.

Covers:
- S5 / V-S30: jwt_utils must NOT read the JWT secret as a module-level
  side-effect at import time. Importing the module with the secret unset must
  not raise; the secret must be resolved lazily and be hot-rotatable by
  clearing a cache (no re-import / restart required).
- A3: import_loader.safe_import_multiple must not mutate the caller's config
  dicts (it currently pops 'name' off the live dict).
- V-S19: import_loader.safe_import must hard-fail (RuntimeError) for CRITICAL
  modules instead of silently degrading to a None stub.
- V-S18: main.py must not run Base.metadata.create_all at import time.
"""

import subprocess
import sys
import textwrap

import pytest


def _run_python(snippet: str) -> subprocess.CompletedProcess:
    """Run a python snippet in a clean subprocess rooted at the backend dir."""
    import os

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(snippet)],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# --------------------------------------------------------------------------- #
# S5 / V-S30: lazy, import-safe JWT secret resolution
# --------------------------------------------------------------------------- #


def test_importing_jwt_utils_does_not_resolve_secret_at_import():
    """Importing jwt_utils must NOT resolve the JWT secret at import time.

    We patch the underlying secret resolver to raise BEFORE importing the
    module. With the old eager module-level `JWT_SECRET_KEY = get_jwt_secret_key()`
    this import crashes with RuntimeError as an opaque import-chain failure.
    With the lazy accessor, import succeeds and the resolver is only consulted
    on first use. We also assert the lazy accessor exists.

    Note: we keep dotenv intact so unrelated import-time requirements (e.g.
    DATABASE_URL for app.core.database) remain satisfied; only the JWT secret
    resolution path is forced to fail.
    """
    # We can't pre-patch jwt_utils itself (importing it IS the thing under test),
    # so we force the underlying resolver to fail by intercepting the only env
    # read it performs: os.getenv('JWT_SECRET_KEY'). Other env reads (e.g.
    # DATABASE_URL needed by app.core.database) are passed through unchanged.
    snippet = """
        import importlib
        import os
        _real_getenv = os.getenv
        def _patched_getenv(key, default=None):
            if key == "JWT_SECRET_KEY":
                return None
            return _real_getenv(key, default)
        os.getenv = _patched_getenv

        mod = importlib.import_module("app.core.jwt_utils")
        assert hasattr(mod, "_get_cached_jwt_secret"), "missing lazy accessor"
        assert hasattr(mod, "clear_jwt_secret_cache"), "missing cache clearer"
        os.getenv = _real_getenv
        print("IMPORT_OK")
    """
    proc = _run_python(snippet)
    assert "IMPORT_OK" in proc.stdout, (
        f"importing jwt_utils resolved/required the secret at import time.\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert proc.returncode == 0, proc.stderr


def test_jwt_secret_is_resolved_lazily_and_errors_only_on_use():
    """With the secret unresolvable, importing succeeds but USING tokens raises."""
    snippet = """
        import os
        _real_getenv = os.getenv
        def _patched_getenv(key, default=None):
            if key == "JWT_SECRET_KEY":
                return None
            return _real_getenv(key, default)
        os.getenv = _patched_getenv

        import importlib
        mod = importlib.import_module("app.core.jwt_utils")
        mod.clear_jwt_secret_cache()
        raised = False
        try:
            mod.create_access_token("user-1")
        except RuntimeError:
            raised = True
        assert raised, "expected RuntimeError when secret missing at use-time"
        os.getenv = _real_getenv
        print("LAZY_USE_OK")
    """
    proc = _run_python(snippet)
    assert "LAZY_USE_OK" in proc.stdout, (
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert proc.returncode == 0, proc.stderr


def test_jwt_secret_cache_picks_up_rotation_after_clear():
    """A rotated secret must be picked up after clearing the cache (no re-import)."""
    from app.core import jwt_utils

    assert hasattr(jwt_utils, "_get_cached_jwt_secret")
    assert hasattr(jwt_utils, "clear_jwt_secret_cache")

    import os

    original = os.environ.get("JWT_SECRET_KEY")
    try:
        os.environ["JWT_SECRET_KEY"] = "secret-A-aaaaaaaaaaaaaaaaaaaa"
        jwt_utils.clear_jwt_secret_cache()
        first = jwt_utils._get_cached_jwt_secret()
        assert first == "secret-A-aaaaaaaaaaaaaaaaaaaa"

        # Rotate the env var; without clearing, the cached value persists.
        os.environ["JWT_SECRET_KEY"] = "secret-B-bbbbbbbbbbbbbbbbbbbb"
        cached_again = jwt_utils._get_cached_jwt_secret()
        assert cached_again == "secret-A-aaaaaaaaaaaaaaaaaaaa", "expected cache hit"

        # Clearing the cache picks up the rotated secret.
        jwt_utils.clear_jwt_secret_cache()
        rotated = jwt_utils._get_cached_jwt_secret()
        assert rotated == "secret-B-bbbbbbbbbbbbbbbbbbbb"
    finally:
        if original is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = original
        jwt_utils.clear_jwt_secret_cache()


def test_token_roundtrip_behaviour_unchanged():
    """Encode/decode must still work identically after the refactor."""
    import os

    from app.core import jwt_utils

    original = os.environ.get("JWT_SECRET_KEY")
    try:
        os.environ["JWT_SECRET_KEY"] = "roundtrip-secret-cccccccccccccccccccc"
        jwt_utils.clear_jwt_secret_cache()
        token = jwt_utils.create_access_token("user-42")
        payload = jwt_utils.decode_token(token)
        assert payload.sub == "user-42"
        assert payload.type == "access"
    finally:
        if original is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = original
        jwt_utils.clear_jwt_secret_cache()


# --------------------------------------------------------------------------- #
# A3: safe_import_multiple must not mutate caller config
# --------------------------------------------------------------------------- #


def test_safe_import_multiple_does_not_mutate_caller_config():
    from app.core.import_loader import safe_import_multiple

    configs = [
        {
            "name": "logger",
            "relative_path": "core.logger",
            "attr_names": ["LOG_PREFIXES"],
        }
    ]
    # Snapshot before.
    assert "name" in configs[0]
    safe_import_multiple(configs)
    # The caller's dict must still contain 'name' (no in-place pop).
    assert "name" in configs[0], "safe_import_multiple mutated caller config dict"
    assert configs[0]["name"] == "logger"


# --------------------------------------------------------------------------- #
# V-S19: critical import failures must hard-fail, not degrade to None stub
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("critical_path", ["routers.registry", "core.database"])
def test_safe_import_raises_for_critical_module_failure(critical_path):
    from app.core.import_loader import safe_import

    with pytest.raises(RuntimeError):
        safe_import(
            f"{critical_path}.__definitely_missing_submodule__",
            attr_names=["whatever"],
            critical=True,
        )


def test_safe_import_non_critical_failure_still_degrades_gracefully():
    """Non-critical failures keep the existing soft-fallback behaviour."""
    from app.core.import_loader import safe_import

    result = safe_import(
        "services.__definitely_missing__",
        attr_names=["foo"],
        fallback_values={"foo": "fallback"},
        warning_message="missing optional module",
    )
    assert result.success is False
    assert result.get("foo") == "fallback"


# --------------------------------------------------------------------------- #
# V-S18: main.py must not run create_all at import time
# --------------------------------------------------------------------------- #


def test_main_does_not_call_create_all_at_import_time():
    """Importing app.main must not invoke Base.metadata.create_all.

    create_all belongs in lifespan/startup, not at module import.
    """
    snippet = """
        import os
        os.environ.setdefault("JWT_SECRET_KEY", "import-safety-secret-dddddddddddd")

        import importlib
        called = {"create_all": False}

        import sqlalchemy
        _orig = sqlalchemy.MetaData.create_all
        def _spy(self, *a, **k):
            called["create_all"] = True
            return None
        sqlalchemy.MetaData.create_all = _spy
        try:
            importlib.import_module("app.main")
        finally:
            sqlalchemy.MetaData.create_all = _orig
        assert called["create_all"] is False, "create_all was invoked at import time"
        print("NO_CREATE_ALL_AT_IMPORT")
    """
    proc = _run_python(snippet)
    # If the app cannot import at all for unrelated env reasons (missing DB driver
    # etc.), surface that clearly rather than silently passing.
    assert "NO_CREATE_ALL_AT_IMPORT" in proc.stdout, (
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert proc.returncode == 0, proc.stderr


def test_main_startup_log_text_redacts_exception_content():
    snippet = """
        import os
        os.environ.setdefault("JWT_SECRET_KEY", "import-safety-secret-dddddddddddd")

        from app.main import _safe_startup_log_text

        secret = "startup-secret-token"
        output = _safe_startup_log_text(RuntimeError(f"route registration failed {secret}"))
        assert secret not in output
        assert "route registration failed" not in output
        assert "RuntimeError" in output
        print("SAFE_STARTUP_LOG_TEXT")
    """
    proc = _run_python(snippet)
    assert "SAFE_STARTUP_LOG_TEXT" in proc.stdout, (
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert proc.returncode == 0, proc.stderr
