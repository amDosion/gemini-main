"""Coverage-focused tests for the research + models REST routers.

Targets
-------
* ``app.routers.ai.research``  — deep-research start/status/cancel/continue/
  followup/summarize/format endpoints plus pure text/prompt helpers.
* ``app.routers.models.models`` — provider model listing (DB-only + verify
  paths), cache clear/status endpoints, admin permission gating, plus the
  large body of pure helper / mode-filter functions.

Strategy
--------
* Each router is mounted on a fresh :class:`FastAPI` app. Only true FastAPI
  boundary dependencies are overridden: auth (``require_current_user``), the
  DB session (``get_db``), and the per-router singleton dependencies
  (rate limiter / research cache / validator / redis cache).
* The DB is a real in-memory SQLite engine populated with the production
  SQLAlchemy models, so user-scoping, profile resolution and saved-model
  merging run for real.
* Only external boundaries are patched: the Google credentials resolver, the
  interactions manager (provider SDK), and the provider factory used by the
  verify path. The routers' own validation / error-mapping / serialization
  logic runs unmocked.

Assertions check real behavior: status codes, response envelopes, rate-limit
(429), unsafe-prompt (400), invalid-agent (400), not-completed (400),
credential-missing (401), admin permission (403), cache lifecycle, and the
deterministic helper branches.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import (
    get_cache,
    get_rate_limiter,
    get_research_cache,
    get_validator,
    require_current_user,
)
from app.models.db_models import (
    ConfigProfile,
    User,
    UserSettings,
    VertexAIConfig,
    generate_uuid,
)
from app.routers.ai import research as rs
from app.routers.models import models as mr
from app.routers.system.admin import require_admin_user

USER_ID = "user-rm-1"
DEEP_AGENT = "deep-research-pro-preview-12-2025"


# --------------------------------------------------------------------------- #
# Shared in-memory DB fixture
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# --------------------------------------------------------------------------- #
# Fakes for the singleton dependencies (rate limiter / cache / validator)
# --------------------------------------------------------------------------- #
class FakeRateLimiter:
    def __init__(self, allow: bool = True) -> None:
        self.allow = allow
        self.calls: List[Dict[str, Any]] = []

    async def check_rate_limit(self, user_id, *, max_requests, window_seconds):
        self.calls.append(
            {"user_id": user_id, "max_requests": max_requests, "window_seconds": window_seconds}
        )
        return self.allow


class FakeValidator:
    def __init__(self, safe: bool = True, warnings: Optional[List[str]] = None) -> None:
        self.safe = safe
        self.warnings = warnings or ["unsafe pattern"]

    def validate_prompt(self, prompt: str):
        return self.safe, ([] if self.safe else list(self.warnings))


class FakeResearchCache:
    """In-memory stand-in for ``ResearchCache`` (no Redis)."""

    def __init__(self) -> None:
        self.interactions: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, str] = {}
        self.deleted: List[str] = []

    def cache_interaction(self, interaction_id, data, ttl=3600):
        self.interactions[interaction_id] = dict(data)

    def get_cached_interaction(self, interaction_id):
        return self.interactions.get(interaction_id)

    def cache_research_result(self, prompt_hash, result_text, ttl=86400):
        self.results[prompt_hash] = result_text

    def delete_cached_interaction(self, interaction_id):
        self.deleted.append(interaction_id)
        self.interactions.pop(interaction_id, None)


class FakeInteractionsManager:
    """Stand-in for the interactions manager (the provider SDK boundary)."""

    def __init__(
        self,
        *,
        create_result: Optional[Dict[str, Any]] = None,
        status_result: Optional[Dict[str, Any]] = None,
        create_error: Optional[Exception] = None,
        status_error: Optional[Exception] = None,
    ) -> None:
        self.create_result = create_result or {"id": "new-int-1", "status": "running"}
        self.status_result = status_result or {"status": "completed", "outputs": []}
        self.create_error = create_error
        self.status_error = status_error
        self.create_calls: List[Dict[str, Any]] = []
        self.cancel_calls: List[Dict[str, Any]] = []

    async def create_interaction(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.create_error:
            raise self.create_error
        return self.create_result

    async def get_interaction_status_async(self, **kwargs):
        if self.status_error:
            raise self.status_error
        return self.status_result

    async def cancel_interaction(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return {"status": "cancelled"}


# --------------------------------------------------------------------------- #
# Research router fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def research_ctx(db_session, monkeypatch):
    """Mount the research router with deterministic fakes + patched boundaries."""
    app = FastAPI()
    app.include_router(rs.router)

    rate_limiter = FakeRateLimiter(allow=True)
    cache = FakeResearchCache()
    validator = FakeValidator(safe=True)
    manager = FakeInteractionsManager()

    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter
    app.dependency_overrides[get_research_cache] = lambda: cache
    app.dependency_overrides[get_validator] = lambda: validator

    async def _fake_resolve(*, provider_id, db, user_id):
        return "fake-google-key", {}

    monkeypatch.setattr(rs.credentials_resolver, "resolve", _fake_resolve)
    monkeypatch.setattr(rs, "get_interactions_manager", lambda **kw: manager)

    ctx = {
        "app": app,
        "rate_limiter": rate_limiter,
        "cache": cache,
        "validator": validator,
        "manager": manager,
        "monkeypatch": monkeypatch,
    }
    with TestClient(app) as client:
        ctx["client"] = client
        yield ctx
    app.dependency_overrides.clear()


# ============================================================================ #
# research.py — pure helper functions
# ============================================================================ #
def test_collect_texts_recurses_strings_lists_dicts():
    bucket: List[str] = []
    value = {
        "content": [
            {"text": "  hello  "},
            {"parts": ["world", "", "  "]},
        ],
        "delta": {"output": "tail"},
        "text": "top",
    }
    rs._collect_texts(value, bucket)
    assert "top" in bucket
    assert "hello" in bucket
    assert "world" in bucket
    assert "tail" in bucket
    # whitespace-only entries are skipped
    assert "" not in bucket and "  " not in bucket


def test_collect_texts_depth_guard_stops_recursion():
    bucket: List[str] = []
    rs._collect_texts({"content": "x"}, bucket, depth=9)
    assert bucket == []


def test_extract_result_dedups_and_joins():
    outputs = [
        {"text": "alpha"},
        {"text": "alpha"},  # duplicate dropped
        {"content": [{"text": "beta"}]},
    ]
    result = rs._extract_result(outputs)
    assert result == "alpha\n\nbeta"


def test_extract_result_non_list_returns_empty():
    assert rs._extract_result({"text": "x"}) == ""
    assert rs._extract_result(None) == ""


def test_extract_progress_prefers_latest_status_update():
    outputs = [
        {"type": "status_update", "text": "first"},
        {"type": "thought_summary", "text": "later"},
    ]
    assert rs._extract_progress(outputs) == "later"


def test_extract_progress_default_when_no_status():
    assert rs._extract_progress([]) == "Research in progress..."
    assert rs._extract_progress([{"type": "other", "text": "x"}]) == "Research in progress..."


def test_build_prompt_appends_format_language_and_tone():
    req = rs.ResearchStartRequest(
        prompt="Research quantum computing trends",
        format="As a report",
        language="French",
        tone="technical",
    )
    full = rs._build_prompt(req)
    assert full.startswith("Research quantum computing trends")
    assert "As a report" in full
    assert "Please respond in French." in full
    assert "technical language" in full


def test_build_prompt_unknown_tone_appends_empty():
    req = rs.ResearchStartRequest(prompt="Investigate market shifts", tone="unknown-tone")
    full = rs._build_prompt(req)
    # unknown tone resolves to empty instruction, prompt text preserved
    assert full.startswith("Investigate market shifts")


def test_build_research_tools_file_search_path():
    tools = rs._build_research_tools(
        include_private_data=True,
        file_search_store_names=["store-a"],
    )
    assert isinstance(tools, list)


def test_build_research_tools_default_path():
    tools = rs._build_research_tools(include_private_data=False, file_search_store_names=None)
    assert isinstance(tools, list)


# ============================================================================ #
# research.py — /start endpoint
# ============================================================================ #
def test_start_research_happy_path(research_ctx):
    research_ctx["manager"].create_result = {"id": "int-123", "status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["interaction_id"] == "int-123"
    assert body["status"] == "running"
    # the start prompt was cached for later status reconciliation
    assert "int-123" in research_ctx["cache"].interactions


def test_start_research_rate_limited(research_ctx):
    research_ctx["rate_limiter"].allow = False
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "RATE_LIMIT_EXCEEDED"


def test_start_research_unsafe_prompt(research_ctx):
    research_ctx["validator"].safe = False
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "INVALID_ARGUMENT"


def test_start_research_non_deep_agent_rejected(research_ctx):
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": "gemini-2.5-flash"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "INVALID_DEEP_RESEARCH_AGENT"


def test_start_research_missing_interaction_id_maps_to_error(research_ctx):
    # Empty id -> the 500 HTTPException is raised, then re-raised as-is.
    research_ctx["manager"].create_result = {"id": "", "status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 500


def test_start_research_missing_credentials_401(research_ctx):
    async def _empty_resolve(*, provider_id, db, user_id):
        return "", {}

    research_ctx["monkeypatch"].setattr(rs.credentials_resolver, "resolve", _empty_resolve)
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 401


def test_start_research_provider_error_mapped(research_ctx):
    research_ctx["manager"].create_error = RuntimeError("provider exploded")
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "Research the future of AI safety", "agent": DEEP_AGENT},
    )
    # handle_gemini_error maps unknown errors to 500
    assert resp.status_code == 500


def test_start_research_prompt_too_short_422(research_ctx):
    # min_length=10 enforced by pydantic before handler runs
    resp = research_ctx["client"].post(
        "/api/research/start",
        json={"prompt": "short", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 422


# ============================================================================ #
# research.py — /status endpoint
# ============================================================================ #
def test_status_returns_cached_completed(research_ctx):
    research_ctx["cache"].interactions["int-c"] = {"status": "completed", "result": "done text"}
    resp = research_ctx["client"].get("/api/research/status/int-c")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"] == "done text"


def test_status_completed_extracts_result_and_caches(research_ctx):
    # prime the start cache so the prompt-hash branch is taken
    research_ctx["cache"].interactions["int-s"] = {"prompt": "my research prompt"}
    research_ctx["manager"].status_result = {
        "status": "completed",
        "outputs": [{"text": "final research output"}],
        "usage": {"input_tokens": 5},
    }
    resp = research_ctx["client"].get("/api/research/status/int-s")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "final research output" in body["result"]
    # research-result cache by prompt hash was populated
    assert research_ctx["cache"].results


def test_status_failed_returns_error(research_ctx):
    research_ctx["manager"].status_result = {"status": "failed", "error": "boom"}
    resp = research_ctx["client"].get("/api/research/status/int-f")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"] == "boom"


def test_status_in_progress_returns_progress(research_ctx):
    research_ctx["manager"].status_result = {
        "status": "running",
        "outputs": [{"type": "status_update", "text": "thinking hard"}],
    }
    resp = research_ctx["client"].get("/api/research/status/int-p")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["progress"] == "thinking hard"


def test_status_provider_error_mapped(research_ctx):
    research_ctx["manager"].status_error = RuntimeError("status failure")
    resp = research_ctx["client"].get("/api/research/status/int-e")
    assert resp.status_code == 500


# ============================================================================ #
# research.py — /cancel endpoint
# ============================================================================ #
def test_cancel_research_success(research_ctx):
    research_ctx["cache"].interactions["int-x"] = {"status": "running"}
    resp = research_ctx["client"].post("/api/research/cancel/int-x")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Research task cancelled"
    assert "int-x" in research_ctx["cache"].deleted


def test_cancel_research_provider_error_mapped(research_ctx):
    async def _boom(**kwargs):
        raise RuntimeError("cancel failed")

    research_ctx["manager"].cancel_interaction = _boom
    resp = research_ctx["client"].post("/api/research/cancel/int-x")
    assert resp.status_code == 500


# ============================================================================ #
# research.py — /continue endpoint
# ============================================================================ #
def test_continue_research_requires_completed_previous(research_ctx):
    research_ctx["manager"].status_result = {"status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/continue/prev-1",
        json={"prompt": "Continue the previous research thread", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 400
    assert "must be completed" in resp.json()["detail"]["message"]


def test_continue_research_happy_path(research_ctx):
    research_ctx["manager"].status_result = {"status": "completed", "outputs": []}
    research_ctx["manager"].create_result = {"id": "cont-1", "status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/continue/prev-1",
        json={"prompt": "Continue the previous research thread", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["interaction_id"] == "cont-1"
    # the create call carried the previous_interaction_id
    assert research_ctx["manager"].create_calls[-1]["previous_interaction_id"] == "prev-1"


def test_continue_research_invalid_agent(research_ctx):
    resp = research_ctx["client"].post(
        "/api/research/continue/prev-1",
        json={"prompt": "Continue the previous research thread", "agent": "gemini-2.5-flash"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "INVALID_DEEP_RESEARCH_AGENT"


def test_continue_research_rate_limited(research_ctx):
    research_ctx["rate_limiter"].allow = False
    resp = research_ctx["client"].post(
        "/api/research/continue/prev-1",
        json={"prompt": "Continue the previous research thread", "agent": DEEP_AGENT},
    )
    assert resp.status_code == 429


# ============================================================================ #
# research.py — /followup endpoint
# ============================================================================ #
def test_followup_research_happy_path(research_ctx):
    research_ctx["manager"].status_result = {"status": "completed", "outputs": []}
    research_ctx["manager"].create_result = {"id": "follow-1", "status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/followup/prev-1",
        json={"question": "What about side effects?"},
    )
    assert resp.status_code == 200
    assert resp.json()["interaction_id"] == "follow-1"


def test_followup_research_requires_completed(research_ctx):
    research_ctx["manager"].status_result = {"status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/followup/prev-1",
        json={"question": "Another question here"},
    )
    assert resp.status_code == 400


def test_followup_research_unsafe_question(research_ctx):
    research_ctx["validator"].safe = False
    resp = research_ctx["client"].post(
        "/api/research/followup/prev-1",
        json={"question": "Another question here"},
    )
    assert resp.status_code == 400


# ============================================================================ #
# research.py — /summarize endpoint
# ============================================================================ #
def test_summarize_research_happy_path(research_ctx):
    research_ctx["manager"].status_result = {"status": "completed", "outputs": []}
    research_ctx["manager"].create_result = {"id": "sum-1", "status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/summarize/prev-1",
        json={"format": "markdown", "max_length": 500},
    )
    assert resp.status_code == 200
    assert resp.json()["interaction_id"] == "sum-1"
    # summarize prompt includes the requested length constraint
    last_input = research_ctx["manager"].create_calls[-1]["input"]
    assert "500 words" in last_input


def test_summarize_research_requires_completed(research_ctx):
    research_ctx["manager"].status_result = {"status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/summarize/prev-1",
        json={"format": "markdown"},
    )
    assert resp.status_code == 400


# ============================================================================ #
# research.py — /format endpoint
# ============================================================================ #
def test_format_research_happy_path(research_ctx):
    research_ctx["manager"].status_result = {"status": "completed", "outputs": []}
    research_ctx["manager"].create_result = {"id": "fmt-1", "status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/format/prev-1",
        json={"output_format": "json", "output_schema": {"title": "string"}},
    )
    assert resp.status_code == 200
    assert resp.json()["interaction_id"] == "fmt-1"
    last_input = research_ctx["manager"].create_calls[-1]["input"]
    assert "JSON" in last_input
    assert "schema" in last_input


def test_format_research_requires_completed(research_ctx):
    research_ctx["manager"].status_result = {"status": "running"}
    resp = research_ctx["client"].post(
        "/api/research/format/prev-1",
        json={"output_format": "xml"},
    )
    assert resp.status_code == 400


# ============================================================================ #
# models.py — pure helper functions
# ============================================================================ #
def test_extract_hidden_model_ids():
    class P:
        hidden_models = ["a", "b", 5, "", "c"]

    assert mr._extract_hidden_model_ids(P()) == {"a", "b", "c"}
    assert mr._extract_hidden_model_ids(None) == set()

    class NoAttr:
        pass

    assert mr._extract_hidden_model_ids(NoAttr()) == set()


def test_apply_hidden_model_filter():
    from app.services.common.model_capabilities import build_model_config

    m1 = build_model_config("openai", "gpt-4o")
    m2 = build_model_config("openai", "gpt-4o-mini")
    models = [m1, m2]
    filtered = mr._apply_hidden_model_filter(models, {m1.id}, include_hidden=False)
    assert all(m.id != m1.id for m in filtered)
    # include_hidden keeps everything
    assert mr._apply_hidden_model_filter(models, {m1.id}, include_hidden=True) == models
    # empty hidden set returns input unchanged
    assert mr._apply_hidden_model_filter(models, set()) == models


def test_matches_model_list_prefix_and_exact():
    assert mr._matches_model_list("gpt-image-1", ["gpt-image-1"]) is True
    assert mr._matches_model_list("imagen-3.0-generate-002", ["imagen-3.0-generate-001"]) is True
    assert mr._matches_model_list("totally-different", ["gpt-image-1"]) is False


def test_model_id_classifiers():
    assert mr._is_gemini_image_model_id("gemini-2.5-flash-image") is True
    assert mr._is_gemini_image_model_id("gemini-2.5-flash") is False
    assert mr._is_openai_gpt_image_model_id("gpt-image-1") is True
    assert mr._is_openai_gpt_image_model_id("chatgpt-image") is True
    assert mr._is_openai_gpt_image_model_id("gpt-4o") is False
    assert mr._is_tongyi_image_generation_model_id("qwen-image") is True
    assert mr._is_tongyi_image_generation_model_id("qwen-image-edit") is False
    assert mr._is_tongyi_image_edit_model_id("qwen-image-edit") is True
    assert mr._is_tongyi_outpainting_model_id("image-out-painting") is True
    assert mr._is_tongyi_virtual_tryon_model_id("aitryon-plus") is True
    assert mr._is_tongyi_video_generation_model_id("wan2.7-t2v-plus") is True


def test_tongyi_audio_classifier_excludes_realtime():
    assert mr._is_tongyi_supported_audio_model_id("qwen-tts") is True
    assert mr._is_tongyi_supported_audio_model_id("qwen-tts-realtime") is False
    assert mr._is_tongyi_supported_audio_model_id("qwen3-tts-vc-x") is False


def test_normalize_context_window():
    assert mr._normalize_context_window(None) is None
    assert mr._normalize_context_window("4096") == 4096
    assert mr._normalize_context_window("not-a-number") is None
    assert mr._normalize_context_window(8192) == 8192


def test_normalize_trait_bool():
    assert mr._normalize_trait_bool(True) is True
    assert mr._normalize_trait_bool("yes") is True
    assert mr._normalize_trait_bool("off") is False
    assert mr._normalize_trait_bool(1) is True
    assert mr._normalize_trait_bool(0) is False


def test_extract_raw_traits():
    raw = {"traits": {"deepResearch": "true", "thinking": True}}
    out = mr._extract_raw_traits(raw)
    assert out["deep_research"] is True
    assert out["thinking"] is True
    assert out["multimodal_understanding"] is False
    # missing/invalid traits dict -> empty
    assert mr._extract_raw_traits({"traits": "bad"}) == {}


def test_parse_and_extract_saved_models():
    raw = [{"id": "m1"}, {"model_id": "m2"}, "garbage", {"name": "noid"}]
    parsed = mr._parse_saved_models(raw)
    assert len(parsed) == 3  # only dict entries
    ids = mr._extract_saved_model_ids(raw)
    assert ids == ["m1", "m2"]
    assert mr._parse_saved_models(None) == []
    assert mr._parse_saved_models("nope") == []


def test_merge_saved_models_adds_and_updates():
    from app.services.common.model_capabilities import build_model_config

    existing = build_model_config("openai", "gpt-4o")
    raw_saved = [
        {"id": "gpt-4o", "name": "GPT-4o Custom", "capabilities": {"vision": True}},
        {"id": "brand-new-model", "name": "Brand New", "context_window": 12345},
    ]
    merged = mr._merge_saved_models("openai", [existing], raw_saved, source="test")
    by_id = {m.id: m for m in merged}
    assert "brand-new-model" in by_id
    assert by_id["brand-new-model"].context_window == 12345
    # vision capability supplemented onto existing
    assert by_id["gpt-4o"].capabilities.vision is True


def test_merge_saved_models_empty_returns_input():
    assert mr._merge_saved_models("openai", [], None, source="t") == []


def test_merge_static_media_models_provider_gating():
    # non-matching providers return input unchanged
    assert mr._merge_google_vertex_static_models("openai", []) == []
    assert mr._merge_tongyi_static_media_models("openai", []) == []
    assert mr._merge_openai_static_media_models("google", []) == []
    # matching provider injects static catalog entries
    google_models = mr._merge_google_vertex_static_models("google", [])
    assert len(google_models) > 0
    openai_models = mr._merge_openai_static_media_models("openai", [])
    assert len(openai_models) > 0


def test_select_default_model_id_prefers_preferred():
    from app.services.common.model_capabilities import build_model_config

    m1 = build_model_config("openai", "gpt-4o")
    m2 = build_model_config("openai", "gpt-4o-mini")
    assert mr._select_default_model_id([m1, m2], [m2.id]) == m2.id
    # fallback to first when no preferred matches
    assert mr._select_default_model_id([m1, m2], ["unknown"]) == m1.id
    assert mr._select_default_model_id([], ["x"]) is None


def test_select_default_model_id_for_mode_uses_mode_default():
    from app.services.common.model_capabilities import build_model_config

    gpt_image = build_model_config("openai", "gpt-image-2")
    other = build_model_config("openai", "gpt-4o")
    chosen = mr._select_default_model_id_for_mode([gpt_image, other], [], "image-gen")
    assert chosen == "gpt-image-2"
    # mode without a registered default falls back to preferred/first
    chosen2 = mr._select_default_model_id_for_mode([other], [], "chat")
    assert chosen2 == other.id


def test_filter_models_by_mode_chat_excludes_media():
    from app.services.common.model_capabilities import build_model_config

    chat_model = build_model_config("openai", "gpt-4o")
    video_model = build_model_config("google", "veo-3.0-generate-001")
    image_model = build_model_config("openai", "gpt-image-2")
    models = [chat_model, video_model, image_model]

    chat_filtered = mr.filter_models_by_mode(models, "chat")
    ids = {m.id for m in chat_filtered}
    assert "gpt-4o" in ids
    assert "veo-3.0-generate-001" not in ids
    assert "gpt-image-2" not in ids


def test_filter_models_by_mode_video_gen_includes_video():
    from app.services.common.model_capabilities import build_model_config

    video_model = build_model_config("google", "veo-3.0-generate-001")
    chat_model = build_model_config("openai", "gpt-4o")
    filtered = mr.filter_models_by_mode([video_model, chat_model], "video-gen")
    ids = {m.id for m in filtered}
    assert "veo-3.0-generate-001" in ids
    assert "gpt-4o" not in ids


def test_filter_models_by_mode_image_gen():
    from app.services.common.model_capabilities import build_model_config

    gen = build_model_config("openai", "gpt-image-2")
    edit = build_model_config("openai", "gpt-image-1-edit")
    filtered = mr.filter_models_by_mode([gen, edit], "image-gen")
    ids = {m.id for m in filtered}
    assert "gpt-image-2" in ids


def test_filter_models_by_mode_unknown_keeps_all():
    from app.services.common.model_capabilities import build_model_config

    m = build_model_config("openai", "gpt-4o")
    assert mr.filter_models_by_mode([m], "totally-unknown-mode") == [m]


def test_cache_lifecycle_helpers():
    from app.services.common.model_capabilities import build_model_config

    mr.clear_cache()  # start clean
    assert mr.is_cache_valid("openai") is False
    assert mr.get_cached_models("openai") is None

    mr.cache_models("openai", [build_model_config("openai", "gpt-4o")])
    assert mr.is_cache_valid("openai") is True
    cached = mr.get_cached_models("openai")
    assert cached and cached[0]["id"] == "gpt-4o"

    mr.clear_cache("openai")
    assert mr.is_cache_valid("openai") is False
    # clearing missing provider is a no-op (no exception)
    mr.clear_cache("nonexistent")
    # clear all
    mr.cache_models("google", [build_model_config("google", "gemini-2.5-flash")])
    mr.clear_cache()
    assert mr.is_cache_valid("google") is False


# ============================================================================ #
# models.py — HTTP endpoints
# ============================================================================ #
class FakeCacheService:
    """Stand-in for the Redis-backed CacheService used by the models router."""

    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}
        self.deleted_patterns: List[str] = []

    def _make_key(self, prefix, *args, **kwargs):
        return ":".join(["cache", prefix, *[str(a) for a in args]])

    async def get_or_set(self, key, fetch, ttl=3600):
        if key not in self.store:
            self.store[key] = await fetch()
        return self.store[key]

    async def delete(self, pattern):
        self.deleted_patterns.append(pattern)
        return 3


@pytest.fixture()
def models_client(db_session):
    app = FastAPI()
    app.include_router(mr.router)
    fake_cache = FakeCacheService()
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_cache] = lambda: fake_cache
    mr.clear_cache()
    with TestClient(app) as client:
        client.fake_cache = fake_cache  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    mr.clear_cache()


def _seed_profile(db, *, provider="openai", saved_models=None, hidden_models=None):
    now = int(time.time() * 1000)
    profile = ConfigProfile(
        id=generate_uuid(),
        user_id=USER_ID,
        name="P",
        provider_id=provider,
        api_key="enc-key",
        base_url="",
        protocol="openai",
        hidden_models=hidden_models or [],
        saved_models=saved_models or [],
        created_at=now,
        updated_at=now,
    )
    db.add(profile)
    db.commit()
    return profile


def test_get_available_models_db_only(models_client, db_session):
    _seed_profile(
        db_session,
        provider="openai",
        saved_models=[{"id": "gpt-4o", "name": "GPT-4o"}],
    )
    resp = models_client.get("/api/models/openai?use_cache=false")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "openai"
    assert body["cached"] is False
    ids = {m["id"] for m in body["models"]}
    assert "gpt-4o" in ids
    assert "mode_catalog" in body
    assert isinstance(body["mode_catalog"], list)


def test_get_available_models_uses_cache_service(models_client, db_session):
    _seed_profile(db_session, provider="openai", saved_models=[{"id": "gpt-4o"}])
    resp = models_client.get("/api/models/openai?use_cache=true")
    assert resp.status_code == 200
    assert resp.json()["cached"] is True


def test_get_available_models_hidden_filter(models_client, db_session):
    _seed_profile(
        db_session,
        provider="openai",
        saved_models=[{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}],
        hidden_models=["gpt-4o-mini"],
    )
    resp = models_client.get("/api/models/openai?use_cache=false")
    ids = {m["id"] for m in resp.json()["models"]}
    assert "gpt-4o-mini" not in ids
    # include_hidden re-exposes it
    resp2 = models_client.get("/api/models/openai?use_cache=false&include_hidden=true")
    ids2 = {m["id"] for m in resp2.json()["models"]}
    assert "gpt-4o-mini" in ids2


def test_get_available_models_mode_filter(models_client, db_session):
    _seed_profile(
        db_session,
        provider="openai",
        saved_models=[{"id": "gpt-4o"}, {"id": "gpt-image-2"}],
    )
    resp = models_client.get("/api/models/openai?use_cache=false&mode=chat")
    body = resp.json()
    assert body["filtered_by_mode"] == "chat"
    ids = {m["id"] for m in body["models"]}
    assert "gpt-4o" in ids
    assert "gpt-image-2" not in ids  # image model excluded from chat mode


def test_get_available_models_verify_path(models_client, db_session, monkeypatch):
    """Verify request (api_key override) calls the provider factory live path."""
    _seed_profile(db_session, provider="openai")

    from app.services.common.model_capabilities import build_model_config

    async def _fake_creds(*, provider, db, user_id, request_api_key, request_base_url):
        return "live-key", "https://api.example.com"

    class FakeService:
        async def get_available_models(self):
            return [build_model_config("openai", "gpt-4o")]

    class FakeFactory:
        @staticmethod
        def create(**kwargs):
            return FakeService()

    monkeypatch.setattr(mr, "get_provider_credentials", _fake_creds)
    import app.services.common.provider_factory as pf

    monkeypatch.setattr(pf, "ProviderFactory", FakeFactory)

    resp = models_client.get("/api/models/openai?api_key=sk-test")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()["models"]}
    assert "gpt-4o" in ids


def test_get_available_models_internal_error_500(models_client, db_session, monkeypatch):
    _seed_profile(db_session, provider="openai")

    def _boom(*a, **k):
        raise RuntimeError("scope build failed")

    # Force an unexpected error inside the handler -> mapped to 500.
    monkeypatch.setattr(mr, "_get_profile_cache_scope", _boom)
    resp = models_client.get("/api/models/openai?use_cache=false")
    assert resp.status_code == 500


def test_clear_model_cache_endpoint(models_client):
    resp = models_client.delete("/api/models/openai/cache")
    assert resp.status_code == 200
    body = resp.json()
    assert "openai" in body["message"]
    assert body["redis_keys_deleted"] == 3
    assert body["pattern"] == "cache:models:openai:*"


def test_cache_status_endpoint(models_client):
    from app.services.common.model_capabilities import build_model_config

    mr.cache_models("openai", [build_model_config("openai", "gpt-4o")])
    resp = models_client.get("/api/models/cache/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "openai" in body
    assert body["openai"]["cached"] is True
    assert body["openai"]["model_count"] == 1


# ----- admin-gated clear-all-cache endpoint -----
def _seed_user(db, *, is_admin: bool):
    user = User(id=USER_ID, email=f"{USER_ID}@x.io", password_hash="h", is_admin=is_admin)
    db.add(user)
    db.commit()
    return user


def test_clear_all_cache_requires_admin(db_session):
    """Non-admin user gets 403 from the require_admin_user dependency."""
    _seed_user(db_session, is_admin=False)
    app = FastAPI()
    app.include_router(mr.router)
    fake_cache = FakeCacheService()
    # Use the real require_admin_user chain (only auth + db overridden).
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_cache] = lambda: fake_cache
    with TestClient(app) as client:
        resp = client.delete("/api/models/cache")
    app.dependency_overrides.clear()
    assert resp.status_code == 403


def test_clear_all_cache_admin_ok(db_session):
    _seed_user(db_session, is_admin=True)
    app = FastAPI()
    app.include_router(mr.router)
    fake_cache = FakeCacheService()
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_cache] = lambda: fake_cache
    with TestClient(app) as client:
        resp = client.delete("/api/models/cache")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["pattern"] == "cache:models:*"
    assert body["redis_keys_deleted"] == 3


def test_clear_all_cache_admin_override_path(db_session):
    """Overriding require_admin_user directly also exercises the handler body."""
    app = FastAPI()
    app.include_router(mr.router)
    fake_cache = FakeCacheService()
    app.dependency_overrides[require_admin_user] = lambda: USER_ID
    app.dependency_overrides[get_cache] = lambda: fake_cache
    with TestClient(app) as client:
        resp = client.delete("/api/models/cache")
    app.dependency_overrides.clear()
    assert resp.status_code == 200


# ----- profile-scope helpers with real DB rows (google + vertex) -----
def test_profile_cache_scope_google_with_vertex(db_session):
    now = int(time.time() * 1000)
    profile = ConfigProfile(
        id=generate_uuid(),
        user_id=USER_ID,
        name="G",
        provider_id="google",
        api_key="k",
        protocol="google",
        saved_models=[{"id": "gemini-2.5-flash"}],
        created_at=now,
        updated_at=now,
    )
    db_session.add(profile)
    vertex = VertexAIConfig(
        user_id=USER_ID,
        api_mode="vertex_ai",
        saved_models=[{"id": "imagen-3.0-generate-002"}],
    )
    db_session.add(vertex)
    db_session.commit()

    scope = mr._get_profile_cache_scope("google", db_session, USER_ID)
    assert "vertex:" in scope
    assert mr.MODEL_CAPABILITY_CACHE_VERSION in scope

    # preferred ids combine profile + vertex saved models
    eff = mr._get_effective_profile("google", db_session, USER_ID)
    vcfg = mr._get_vertex_ai_config(db_session, USER_ID)
    preferred = mr._build_preferred_model_ids("google", eff, vcfg)
    assert "gemini-2.5-flash" in preferred
    assert "imagen-3.0-generate-002" in preferred


def test_profile_cache_scope_no_profile(db_session):
    scope = mr._get_profile_cache_scope("openai", db_session, USER_ID)
    assert scope.startswith("no-profile")


def test_effective_profile_honors_active_setting(db_session):
    now = int(time.time() * 1000)
    p1 = ConfigProfile(
        id=generate_uuid(), user_id=USER_ID, name="A", provider_id="openai",
        api_key="k", protocol="openai", created_at=now, updated_at=now,
    )
    p2 = ConfigProfile(
        id=generate_uuid(), user_id=USER_ID, name="B", provider_id="openai",
        api_key="k", protocol="openai", created_at=now, updated_at=now + 1,
    )
    db_session.add_all([p1, p2])
    db_session.add(UserSettings(user_id=USER_ID, active_profile_id=p1.id))
    db_session.commit()

    eff = mr._get_effective_profile("openai", db_session, USER_ID)
    assert eff.id == p1.id  # active profile wins over recency

    # hint shortcut bypasses the UserSettings query
    eff_hint = mr._get_effective_profile(
        "openai", db_session, USER_ID, active_profile_id_hint=p2.id
    )
    assert eff_hint.id == p2.id
