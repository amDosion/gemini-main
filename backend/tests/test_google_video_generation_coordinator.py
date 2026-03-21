from app.services.common.video_mode_contract import apply_video_mode_runtime_overrides
from app.services.common.mode_controls_catalog import resolve_mode_controls


def test_google_video_contract_for_veo31_keeps_4k_and_official_extension_constraints() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-001")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="vertex_ai",
    )

    resolution_values = [item["value"] for item in runtime_schema["resolution_tiers"]]
    assert resolution_values == ["720p", "1080p", "4k"]

    extension_constraints = runtime_schema["video_contract"]["extension_constraints"]
    assert extension_constraints["added_seconds"] == 7
    assert extension_constraints["max_extension_count"] == 20
    assert extension_constraints["max_source_video_seconds"] == 141
    assert extension_constraints["max_output_video_seconds"] == 148
    assert extension_constraints["require_duration_seconds"] == ["8"]
    assert extension_constraints["require_resolution_values"] == ["720p"]


def test_google_video_contract_duration_matrix_filters_totals_above_output_limit() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-3.1-generate-preview")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="vertex_ai",
    )

    matrix = runtime_schema["video_contract"]["extension_duration_matrix"]
    eight_second_plan = next(item for item in matrix if item["base_seconds"] == "8")
    assert eight_second_plan["options"][-1]["count"] == 20
    assert eight_second_plan["options"][-1]["total_seconds"] == 148

    four_second_plan = next(item for item in matrix if item["base_seconds"] == "4")
    assert four_second_plan["options"][-1]["total_seconds"] <= 148


def test_google_video_contract_for_veo2_disables_extension_but_keeps_mask_edit_path() -> None:
    schema = resolve_mode_controls("google", "video-gen", "veo-2.0-generate-001")
    assert schema is not None

    runtime_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="video-gen",
        runtime_api_mode="gemini_api",
    )
    contract = runtime_schema["video_contract"]

    assert contract["supports"]["video_extension"] is False
    assert contract["supports"]["video_mask_image"] is True
