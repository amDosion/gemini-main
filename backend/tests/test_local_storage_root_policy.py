"""Regression: local storage provider must not accept arbitrary server roots.

CANON-020 / CANON-025 / CANON-026 / W02R-010: an authenticated user could set a
'local' storage config with an arbitrary absolute storage_path; containment was
enforced only relative to that user-chosen root, so the user could browse / list /
upload / delete / rename anywhere the app user could access.

resolve_local_storage_runtime_config (the single resolution choke point used by
every local operation) must reject roots outside an operator-controlled allow
list. Default allow-root = the default local storage base, so out-of-the-box
behaviour is unchanged.
"""

import os

import pytest

from app.services.storage import local_provider


def test_default_local_storage_path_is_allowed():
    sp, prefix = local_provider.resolve_local_storage_runtime_config({})
    assert sp and prefix


def test_arbitrary_absolute_root_is_rejected(tmp_path):
    # An absolute path outside the default base (and with no operator allowlist)
    # must be rejected rather than silently accepted as the storage root.
    outside = str(tmp_path / "attacker_root")
    with pytest.raises(ValueError):
        local_provider.resolve_local_storage_runtime_config({"storage_path": outside})


def test_operator_allowlisted_root_is_permitted(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(tmp_path))
    sp, _prefix = local_provider.resolve_local_storage_runtime_config(
        {"storage_path": str(tmp_path / "sub")}
    )
    assert os.path.realpath(sp).startswith(os.path.realpath(str(tmp_path)))


@pytest.mark.asyncio
async def test_delete_rejects_sibling_dir_escape(tmp_path, monkeypatch):
    # CANON-020/025/026: delete() per-file containment must use realpath + os.sep,
    # so a sibling directory whose name shares the root's prefix (storage_evil vs
    # storage) cannot be escaped into via ../.
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(tmp_path))
    root = tmp_path / "storage"
    root.mkdir()
    sibling = tmp_path / "storage_evil"
    sibling.mkdir()
    victim = sibling / "secret.txt"
    victim.write_text("do-not-delete", encoding="utf-8")

    provider = local_provider.LocalProvider({"storage_path": str(root), "url_prefix": "/p"})
    result = await provider.delete("/p/../storage_evil/secret.txt")

    assert result is False
    assert victim.exists()  # escape must NOT have deleted the sibling file


@pytest.mark.asyncio
async def test_local_upload_url_and_path_are_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(tmp_path))
    root = tmp_path / "storage"
    provider = local_provider.LocalProvider(
        local_provider.scope_local_storage_config_for_user(
            {"storage_path": str(root)},
            "user-a",
        )
    )

    result = await provider.upload("x.png", b"img", "image/png")

    assert result.success is True
    assert result.url.startswith("/api/storage/local-files/user-a/")
    assert str(root / "user-a") in result.metadata["file_path"]


@pytest.mark.asyncio
async def test_local_browse_owner_scope_hides_sibling_users(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(tmp_path))
    root = tmp_path / "storage"
    (root / "user-a").mkdir(parents=True)
    (root / "user-b").mkdir(parents=True)
    (root / "user-a" / "a.txt").write_text("a", encoding="utf-8")
    (root / "user-b" / "b.txt").write_text("b", encoding="utf-8")

    provider = local_provider.LocalProvider(
        local_provider.scope_local_storage_config_for_user(
            {"storage_path": str(root)},
            "user-a",
        )
    )

    result = await provider.browse()
    paths = {item["path"] for item in result["items"]}

    assert paths == {"a.txt"}


def test_local_public_file_resolution_is_owner_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(tmp_path))
    root = tmp_path / "storage"
    owner_file = root / "user-a" / "visible.txt"
    sibling_file = root / "user-b" / "secret.txt"
    owner_file.parent.mkdir(parents=True)
    sibling_file.parent.mkdir(parents=True)
    owner_file.write_text("visible", encoding="utf-8")
    sibling_file.write_text("secret", encoding="utf-8")
    config = {"storage_path": str(root)}

    assert local_provider.resolve_local_public_file_path_for_user(
        "/api/storage/local-files/user-a/visible.txt",
        "user-a",
        config,
    ) == owner_file
    assert local_provider.resolve_local_public_file_path_for_user(
        "/api/storage/local-files/user-b/secret.txt",
        "user-a",
        config,
    ) is None
    assert local_provider.resolve_local_public_file_path_for_user(
        "/api/storage/local-files/user-a/visible.txt",
        None,
        config,
    ) is None


def test_local_public_file_resolution_enforces_owner_prefix_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(tmp_path))
    root = tmp_path / "storage"
    misleading_alias = root / "user-a" / "b" / "visible.txt"
    misleading_alias.parent.mkdir(parents=True)
    misleading_alias.write_text("visible", encoding="utf-8")

    assert local_provider.resolve_local_public_file_path_for_user(
        "/api/storage/local-files/user-ab/visible.txt",
        "user-a",
        {"storage_path": str(root)},
    ) is None
