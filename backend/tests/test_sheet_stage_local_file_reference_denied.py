"""Regression: sheet-stage ingest must not read arbitrary server-local files.

CANON-008 / W02R-006: build_sheet_ingest_kwargs_from_request treated a non-http,
non-data `file_url` as a server filesystem path and called Path(file_url).read_bytes()
with only exists()/is_file() checks (no allow-root, no ownership, no feature flag).
Any authenticated user could read arbitrary host files (LFI) whose bytes were then
base64-ingested and surfaced back.

A non-http/non-data file_url must be rejected here and routed only through the
vetted resolve_file_reference callback, never read directly.
"""

import base64
import os
import tempfile

import pytest

from app.services.agent.sheet_stage_protocol_service import (
    build_sheet_ingest_kwargs_from_request,
)


def _write_secret_file() -> str:
    fd, path = tempfile.mkstemp(prefix="canon008-secret-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("TOP-SECRET-DO-NOT-READ")
    return path


def test_direct_local_file_url_is_rejected_not_read():
    secret_path = _write_secret_file()
    try:
        with pytest.raises(ValueError):
            build_sheet_ingest_kwargs_from_request(
                request_body={"file_url": secret_path},
                user_id="attacker",
                resolve_file_reference=None,
            )
    finally:
        os.remove(secret_path)


def test_direct_local_file_url_never_leaks_content():
    secret_path = _write_secret_file()
    encoded_secret = base64.b64encode(b"TOP-SECRET-DO-NOT-READ").decode("ascii")
    try:
        try:
            kwargs = build_sheet_ingest_kwargs_from_request(
                request_body={"file_url": secret_path},
                user_id="attacker",
                resolve_file_reference=None,
            )
        except ValueError:
            return  # rejected outright — acceptable and preferred
        # If it did not raise, it must not have read/exposed the file bytes.
        assert kwargs.get("content") != encoded_secret
        assert kwargs.get("file_url") != secret_path or kwargs.get("content_encoding") != "base64"
    finally:
        os.remove(secret_path)


def test_http_file_url_still_passes_through():
    kwargs = build_sheet_ingest_kwargs_from_request(
        request_body={"file_url": "https://example.com/data.csv"},
        user_id="u1",
        resolve_file_reference=None,
    )
    assert kwargs.get("file_url") == "https://example.com/data.csv"
