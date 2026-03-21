from app.services.common.video_mode_contract import (
    apply_video_mode_runtime_overrides,
    resolve_runtime_mode_controls_schema,
)
from app.services.common.mode_controls_catalog import resolve_mode_controls


def test_google_video_contract_exposes_extension_duration_matrix_and_slots() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-preview")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="vertex_ai",
    )
    contract = runtime_schema["video_contract"]

    assert contract["supports"]["video_extension"] is True
    assert contract["supports"]["reference_images"] is True
    assert contract["supports"]["first_last_frame"] is True
    assert contract["supports"]["video_mask_image"] is False

    matrix = {
        item["base_seconds"]: item["options"]
        for item in contract["extension_duration_matrix"]
    }
    assert "8" in matrix
    assert matrix["8"][0]["total_seconds"] == 8
    assert matrix["8"][-1]["total_seconds"] == 148

    slot_map = {slot["name"]: slot for slot in contract["attachment_slots"]}
    assert slot_map["source_image"]["enabled"] is True
    assert slot_map["last_frame_image"]["enabled"] is True
    assert slot_map["reference_images"]["max_items"] == 3
    assert contract["field_policies"]["enhance_prompt"]["mandatory"] is True
    assert contract["field_policies"]["subtitle_mode"]["single_sidecar_format"] is True
    assert contract["field_policies"]["storyboard_prompt"]["deprecated_companion_fields"] == [
        "tracked_feature",
        "tracking_overlay_text",
    ]


def test_google_video_runtime_contract_strips_vertex_only_options_for_gemini_api() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-preview")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="gemini_api",
    )

    assert runtime_schema["runtime_api_mode"] == "gemini_api"
    assert "generate_audio" not in runtime_schema["param_options"]
    assert "person_generation" not in runtime_schema["param_options"]
    assert runtime_schema["constraints"]["supports_generate_audio"] is False
    assert runtime_schema["constraints"]["supports_person_generation"] is False
    assert runtime_schema["defaults"]["generate_audio"] is False
    assert runtime_schema["defaults"]["person_generation"] is None
    assert runtime_schema["video_contract"]["supports"]["generate_audio"] is False
    assert runtime_schema["video_contract"]["supports"]["person_generation"] is False


def test_runtime_schema_wrapper_returns_contract_for_google_video() -> None:
    schema = resolve_runtime_mode_controls_schema(
        provider="google",
        mode="video-gen",
        model_id="veo-2.0-generate-001",
    )

    assert schema is not None
    assert schema["runtime_api_mode"] == "gemini_api"
    assert schema["video_contract"]["supports"]["video_extension"] is False
    assert schema["video_contract"]["supports"]["video_mask_image"] is True
