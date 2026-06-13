from __future__ import annotations

import logging
import sys
import types

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers.system import health as health_module


async def _ok_check() -> None:
    return None


async def _failing_check() -> None:
    raise RuntimeError("database password leaked in exception")


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_module.router)
    return app


@pytest.mark.asyncio
async def test_public_health_payload_omits_internal_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "_check_db", _ok_check)
    monkeypatch.setattr(health_module, "_check_redis", _ok_check)
    monkeypatch.setattr(health_module, "_check_provider", _ok_check)
    monkeypatch.setattr(health_module, "_gemini_pool_health", lambda: {"max_size": 200})
    health_module.set_availability(True, True, True, True)

    payload = await health_module.build_health_payload(include_internal_errors=False)

    assert payload == {"status": "healthy", "version": "1.0.0"}
    assert "components" not in payload
    assert "gemini_pool" not in payload
    assert "selenium" not in payload
    assert "upload_worker_pool" not in payload


@pytest.mark.asyncio
async def test_public_health_payload_keeps_error_details_admin_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health_module, "_check_db", _failing_check)
    monkeypatch.setattr(health_module, "_check_redis", _ok_check)
    monkeypatch.setattr(health_module, "_check_provider", _ok_check)
    monkeypatch.setattr(health_module, "_gemini_pool_health", lambda: {"max_size": 200})

    public_payload = await health_module.build_health_payload(include_internal_errors=False)
    admin_payload = await health_module.build_health_payload(include_internal_errors=True)

    assert public_payload == {"status": "degraded", "version": "1.0.0"}
    assert "database password leaked in exception" not in str(public_payload)
    assert admin_payload["components"]["db"]["status"] == "error"
    assert "database password leaked in exception" in admin_payload["components"]["db"]["error"]
    assert admin_payload["gemini_pool"] == {"max_size": 200}


def test_public_health_route_has_minimal_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "_check_db", _ok_check)
    monkeypatch.setattr(health_module, "_check_redis", _ok_check)
    monkeypatch.setattr(health_module, "_check_provider", _ok_check)

    resp = TestClient(_build_app()).get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "version": "1.0.0"}


def test_gemini_pool_health_logs_failure_summary(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "gemini-pool-secret"
    fake_client_pool = types.ModuleType("app.services.gemini.client_pool")
    fake_client_pool.GOOGLE_GENAI_AVAILABLE = True

    def _boom():
        raise RuntimeError(f"pool failed {secret}")

    fake_client_pool.get_client_pool = _boom
    monkeypatch.setitem(sys.modules, "app.services.gemini.client_pool", fake_client_pool)

    with caplog.at_level(logging.WARNING, logger=health_module.logger.name):
        payload = health_module._gemini_pool_health()

    assert payload["error"] == "pool unavailable"
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_public_root_route_omits_capability_flags() -> None:
    health_module.set_availability(True, True, True, True)

    resp = TestClient(_build_app()).get("/")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "status": "ok",
        "message": "Gemini Chat Backend API",
        "version": "1.0.0",
    }
    assert "selenium_available" not in body
    assert "upload_worker_pool_available" not in body
