"""Regression tests for SecurityHeadersMiddleware HSTS/CSP behavior.

Covers cluster sec-headers (S7 LOW / A6 MEDIUM):
- Content-Security-Policy must always be present.
- Strict-Transport-Security must be present under HTTPS or production.
- Strict-Transport-Security must NOT be present on plain-HTTP non-prod
  (local dev) so it does not pin localhost to HTTPS.
- Existing headers (X-Content-Type-Options, X-Frame-Options,
  Referrer-Policy) must remain intact.
- Headers already set downstream must not be overwritten.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from app.core import middleware_config
from app.core.middleware_config import SecurityHeadersMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    @app.get("/preset")
    async def preset() -> JSONResponse:
        # Downstream explicitly sets a CSP/HSTS; middleware must not clobber.
        return JSONResponse(
            {"ok": True},
            headers={
                "Content-Security-Policy": "default-src 'none'",
                "Strict-Transport-Security": "max-age=1",
            },
        )

    return app


@pytest.fixture
def dev_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force non-production so HSTS gating depends purely on scheme.

    ``is_production`` is a computed Pydantic property (no setter), so patch
    the underlying ``environment`` field it derives from.
    """
    monkeypatch.setattr(
        middleware_config.settings, "environment", "development", raising=False
    )
    assert middleware_config.settings.is_production is False


@pytest.fixture
def prod_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        middleware_config.settings, "environment", "production", raising=False
    )
    assert middleware_config.settings.is_production is True


def test_csp_always_present_on_plain_http(dev_env: None) -> None:
    client = TestClient(_build_app(), base_url="http://testserver")
    resp = client.get("/ping")
    assert resp.status_code == 200
    csp = resp.headers.get("Content-Security-Policy")
    assert csp, "CSP header must always be present"
    assert "default-src" in csp


def test_no_hsts_on_plain_http_non_prod(dev_env: None) -> None:
    client = TestClient(_build_app(), base_url="http://testserver")
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert (
        "Strict-Transport-Security" not in resp.headers
    ), "HSTS must not be sent on plain-HTTP local dev"


def test_hsts_present_on_https(dev_env: None) -> None:
    # base_url with https makes Starlette set scope scheme == 'https'
    client = TestClient(_build_app(), base_url="https://testserver")
    resp = client.get("/ping")
    assert resp.status_code == 200
    hsts = resp.headers.get("Strict-Transport-Security")
    assert hsts, "HSTS must be sent over HTTPS"
    assert "max-age=" in hsts


def test_hsts_present_in_production_even_on_http(prod_env: None) -> None:
    client = TestClient(_build_app(), base_url="http://testserver")
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert (
        "Strict-Transport-Security" in resp.headers
    ), "HSTS must be sent in production (TLS-terminating proxy assumed)"


def test_existing_headers_intact(dev_env: None) -> None:
    client = TestClient(_build_app(), base_url="http://testserver")
    resp = client.get("/ping")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert (
        resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    )


def test_downstream_headers_not_overwritten(prod_env: None) -> None:
    client = TestClient(_build_app(), base_url="https://testserver")
    resp = client.get("/preset")
    assert resp.headers.get("Content-Security-Policy") == "default-src 'none'"
    assert resp.headers.get("Strict-Transport-Security") == "max-age=1"
