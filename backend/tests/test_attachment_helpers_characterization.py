"""Characterization pin for AttachmentService pure helpers (refactor A4).

These helpers are being extracted from the 1153-line attachment_service.py
monolith into focused modules. Behavior must be IDENTICAL after the split, so
pin the observable contract of each helper FIRST (red→green guard).

Covered helpers (all pure / DB-free except _find_attachment_by_url which only
reads the passed messages list):
  - _build_generated_filename
  - _resolve_provider_asset_metadata
  - _is_persistent_storage_url
  - _is_google_provider_http_file_url
  - _parse_data_url
  - _find_attachment_by_url
"""

import base64

import pytest

from app.services.common.attachment_service import AttachmentService


def _svc() -> AttachmentService:
    # These helpers never touch self.db, so a sentinel is fine.
    return AttachmentService(db=object())


def test_build_generated_filename_png_extension():
    name = _svc()._build_generated_filename("generated", "image/png")
    assert name.startswith("generated-")
    assert name.endswith(".png")


def test_build_generated_filename_jpeg_normalized_to_jpg():
    # mimetypes guesses ".jpe" for image/jpeg; helper normalizes to ".jpg".
    name = _svc()._build_generated_filename("gen", "image/jpeg")
    assert name.endswith(".jpg")


def test_build_generated_filename_unknown_mime_falls_back_to_bin():
    name = _svc()._build_generated_filename("gen", "application/x-totally-unknown")
    assert name.endswith(".bin")


def test_build_generated_filename_strips_mime_params():
    name = _svc()._build_generated_filename("gen", "image/png; charset=binary")
    assert name.endswith(".png")


def test_resolve_provider_asset_metadata_prefers_explicit_file_uri():
    file_uri, google_file_uri = _svc()._resolve_provider_asset_metadata(
        ai_url="data:image/png;base64,AAAA",
        file_uri="files/explicit-123",
    )
    assert file_uri == "files/explicit-123"
    # normalize_gemini_file_name returns "files/<id>" form.
    assert google_file_uri == "files/explicit-123"


def test_resolve_provider_asset_metadata_falls_back_to_gs_ai_url():
    file_uri, google_file_uri = _svc()._resolve_provider_asset_metadata(
        ai_url="gs://bucket/object.mp4",
    )
    assert file_uri == "gs://bucket/object.mp4"
    assert google_file_uri == ""


def test_resolve_provider_asset_metadata_empty_for_plain_http():
    file_uri, google_file_uri = _svc()._resolve_provider_asset_metadata(
        ai_url="https://example.com/img.png",
    )
    assert file_uri == ""
    assert google_file_uri == ""


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://cdn.example.com/a.png", True),
        ("http://example.com/x", True),
        ("", False),
        (None, False),
        ("gs://bucket/o", False),
        ("files/abc", False),
        ("data:image/png;base64,AAAA", False),
    ],
)
def test_is_persistent_storage_url(url, expected):
    assert _svc()._is_persistent_storage_url(url) is expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://generativelanguage.googleapis.com/v1/files/abc", True),
        ("https://example.com/files/abc", True),
        ("https://example.com/images/abc", False),
        ("http://example.com/files/abc", False),
        ("", False),
    ],
)
def test_is_google_provider_http_file_url(url, expected):
    assert _svc()._is_google_provider_http_file_url(url) is expected


def test_parse_data_url_extracts_mime_and_payload():
    payload = base64.b64encode(b"hello").decode("ascii")
    data_url = f"data:image/webp;base64,{payload}"
    mime, b64 = _svc()._parse_data_url(data_url)
    assert mime == "image/webp"
    assert base64.b64decode(b64) == b"hello"


def test_parse_data_url_rejects_non_data_url():
    with pytest.raises(ValueError):
        _svc()._parse_data_url("https://example.com/x.png")


def test_find_attachment_by_url_matches_url_then_temp_url():
    messages = [
        {"attachments": [{"id": "a1", "url": "http://x/1.png"}]},
        {"attachments": [{"id": "a2", "tempUrl": "blob:abc"}]},
    ]
    assert _svc()._find_attachment_by_url("http://x/1.png", messages) == "a1"
    assert _svc()._find_attachment_by_url("blob:abc", messages) == "a2"
    assert _svc()._find_attachment_by_url("http://x/none", messages) is None


def test_find_attachment_by_url_returns_most_recent_first():
    # Two messages both reference the same url; reversed() means the LAST
    # message in the list wins (newest-to-oldest scan).
    messages = [
        {"attachments": [{"id": "old", "url": "http://x/dup.png"}]},
        {"attachments": [{"id": "new", "url": "http://x/dup.png"}]},
    ]
    assert _svc()._find_attachment_by_url("http://x/dup.png", messages) == "new"
