"""Coverage-focused tests for app.routers.storage.storage.

These tests exercise the storage router's pure helpers plus the FastAPI
endpoints via TestClient with the DB session and auth dependency overridden,
and StorageManager / decrypt / redis / httpx boundaries mocked. They assert
real behaviour: status codes, response shapes, permission / fail-closed
branches and error mapping.
"""
import importlib
import logging
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.routers.storage.storage as storage_mod
from app.core.dependencies import require_current_user, get_cache
from app.core.database import get_db
from app.core.encryption import ConfigDecryptionError
from app.utils.url_security import UnsafeURLError


TEST_USER = "user-storage-1"


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_db():
    return MagicMock(name="db_session")


@pytest.fixture
def client(fake_db):
    """TestClient with auth + db + cache dependencies overridden."""
    app = FastAPI()
    app.include_router(storage_mod.router)

    app.dependency_overrides[require_current_user] = lambda: TEST_USER
    app.dependency_overrides[storage_mod.require_admin_user] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: fake_db
    # Default: cache unavailable (router gracefully degrades)
    app.dependency_overrides[storage_mod._get_cache_optional] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _storage_log_text(caplog) -> str:
    return "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == storage_mod.logger.name
    )


# ===========================================================================
# Pure helper functions
# ===========================================================================
def test_mask_url_masks_credentials():
    masked = storage_mod._mask_url("postgres://user:secret@host:5432/db")
    assert masked == "postgres://user:***@host:5432/db"


def test_mask_url_passthrough_when_no_credentials():
    assert storage_mod._mask_url("https://example.com/path") == "https://example.com/path"
    assert storage_mod._mask_url("not-a-url") == "not-a-url"
    # creds without ':' separator are returned unchanged
    assert storage_mod._mask_url("scheme://token@host") == "scheme://token@host"


def test_storage_revision_key_normalizes_blank_user():
    assert storage_mod._storage_revision_key("") == f"{storage_mod._STORAGE_REVISION_KEY_PREFIX}default"
    assert storage_mod._storage_revision_key("  abc  ") == f"{storage_mod._STORAGE_REVISION_KEY_PREFIX}abc"


def test_browse_total_cache_key_is_deterministic_and_path_normalized():
    key1 = storage_mod._storage_browse_total_cache_key("u", "s", "/a/b/", 3)
    key2 = storage_mod._storage_browse_total_cache_key("u", "s", "a/b", 3)
    assert key1 == key2
    assert key1.startswith("cache:storage:browse-total:u:s:3:")
    # bad revision falls back to 0
    bad_rev = storage_mod._storage_browse_total_cache_key("u", "s", "a", "not-int")
    assert ":0:" in bad_rev


def test_metadata_cache_key_clamps_negative_revision():
    key = storage_mod._storage_metadata_cache_key("u", "https://x/y", storage_revision=-5)
    assert ":0:" in key


def test_normalize_optional_int_variants():
    assert storage_mod._normalize_optional_int("42") == 42
    assert storage_mod._normalize_optional_int("  7 ") == 7
    assert storage_mod._normalize_optional_int("") is None
    assert storage_mod._normalize_optional_int(None) is None
    assert storage_mod._normalize_optional_int("-1") is None
    assert storage_mod._normalize_optional_int("abc") is None


def test_normalize_total_count_variants():
    assert storage_mod._normalize_total_count(5) == 5
    assert storage_mod._normalize_total_count(-3) == 0
    assert storage_mod._normalize_total_count("9") == 9
    assert storage_mod._normalize_total_count(True) is None
    assert storage_mod._normalize_total_count("x") is None


def test_extract_non_negative_int():
    assert storage_mod._extract_non_negative_int("10") == 10
    assert storage_mod._extract_non_negative_int(-2) is None
    assert storage_mod._extract_non_negative_int("nope") is None


def test_build_preview_proxy_etag_is_weak_and_stable():
    etag1 = storage_mod._build_preview_proxy_etag("https://x/y", 4)
    etag2 = storage_mod._build_preview_proxy_etag("https://x/y", 4)
    assert etag1 == etag2
    assert etag1.startswith('W/"storage-preview-4-')
    # negative revision normalizes to 0
    assert storage_mod._build_preview_proxy_etag("https://x/y", -1).startswith('W/"storage-preview-0-')


def test_normalize_and_looks_like_etag_validator():
    assert storage_mod._normalize_etag_token('W/"abc"') == '"abc"'
    assert storage_mod._normalize_etag_token('  "abc"  ') == '"abc"'
    assert storage_mod._looks_like_etag_validator('"abc"') is True
    assert storage_mod._looks_like_etag_validator('W/"abc"') is True
    assert storage_mod._looks_like_etag_validator("plain") is False


def test_build_preview_proxy_url_quotes_url():
    out = storage_mod._build_preview_proxy_url("https://h/a b?x=1")
    assert out.startswith("/api/storage/preview?url=")
    assert "%20" in out  # space is percent-encoded


def test_extract_hostname_from_value():
    assert storage_mod._extract_hostname_from_value("https://Example.com/x") == "example.com"
    assert storage_mod._extract_hostname_from_value("cdn.example.com") == "cdn.example.com"
    assert storage_mod._extract_hostname_from_value("") is None


def test_apply_private_auth_vary_dedupes():
    headers = {"Vary": "Authorization"}
    storage_mod._apply_private_auth_vary(headers)
    tokens = [t.strip() for t in headers["Vary"].split(",")]
    assert "Authorization" in tokens
    assert "Cookie" in tokens
    assert tokens.count("Authorization") == 1


def test_request_matches_etag_star_and_list():
    def make_request(if_none_match):
        req = MagicMock()
        req.headers = {"if-none-match": if_none_match}
        return req

    etag = 'W/"storage-preview-1-abc"'
    assert storage_mod._request_matches_etag(make_request("*"), etag) is True
    assert storage_mod._request_matches_etag(make_request(etag), etag) is True
    assert storage_mod._request_matches_etag(make_request('"other", ' + etag), etag) is True
    assert storage_mod._request_matches_etag(make_request(""), etag) is False
    assert storage_mod._request_matches_etag(make_request('"nope"'), etag) is False


def test_build_upstream_range_request_headers():
    def make_request(headers):
        req = MagicMock()
        req.headers = headers
        return req

    # no range -> empty
    assert storage_mod._build_upstream_range_request_headers(make_request({})) == {}
    # range only
    out = storage_mod._build_upstream_range_request_headers(make_request({"range": "bytes=0-99"}))
    assert out == {"Range": "bytes=0-99"}
    # if-range etag matches current -> keep range
    etag = 'W/"e"'
    out = storage_mod._build_upstream_range_request_headers(
        make_request({"range": "bytes=0-99", "if-range": etag}), current_etag=etag
    )
    assert out == {"Range": "bytes=0-99"}
    # if-range etag mismatch -> drop range entirely
    out = storage_mod._build_upstream_range_request_headers(
        make_request({"range": "bytes=0-99", "if-range": '"x"'}), current_etag=etag
    )
    assert out == {}
    # if-range as date passthrough
    out = storage_mod._build_upstream_range_request_headers(
        make_request({"range": "bytes=0-99", "if-range": "Wed, 21 Oct 2015 07:28:00 GMT"})
    )
    assert out["If-Range"] == "Wed, 21 Oct 2015 07:28:00 GMT"


def test_copy_upstream_proxy_headers_206_implies_accept_ranges():
    upstream = MagicMock()
    upstream.headers = {"content-length": "123", "content-range": "bytes 0-9/123"}
    upstream.status_code = 206
    headers = {}
    storage_mod._copy_upstream_proxy_headers(headers, upstream)
    assert headers["Content-Length"] == "123"
    assert headers["Accept-Ranges"] == "bytes"
    assert headers["Content-Range"] == "bytes 0-9/123"


def test_copy_upstream_proxy_headers_includes_etag_when_requested():
    upstream = MagicMock()
    upstream.headers = {"etag": '"u"', "last-modified": "now", "accept-ranges": "bytes"}
    upstream.status_code = 200
    headers = {}
    storage_mod._copy_upstream_proxy_headers(headers, upstream, include_upstream_etag=True)
    assert headers["ETag"] == '"u"'
    assert headers["Last-Modified"] == "now"
    assert headers["Accept-Ranges"] == "bytes"


def test_sanitize_download_name_strips_invalid_chars():
    assert storage_mod._sanitize_download_name('a/b:c*?.png', "fb") == "a_b_c_.png"
    assert storage_mod._sanitize_download_name("   ", "fallback") == "fallback"
    assert storage_mod._sanitize_download_name("...", "fb") == "fb"


def test_normalize_and_parent_storage_item_path():
    assert storage_mod._normalize_storage_item_path("\\a\\b\\") == "a/b"
    assert storage_mod._storage_item_parent_path("a/b/c.png") == "a/b"
    assert storage_mod._storage_item_parent_path("root.png") == ""
    assert storage_mod._storage_item_parent_path("") == ""


def test_sanitize_archive_path_drops_traversal_segments():
    assert storage_mod._sanitize_archive_path("../../etc/passwd") == "etc/passwd"
    assert storage_mod._sanitize_archive_path("a/./b") == "a/b"
    assert storage_mod._sanitize_archive_path("") == "item"


def test_ensure_unique_archive_path_appends_suffix():
    used = set()
    p1 = storage_mod._ensure_unique_archive_path("dir/file.png", used)
    p2 = storage_mod._ensure_unique_archive_path("dir/file.png", used)
    assert p1 == "dir/file.png"
    assert p2 == "dir/file-2.png"
    assert p1 in used and p2 in used


def test_storage_download_limit_messages():
    assert "MiB" in storage_mod._describe_storage_download_byte_limit(2 * 1024 * 1024)
    assert "限制" in storage_mod._storage_download_size_limit_message("单文件下载", 1024 * 1024)
    assert "文件限制" in storage_mod._storage_download_file_limit_message(500)


def test_normalize_storage_metadata_payload_round_trips_fields():
    data = {
        "url": "  https://x/y  ",
        "finalUrl": "https://x/z",
        "contentType": "image/png",
        "contentLength": 10,
        "error": None,
    }
    out = storage_mod._normalize_storage_metadata_payload(data, source="cache")
    assert out["url"] == "https://x/y"
    assert out["source"] == "cache"
    assert out["contentType"] == "image/png"


def test_build_unavailable_metadata():
    out = storage_mod._build_unavailable_metadata("https://x", "boom")
    assert out["source"] == "unavailable"
    assert out["error"] == "boom"
    assert out["contentType"] is None


def test_is_restricted_network_error():
    assert storage_mod._is_restricted_network_error(UnsafeURLError("URL 指向受限地址")) is True
    assert storage_mod._is_restricted_network_error(UnsafeURLError("URL 指向受限网络地址")) is True
    assert storage_mod._is_restricted_network_error(UnsafeURLError("something else")) is False


# ===========================================================================
# _resolve_safe_preview_fetch_url (fail-closed allowlist core)
# ===========================================================================
def test_resolve_safe_preview_fetch_url_empty_rejected():
    with pytest.raises(HTTPException) as exc:
        storage_mod._resolve_safe_preview_fetch_url("", set())
    assert exc.value.status_code == 400


def test_resolve_safe_preview_fetch_url_passes_through_safe_url(monkeypatch):
    monkeypatch.setattr(storage_mod, "validate_outbound_http_url", lambda u: u)
    assert storage_mod._resolve_safe_preview_fetch_url("https://ok/x", set()) == "https://ok/x"


def test_resolve_safe_preview_fetch_url_allowlists_restricted_host(monkeypatch):
    def fake_validate(url):
        raise UnsafeURLError("URL 指向受限网络地址")

    monkeypatch.setattr(storage_mod, "validate_outbound_http_url", fake_validate)
    # CANON-007: the bypass now requires the host to be approved by the OPERATOR
    # (deploy-time env), not merely present in the user-derived storage allowlist.
    monkeypatch.setattr(
        storage_mod, "_operator_allowed_private_hosts", lambda: {"internal.example.com"}
    )
    url = "https://internal.example.com/file.png"
    # operator-approved AND user-configured host -> allowed despite restricted error
    assert storage_mod._resolve_safe_preview_fetch_url(url, {"internal.example.com"}) == url


def test_resolve_safe_preview_fetch_url_blocks_restricted_host_not_in_allowlist(monkeypatch):
    def fake_validate(url):
        raise UnsafeURLError("URL 指向受限网络地址")

    monkeypatch.setattr(storage_mod, "validate_outbound_http_url", fake_validate)
    with pytest.raises(HTTPException) as exc:
        storage_mod._resolve_safe_preview_fetch_url("https://internal/x", set())
    assert exc.value.status_code == 400


def test_resolve_safe_preview_fetch_url_non_restricted_error_always_rejected(monkeypatch):
    def fake_validate(url):
        raise UnsafeURLError("URL scheme 非法")

    monkeypatch.setattr(storage_mod, "validate_outbound_http_url", fake_validate)
    # even if host appears in allowlist, a non-restricted error fails closed
    with pytest.raises(HTTPException) as exc:
        storage_mod._resolve_safe_preview_fetch_url("https://h/x", {"h"})
    assert exc.value.status_code == 400


# ===========================================================================
# _collect_storage_preview_host_allowlist (decrypt fail-closed degrade path)
# ===========================================================================
def _make_storage_config(provider, config):
    cfg = MagicMock()
    cfg.id = "cfg-1"
    cfg.provider = provider
    cfg.config = config
    cfg.enabled = True
    return cfg


def test_collect_allowlist_uses_decrypted_domain(monkeypatch):
    cfg = _make_storage_config("lsky", {"domain": "https://img.example.com"})
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [cfg]
    monkeypatch.setattr(storage_mod, "decrypt_config", lambda c: c)

    allowlist = storage_mod._collect_storage_preview_host_allowlist(db, TEST_USER)
    assert "img.example.com" in allowlist


def test_collect_allowlist_aliyun_and_tencent_synthesized_hosts(monkeypatch):
    aliyun = _make_storage_config(
        "aliyun-oss", {"bucket": "mybucket", "endpoint": "oss-cn.aliyuncs.com"}
    )
    tencent = _make_storage_config(
        "tencent-cos", {"bucket": "cosbucket", "region": "ap-shanghai"}
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [aliyun, tencent]
    monkeypatch.setattr(storage_mod, "decrypt_config", lambda c: c)

    allowlist = storage_mod._collect_storage_preview_host_allowlist(db, TEST_USER)
    assert "mybucket.oss-cn.aliyuncs.com" in allowlist
    assert "cosbucket.cos.ap-shanghai.myqcloud.com" in allowlist


def test_collect_allowlist_falls_back_to_public_fields_on_decrypt_error(monkeypatch):
    # raw config still has a public domain even though decryption fails closed
    cfg = _make_storage_config("lsky", {"domain": "https://public.example.com"})
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [cfg]

    def boom(_c):
        raise ConfigDecryptionError("token")

    monkeypatch.setattr(storage_mod, "decrypt_config", boom)
    allowlist = storage_mod._collect_storage_preview_host_allowlist(db, TEST_USER)
    # degrade path: uses raw_config public fields
    assert "public.example.com" in allowlist


def test_collect_allowlist_skips_non_dict_decrypted(monkeypatch):
    cfg = _make_storage_config("lsky", {"domain": "https://x.example.com"})
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [cfg]
    monkeypatch.setattr(storage_mod, "decrypt_config", lambda c: "not-a-dict")
    allowlist = storage_mod._collect_storage_preview_host_allowlist(db, TEST_USER)
    assert allowlist == set()


# ===========================================================================
# _resolve_enabled_storage_config
# ===========================================================================
def test_resolve_enabled_storage_config_active_missing(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # no ActiveStorage
    with pytest.raises(HTTPException) as exc:
        storage_mod._resolve_enabled_storage_config(db, TEST_USER, storage_id=None)
    assert exc.value.status_code == 400
    assert "未设置存储配置" in str(exc.value.detail)


def test_resolve_enabled_storage_config_not_found(monkeypatch):
    db = MagicMock()

    class _FakeUserQuery:
        def __init__(self, *a, **k):
            pass

        def get(self, _model, _id):
            return None

    monkeypatch.setattr(storage_mod, "UserScopedQuery", _FakeUserQuery)
    with pytest.raises(HTTPException) as exc:
        storage_mod._resolve_enabled_storage_config(db, TEST_USER, storage_id="sid")
    assert exc.value.status_code == 404


def test_resolve_enabled_storage_config_disabled(monkeypatch):
    db = MagicMock()
    cfg = MagicMock()
    cfg.enabled = False

    class _FakeUserQuery:
        def __init__(self, *a, **k):
            pass

        def get(self, _model, _id):
            return cfg

    monkeypatch.setattr(storage_mod, "UserScopedQuery", _FakeUserQuery)
    with pytest.raises(HTTPException) as exc:
        storage_mod._resolve_enabled_storage_config(db, TEST_USER, storage_id="sid")
    assert exc.value.status_code == 400
    assert "已禁用" in str(exc.value.detail)


def test_resolve_enabled_storage_config_ok(monkeypatch):
    db = MagicMock()
    cfg = MagicMock()
    cfg.enabled = True

    class _FakeUserQuery:
        def __init__(self, *a, **k):
            pass

        def get(self, _model, _id):
            return cfg

    monkeypatch.setattr(storage_mod, "UserScopedQuery", _FakeUserQuery)
    resolved_id, resolved_cfg = storage_mod._resolve_enabled_storage_config(
        db, TEST_USER, storage_id="sid"
    )
    assert resolved_id == "sid"
    assert resolved_cfg is cfg


# ===========================================================================
# Config CRUD endpoints (TestClient + mocked StorageManager)
# ===========================================================================
def _patch_manager(monkeypatch, manager):
    monkeypatch.setattr(storage_mod, "StorageManager", lambda *a, **k: manager)


def _patch_bump(monkeypatch, value=7):
    async def fake_bump(_user_id):
        return value

    monkeypatch.setattr(storage_mod, "_bump_storage_revision", fake_bump)


def _patch_get_revision(monkeypatch, value=3):
    async def fake_get(_user_id):
        return value

    monkeypatch.setattr(storage_mod, "_get_storage_revision", fake_get)


def test_get_storage_configs(client, monkeypatch):
    manager = MagicMock()
    manager.get_all_configs.return_value = [{"id": "a"}, {"id": "b"}]
    _patch_manager(monkeypatch, manager)

    resp = client.get("/api/storage/configs")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "a"}, {"id": "b"}]


def test_create_storage_config_dict_result(client, monkeypatch):
    manager = MagicMock()
    manager.create_config.return_value = {"id": "new"}
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=11)

    resp = client.post("/api/storage/configs", json={"provider": "lsky"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "new"
    assert body["storage_revision"] == 11


def test_create_storage_config_non_dict_result_wrapped(client, monkeypatch):
    manager = MagicMock()
    manager.create_config.return_value = "string-id"
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=2)

    resp = client.post("/api/storage/configs", json={"provider": "lsky"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == "string-id"
    assert body["storage_revision"] == 2


def test_update_storage_config(client, monkeypatch):
    manager = MagicMock()
    manager.update_config.return_value = {"id": "cfg-1", "updated": True}
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=5)

    resp = client.put("/api/storage/configs/cfg-1", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["storage_revision"] == 5
    manager.update_config.assert_called_once()


def test_delete_storage_config(client, monkeypatch):
    manager = MagicMock()
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=9)

    resp = client.delete("/api/storage/configs/cfg-1")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "storage_revision": 9}
    manager.delete_config.assert_called_once_with("cfg-1")


def test_get_active_storage(client, monkeypatch):
    manager = MagicMock()
    manager.get_active_storage_id.return_value = "active-sid"
    _patch_manager(monkeypatch, manager)

    resp = client.get("/api/storage/active")
    assert resp.status_code == 200
    assert resp.json() == {"storage_id": "active-sid"}


def test_set_active_storage(client, monkeypatch):
    manager = MagicMock()
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=4)

    resp = client.post("/api/storage/active/sid-123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["storage_id"] == "sid-123"
    assert body["storage_revision"] == 4
    manager.set_active_storage.assert_called_once_with("sid-123")


# ===========================================================================
# /test endpoint
# ===========================================================================
def test_test_storage_config_success(client, monkeypatch):
    manager = MagicMock()
    manager.test_config = AsyncMock(return_value={"success": True, "test_url": "https://x"})
    _patch_manager(monkeypatch, manager)

    resp = client.post("/api/storage/test", json={"provider": "lsky", "config": {}})
    assert resp.status_code == 200
    assert resp.json()["test_url"] == "https://x"


def test_test_storage_config_failure_maps_to_400(client, monkeypatch):
    manager = MagicMock()
    manager.test_config = AsyncMock(return_value={"success": False, "message": "bad creds"})
    _patch_manager(monkeypatch, manager)

    resp = client.post("/api/storage/test", json={"provider": "lsky", "config": {}})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad creds"


# ===========================================================================
# /upload endpoint
# ===========================================================================
def test_upload_file_success(client, monkeypatch):
    manager = MagicMock()
    manager.upload_file = AsyncMock(return_value={"success": True, "url": "https://cdn/x.png"})
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=8)

    resp = client.post(
        "/api/storage/upload",
        files={"file": ("a.png", b"img-bytes", "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://cdn/x.png"
    assert body["storage_revision"] == 8


def test_upload_file_failure_maps_to_400(client, monkeypatch):
    manager = MagicMock()
    manager.upload_file = AsyncMock(return_value={"success": False, "error": "no config"})
    _patch_manager(monkeypatch, manager)

    resp = client.post(
        "/api/storage/upload",
        files={"file": ("a.png", b"img", "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "no config"


# ===========================================================================
# item delete / batch-delete / rename
# ===========================================================================
def test_delete_storage_item_requires_path(client, monkeypatch):
    _patch_manager(monkeypatch, MagicMock())
    resp = client.post("/api/storage/items/delete", json={"storage_id": "s"})
    assert resp.status_code == 400
    assert "path is required" in resp.json()["detail"]


def test_delete_storage_item_success(client, monkeypatch):
    manager = MagicMock()
    manager.delete_storage_item = AsyncMock(return_value={"success": True})
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=6)

    resp = client.post("/api/storage/items/delete", json={"storage_id": "s", "path": "a/b.png"})
    assert resp.status_code == 200
    assert resp.json()["storage_revision"] == 6


def test_delete_storage_item_failure_raises_400_with_revision(client, monkeypatch):
    manager = MagicMock()
    manager.delete_storage_item = AsyncMock(return_value={"success": False, "message": "denied"})
    _patch_manager(monkeypatch, manager)
    _patch_get_revision(monkeypatch, value=3)

    resp = client.post("/api/storage/items/delete", json={"storage_id": "s", "path": "a/b.png"})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["message"] == "denied"
    assert detail["storage_revision"] == 3


def test_batch_delete_requires_items(client, monkeypatch):
    _patch_manager(monkeypatch, MagicMock())
    resp = client.post("/api/storage/items/batch-delete", json={"items": []})
    assert resp.status_code == 400
    assert "items is required" in resp.json()["detail"]


def test_batch_delete_all_success(client, monkeypatch):
    manager = MagicMock()
    manager.delete_storage_item = AsyncMock(return_value={"success": True, "path": "x"})
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=12)

    resp = client.post(
        "/api/storage/items/batch-delete",
        json={"storage_id": "s", "items": [{"path": "a.png"}, {"path": "b.png"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["success_count"] == 2
    assert body["failure_count"] == 0
    assert body["storage_revision"] == 12


def test_batch_delete_partial_failure_raises_400(client, monkeypatch):
    async def delete_side_effect(**kwargs):
        if kwargs["path"] == "good.png":
            return {"success": True, "path": "good.png"}
        raise RuntimeError("boom")

    manager = MagicMock()
    manager.delete_storage_item = AsyncMock(side_effect=delete_side_effect)
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=15)

    resp = client.post(
        "/api/storage/items/batch-delete",
        json={"storage_id": "s", "items": [{"path": "good.png"}, {"path": "bad.png"}]},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["success_count"] == 1
    assert detail["failure_count"] == 1
    assert len(detail["failures"]) == 1
    assert detail["storage_revision"] == 15


def test_batch_delete_missing_path_item_counts_as_failure(client, monkeypatch):
    manager = MagicMock()
    manager.delete_storage_item = AsyncMock(return_value={"success": True})
    _patch_manager(monkeypatch, manager)
    _patch_get_revision(monkeypatch, value=1)

    resp = client.post(
        "/api/storage/items/batch-delete",
        json={"storage_id": "s", "items": [{"path": ""}]},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["failure_count"] == 1
    # no success -> uses _get_storage_revision
    assert detail["storage_revision"] == 1


def test_rename_storage_item_requires_path_and_name(client, monkeypatch):
    _patch_manager(monkeypatch, MagicMock())
    resp = client.post("/api/storage/items/rename", json={"new_name": "x"})
    assert resp.status_code == 400
    assert "path is required" in resp.json()["detail"]

    resp = client.post("/api/storage/items/rename", json={"path": "a/b"})
    assert resp.status_code == 400
    assert "new_name is required" in resp.json()["detail"]


def test_rename_storage_item_success(client, monkeypatch):
    manager = MagicMock()
    manager.rename_storage_item = AsyncMock(return_value={"success": True})
    _patch_manager(monkeypatch, manager)
    _patch_bump(monkeypatch, value=22)

    resp = client.post(
        "/api/storage/items/rename",
        json={"storage_id": "s", "path": "a/b.png", "new_name": "c.png"},
    )
    assert resp.status_code == 200
    assert resp.json()["storage_revision"] == 22


def test_rename_storage_item_failure_raises_400(client, monkeypatch):
    manager = MagicMock()
    manager.rename_storage_item = AsyncMock(return_value={"success": False, "message": "exists"})
    _patch_manager(monkeypatch, manager)
    _patch_get_revision(monkeypatch, value=4)

    resp = client.post(
        "/api/storage/items/rename",
        json={"storage_id": "s", "path": "a/b.png", "new_name": "c.png"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message"] == "exists"


# ===========================================================================
# /metadata/batch
# ===========================================================================
def test_metadata_batch_requires_list(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    _patch_get_revision(monkeypatch, value=0)
    resp = client.post("/api/storage/metadata/batch", json={"urls": "not-a-list"})
    assert resp.status_code == 400
    assert "urls 必须是数组" in resp.json()["detail"]


def test_metadata_batch_dedupes_and_returns_items(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    _patch_get_revision(monkeypatch, value=2)

    captured = {}

    async def fake_resolve(urls, **kwargs):
        captured["urls"] = urls
        return [{"url": u, "source": "cache"} for u in urls]

    monkeypatch.setattr(storage_mod, "_resolve_storage_metadata_list", fake_resolve)

    resp = client.post(
        "/api/storage/metadata/batch",
        json={"urls": ["https://a", "https://a", "", "https://b"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    # dedupe + drop empty
    assert captured["urls"] == ["https://a", "https://b"]
    assert body["total"] == 2
    assert body["storage_revision"] == 2


# ===========================================================================
# browse endpoints
# ===========================================================================
def test_browse_storage_attaches_preview_urls_and_revision(client, monkeypatch):
    manager = MagicMock()
    manager.browse_storage = AsyncMock(
        return_value={
            "supported": True,
            "storage_id": "sid",
            "path": "",
            "items": [
                {"entry_type": "file", "name": "x.png", "url": "https://cdn/x.png"},
                {"entry_type": "directory", "name": "d"},
            ],
        }
    )
    manager.count_storage_items = AsyncMock(return_value={"total_count": 5})
    _patch_manager(monkeypatch, manager)
    monkeypatch.setattr(
        storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: {"cdn"}
    )
    _patch_get_revision(monkeypatch, value=9)
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)

    resp = client.get("/api/storage/browse/sid")
    assert resp.status_code == 200
    body = resp.json()
    assert body["storage_revision"] == 9
    assert body["total_count"] == 5
    file_item = next(i for i in body["items"] if i["entry_type"] == "file")
    assert file_item["preview_url"].startswith("/api/storage/preview?url=")


def test_browse_active_storage_unsupported_total_count_none(client, monkeypatch):
    manager = MagicMock()
    manager.browse_active_storage = AsyncMock(
        return_value={"supported": False, "storage_id": "sid", "items": []}
    )
    _patch_manager(monkeypatch, manager)
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    _patch_get_revision(monkeypatch, value=1)

    resp = client.get("/api/storage/active/browse")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] is None
    assert body["storage_revision"] == 1


# ===========================================================================
# upload-status / upload-task ownership (permission branches)
# ===========================================================================
def test_upload_status_owned_task(client, monkeypatch):
    task = MagicMock()
    task.to_dict.return_value = {"id": "t1", "status": "completed"}
    monkeypatch.setattr(storage_mod, "_require_owned_upload_task", lambda db, tid, uid: task)

    resp = client.get("/api/storage/upload-status/t1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_upload_status_not_owned_returns_404(client, monkeypatch):
    def deny(db, tid, uid):
        raise HTTPException(status_code=404, detail="上传任务不存在")

    monkeypatch.setattr(storage_mod, "_require_owned_upload_task", deny)
    resp = client.get("/api/storage/upload-status/t1")
    assert resp.status_code == 404


def test_require_owned_upload_task_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        storage_mod._require_owned_upload_task(db, "tid", "uid")
    assert exc.value.status_code == 404


def test_require_owned_upload_task_not_owned(monkeypatch):
    db = MagicMock()
    task = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = task
    monkeypatch.setattr(storage_mod, "is_upload_task_owned_by_user", lambda db, t, u: False)
    with pytest.raises(HTTPException) as exc:
        storage_mod._require_owned_upload_task(db, "tid", "uid")
    assert exc.value.status_code == 404


def test_require_owned_upload_task_owned(monkeypatch):
    db = MagicMock()
    task = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = task
    monkeypatch.setattr(storage_mod, "is_upload_task_owned_by_user", lambda db, t, u: True)
    assert storage_mod._require_owned_upload_task(db, "tid", "uid") is task


def test_retry_upload_only_failed_or_completed(client, monkeypatch):
    task = MagicMock()
    task.status = "uploading"
    monkeypatch.setattr(storage_mod, "_require_owned_upload_task", lambda db, tid, uid: task)

    resp = client.post("/api/storage/retry-upload/t1")
    assert resp.status_code == 400
    assert "只能重试失败的任务" in resp.json()["detail"]


def test_retry_upload_success(client, monkeypatch, fake_db):
    task = MagicMock()
    task.status = "failed"
    monkeypatch.setattr(storage_mod, "_require_owned_upload_task", lambda db, tid, uid: task)
    monkeypatch.setattr(storage_mod.redis_queue, "enqueue", AsyncMock(return_value=4))

    resp = client.post("/api/storage/retry-upload/t1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["queue_position"] == 4
    # task was reset
    assert task.status == "pending"


# ===========================================================================
# upload-logs
# ===========================================================================
def test_upload_logs_returns_logs(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_require_owned_upload_task", lambda db, tid, uid: MagicMock())
    monkeypatch.setattr(storage_mod.redis_queue, "_redis", object(), raising=False)
    monkeypatch.setattr(
        storage_mod.redis_queue, "get_task_logs", AsyncMock(return_value=["line1", "line2"])
    )

    resp = client.get("/api/storage/upload-logs/t1?tail=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == "t1"
    assert body["logs"] == ["line1", "line2"]


def test_upload_logs_redis_error_returns_503(client, monkeypatch, caplog):
    secret = "upload-logs-secret"
    monkeypatch.setattr(storage_mod, "_require_owned_upload_task", lambda db, tid, uid: MagicMock())
    monkeypatch.setattr(storage_mod.redis_queue, "_redis", object(), raising=False)
    monkeypatch.setattr(
        storage_mod.redis_queue,
        "get_task_logs",
        AsyncMock(side_effect=RuntimeError(f"redis down {secret}")),
    )

    with caplog.at_level(logging.ERROR, logger=storage_mod.logger.name):
        resp = client.get("/api/storage/upload-logs/t1")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "获取任务日志失败"
    assert secret not in resp.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


# ===========================================================================
# worker-pool/health
# ===========================================================================
def test_worker_pool_health_unavailable_import_error(client, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if "upload_worker_pool" in name:
            raise ImportError("no worker pool")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    resp = client.get("/api/storage/worker-pool/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["error"] == "Worker pool module not available"


def test_storage_diagnostics_require_admin_user(fake_db):
    app = FastAPI()
    app.include_router(storage_mod.router)

    fake_user = types.SimpleNamespace(id=TEST_USER, is_admin=False)
    fake_db.query.return_value.filter.return_value.first.return_value = fake_user
    app.dependency_overrides[require_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: fake_db

    with TestClient(app) as test_client:
        debug_resp = test_client.get("/api/storage/debug")
        worker_health_resp = test_client.get("/api/storage/worker-pool/health")

    app.dependency_overrides.clear()

    assert debug_resp.status_code == 403
    assert worker_health_resp.status_code == 403


# ===========================================================================
# debug endpoint
# ===========================================================================
def test_storage_debug_returns_runtime_info(client):
    resp = client.get("/api/storage/debug")
    assert resp.status_code == 200
    body = resp.json()
    assert "module_file" in body
    assert body["features"]["upload_async"] is True
    # database url should be masked (no raw password)
    assert isinstance(body["database_url"], str)


def test_worker_status_handles_single_worker_pool(client, monkeypatch):
    from app.services.common import upload_worker_pool as pool_mod

    class FakeTask:
        def done(self):
            return False

    fake_pool = types.SimpleNamespace(
        _running=True,
        _worker_task=FakeTask(),
        _reconcile_interval_s=15.0,
        _reconcile_limit=500,
    )
    fake_redis = types.SimpleNamespace(
        _redis=object(),
        connect=AsyncMock(),
        get_stats=AsyncMock(return_value={"queue_length": 0}),
    )
    monkeypatch.setattr(pool_mod, "worker_pool", fake_pool)
    monkeypatch.setattr(storage_mod, "redis_queue", fake_redis)

    resp = client.get("/api/storage/worker-status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["worker_pool"]["workers_total"] == 1
    assert body["worker_pool"]["workers_alive"] == 1
    assert body["redis"]["stats"] == {"queue_length": 0}


def test_worker_status_import_error_is_generic(client, monkeypatch, caplog):
    import builtins

    secret = "worker-status-secret"
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if "upload_worker_pool" in name:
            raise ImportError(f"no worker pool {secret}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with caplog.at_level(logging.ERROR, logger=storage_mod.logger.name):
        resp = client.get("/api/storage/worker-status")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "WorkerPool 不可用"
    assert secret not in resp.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


# ===========================================================================
# upload-from-url
# ===========================================================================
async def test_upload_from_url_requires_json_object_direct():
    # FastAPI coerces the body to dict, so the isinstance guard is exercised by
    # calling the handler directly with a non-dict payload.
    with pytest.raises(HTTPException) as exc:
        await storage_mod.upload_from_url(
            data="not-an-object", user_id=TEST_USER, db=MagicMock()
        )
    assert exc.value.status_code == 400
    assert "请求体必须为 JSON 对象" in str(exc.value.detail)


def test_upload_from_url_rejects_unsafe_url(client, monkeypatch):
    def reject(url):
        raise HTTPException(status_code=400, detail="URL 指向受限网络地址")

    monkeypatch.setattr(storage_mod, "_validate_outbound_http_url", reject)
    resp = client.post(
        "/api/storage/upload-from-url",
        json={"url": "https://internal/secret.png", "filename": "a.png"},
    )
    assert resp.status_code == 400
    assert "受限" in resp.json()["detail"]


def test_upload_from_url_requires_filename(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_validate_outbound_http_url", lambda u: u)
    resp = client.post(
        "/api/storage/upload-from-url",
        json={"url": "https://src/a.png", "filename": ""},
    )
    assert resp.status_code == 400
    assert "filename 不能为空" in resp.json()["detail"]


def test_upload_from_url_success_enqueues(client, monkeypatch, fake_db):
    monkeypatch.setattr(storage_mod, "_validate_outbound_http_url", lambda u: u)
    monkeypatch.setattr(
        storage_mod,
        "_resolve_enabled_storage_config",
        lambda db, user_id, storage_id: ("resolved-sid", MagicMock()),
    )
    # no session ownership conflict
    fake_db.query.return_value.filter.return_value.first.return_value = None
    monkeypatch.setattr(storage_mod.redis_queue, "_redis", object(), raising=False)
    monkeypatch.setattr(storage_mod.redis_queue, "enqueue", AsyncMock(return_value=3))
    monkeypatch.setattr(storage_mod.redis_queue, "append_task_log", AsyncMock(return_value=None))

    resp = client.post(
        "/api/storage/upload-from-url",
        json={"url": "https://src/a.png", "filename": "a.png"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["queue_position"] == 3
    assert body["enqueued"] is True
    fake_db.add.assert_called_once()


def test_upload_from_url_session_owner_mismatch_404(client, monkeypatch, fake_db):
    monkeypatch.setattr(storage_mod, "_validate_outbound_http_url", lambda u: u)
    owner = MagicMock()
    owner.user_id = "someone-else"
    fake_db.query.return_value.filter.return_value.first.return_value = owner

    resp = client.post(
        "/api/storage/upload-from-url",
        json={"url": "https://src/a.png", "filename": "a.png", "session_id": "sess-1"},
    )
    assert resp.status_code == 404
    assert "会话不存在" in resp.json()["detail"]


# ===========================================================================
# downloads (prepared) + local-files
# ===========================================================================
def test_get_prepared_storage_download_missing_404(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)

    def missing(download_id, *, user_id):
        raise HTTPException(status_code=404, detail="下载不存在或已过期")

    monkeypatch.setattr(storage_mod, "_load_storage_download_metadata", missing)
    resp = client.get("/api/storage/downloads/does-not-exist")
    assert resp.status_code == 404


def test_get_prepared_storage_download_serves_file(client, monkeypatch, tmp_path):
    target = tmp_path / "out.bin"
    target.write_bytes(b"download-bytes")
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)
    monkeypatch.setattr(
        storage_mod,
        "_load_storage_download_metadata",
        lambda download_id, *, user_id: {
            "file_path": str(target),
            "media_type": "application/octet-stream",
            "file_name": "out.bin",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    )
    resp = client.get("/api/storage/downloads/dl-1")
    assert resp.status_code == 200
    assert resp.content == b"download-bytes"
    assert resp.headers["X-Storage-Download-Id"] == "dl-1"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_local_files_missing_resolves_404(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "resolve_local_public_file_path", lambda url: None)
    resp = client.get("/api/storage/local-files/a/b.png")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "File not found"


def test_local_files_serves_existing_file(client, monkeypatch, tmp_path):
    f = tmp_path / "pic.png"
    f.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(storage_mod, "resolve_local_public_file_path", lambda url: f)
    resp = client.get("/api/storage/local-files/pic.png")
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG\r\n"
    assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"


# ===========================================================================
# /preview endpoint (proxy + fail-closed + 304 + error mapping)
# ===========================================================================
def test_preview_rejected_url_returns_400(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())

    def reject(url, hosts):
        raise HTTPException(status_code=400, detail="URL 指向受限网络地址")

    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", reject)
    resp = client.get("/api/storage/preview", params={"url": "https://internal/secret"})
    assert resp.status_code == 400


def test_preview_returns_304_on_matching_etag(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=2)
    etag = storage_mod._build_preview_proxy_etag("https://cdn/x.png", 2)

    resp = client.get(
        "/api/storage/preview",
        params={"url": "https://cdn/x.png"},
        headers={"If-None-Match": etag},
    )
    assert resp.status_code == 304
    assert resp.headers["ETag"] == etag


def test_preview_streams_upstream_success(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=2)

    upstream = MagicMock()
    upstream.status_code = 200
    upstream.headers = {"content-type": "image/png", "content-length": "5"}

    async def fake_aiter():
        yield b"hello"

    upstream.aiter_bytes = fake_aiter
    upstream.aclose = AsyncMock()
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()

    async def fake_open(*args, **kwargs):
        return fake_client, upstream, "https://cdn/x.png"

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", fake_open)

    resp = client.get("/api/storage/preview", params={"url": "https://cdn/x.png"})
    assert resp.status_code == 200
    assert resp.content == b"hello"
    assert resp.headers["X-Storage-Revision"] == "2"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_preview_upstream_error_status_propagated(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=0)

    upstream = MagicMock()
    upstream.status_code = 404
    upstream.headers = {}
    upstream.aclose = AsyncMock()
    upstream.aread = AsyncMock(return_value=b"not found")
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()

    async def fake_open(*args, **kwargs):
        return fake_client, upstream, "https://cdn/x.png"

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", fake_open)

    resp = client.get("/api/storage/preview", params={"url": "https://cdn/missing.png"})
    assert resp.status_code == 404
    upstream.aclose.assert_awaited()
    fake_client.aclose.assert_awaited()


def test_preview_unexpected_exception_maps_to_500_without_leak(client, monkeypatch, caplog):
    secret = "preview-secret-token"
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=0)

    async def boom(*args, **kwargs):
        raise RuntimeError(f"network exploded {secret}")

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", boom)

    with caplog.at_level(logging.ERROR, logger=storage_mod.logger.name):
        resp = client.get("/api/storage/preview", params={"url": "https://cdn/x.png"})

    assert resp.status_code == 500
    assert resp.json()["detail"] == "预览失败"
    log_text = _storage_log_text(caplog)
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# /download endpoint
# ===========================================================================
def test_download_streams_with_attachment_disposition(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=5)

    upstream = MagicMock()
    upstream.status_code = 200
    upstream.headers = {"content-type": "image/png", "content-length": "3", "etag": '"u"'}

    async def fake_aiter():
        yield b"abc"

    upstream.aiter_bytes = fake_aiter
    upstream.aclose = AsyncMock()
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()

    async def fake_open(*args, **kwargs):
        return fake_client, upstream, "https://cdn/photo.png?sig=1"

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", fake_open)

    resp = client.get("/api/storage/download", params={"url": "https://cdn/photo.png"})
    assert resp.status_code == 200
    assert resp.content == b"abc"
    assert 'attachment; filename="photo.png"' in resp.headers["Content-Disposition"]
    assert resp.headers["X-Storage-Revision"] == "5"
    assert resp.headers["ETag"] == '"u"'


def test_download_upstream_error_propagated(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=0)

    upstream = MagicMock()
    upstream.status_code = 502
    upstream.headers = {}
    upstream.aclose = AsyncMock()
    upstream.aread = AsyncMock(return_value=b"bad gateway")
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()

    async def fake_open(*args, **kwargs):
        return fake_client, upstream, "https://cdn/x.png"

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", fake_open)
    resp = client.get("/api/storage/download", params={"url": "https://cdn/x.png"})
    assert resp.status_code == 502


def test_download_rejected_url_returns_400(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())

    def reject(url, hosts):
        raise HTTPException(status_code=400, detail="url 不能为空")

    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", reject)
    resp = client.get("/api/storage/download", params={"url": "x"})
    assert resp.status_code == 400


def test_download_unexpected_exception_maps_to_500_without_leak(client, monkeypatch, caplog):
    secret = "download-secret-token"
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    _patch_get_revision(monkeypatch, value=0)

    async def boom(*args, **kwargs):
        raise RuntimeError(f"download exploded {secret}")

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", boom)

    with caplog.at_level(logging.ERROR, logger=storage_mod.logger.name):
        resp = client.get("/api/storage/download", params={"url": "https://cdn/x.png"})

    assert resp.status_code == 500
    assert resp.json()["detail"] == "下载失败"
    log_text = _storage_log_text(caplog)
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# sync upload helpers (upload_to_lsky_sync, upload_to_active_storage)
# ===========================================================================
def test_upload_to_lsky_sync_incomplete_config():
    out = storage_mod.upload_to_lsky_sync("a.png", b"x", "image/png", {})
    assert out["success"] is False
    assert "配置不完整" in out["error"]


def test_upload_to_lsky_sync_success(monkeypatch):
    captured = {}

    class _Resp:
        def json(self):
            return {"status": True, "data": {"links": {"url": "https://img/abc.png"}}}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return _Resp()

    fake_requests = types.SimpleNamespace(post=fake_post)
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    # Public IP literal domain passes the SSRF egress guard without DNS, keeping
    # this test focused on the upload-logic happy path. (SSRF rejection of
    # private/internal domains is covered by test_storage_router_lsky_upload_ssrf.py.)
    out = storage_mod.upload_to_lsky_sync(
        "a.png", b"x", "image/png", {"domain": "https://8.8.8.8/", "token": "tok", "strategyId": 1}
    )
    assert out["success"] is True
    assert out["url"] == "https://img/abc.png"
    assert captured["url"] == "https://8.8.8.8/api/v1/upload"
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_upload_to_lsky_sync_failure_response(monkeypatch):
    class _Resp:
        def json(self):
            return {"status": False, "message": "rejected"}

    fake_requests = types.SimpleNamespace(post=lambda url, **kwargs: _Resp())
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    out = storage_mod.upload_to_lsky_sync(
        "a.png", b"x", "image/png", {"domain": "https://8.8.8.8", "token": "tok"}
    )
    assert out["success"] is False
    assert out["error"] == "rejected"


def test_upload_to_active_storage_no_active_config(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    monkeypatch.setattr(storage_mod, "SessionLocal", lambda: db)

    out = storage_mod.upload_to_active_storage(b"x", "a.png", "image/png", user_id="u")
    assert out["success"] is False
    assert "未设置存储配置" in out["error"]


def test_upload_to_active_storage_unsupported_provider(monkeypatch):
    db = MagicMock()
    active = MagicMock()
    active.storage_id = "sid"
    config = MagicMock()
    config.enabled = True
    config.provider = "weird-provider"

    # first() called twice: ActiveStorage then StorageConfig
    db.query.return_value.filter.return_value.first.side_effect = [active, config]
    monkeypatch.setattr(storage_mod, "SessionLocal", lambda: db)

    out = storage_mod.upload_to_active_storage(b"x", "a.png", "image/png", user_id="u")
    assert out["success"] is False
    assert "不支持的存储类型" in out["error"]


async def test_upload_to_active_storage_async_success(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(storage_mod, "SessionLocal", lambda: db)
    manager = MagicMock()
    manager.upload_file = AsyncMock(return_value={"success": True, "url": "https://cdn/x"})
    monkeypatch.setattr(storage_mod, "StorageManager", lambda *a, **k: manager)

    out = await storage_mod.upload_to_active_storage_async(b"x", "a.png", "image/png", user_id="u")
    assert out["success"] is True
    assert out["url"] == "https://cdn/x"


async def test_upload_to_active_storage_async_http_error(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(storage_mod, "SessionLocal", lambda: db)
    manager = MagicMock()
    manager.upload_file = AsyncMock(side_effect=HTTPException(status_code=400, detail="bad"))
    monkeypatch.setattr(storage_mod, "StorageManager", lambda *a, **k: manager)

    out = await storage_mod.upload_to_active_storage_async(b"x", "a.png", "image/png", user_id="u")
    assert out["success"] is False
    assert out["error"] == "bad"


# ===========================================================================
# async metadata + total-count helpers
# ===========================================================================
async def test_resolve_storage_metadata_cache_only_empty_inputs():
    out = await storage_mod._resolve_storage_metadata_cache_only(
        [], user_id="u", cache=None
    )
    assert out == {}


async def test_resolve_storage_metadata_cache_only_hits():
    cache = MagicMock()
    cache.get = AsyncMock(return_value={"url": "https://a", "source": "x"})
    out = await storage_mod._resolve_storage_metadata_cache_only(
        ["https://a"], user_id="u", cache=cache
    )
    assert "https://a" in out
    assert out["https://a"]["source"] == "cache"


async def test_attach_total_count_uses_cache(monkeypatch):
    cache = MagicMock()
    cache.get = AsyncMock(return_value={"total_count": 42})
    manager = MagicMock()
    result = {"supported": True, "storage_id": "sid", "path": ""}
    out = await storage_mod._attach_total_count_to_browse_payload(
        result, manager=manager, storage_id="sid", user_id="u", cache=cache
    )
    assert out["total_count"] == 42
    # cache hit -> manager.count_storage_items not called
    manager.count_storage_items.assert_not_called()


async def test_attach_total_count_not_supported_returns_none():
    out = await storage_mod._attach_total_count_to_browse_payload(
        {"supported": False}, manager=MagicMock(), storage_id="sid", user_id="u", cache=None
    )
    assert out["total_count"] is None


async def test_attach_total_count_disallow_fresh_count():
    manager = MagicMock()
    manager.count_storage_items = AsyncMock(return_value={"total_count": 99})
    out = await storage_mod._attach_total_count_to_browse_payload(
        {"supported": True, "storage_id": "sid", "path": ""},
        manager=manager,
        storage_id="sid",
        user_id="u",
        cache=None,
        allow_fresh_count=False,
    )
    assert out["total_count"] is None
    manager.count_storage_items.assert_not_called()


async def test_attach_total_count_fresh_count_from_manager():
    manager = MagicMock()
    manager.count_storage_items = AsyncMock(return_value={"total_count": 17})
    out = await storage_mod._attach_total_count_to_browse_payload(
        {"supported": True, "storage_id": "sid", "path": "dir"},
        manager=manager,
        storage_id="sid",
        user_id="u",
        cache=None,
    )
    assert out["total_count"] == 17
    manager.count_storage_items.assert_awaited_once()


async def test_storage_revision_redis_error_log_is_summarized(monkeypatch, caplog):
    secret = "storage-revision-secret"
    monkeypatch.setattr(storage_mod.redis_queue, "_redis", None, raising=False)
    monkeypatch.setattr(
        storage_mod.redis_queue,
        "connect",
        AsyncMock(side_effect=RuntimeError(f"redis failed {secret}")),
    )

    with caplog.at_level(logging.DEBUG, logger=storage_mod.logger.name):
        redis_conn = await storage_mod._get_storage_revision_redis()

    log_text = _storage_log_text(caplog)
    assert redis_conn is None
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert "<redacted error; length=" in log_text
    assert all(record.exc_info is None for record in caplog.records)


async def test_attach_total_count_manager_error_log_is_summarized(caplog):
    secret = "storage-count-secret"
    manager = MagicMock()
    manager.count_storage_items = AsyncMock(
        side_effect=RuntimeError(f"count failed {secret}")
    )

    with caplog.at_level(logging.WARNING, logger=storage_mod.logger.name):
        out = await storage_mod._attach_total_count_to_browse_payload(
            {"supported": True, "storage_id": "sid", "path": f"private/{secret}"},
            manager=manager,
            storage_id="sid",
            user_id="u",
            cache=None,
        )

    log_text = _storage_log_text(caplog)
    assert out["total_count"] is None
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert "<redacted error; length=" in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# preview-url enrichment of browse payload (pure)
# ===========================================================================
def test_attach_preview_urls_skips_directories_and_bad_urls(monkeypatch):
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    payload = {
        "items": [
            {"entry_type": "file", "url": "https://cdn/a.png"},
            {"entry_type": "directory", "name": "d"},
            {"entry_type": "file", "url": ""},
            "not-a-dict",
        ]
    }
    out = storage_mod._attach_preview_urls_to_browse_payload(payload, set())
    items = out["items"]
    assert items[0]["preview_url"].startswith("/api/storage/preview?url=")
    assert items[1]["preview_url"] is None
    assert items[2]["preview_url"] is None
    assert items[3] == "not-a-dict"


def test_attach_preview_urls_unsafe_url_yields_none(monkeypatch):
    def reject(url, hosts):
        raise HTTPException(status_code=400, detail="restricted")

    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", reject)
    payload = {"items": [{"entry_type": "file", "url": "https://internal/x"}]}
    out = storage_mod._attach_preview_urls_to_browse_payload(payload, set())
    assert out["items"][0]["preview_url"] is None


def test_attach_preview_urls_non_list_items_passthrough():
    payload = {"items": "nope"}
    assert storage_mod._attach_preview_urls_to_browse_payload(payload, set()) == payload


# ===========================================================================
# download listing / collection helpers
# ===========================================================================
def _fake_manager_with_browse(pages):
    """pages: list of browse_storage return dicts, consumed in order."""
    manager = MagicMock()
    manager.browse_storage = AsyncMock(side_effect=list(pages))
    return manager


async def test_list_storage_path_entries_unsupported_raises():
    manager = _fake_manager_with_browse([{"supported": False, "message": "not supported"}])
    with pytest.raises(HTTPException) as exc:
        await storage_mod._list_storage_path_entries(manager, storage_id="sid", path="")
    assert exc.value.status_code == 400
    assert "not supported" in str(exc.value.detail)


async def test_list_storage_path_entries_paginates():
    pages = [
        {
            "supported": True,
            "items": [{"entry_type": "file", "path": "a.png", "url": "https://cdn/a.png"}],
            "has_more": True,
            "next_cursor": "c1",
        },
        {
            "supported": True,
            "items": [{"entry_type": "file", "path": "b.png", "url": "https://cdn/b.png"}],
            "has_more": False,
            "next_cursor": None,
        },
    ]
    manager = _fake_manager_with_browse(pages)
    entries = await storage_mod._list_storage_path_entries(manager, storage_id="sid", path="")
    assert [e["path"] for e in entries] == ["a.png", "b.png"]
    assert manager.browse_storage.await_count == 2


async def test_list_storage_path_entries_enforces_max_total_files():
    pages = [
        {
            "supported": True,
            "items": [
                {"entry_type": "file", "path": "a.png", "url": "https://cdn/a.png"},
                {"entry_type": "file", "path": "b.png", "url": "https://cdn/b.png"},
            ],
            "has_more": False,
            "next_cursor": None,
        }
    ]
    manager = _fake_manager_with_browse(pages)
    with pytest.raises(HTTPException) as exc:
        await storage_mod._list_storage_path_entries(
            manager, storage_id="sid", path="", max_total_files=1
        )
    assert exc.value.status_code == 413


async def test_collect_storage_download_entries_single_file(monkeypatch):
    # resolved via parent directory listing
    parent_listing = [
        {"entry_type": "file", "path": "dir/a.png", "url": "https://cdn/a.png", "name": "a.png", "size": 10},
    ]

    async def fake_list(manager, *, storage_id, path, existing_paths=None, max_total_files=None):
        return parent_listing

    monkeypatch.setattr(storage_mod, "_list_storage_path_entries", fake_list)
    manager = MagicMock()
    entries, skipped = await storage_mod._collect_storage_download_entries(
        manager, storage_id="sid", items=[{"path": "dir/a.png", "name": "a.png"}]
    )
    assert len(entries) == 1
    assert entries[0]["file_url"] == "https://cdn/a.png"
    assert skipped == []


async def test_collect_storage_download_entries_file_not_found(monkeypatch):
    async def fake_list(manager, *, storage_id, path, existing_paths=None, max_total_files=None):
        return []  # parent directory empty -> file not resolvable

    monkeypatch.setattr(storage_mod, "_list_storage_path_entries", fake_list)
    manager = MagicMock()
    entries, skipped = await storage_mod._collect_storage_download_entries(
        manager, storage_id="sid", items=[{"path": "dir/missing.png", "name": "missing.png"}]
    )
    assert entries == []
    assert skipped[0]["reason"] == "file not found"


async def test_collect_storage_download_entries_missing_path_skipped():
    manager = MagicMock()
    entries, skipped = await storage_mod._collect_storage_download_entries(
        manager, storage_id="sid", items=[{"name": "x"}, "not-a-dict"]
    )
    assert entries == []
    assert skipped[0]["reason"] == "missing path"


async def test_collect_storage_download_entries_directory(monkeypatch):
    nested = [
        {"entry_type": "file", "path": "folder/x.png", "url": "https://cdn/x.png", "name": "x.png", "size": 5},
    ]

    async def fake_dir_files(manager, *, storage_id, path, existing_paths=None, max_total_files=None):
        return nested

    monkeypatch.setattr(storage_mod, "_list_storage_directory_files", fake_dir_files)
    manager = MagicMock()
    entries, skipped = await storage_mod._collect_storage_download_entries(
        manager,
        storage_id="sid",
        items=[{"path": "folder", "name": "folder", "is_directory": True}],
    )
    assert len(entries) == 1
    assert entries[0]["archive_path"].startswith("folder/")
    assert skipped == []


async def test_collect_storage_download_entries_empty_directory(monkeypatch):
    async def fake_dir_files(manager, *, storage_id, path, existing_paths=None, max_total_files=None):
        return []

    monkeypatch.setattr(storage_mod, "_list_storage_directory_files", fake_dir_files)
    manager = MagicMock()
    entries, skipped = await storage_mod._collect_storage_download_entries(
        manager,
        storage_id="sid",
        items=[{"path": "empty", "name": "empty", "is_directory": True}],
    )
    assert entries == []
    assert skipped[0]["reason"] == "empty directory"


def test_cleanup_expired_storage_downloads_scan_error_log_is_summarized(
    monkeypatch, caplog
):
    secret = "storage-temp-secret"

    class FakeDownloadDir:
        def glob(self, pattern):
            raise RuntimeError(f"scan failed {secret}")

    monkeypatch.setattr(storage_mod, "_STORAGE_DOWNLOAD_DIR", FakeDownloadDir())

    with caplog.at_level(logging.DEBUG, logger=storage_mod.logger.name):
        storage_mod._cleanup_expired_storage_downloads()

    log_text = _storage_log_text(caplog)
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert "<redacted error; length=" in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# prepare_storage_download endpoint (single file happy path + guards)
# ===========================================================================
def test_prepare_download_requires_items(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)
    resp = client.post("/api/storage/items/downloads", json={"items": []})
    assert resp.status_code == 400
    assert "items is required" in resp.json()["detail"]


def test_prepare_download_no_downloadable_files(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)
    monkeypatch.setattr(
        storage_mod,
        "_resolve_enabled_storage_config",
        lambda db, user_id, storage_id: ("sid", MagicMock()),
    )
    _patch_manager(monkeypatch, MagicMock())
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())

    async def fake_collect(manager, *, storage_id, items, max_total_files=None):
        return [], [{"path": "x", "status": "skipped", "reason": "file not found"}]

    monkeypatch.setattr(storage_mod, "_collect_storage_download_entries", fake_collect)

    resp = client.post(
        "/api/storage/items/downloads",
        json={"storage_id": "sid", "items": [{"path": "x.png"}]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message"] == "没有可下载的文件"


def test_prepare_download_single_file_success(client, monkeypatch, tmp_path):
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)
    monkeypatch.setattr(
        storage_mod,
        "_resolve_enabled_storage_config",
        lambda db, user_id, storage_id: ("sid", MagicMock()),
    )
    _patch_manager(monkeypatch, MagicMock())
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)

    async def fake_collect(manager, *, storage_id, items, max_total_files=None):
        return (
            [{"file_url": "https://cdn/a.png", "name": "a.png", "archive_path": "a.png", "size": 10}],
            [],
        )

    monkeypatch.setattr(storage_mod, "_collect_storage_download_entries", fake_collect)

    async def fake_stream(safe_url, *, target_path, allowed_hosts, **kwargs):
        Path(target_path).write_bytes(b"file-bytes")
        return {
            "final_url": "https://cdn/a.png",
            "content_type": "image/png",
            "content_length": 10,
        }

    monkeypatch.setattr(storage_mod, "_stream_safe_url_to_file", fake_stream)

    captured = {}

    def fake_persist(download_id, **kwargs):
        captured.update(kwargs)
        return {"created_at": "2026-01-01T00:00:00Z", "expires_at": "2026-01-01T06:00:00Z"}

    monkeypatch.setattr(storage_mod, "_persist_storage_download_metadata", fake_persist)

    resp = client.post(
        "/api/storage/items/downloads",
        json={"storage_id": "sid", "items": [{"path": "a.png", "name": "a.png"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["archive"] is False
    assert body["total_files"] == 1
    assert body["file_name"] == "a.png"
    assert body["download_url"].startswith("/api/storage/downloads/")


def test_prepare_download_single_file_too_large(client, monkeypatch):
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)
    monkeypatch.setattr(
        storage_mod,
        "_resolve_enabled_storage_config",
        lambda db, user_id, storage_id: ("sid", MagicMock()),
    )
    _patch_manager(monkeypatch, MagicMock())
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())

    too_big = storage_mod._STORAGE_DOWNLOAD_MAX_FILE_BYTES + 1

    async def fake_collect(manager, *, storage_id, items, max_total_files=None):
        return (
            [{"file_url": "https://cdn/a.png", "name": "a.png", "archive_path": "a.png", "size": too_big}],
            [],
        )

    monkeypatch.setattr(storage_mod, "_collect_storage_download_entries", fake_collect)

    resp = client.post(
        "/api/storage/items/downloads",
        json={"storage_id": "sid", "items": [{"path": "a.png", "name": "a.png"}]},
    )
    assert resp.status_code == 413


def test_prepare_download_unexpected_exception_maps_to_500_without_leak(
    client,
    monkeypatch,
    caplog,
):
    secret = "prepare-download-secret-token"
    monkeypatch.setattr(storage_mod, "_cleanup_expired_storage_downloads", lambda: None)
    monkeypatch.setattr(storage_mod, "_cleanup_storage_download_by_id", lambda download_id: None)
    monkeypatch.setattr(
        storage_mod,
        "_resolve_enabled_storage_config",
        lambda db, user_id, storage_id: ("sid", MagicMock()),
    )
    _patch_manager(monkeypatch, MagicMock())
    monkeypatch.setattr(storage_mod, "_collect_storage_preview_host_allowlist", lambda db, u: set())
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)

    async def fake_collect(manager, *, storage_id, items, max_total_files=None):
        return (
            [{"file_url": "https://cdn/a.png", "name": "a.png", "archive_path": "a.png", "size": 10}],
            [],
        )

    async def boom(*args, **kwargs):
        raise RuntimeError(f"stream failed {secret}")

    monkeypatch.setattr(storage_mod, "_collect_storage_download_entries", fake_collect)
    monkeypatch.setattr(storage_mod, "_stream_safe_url_to_file", boom)

    with caplog.at_level(logging.ERROR, logger=storage_mod.logger.name):
        resp = client.post(
            "/api/storage/items/downloads",
            json={"storage_id": "sid", "items": [{"path": "a.png", "name": "a.png"}]},
        )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "准备下载失败"
    log_text = _storage_log_text(caplog)
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


# ===========================================================================
# metadata fetch + list helpers (httpx boundary mocked)
# ===========================================================================
async def test_fetch_url_metadata_success(monkeypatch):
    upstream = MagicMock()
    upstream.status_code = 200
    upstream.headers = {
        "content-type": "image/png",
        "content-length": "100",
        "last-modified": "now",
        "etag": '"e"',
        "cache-control": "max-age=60",
    }
    upstream.aclose = AsyncMock()
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()

    async def fake_open(*args, **kwargs):
        return fake_client, upstream, "https://cdn/final.png"

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", fake_open)
    out = await storage_mod._fetch_url_metadata("https://cdn/x.png", allowed_hosts=set())
    assert out["contentType"] == "image/png"
    assert out["contentLength"] == 100
    assert out["finalUrl"] == "https://cdn/final.png"
    assert out["source"] == "upstream"
    upstream.aclose.assert_awaited()
    fake_client.aclose.assert_awaited()


async def test_fetch_url_metadata_error_status(monkeypatch):
    upstream = MagicMock()
    upstream.status_code = 403
    upstream.headers = {}
    upstream.aclose = AsyncMock()
    upstream.aread = AsyncMock(return_value=b"forbidden")
    fake_client = MagicMock()
    fake_client.aclose = AsyncMock()

    async def fake_open(*args, **kwargs):
        return fake_client, upstream, "https://cdn/x.png"

    monkeypatch.setattr(storage_mod, "_open_safe_stream_with_redirect_guard", fake_open)
    with pytest.raises(HTTPException) as exc:
        await storage_mod._fetch_url_metadata("https://cdn/x.png", allowed_hosts=set())
    assert exc.value.status_code == 403


async def test_resolve_storage_metadata_list_uses_cache(monkeypatch):
    cache = MagicMock()
    cache.get = AsyncMock(return_value={"url": "https://a", "source": "y"})
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)

    out = await storage_mod._resolve_storage_metadata_list(
        ["https://a"], user_id="u", allowed_hosts=set(), cache=cache
    )
    assert len(out) == 1
    assert out[0]["source"] == "cache"


async def test_resolve_storage_metadata_list_unsafe_url(monkeypatch):
    def reject(url, hosts):
        raise HTTPException(status_code=400, detail="restricted")

    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", reject)
    out = await storage_mod._resolve_storage_metadata_list(
        ["https://internal"], user_id="u", allowed_hosts=set(), cache=None
    )
    assert out[0]["source"] == "unavailable"


async def test_resolve_storage_metadata_list_budget_exceeded(monkeypatch):
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    out = await storage_mod._resolve_storage_metadata_list(
        ["https://a"], user_id="u", allowed_hosts=set(), cache=None, max_fetch=0
    )
    assert out[0]["source"] == "unavailable"
    assert "budget" in out[0]["error"]


async def test_resolve_storage_metadata_list_fetches_and_caches(monkeypatch):
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=None)

    async def fake_fetch(safe_url, *, allowed_hosts, timeout):
        return {"url": safe_url, "contentType": "image/png", "source": "upstream"}

    monkeypatch.setattr(storage_mod, "_fetch_url_metadata", fake_fetch)
    out = await storage_mod._resolve_storage_metadata_list(
        ["https://a"], user_id="u", allowed_hosts=set(), cache=cache
    )
    assert out[0]["contentType"] == "image/png"
    cache.set.assert_awaited()


# ===========================================================================
# storage-revision redis helpers
# ===========================================================================
async def test_get_storage_revision_no_redis(monkeypatch):
    async def no_redis():
        return None

    monkeypatch.setattr(storage_mod, "_get_storage_revision_redis", no_redis)
    assert await storage_mod._get_storage_revision("u") == 0


async def test_get_storage_revision_reads_value(monkeypatch):
    redis_conn = MagicMock()
    redis_conn.get = AsyncMock(return_value="7")

    async def get_conn():
        return redis_conn

    monkeypatch.setattr(storage_mod, "_get_storage_revision_redis", get_conn)
    assert await storage_mod._get_storage_revision("u") == 7


async def test_get_storage_revision_handles_bad_value(monkeypatch):
    redis_conn = MagicMock()
    redis_conn.get = AsyncMock(return_value="not-an-int")

    async def get_conn():
        return redis_conn

    monkeypatch.setattr(storage_mod, "_get_storage_revision_redis", get_conn)
    assert await storage_mod._get_storage_revision("u") == 0


async def test_bump_storage_revision_no_redis(monkeypatch):
    async def no_redis():
        return None

    monkeypatch.setattr(storage_mod, "_get_storage_revision_redis", no_redis)
    assert await storage_mod._bump_storage_revision("u") == 0


async def test_bump_storage_revision_increments(monkeypatch):
    redis_conn = MagicMock()
    redis_conn.get = AsyncMock(return_value="0")
    redis_conn.incr = AsyncMock(return_value=1)
    redis_conn.expire = AsyncMock(return_value=None)

    async def get_conn():
        return redis_conn

    monkeypatch.setattr(storage_mod, "_get_storage_revision_redis", get_conn)
    assert await storage_mod._bump_storage_revision("u") == 1
    redis_conn.incr.assert_awaited()
    redis_conn.expire.assert_awaited()


# ===========================================================================
# attach_metadata_to_browse_payload (cache-only enrichment, no network)
# ===========================================================================
async def test_attach_metadata_to_browse_payload_marks_non_media_none(monkeypatch):
    monkeypatch.setattr(storage_mod, "_resolve_safe_preview_fetch_url", lambda url, hosts: url)

    async def empty_cache_only(*args, **kwargs):
        return {}

    async def no_backfill(*args, **kwargs):
        return []

    monkeypatch.setattr(storage_mod, "_resolve_storage_metadata_cache_only", empty_cache_only)
    monkeypatch.setattr(storage_mod, "_resolve_storage_metadata_list", no_backfill)

    payload = {
        "items": [
            {"entry_type": "directory", "name": "d"},
            {"entry_type": "file", "name": "readme.txt", "url": "https://cdn/r.txt"},
            {"entry_type": "file", "name": "pic.png", "url": "https://cdn/pic.png"},
        ]
    }
    out = await storage_mod._attach_metadata_to_browse_payload(
        payload, user_id="u", allowed_hosts=set(), cache=None
    )
    items = out["items"]
    # directory and non-media get metadata=None
    assert items[0]["metadata"] is None
    assert items[1]["metadata"] is None
    # media file had no cache + empty backfill -> metadata None, helper key removed
    assert "__meta_safe_url" not in items[2]


async def test_attach_metadata_to_browse_payload_empty_items_passthrough():
    payload = {"items": []}
    out = await storage_mod._attach_metadata_to_browse_payload(
        payload, user_id="u", allowed_hosts=set(), cache=None
    )
    assert out == payload


# ===========================================================================
# update_session_attachment_url permission branches
# ===========================================================================
async def test_update_session_attachment_url_missing_session(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    # should return quietly (no exception, no commit)
    await storage_mod.update_session_attachment_url(
        db, "sess", "msg", "att", "https://cdn/x", expected_user_id="u"
    )
    db.commit.assert_not_called()


async def test_update_session_attachment_url_user_mismatch(monkeypatch):
    db = MagicMock()
    session = MagicMock()
    session.user_id = "owner-a"
    db.query.return_value.filter.return_value.first.return_value = session
    # expected_user differs from session owner -> skip without commit
    await storage_mod.update_session_attachment_url(
        db, "sess", "msg", "att", "https://cdn/x", expected_user_id="owner-b"
    )
    db.commit.assert_not_called()


# ===========================================================================
# process_upload_task early exit (task missing)
# ===========================================================================
async def test_process_upload_task_missing_task(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    monkeypatch.setattr(storage_mod, "SessionLocal", lambda: db)
    # returns quietly; db closed
    await storage_mod.process_upload_task("nonexistent-task")
    db.close.assert_called_once()


# ===========================================================================
# module import sanity
# ===========================================================================
def test_router_prefix_is_storage_api():
    assert storage_mod.router.prefix == "/api/storage"
