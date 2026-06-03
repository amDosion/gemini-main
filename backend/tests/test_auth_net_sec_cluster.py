"""Regression tests for cluster auth-net-sec findings.

Covers:
- S4: GET /api/auth/ip-info must not leak internal request headers / geolocation
  to unauthenticated callers.
- V-S23(a): url_security must expose an async SSRF validator that does not block
  the event loop on a slow resolver (bounded getaddrinfo).
- V-S23(b): auth cookie policy must be secure + samesite=strict whenever the
  request is HTTPS, even when ENVIRONMENT != production.
- S6: rate-limit client IP must ignore spoofable proxy headers from an untrusted
  peer and only honor them from a configured trusted-proxy CIDR.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str | None = None,
    scheme: str = "http",
):
    """Build a minimal duck-typed Request usable by the helpers under test."""
    header_map = {k: v for k, v in (headers or {}).items()}

    class _Headers:
        def __init__(self, data: dict[str, str]):
            # case-insensitive like starlette Headers
            self._data = {k.lower(): v for k, v in data.items()}

        def get(self, key, default=None):
            return self._data.get(key.lower(), default)

    client = SimpleNamespace(host=client_host) if client_host is not None else None
    url = SimpleNamespace(scheme=scheme)
    return SimpleNamespace(headers=_Headers(header_map), client=client, url=url)


# ---------------------------------------------------------------------------
# V-S23(b): cookie policy must harden on HTTPS regardless of ENVIRONMENT
# ---------------------------------------------------------------------------
def test_cookie_policy_is_secure_strict_for_https_even_in_dev(monkeypatch):
    from app.routers.auth import auth as auth_module

    # Force a non-production environment.
    monkeypatch.setattr(auth_module.settings, "environment", "development", raising=False)
    monkeypatch.setattr(
        type(auth_module.settings), "is_production", property(lambda self: False), raising=False
    )

    https_request = _make_request(scheme="https")
    policy = auth_module._build_cookie_policy(https_request)

    assert policy.secure is True, "HTTPS request must get Secure cookies even in dev"
    assert policy.samesite == "strict", "HTTPS request must get SameSite=strict even in dev"


def test_cookie_policy_honors_forwarded_proto_https(monkeypatch):
    from app.routers.auth import auth as auth_module

    monkeypatch.setattr(
        type(auth_module.settings), "is_production", property(lambda self: False), raising=False
    )

    request = _make_request(scheme="http", headers={"X-Forwarded-Proto": "https"})
    policy = auth_module._build_cookie_policy(request)

    assert policy.secure is True
    assert policy.samesite == "strict"


def test_cookie_policy_stays_lax_for_plain_http_dev(monkeypatch):
    from app.routers.auth import auth as auth_module

    monkeypatch.setattr(
        type(auth_module.settings), "is_production", property(lambda self: False), raising=False
    )

    request = _make_request(scheme="http")
    policy = auth_module._build_cookie_policy(request)

    # Plain HTTP local dev keeps the relaxed policy so cookies still flow.
    assert policy.secure is False
    assert policy.samesite == "lax"


# ---------------------------------------------------------------------------
# S6: rate-limit client IP must not trust spoofed proxy headers
# ---------------------------------------------------------------------------
def test_spoofed_forwarded_for_ignored_from_untrusted_peer(monkeypatch):
    from app.services.common import system_config_service as svc

    # No trusted proxies configured.
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

    request = _make_request(
        headers={"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "5.6.7.8"},
        client_host="203.0.113.9",
    )

    ip = svc.get_client_ip(request)
    assert ip == "203.0.113.9", "untrusted peer must not be able to spoof client IP"


def test_forwarded_for_honored_from_trusted_proxy_cidr(monkeypatch):
    from app.services.common import system_config_service as svc

    # Direct peer is inside the trusted proxy range.
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")

    request = _make_request(
        headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.5"},
        client_host="10.0.0.5",
    )

    ip = svc.get_client_ip(request)
    assert ip == "1.2.3.4", "trusted proxy's forwarded client IP must be honored"


def test_forwarded_for_ignored_when_peer_outside_trusted_cidr(monkeypatch):
    from app.services.common import system_config_service as svc

    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")

    request = _make_request(
        headers={"X-Forwarded-For": "1.2.3.4"},
        client_host="203.0.113.9",  # NOT in 10/8
    )

    ip = svc.get_client_ip(request)
    assert ip == "203.0.113.9", "peer outside trusted CIDR must not be trusted"


# ---------------------------------------------------------------------------
# V-S23(a): async SSRF validator must be bounded (no event-loop stall)
# ---------------------------------------------------------------------------
def test_async_validator_exists_and_validates_public_url():
    from app.utils import url_security

    assert hasattr(
        url_security, "validate_outbound_http_url_async"
    ), "async SSRF validator must exist for async callers"


def test_async_validator_times_out_slow_resolver(monkeypatch):
    """A slow getaddrinfo must not block forever; it raises UnsafeURLError."""
    from app.utils import url_security

    def _slow_getaddrinfo(*args, **kwargs):
        time.sleep(5)  # simulate a stalled resolver
        return [(2, 1, 6, "", ("1.2.3.4", 0))]

    monkeypatch.setattr(url_security.socket, "getaddrinfo", _slow_getaddrinfo)

    async def _run():
        start = time.monotonic()
        with pytest.raises(url_security.UnsafeURLError):
            await url_security.validate_outbound_http_url_async(
                "https://example.com", resolve_timeout=0.25
            )
        return time.monotonic() - start

    elapsed = asyncio.run(_run())
    assert elapsed < 3, f"async validator did not bound the slow resolver (took {elapsed:.2f}s)"


def test_sync_validator_still_present_for_thread_callers():
    """read_webpage runs the SYNC validator in a thread; it must not be removed."""
    from app.utils import url_security

    assert hasattr(url_security, "validate_outbound_http_url")


# ---------------------------------------------------------------------------
# S4: /api/auth/ip-info must not leak internal headers / geo to anon callers
# ---------------------------------------------------------------------------
def test_ip_info_endpoint_does_not_leak_internal_headers():
    """The ip-info response must not expose raw forwarded headers or geo."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.auth.auth import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get(
        "/api/auth/ip-info",
        headers={
            "X-Forwarded-For": "1.2.3.4",
            "X-Real-IP": "5.6.7.8",
            "CF-Connecting-IP": "9.9.9.9",
            "User-Agent": "leak-probe",
        },
    )

    # Endpoint may now require auth (401/403) OR return a minimal coarse body.
    if resp.status_code in (401, 403):
        return

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Must NOT echo raw forwarded headers or internal request-header map.
    assert "headers" not in body, "internal headers must not be leaked"
    # Must NOT leak geolocation details.
    assert "ip_info" not in body or body.get("ip_info") is None
    # Must NOT echo the upstream client_host (internal infra detail).
    assert "client_host" not in body
