from app.services.common.video_mode_contract import (
    extract_video_mode_attachment_params,
    merge_video_mode_attachment_params,
    normalize_video_generation_request_params,
    resolve_runtime_mode_controls_schema,
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


def test_tongyi_videoedit_treats_loose_image_with_source_video_as_reference_image() -> None:
    attachments = [
        {"mime_type": "video/mp4", "url": "https://example.test/source.mp4"},
        {"mime_type": "image/png", "url": "https://example.test/style.png"},
    ]

    params, extracted = merge_video_mode_attachment_params(
        method_name="generate_video",
        params={},
        attachments=attachments,
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-videoedit",
    )

    assert params["source_video"]["url"] == "https://example.test/source.mp4"
    assert params["reference_images"]["raw"][0]["url"] == "https://example.test/style.png"
    assert extracted["reference_images"]["raw"][0]["url"] == "https://example.test/style.png"
    assert "video_mask_image" not in params
    assert "video_mask_mode" not in params


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


def test_video_request_normalization_forces_enhance_prompt_and_audio_policy() -> None:
    params, meta = normalize_video_generation_request_params(
        provider="google",
        mode="video-gen",
        model_id="veo-3.1-generate-preview",
        params={
            "seconds": "8",
            "resolution": "720p",
            "enhance_prompt": False,
            "generate_audio": True,
        },
    )

    assert params["enhance_prompt"] is True
    assert params["generate_audio"] is False
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


def test_google_first_last_frame_request_derives_google_strategy_id() -> None:
    _params, meta = normalize_video_generation_request_params(
        provider="google",
        mode="video-gen",
        model_id="veo-3.1-generate-preview",
        params={
            "seconds": "8",
            "resolution": "720p",
            "source_image": {"url": "data:image/png;base64,start", "mime_type": "image/png"},
            "last_frame_image": {"url": "data:image/png;base64,end", "mime_type": "image/png"},
        },
    )

    assert meta["input_strategy"] == "first_last_frame"


def test_google_mask_edit_request_derives_google_strategy_id() -> None:
    _params, meta = normalize_video_generation_request_params(
        provider="google",
        mode="video-gen",
        model_id="veo-2.0-generate-001",
        params={
            "seconds": "8",
            "resolution": "720p",
            "source_video": {"url": "https://example.test/source.mp4"},
            "video_mask_image": {"url": "data:image/png;base64,mask", "mime_type": "image/png"},
        },
    )

    assert meta["input_strategy"] == "masked_video_edit"


def test_video_request_normalization_removes_image_count_fields() -> None:
    params, meta = normalize_video_generation_request_params(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-t2v",
        params={
            "seconds": "5",
            "resolution": "1080p",
            "number_of_images": 4,
            "num_images": 4,
            "n": 4,
        },
    )

    assert "number_of_images" not in params
    assert "num_images" not in params
    assert "n" not in params
    assert meta["input_strategy"] == "text_to_video"


def test_tongyi_i2v_controls_include_provider_specific_video_contract() -> None:
    schema = resolve_runtime_mode_controls_schema(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-i2v",
    )

    assert schema is not None
    contract = schema["video_contract"]
    assert contract["supports"]["first_last_frame"] is True
    assert contract["supports"]["video_continuation"] is True
    assert contract["supports"]["video_mask_image"] is False
    assert [strategy["id"] for strategy in contract["input_strategies"]] == [
        "first_frame_to_video",
        "first_last_frame_to_video",
        "video_continuation",
        "video_continuation_to_last_frame",
    ]
    assert {slot["name"] for slot in contract["attachment_slots"] if slot["enabled"]} == {
        "source_image",
        "last_frame_image",
        "source_video",
        "driving_audio",
    }


def test_tongyi_videoedit_controls_model_reference_based_edit_not_masked_edit() -> None:
    schema = resolve_runtime_mode_controls_schema(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-videoedit",
    )

    assert schema is not None
    contract = schema["video_contract"]
    assert contract["supports"]["video_edit"] is True
    assert contract["supports"]["video_mask_image"] is False
    assert [strategy["id"] for strategy in contract["input_strategies"]] == ["video_edit"]
    assert {slot["name"] for slot in contract["attachment_slots"] if slot["enabled"]} == {
        "source_video",
        "video_edit_reference_images",
    }


def test_tongyi_video_request_honors_explicit_input_strategy() -> None:
    params, meta = normalize_video_generation_request_params(
        provider="tongyi",
        mode="video-gen",
        model_id="wan2.7-i2v",
        params={
            "video_input_strategy": "video_continuation_to_last_frame",
            "source_video": {"url": "https://example.test/source.mp4"},
            "last_frame_image": {"url": "https://example.test/end.png"},
            "seconds": "5",
            "resolution": "1080p",
        },
    )

    assert params["video_input_strategy"] == "video_continuation_to_last_frame"
    assert meta["input_strategy"] == "video_continuation_to_last_frame"
    assert meta["runtime_api_mode"] == "dashscope"


def test_tongyi_video_request_rejects_unsupported_input_strategy() -> None:
    try:
        normalize_video_generation_request_params(
            provider="tongyi",
            mode="video-gen",
            model_id="wan2.7-t2v",
            params={
                "video_input_strategy": "video_edit",
                "seconds": "5",
                "resolution": "1080p",
            },
        )
    except ValueError as exc:
        assert "unsupported video_input_strategy" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for unsupported Tongyi video input strategy")


def test_tongyi_video_request_rejects_strategy_missing_required_media() -> None:
    try:
        normalize_video_generation_request_params(
            provider="tongyi",
            mode="video-gen",
            model_id="wan2.7-i2v",
            params={
                "video_input_strategy": "first_last_frame_to_video",
                "source_image": {"url": "https://example.test/start.png"},
                "seconds": "5",
                "resolution": "1080p",
            },
        )
    except ValueError as exc:
        message = str(exc).lower()
        assert "first_last_frame_to_video" in message
        assert "last_frame_image" in message
    else:
        raise AssertionError("Expected ValueError for missing last_frame_image")


def test_tongyi_i2v_request_without_media_is_rejected_before_provider_call() -> None:
    try:
        normalize_video_generation_request_params(
            provider="tongyi",
            mode="video-gen",
            model_id="wan2.7-i2v",
            params={
                "seconds": "5",
                "resolution": "1080p",
            },
        )
    except ValueError as exc:
        assert "requires one of" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing i2v media")
