"""Regression: S3Provider._create_client must reject SSRF endpoints before boto3 connects.

CANON-XXX / W02R-XXX: S3Provider._create_client passed user-configured 'endpoint'
directly to boto3.client(endpoint_url=...) without outbound URL validation.
An authenticated user with a custom S3-compatible endpoint pointing at loopback,
RFC-1918, or cloud-metadata addresses turned S3 configuration into an SSRF primitive.

The guard must reject restricted endpoints via validate_storage_egress_url BEFORE
boto3.client is invoked.
"""

import types
import pytest

from app.services.storage import s3_provider as s3_provider_mod
from app.services.storage.s3_provider import S3Provider

_BASE_CONFIG: dict = {
    "access_key_id": "AKIAtest",
    "secret_access_key": "secrettest",
    "region": "us-east-1",
    "bucket": "test-bucket",
}


class _StubS3Client:
    """Minimal boto3 S3 client stub — never makes network calls."""

    def list_objects_v2(self, **kwargs):
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "KeyCount": 0,
            "Contents": [],
            "CommonPrefixes": [],
            "IsTruncated": False,
        }

    def put_object(self, **kwargs):
        return {"ResponseMetadata": {"HTTPStatusCode": 200}, "ETag": '"abc"'}


def _stub_boto3(monkeypatch):
    """Replace the module-level boto3 reference with a stub that records calls."""
    calls: list = []

    def _client(**kwargs):
        calls.append(kwargs)
        return _StubS3Client()

    monkeypatch.setattr(
        s3_provider_mod, "boto3", types.SimpleNamespace(client=_client)
    )
    return calls


# ---------------------------------------------------------------------------
# DENIED tests — real validate_storage_egress_url rejects IP literals (no DNS)
# ---------------------------------------------------------------------------


def test_create_client_rejects_loopback_endpoint(monkeypatch):
    """Loopback endpoint must raise ValueError with 'SSRF'; boto3.client must not run."""
    boto3_calls = _stub_boto3(monkeypatch)

    provider = S3Provider({**_BASE_CONFIG, "endpoint": "http://127.0.0.1:9000"})

    with pytest.raises(ValueError, match="SSRF"):
        provider._create_client()

    assert boto3_calls == [], "boto3.client must NOT be called for a denied endpoint"


def test_create_client_rejects_metadata_ip_endpoint(monkeypatch):
    """Cloud metadata IP must raise ValueError with 'SSRF'; boto3.client must not run."""
    boto3_calls = _stub_boto3(monkeypatch)

    provider = S3Provider({**_BASE_CONFIG, "endpoint": "http://169.254.169.254/latest"})

    with pytest.raises(ValueError, match="SSRF"):
        provider._create_client()

    assert boto3_calls == []


def test_create_client_rejects_schemeless_private_endpoint(monkeypatch):
    """A schemeless private endpoint (treated as https://) must raise ValueError with 'SSRF'."""
    boto3_calls = _stub_boto3(monkeypatch)

    provider = S3Provider({**_BASE_CONFIG, "endpoint": "127.0.0.1:9000"})

    with pytest.raises(ValueError, match="SSRF"):
        provider._create_client()

    assert boto3_calls == []


# ---------------------------------------------------------------------------
# ALLOWED test — public endpoint passes; boto3 stubbed (no real network call)
# ---------------------------------------------------------------------------


def test_create_client_passes_for_public_endpoint(monkeypatch):
    """A public endpoint must not raise; boto3.client must be invoked."""
    import app.core.config as config_mod

    boto3_calls = _stub_boto3(monkeypatch)
    monkeypatch.setattr(
        config_mod.settings,
        "storage_s3_compatible_allowed_endpoint_hosts_raw",
        "s3.example.com",
        raising=False,
    )
    # Patch validate_storage_egress_url so no real DNS lookup occurs.
    # raising=False: attribute may not yet exist before the fix is applied.
    monkeypatch.setattr(
        s3_provider_mod,
        "validate_storage_egress_url",
        lambda url, **kwargs: url,
        raising=False,
    )

    provider = S3Provider({**_BASE_CONFIG, "endpoint": "https://s3.example.com"})
    client = provider._create_client()

    assert boto3_calls, "boto3.client must be called for a valid public endpoint"
    assert client is not None


def test_custom_endpoint_forces_path_style_addressing(monkeypatch):
    """Custom endpoints must not let boto3 connect to bucket.endpoint hosts."""
    import app.core.config as config_mod

    boto3_calls = _stub_boto3(monkeypatch)
    monkeypatch.setattr(
        config_mod.settings,
        "storage_s3_compatible_allowed_endpoint_hosts_raw",
        "s3.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        s3_provider_mod,
        "validate_storage_egress_url",
        lambda url, **kwargs: url,
        raising=False,
    )

    provider = S3Provider({
        **_BASE_CONFIG,
        "endpoint": "https://s3.example.com",
        "force_path_style": False,
    })
    provider._create_client()

    config = boto3_calls[0]["config"]
    assert config.s3["addressing_style"] == "path"


def test_create_client_rejects_public_endpoint_without_operator_allowlist(monkeypatch):
    boto3_calls = _stub_boto3(monkeypatch)

    provider = S3Provider({**_BASE_CONFIG, "endpoint": "https://s3.example.com"})

    with pytest.raises(ValueError, match="allowlisted"):
        provider._create_client()

    assert boto3_calls == []


# ---------------------------------------------------------------------------
# NO-ENDPOINT test — AWS default path; validation must be skipped
# ---------------------------------------------------------------------------


def test_create_client_no_endpoint_skips_validation(monkeypatch):
    """When no custom endpoint is configured, validation is skipped (AWS default path)."""
    validate_calls: list = []

    def _track_validate(url, **kwargs):
        validate_calls.append(url)
        return url

    boto3_calls = _stub_boto3(monkeypatch)
    monkeypatch.setattr(
        s3_provider_mod,
        "validate_storage_egress_url",
        _track_validate,
        raising=False,
    )

    provider = S3Provider(_BASE_CONFIG)  # no 'endpoint' key
    provider._create_client()

    assert boto3_calls, "boto3.client must be called for the AWS default path"
    assert validate_calls == [], "validate_storage_egress_url must NOT run when no endpoint is set"


# ---------------------------------------------------------------------------
# Integration test via upload()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_returns_failure_for_ssrf_endpoint(monkeypatch):
    """upload() must return UploadResult(success=False) with 'SSRF' in error for denied endpoints."""
    boto3_calls = _stub_boto3(monkeypatch)

    provider = S3Provider({**_BASE_CONFIG, "endpoint": "http://127.0.0.1:9000"})
    result = await provider.upload("test.png", b"data", "image/png")

    assert result.success is False, "upload must fail for an SSRF endpoint"
    assert "SSRF" in (result.error or ""), f"error must mention SSRF, got: {result.error!r}"
    assert boto3_calls == [], "boto3.client must NOT be called for a denied endpoint"
