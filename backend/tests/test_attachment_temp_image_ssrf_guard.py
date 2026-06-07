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

from app.routers.core import attachments


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
