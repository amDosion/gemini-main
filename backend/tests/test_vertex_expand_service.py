import base64
import io

import pytest
from PIL import Image as PILImage

from app.routers.models.models import filter_models_by_mode
from app.services.common.google_model_catalog import (
    IMAGEN_EDIT_MODELS,
    IMAGE_UPSCALE_MODELS,
    get_static_google_vertex_model_ids_for_mode,
    get_static_google_vertex_models,
)
from app.services.common.model_capabilities import Capabilities, ModelConfig
from app.services.gemini.vertexai.expand_service import ExpandService


def _png_data_url(width=64, height=48):
    image = PILImage.new("RGB", (width, height), (120, 160, 200))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class _FakeSdkImage:
    def __init__(self, image_bytes):
        self.image_bytes = image_bytes

    def save(self, path):
        with open(path, "wb") as handle:
            handle.write(self.image_bytes)


class _FakeGeneratedImage:
    def __init__(self, image_bytes):
        self.image = _FakeSdkImage(image_bytes)
        self.rai_filtered_reason = None
        self.rai_reason = None
        self.safety_attributes = None


class _FakeResponse:
    def __init__(self, image_bytes):
        self.generated_images = [_FakeGeneratedImage(image_bytes)]


class _FakeModels:
    def __init__(self, output_bytes):
        self.output_bytes = output_bytes
        self.edit_calls = []
        self.upscale_calls = []

    def edit_image(self, **kwargs):
        self.edit_calls.append(kwargs)
        return _FakeResponse(self.output_bytes)

    def upscale_image(self, **kwargs):
        self.upscale_calls.append(kwargs)
        return _FakeResponse(self.output_bytes)


class _FakeClient:
    def __init__(self, output_bytes):
        self.models = _FakeModels(output_bytes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "mode_kwargs"),
    [
        ("ratio", {"output_ratio": "16:9"}),
        ("scale", {"x_scale": 1.5, "y_scale": 1.25}),
        ("offset", {"left_offset": 16, "right_offset": 24, "top_offset": 8, "bottom_offset": 12}),
    ],
)
async def test_outpaint_modes_use_selected_edit_model_and_forward_sdk_config(monkeypatch, mode, mode_kwargs):
    output_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    fake_client = _FakeClient(output_bytes)
    service = ExpandService()
    monkeypatch.setattr(service, "_get_vertex_client", lambda: fake_client)

    results = await service.expand_image(
        prompt="extend the clean studio background",
        model="imagen-3.0-capability-001",
        reference_images={"raw": _png_data_url()},
        mode=mode,
        number_of_images=2,
        output_mime_type="image/jpeg",
        output_compression_quality=82,
        negative_prompt="text, watermark",
        seed=123,
        base_steps=35,
        guidance_scale=12.5,
        **mode_kwargs,
    )

    assert len(fake_client.models.edit_calls) == 1
    assert fake_client.models.upscale_calls == []
    call = fake_client.models.edit_calls[0]
    assert call["model"] == "imagen-3.0-capability-001"
    assert call["config"].edit_mode == "EDIT_MODE_OUTPAINT"
    assert call["config"].number_of_images == 2
    assert call["config"].output_mime_type == "image/jpeg"
    assert call["config"].output_compression_quality == 82
    assert call["config"].negative_prompt == "text, watermark"
    assert call["config"].seed == 123
    assert call["config"].base_steps == 35
    assert call["config"].guidance_scale == 12.5
    assert getattr(call["config"], "person_generation", None) is None
    assert getattr(call["config"], "safety_filter_level", None) is None
    assert results[0]["mime_type"] == "image/jpeg"
    assert results[0]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_upscale_mode_uses_selected_upscale_model_without_safety_or_person_config(monkeypatch):
    output_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    fake_client = _FakeClient(output_bytes)
    service = ExpandService()
    monkeypatch.setattr(service, "_get_vertex_client", lambda: fake_client)

    results = await service.expand_image(
        prompt="",
        model="imagen-4.0-upscale-preview",
        reference_images={"raw": _png_data_url()},
        mode="upscale",
        upscale_factor="x3",
        output_mime_type="image/png",
    )

    assert fake_client.models.edit_calls == []
    assert len(fake_client.models.upscale_calls) == 1
    call = fake_client.models.upscale_calls[0]
    assert call["model"] == "imagen-4.0-upscale-preview"
    assert call["upscale_factor"] == "x3"
    assert getattr(call["config"], "person_generation", None) is None
    assert getattr(call["config"], "safety_filter_level", None) is None
    assert results[0]["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_expand_service_rejects_model_that_does_not_match_submode():
    service = ExpandService()

    with pytest.raises(ValueError, match="不支持图像扩展操作"):
        await service.expand_image(
            prompt="extend",
            model="imagen-4.0-upscale-preview",
            reference_images={"raw": _png_data_url()},
            mode="ratio",
            output_ratio="16:9",
        )

    with pytest.raises(ValueError, match="不支持图片放大操作"):
        await service.expand_image(
            prompt="",
            model="imagen-3.0-capability-001",
            reference_images={"raw": _png_data_url()},
            mode="upscale",
            upscale_factor="x2",
        )


def test_image_outpainting_model_filter_only_exposes_vertex_expand_models():
    models = [
        ModelConfig(
            id="imagen-3.0-capability-001",
            name="Imagen Edit",
            description="outpaint",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="imagen-4.0-upscale-preview",
            name="Imagen Upscale",
            description="upscale",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="image-segmentation-001",
            name="Segmentation",
            description="segmentation",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="gemini-2.5-flash",
            name="Gemini Flash",
            description="chat",
            capabilities=Capabilities(vision=True),
        ),
    ]

    filtered = filter_models_by_mode(models, "image-outpainting")

    assert [model.id for model in filtered] == [
        "imagen-3.0-capability-001",
        "imagen-4.0-upscale-preview",
    ]


def test_google_vertex_static_catalog_drives_expand_model_availability():
    all_static_models = get_static_google_vertex_models()
    outpainting_models = get_static_google_vertex_model_ids_for_mode("image-outpainting")

    assert "imagen-3.0-capability-001" in all_static_models
    assert "imagen-4.0-upscale-preview" in all_static_models
    assert outpainting_models == [
        "imagen-3.0-capability-001",
        "imagen-4.0-upscale-preview",
    ]
    assert IMAGEN_EDIT_MODELS == [
        "imagen-3.0-capability-001",
    ]
    assert IMAGE_UPSCALE_MODELS == ["imagen-4.0-upscale-preview"]


def test_expand_service_model_validation_is_backed_by_static_catalog():
    service = ExpandService()
    outpainting_models = set(get_static_google_vertex_model_ids_for_mode("image-outpainting"))

    assert service.expand_models == outpainting_models
    assert service.edit_models == {"imagen-3.0-capability-001"}
    assert service.upscale_models == {"imagen-4.0-upscale-preview"}
