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
