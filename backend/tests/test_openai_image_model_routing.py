from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from app.core.provider_param_whitelist import validate_mode_param_keys
from app.routers.models.models import (
    _select_default_model_id_for_mode,
    filter_models_by_mode,
)
from app.services.common.mode_controls_catalog import (
    resolve_mode_controls,
    validate_params_with_catalog,
)
from app.services.common.model_capabilities import ModelConfig, get_openai_capabilities
from app.services.openai.image_editor import ImageEditor
from app.services.openai.image_generator import ImageGenerator
from app.services.openai.image_route_contract import (
    OpenAIImageRoute,
    select_image_edit_route,
    select_image_generation_route,
)
from app.services.openai.model_manager import ModelManager
from app.services.openai.openai_service import OpenAIService


class _FakeRetryableOpenAIError(RuntimeError):
    status_code = 502


def _model(model_id: str) -> ModelConfig:
    return ModelConfig(
        id=model_id,
        name=model_id,
        description=model_id,
        capabilities=get_openai_capabilities(model_id),
    )


def test_openai_gpt_image_models_are_available_in_gen_mode_only() -> None:
    models = [
        _model("gpt-5.4-mini"),
        _model("gpt-image-2"),
        _model("dall-e-3"),
    ]

    image_gen_ids = {model.id for model in filter_models_by_mode(models, "image-gen")}
    image_chat_edit_ids = {model.id for model in filter_models_by_mode(models, "image-chat-edit")}
    chat_ids = {model.id for model in filter_models_by_mode(models, "chat")}

    assert "gpt-image-2" in image_gen_ids
    assert "gpt-image-2" in image_chat_edit_ids
    assert "dall-e-3" not in image_gen_ids
    assert "dall-e-3" not in image_chat_edit_ids
    assert "gpt-5.4-mini" not in image_gen_ids
    assert "gpt-5.4-mini" not in image_chat_edit_ids
    assert "gpt-image-2" not in chat_ids
    assert "dall-e-3" not in chat_ids


def test_openai_image_gen_defaults_to_gpt_image_2() -> None:
    models = [
        _model("dall-e-3"),
        _model("gpt-image-2"),
        _model("gpt-image-1.5"),
    ]

    filtered = filter_models_by_mode(models, "image-gen")

    assert [model.id for model in filtered] == ["gpt-image-2", "gpt-image-1.5"]
    assert _select_default_model_id_for_mode(filtered, [], "image-gen") == "gpt-image-2"


def test_openai_gpt_image_capabilities_and_display_name() -> None:
    capabilities = get_openai_capabilities("gpt-image-2")
    manager = ModelManager(client=object())  # type: ignore[arg-type]

    assert capabilities.vision is True
    assert manager._build_display_name("gpt-image-2", fallback="gpt-image-2") == "GPT Image 2"
    assert "image generation" in manager._build_description("gpt-image-2", fallback="").lower()


def test_openai_gpt_image_generation_uses_gpt_image_sizes() -> None:
    generator = ImageGenerator(api_key="test-key", client=object())  # type: ignore[arg-type]

    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "1K", "image_aspect_ratio": "1:1"}
    )["size"] == "1024x1024"
    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "2K", "image_aspect_ratio": "1:1"}
    )["size"] == "2048x2048"
    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "4K", "image_aspect_ratio": "16:9"}
    )["size"] == "3840x2160"
    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "4K", "image_aspect_ratio": "9:16"}
    )["size"] == "2160x3840"
    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "max", "image_aspect_ratio": "1:1"}
    )["size"] == "2880x2880"
    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "1K", "image_aspect_ratio": "4:3"}
    )["size"] == "1152x864"
    assert generator._normalize_generate_kwargs(
        "gpt-image-2", {"image_resolution": "1K", "image_aspect_ratio": "3:4"}
    )["size"] == "864x1152"
    assert generator._normalize_generate_kwargs("gpt-image-2", {"size": "3456x2304"})[
        "size"
    ] == "3456x2304"
    assert "size" not in generator._normalize_generate_kwargs("gpt-image-2", {"size": "4000x2160"})
    assert generator._normalize_generate_kwargs("gpt-image-2", {"image_aspect_ratio": "4:3"})[
        "size"
    ] == "1152x864"
    assert generator._normalize_generate_kwargs("gpt-image-2", {"image_aspect_ratio": "3:4"})[
        "size"
    ] == "864x1152"
    assert generator._normalize_generate_kwargs("gpt-image-2", {"image_aspect_ratio": "16:9"})[
        "size"
    ] == "1280x720"


def test_openai_gpt_image_generation_keeps_supported_gpt_image_params() -> None:
    generator = ImageGenerator(api_key="test-key", client=object())  # type: ignore[arg-type]

    normalized = generator._normalize_generate_kwargs(
        "gpt-image-2",
        {
            "image_resolution": "4K",
            "image_aspect_ratio": "16:9",
            "quality": "low",
            "background": "opaque",
            "moderation": "low",
            "output_format": "image/jpeg",
            "output_compression_quality": 72,
            "response_format": "url",
            "style": "vivid",
            "number_of_images": 3,
        },
    )

    assert normalized["size"] == "3840x2160"
    assert normalized["quality"] == "low"
    assert normalized["background"] == "opaque"
    assert normalized["moderation"] == "low"
    assert normalized["output_format"] == "jpeg"
    assert normalized["output_compression"] == 72
    assert normalized["n"] == 3
    assert "response_format" not in normalized
    assert "style" not in normalized


def test_openai_gpt_image_2_prunes_unsupported_transparent_background() -> None:
    generator = ImageGenerator(api_key="test-key", client=object())  # type: ignore[arg-type]

    assert "background" not in generator._normalize_generate_kwargs(
        "gpt-image-2",
        {"background": "transparent"},
    )
    assert generator._normalize_generate_kwargs(
        "gpt-image-1.5",
        {"background": "transparent"},
    )["background"] == "transparent"


def test_openai_gpt_image_params_pass_mode_provider_whitelist() -> None:
    validate_mode_param_keys(
        provider="openai",
        mode="image-gen",
        option_keys=[
            "numberOfImages",
            "quality",
            "background",
            "moderation",
            "outputFormat",
            "outputCompression",
            "outputCompressionQuality",
            "enhancePromptThinkingLevel",
            "openaiResponsesModel",
            "openaiPreviousResponseId",
        ],
        extra_keys=[],
    )


def test_openai_image_route_contract_defaults_to_image_api() -> None:
    assert select_image_generation_route({}) == OpenAIImageRoute.IMAGE_GENERATIONS
    assert select_image_edit_route("image-chat-edit", {}) == OpenAIImageRoute.IMAGE_EDITS
    assert select_image_edit_route("image-inpainting", {}) == OpenAIImageRoute.IMAGE_EDITS


def test_openai_image_route_contract_uses_responses_only_for_edit_continuation_state() -> None:
    assert select_image_generation_route({"openai_image_api": "responses"}) == OpenAIImageRoute.IMAGE_GENERATIONS
    assert (
        select_image_generation_route({"openai_previous_response_id": "resp_123"})
        == OpenAIImageRoute.IMAGE_GENERATIONS
    )
    assert select_image_edit_route("image-chat-edit", {"openai_image_api": "responses"}) == OpenAIImageRoute.IMAGE_EDITS
    assert (
        select_image_edit_route("image-chat-edit", {"openai_previous_response_id": "resp_123"})
        == OpenAIImageRoute.RESPONSES_IMAGE_EDIT
    )


def test_pdf_extract_template_params_pass_mode_provider_whitelist() -> None:
    validate_mode_param_keys(
        provider="openai",
        mode="pdf-extract",
        option_keys=[
            "pdfExtractTemplate",
            "pdfAdditionalInstructions",
        ],
        extra_keys=[],
    )


class _FakeImagesClient:
    def __init__(
        self,
        *,
        fail_multi_image: bool = False,
        multi_generate_result_count: int | None = None,
        multi_edit_result_count: int | None = None,
        single_generate_failures: int = 0,
        single_edit_failures: int = 0,
    ) -> None:
        self.calls = []
        self.edit_calls = []
        self.fail_multi_image = fail_multi_image
        self.multi_generate_result_count = multi_generate_result_count
        self.multi_edit_result_count = multi_edit_result_count
        self.single_generate_failures = single_generate_failures
        self.single_edit_failures = single_edit_failures

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        count = int(kwargs.get("n") or 1)
        if self.fail_multi_image and count > 1:
            raise _FakeRetryableOpenAIError("native multi-image request failed")
        if count == 1 and self.single_generate_failures > 0:
            self.single_generate_failures -= 1
            raise _FakeRetryableOpenAIError("single-image request failed")
        result_count = self.multi_generate_result_count if count > 1 and self.multi_generate_result_count is not None else count
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=f"base64-payload-{idx}",
                    revised_prompt=f"revised-{idx}",
                )
                for idx in range(result_count)
            ]
        )

    async def edit(
        self,
        *,
        model,
        prompt,
        image,
        background=None,
        input_fidelity=None,
        mask=None,
        n=None,
        output_compression=None,
        output_format=None,
        partial_images=None,
        quality=None,
        response_format=None,
        size=None,
        stream=None,
        user=None,
        extra_body=None,
        timeout=None,
    ):
        kwargs = {
            key: value
            for key, value in locals().items()
            if key != "self" and value is not None
        }
        self.edit_calls.append(kwargs)
        count = int(n or 1)
        if self.fail_multi_image and count > 1:
            raise _FakeRetryableOpenAIError("native multi-image edit request failed")
        if count == 1 and self.single_edit_failures > 0:
            self.single_edit_failures -= 1
            raise _FakeRetryableOpenAIError("single-image edit request failed")
        result_count = self.multi_edit_result_count if count > 1 and self.multi_edit_result_count is not None else count
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=f"edited-base64-payload-{idx}",
                    revised_prompt=f"edited-revised-{idx}",
                )
                for idx in range(result_count)
            ]
        )


class _FakeChatCompletionsClient:
    def __init__(self, enhanced_prompt: str = "enhanced prompt") -> None:
        self.calls = []
        self.enhanced_prompt = enhanced_prompt

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.enhanced_prompt),
                )
            ]
        )


class _FakeChatClient:
    def __init__(self, enhanced_prompt: str = "enhanced prompt") -> None:
        self.completions = _FakeChatCompletionsClient(enhanced_prompt=enhanced_prompt)


class _FakeResponsesClient:
    def __init__(self, *, output_text: str | None = None) -> None:
        self.calls = []
        self.output_text = output_text

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="resp_456",
            output=[
                SimpleNamespace(
                    type="image_generation_call",
                    result="responses-image-base64",
                )
            ],
            output_text=self.output_text if self.output_text is not None else "Responses image result.",
        )


class _FakeOpenAIClient:
    def __init__(
        self,
        *,
        fail_multi_image: bool = False,
        multi_generate_result_count: int | None = None,
        multi_edit_result_count: int | None = None,
        single_generate_failures: int = 0,
        single_edit_failures: int = 0,
        enhanced_prompt: str = "enhanced prompt",
        responses_output_text: str | None = None,
    ) -> None:
        self.images = _FakeImagesClient(
            fail_multi_image=fail_multi_image,
            multi_generate_result_count=multi_generate_result_count,
            multi_edit_result_count=multi_edit_result_count,
            single_generate_failures=single_generate_failures,
            single_edit_failures=single_edit_failures,
        )
        self.chat = _FakeChatClient(enhanced_prompt=enhanced_prompt)
        self.responses = _FakeResponsesClient(output_text=responses_output_text)


class _FakeOpenAIClientWithOptions(_FakeOpenAIClient):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.option_calls = []

    def with_options(self, **kwargs):
        self.option_calls.append(kwargs)
        return self


@pytest.mark.asyncio
async def test_openai_gpt_image_generation_returns_all_native_n_results() -> None:
    fake_client = _FakeOpenAIClient()
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await generator.generate_image(
        "Generate simple icon variants.",
        "gpt-image-2",
        image_resolution="1K",
        image_aspect_ratio="1:1",
        number_of_images=3,
        quality="low",
        background="opaque",
        moderation="low",
        output_format="png",
    )

    assert fake_client.images.calls[0]["n"] == 3
    assert len(results) == 3
    assert [item["revised_prompt"] for item in results] == [
        "revised-0",
        "revised-1",
        "revised-2",
    ]
    assert all(item["url"].startswith("data:image/png;base64,") for item in results)


@pytest.mark.asyncio
async def test_openai_compatible_image_generation_uses_native_multi_image_first() -> None:
    fake_client = _FakeOpenAIClient()
    generator = ImageGenerator(
        api_key="test-key",
        base_url="https://sub2api.lspon.com/v1",
        client=fake_client,  # type: ignore[arg-type]
    )

    results = await generator.generate_image(
        "Generate simple icon variants.",
        "gpt-image-2",
        image_resolution="1K",
        image_aspect_ratio="1:1",
        number_of_images=3,
        output_format="png",
    )

    assert [call["n"] for call in fake_client.images.calls] == [3]
    assert len(results) == 3


@pytest.mark.asyncio
async def test_openai_image_generator_uses_image_specific_request_options() -> None:
    fake_client = _FakeOpenAIClientWithOptions()
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    await generator.generate_image(
        "Generate a simple icon.",
        "gpt-image-2",
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )

    assert fake_client.option_calls[0] == {"timeout": 240.0, "max_retries": 0}


@pytest.mark.asyncio
async def test_openai_image_generator_uses_gpt_image_2_by_default() -> None:
    fake_client = _FakeOpenAIClient()
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    await generator.generate_image(
        "Generate a simple icon.",
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )

    assert fake_client.images.calls[0]["model"] == "gpt-image-2"
    assert fake_client.images.calls[0]["quality"] == "high"
    assert fake_client.images.calls[0]["output_format"] == "png"


@pytest.mark.asyncio
async def test_openai_image_generator_enhances_prompt_when_requested() -> None:
    fake_client = _FakeOpenAIClient(enhanced_prompt="Enhanced product photo prompt.")
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await generator.generate_image(
        "product photo",
        "gpt-image-2",
        image_resolution="1K",
        image_aspect_ratio="1:1",
        enhance_prompt=True,
        enhance_prompt_model="gpt-5.4-mini",
        enhance_prompt_thinking_level="high",
    )

    image_call = fake_client.images.calls[0]
    chat_call = fake_client.chat.completions.calls[0]
    assert chat_call["model"] == "gpt-5.4-mini"
    assert chat_call["reasoning_effort"] == "high"
    assert image_call["prompt"] == "Enhanced product photo prompt."
    assert results[0]["enhanced_prompt"] == "Enhanced product photo prompt."


@pytest.mark.asyncio
async def test_openai_image_generator_does_not_hardcode_prompt_enhancement_model() -> None:
    fake_client = _FakeOpenAIClient(enhanced_prompt="Should not be used.")
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await generator.generate_image(
        "product photo",
        "gpt-image-2",
        image_resolution="1K",
        image_aspect_ratio="1:1",
        enhance_prompt=True,
    )

    image_call = fake_client.images.calls[0]
    assert fake_client.chat.completions.calls == []
    assert image_call["prompt"] == "product photo"
    assert "enhanced_prompt" not in results[0]


@pytest.mark.asyncio
async def test_openai_gpt_image_generation_uses_native_n_without_manual_fallback_on_provider_error() -> None:
    fake_client = _FakeOpenAIClient(fail_multi_image=True)
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(_FakeRetryableOpenAIError, match="native multi-image request failed"):
        await generator.generate_image(
            "Generate simple icon variants.",
            "gpt-image-2",
            image_resolution="1K",
            image_aspect_ratio="1:1",
            number_of_images=3,
            quality="low",
            background="opaque",
            moderation="low",
            output_format="png",
        )

    assert [call["n"] for call in fake_client.images.calls] == [3]


@pytest.mark.asyncio
async def test_openai_gpt_image_generation_does_not_manual_retry_single_image_request() -> None:
    fake_client = _FakeOpenAIClient(single_generate_failures=1)
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(_FakeRetryableOpenAIError, match="single-image request failed"):
        await generator.generate_image(
            "Generate a single product image.",
            "gpt-image-2",
            image_resolution="max",
            image_aspect_ratio="1:1",
            number_of_images=1,
            output_format="png",
        )

    assert [call["n"] for call in fake_client.images.calls] == [1]


@pytest.mark.asyncio
async def test_openai_gpt_image_generation_rejects_short_native_batch_response() -> None:
    fake_client = _FakeOpenAIClient(multi_generate_result_count=0)
    generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="returned fewer images than requested"):
        await generator.generate_image(
            "Generate simple icon variants.",
            "gpt-image-2",
            image_resolution="1K",
            image_aspect_ratio="1:1",
            number_of_images=3,
            output_format="png",
        )

    assert [call["n"] for call in fake_client.images.calls] == [3]


@pytest.mark.asyncio
async def test_openai_service_passes_image_specific_request_options_to_image_clients() -> None:
    fake_client = _FakeOpenAIClientWithOptions()
    service = OpenAIService(
        api_key="test-key",
        api_url="https://api.openai.test/v1",
        image_timeout=321,
        image_max_retries=2,
    )
    service.client = fake_client  # type: ignore[assignment]

    await service.generate_image(
        "Generate a simple icon.",
        model="gpt-image-2",
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )
    await service.edit_image(
        prompt="Edit the image.",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )

    assert fake_client.option_calls == [
        {"timeout": 321.0, "max_retries": 2},
        {"timeout": 321.0, "max_retries": 2},
    ]


@pytest.mark.asyncio
async def test_openai_service_exposes_image_edit_dispatch() -> None:
    class FakeEditor:
        def __init__(self) -> None:
            self.calls = []

        async def edit_image(self, prompt, model, **kwargs):
            self.calls.append({"prompt": prompt, "model": model, **kwargs})
            return [{"url": "data:image/png;base64,edited"}]

    fake_editor = FakeEditor()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service._image_editor = fake_editor

    result = await service.edit_image(
        prompt="Replace the background with a clean studio setup.",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        mode="image-inpainting",
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )

    assert result == [{"url": "data:image/png;base64,edited"}]
    assert fake_editor.calls == [
        {
            "prompt": "Replace the background with a clean studio setup.",
            "model": "gpt-image-2",
            "reference_images": {"raw": "data:image/png;base64,c2FtcGxl"},
            "mode": "image-inpainting",
            "image_resolution": "1K",
            "image_aspect_ratio": "1:1",
        }
    ]


@pytest.mark.asyncio
async def test_openai_image_editor_calls_images_edit_with_reference_images() -> None:
    fake_client = _FakeOpenAIClient()
    editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await editor.edit_image(
        prompt="Turn the product photo into a gift basket scene.",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        image_resolution="1K",
        image_aspect_ratio="1:1",
        number_of_images=2,
        quality="high",
        background="opaque",
        moderation="low",
        output_format="jpeg",
        output_compression_quality=72,
    )

    edit_call = fake_client.images.edit_calls[0]
    assert edit_call["model"] == "gpt-image-2"
    assert edit_call["prompt"] == "Turn the product photo into a gift basket scene."
    assert edit_call["size"] == "1024x1024"
    assert edit_call["n"] == 2
    assert edit_call["quality"] == "high"
    assert edit_call["background"] == "opaque"
    assert "moderation" not in edit_call
    assert edit_call["extra_body"]["moderation"] == "low"
    assert edit_call["output_format"] == "jpeg"
    assert edit_call["output_compression"] == 72
    assert edit_call["image"][0][0] == "image_0.png"
    assert edit_call["image"][0][1] == b"sample"
    assert len(results) == 2
    assert results[0]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_openai_image_editor_uses_native_n_without_manual_fallback_on_provider_error() -> None:
    fake_client = _FakeOpenAIClient(fail_multi_image=True)
    editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(_FakeRetryableOpenAIError, match="native multi-image edit request failed"):
        await editor.edit_image(
            prompt="Create edited variants.",
            model="gpt-image-2",
            reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
            image_resolution="1K",
            image_aspect_ratio="1:1",
            number_of_images=2,
            output_format="png",
        )

    assert [call["n"] for call in fake_client.images.edit_calls] == [2]


@pytest.mark.asyncio
async def test_openai_image_editor_does_not_manual_retry_single_image_request() -> None:
    fake_client = _FakeOpenAIClient(single_edit_failures=1)
    editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(_FakeRetryableOpenAIError, match="single-image edit request failed"):
        await editor.edit_image(
            prompt="Create one edited variant.",
            model="gpt-image-2",
            reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
            image_resolution="1K",
            image_aspect_ratio="1:1",
            number_of_images=1,
            output_format="png",
        )

    assert [call["n"] for call in fake_client.images.edit_calls] == [1]


@pytest.mark.asyncio
async def test_openai_image_editor_rejects_short_native_batch_response() -> None:
    fake_client = _FakeOpenAIClient(multi_edit_result_count=0)
    editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="returned fewer images than requested"):
        await editor.edit_image(
            prompt="Create edited variants.",
            model="gpt-image-2",
            reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
            image_resolution="1K",
            image_aspect_ratio="1:1",
            number_of_images=2,
            output_format="png",
        )

    assert [call["n"] for call in fake_client.images.edit_calls] == [2]


@pytest.mark.asyncio
async def test_openai_image_editor_enhances_prompt_when_requested() -> None:
    fake_client = _FakeOpenAIClient(enhanced_prompt="Enhanced edit prompt.")
    editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await editor.edit_image(
        prompt="replace background",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        image_resolution="1K",
        image_aspect_ratio="1:1",
        enhance_prompt=True,
        enhance_prompt_model="gpt-5.4-mini",
        enhance_prompt_thinking_level="high",
    )

    edit_call = fake_client.images.edit_calls[0]
    chat_call = fake_client.chat.completions.calls[0]
    assert chat_call["model"] == "gpt-5.4-mini"
    assert chat_call["reasoning_effort"] == "high"
    assert edit_call["prompt"] == "Enhanced edit prompt."
    assert results[0]["enhanced_prompt"] == "Enhanced edit prompt."


@pytest.mark.asyncio
async def test_openai_image_editor_resolves_local_storage_reference_url() -> None:
    local_file = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "temp"
        / "local_storage"
        / "tests"
        / "openai-local-reference.png"
    )
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"local-storage-image")

    fake_client = _FakeOpenAIClient()
    editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    await editor.edit_image(
        prompt="Use local storage reference.",
        model="gpt-image-2",
        reference_images={"raw": "/api/storage/local-files/tests/openai-local-reference.png"},
        image_resolution="1K",
        image_aspect_ratio="1:1",
        number_of_images=1,
    )

    edit_call = fake_client.images.edit_calls[0]
    assert edit_call["image"][0][0] == "image_0.png"
    assert edit_call["image"][0][1] == b"local-storage-image"
    assert edit_call["image"][0][2] == "image/png"


@pytest.mark.asyncio
async def test_openai_image_editor_rejects_server_filesystem_reference(tmp_path: Path) -> None:
    local_file = tmp_path / "secret-reference.png"
    local_file.write_bytes(b"server-local-secret")

    editor = ImageEditor(api_key="test-key", client=_FakeOpenAIClient())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unsupported image source string"):
        await editor._load_image_bytes(str(local_file))  # noqa: SLF001 - verifies provider boundary


@pytest.mark.asyncio
async def test_openai_image_editor_rejects_unsafe_http_reference_url() -> None:
    editor = ImageEditor(api_key="test-key", client=_FakeOpenAIClient())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="URL"):
        await editor._load_image_bytes("http://127.0.0.1/internal.png")  # noqa: SLF001 - SSRF guard


def test_openai_gpt_image_controls_schema_exposes_model_specific_options() -> None:
    schema = resolve_mode_controls("openai", "image-gen", "gpt-image-2")

    assert schema is not None
    assert schema["constraints"]["max_image_count"] == 10
    assert {item["value"] for item in schema["aspect_ratios"]} == {
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
    }
    allowed_aspects = {item["value"] for item in schema["aspect_ratios"]}
    assert {item["value"] for item in schema["resolution_tiers"]} == {"auto", "1K", "2K", "max"}
    max_tier = next(item for item in schema["resolution_tiers"] if item["value"] == "max")
    assert max_tier["label"] == "Max"
    assert all(set(aspect_map) == allowed_aspects for aspect_map in schema["resolution_map"].values())
    assert schema["resolution_map"]["1K"]["4:3"] == "1152x864"
    assert schema["resolution_map"]["1K"]["3:4"] == "864x1152"
    assert schema["resolution_map"]["2K"]["1:1"] == "2048x2048"
    assert schema["resolution_map"]["2K"]["4:3"] == "2048x1536"
    assert schema["resolution_map"]["2K"]["3:4"] == "1536x2048"
    assert schema["resolution_map"]["2K"]["16:9"] == "2048x1152"
    assert schema["resolution_map"]["max"]["1:1"] == "2880x2880"
    assert schema["resolution_map"]["max"]["16:9"] == "3840x2160"
    assert schema["resolution_map"]["max"]["9:16"] == "2160x3840"
    assert schema["defaults"]["quality"] == "high"
    assert schema["defaults"]["output_format"] == "png"
    assert schema["defaults"]["enhance_prompt"] is False
    assert schema["param_options"]["quality"] == []
    assert schema["param_options"]["background"] == []
    assert schema["param_options"]["moderation"] == []
    assert schema["param_options"]["output_format"] == []
    assert schema["numeric_ranges"]["output_compression_quality"] is None

    validated = validate_params_with_catalog(
        "openai",
        "image-gen",
        "gpt-image-2",
        {
            "image_resolution": "max",
            "image_aspect_ratio": "16:9",
            "number_of_images": 3,
        },
    )

    assert validated["number_of_images"] == 3

    legacy_validated = validate_params_with_catalog(
        "openai",
        "image-gen",
        "gpt-image-2",
        {
            "image_resolution": "4K",
            "image_aspect_ratio": "16:9",
        },
    )
    assert legacy_validated["image_resolution"] == "max"


def test_openai_chat_edit_controls_schema_uses_gpt_image_edit_surface() -> None:
    schema = resolve_mode_controls("openai", "image-chat-edit", "gpt-image-2")

    assert schema is not None
    assert schema["mode"] == "image-edit"
    assert schema["requested_mode"] == "image-chat-edit"
    assert schema["constraints"]["max_image_count"] == 10
    assert {item["value"] for item in schema["aspect_ratios"]} == {
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
    }
    assert {item["value"] for item in schema["resolution_tiers"]} == {"auto", "1K", "2K", "max"}
    assert "output_mime_type" not in schema["param_options"]
    assert schema["defaults"]["quality"] == "high"
    assert schema["defaults"]["output_format"] == "png"
    assert schema["defaults"]["enhance_prompt"] is False
    assert schema["param_options"]["quality"] == []
    assert schema["param_options"]["background"] == []
    assert schema["param_options"]["moderation"] == []
    assert schema["param_options"]["output_format"] == []

    validated = validate_params_with_catalog(
        "openai",
        "image-chat-edit",
        "gpt-image-2",
        {
            "image_resolution": "2K",
            "image_aspect_ratio": "16:9",
            "number_of_images": 2,
        },
    )

    assert validated["number_of_images"] == 2


def test_openai_image_gen_controls_schema_defaults_to_gpt_image_surface() -> None:
    schema = resolve_mode_controls("openai", "image-gen")

    assert schema is not None
    assert schema["constraints"]["max_image_count"] == 10
    assert schema["defaults"]["resolution"] == "auto"
    assert {item["value"] for item in schema["aspect_ratios"]} == {
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
    }
    assert {item["value"] for item in schema["resolution_tiers"]} == {"auto", "1K", "2K", "max"}
    assert schema["defaults"]["quality"] == "high"
    assert schema["defaults"]["output_format"] == "png"
    assert schema["defaults"]["enhance_prompt"] is False
    assert schema["param_options"]["quality"] == []
    assert schema["param_options"]["background"] == []
    assert schema["param_options"]["moderation"] == []
    assert schema["param_options"]["output_format"] == []


def test_openai_edit_derived_modes_use_gpt_image_edit_surface() -> None:
    for mode in [
        "image-mask-edit",
        "image-inpainting",
        "image-background-edit",
        "image-recontext",
        "image-outpainting",
        "virtual-try-on",
    ]:
        schema = resolve_mode_controls("openai", mode, "gpt-image-2")

        assert schema is not None
        assert schema["mode"] == "image-edit"
        assert schema["requested_mode"] == mode
        assert schema["constraints"]["max_image_count"] == 10
        assert {item["value"] for item in schema["aspect_ratios"]} == {
            "1:1",
            "4:3",
            "3:4",
            "16:9",
            "9:16",
        }
        assert {item["value"] for item in schema["resolution_tiers"]} == {"auto", "1K", "2K", "max"}
        assert "outpaint_mode" not in schema["param_options"]
        assert "edit_mode" not in schema["param_options"]
        assert "base_steps" not in schema.get("numeric_ranges", {})


def test_openai_gpt_image_model_is_available_for_edit_derived_modes() -> None:
    models = [
        _model("gpt-5.4-mini"),
        _model("gpt-image-2"),
        _model("imagen-3.0-capability-001"),
    ]

    for mode in [
        "image-mask-edit",
        "image-background-edit",
        "image-recontext",
        "image-outpainting",
        "virtual-try-on",
    ]:
        mode_ids = {model.id for model in filter_models_by_mode(models, mode)}
        assert "gpt-image-2" in mode_ids
        assert "gpt-5.4-mini" not in mode_ids


@pytest.mark.asyncio
async def test_openai_service_exposes_outpainting_as_gpt_image_edit() -> None:
    class FakeEditor:
        def __init__(self) -> None:
            self.calls = []

        async def edit_image(self, prompt, model, **kwargs):
            self.calls.append({"prompt": prompt, "model": model, **kwargs})
            return [{"url": "data:image/png;base64,outpainted"}]

    fake_editor = FakeEditor()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service._image_editor = fake_editor

    result = await service.expand_image(
        prompt="Extend the product photo to a clean studio 16:9 composition.",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        image_resolution="2K",
        image_aspect_ratio="16:9",
        number_of_images=2,
    )

    assert result == [{"url": "data:image/png;base64,outpainted"}]
    assert fake_editor.calls == [
        {
            "prompt": "Extend the product photo to a clean studio 16:9 composition.",
            "model": "gpt-image-2",
            "reference_images": {"raw": "data:image/png;base64,c2FtcGxl"},
            "mode": "image-outpainting",
            "image_resolution": "2K",
            "image_aspect_ratio": "16:9",
            "number_of_images": 2,
        }
    ]


@pytest.mark.asyncio
async def test_openai_service_exposes_virtual_tryon_as_multi_reference_edit() -> None:
    class FakeEditor:
        def __init__(self) -> None:
            self.calls = []

        async def edit_image(self, prompt, model, **kwargs):
            self.calls.append({"prompt": prompt, "model": model, **kwargs})
            return [{"url": "data:image/png;base64,tryon"}]

    fake_editor = FakeEditor()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service._image_editor = fake_editor

    result = await service.virtual_tryon(
        prompt="",
        model="gpt-image-2",
        reference_images={
            "raw": [
                "data:image/png;base64,cGVyc29u",
                "data:image/png;base64,Z2FybWVudA==",
            ]
        },
        number_of_images=1,
    )

    assert result == [{"url": "data:image/png;base64,tryon"}]
    assert fake_editor.calls[0]["model"] == "gpt-image-2"
    assert fake_editor.calls[0]["mode"] == "virtual-try-on"
    assert "wear the garment" in fake_editor.calls[0]["prompt"].lower()
    assert fake_editor.calls[0]["reference_images"]["raw"] == [
        "data:image/png;base64,cGVyc29u",
        "data:image/png;base64,Z2FybWVudA==",
    ]


@pytest.mark.asyncio
async def test_openai_service_routes_image_generation_through_images_api_even_with_legacy_api_hint() -> None:
    fake_client = _FakeOpenAIClient()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]
    service._image_generator = ImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await service.generate_image(
        prompt="Generate a clean product hero image.",
        model="gpt-image-2",
        openai_image_api="responses",
        openai_responses_model="gpt-5.4-mini",
        image_resolution="1K",
        image_aspect_ratio="1:1",
        quality="high",
    )

    assert fake_client.responses.calls == []
    call = fake_client.images.calls[0]
    assert call["model"] == "gpt-image-2"
    assert call["prompt"] == "Generate a clean product hero image."
    assert call["size"] == "1024x1024"
    assert results[0]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_openai_service_can_route_multi_turn_image_edit_through_responses_api() -> None:
    fake_client = _FakeOpenAIClient()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]
    service._image_editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await service.edit_image(
        prompt="Make the background warmer.",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        mode="image-chat-edit",
        openai_responses_model="gpt-5.4-mini",
        openai_previous_response_id="resp_123",
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )

    call = fake_client.responses.calls[0]
    assert call["model"] == "gpt-5.4-mini"
    assert call["previous_response_id"] == "resp_123"
    assert call["tools"][0]["action"] == "edit"
    assert call["input"][0]["content"][0] == {
        "type": "input_text",
        "text": "Make the background warmer.",
    }
    assert call["input"][0]["content"][1]["type"] == "input_image"
    assert call["input"][0]["content"][1]["image_url"] == "data:image/png;base64,c2FtcGxl"
    assert results[0]["openai_response_id"] == "resp_456"


@pytest.mark.asyncio
async def test_openai_service_routes_chat_edit_through_images_edit_without_responses_state() -> None:
    fake_client = _FakeOpenAIClient()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]
    service._image_editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await service.edit_image(
        prompt="Make the product photo warmer.",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        mode="image-chat-edit",
        image_resolution="1K",
        image_aspect_ratio="1:1",
    )

    assert fake_client.responses.calls == []
    call = fake_client.images.edit_calls[0]
    assert call["model"] == "gpt-image-2"
    assert call["prompt"] == "Make the product photo warmer."
    assert call["size"] == "1024x1024"
    assert results[0]["url"].startswith("data:image/png;base64,edited-base64-payload")


@pytest.mark.asyncio
async def test_openai_service_does_not_fallback_when_continuation_responses_edit_fails() -> None:
    class FailingResponsesClient:
        def __init__(self) -> None:
            self.calls = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("responses endpoint is not available")

    fake_client = _FakeOpenAIClient()
    fake_client.responses = FailingResponsesClient()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]
    service._image_editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="responses endpoint is not available"):
        await service.edit_image(
            prompt="Make the product photo warmer.",
            model="gpt-image-2",
            reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
            mode="image-chat-edit",
            openai_previous_response_id="resp_123",
            image_resolution="1K",
            image_aspect_ratio="1:1",
        )

    assert fake_client.responses.calls
    assert fake_client.images.edit_calls == []


@pytest.mark.asyncio
async def test_openai_responses_image_edit_requires_reference_image() -> None:
    fake_client = _FakeOpenAIClient()
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]
    service._image_editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="reference image is required"):
        await service.edit_image(
            prompt="Make the background warmer.",
            model="gpt-image-2",
            reference_images={},
            mode="image-chat-edit",
            openai_responses_model="gpt-5.4-mini",
            openai_previous_response_id="resp_123",
            image_resolution="1K",
            image_aspect_ratio="1:1",
        )

    assert fake_client.responses.calls == []


@pytest.mark.asyncio
async def test_openai_responses_image_edit_returns_enhanced_prompt_when_requested() -> None:
    fake_client = _FakeOpenAIClient(enhanced_prompt="Enhanced Responses edit prompt.")
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]
    service._image_editor = ImageEditor(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    results = await service.edit_image(
        prompt="make it warmer",
        model="gpt-image-2",
        reference_images={"raw": "data:image/png;base64,c2FtcGxl"},
        mode="image-chat-edit",
        openai_responses_model="gpt-5.4-mini",
        openai_previous_response_id="resp_123",
        image_resolution="1K",
        image_aspect_ratio="1:1",
        enhance_prompt=True,
        enhance_prompt_model="gpt-5.5",
        enhance_prompt_thinking_level="high",
    )

    chat_call = fake_client.chat.completions.calls[0]
    responses_call = fake_client.responses.calls[0]

    assert chat_call["model"] == "gpt-5.5"
    assert chat_call["reasoning_effort"] == "high"
    assert responses_call["input"][0]["content"][0] == {
        "type": "input_text",
        "text": "Enhanced Responses edit prompt.",
    }
    assert results[0]["enhanced_prompt"] == "Enhanced Responses edit prompt."


@pytest.mark.asyncio
async def test_openai_service_extracts_pdf_data_with_responses_file_input() -> None:
    fake_client = _FakeOpenAIClient(
        responses_output_text=json.dumps(
            {
                "vendor": "Acme",
                "total": "$42.00",
            }
        )
    )
    service = OpenAIService(api_key="test-key", api_url="https://api.openai.test/v1")
    service.client = fake_client  # type: ignore[assignment]

    result = await service.extract_pdf_data(
        prompt="Extract the invoice fields.",
        model="gpt-5.4-mini",
        reference_images={"pdf_bytes": b"%PDF-1.4 sample"},
        template_type="invoice",
    )

    call = fake_client.responses.calls[0]
    content = call["input"][0]["content"]
    assert call["model"] == "gpt-5.4-mini"
    assert content[0]["type"] == "input_file"
    assert content[0]["filename"] == "invoice.pdf"
    assert content[0]["file_data"].startswith("data:application/pdf;base64,")
    assert content[1]["type"] == "input_text"
    assert result["success"] is True
    assert result["template_type"] == "invoice"
    assert result["data"] == {"vendor": "Acme", "total": "$42.00"}
