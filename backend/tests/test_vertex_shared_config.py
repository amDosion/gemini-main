"""Regression tests for the shared Vertex AI config loader (V-S25).

`ExpandService._load_config` and `SegmentationService._load_config` were
near-verbatim duplicates that bypassed the shared TTL config cache used by the
coordinator layer. This forced a fresh DB SELECT on every service instance even
when a request fanned out across both services for the same user.

These tests pin:
1. A single shared helper `load_vertex_ai_config(user_id, db)` exists and both
   services route through it.
2. Both services produce an identical config dict (same shape) for the same
   user/db.
3. The shared TTL cache coalesces the DB read: the per-user row is fetched once
   across two service instances rather than once per service.
"""

from __future__ import annotations

from typing import Any, List

import pytest

from app.services.gemini.coordinators._config_cache import clear_config_cache
from app.services.gemini.vertexai.expand_service import ExpandService
from app.services.gemini.vertexai.segmentation_service import SegmentationService


class _FakeVertexRow:
    """Mimics a VertexAIConfig ORM row for the columns the loader reads."""

    def __init__(self) -> None:
        self.api_mode = "vertex_ai"
        self.vertex_ai_project_id = "proj-123"
        self.vertex_ai_location = "europe-west4"
        self.vertex_ai_credentials_json = "ENC::creds-blob"


class _FakeQuery:
    def __init__(self, counter: List[int], row: Any) -> None:
        self._counter = counter
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        self._counter[0] += 1
        return self._row


class _FakeSession:
    """Counts how many times a VertexAIConfig row is SELECTed."""

    def __init__(self, row: Any) -> None:
        self.query_counter: List[int] = [0]
        self._row = row

    def query(self, model):
        return _FakeQuery(self.query_counter, self._row)


_SENTINEL_CREDENTIALS = object()


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture
def _patch_decrypt_and_credentials(monkeypatch):
    """Patch decrypt + service_account so no real crypto/GCP calls happen."""
    import app.core.encryption as encryption
    from google.oauth2 import service_account

    monkeypatch.setattr(
        encryption, "decrypt_data", lambda blob, **kw: '{"type": "service_account"}'
    )
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        classmethod(lambda cls, info, **kw: _SENTINEL_CREDENTIALS),
    )


def test_shared_loader_exists_and_is_importable():
    # RED: module/helper does not exist yet.
    from app.services.gemini.vertexai._vertex_config import load_vertex_ai_config

    assert callable(load_vertex_ai_config)


def test_both_services_produce_identical_config(_patch_decrypt_and_credentials):
    row = _FakeVertexRow()
    session = _FakeSession(row)

    expand = ExpandService(user_id="user-a", db=session)
    seg = SegmentationService(user_id="user-a", db=session)

    expand_config = expand._load_config()
    seg_config = seg._load_config()

    # Identical shape and values across both services.
    assert expand_config == seg_config
    assert expand_config["project_id"] == "proj-123"
    assert expand_config["location"] == "europe-west4"
    assert expand_config["credentials"] is _SENTINEL_CREDENTIALS


def test_shared_cache_coalesces_db_read_across_services(_patch_decrypt_and_credentials):
    row = _FakeVertexRow()
    session = _FakeSession(row)

    # Two distinct service instances for the SAME user.
    expand = ExpandService(user_id="user-shared", db=session)
    seg = SegmentationService(user_id="user-shared", db=session)

    expand._load_config()
    seg._load_config()

    # The shared TTL cache must coalesce the per-user DB SELECT to a single read.
    assert session.query_counter[0] == 1, (
        "Expected the VertexAIConfig row to be SELECTed once across both services "
        f"via the shared cache, got {session.query_counter[0]} reads."
    )


def test_loader_falls_back_to_environment_when_no_db_row(monkeypatch):
    # No DB row -> environment fallback path must still produce a project_id.
    from app.core.config import settings

    monkeypatch.setattr(settings, "gcp_project_id", "env-proj", raising=False)
    monkeypatch.setattr(settings, "gcp_location", "us-east1", raising=False)

    session = _FakeSession(None)
    expand = ExpandService(user_id="user-noconf", db=session)
    config = expand._load_config()

    assert config["project_id"] == "env-proj"
    assert config["location"] == "us-east1"
    assert "credentials" not in config or config.get("credentials") is None


def test_loader_raises_when_project_id_missing(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gcp_project_id", None, raising=False)
    monkeypatch.setattr(settings, "gcp_location", None, raising=False)

    # No user_id/db at all -> straight to env, which has no project_id.
    seg = SegmentationService()
    with pytest.raises(ValueError, match="GCP_PROJECT_ID|GCP configuration"):
        seg._load_config()
