"""SSRF-guard regression tests for AliyunProvider._create_bucket_client.

TDD pass:
  1. Write tests (they FAIL before the guard is added).
  2. Add validate_storage_egress_url call to _create_bucket_client.
  3. Tests pass; no real network call is made in any test.
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers / shared setup
# ---------------------------------------------------------------------------

_VALID_CONFIG = {
    "access_key_id": "AKID_PLAINTEXT",
    "access_key_secret": "AKSECRET_PLAINTEXT",
    "bucket": "my-bucket",
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
}

_SSRF_CONFIGS = [
    # loopback
    {"endpoint": "127.0.0.1"},
    # private RFC-1918
    {"endpoint": "192.168.1.10"},
    # link-local / EC2 metadata
    {"endpoint": "169.254.169.254"},
    # localhost hostname
    {"endpoint": "localhost"},
    # with explicit http scheme retained after _clean_endpoint strips it — guard
    # must still see https://169.254.169.254 before oss2.Bucket is called
    {"endpoint": "http://169.254.169.254"},
]


def _make_config(endpoint_override: str) -> dict:
    cfg = dict(_VALID_CONFIG)
    cfg["endpoint"] = endpoint_override
    return cfg


# ---------------------------------------------------------------------------
# Test 1: PUBLIC host — oss2.Bucket IS called (guard permits it), no real net
# ---------------------------------------------------------------------------

def test_create_bucket_client_permits_public_aliyun_endpoint(monkeypatch):
    """Guard must pass a legitimate public Aliyun OSS endpoint unchanged."""
    from app.services.storage import aliyun_provider

    bucket_calls: list[tuple] = []

    class _FakeBucket:
        pass

    def _fake_auth(key_id, key_secret):
        return object()

    def _fake_bucket(auth, endpoint, bucket_name):
        bucket_calls.append((endpoint, bucket_name))
        return _FakeBucket()

    # Patch validate_storage_egress_url to confirm it is called and returns the
    # URL without raising (real public host check skips DNS in unit tests).
    validated_urls: list[str] = []

    def _fake_validate(url: str) -> str:
        validated_urls.append(url)
        return url  # pretend it is safe

    monkeypatch.setattr(aliyun_provider.oss2, "Auth", _fake_auth)
    monkeypatch.setattr(aliyun_provider.oss2, "Bucket", _fake_bucket)
    monkeypatch.setattr(aliyun_provider, "validate_storage_egress_url", _fake_validate)

    provider = aliyun_provider.AliyunProvider(_VALID_CONFIG)
    bucket = provider._create_bucket_client()

    assert isinstance(bucket, _FakeBucket)
    assert len(bucket_calls) == 1, "oss2.Bucket must be called exactly once for a valid endpoint"
    assert len(validated_urls) == 1, "validate_storage_egress_url must be called"
    assert "oss-cn-hangzhou.aliyuncs.com" in validated_urls[0]


# ---------------------------------------------------------------------------
# Test 2: DENIED hosts — guard raises ValueError, oss2.Bucket is never called
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("endpoint", [
    "127.0.0.1",
    "192.168.1.10",
    "169.254.169.254",
    "localhost",
    "http://169.254.169.254",
])
def test_create_bucket_client_rejects_ssrf_endpoint(monkeypatch, endpoint):
    """Guard must raise ValueError for private/loopback/metadata endpoints.

    oss2.Bucket must NOT be called — the guard rejects before the network call.
    """
    from app.services.storage import aliyun_provider
    from app.utils.url_security import UnsafeURLError

    bucket_calls: list = []

    def _fake_auth(key_id, key_secret):
        return object()

    def _fake_bucket(*args, **kwargs):
        bucket_calls.append(args)
        return object()

    # Use the REAL validate_storage_egress_url so the guard logic is actually
    # exercised — no monkeypatching of the security primitive.
    monkeypatch.setattr(aliyun_provider.oss2, "Auth", _fake_auth)
    monkeypatch.setattr(aliyun_provider.oss2, "Bucket", _fake_bucket)

    provider = aliyun_provider.AliyunProvider(_make_config(endpoint))

    with pytest.raises(ValueError):
        provider._create_bucket_client()

    assert bucket_calls == [], (
        f"oss2.Bucket must not be called for SSRF endpoint {endpoint!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: upload() propagates the SSRF rejection without raising to the caller
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_returns_failure_for_ssrf_endpoint(monkeypatch):
    """upload() must return UploadResult(success=False) for a denied endpoint.

    No oss2.Bucket or network call should occur.
    """
    from app.services.storage import aliyun_provider

    bucket_calls: list = []

    def _fake_auth(key_id, key_secret):
        return object()

    def _fake_bucket(*args, **kwargs):
        bucket_calls.append(args)
        return object()

    monkeypatch.setattr(aliyun_provider.oss2, "Auth", _fake_auth)
    monkeypatch.setattr(aliyun_provider.oss2, "Bucket", _fake_bucket)

    provider = aliyun_provider.AliyunProvider(_make_config("127.0.0.1"))
    result = await provider.upload("img.png", b"data", "image/png")

    assert result.success is False
    assert result.error is not None
    assert bucket_calls == [], "oss2.Bucket must not be called for SSRF endpoint"
