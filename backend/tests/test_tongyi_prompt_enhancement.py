from types import SimpleNamespace

import pytest

from app.services.tongyi.image_edit import ImageEditResult, ImageEditService
from app.services.tongyi.image_generation import ImageGenerationRequest, ImageGenerationService
from app.services.tongyi.prompt_optimizer import EditPromptOptimizer, GenerationPromptOptimizer
from app.services.tongyi.tongyi_service import TongyiService
from app.services.tongyi import image_edit as image_edit_module


class _FakeImageGenerationService:
    def __init__(self) -> None:
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return [
            SimpleNamespace(
                url="https://example.test/generated.png",
                mime_type="image/png",
                optimized_prompt="优化后的文生图提示词",
            )
        ]


class _FakeImageEditService:
    def __init__(self) -> None:
        self.calls = []

    async def edit(self, *, model, prompt, image_url, options):
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "image_url": image_url,
                "options": options,
            }
        )
        return ImageEditResult(
            success=True,
            url="https://example.test/edited.png",
            optimized_prompt="优化后的编辑提示词",
            original_prompt=prompt,
        )


class _FakeMultiImageEditService:
    def __init__(self) -> None:
        self.calls = []

    async def edit(self, *, model, prompt, image_url, options):
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "image_url": image_url,
                "options": options,
            }
        )
        return SimpleNamespace(
            success=True,
            url="https://example.test/edited-1.png",
            urls=[
                "https://example.test/edited-1.png",
                "https://example.test/edited-2.png",
                "https://example.test/edited-3.png",
                "https://example.test/edited-4.png",
            ],
            mime_type="image/png",
            optimized_prompt="优化后的编辑提示词",
        )


class _PayloadCapturingImageGenerationService(ImageGenerationService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.payloads = []

    async def _call_api(self, endpoint: str, payload: dict) -> dict:
        self.payloads.append(payload)
        return {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.test/generated.png"}
                            ]
                        }
                    }
                ]
            }
        }


class _LocalCanvasImageEditService(ImageEditService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.optimizer_image = None
        self.payload = {}

    @property
    def edit_optimizer(self):
        return self

    async def optimize(self, prompt, image, enable_rewrite=True, model=None):
        self.optimizer_image = image
        return SimpleNamespace(success=True, optimized_prompt="本地画布增强提示词")

    async def call_api(self, endpoint: str, payload: dict, use_oss_resolve: bool = True) -> dict:
        self.payload = payload
        return {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.test/local-canvas-edited.png"}
                            ]
                        }
                    }
                ]
            }
        }


class _FakeOptimizerResponse:
    status_code = 200
    text = '{"ok": true}'

    def __init__(self, content: str) -> None:
        self._content = content

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": self._content,
                    }
                }
            ]
        }


class _CapturingOptimizerClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.payloads = []

    async def post(self, url: str, json: dict, headers: dict):
        self.payloads.append(json)
        return _FakeOptimizerResponse(self.content)


@pytest.mark.asyncio
async def test_tongyi_image_generation_uses_snake_case_prompt_extend_for_local_enhancement() -> None:
    service = TongyiService(api_key="test-key")
    fake_generation = _FakeImageGenerationService()
    service._image_generation_service = fake_generation

    results = await service.generate_image(
        prompt="生成一张产品图",
        model="qwen-image-plus",
        prompt_extend=True,
        add_magic_suffix=False,
    )

    assert fake_generation.requests[0].enable_prompt_optimize is True
    assert fake_generation.requests[0].add_magic_suffix is False
    assert results[0]["enhanced_prompt"] == "优化后的文生图提示词"


@pytest.mark.asyncio
async def test_tongyi_wan27_image_generation_keeps_local_enhancement_and_selected_model() -> None:
    service = TongyiService(api_key="test-key")
    fake_generation = _FakeImageGenerationService()
    service._image_generation_service = fake_generation

    await service.generate_image(
        prompt="生成一张产品图",
        model="wan2.7-image-pro",
        enhance_prompt=True,
        enhance_prompt_model="qwen-max",
        add_magic_suffix=True,
    )

    request = fake_generation.requests[0]
    assert request.enable_prompt_optimize is True
    assert request.add_magic_suffix is False
    assert request.prompt_optimize_model == "qwen-max"


@pytest.mark.asyncio
async def test_tongyi_image_generation_uses_snake_case_number_of_images() -> None:
    service = TongyiService(api_key="test-key")
    fake_generation = _FakeImageGenerationService()
    service._image_generation_service = fake_generation

    await service.generate_image(
        prompt="生成四张产品图",
        model="wan2.7-image-pro",
        number_of_images=4,
    )

    assert fake_generation.requests[0].num_images == 4


@pytest.mark.asyncio
async def test_tongyi_wan27_generation_passes_sequential_mode_without_thinking_mode() -> None:
    service = TongyiService(api_key="test-key")
    fake_generation = _FakeImageGenerationService()
    service._image_generation_service = fake_generation

    await service.generate_image(
        prompt="生成一组连续故事分镜",
        model="wan2.7-image-pro",
        number_of_images=12,
        enable_sequential=True,
        thinking_mode=True,
    )

    request = fake_generation.requests[0]
    assert request.num_images == 12
    assert request.enable_sequential is True
    assert request.thinking_mode is None


@pytest.mark.asyncio
async def test_tongyi_image_generation_does_not_enable_dashscope_prompt_extend_by_default() -> None:
    service = _PayloadCapturingImageGenerationService()

    await service._generate_qwen_image(
        ImageGenerationRequest(
            model_id="qwen-image-plus",
            prompt="生成一张产品图",
            enable_prompt_optimize=False,
        )
    )
    await service._generate_wan_v2_image(
        ImageGenerationRequest(
            model_id="wan2.6-t2i",
            prompt="生成一张产品图",
            enable_prompt_optimize=False,
        )
    )

    assert service.payloads[0]["parameters"]["prompt_extend"] is False
    assert service.payloads[1]["parameters"]["prompt_extend"] is False


@pytest.mark.asyncio
async def test_tongyi_image_edit_uses_snake_case_prompt_extend_and_returns_enhanced_prompt() -> None:
    service = TongyiService(api_key="test-key")
    fake_edit = _FakeImageEditService()
    service._image_edit_service = fake_edit

    results = await service.edit_image(
        prompt="把背景改成白色影棚",
        model="qwen-image-edit-plus",
        reference_images={"raw": "https://example.test/source.png"},
        prompt_extend=True,
    )

    assert fake_edit.calls[0]["options"].enable_prompt_optimize is True
    assert results[0]["enhanced_prompt"] == "优化后的编辑提示词"


@pytest.mark.asyncio
async def test_tongyi_image_edit_accepts_local_canvas_url_and_returns_enhanced_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    local_image = tmp_path / "source.png"
    local_image.write_bytes(b"local-canvas-image")
    local_url = "/api/storage/local-files/2026/05/27/source.png"
    upload_calls = []

    def fake_resolve_local_public_file_path(file_url: str):
        assert file_url == local_url
        return local_image

    async def fake_upload_bytes_to_dashscope_async(image_data, filename, api_key, model):
        upload_calls.append(
            {
                "image_data": image_data,
                "filename": filename,
                "api_key": api_key,
                "model": model,
            }
        )
        return SimpleNamespace(success=True, oss_url="oss://dashscope/source.png")

    monkeypatch.setattr(
        image_edit_module,
        "resolve_local_public_file_path",
        fake_resolve_local_public_file_path,
    )
    monkeypatch.setattr(
        image_edit_module,
        "upload_bytes_to_dashscope_async",
        fake_upload_bytes_to_dashscope_async,
    )

    service = _LocalCanvasImageEditService()
    result = await service.edit(
        model="qwen-image-edit-plus",
        prompt="把背景改成白色影棚",
        image_url=local_url,
        options=image_edit_module.ImageEditOptions(enable_prompt_optimize=True),
    )

    assert result.success is True
    assert result.optimized_prompt == "本地画布增强提示词"
    assert service.optimizer_image == b"local-canvas-image"
    assert upload_calls[0]["image_data"] == b"local-canvas-image"
    assert upload_calls[0]["model"] == "qwen-image-edit-plus"
    assert service.payload["input"]["messages"][0]["content"][0] == {
        "image": "oss://dashscope/source.png"
    }


@pytest.mark.asyncio
async def test_tongyi_wan27_image_edit_keeps_local_enhancement_and_selected_model() -> None:
    service = TongyiService(api_key="test-key")
    fake_edit = _FakeImageEditService()
    service._image_edit_service = fake_edit

    await service.edit_image(
        prompt="把背景改成白色影棚",
        model="wan2.7-image-pro",
        reference_images={"raw": "https://example.test/source.png"},
        enhance_prompt=True,
        enhance_prompt_model="qwen-vl-max",
    )

    options = fake_edit.calls[0]["options"]
    assert options.enable_prompt_optimize is True
    assert options.prompt_extend is False
    assert options.prompt_optimize_model == "qwen-vl-max"


@pytest.mark.asyncio
async def test_tongyi_image_edit_replaces_non_visual_prompt_model_with_vision_default() -> None:
    service = TongyiService(api_key="test-key")
    fake_edit = _FakeImageEditService()
    service._image_edit_service = fake_edit

    await service.edit_image(
        prompt="把背景改成白色影棚",
        model="wan2.7-image-pro",
        reference_images={"raw": "https://example.test/source.png"},
        enhance_prompt=True,
        enhance_prompt_model="qwen-plus",
    )

    options = fake_edit.calls[0]["options"]
    assert options.enable_prompt_optimize is True
    assert options.prompt_optimize_model == "qwen-vl-max-latest"


@pytest.mark.asyncio
async def test_tongyi_image_edit_returns_all_generated_urls() -> None:
    service = TongyiService(api_key="test-key")
    fake_edit = _FakeMultiImageEditService()
    service._image_edit_service = fake_edit

    results = await service.edit_image(
        prompt="生成四个编辑版本",
        model="wan2.7-image-pro",
        reference_images={"raw": "https://example.test/source.png"},
        number_of_images=4,
    )

    assert fake_edit.calls[0]["options"].n == 4
    assert [item["url"] for item in results] == [
        "https://example.test/edited-1.png",
        "https://example.test/edited-2.png",
        "https://example.test/edited-3.png",
        "https://example.test/edited-4.png",
    ]


@pytest.mark.asyncio
async def test_tongyi_image_edit_does_not_enable_dashscope_prompt_extend_by_default() -> None:
    service = TongyiService(api_key="test-key")
    fake_edit = _FakeImageEditService()
    service._image_edit_service = fake_edit

    await service.edit_image(
        prompt="把背景改成白色影棚",
        model="qwen-image-edit-plus",
        reference_images={"raw": "https://example.test/source.png"},
    )

    assert fake_edit.calls[0]["options"].prompt_extend is False


def test_tongyi_image_generation_parses_dashscope_actual_prompt() -> None:
    service = ImageGenerationService(api_key="test-key")

    results = service._parse_image_response(
        {
            "output": {
                "results": [
                    {
                        "url": "https://example.test/generated.png",
                        "orig_prompt": "原始提示词",
                        "actual_prompt": "DashScope 实际使用的提示词",
                    }
                ]
            }
        }
    )

    assert results[0].original_prompt == "原始提示词"
    assert results[0].optimized_prompt == "DashScope 实际使用的提示词"


def test_tongyi_image_edit_parses_all_multimodal_images() -> None:
    service = ImageEditService(api_key="test-key")

    urls = service.extract_image_urls(
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.test/edited-1.png"},
                                {"image": "https://example.test/edited-2.png"},
                            ]
                        }
                    },
                    {
                        "message": {
                            "content": [
                                {"image": "https://example.test/edited-3.png"},
                                {"image": "https://example.test/edited-4.png"},
                            ]
                        }
                    },
                ]
            }
        },
        "wan2.7-image-pro",
    )

    assert urls == [
        "https://example.test/edited-1.png",
        "https://example.test/edited-2.png",
        "https://example.test/edited-3.png",
        "https://example.test/edited-4.png",
    ]


@pytest.mark.asyncio
async def test_tongyi_generation_prompt_optimizer_uses_selected_model() -> None:
    optimizer = GenerationPromptOptimizer(api_key="test-key")
    fake_client = _CapturingOptimizerClient("优化后的提示词")
    optimizer._client = fake_client

    result = await optimizer.optimize(
        "生成一张产品图",
        enable_rewrite=True,
        add_magic_suffix=False,
        model="qwen-max",
    )

    assert result.optimized_prompt == "优化后的提示词"
    assert fake_client.payloads[0]["model"] == "qwen-max"


@pytest.mark.asyncio
async def test_tongyi_edit_prompt_optimizer_uses_selected_model() -> None:
    optimizer = EditPromptOptimizer(api_key="test-key")
    fake_client = _CapturingOptimizerClient('{"Rewritten": "优化后的编辑提示词"}')
    optimizer._client = fake_client

    result = await optimizer.optimize(
        "把背景改成白色影棚",
        "https://example.test/source.png",
        enable_rewrite=True,
        model="qwen-vl-max",
    )

    assert result.optimized_prompt == "优化后的编辑提示词"
    assert fake_client.payloads[0]["model"] == "qwen-vl-max"
