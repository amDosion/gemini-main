from app.services.common.video_mode_contract import (
    extract_video_mode_attachment_params,
    merge_video_mode_attachment_params,
    normalize_video_generation_request_params,
)


def test_generate_video_normalizes_plain_images_into_source_and_reference_slots() -> None:
    attachments = [
        {"mime_type": "image/png", "url": "data:image/png;base64,one"},
        {"mime_type": "image/png", "url": "data:image/png;base64,two"},
        {"mime_type": "image/png", "url": "data:image/png;base64,three"},
    ]

    params, extracted = merge_video_mode_attachment_params(
        method_name="generate_video",
        params={},
        attachments=attachments,
    )

    assert extracted["source_image"]["url"].endswith(",one")
    assert params["source_image"]["url"].endswith(",one")
    assert len(params["reference_images"]["raw"]) == 2
    assert params["reference_images"]["raw"][0]["url"].endswith(",two")
    assert params["reference_images"]["raw"][1]["url"].endswith(",three")


def test_generate_video_honors_explicit_last_frame_role() -> None:
    attachments = [
        {"mime_type": "image/png", "url": "data:image/png;base64,start", "role": "start-frame"},
        {"mime_type": "image/png", "url": "data:image/png;base64,end", "role": "last-frame"},
    ]

    params = extract_video_mode_attachment_params(attachments)

    assert params["source_image"]["url"].endswith(",start")
    assert params["last_frame_image"]["url"].endswith(",end")


def test_generate_video_treats_loose_image_as_mask_when_source_video_exists() -> None:
    attachments = [
        {"mime_type": "video/mp4", "file_uri": "files/video123"},
        {"mime_type": "image/png", "url": "data:image/png;base64,maskless"},
    ]

    params, _ = merge_video_mode_attachment_params(
        method_name="generate_video",
        params={},
        attachments=attachments,
    )

    assert params["source_video"]["provider_file_name"] == "files/video123"
    assert params["video_mask_image"]["url"].endswith(",maskless")
    assert params["video_mask_mode"] == "REMOVE"


def test_delete_video_extracts_provider_asset_references_from_attachment() -> None:
    attachments = [
        {"mime_type": "application/octet-stream", "file_uri": "gs://bucket/demo.mp4"},
    ]

    params, _ = merge_video_mode_attachment_params(
        method_name="delete_video",
        params={},
        attachments=attachments,
    )

    assert params["gcs_uri"] == "gs://bucket/demo.mp4"


def test_video_request_normalization_forces_enhance_prompt_and_strips_runtime_unsupported_fields() -> None:
    params, meta = normalize_video_generation_request_params(
        provider="google",
        mode="video-gen",
        model_id="veo-3.1-generate-preview",
        params={
            "seconds": "8",
            "resolution": "720p",
            "enhance_prompt": False,
            "generate_audio": True,
            "person_generation": "allow_adult",
        },
    )

    assert params["enhance_prompt"] is True
    assert params["generate_audio"] is False
    assert "person_generation" not in params
    assert meta["runtime_api_mode"] == "gemini_api"


def test_video_request_normalization_rejects_extension_for_non_extension_model() -> None:
    try:
        normalize_video_generation_request_params(
            provider="google",
            mode="video-gen",
            model_id="veo-2.0-generate-001",
            params={
                "seconds": "8",
                "resolution": "720p",
                "video_extension_count": 1,
            },
        )
    except ValueError as exc:
        assert "not supported" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for unsupported Veo 2 video extension")


def test_video_request_normalization_prefers_explicit_storyboard_prompt_over_tracking_fields() -> None:
    params, meta = normalize_video_generation_request_params(
        provider="google",
        mode="video-gen",
        model_id="veo-3.1-generate-preview",
        params={
            "seconds": "8",
            "resolution": "720p",
            "storyboard_prompt": "Shot 1: close-up of the lace cuff. Shot 2: styling reveal.",
            "tracked_feature": "lace cuff",
            "tracking_overlay_text": "Double-Layer Lace",
            "source_image": {"url": "data:image/png;base64,abc", "mime_type": "image/png"},
        },
    )

    assert "tracked_feature" not in params
    assert "tracking_overlay_text" not in params
    assert meta["input_strategy"] == "image_to_video"
