"""
TDD regression tests for SSRF guard in upload_to_lsky_sync.

Tests:
1. DENIED: A private/loopback upload_url must be rejected BEFORE any network call.
2. ALLOWED: A public-host upload_url must proceed (network call mocked).
"""

import pytest
from unittest.mock import patch, MagicMock

# Module path where `requests` is imported inside upload_to_lsky_sync.
# The function does `import requests` locally, so the live module is
# `requests` in sys.modules — patch it at the canonical path.
_REQUESTS_POST = "requests.post"

# validate_storage_egress_url is called from storage.py; we can patch it
# at the storage module to control behaviour in public-host tests without
# triggering real DNS resolution in the WSL/test environment.
_EGRESS_VALIDATE = (
    "app.routers.storage.storage.validate_storage_egress_url"
)


def _call(domain: str, config_override: dict | None = None) -> dict:
    """Invoke upload_to_lsky_sync with the given domain."""
    from app.routers.storage.storage import upload_to_lsky_sync

    config = {
        "domain": domain,
        "token": "test-token",
        "strategyId": None,
    }
    if config_override:
        config.update(config_override)
    return upload_to_lsky_sync("test.png", b"imgdata", "image/png", config)


# ---------------------------------------------------------------------------
# DENIED: private / loopback host — must fail closed WITHOUT a network call
# ---------------------------------------------------------------------------

class TestLskyUploadSsrfDenied:
    """SSRF guard must reject private/loopback targets before touching the wire."""

    @pytest.mark.parametrize("domain", [
        "http://127.0.0.1:8080",
        "http://localhost",
        "http://169.254.169.254",            # AWS/GCP metadata endpoint
        "http://192.168.1.10",               # RFC-1918 private range
        "http://10.0.0.1",                   # RFC-1918 private range
        "http://[::1]",                      # IPv6 loopback
    ])
    def test_ssrf_denied_no_network_call(self, domain):
        """Rejected domains must return a failure dict and never call requests.post."""
        with patch(_REQUESTS_POST) as mock_post:
            result = _call(domain)

        # Guard must have blocked the request — network must NOT be touched
        mock_post.assert_not_called()

        # Must return failure dict — not raise
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert result.get("error"), "Expected a non-empty error message"


# ---------------------------------------------------------------------------
# ALLOWED: public host — guard passes through, network call is mocked
# ---------------------------------------------------------------------------

class TestLskyUploadPublicHost:
    """A legitimate public domain must reach requests.post (mocked)."""

    def test_public_host_calls_requests_post(self):
        """Public domain must pass the SSRF guard and reach the mocked HTTP layer."""
        upload_url = "https://img.lsky.example.com/api/v1/upload"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": True,
            "data": {"links": {"url": "https://img.lsky.example.com/test.png"}},
        }

        # Patch the egress validator to pass through (simulates a real public host)
        # and patch requests.post to avoid a real network call.
        with patch(_EGRESS_VALIDATE, return_value=upload_url) as mock_validate, \
             patch(_REQUESTS_POST, return_value=mock_resp) as mock_post:
            result = _call("https://img.lsky.example.com")

        mock_validate.assert_called_once_with(upload_url)
        mock_post.assert_called_once()
        assert result.get("success") is True
        assert result.get("url") == "https://img.lsky.example.com/test.png"

    def test_public_host_passes_allow_redirects_false(self):
        """requests.post must be called with allow_redirects=False."""
        upload_url = "https://cdn.lsky.example.com/api/v1/upload"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": True,
            "data": {"links": {"url": "https://cdn.lsky.example.com/img.png"}},
        }

        with patch(_EGRESS_VALIDATE, return_value=upload_url), \
             patch(_REQUESTS_POST, return_value=mock_resp) as mock_post:
            _call("https://cdn.lsky.example.com")

        _, kwargs = mock_post.call_args
        assert kwargs.get("allow_redirects") is False, (
            "requests.post must include allow_redirects=False to prevent redirect-bypass SSRF"
        )
