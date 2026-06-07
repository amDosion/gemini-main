"""M2: workflow local-file reference must enforce allow-root containment.

When ``workflow_allow_local_file_reference`` is enabled, ``load_binary_from_reference``
previously did ``Path(path_value).expanduser().read_bytes()`` with no root bounding,
so a workflow author could read arbitrary server files (``~/.ssh/id_rsa``,
``/etc/passwd``, ``../../`` escapes). The loader must require the resolved path to
live under an operator allow-root (``LOCAL_STORAGE_ALLOWED_ROOTS`` / default) and
reject ``~`` expansion — consistent with the local storage provider containment.

Tests use relative paths + ``chdir`` so they exercise the local-file branch
(``urlparse`` scheme == "") identically on POSIX and Windows (an absolute Windows
path like ``C:\\...`` is parsed as scheme "c" and never reaches this branch).
"""

import pytest

from app.core.config import settings
from app.services.agent.workflow_engine import references


@pytest.fixture(autouse=True)
def _enable_flag(monkeypatch):
    monkeypatch.setattr(settings, "workflow_allow_local_file_reference", True, raising=False)


def test_local_reference_rejects_path_outside_allow_root(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCAL_STORAGE_ALLOWED_ROOTS", raising=False)
    (tmp_path / "secret.txt").write_bytes(b"SECRET-DO-NOT-LEAK")
    monkeypatch.chdir(tmp_path)  # relative path resolves here, outside any allow-root
    with pytest.raises(ValueError):
        references.load_binary_from_reference(None, "secret.txt")


def test_local_reference_rejects_home_expansion(monkeypatch):
    monkeypatch.delenv("LOCAL_STORAGE_ALLOWED_ROOTS", raising=False)
    with pytest.raises(ValueError):
        references.load_binary_from_reference(None, "~/.ssh/id_rsa")


def test_local_reference_rejects_traversal_escape(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    (tmp_path / "outside.txt").write_bytes(b"SECRET")
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(root))
    monkeypatch.chdir(root)
    with pytest.raises(ValueError):
        references.load_binary_from_reference(None, "../outside.txt")


def test_local_reference_allows_file_inside_allow_root(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "data.csv").write_bytes(b"a,b,c\n1,2,3\n")
    monkeypatch.setenv("LOCAL_STORAGE_ALLOWED_ROOTS", str(root))
    monkeypatch.chdir(root)
    raw, _mime, name = references.load_binary_from_reference(None, "data.csv")
    assert raw == b"a,b,c\n1,2,3\n"
    assert name == "data.csv"


def test_local_reference_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "workflow_allow_local_file_reference", False, raising=False)
    (tmp_path / "data.csv").write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        references.load_binary_from_reference(None, "data.csv")
