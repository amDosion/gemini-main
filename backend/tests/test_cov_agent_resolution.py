"""
Genuine behavior tests for app.services.agent.workflow_engine.agent_resolution.

These helpers are extracted from WorkflowEngine and operate on an ``engine``
object that exposes ``_``-prefixed methods (the engine wraps each module-level
function). We build a faithful fake engine that wires every cross-call back to
the real module function, plus a real in-memory SQLite session with the real
ConfigProfile / UserSettings models for the DB-touching resolvers.

Only external boundaries are mocked (provider factory / credentials resolver /
ADK SDK). All resolution, ranking, classification and validation logic is the
real system under test.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.db_models import ConfigProfile, UserSettings
import app.services.agent.workflow_engine.agent_resolution as ar


# ---------------------------------------------------------------------------
# In-memory DB
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_profile(
    session,
    *,
    profile_id: str,
    user_id: str = "user-1",
    provider_id: str = "google",
    api_key: str = "secret",
    saved_models: Any = None,
    updated_at: int = 1000,
    name: str = "p",
) -> ConfigProfile:
    profile = ConfigProfile(
        id=profile_id,
        user_id=user_id,
        name=name,
        provider_id=provider_id,
        api_key=api_key,
        protocol="google",
        saved_models=saved_models if saved_models is not None else [],
        created_at=1,
        updated_at=updated_at,
    )
    session.add(profile)
    session.commit()
    return profile


# ---------------------------------------------------------------------------
# Fake engine that maps every `engine._xxx` call to the real module function.
# ---------------------------------------------------------------------------

def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _to_float(value: Any, default: float = 0.0) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0, minimum=None, maximum=None) -> Optional[int]:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def make_engine(db: Any = None, user_id: str = "user-1") -> SimpleNamespace:
    """Build an engine whose `_xxx` methods delegate to the real module funcs."""
    engine = SimpleNamespace()
    engine.db = db
    engine.llm_service = SimpleNamespace(user_id=user_id)
    engine._profiles_cache = {}
    engine._saved_model_ids_cache = {}

    engine._to_bool = _to_bool
    engine._to_float = _to_float
    engine._to_int = _to_int

    # Bind every module-level helper as an `_`-prefixed bound method.
    def bind(name: str, func):
        setattr(engine, name, lambda *a, _f=func, **kw: _f(engine, *a, **kw))

    bind("_get_workflow_user_id", ar.get_workflow_user_id)
    bind("_extract_agent_card_defaults", ar.extract_agent_card_defaults)
    bind("_extract_agent_llm_defaults", ar.extract_agent_llm_defaults)
    bind("_resolve_llm_default_value", ar.resolve_llm_default_value)
    bind("_is_active_inline_provider_token", ar.is_active_inline_provider_token)
    bind("_is_auto_inline_model_token", ar.is_auto_inline_model_token)
    bind("_should_resolve_inline_from_active_profile", ar.should_resolve_inline_from_active_profile)
    bind("_get_user_profiles", ar.get_user_profiles)
    bind("_generate_workflow_frontend_session_id", ar.generate_workflow_frontend_session_id)
    bind("_extract_model_version", ar.extract_model_version)
    bind("_looks_like_google_chat_image_edit_model", ar.looks_like_google_chat_image_edit_model)
    bind("_looks_like_image_generation_model", ar.looks_like_image_generation_model)
    bind("_looks_like_image_edit_model", ar.looks_like_image_edit_model)
    bind("_looks_like_video_generation_model", ar.looks_like_video_generation_model)
    bind("_looks_like_audio_generation_model", ar.looks_like_audio_generation_model)
    bind("_looks_like_vision_understand_model", ar.looks_like_vision_understand_model)
    bind("_looks_like_text_model", ar.looks_like_text_model)
    bind("_is_candidate_for_agent_task", ar.is_candidate_for_agent_task)
    bind("_rank_model_for_agent_task", ar.rank_model_for_agent_task)
    bind("_list_saved_model_ids", ar.list_saved_model_ids)
    bind("_get_default_image_model", ar.get_default_image_model)
    bind("_get_default_video_model", ar.get_default_video_model)
    bind("_get_default_audio_model", ar.get_default_audio_model)
    bind("_select_image_model", ar.select_image_model)
    bind("_default_text_model_for_provider", ar.default_text_model_for_provider)
    bind("_select_text_chat_target", ar.select_text_chat_target)
    bind("_rank_provider_profiles_for_tool", ar.rank_provider_profiles_for_tool)
    bind("_select_provider_profile_for_tool", ar.select_provider_profile_for_tool)
    bind("_is_usable_requested_image_model", ar.is_usable_requested_image_model)
    bind("_resolve_image_model_for_profile", ar.resolve_image_model_for_profile)
    bind("_list_candidate_image_models", ar.list_candidate_image_models)
    bind("_select_profile_target_for_agent_task", ar.select_profile_target_for_agent_task)
    bind("_resolve_preferred_model_for_agent_task", ar.resolve_preferred_model_for_agent_task)
    bind("_build_inline_agent", ar.build_inline_agent)
    bind("_should_use_adk_runtime", ar.should_use_adk_runtime)
    return engine


# ---------------------------------------------------------------------------
# Trivial accessors / parsers
# ---------------------------------------------------------------------------

def test_get_workflow_user_id_strips_and_stringifies() -> None:
    engine = make_engine(user_id="  user-x  ")
    assert ar.get_workflow_user_id(engine) == "user-x"


def test_get_workflow_user_id_empty() -> None:
    engine = make_engine(user_id="")
    assert ar.get_workflow_user_id(engine) == ""


def test_extract_agent_card_defaults_parses_defaults() -> None:
    engine = make_engine()
    agent = SimpleNamespace(
        id="a1",
        agent_card_json=json.dumps({"defaults": {"llm": {"profileId": "p1"}}}),
    )
    defaults = ar.extract_agent_card_defaults(engine, agent)
    assert defaults == {"llm": {"profileId": "p1"}}


def test_extract_agent_card_defaults_missing_returns_empty() -> None:
    engine = make_engine()
    assert ar.extract_agent_card_defaults(engine, SimpleNamespace(agent_card_json=None)) == {}


def test_extract_agent_card_defaults_invalid_json_logs_and_returns_empty() -> None:
    engine = make_engine()
    agent = SimpleNamespace(id="bad", agent_card_json="{not json")
    assert ar.extract_agent_card_defaults(engine, agent) == {}


def test_extract_agent_card_defaults_non_dict_defaults() -> None:
    engine = make_engine()
    agent = SimpleNamespace(id="a", agent_card_json=json.dumps({"defaults": [1, 2]}))
    assert ar.extract_agent_card_defaults(engine, agent) == {}


def test_extract_agent_llm_defaults_present_and_absent() -> None:
    engine = make_engine()
    assert ar.extract_agent_llm_defaults(engine, {"llm": {"a": 1}}) == {"a": 1}
    assert ar.extract_agent_llm_defaults(engine, {"llm": "nope"}) == {}
    assert ar.extract_agent_llm_defaults(engine, "not-a-dict") == {}


def test_resolve_llm_default_value_skips_none_and_blank() -> None:
    engine = make_engine()
    payload = {"a": None, "b": "  ", "c": "value", "d": 0}
    assert ar.resolve_llm_default_value(engine, payload, "a", "b", "c") == "value"
    # First non-blank wins; 0 is a valid value (not None/blank-string)
    assert ar.resolve_llm_default_value(engine, payload, "d") == 0
    assert ar.resolve_llm_default_value(engine, payload, "missing") is None


# ---------------------------------------------------------------------------
# invoke_llm_chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoke_llm_chat_passes_profile_when_supported() -> None:
    captured: Dict[str, Any] = {}

    async def chat(*, provider_id, model_id, messages, system_prompt, temperature, max_tokens, profile_id=""):
        captured.update(locals())
        return {"text": "ok"}

    engine = make_engine()
    engine.llm_service = SimpleNamespace(chat=chat)
    result = await ar.invoke_llm_chat(
        engine,
        provider_id="google",
        model_id="gemini-2.5-flash",
        messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
        temperature=0.5,
        max_tokens=100,
        profile_id="prof-1",
    )
    assert result == {"text": "ok"}
    assert captured["profile_id"] == "prof-1"


@pytest.mark.asyncio
async def test_invoke_llm_chat_passes_profile_via_var_keyword() -> None:
    captured: Dict[str, Any] = {}

    async def chat(*, provider_id, model_id, messages, system_prompt, temperature, max_tokens, **kwargs):
        captured.update(kwargs)
        return {"text": "ok"}

    engine = make_engine()
    engine.llm_service = SimpleNamespace(chat=chat)
    await ar.invoke_llm_chat(
        engine,
        provider_id="g",
        model_id="m",
        messages=[],
        system_prompt="",
        temperature=0.1,
        max_tokens=1,
        profile_id="prof-2",
    )
    assert captured["profile_id"] == "prof-2"


@pytest.mark.asyncio
async def test_invoke_llm_chat_omits_profile_when_unsupported() -> None:
    captured: Dict[str, Any] = {}

    async def chat(*, provider_id, model_id, messages, system_prompt, temperature, max_tokens):
        captured["called"] = True
        return {"ok": True}

    engine = make_engine()
    engine.llm_service = SimpleNamespace(chat=chat)
    result = await ar.invoke_llm_chat(
        engine,
        provider_id="g",
        model_id="m",
        messages=[],
        system_prompt="",
        temperature=0.1,
        max_tokens=1,
        profile_id="prof-1",
    )
    assert result == {"ok": True}
    assert captured["called"] is True


@pytest.mark.asyncio
async def test_invoke_llm_chat_missing_chat_raises() -> None:
    engine = make_engine()
    engine.llm_service = SimpleNamespace(chat=None)
    with pytest.raises(ValueError, match="chat is not available"):
        await ar.invoke_llm_chat(
            engine,
            provider_id="g",
            model_id="m",
            messages=[],
            system_prompt="",
            temperature=0.1,
            max_tokens=1,
        )


# ---------------------------------------------------------------------------
# create_provider_service (the engine-level shim around _create_tool_provider_service)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_provider_service_no_profile() -> None:
    calls: List[Any] = []

    async def creator(provider_id):
        calls.append(provider_id)
        return SimpleNamespace(provider=provider_id)

    engine = make_engine()
    engine._create_tool_provider_service = creator
    svc = await ar.create_provider_service(engine, "openai")
    assert svc.provider == "openai"
    assert calls == ["openai"]


@pytest.mark.asyncio
async def test_create_provider_service_with_profile_kwarg() -> None:
    captured: Dict[str, Any] = {}

    async def creator(provider_id, profile_id=""):
        captured.update({"provider_id": provider_id, "profile_id": profile_id})
        return SimpleNamespace()

    engine = make_engine()
    engine._create_tool_provider_service = creator
    await ar.create_provider_service(engine, "google", profile_id="p1")
    assert captured == {"provider_id": "google", "profile_id": "p1"}


@pytest.mark.asyncio
async def test_create_provider_service_missing_creator_raises() -> None:
    engine = make_engine()
    engine._create_tool_provider_service = None
    with pytest.raises(ValueError, match="not available"):
        await ar.create_provider_service(engine, "g")


@pytest.mark.asyncio
async def test_create_provider_service_var_keyword_passes_profile() -> None:
    captured: Dict[str, Any] = {}

    async def creator(provider_id, **kwargs):
        captured.update(provider_id=provider_id, **kwargs)
        return SimpleNamespace()

    engine = make_engine()
    engine._create_tool_provider_service = creator
    await ar.create_provider_service(engine, "google", profile_id="pX")
    assert captured == {"provider_id": "google", "profile_id": "pX"}


@pytest.mark.asyncio
async def test_create_provider_service_signature_inspection_failure_falls_back() -> None:
    # A builtin-like callable whose signature can't be introspected forces the
    # except branch; the profile-less call path is then used.
    calls: List[Any] = []

    class Creator:
        def __call__(self, provider_id, profile_id=""):
            calls.append((provider_id, profile_id))

            async def _coro():
                return SimpleNamespace()

            return _coro()

    creator = Creator()
    engine = make_engine()
    engine._create_tool_provider_service = creator
    await ar.create_provider_service(engine, "google", profile_id="pX")
    assert calls and calls[0][0] in ("google",)


# ---------------------------------------------------------------------------
# should_resolve_inline_from_active_profile
# ---------------------------------------------------------------------------

def test_should_resolve_inline_explicit_flag() -> None:
    engine = make_engine()
    assert ar.should_resolve_inline_from_active_profile(
        engine,
        node_data={"inlineUseActiveProfile": True},
        inline_provider_id="openai",
        inline_model_id="gpt-4o",
    ) is True


def test_should_resolve_inline_via_tokens() -> None:
    engine = make_engine()
    assert ar.should_resolve_inline_from_active_profile(
        engine,
        node_data={},
        inline_provider_id="__active__",
        inline_model_id="__auto__",
    ) is True


def test_should_resolve_inline_false_with_concrete_values() -> None:
    engine = make_engine()
    assert ar.should_resolve_inline_from_active_profile(
        engine,
        node_data={},
        inline_provider_id="openai",
        inline_model_id="gpt-4o",
    ) is False


# ---------------------------------------------------------------------------
# get_user_profiles (DB + cache)
# ---------------------------------------------------------------------------

def test_get_user_profiles_queries_and_caches(db_session) -> None:
    _make_profile(db_session, profile_id="p1")
    engine = make_engine(db=db_session)
    profiles = ar.get_user_profiles(engine, "user-1")
    assert [p.id for p in profiles] == ["p1"]
    # Cached: deleting from DB should not change the cached result.
    db_session.query(ConfigProfile).delete()
    db_session.commit()
    cached = ar.get_user_profiles(engine, "user-1")
    assert [p.id for p in cached] == ["p1"]


def test_get_user_profiles_empty_user_or_no_db() -> None:
    assert ar.get_user_profiles(make_engine(db=object()), "") == []
    assert ar.get_user_profiles(make_engine(db=None), "user-1") == []


# ---------------------------------------------------------------------------
# generate_workflow_frontend_session_id
# ---------------------------------------------------------------------------

def test_generate_session_id_uses_user_hint() -> None:
    engine = make_engine(user_id="user-1")
    sid = ar.generate_workflow_frontend_session_id(engine)
    assert sid.startswith("wf-user-1-")


def test_generate_session_id_falls_back_to_workflow_for_empty_user() -> None:
    engine = make_engine(user_id="!!!")
    sid = ar.generate_workflow_frontend_session_id(engine)
    assert sid.startswith("wf-workflow-")


# ---------------------------------------------------------------------------
# extract_model_version
# ---------------------------------------------------------------------------

def test_extract_model_version_picks_max_number() -> None:
    engine = make_engine()
    assert ar.extract_model_version(engine, "gemini-2.5-flash") == 2.5
    assert ar.extract_model_version(engine, "gpt-4o") == 4.0
    assert ar.extract_model_version(engine, "no-numbers-here") == 0.0


# ---------------------------------------------------------------------------
# Model classification helpers
# ---------------------------------------------------------------------------

def test_looks_like_google_chat_image_edit_model() -> None:
    engine = make_engine()
    f = ar.looks_like_google_chat_image_edit_model
    assert f(engine, "gemini-2.5-flash-image") is True
    assert f(engine, "nano-banana") is True
    assert f(engine, "imagen-3.0-generate") is False  # imagen excluded
    assert f(engine, "gpt-4o") is False
    assert f(engine, "") is False


def test_looks_like_image_generation_model() -> None:
    engine = make_engine()
    f = ar.looks_like_image_generation_model
    assert f(engine, "imagen-3.0-generate-002") is True
    assert f(engine, "wan2.6-t2i") is True
    assert f(engine, "flux-pro") is True
    # excluded: video / edit-ish tokens
    assert f(engine, "veo-3.1") is False
    assert f(engine, "qwen-image-edit") is False
    assert f(engine, "gpt-4o") is False
    assert f(engine, "") is False


def test_looks_like_image_edit_model() -> None:
    engine = make_engine()
    f = ar.looks_like_image_edit_model
    assert f(engine, "gemini-2.5-flash-image") is True
    assert f(engine, "qwen-image-edit") is True
    assert f(engine, "imagen-3.0-capability-001") is True  # imagen w/o "generate"
    assert f(engine, "imagen-3.0-generate-002") is False
    assert f(engine, "") is False


def test_looks_like_video_generation_model() -> None:
    engine = make_engine()
    f = ar.looks_like_video_generation_model
    assert f(engine, "veo-3.1-generate-preview") is True
    assert f(engine, "sora-2") is True
    assert f(engine, "some-video-model") is True
    assert f(engine, "gemini-vision") is False  # vision excluded
    assert f(engine, "gpt-4o") is False
    assert f(engine, "") is False


def test_looks_like_audio_generation_model() -> None:
    engine = make_engine()
    f = ar.looks_like_audio_generation_model
    assert f(engine, "tts-1") is True
    assert f(engine, "gpt-4o-tts") is True
    assert f(engine, "openai-speech") is True
    assert f(engine, "whisper-1") is False  # ASR excluded
    assert f(engine, "gpt-4o") is False
    assert f(engine, "") is False


def test_looks_like_vision_understand_model() -> None:
    engine = make_engine()
    f = ar.looks_like_vision_understand_model
    assert f(engine, "gpt-4o") is True
    assert f(engine, "claude-3-opus") is True
    assert f(engine, "qwen2.5-vl-7b") is True
    assert f(engine, "gemini-2.5-flash-image") is True  # google chat image edit path
    assert f(engine, "imagen-3.0") is False
    assert f(engine, "veo-3.1") is False
    assert f(engine, "") is False


def test_looks_like_text_model() -> None:
    engine = make_engine()
    f = ar.looks_like_text_model
    assert f(engine, "gemini-2.5-flash") is True
    assert f(engine, "gpt-4o-mini") is True
    assert f(engine, "imagen-3.0") is False
    assert f(engine, "veo-3.1") is False
    assert f(engine, "tts-1") is False
    assert f(engine, "") is False


# ---------------------------------------------------------------------------
# is_candidate_for_agent_task — task routing
# ---------------------------------------------------------------------------

def test_is_candidate_for_agent_task_routes_by_task() -> None:
    engine = make_engine()
    f = ar.is_candidate_for_agent_task
    assert f(engine, "gpt-4o", "vision-understand") is True
    assert f(engine, "imagen-3.0-generate-002", "image-gen") is True
    assert f(engine, "qwen-image-edit", "image-edit") is True
    assert f(engine, "veo-3.1-generate-preview", "video-gen") is True
    assert f(engine, "tts-1", "audio-gen") is True
    assert f(engine, "gemini-2.5-flash", "chat") is True
    # unknown task falls back to text classification
    assert f(engine, "gemini-2.5-flash", "totally-unknown") is True


def test_is_candidate_image_chat_edit_mode() -> None:
    engine = make_engine()
    assert ar.is_candidate_for_agent_task(
        engine,
        "gemini-2.5-flash-image",
        "image_edit",
        preferred_mode="image_chat_edit",
    ) is True


# ---------------------------------------------------------------------------
# rank_model_for_agent_task — ranking semantics per task family
# ---------------------------------------------------------------------------

def test_rank_vision_prefers_google_chat_image_then_vl() -> None:
    engine = make_engine()
    r = ar.rank_model_for_agent_task
    google_chat = r(engine, "gemini-2.5-flash-image", "vision-understand")
    vl = r(engine, "qwen2.5-vl-7b", "vision-understand")
    none = r(engine, "random-model", "vision-understand")
    assert google_chat[0] == 0
    assert vl[0] == 1
    assert none[0] == 9


def test_rank_image_gen_family_order() -> None:
    engine = make_engine()
    r = ar.rank_model_for_agent_task
    assert r(engine, "gpt-image-2", "image-gen")[0] == 0
    assert r(engine, "gpt-image-1", "image-gen")[0] == 1
    assert r(engine, "imagen-3.0-generate-002", "image-gen")[0] == 2
    assert r(engine, "wanx-v1", "image-gen")[0] == 3
    assert r(engine, "some-image-thing", "image-gen")[0] == 4
    assert r(engine, "unrelated", "image-gen")[0] == 9


def test_rank_image_edit_chat_mode_top() -> None:
    engine = make_engine()
    top = ar.rank_model_for_agent_task(
        engine, "gemini-2.5-flash-image", "image-edit", preferred_mode="image-chat-edit"
    )
    assert top[0] == 0


def test_rank_video_gen_family_and_preview_reset() -> None:
    engine = make_engine()
    r = ar.rank_model_for_agent_task
    veo31_preview = r(engine, "veo-3.1-generate-preview", "video-gen")
    veo = r(engine, "veo-2.0", "video-gen")
    sora = r(engine, "sora-2", "video-gen")
    assert veo31_preview[0] == 0
    assert veo31_preview[1] == 0  # preview penalty reset for veo-3.1 preview
    assert veo[0] == 2
    assert sora[0] == 3


def test_rank_audio_gen_family() -> None:
    engine = make_engine()
    r = ar.rank_model_for_agent_task
    assert r(engine, "tts-1-hd", "audio-gen")[0] == 0
    assert r(engine, "tts-1", "audio-gen")[0] == 1
    assert r(engine, "azure-tts", "audio-gen")[0] == 2
    assert r(engine, "speech-x", "audio-gen")[0] == 3
    assert r(engine, "unknown", "audio-gen")[0] == 9


def test_rank_text_chat_gemini_families() -> None:
    engine = make_engine()
    r = ar.rank_model_for_agent_task
    assert r(engine, "gemini-2.5-pro", "chat")[0] == 0
    assert r(engine, "gemini-2.5-flash", "chat")[0] == 1
    assert r(engine, "gemini-2.0-flash", "chat")[0] == 2
    assert r(engine, "gemini-1.5", "chat")[0] == 3
    assert r(engine, "gpt-4o", "chat")[0] == 4


# ---------------------------------------------------------------------------
# list_saved_model_ids — parsing + caching
# ---------------------------------------------------------------------------

def test_list_saved_model_ids_handles_dicts_and_strings() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p1",
        updated_at=5,
        saved_models=[{"id": "m1"}, {"model_id": "m2"}, "m3", {"id": ""}, 123],
    )
    ids = ar.list_saved_model_ids(engine, profile)
    assert ids == ["m1", "m2", "m3", "123"]


def test_list_saved_model_ids_parses_json_string() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p1", updated_at=5, saved_models=json.dumps([{"id": "x"}]))
    assert ar.list_saved_model_ids(engine, profile) == ["x"]


def test_list_saved_model_ids_invalid_json_returns_empty() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p1", updated_at=5, saved_models="{bad")
    assert ar.list_saved_model_ids(engine, profile) == []


def test_list_saved_model_ids_uses_cache() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p1", updated_at=5, saved_models=[{"id": "first"}])
    assert ar.list_saved_model_ids(engine, profile) == ["first"]
    # Mutating saved_models but keeping same id+updated_at returns cached value.
    profile.saved_models = [{"id": "second"}]
    assert ar.list_saved_model_ids(engine, profile) == ["first"]


# ---------------------------------------------------------------------------
# Default model lookups
# ---------------------------------------------------------------------------

def test_get_default_image_model_generate_and_edit() -> None:
    engine = make_engine()
    g = ar.get_default_image_model
    assert g(engine, "google", "generate") == "imagen-3.0-generate-002"
    assert g(engine, "openai", "generate") == "gpt-image-2"
    assert g(engine, "tongyi", "generate") == "wan2.6-t2i"
    assert g(engine, "google", "edit") == "imagen-3.0-capability-001"
    assert g(engine, "dashscope", "edit") == "wan2.6-image"
    assert g(engine, "unknown", "generate") == ""


def test_get_default_video_and_audio_models() -> None:
    engine = make_engine()
    assert ar.get_default_video_model(engine, "google") == "veo-3.1-generate-preview"
    assert ar.get_default_video_model(engine, "openai") == "sora-2"
    assert ar.get_default_video_model(engine, "tongyi") == ""
    assert ar.get_default_audio_model(engine, "openai") == "tts-1"
    assert ar.get_default_audio_model(engine, "google") == ""


def test_default_text_model_for_provider() -> None:
    engine = make_engine()
    d = ar.default_text_model_for_provider
    assert d(engine, "google") == "gemini-2.5-flash"
    assert d(engine, "openai") == "gpt-4o-mini"
    assert d(engine, "tongyi") == "qwen-plus"
    assert d(engine, "ollama") == "llama3.1:8b"
    assert d(engine, "weird") == ""


# ---------------------------------------------------------------------------
# select_image_model
# ---------------------------------------------------------------------------

def test_select_image_model_matches_saved_then_default() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p1", updated_at=1, provider_id="google",
        saved_models=[{"id": "gemini-2.5-flash"}, {"id": "imagen-3.0-generate-002"}],
    )
    assert ar.select_image_model(engine, profile, "generate") == "imagen-3.0-generate-002"


def test_select_image_model_substring_fallback() -> None:
    engine = make_engine()
    # No strict-match generation model, but a model containing "image".
    profile = SimpleNamespace(
        id="p2", updated_at=1, provider_id="custom",
        saved_models=[{"id": "my-custom-image-thing-edit"}],
    )
    chosen = ar.select_image_model(engine, profile, "generate")
    assert "image" in chosen


def test_select_image_model_default_when_no_saved() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p3", updated_at=1, provider_id="google", saved_models=[])
    assert ar.select_image_model(engine, profile, "generate") == "imagen-3.0-generate-002"


# ---------------------------------------------------------------------------
# select_text_chat_target (DB-backed)
# ---------------------------------------------------------------------------

def test_select_text_chat_target_requested_model_wins(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    provider, model = ar.select_text_chat_target(engine, requested_model="custom-model")
    assert provider == "google"
    assert model == "custom-model"


def test_select_text_chat_target_picks_text_model(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "imagen-3.0-generate-002"}, {"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    provider, model = ar.select_text_chat_target(engine)
    assert provider == "google"
    assert model == "gemini-2.5-flash"


def test_select_text_chat_target_active_profile_first(db_session) -> None:
    _make_profile(db_session, profile_id="p-openai", provider_id="openai",
                  saved_models=[{"id": "gpt-4o-mini"}], updated_at=10)
    _make_profile(db_session, profile_id="p-google", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}], updated_at=20)
    db_session.add(UserSettings(user_id="user-1", active_profile_id="p-openai"))
    db_session.commit()
    engine = make_engine(db=db_session)
    provider, model = ar.select_text_chat_target(engine)
    assert provider == "openai"
    assert model == "gpt-4o-mini"


def test_select_text_chat_target_requested_profile_not_found(db_session) -> None:
    _make_profile(db_session, profile_id="p1", saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到 Profile 配置"):
        ar.select_text_chat_target(engine, requested_profile_id="nope")


def test_select_text_chat_target_requested_provider_not_found(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到 Provider 配置"):
        ar.select_text_chat_target(engine, requested_provider="openai")


def test_select_text_chat_target_no_user_raises(db_session) -> None:
    engine = make_engine(db=db_session, user_id="")
    with pytest.raises(ValueError, match="无法识别当前用户"):
        ar.select_text_chat_target(engine)


def test_select_text_chat_target_no_profiles_with_key(db_session) -> None:
    # Profile without api_key is filtered out -> no usable profile.
    p = ConfigProfile(id="p1", user_id="user-1", name="n", provider_id="google",
                      api_key="", protocol="google", saved_models=[], created_at=1, updated_at=1)
    db_session.add(p)
    db_session.commit()
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到可用 Provider API Key"):
        ar.select_text_chat_target(engine)


def test_select_text_chat_target_default_model_when_no_saved(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google", saved_models=[])
    engine = make_engine(db=db_session)
    provider, model = ar.select_text_chat_target(engine)
    assert provider == "google"
    assert model == "gemini-2.5-flash"  # default for google


# ---------------------------------------------------------------------------
# rank_provider_profiles_for_tool / select_provider_profile_for_tool (DB-backed)
# ---------------------------------------------------------------------------

def test_rank_provider_profiles_generate_scores_image_capable_first(db_session) -> None:
    _make_profile(db_session, profile_id="img", provider_id="custom",
                  saved_models=[{"id": "flux-pro"}], updated_at=5)
    _make_profile(db_session, profile_id="goog", provider_id="google",
                  saved_models=[], updated_at=5)
    engine = make_engine(db=db_session)
    ranked = ar.rank_provider_profiles_for_tool(engine, "", "generate")
    # The image-capable custom profile (score 0) ranks ahead of bare google (score 1).
    assert ranked[0].id == "img"


def test_select_provider_profile_for_tool_returns_top(db_session) -> None:
    _make_profile(db_session, profile_id="goog", provider_id="google", saved_models=[])
    engine = make_engine(db=db_session)
    chosen = ar.select_provider_profile_for_tool(engine, "google", "generate")
    assert chosen.id == "goog"


def test_rank_provider_profiles_requested_provider_filters(db_session) -> None:
    _make_profile(db_session, profile_id="goog", provider_id="google", saved_models=[])
    _make_profile(db_session, profile_id="oai", provider_id="openai", saved_models=[])
    engine = make_engine(db=db_session)
    ranked = ar.rank_provider_profiles_for_tool(engine, "openai", "generate")
    assert ranked[0].id == "oai"


def test_rank_provider_profiles_requested_profile_not_found(db_session) -> None:
    _make_profile(db_session, profile_id="goog", provider_id="google", saved_models=[])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到 Profile 配置"):
        ar.rank_provider_profiles_for_tool(engine, "", "generate", requested_profile_id="missing")


def test_rank_provider_profiles_profile_provider_mismatch(db_session) -> None:
    _make_profile(db_session, profile_id="goog", provider_id="google", saved_models=[])
    _make_profile(db_session, profile_id="oai", provider_id="openai", saved_models=[])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="不匹配 Provider"):
        ar.rank_provider_profiles_for_tool(
            engine, "openai", "generate", requested_profile_id="goog"
        )


def test_rank_provider_profiles_no_usable_provider(db_session) -> None:
    # weirdprovider scores 9 (no google/openai/tongyi prefix, no image models)
    # so the "no usable provider" path triggers.
    _make_profile(db_session, profile_id="x", provider_id="weirdprovider", saved_models=[])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="没有可用于图像工具"):
        ar.rank_provider_profiles_for_tool(engine, "", "generate")


def test_rank_provider_profiles_no_user(db_session) -> None:
    engine = make_engine(db=db_session, user_id="")
    with pytest.raises(ValueError, match="无法识别当前用户"):
        ar.rank_provider_profiles_for_tool(engine, "", "generate")


def test_rank_provider_profiles_requested_provider_with_preferred_profile(db_session) -> None:
    _make_profile(db_session, profile_id="g1", provider_id="google",
                  saved_models=[{"id": "imagen-3.0-generate-002"}], updated_at=5)
    _make_profile(db_session, profile_id="g2", provider_id="google",
                  saved_models=[{"id": "imagen-3.0-generate-002"}], updated_at=9)
    engine = make_engine(db=db_session)
    ranked = ar.rank_provider_profiles_for_tool(
        engine, "google", "generate", requested_profile_id="g1"
    )
    # Preferred profile is forced to the front despite g2 being newer.
    assert ranked[0].id == "g1"


def test_rank_provider_profiles_preferred_profile_unsupported_op(db_session) -> None:
    # Preferred profile scores 9 for the operation -> explicit error.
    _make_profile(db_session, profile_id="weird", provider_id="weirdprovider",
                  saved_models=[], updated_at=5)
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="不支持当前图像工具操作"):
        ar.rank_provider_profiles_for_tool(
            engine, "", "generate", requested_profile_id="weird"
        )


def test_rank_provider_profiles_no_provider_preferred_profile_first(db_session) -> None:
    _make_profile(db_session, profile_id="g-old", provider_id="google",
                  saved_models=[], updated_at=1)
    _make_profile(db_session, profile_id="g-pref", provider_id="google",
                  saved_models=[], updated_at=2)
    engine = make_engine(db=db_session)
    ranked = ar.rank_provider_profiles_for_tool(
        engine, "", "edit", requested_profile_id="g-pref"
    )
    assert ranked[0].id == "g-pref"


def test_rank_provider_profiles_edit_op_scoring(db_session) -> None:
    # edit op: a profile with an edit-capable model scores 0 over bare google (1).
    _make_profile(db_session, profile_id="edit", provider_id="custom",
                  saved_models=[{"id": "qwen-image-edit"}], updated_at=5)
    _make_profile(db_session, profile_id="goog", provider_id="google",
                  saved_models=[], updated_at=5)
    engine = make_engine(db=db_session)
    ranked = ar.rank_provider_profiles_for_tool(engine, "", "edit")
    assert ranked[0].id == "edit"


# ---------------------------------------------------------------------------
# is_usable_requested_image_model / resolve_image_model_for_profile
# ---------------------------------------------------------------------------

def test_is_usable_requested_image_model() -> None:
    engine = make_engine()
    f = ar.is_usable_requested_image_model
    assert f(engine, "imagen-3.0-generate-002", "generate") is True
    assert f(engine, "my-image-model", "generate") is True
    assert f(engine, "custom-edit-tool", "edit") is True
    assert f(engine, "gemini-2.5-flash", "generate") is False  # text model -> not usable
    assert f(engine, "", "generate") is False
    # Unknown, non-text -> permissive True
    assert f(engine, "veo-3.1", "generate") is True


def test_resolve_image_model_for_profile_prefers_requested() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p", updated_at=1, provider_id="google",
                              saved_models=[{"id": "imagen-3.0-generate-002"}])
    assert ar.resolve_image_model_for_profile(
        engine, profile, "generate", requested_model="flux-pro"
    ) == "flux-pro"


def test_resolve_image_model_for_profile_falls_back_to_select() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p", updated_at=1, provider_id="google",
                              saved_models=[{"id": "imagen-3.0-generate-002"}])
    # requested is a text model -> not usable -> select from saved
    assert ar.resolve_image_model_for_profile(
        engine, profile, "generate", requested_model="gemini-2.5-flash"
    ) == "imagen-3.0-generate-002"


# ---------------------------------------------------------------------------
# list_candidate_image_models
# ---------------------------------------------------------------------------

def test_list_candidate_image_models_dedup_and_rank() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p", updated_at=1, provider_id="google",
        saved_models=[{"id": "some-image"}, {"id": "imagen-3.0-generate-002"}],
    )
    candidates = ar.list_candidate_image_models(
        engine, profile, "generate", requested_model="imagen-3.0-generate-002"
    )
    # requested comes first; no duplicates; default appended.
    assert candidates[0] == "imagen-3.0-generate-002"
    assert len(candidates) == len(set(candidates))
    assert "imagen-3.0-generate-002" in candidates


def test_list_candidate_image_models_chat_edit_google() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p", updated_at=1, provider_id="google",
        saved_models=[{"id": "gemini-2.5-flash-image"}],
    )
    candidates = ar.list_candidate_image_models(
        engine, profile, "edit", preferred_mode="image-chat-edit"
    )
    assert candidates == ["gemini-2.5-flash-image"]


def test_list_candidate_image_models_edit_ranks_capability_first() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p", updated_at=1, provider_id="google",
        saved_models=[
            {"id": "some-image-edit"},
            {"id": "imagen-3.0-capability-001"},
            {"id": "wanx-edit"},
        ],
    )
    candidates = ar.list_candidate_image_models(engine, profile, "edit")
    # imagen capability (base 0) ranks ahead of wanx (2) and generic edit (3).
    assert candidates[0] == "imagen-3.0-capability-001"


def test_list_candidate_image_models_generate_ranks_imagen_generate_first() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p", updated_at=1, provider_id="google",
        saved_models=[
            {"id": "dall-e-3"},
            {"id": "imagen-3.0-generate-002"},
            {"id": "some-image"},
        ],
    )
    candidates = ar.list_candidate_image_models(engine, profile, "generate")
    assert candidates[0] == "imagen-3.0-generate-002"


def test_list_candidate_image_models_preview_penalty_demotes() -> None:
    engine = make_engine()
    profile = SimpleNamespace(
        id="p", updated_at=1, provider_id="custom",
        saved_models=[
            {"id": "imagen-3.0-generate-preview"},
            {"id": "imagen-3.0-generate-002"},
        ],
    )
    candidates = ar.list_candidate_image_models(engine, profile, "generate")
    # Preview variant gets a +3 penalty so the stable one ranks first.
    assert candidates.index("imagen-3.0-generate-002") < candidates.index(
        "imagen-3.0-generate-preview"
    )


def test_list_candidate_image_models_chat_edit_google_fallback() -> None:
    engine = make_engine()
    profile = SimpleNamespace(id="p", updated_at=1, provider_id="google", saved_models=[])
    candidates = ar.list_candidate_image_models(
        engine, profile, "edit", requested_model="custom", preferred_mode="image-chat-edit"
    )
    assert candidates[0] == "gemini-2.5-flash-image"


# ---------------------------------------------------------------------------
# resolve_preferred_model_for_agent_task (DB-backed)
# ---------------------------------------------------------------------------

def test_resolve_preferred_model_no_user_returns_requested() -> None:
    engine = make_engine(db=object(), user_id="")
    assert ar.resolve_preferred_model_for_agent_task(
        engine, "google", "  some-model  ", "chat"
    ) == "some-model"


def test_resolve_preferred_model_blank_provider_returns_requested(db_session) -> None:
    engine = make_engine(db=db_session)
    assert ar.resolve_preferred_model_for_agent_task(
        engine, "", "req-model", "chat"
    ) == "req-model"


def test_resolve_preferred_model_no_matching_profile_returns_requested(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    assert ar.resolve_preferred_model_for_agent_task(
        engine, "openai", "fallback-model", "chat"
    ) == "fallback-model"


def test_resolve_preferred_model_chat_picks_best_gemini(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-1.5-flash"}, {"id": "gemini-2.5-pro"}])
    engine = make_engine(db=db_session)
    chosen = ar.resolve_preferred_model_for_agent_task(engine, "google", "", "chat")
    assert chosen == "gemini-2.5-pro"


def test_resolve_preferred_model_no_candidates_uses_default_text(db_session) -> None:
    # Saved models are all image models -> no text candidate -> default text model.
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "imagen-3.0-generate-002"}])
    engine = make_engine(db=db_session)
    chosen = ar.resolve_preferred_model_for_agent_task(engine, "google", "", "chat")
    assert chosen == "gemini-2.5-flash"


def test_resolve_preferred_model_no_candidates_image_gen_default(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])  # no image-gen models
    engine = make_engine(db=db_session)
    chosen = ar.resolve_preferred_model_for_agent_task(engine, "google", "", "image-gen")
    assert chosen == "imagen-3.0-generate-002"


def test_resolve_preferred_model_no_candidates_image_chat_edit_default(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    chosen = ar.resolve_preferred_model_for_agent_task(
        engine, "google", "", "image-edit", preferred_mode="image-chat-edit"
    )
    assert chosen == "gemini-3.1-flash-image-preview"


def test_resolve_preferred_model_no_candidates_video_default(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    chosen = ar.resolve_preferred_model_for_agent_task(engine, "google", "", "video-gen")
    assert chosen == "veo-3.1-generate-preview"


def test_resolve_preferred_model_no_candidates_audio_default(db_session) -> None:
    _make_profile(db_session, profile_id="p1", provider_id="openai",
                  saved_models=[{"id": "gpt-4o"}])
    engine = make_engine(db=db_session)
    chosen = ar.resolve_preferred_model_for_agent_task(engine, "openai", "", "audio-gen")
    assert chosen == "tts-1"


# ---------------------------------------------------------------------------
# select_profile_target_for_agent_task (DB-backed, the big integration path)
# ---------------------------------------------------------------------------

def test_select_profile_target_chat_active_profile_first(db_session) -> None:
    _make_profile(db_session, profile_id="p-oai", provider_id="openai",
                  saved_models=[{"id": "gpt-4o-mini"}], updated_at=10)
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-pro"}], updated_at=5)
    db_session.add(UserSettings(user_id="user-1", active_profile_id="p-oai"))
    db_session.commit()
    engine = make_engine(db=db_session)
    provider, model, profile_id = ar.select_profile_target_for_agent_task(
        engine, agent_task_type="chat"
    )
    assert provider == "openai"
    assert profile_id == "p-oai"
    assert model == "gpt-4o-mini"


def test_select_profile_target_requested_provider(db_session) -> None:
    _make_profile(db_session, profile_id="p-oai", provider_id="openai",
                  saved_models=[{"id": "gpt-4o-mini"}])
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-pro"}])
    engine = make_engine(db=db_session)
    provider, model, profile_id = ar.select_profile_target_for_agent_task(
        engine, agent_task_type="chat", requested_provider="google"
    )
    assert provider == "google"
    assert profile_id == "p-goog"


def test_select_profile_target_requested_profile_first(db_session) -> None:
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    _make_profile(db_session, profile_id="p-oai", provider_id="openai",
                  saved_models=[{"id": "gpt-4o-mini"}])
    engine = make_engine(db=db_session)
    provider, model, profile_id = ar.select_profile_target_for_agent_task(
        engine, agent_task_type="chat", requested_profile_id="p-oai"
    )
    assert profile_id == "p-oai"
    assert provider == "openai"


def test_select_profile_target_no_user(db_session) -> None:
    engine = make_engine(db=db_session, user_id="")
    with pytest.raises(ValueError, match="无法识别当前用户"):
        ar.select_profile_target_for_agent_task(engine, agent_task_type="chat")


def test_select_profile_target_no_db() -> None:
    engine = make_engine(db=None)
    with pytest.raises(ValueError, match="缺少数据库上下文"):
        ar.select_profile_target_for_agent_task(engine, agent_task_type="chat")


def test_select_profile_target_no_profiles(db_session) -> None:
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到可用 Provider API Key"):
        ar.select_profile_target_for_agent_task(engine, agent_task_type="chat")


def test_select_profile_target_requested_provider_missing(db_session) -> None:
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到 Provider 配置"):
        ar.select_profile_target_for_agent_task(
            engine, agent_task_type="chat", requested_provider="openai"
        )


def test_select_profile_target_requested_profile_missing(db_session) -> None:
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到 Profile 配置"):
        ar.select_profile_target_for_agent_task(
            engine, agent_task_type="chat", requested_profile_id="nope"
        )


def test_select_profile_target_video_gen_falls_back_to_default(db_session) -> None:
    # Only a text model saved, but video-gen falls back to the default veo model
    # which IS a candidate, so resolution succeeds.
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-flash"}])
    engine = make_engine(db=db_session)
    provider, model, profile_id = ar.select_profile_target_for_agent_task(
        engine, agent_task_type="video-gen"
    )
    assert provider == "google"
    assert model == "veo-3.1-generate-preview"


def test_select_profile_target_requested_provider_no_task_model(db_session) -> None:
    # weirdprovider has no default model for video-gen -> resolve returns "" -> no candidate.
    _make_profile(db_session, profile_id="p-weird", provider_id="weirdprovider",
                  saved_models=[{"id": "weird-text-model"}])
    engine = make_engine(db=db_session)
    with pytest.raises(ValueError, match="未找到支持任务"):
        ar.select_profile_target_for_agent_task(
            engine, agent_task_type="video-gen", requested_provider="weirdprovider"
        )


# ---------------------------------------------------------------------------
# build_inline_agent
# ---------------------------------------------------------------------------

def test_build_inline_agent_concrete_values() -> None:
    engine = make_engine()
    agent = ar.build_inline_agent(
        engine,
        node_id="n1",
        node_data={
            "inlineProviderId": "openai",
            "inlineModelId": "gpt-4o",
            "inlineAgentName": "My Agent",
            "inlineSystemPrompt": "be helpful",
            "agentTemperature": 0.3,
            "agentMaxTokens": 2048,
            "agentTaskType": "chat",
            "inlineProfileId": "prof-9",
        },
    )
    assert agent is not None
    assert agent.id == "inline::n1"
    assert agent.provider_id == "openai"
    assert agent.model_id == "gpt-4o"
    assert agent.name == "My Agent"
    assert agent.temperature == 0.3
    assert agent.max_tokens == 2048
    card = json.loads(agent.agent_card_json)
    assert card["defaults"]["llm"]["profileId"] == "prof-9"
    assert card["defaults"]["defaultTaskType"] == "chat"


def test_build_inline_agent_missing_provider_returns_none() -> None:
    engine = make_engine()
    assert ar.build_inline_agent(
        engine, node_id="n1", node_data={"inlineModelId": "gpt-4o"}
    ) is None


def test_build_inline_agent_default_name() -> None:
    engine = make_engine()
    agent = ar.build_inline_agent(
        engine,
        node_id="node-7",
        node_data={"inlineProviderId": "openai", "inlineModelId": "gpt-4o"},
    )
    assert agent is not None
    assert agent.name == "Inline Agent node-7"


def test_build_inline_agent_resolves_from_active_profile(db_session) -> None:
    _make_profile(db_session, profile_id="p-goog", provider_id="google",
                  saved_models=[{"id": "gemini-2.5-pro"}])
    db_session.add(UserSettings(user_id="user-1", active_profile_id="p-goog"))
    db_session.commit()
    engine = make_engine(db=db_session)
    agent = ar.build_inline_agent(
        engine,
        node_id="n1",
        node_data={
            "inlineProviderId": "__active__",
            "inlineModelId": "__auto__",
            "agentTaskType": "chat",
        },
    )
    assert agent is not None
    assert agent.provider_id == "google"
    assert agent.model_id == "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# should_use_adk_runtime
# ---------------------------------------------------------------------------

def test_should_use_adk_runtime_true_for_google_adk_chat() -> None:
    engine = make_engine()
    agent = SimpleNamespace(agent_type="adk")
    assert ar.should_use_adk_runtime(engine, agent, "google", "chat") is True


def test_should_use_adk_runtime_false_for_non_google() -> None:
    engine = make_engine()
    agent = SimpleNamespace(agent_type="adk")
    assert ar.should_use_adk_runtime(engine, agent, "openai", "chat") is False


def test_should_use_adk_runtime_false_for_media_task() -> None:
    engine = make_engine()
    agent = SimpleNamespace(agent_type="adk")
    assert ar.should_use_adk_runtime(engine, agent, "google", "image-gen") is False


def test_should_use_adk_runtime_false_for_non_adk_agent_type() -> None:
    engine = make_engine()
    agent = SimpleNamespace(agent_type="standard")
    assert ar.should_use_adk_runtime(engine, agent, "google", "chat") is False


# ---------------------------------------------------------------------------
# create_tool_provider_service (mock external boundaries only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tool_provider_service_no_user(db_session) -> None:
    engine = make_engine(db=db_session, user_id="")
    with pytest.raises(ValueError, match="无法识别当前用户"):
        await ar.create_tool_provider_service(engine, "google")


@pytest.mark.asyncio
async def test_create_tool_provider_service_resolves_and_creates(db_session, monkeypatch) -> None:
    engine = make_engine(db=db_session)

    class FakeResolver:
        async def resolve(self, *, provider_id, db, user_id, profile_id):
            assert provider_id == "google"
            assert user_id == "user-1"
            return ("API_KEY", "https://base")

    created: Dict[str, Any] = {}

    def fake_create(*, provider, api_key, api_url, user_id, db):
        created.update(provider=provider, api_key=api_key, api_url=api_url, user_id=user_id)
        return SimpleNamespace(ok=True)

    monkeypatch.setattr(
        "app.services.llm.credentials_resolver.ProviderCredentialsResolver",
        FakeResolver,
    )
    monkeypatch.setattr(
        "app.services.common.provider_factory.ProviderFactory.create",
        staticmethod(fake_create),
    )

    svc = await ar.create_tool_provider_service(engine, "google", profile_id="p1")
    assert svc.ok is True
    assert created["provider"] == "google"
    assert created["api_key"] == "API_KEY"
    assert created["api_url"] == "https://base"


# ---------------------------------------------------------------------------
# run_adk_text_chat (mock external boundaries only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_adk_text_chat_no_user(db_session) -> None:
    engine = make_engine(db=db_session, user_id="")
    with pytest.raises(ValueError, match="user_id is empty"):
        await ar.run_adk_text_chat(
            engine,
            agent=SimpleNamespace(name="a", id="a1"),
            provider_id="google",
            model_id="gemini-2.5-flash",
            system_prompt="sys",
            prompt="hi",
            node_id="n1",
        )


@pytest.mark.asyncio
async def test_run_adk_text_chat_missing_api_key(db_session, monkeypatch) -> None:
    engine = make_engine(db=db_session)

    class FakeResolver:
        async def resolve(self, *, provider_id, db, user_id, profile_id):
            return ("", "")

    monkeypatch.setattr(
        "app.services.llm.credentials_resolver.ProviderCredentialsResolver",
        FakeResolver,
    )
    with pytest.raises(ValueError, match="missing API key"):
        await ar.run_adk_text_chat(
            engine,
            agent=SimpleNamespace(name="a", id="a1"),
            provider_id="google",
            model_id="gemini-2.5-flash",
            system_prompt="sys",
            prompt="hi",
            node_id="n1",
        )


@pytest.mark.asyncio
async def test_run_adk_text_chat_full_path(db_session, monkeypatch) -> None:
    engine = make_engine(db=db_session)

    class FakeResolver:
        async def resolve(self, *, provider_id, db, user_id, profile_id):
            return ("KEY", "")

    class FakeADKAgent:
        def __init__(self, **kwargs):
            self.is_available = True

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        async def run_once(self, *, user_id, session_id, input_data, google_api_key):
            return {"text": "adk-response"}

    monkeypatch.setattr(
        "app.services.llm.credentials_resolver.ProviderCredentialsResolver",
        FakeResolver,
    )
    monkeypatch.setattr("app.services.gemini.agent.adk_agent.ADKAgent", FakeADKAgent)
    monkeypatch.setattr("app.services.gemini.agent.adk_runner.ADKRunner", FakeRunner)
    monkeypatch.setattr(
        "app.services.agent.adk_builtin_tools.build_adk_builtin_tools",
        lambda: [],
    )

    result = await ar.run_adk_text_chat(
        engine,
        agent=SimpleNamespace(name="ADK", id="a1"),
        provider_id="google",
        model_id="gemini-2.5-flash",
        system_prompt="sys",
        prompt="hi",
        node_id="node-1",
    )
    assert result["text"] == "adk-response"
    assert "session_id" in result


@pytest.mark.asyncio
async def test_run_adk_text_chat_sdk_unavailable(db_session, monkeypatch) -> None:
    engine = make_engine(db=db_session)

    class FakeResolver:
        async def resolve(self, *, provider_id, db, user_id, profile_id):
            return ("KEY", "")

    class FakeADKAgent:
        def __init__(self, **kwargs):
            self.is_available = False

    monkeypatch.setattr(
        "app.services.llm.credentials_resolver.ProviderCredentialsResolver",
        FakeResolver,
    )
    monkeypatch.setattr("app.services.gemini.agent.adk_agent.ADKAgent", FakeADKAgent)
    monkeypatch.setattr(
        "app.services.agent.adk_builtin_tools.build_adk_builtin_tools",
        lambda: [],
    )
    with pytest.raises(RuntimeError, match="google.adk SDK is not available"):
        await ar.run_adk_text_chat(
            engine,
            agent=SimpleNamespace(name="ADK", id="a1"),
            provider_id="google",
            model_id="gemini-2.5-flash",
            system_prompt="sys",
            prompt="hi",
            node_id="node-1",
        )
