"""Regression: storage preview/download must not let users self-bypass SSRF.

CANON-007 / W02R-013: _resolve_safe_preview_fetch_url rebuilt a host allowlist
from the *user's own* storage config (endpoint/domain/url_prefix). When
validate_outbound_http_url rejected a restricted (loopback/private/metadata-IP)
address, the helper returned the raw URL anyway if the host was in that
user-derived allowlist -> authenticated SSRF to internal services.

The private-network bypass must be controlled by the OPERATOR (deploy-time env),
never self-populated by an authenticated user's storage config.
"""

import pytest
from fastapi import HTTPException

from app.routers.storage import storage


def test_public_ip_literal_passes_without_bypass():
    # Sanity: a public IP literal needs no bypass and no DNS.
    assert (
        storage._resolve_safe_preview_fetch_url("http://1.1.1.1/x", set())
        == "http://1.1.1.1/x"
    )


def test_user_self_allowlisted_private_host_is_rejected():
    # Attacker put 127.0.0.1 in their storage config -> allowed_hosts contains it,
    # but with no operator allowlist the private-network rejection must stand.
    with pytest.raises(HTTPException) as exc_info:
        storage._resolve_safe_preview_fetch_url("http://127.0.0.1:6379/x", {"127.0.0.1"})
    assert exc_info.value.status_code == 400


def test_metadata_ip_rejected_even_if_user_allowlisted():
    with pytest.raises(HTTPException) as exc_info:
        storage._resolve_safe_preview_fetch_url(
            "http://169.254.169.254/latest/meta-data/", {"169.254.169.254"}
        )
    assert exc_info.value.status_code == 400


def test_operator_allowlisted_private_host_is_permitted(monkeypatch):
    # Operator explicitly allows an internal MinIO host at deploy time.
    monkeypatch.setattr(storage, "_operator_allowed_private_hosts", lambda: {"127.0.0.1"})
    assert (
        storage._resolve_safe_preview_fetch_url("http://127.0.0.1:9000/bucket/x", {"127.0.0.1"})
        == "http://127.0.0.1:9000/bucket/x"
    )
