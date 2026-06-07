"""Boundary primitive for user-configured outbound endpoints (storage provider
domain / custom base_url) — SSRF allow/deny with an operator-only private-host
allowlist.

Residual-SSRF follow-up to the committed url_security boundary: storage providers
(lsky/s3/aliyun) and custom provider base_urls take a user-supplied host. Public
destinations are allowed; a restricted (private/loopback/metadata) destination is
allowed ONLY when the OPERATOR allowlisted its host (never self-populated from a
user's own config), so an authenticated user cannot turn a configured endpoint
into an internal SSRF probe.
"""

import pytest

from app.utils.url_security import (
    UnsafeURLError,
    _resolve_single_allowed_ip,
    operator_allowed_private_hosts,
    validate_storage_egress_url,
)


def test_public_ip_endpoint_is_allowed():
    # public IP literal -> no DNS, passes
    assert validate_storage_egress_url("https://1.1.1.1/api/v1/upload") == "https://1.1.1.1/api/v1/upload"


def test_private_endpoint_is_denied_without_operator_allowlist():
    with pytest.raises(UnsafeURLError):
        validate_storage_egress_url("http://10.0.0.5/api/v1/upload")


def test_loopback_endpoint_is_denied_without_operator_allowlist():
    with pytest.raises(UnsafeURLError):
        validate_storage_egress_url("http://127.0.0.1:9000/api/v1/upload")


def test_metadata_endpoint_is_denied_without_operator_allowlist():
    with pytest.raises(UnsafeURLError):
        validate_storage_egress_url("http://169.254.169.254/latest/meta-data/")


def test_private_endpoint_allowed_when_operator_allowlists_host():
    # operator opted in (e.g. self-hosted MinIO/lsky on a private network)
    assert (
        validate_storage_egress_url(
            "http://10.0.0.5/api/v1/upload", allow_hosts={"10.0.0.5"}
        )
        == "http://10.0.0.5/api/v1/upload"
    )


def test_non_http_scheme_is_denied_even_when_host_allowlisted():
    with pytest.raises(UnsafeURLError):
        validate_storage_egress_url("file:///etc/passwd", allow_hosts={""})


def test_empty_url_is_denied():
    with pytest.raises(UnsafeURLError):
        validate_storage_egress_url("")


def test_operator_allowlist_reads_env_setting(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(
        config_mod.settings,
        "storage_preview_allowed_private_hosts_raw",
        "minio.internal, 10.0.0.5",
        raising=False,
    )
    hosts = operator_allowed_private_hosts()
    assert "minio.internal" in hosts
    assert "10.0.0.5" in hosts


def test_operator_allowlist_default_empty(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(
        config_mod.settings, "storage_preview_allowed_private_hosts_raw", "", raising=False
    )
    assert operator_allowed_private_hosts() == set()


def test_endpoint_uses_operator_env_allowlist_when_allow_hosts_omitted(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(
        config_mod.settings,
        "storage_preview_allowed_private_hosts_raw",
        "10.0.0.5",
        raising=False,
    )
    # no explicit allow_hosts -> falls back to operator env allowlist
    assert (
        validate_storage_egress_url("http://10.0.0.5/api/v1/upload")
        == "http://10.0.0.5/api/v1/upload"
    )


# --- connect-time IP pinning must stay CONSISTENT with the validation gate ---
# Regression: validate_storage_egress_url allowed an operator-allowlisted private
# host, but the pinning backend (_resolve_single_allowed_ip) re-checked the
# resolved IP and rejected it, so allowlisted self-hosted storage broke at connect.


def test_pinning_resolve_honors_operator_allowlist_for_private_ip(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(
        config_mod.settings,
        "storage_preview_allowed_private_hosts_raw",
        "192.168.1.50",
        raising=False,
    )
    # operator-allowlisted private IP literal must be returned (pinned), not rejected
    assert _resolve_single_allowed_ip("192.168.1.50", 80) == "192.168.1.50"


def test_pinning_resolve_rejects_non_allowlisted_private_ip(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(
        config_mod.settings, "storage_preview_allowed_private_hosts_raw", "", raising=False
    )
    with pytest.raises(UnsafeURLError):
        _resolve_single_allowed_ip("10.0.0.5", 80)
