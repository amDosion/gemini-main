"""Regression: the temp-image proxy must not be an SSRF primitive.

CANON-006 / W02R-020: GET /api/temp-images/{id}?no_redirect=1 proxies a
user/provider-controlled URL via _proxy_remote_image. Before the fix it used
httpx.AsyncClient(follow_redirects=True) with no outbound URL validation, so an
authenticated user who stored temp_url/url pointing at loopback/private/cloud-
metadata addresses turned the backend into a full-read SSRF proxy.

These tests pin the sink behaviour directly (no network, no DB): a restricted
target must be rejected by the shared url_security guard before any fetch.
"""

import pytest
from fastapi import HTTPException
from contextlib import asynccontextmanager
from types import SimpleNamespace

from app.routers.core import attachments
from app.utils.media_limits import MediaTooLargeError, decode_base64_data_url_limited


@pytest.mark.asyncio
async def test_proxy_remote_image_blocks_loopback():
    with pytest.raises(HTTPException) as exc_info:
        await attachments._proxy_remote_image("http://127.0.0.1:9/x", "image/png")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_proxy_remote_image_blocks_cloud_metadata_ip():
    with pytest.raises(HTTPException) as exc_info:
        await attachments._proxy_remote_image(
            "http://169.254.169.254/latest/meta-data/", "image/png"
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_proxy_remote_image_rejects_non_http_scheme():
    with pytest.raises(HTTPException) as exc_info:
        await attachments._proxy_remote_image("file:///etc/passwd", "image/png")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_proxy_remote_image_rejects_oversized_remote_response(monkeypatch):
    class _FakeResponse:
        status_code = 200
        headers = {"content-length": str(64 * 1024 * 1024)}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b""

    @asynccontextmanager
    async def _fake_stream(*args, **kwargs):
        yield _FakeResponse(), "https://example.test/image.png"

    monkeypatch.setattr(attachments, "validate_outbound_http_url", lambda url: url)
    monkeypatch.setattr(attachments, "stream_with_redirect_guard", _fake_stream)

    with pytest.raises(HTTPException) as exc_info:
        await attachments._proxy_remote_image("https://example.test/image.png", "image/png")

    assert exc_info.value.status_code == 413


def test_decode_base64_data_url_limited_rejects_oversized_before_decode():
    data_url = "data:image/png;base64," + ("A" * 128)
    with pytest.raises(MediaTooLargeError):
        decode_base64_data_url_limited(data_url, max_bytes=8)


def test_local_file_response_uses_private_cache_headers(monkeypatch, tmp_path):
    local_file = tmp_path / "owned.png"
    local_file.write_bytes(b"png")

    def _fake_resolve(file_url, config=None):
        assert config is not None
        return local_file

    monkeypatch.setattr(attachments, "resolve_local_public_file_path", _fake_resolve)

    response = attachments._build_local_file_response(
        "/api/storage/local-files/user-a/owned.png",
        "image/png",
        user_id="user-a",
    )

    assert response is not None
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Vary"] == "Authorization, Cookie"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


class _FakeQuery:
    def __init__(self, attachment):
        self._attachment = attachment

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._attachment


class _FakeDb:
    def __init__(self, attachment):
        self._attachment = attachment

    def query(self, *args, **kwargs):
        return _FakeQuery(self._attachment)


@pytest.mark.asyncio
async def test_temp_image_no_redirect_does_not_resolve_other_user_local_file(monkeypatch, tmp_path):
    local_file = tmp_path / "other-user.png"
    local_file.write_bytes(b"png")
    attachment = SimpleNamespace(
        id="att-other-local",
        user_id="user-b",
        temp_url=None,
        url="/api/storage/local-files/user-a/other-user.png",
        upload_status="completed",
        mime_type="image/png",
        google_file_uri=None,
        file_uri=None,
        gcs_uri=None,
    )

    def _fake_resolve(file_url, config=None):
        if config is None:
            return local_file
        return None

    monkeypatch.setattr(attachments, "resolve_local_public_file_path", _fake_resolve)

    with pytest.raises(HTTPException) as exc_info:
        await attachments.get_temp_image(
            "att-other-local",
            request=SimpleNamespace(headers={}, cookies={}),
            no_redirect=True,
            db=_FakeDb(attachment),
            current_user="user-b",
        )

    assert exc_info.value.status_code == 400
