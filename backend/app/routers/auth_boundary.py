"""Global auth boundary helpers for router registration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from starlette.requests import HTTPConnection

from ..core.config import settings
from ..core.user_context import require_user_id


PUBLIC_AUTH_WHITELIST = frozenset(
    {
        "/",
        "/health",
        "/api/auth/config",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
    }
)


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def is_public_auth_path(path: str) -> bool:
    return _normalize_path(path) in PUBLIC_AUTH_WHITELIST


def enforce_global_auth_boundary(connection: HTTPConnection) -> None:
    """Route-level deny-by-default auth boundary with whitelist bypass."""
    if not settings.enable_global_auth_boundary:
        return

    if connection.scope.get("type") != "http":
        return

    method = str(connection.scope.get("method", "")).upper()
    if method == "OPTIONS":
        return

    if is_public_auth_path(connection.url.path):
        return

    require_user_id(connection)  # type: ignore[arg-type]


def include_router_with_auth_boundary(app: FastAPI, router: APIRouter) -> None:
    if settings.enable_global_auth_boundary:
        app.include_router(
            router,
            dependencies=[Depends(enforce_global_auth_boundary)],
        )
        return

    app.include_router(router)
