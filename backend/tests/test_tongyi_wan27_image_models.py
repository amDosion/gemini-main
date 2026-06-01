import pytest

from app.routers.models.models import (
    _apply_hidden_model_filter,
    _merge_tongyi_static_media_models,
    filter_models_by_mode,
)
from app.services.common.mode_controls_catalog import resolve_mode_controls
from app.services.common.model_capabilities import build_model_config
from app.services.tongyi.image_edit import ImageEditOptions, ImageEditService
from app.services.tongyi.image_generation import ImageGenerationRequest, ImageGenerationService


def _ids_for_mode(model_ids: list[str], mode: str) -> set[str]:
    models = [build_model_config("tongyi", model_id) for model_id in model_ids]
    return {model.id for model in filter_models_by_mode(models, mode)}


def test_tongyi_latest_image_models_are_exposed_to_the_right_modes() -> None:
    model_ids = [
        "qwen-max",
        "qwen-image-2.0",
        "qwen-image-2.0-pro",
        "qwen-image-max",
        "qwen-image-edit-plus",
        "wan2.7-image",
        "wan2.7-image-pro",
        "z-image-turbo",
    ]

    image_gen_ids = _ids_for_mode(model_ids, "image-gen")
    image_edit_ids = _ids_for_mode(model_ids, "image-chat-edit")
    chat_ids = _ids_for_mode(model_ids, "chat")

    assert "qwen-image-2.0" in image_gen_ids
    assert "qwen-image-2.0-pro" in image_gen_ids
    assert "qwen-image-max" in image_gen_ids
    assert "wan2.7-image" in image_gen_ids
    assert "wan2.7-image-pro" in image_gen_ids
    assert "z-image-turbo" in image_gen_ids
    assert "qwen-image-edit-plus" not in image_gen_ids

    assert "qwen-image-2.0" in image_edit_ids
    assert "qwen-image-2.0-pro" in image_edit_ids
    assert "qwen-image-edit-plus" in image_edit_ids
    assert "wan2.7-image" in image_edit_ids
    assert "wan2.7-image-pro" in image_edit_ids
    assert "qwen-image-max" not in image_edit_ids
    assert "z-image-turbo" not in image_edit_ids

    assert "qwen-image-2.0" not in chat_ids
    assert "qwen-image-edit-plus" not in chat_ids
    assert "wan2.7-image" not in chat_ids


def test_tongyi_image_edit_surface_modes_do_not_leak_video_or_vl_models() -> None:
    model_ids = [
        "qwen-image-2.0-pro",
        "qwen-image-edit-plus",
        "qwen-vl-max",
        "wan2.7-image",
        "wan2.7-t2v",
        "wan2.7-i2v",
        "qwen-tts",
        "image-out-painting",
        "aitryon-plus",
    ]

    edit_surface_modes = [
        "image-chat-edit",
        "image-inpainting",
        "image-background-edit",
        "image-recontext",
        "image-mask-edit",
    ]
    for mode in edit_surface_modes:
        ids = _ids_for_mode(model_ids, mode)
        assert "qwen-image-2.0-pro" in ids
        assert "qwen-image-edit-plus" in ids
        assert "wan2.7-image" in ids
        assert "qwen-vl-max" not in ids
        assert "wan2.7-t2v" not in ids
        assert "wan2.7-i2v" not in ids
        assert "qwen-tts" not in ids
        assert "image-out-painting" not in ids
        assert "aitryon-plus" not in ids

    assert _ids_for_mode(model_ids, "image-outpainting") == {"image-out-painting"}
    assert _ids_for_mode(model_ids, "virtual-try-on") == {"aitryon-plus"}
    assert _ids_for_mode(model_ids, "audio-gen") == {"qwen-tts"}


def test_hidden_model_filter_can_be_bypassed_for_utility_model_pools() -> None:
    models = [
        build_model_config("tongyi", "qwen-vl-max-latest"),
        build_model_config("tongyi", "wan2.7-image-pro"),
    ]

    visible_models = _apply_hidden_model_filter(
        models,
        hidden_ids={"qwen-vl-max-latest"},
        include_hidden=False,
    )
    utility_models = _apply_hidden_model_filter(
        models,
        hidden_ids={"qwen-vl-max-latest"},
        include_hidden=True,
    )

    assert [model.id for model in visible_models] == ["wan2.7-image-pro"]
    assert [model.id for model in utility_models] == [
        "qwen-vl-max-latest",
        "wan2.7-image-pro",
    ]


def test_tongyi_static_media_catalog_is_merged_before_image_mode_filtering() -> None:
    profile_models = [build_model_config("tongyi", "z-image-turbo")]
    merged = _merge_tongyi_static_media_models("tongyi", profile_models)

    image_gen_ids = {model.id for model in filter_models_by_mode(merged, "image-gen")}

    assert "z-image-turbo" in image_gen_ids
    assert "wan2.7-image" in image_gen_ids
    assert "wan2.7-image-pro" in image_gen_ids
    assert "image-out-painting" in {model.id for model in filter_models_by_mode(merged, "image-outpainting")}
    assert "aitryon-plus" in {model.id for model in filter_models_by_mode(merged, "virtual-try-on")}
    assert "qwen-tts" in {model.id for model in filter_models_by_mode(merged, "audio-gen")}


def test_tongyi_wan27_generation_and_edit_controls_have_distinct_resolution_rules() -> None:
    gen_pro = resolve_mode_controls("tongyi", "image-gen", "wan2.7-image-pro")
    gen_fast = resolve_mode_controls("tongyi", "image-gen", "wan2.7-image")
    qwen_gen = resolve_mode_controls("tongyi", "image-gen", "qwen-image-2.0-pro")
    qwen_edit = resolve_mode_controls("tongyi", "image-chat-edit", "qwen-image-edit-plus")
    edit_pro = resolve_mode_controls("tongyi", "image-chat-edit", "wan2.7-image-pro")

    assert gen_pro is not None
    assert gen_fast is not None
    assert qwen_gen is not None
    assert qwen_edit is not None
    assert edit_pro is not None

    assert [tier["value"] for tier in gen_pro["resolution_tiers"]] == ["1K", "2K", "4K"]
    assert [tier["value"] for tier in gen_fast["resolution_tiers"]] == ["1K", "2K"]
    assert [tier["value"] for tier in edit_pro["resolution_tiers"]] == ["1K", "2K"]
    assert gen_pro["constraints"]["max_image_count"] == 12
    assert gen_fast["constraints"]["max_image_count"] == 12
    assert gen_pro["defaults"]["enable_sequential"] is False
    assert qwen_gen["constraints"]["max_image_count"] == 6
    assert qwen_edit["constraints"]["max_image_count"] == 6
    assert gen_pro["defaults"]["thinking_mode"] is True
    assert set(gen_pro["constraints"]["unsupported_params"]) == {
        "negative_prompt",
        "prompt_extend",
        "add_magic_suffix",
        "style",
    }
    assert set(edit_pro["constraints"]["unsupported_params"]) == {
        "negative_prompt",
        "prompt_extend",
        "add_magic_suffix",
        "style",
        "thinking_mode",
    }
    assert "thinking_mode" not in edit_pro["defaults"]
    assert "thinking_mode" not in edit_pro.get("param_options", {})


class _PayloadCapturingWan27GenerationService(ImageGenerationService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.endpoint = ""
        self.payload = {}

    async def _call_api(self, endpoint: str, payload: dict) -> dict:
        self.endpoint = endpoint
        self.payload = payload
        return {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.test/wan27-generated.png"}
                            ]
                        }
                    }
                ]
            }
        }


class _PayloadCapturingWan27EditService(ImageEditService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.endpoint = ""
        self.payload = {}

    async def process_reference_image(self, image_url: str, model: str) -> str:
        return "oss://example/source.png"

    async def call_api(self, endpoint: str, payload: dict, use_oss_resolve: bool = True) -> dict:
        self.endpoint = endpoint
        self.payload = payload
        return {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.test/wan27-edited.png"}
                            ]
                        }
                    }
                ]
            }
        }


@pytest.mark.asyncio
async def test_tongyi_wan27_text_to_image_uses_multimodal_generation_payload() -> None:
    service = _PayloadCapturingWan27GenerationService()

    results = await service.generate(
        ImageGenerationRequest(
            model_id="wan2.7-image-pro",
            prompt="一间现代客厅",
            aspect_ratio="1:1",
            resolution="4K",
            num_images=1,
            negative_prompt="no text",
            seed=123,
            thinking_mode=True,
        )
    )

    assert results[0].url == "https://example.test/wan27-generated.png"
    assert service.endpoint.endswith("/api/v1/services/aigc/multimodal-generation/generation")
    assert service.payload["model"] == "wan2.7-image-pro"
    assert service.payload["input"]["messages"][0]["content"] == [{"text": "一间现代客厅"}]
    assert service.payload["parameters"] == {
        "size": "4K",
        "n": 1,
        "watermark": False,
        "thinking_mode": True,
        "seed": 123,
    }


@pytest.mark.asyncio
async def test_tongyi_wan27_text_to_image_caps_standard_count_and_allows_sequential_count() -> None:
    service = _PayloadCapturingWan27GenerationService()

    await service.generate(
        ImageGenerationRequest(
            model_id="wan2.7-image-pro",
            prompt="生成一组连续故事分镜",
            aspect_ratio="1:1",
            resolution="4K",
            num_images=12,
            thinking_mode=True,
        )
    )

    assert service.payload["parameters"]["n"] == 4
    assert service.payload["parameters"]["size"] == "2048*2048"
    assert service.payload["parameters"]["thinking_mode"] is True
    assert "enable_sequential" not in service.payload["parameters"]

    await service.generate(
        ImageGenerationRequest(
            model_id="wan2.7-image-pro",
            prompt="生成一组连续故事分镜",
            aspect_ratio="1:1",
            resolution="4K",
            num_images=12,
            thinking_mode=True,
            enable_sequential=True,
        )
    )

    assert service.payload["parameters"]["n"] == 12
    assert service.payload["parameters"]["size"] == "2048*2048"
    assert service.payload["parameters"]["enable_sequential"] is True
    assert "thinking_mode" not in service.payload["parameters"]


@pytest.mark.asyncio
async def test_tongyi_qwen_image_20_generation_allows_six_outputs() -> None:
    service = _PayloadCapturingWan27GenerationService()

    await service.generate(
        ImageGenerationRequest(
            model_id="qwen-image-2.0-pro",
            prompt="生成六张海报变体",
            aspect_ratio="1:1",
            num_images=6,
        )
    )

    assert service.payload["parameters"]["n"] == 6


@pytest.mark.asyncio
async def test_tongyi_wan27_image_edit_uses_multimodal_generation_payload() -> None:
    service = _PayloadCapturingWan27EditService()

    result = await service.edit(
        model="wan2.7-image-pro",
        prompt="把车身改成红色",
        image_url="https://example.test/source.png",
        options=ImageEditOptions(size="2K", aspect_ratio="16:9", seed=456),
    )

    assert result.success is True
    assert result.url == "https://example.test/wan27-edited.png"
    assert service.endpoint.endswith("/api/v1/services/aigc/multimodal-generation/generation")
    assert service.payload["model"] == "wan2.7-image-pro"
    assert service.payload["input"]["messages"][0]["content"] == [
        {"image": "oss://example/source.png"},
        {"text": "把车身改成红色"},
    ]
    assert service.payload["parameters"] == {
        "size": "2730*1536",
        "n": 1,
        "watermark": False,
        "seed": 456,
    }
