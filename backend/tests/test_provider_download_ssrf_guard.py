"""Regression: provider image downloads must pass the outbound SSRF guard.

CANON-011 (Grok) / CANON-012 (Tongyi): provider services download user-supplied
reference / expansion image URLs server-side (bytes are then sent to the
provider) with no SSRF validation, enabling authenticated blind SSRF / internal
probing.

These pin the two cleanly unit-testable sinks. (The PDF extractors and aiohttp
download sinks share the same one-line guard and are tracked as a follow-up.)
"""

import pytest

from app.services.grok.image_editor import ImageEditor
from app.services.tongyi import image_expand as image_expand_mod
from app.utils.url_security import UnsafeURLError


def test_tongyi_download_image_blocks_loopback_without_fetching(monkeypatch):
    calls = {"n": 0}

    def _must_not_be_called(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("requests.get must not run for a blocked SSRF URL")

    monkeypatch.setattr(image_expand_mod.requests, "get", _must_not_be_called)
    result = image_expand_mod.ImageExpandService.download_image("http://127.0.0.1:9/x")
    assert result is None
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_grok_load_image_bytes_blocks_loopback():
    editor = ImageEditor(api_key="k", base_url="https://api.example.com")
    with pytest.raises(UnsafeURLError):
        await editor._load_image_bytes("http://127.0.0.1:9/x")


@pytest.mark.asyncio
async def test_grok_load_image_bytes_blocks_metadata_ip():
    editor = ImageEditor(api_key="k", base_url="https://api.example.com")
    with pytest.raises(UnsafeURLError):
        await editor._load_image_bytes("http://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_openai_pdf_extractor_blocks_loopback_pdf_url():
    # CANON-010: pdf_url is attachment/user-controlled and fetched server-side.
    from app.services.openai.pdf_extractor import OpenAIPDFExtractor

    extractor = OpenAIPDFExtractor(api_key="k")
    with pytest.raises(UnsafeURLError):
        await extractor._resolve_pdf_bytes({"pdf_url": "http://127.0.0.1:9/x.pdf"}, {})


@pytest.mark.asyncio
async def test_gemini_pdf_extractor_blocks_loopback_pdf_url():
    # CANON-010: same sink in the Gemini extractor.
    from app.services.gemini.common.pdf_extractor import PDFExtractorService

    extractor = PDFExtractorService()
    with pytest.raises(UnsafeURLError):
        await extractor.extract_pdf_data(
            prompt="x",
            model="gemini-2.0-flash",
            reference_images={"pdf_url": "http://127.0.0.1:9/x.pdf"},
        )


def test_tongyi_upload_to_dashscope_blocks_loopback_image_url(monkeypatch):
    # CANON-012: a loopback/private image_url must be rejected up-front, before the
    # upload-policy fetch or the image download (so NO outbound request is made).
    from app.services.tongyi import file_upload as file_upload_mod

    calls = {"n": 0}

    def _must_not_be_called(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("requests.get must not run for a blocked SSRF URL")

    monkeypatch.setattr(file_upload_mod.requests, "get", _must_not_be_called)
    result = file_upload_mod.upload_to_dashscope("http://127.0.0.1:9/x.jpg", api_key="k")
    assert result.success is False
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_gemini_expand_service_blocks_loopback_image_url():
    # CANON-021: _load_image_from_path downloads a user-supplied http(s) image URL
    # via aiohttp; a restricted target must be rejected before the download.
    from app.services.gemini.vertexai.expand_service import ExpandService

    svc = ExpandService()
    with pytest.raises(UnsafeURLError):
        await svc._load_image_from_path("http://127.0.0.1:9/x.png")


@pytest.mark.asyncio
async def test_gemini_expand_service_rejects_arbitrary_local_path(tmp_path):
    # CANON-017/021: _load_image_from_path's local-file branch must not read an
    # arbitrary path; only allow-rooted local-files references are permitted.
    from app.services.gemini.vertexai.expand_service import ExpandService

    secret = tmp_path / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n")
    svc = ExpandService()
    with pytest.raises(ValueError):
        await svc._load_image_from_path(str(secret))


@pytest.mark.asyncio
async def test_tongyi_upload_async_blocks_loopback_before_policy(monkeypatch):
    # CANON-012 (production path): upload_to_dashscope_async is the variant actually
    # used by image_edit / virtual_tryon. A loopback image_url must be rejected
    # up-front, before the upload-policy fetch (so NO outbound request is made).
    from app.services.tongyi import file_upload as file_upload_mod

    calls = {"n": 0}

    async def _track(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("upload-policy fetch must not run for a blocked URL")

    monkeypatch.setattr(file_upload_mod, "_get_upload_policy_async", _track)
    result = await file_upload_mod.upload_to_dashscope_async("http://127.0.0.1:9/x.jpg", api_key="k")
    assert result.success is False
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_geminiapi_conversational_download_blocks_loopback():
    # CANON-021: the geminiapi conversational image-edit reference download must run
    # through the shared egress guard (initial URL + every redirect hop validated).
    from app.services.gemini.geminiapi.conversational_image_edit_service import (
        ConversationalImageEditService,
    )

    with pytest.raises(UnsafeURLError):
        await ConversationalImageEditService._download_http_image_guarded("http://127.0.0.1:9/x.png")


def test_workflow_remote_reference_blocks_redirect_to_internal(monkeypatch):
    # CANON-018 / W02R-023: the workflow remote-reference loader validated the
    # initial URL but urlopen followed redirects; a 302 -> internal host must be
    # re-validated per hop and rejected.
    import ipaddress
    from types import SimpleNamespace
    from urllib.error import HTTPError

    from app.services.agent.workflow_engine import references as refs

    def _parse_ip(host):
        try:
            return ipaddress.ip_address(host)
        except ValueError:
            return None

    engine = SimpleNamespace(
        _is_disallowed_reference_hostname=lambda h: False,
        _parse_reference_ip_host=_parse_ip,
        _is_disallowed_reference_ip=lambda ip: ip.is_loopback or ip.is_private or ip.is_link_local,
    )

    class _Opener:
        def open(self, request, timeout=None):
            raise HTTPError(
                getattr(request, "full_url", "http://1.1.1.1/start"),
                302,
                "Found",
                {"Location": "http://127.0.0.1/secret"},
                None,
            )

    monkeypatch.setattr(refs, "build_opener", lambda *a, **k: _Opener())
    with pytest.raises(ValueError):
        refs.load_binary_from_reference(engine, "http://1.1.1.1/start", 1024 * 1024)

def test_tongyi_execute_with_fallback_blocks_loopback_before_submit(monkeypatch):
    # svc-providers-1: execute_with_fallback is the real entry point used by
    # tongyi_service.expand_image. A loopback image_url must be rejected up-front
    # before submit_task (which would forward the URL to DashScope) is called.
    calls = {"submit": 0, "post": 0}

    def _must_not_submit(*args, **kwargs):
        calls["submit"] += 1
        raise AssertionError("submit_task must not run for a blocked SSRF URL")

    def _must_not_post(*args, **kwargs):
        calls["post"] += 1
        raise AssertionError("requests.post must not run for a blocked SSRF URL")

    svc = image_expand_mod.ImageExpandService()
    monkeypatch.setattr(svc, "submit_task", _must_not_submit)
    monkeypatch.setattr(image_expand_mod.requests, "post", _must_not_post)

    result = svc.execute_with_fallback(
        image_url="http://127.0.0.1:9/secret.png",
        api_key="test-key",
        parameters={},
    )
    assert result.success is False
    assert calls["submit"] == 0
    assert calls["post"] == 0


def test_tongyi_execute_with_fallback_allows_oss_scheme(monkeypatch):
    # svc-providers-1: oss:// URLs are not HTTP fetches — DashScope handles them
    # natively.  The SSRF guard must not block oss:// and must pass it through to
    # submit_task unchanged.
    submitted = {}

    def _fake_submit(image_url, api_key, parameters, use_oss_resolve=False):
        submitted["image_url"] = image_url
        submitted["use_oss_resolve"] = use_oss_resolve
        return False, None, "test-short-circuit"

    svc = image_expand_mod.ImageExpandService()
    monkeypatch.setattr(svc, "submit_task", _fake_submit)

    result = svc.execute_with_fallback(
        image_url="oss://test-bucket/path/to/image.png",
        api_key="test-key",
        parameters={},
    )
    # The call must reach submit_task (not be blocked by the SSRF guard).
    assert "image_url" in submitted
    assert submitted["image_url"] == "oss://test-bucket/path/to/image.png"
    assert submitted["use_oss_resolve"] is True
    # Submit returned failure (as arranged), so execute_with_fallback also fails.
    assert result.success is False
