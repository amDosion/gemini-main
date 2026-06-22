"""Characterization + regression tests for the global auth boundary.

Covers finding V-S5: PUBLIC_AUTH_WHITELIST and enforce_global_auth_boundary had
zero test coverage. These tests exercise the *real* enforce_global_auth_boundary,
is_public_auth_path, _normalize_path, and include_router_with_auth_boundary logic
imported from app.routers.auth_boundary.

The deny-by-default behavior is already correct, so these tests are expected to
PASS against current code. They lock in:
  - every whitelisted path is treated as public (no auth required),
  - non-whitelisted paths require auth (deny-by-default -> 401),
  - trailing-slash normalization,
  - OPTIONS / non-http scope bypass,
  - the boundary disabled escape hatch,
  - router registration wiring (dependency present iff boundary enabled).
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from starlette.requests import HTTPConnection

from app.routers import auth_boundary
from app.routers.auth_boundary import (
    PUBLIC_AUTH_WHITELIST,
    enforce_global_auth_boundary,
    include_router_with_auth_boundary,
    is_public_auth_path,
    _normalize_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_connection(
    *,
    path: str = "/",
    method: str = "GET",
    scope_type: str = "http",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> HTTPConnection:
    """Build a minimal HTTPConnection that enforce_global_auth_boundary can read.

    The boundary only inspects scope['type'], scope['method'], and url.path; an
    unauthenticated connection (no Authorization header, no cookie) is enough to
    drive require_user_id down its fail-closed path without touching the DB.
    """
    scope = {
        "type": scope_type,
        "method": method,
        "path": path,
        "headers": headers or [],
        "query_string": b"",
    }
    return HTTPConnection(scope)


@pytest.fixture
def boundary_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the global auth boundary ON regardless of env defaults."""
    monkeypatch.setattr(auth_boundary.settings, "enable_global_auth_boundary", True)


@pytest.fixture
def boundary_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the global auth boundary OFF (escape hatch)."""
    monkeypatch.setattr(auth_boundary.settings, "enable_global_auth_boundary", False)


# ---------------------------------------------------------------------------
# _normalize_path / is_public_auth_path unit behavior
# ---------------------------------------------------------------------------

def test_normalize_empty_path_becomes_root():
    assert _normalize_path("") == "/"


def test_normalize_root_is_preserved():
    assert _normalize_path("/") == "/"


def test_normalize_strips_single_trailing_slash():
    assert _normalize_path("/api/auth/login/") == "/api/auth/login"


def test_normalize_strips_multiple_trailing_slashes():
    assert _normalize_path("/health///") == "/health"


def test_normalize_does_not_strip_root_slash():
    # Root must remain "/" and never collapse to "".
    assert _normalize_path("/") == "/"


def test_normalize_leaves_non_trailing_slash_path_untouched():
    assert _normalize_path("/api/files") == "/api/files"


def test_is_public_auth_path_true_for_whitelisted():
    assert is_public_auth_path("/api/auth/login") is True


def test_is_public_auth_path_true_for_whitelisted_with_trailing_slash():
    assert is_public_auth_path("/api/auth/login/") is True


def test_is_public_auth_path_true_for_empty_path_maps_to_root():
    # "" normalizes to "/", which is whitelisted.
    assert is_public_auth_path("") is True


def test_is_public_auth_path_false_for_non_whitelisted():
    assert is_public_auth_path("/api/files") is False


def test_is_public_auth_path_false_for_prefix_of_whitelisted():
    # Deny-by-default: a *prefix* of a whitelisted route is not itself public.
    assert is_public_auth_path("/api/auth") is False


def test_is_public_auth_path_false_for_extension_of_whitelisted():
    # /api/auth/login is public, but /api/auth/login/extra is not.
    assert is_public_auth_path("/api/auth/login/extra") is False


# ---------------------------------------------------------------------------
# enforce_global_auth_boundary: whitelist bypass (no auth required)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("public_path", sorted(PUBLIC_AUTH_WHITELIST))
def test_every_whitelisted_path_is_public(boundary_enabled, public_path):
    """Every entry in PUBLIC_AUTH_WHITELIST must pass without auth."""
    conn = make_connection(path=public_path)
    # Must not raise even though the connection carries no credentials.
    assert enforce_global_auth_boundary(conn) is None


@pytest.mark.parametrize(
    "public_path",
    sorted(path for path in PUBLIC_AUTH_WHITELIST if path != "/"),
)
def test_whitelisted_path_with_trailing_slash_is_public(boundary_enabled, public_path):
    """Trailing-slash variants of whitelisted paths normalize to public.

    Root ("/") has no distinct trailing-slash variant, so it is covered by the
    root normalization tests instead of becoming a skipped parameter case.
    """
    conn = make_connection(path=public_path + "/")
    assert enforce_global_auth_boundary(conn) is None


def test_whitelist_contents_are_locked():
    """Guard against accidental whitelist drift (adding a new public route is a
    security-relevant decision and should fail this test until updated)."""
    assert PUBLIC_AUTH_WHITELIST == frozenset(
        {
            "/",
            "/health",
            "/api/auth/config",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
        }
    )


# ---------------------------------------------------------------------------
# enforce_global_auth_boundary: deny-by-default for non-whitelisted paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "protected_path",
    [
        "/api/files",
        "/api/sessions",
        "/api/auth",  # prefix of a whitelisted route, but not whitelisted itself
        "/api/auth/logout",  # auth namespace but not in whitelist
        "/api/modes/gemini/chat",
        "/api/auth/login/extra",
    ],
)
def test_non_whitelisted_path_requires_auth(boundary_enabled, protected_path):
    """Deny-by-default: an unauthenticated request to a protected path -> 401."""
    conn = make_connection(path=protected_path)
    with pytest.raises(HTTPException) as exc_info:
        enforce_global_auth_boundary(conn)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Authentication required"


def test_non_whitelisted_trailing_slash_still_requires_auth(boundary_enabled):
    """A trailing slash must not be a way to dodge auth on a protected path."""
    conn = make_connection(path="/api/files/")
    with pytest.raises(HTTPException) as exc_info:
        enforce_global_auth_boundary(conn)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# enforce_global_auth_boundary: scope / method / toggle bypasses
# ---------------------------------------------------------------------------

def test_options_preflight_bypasses_auth_on_protected_path(boundary_enabled):
    """CORS preflight (OPTIONS) is exempt even on a protected path."""
    conn = make_connection(path="/api/files", method="OPTIONS")
    assert enforce_global_auth_boundary(conn) is None


def test_options_method_is_case_insensitive(boundary_enabled):
    """Method comparison is upper-cased before the OPTIONS check."""
    conn = make_connection(path="/api/files", method="options")
    assert enforce_global_auth_boundary(conn) is None


def test_non_http_scope_bypasses_auth(boundary_enabled):
    """Non-http scopes (e.g. websocket) skip the route-level boundary."""
    conn = make_connection(path="/api/files", scope_type="websocket")
    assert enforce_global_auth_boundary(conn) is None


def test_boundary_disabled_allows_protected_path(boundary_disabled):
    """When the boundary is disabled, even protected paths pass without auth."""
    conn = make_connection(path="/api/files")
    assert enforce_global_auth_boundary(conn) is None


# ---------------------------------------------------------------------------
# include_router_with_auth_boundary: registration wiring
# ---------------------------------------------------------------------------

def _router_routes_have_boundary_dependency(app: FastAPI, marker_path: str) -> bool:
    """Return True if the route for marker_path carries the enforce dependency."""
    for route in app.routes:
        if getattr(route, "path", None) == marker_path:
            calls = [dep.call for dep in route.dependant.dependencies]
            return enforce_global_auth_boundary in calls
    raise AssertionError(f"route {marker_path!r} was not registered")


def _make_router(marker_path: str = "/_boundary_probe") -> APIRouter:
    router = APIRouter()

    @router.get(marker_path)
    async def _probe():  # pragma: no cover - never executed, only registered
        return {"ok": True}

    return router


def test_include_router_adds_dependency_when_enabled(boundary_enabled):
    app = FastAPI()
    include_router_with_auth_boundary(app, _make_router())
    assert _router_routes_have_boundary_dependency(app, "/_boundary_probe") is True


def test_include_router_omits_dependency_when_disabled(boundary_disabled):
    app = FastAPI()
    include_router_with_auth_boundary(app, _make_router())
    assert _router_routes_have_boundary_dependency(app, "/_boundary_probe") is False
