from types import SimpleNamespace

from app.services.agent.workflow_engine.agent_resolution import (
    extract_model_version,
    get_default_video_model,
    is_candidate_for_agent_task,
    list_saved_model_ids,
    looks_like_video_generation_model,
    rank_model_for_agent_task,
    resolve_preferred_model_for_agent_task,
)


def _build_engine_with_profiles(*profiles: SimpleNamespace) -> SimpleNamespace:
    engine = SimpleNamespace(
        db=object(),
        llm_service=SimpleNamespace(user_id="user-1"),
        _saved_model_ids_cache={},
    )
    engine._get_workflow_user_id = lambda: "user-1"
    engine._get_user_profiles = lambda user_id: list(profiles)
    engine._list_saved_model_ids = lambda profile: list_saved_model_ids(engine, profile)
    engine._looks_like_video_generation_model = (
        lambda model_id: looks_like_video_generation_model(engine, model_id)
    )
    engine._is_candidate_for_agent_task = (
        lambda model_id, agent_task_type, preferred_mode="": is_candidate_for_agent_task(
            engine,
            model_id,
            agent_task_type,
            preferred_mode,
        )
    )
    engine._extract_model_version = lambda model_id: extract_model_version(engine, model_id)
    engine._rank_model_for_agent_task = (
        lambda model_id, agent_task_type, preferred_mode="": rank_model_for_agent_task(
            engine,
            model_id,
            agent_task_type,
            preferred_mode,
        )
    )
    engine._get_default_video_model = lambda provider_id: get_default_video_model(engine, provider_id)
    return engine


def test_resolve_preferred_video_model_prefers_veo31_preview_over_non_preview_saved_model() -> None:
    profile = SimpleNamespace(
        id="google-profile-1",
        provider_id="google",
        api_key="secret",
        updated_at=1,
        saved_models=[
            {"id": "veo-3.1-generate-001"},
            {"id": "veo-3.1-generate-preview"},
            {"id": "veo-3.1-fast-generate-preview"},
        ],
    )
    engine = _build_engine_with_profiles(profile)

    chosen = resolve_preferred_model_for_agent_task(
        engine,
        provider_id="google",
        requested_model="",
        agent_task_type="video-gen",
        preferred_mode="video-gen",
        preferred_profile_id="google-profile-1",
    )

    assert chosen == "veo-3.1-generate-preview"


def test_rank_video_models_prefers_veo31_preview_family() -> None:
    engine = _build_engine_with_profiles()

    preview_rank = rank_model_for_agent_task(engine, "veo-3.1-generate-preview", "video-gen")
    non_preview_rank = rank_model_for_agent_task(engine, "veo-3.1-generate-001", "video-gen")

    assert preview_rank < non_preview_rank
