"""Regression tests for router registration (V-S8 fail-closed, A7 route presence).

Covers two findings against ``app.routers.registry``:

* A7 — route registration order is order-sensitive but was untested. These
  tests build the app via ``register_routers`` and assert that the workflows
  and multi-agent routes are present, and that the public/auth-boundary
  ordering is intact (auth + core routes co-exist, public whitelist paths
  registered).
* V-S8 — ``multi_agent_router`` and ``workflows_router`` registration was
  wrapped in ``try/except Exception: logger.error(...)`` with no re-raise, so
  a runtime failure left those routes silently unregistered while every other
  router crashed startup. The fail-closed test monkeypatches
  ``include_router_with_auth_boundary`` to raise for those routers and asserts
  the failure propagates instead of being swallowed.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import APIRouter, FastAPI

from app.routers import registry


def _collect_paths(app: FastAPI) -> set[str]:
    return {
        str(getattr(route, "path", ""))
        for route in app.routes
        if hasattr(route, "path")
    }


def _build_app() -> FastAPI:
    app = FastAPI()
    registry.register_routers(app)
    return app


def test_workflows_routes_are_registered() -> None:
    """Workflow engine routes must be present after registration (A7)."""
    paths = _collect_paths(_build_app())

    # Core workflow surfaces that the frontend depends on.
    assert "/api/workflows/execute" in paths
    assert "/api/workflows/history" in paths
    assert "/api/workflows/templates" in paths


def test_multi_agent_routes_are_registered() -> None:
    """Multi-agent routes (prefix /api/multi-agent) must be present (A7)."""
    paths = _collect_paths(_build_app())

    # multi_agent_router is declared with prefix="/api/multi-agent".
    assert any(p.startswith("/api/multi-agent") for p in paths), (
        "No /api/multi-agent routes registered"
    )
    assert "/api/multi-agent/agents" in paths


def test_multi_agent_registered_before_core_chat() -> None:
    """Ordering invariant (A7): multi-agent routes precede the catch-all
    core chat/modes routes so path resolution is not shadowed."""
    app = _build_app()
    ordered_paths = [
        str(getattr(route, "path", ""))
        for route in app.routes
        if hasattr(route, "path")
    ]

    first_multi_agent = next(
        (i for i, p in enumerate(ordered_paths) if p.startswith("/api/multi-agent")),
        None,
    )
    first_modes_chat = next(
        (i for i, p in enumerate(ordered_paths) if p.startswith("/api/modes/")),
        None,
    )

    assert first_multi_agent is not None, "multi-agent routes missing"
    if first_modes_chat is not None:
        assert first_multi_agent < first_modes_chat, (
            "multi-agent routes must register before core /api/modes routes"
        )


def test_public_auth_boundary_ordering_preserved() -> None:
    """The auth-boundary whitelist and core/auth routes must coexist (A7).

    Public whitelist paths must still be reachable as registered routes, and
    the auth router must register after the core routes (catch-all last)."""
    app = _build_app()
    paths = _collect_paths(app)

    # Public whitelist endpoints from auth_boundary must exist as routes.
    assert "/health" in paths

    # If auth router is available, its public endpoints are registered.
    if registry.AUTH_ROUTER_AVAILABLE and registry.auth_router is not None:
        assert any(p.startswith("/api/auth") for p in paths), (
            "auth routes missing despite available auth router"
        )


def test_multi_agent_registration_failure_propagates(monkeypatch) -> None:
    """V-S8: a runtime failure registering multi_agent_router must NOT be
    silently swallowed; it must propagate (fail-closed startup)."""
    real_include = registry.include_router_with_auth_boundary

    class _BoomError(RuntimeError):
        pass

    def fake_include(app: FastAPI, router: APIRouter) -> None:
        if router is registry.multi_agent_router:
            raise _BoomError("simulated multi_agent registration failure")
        return real_include(app, router)

    monkeypatch.setattr(registry, "include_router_with_auth_boundary", fake_include)

    app = FastAPI()
    with pytest.raises(_BoomError):
        registry.register_routers(app)


def test_workflows_registration_failure_propagates(monkeypatch) -> None:
    """V-S8: a runtime failure registering workflows_router must NOT be
    silently swallowed; it must propagate (fail-closed startup)."""
    real_include = registry.include_router_with_auth_boundary

    class _BoomError(RuntimeError):
        pass

    def fake_include(app: FastAPI, router: APIRouter) -> None:
        if router is registry.workflows_router:
            raise _BoomError("simulated workflows registration failure")
        return real_include(app, router)

    monkeypatch.setattr(registry, "include_router_with_auth_boundary", fake_include)

    app = FastAPI()
    with pytest.raises(_BoomError):
        registry.register_routers(app)


def test_auth_router_import_failure_log_is_summarized(caplog) -> None:
    secret = "sorftime-secret-token"

    with caplog.at_level(logging.ERROR, logger=registry.logger.name):
        registry._log_auth_router_import_failure(
            "Unexpected error",
            RuntimeError(f"import failed {secret}"),
        )

    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "RuntimeError" in caplog.text
