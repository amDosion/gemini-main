from app.routers.models.models import filter_models_by_mode
from app.services.gemini.coordinators.image_edit_coordinator import ImageEditCoordinator
from app.services.gemini.google_service import GoogleService
from app.services.gemini.http_options import HttpOptions
from app.services.common.google_model_catalog import (
    DEPRECATED_GOOGLE_VERTEX_IMAGE_MODEL_MIGRATIONS,
    get_static_google_vertex_model_ids_for_mode,
    get_static_google_vertex_models,
)
from app.services.gemini.geminiapi.recontext_image_service import (
    GeminiRecontextImageService,
)
from app.services.gemini.vertexai.background_edit_service import BackgroundEditService
from app.services.gemini.geminiapi.imagen_gemini_api import GeminiAPIImageGenerator
from app.services.common.model_capabilities import Capabilities, ModelConfig
from app.services.common.mode_controls_catalog import (
    resolve_mode_controls,
    validate_params_with_catalog,
)
from app.services.common.video_mode_contract import apply_video_mode_runtime_overrides
import pytest


def test_static_google_vertex_catalog_excludes_deprecated_image_preview_endpoints():
    static_models = set(get_static_google_vertex_models())

    assert not static_models.intersection(DEPRECATED_GOOGLE_VERTEX_IMAGE_MODEL_MIGRATIONS)
    assert "gemini-2.5-flash-image" in static_models
    assert "virtual-try-on-001" in static_models


def test_recontext_modes_migrate_to_gemini_flash_image():
    for mode in ("image-recontext", "product-recontext"):
        mode_models = get_static_google_vertex_model_ids_for_mode(mode)

        assert "gemini-2.5-flash-image" in mode_models
        assert "imagen-3.0-capability-001" not in mode_models
        assert "imagen-product-recontext-preview-06-30" not in mode_models
        assert "imagen-4.0-ingredients-preview" not in mode_models


def test_background_mode_uses_imagen_background_edit_not_gemini_recontext():
    mode_models = get_static_google_vertex_model_ids_for_mode("image-background-edit")

    assert "imagen-3.0-capability-001" in mode_models
    assert "gemini-2.5-flash-image" not in mode_models
    assert "imagen-product-recontext-preview-06-30" not in mode_models


def test_filter_models_hides_deprecated_recontext_model_even_if_returned_by_api():
    models = [
        ModelConfig(
            id="imagen-product-recontext-preview-06-30",
            name="Deprecated Product Recontext",
            description="deprecated",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="gemini-2.5-flash-image",
            name="Gemini 2.5 Flash Image",
            description="replacement",
            capabilities=Capabilities(vision=True, search=True),
        ),
    ]

    filtered = filter_models_by_mode(models, "product-recontext")

    assert [model.id for model in filtered] == ["gemini-2.5-flash-image"]


def test_image_recontext_filter_excludes_imagen_edit_model_that_requires_mask():
    models = [
        ModelConfig(
            id="imagen-3.0-capability-001",
            name="Imagen Capability",
            description="edit model",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="gemini-2.5-flash-image",
            name="Gemini 2.5 Flash Image",
            description="replacement",
            capabilities=Capabilities(vision=True, search=True),
        ),
    ]

    filtered = filter_models_by_mode(models, "image-recontext")

    assert [model.id for model in filtered] == ["gemini-2.5-flash-image"]


def test_image_background_filter_excludes_gemini_recontext_model():
    models = [
        ModelConfig(
            id="imagen-3.0-capability-001",
            name="Imagen Capability",
            description="official background edit model",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="gemini-2.5-flash-image",
            name="Gemini 2.5 Flash Image",
            description="recontext replacement",
            capabilities=Capabilities(vision=True, search=True),
        ),
        ModelConfig(
            id="gemini-2.5-pro",
            name="Gemini 2.5 Pro",
            description="vision chat model",
            capabilities=Capabilities(vision=True, search=True),
        ),
    ]

    filtered = filter_models_by_mode(models, "image-background-edit")

    assert [model.id for model in filtered] == ["imagen-3.0-capability-001"]


def test_image_mask_filter_excludes_gemini_image_models():
    models = [
        ModelConfig(
            id="imagen-3.0-capability-001",
            name="Imagen Capability",
            description="official mask edit model",
            capabilities=Capabilities(vision=True),
        ),
        ModelConfig(
            id="gemini-2.5-flash-image",
            name="Gemini 2.5 Flash Image",
            description="Gemini image model",
            capabilities=Capabilities(vision=True, search=True),
        ),
        ModelConfig(
            id="gemini-2.5-pro",
            name="Gemini 2.5 Pro",
            description="vision chat model",
            capabilities=Capabilities(vision=True, search=True),
        ),
    ]

    filtered = filter_models_by_mode(models, "image-mask-edit")

    assert [model.id for model in filtered] == ["imagen-3.0-capability-001"]


@pytest.mark.asyncio
async def test_mask_mode_rejects_gemini_image_model_before_conversational_route(monkeypatch):
    coordinator = ImageEditCoordinator.__new__(ImageEditCoordinator)
    coordinator._config = {"api_mode": "vertex_ai"}
    coordinator._editor_cache = {}

    async def fail_conversational_route(**_kwargs):
        raise AssertionError("image-mask-edit must not route to conversational image edit")

    monkeypatch.setattr(
        coordinator,
        "_edit_with_conversational_image_service",
        fail_conversational_route,
    )

    with pytest.raises(ValueError, match="not compatible with Vertex Imagen edit_image API"):
        await coordinator.edit_image(
            prompt="insert detail",
            reference_images={"raw": "data:image/png;base64,raw"},
            model="gemini-2.5-flash-image",
            mode="image-mask-edit",
        )


def test_background_edit_service_defaults_to_bgswap_with_automatic_background_mask():
    service = BackgroundEditService.__new__(BackgroundEditService)

    config = service._apply_service_defaults({})
    edit_config = service._build_config(config)

    assert config["mask_mode"] == "MASK_MODE_BACKGROUND"
    assert edit_config.edit_mode.name == "EDIT_MODE_BGSWAP"


def test_image_mask_controls_only_expose_local_mask_edit_modes():
    schema = resolve_mode_controls("google", "image-mask-edit", "imagen-3.0-capability-001")

    assert schema is not None
    assert [
        item["value"]
        for item in schema["param_options"]["edit_mode"]
    ] == [
        "EDIT_MODE_INPAINT_INSERTION",
        "EDIT_MODE_INPAINT_REMOVAL",
    ]


def test_image_mask_legacy_workflow_edit_modes_still_validate_for_backend_compatibility():
    for edit_mode in ("EDIT_MODE_OUTPAINT", "EDIT_MODE_BGSWAP"):
        valid = validate_params_with_catalog(
            "google",
            "image-mask-edit",
            "imagen-3.0-capability-001",
            {"edit_mode": edit_mode},
        )

        assert valid["edit_mode"] == edit_mode


def test_recontext_controls_allow_official_gemini_image_batch_and_ratios():
    schema = resolve_mode_controls("google", "image-recontext", "gemini-2.5-flash-image")

    assert schema is not None
    assert schema["mode"] == "image-recontext"
    assert schema["constraints"]["max_image_count"] == 10
    assert [item["value"] for item in schema["param_options"]["number_of_images"]] == list(range(1, 11))
    assert [item["value"] for item in schema["resolution_tiers"]] == ["1K", "2K", "4K"]
    assert "output_mime_type" not in schema["defaults"]
    assert "output_compression_quality" not in schema["defaults"]
    assert "output_mime_type" not in schema["param_options"]
    assert "output_compression_quality" not in schema["numeric_ranges"]

    aspect_values = [item["value"] for item in schema["aspect_ratios"]]
    assert aspect_values == ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
    assert "1:4" not in aspect_values


def test_gemini_image_generation_controls_do_not_expose_unsupported_output_mime():
    schema = resolve_mode_controls("google", "image-gen", "gemini-2.5-flash-image")

    assert schema is not None
    assert schema["constraints"]["max_image_count"] == 8
    assert "output_mime_type" not in schema["defaults"]
    assert "output_compression_quality" not in schema["defaults"]
    assert "output_mime_type" not in schema["param_options"]
    assert "output_compression_quality" not in schema["numeric_ranges"]

    with pytest.raises(ValueError, match="output_mime_type.*not supported"):
        validate_params_with_catalog(
            "google",
            "image-gen",
            "gemini-2.5-flash-image",
            {
                "number_of_images": 1,
                "aspect_ratio": "1:1",
                "resolution": "1K",
                "output_mime_type": "image/jpeg",
            },
        )


def test_gemini_api_runtime_image_generation_controls_hide_output_mime_for_imagen():
    schema = resolve_mode_controls("google", "image-gen", "imagen-4.0-generate-001")

    assert schema is not None
    assert "output_mime_type" in schema["defaults"]
    assert "output_mime_type" in schema["param_options"]
    assert schema["defaults"]["output_compression_quality"] == 100

    gemini_api_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="image-gen",
        runtime_api_mode="gemini_api",
    )
    vertex_schema = apply_video_mode_runtime_overrides(
        schema,
        provider="google",
        mode="image-gen",
        runtime_api_mode="vertex_ai",
    )

    assert "output_mime_type" not in gemini_api_schema["defaults"]
    assert "output_compression_quality" not in gemini_api_schema["defaults"]
    assert "output_mime_type" not in gemini_api_schema["param_options"]
    assert "output_compression_quality" not in gemini_api_schema["numeric_ranges"]
    assert "output_mime_type" in vertex_schema["defaults"]
    assert "output_mime_type" in vertex_schema["param_options"]


def test_recontext_catalog_validation_accepts_ten_and_rejects_eleven():
    valid = validate_params_with_catalog(
        "google",
        "image-recontext",
        "gemini-2.5-flash-image",
        {
            "number_of_images": 10,
            "aspect_ratio": "3:2",
            "resolution": "4K",
        },
    )

    assert valid["number_of_images"] == 10

    with pytest.raises(ValueError, match="Invalid number_of_images"):
        validate_params_with_catalog(
            "google",
            "image-recontext",
            "gemini-2.5-flash-image",
            {
                "number_of_images": 11,
                "aspect_ratio": "3:2",
                "resolution": "4K",
            },
        )


def test_gemini_recontext_prompt_distinguishes_scene_recontext_from_background_swap():
    prompt = GeminiRecontextImageService.build_recontext_prompt("replace the background", 1)

    assert "Recontext the provided subject" in prompt
    assert "not a mask-based background swap" in prompt
    assert "new scene context" in prompt


@pytest.mark.parametrize("mode", ["image-chat-edit", "image-recontext", "product-recontext"])
def test_google_service_uses_long_request_http_options_for_gemini_image_edit_modes(mode):
    service = GoogleService.__new__(GoogleService)
    service.api_key = "developer-api-key"
    service.use_vertex = False
    service.project = None
    service.location = "us-central1"
    service.http_options = HttpOptions(timeout=30000, use_default_timeout=True)
    service._pool_kwargs = {
        "api_key": "developer-api-key",
        "use_vertex": False,
        "project": None,
        "location": "us-central1",
        "http_options": service.http_options,
    }

    pool_kwargs = service._get_pool_kwargs_for_mode(mode)

    assert pool_kwargs["http_options"].timeout is None
    assert pool_kwargs["http_options"].use_default_timeout is False


def test_gemini_api_generate_images_config_rejects_unsupported_output_mime_type():
    generator = GeminiAPIImageGenerator(api_key="test-key")

    with pytest.raises(ValueError, match="output_mime_type.*not supported in Gemini API"):
        generator._build_config(
            model="imagen-4.0-generate-001",
            number_of_images=1,
            aspect_ratio="1:1",
            output_mime_type="image/jpeg",
            output_compression_quality=80,
        )


@pytest.mark.asyncio
async def test_recontext_with_gemini_flash_image_routes_to_recontext_service(monkeypatch):
    coordinator = ImageEditCoordinator()
    captured = {}

    async def fake_recontext_route(**kwargs):
        captured.update(kwargs)
        return [{"ok": True}]

    monkeypatch.setattr(
        coordinator,
        "_edit_with_gemini_recontext_service",
        fake_recontext_route,
    )

    result = await coordinator.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        mode="image-recontext",
        pool_kwargs={"use_vertex": True},
        chat_session_manager=object(),
        file_handler=object(),
        user_id="user-1",
        frontend_session_id="session-1",
    )

    assert result == [{"ok": True}]
    assert captured["model"] == "gemini-2.5-flash-image"
    assert captured["reference_images"] == {"raw": "data:image/png;base64,AAAA"}


@pytest.mark.asyncio
async def test_background_mode_does_not_route_gemini_image_to_conversational_service(monkeypatch):
    coordinator = ImageEditCoordinator.__new__(ImageEditCoordinator)
    coordinator._user_id = "user-1"
    coordinator._db = None
    coordinator._editor_cache = {}
    coordinator._config = {
        "api_mode": "vertex_ai",
        "vertex_ai_project_id": "vertex-project",
        "vertex_ai_location": "us-central1",
        "vertex_ai_credentials_json": "{}",
    }

    async def fail_if_conversational_route(**_kwargs):
        raise AssertionError("background mode must not route to Gemini conversational image editing")

    monkeypatch.setattr(
        coordinator,
        "_edit_with_conversational_image_service",
        fail_if_conversational_route,
    )

    with pytest.raises(ValueError, match="not compatible with Vertex Imagen edit_image API"):
        await coordinator.edit_image(
            prompt="replace the background with a boutique store",
            model="gemini-2.5-flash-image",
            reference_images={"raw": "data:image/png;base64,AAAA"},
            mode="image-background-edit",
            pool_kwargs={"use_vertex": True},
            chat_session_manager=object(),
            file_handler=object(),
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_recontext_route_uses_vertex_config_for_gemini_pool_kwargs(monkeypatch):
    coordinator = ImageEditCoordinator.__new__(ImageEditCoordinator)
    coordinator._user_id = "user-1"
    coordinator._db = None
    coordinator._editor_cache = {}
    coordinator._config = {
        "api_mode": "vertex_ai",
        "vertex_ai_project_id": "vertex-project",
        "vertex_ai_location": "us-central1",
        "vertex_ai_credentials_json": "{}",
    }
    credentials = object()
    captured = {}

    monkeypatch.setattr(
        coordinator,
        "_build_vertex_credentials_object",
        lambda: credentials,
        raising=False,
    )

    async def fake_recontext_route(**kwargs):
        captured.update(kwargs)
        return [{"ok": True}]

    monkeypatch.setattr(
        coordinator,
        "_edit_with_gemini_recontext_service",
        fake_recontext_route,
    )

    result = await coordinator.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        mode="image-recontext",
        pool_kwargs={
            "api_key": "developer-api-key",
            "use_vertex": False,
            "http_options": object(),
        },
        chat_session_manager=object(),
        file_handler=object(),
        user_id="user-1",
        frontend_session_id="session-1",
    )

    assert result == [{"ok": True}]
    assert captured["pool_kwargs"]["use_vertex"] is True
    assert captured["pool_kwargs"]["project"] == "vertex-project"
    assert captured["pool_kwargs"]["location"] == "us-central1"
    assert captured["pool_kwargs"]["credentials"] is credentials


@pytest.mark.asyncio
async def test_chat_edit_uses_gemini_api_even_when_vertex_config_is_active(monkeypatch):
    coordinator = ImageEditCoordinator.__new__(ImageEditCoordinator)
    coordinator._user_id = "user-1"
    coordinator._db = None
    coordinator._editor_cache = {}
    coordinator._config = {
        "api_mode": "vertex_ai",
        "gemini_api_key": "configured-api-key",
        "vertex_ai_project_id": "vertex-project",
        "vertex_ai_location": "us-central1",
        "vertex_ai_credentials_json": "{}",
    }
    captured = {}

    def fail_if_vertex_credentials_are_built():
        raise AssertionError("image-chat-edit must not build a Vertex AI client")

    monkeypatch.setattr(
        coordinator,
        "_build_vertex_credentials_object",
        fail_if_vertex_credentials_are_built,
        raising=False,
    )

    async def fake_conversational_route(**kwargs):
        captured.update(kwargs)
        return [{"ok": True}]

    monkeypatch.setattr(
        coordinator,
        "_edit_with_conversational_image_service",
        fake_conversational_route,
    )

    result = await coordinator.edit_image(
        prompt="make the product photo brighter",
        model="gemini-3.1-flash-image-preview",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        mode="image-chat-edit",
        pool_kwargs={
            "api_key": "developer-api-key",
            "use_vertex": True,
            "project": "vertex-project",
            "location": "us-central1",
            "http_options": object(),
        },
        chat_session_manager=object(),
        file_handler=object(),
        user_id="user-1",
        frontend_session_id="session-1",
    )

    assert result == [{"ok": True}]
    assert captured["model"] == "gemini-3.1-flash-image-preview"
    assert captured["pool_kwargs"]["use_vertex"] is False
    assert captured["pool_kwargs"]["api_key"] == "developer-api-key"
    assert "credentials" not in captured["pool_kwargs"]
    assert "project" not in captured["pool_kwargs"]
    assert "location" not in captured["pool_kwargs"]


@pytest.mark.asyncio
async def test_gemini_recontext_service_uses_official_chat_mode_for_image_editing():
    create_calls = []
    send_calls = []

    class FakeInlineData:
        data = b"fake-image"
        mime_type = "image/png"

    class FakePart:
        inline_data = FakeInlineData()
        text = None

    class FakeContent:
        parts = [FakePart()]

    class FakeCandidate:
        content = FakeContent()

    class FakeResponse:
        candidates = [FakeCandidate()]

    class FakeChat:
        def send_message(self, **kwargs):
            send_calls.append(kwargs)
            return FakeResponse()

    class FakeChats:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    service = GeminiRecontextImageService(
        chat_session_manager=object(),
        file_handler=object(),
        client=FakeClient(),
        use_vertex=True,
    )

    result = await service.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        user_id="user-1",
        frontend_session_id="session-1",
    )

    assert result[0]["url"] == "data:image/png;base64,ZmFrZS1pbWFnZQ=="
    assert create_calls[0]["model"] == "gemini-2.5-flash-image"
    assert getattr(create_calls[0]["config"], "image_config", None) is None
    assert len(send_calls) == 1
    assert any(
        getattr(part, "text", "") and "Recontext the provided subject" in part.text
        for part in send_calls[0]["message"]
    )
    assert any(
        getattr(part, "text", "") and "put the product on a summer desk" in part.text
        for part in send_calls[0]["message"]
    )


@pytest.mark.asyncio
async def test_gemini_recontext_service_passes_vertex_credentials_to_client_pool(monkeypatch):
    captured = {}
    credentials = object()

    class FakeInlineData:
        data = b"fake-image"
        mime_type = "image/png"

    class FakePart:
        inline_data = FakeInlineData()
        text = None

    class FakeContent:
        parts = [FakePart()]

    class FakeCandidate:
        content = FakeContent()

    class FakeResponse:
        candidates = [FakeCandidate()]

    class FakeChat:
        def send_message(self, **kwargs):
            return FakeResponse()

    class FakeChats:
        def create(self, **kwargs):
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    class FakePool:
        def get_client(self, **kwargs):
            captured.update(kwargs)
            return FakeClient()

    monkeypatch.setattr(
        "app.services.gemini.geminiapi.recontext_image_service.get_client_pool",
        lambda: FakePool(),
    )

    service = GeminiRecontextImageService(
        chat_session_manager=object(),
        file_handler=object(),
        api_key="developer-api-key",
        use_vertex=True,
        project="vertex-project",
        location="us-central1",
        credentials=credentials,
    )

    result = await service.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        user_id="user-1",
    )

    assert len(result) == 1
    assert captured["vertexai"] is True
    assert captured["project"] == "vertex-project"
    assert captured["location"] == "us-central1"
    assert captured["credentials"] is credentials


@pytest.mark.asyncio
async def test_gemini_recontext_service_extracts_images_from_response_parts_without_candidates():
    class FakeInlineData:
        data = b"fake-image-from-parts"
        mime_type = "image/png"

    class FakePart:
        inline_data = FakeInlineData()
        text = None

    class FakeResponse:
        candidates = []
        parts = [FakePart()]

    class FakeChat:
        def send_message(self, **kwargs):
            return FakeResponse()

    class FakeChats:
        def create(self, **kwargs):
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    service = GeminiRecontextImageService(
        chat_session_manager=object(),
        file_handler=object(),
        client=FakeClient(),
        use_vertex=True,
    )

    result = await service.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        user_id="user-1",
    )

    assert result[0]["url"] == "data:image/png;base64,ZmFrZS1pbWFnZS1mcm9tLXBhcnRz"


@pytest.mark.asyncio
async def test_gemini_recontext_service_rejects_developer_api_unsupported_output_mime_type():
    captured = {}

    class FakeInlineData:
        data = b"fake-image"
        mime_type = "image/png"

    class FakePart:
        inline_data = FakeInlineData()
        text = None

    class FakeContent:
        parts = [FakePart()]

    class FakeCandidate:
        content = FakeContent()

    class FakeResponse:
        candidates = [FakeCandidate()]

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        models = FakeModels()

    service = GeminiRecontextImageService(
        chat_session_manager=object(),
        file_handler=object(),
        client=FakeClient(),
        use_vertex=False,
    )

    with pytest.raises(ValueError, match="output_mime_type.*not supported in Gemini API"):
        await service.edit_image(
            prompt="put the product on a summer desk",
            model="gemini-2.5-flash-image",
            reference_images={"raw": "data:image/png;base64,AAAA"},
            image_aspect_ratio="1:1",
            output_mime_type="image/jpeg",
            output_compression_quality=80,
        )

    assert captured == {}


@pytest.mark.asyncio
async def test_gemini_recontext_service_prefers_single_official_chat_request_for_ten_outputs():
    create_calls = []
    send_calls = []

    class FakeInlineData:
        def __init__(self, index):
            self.data = f"fake-image-{index}".encode()
            self.mime_type = "image/png"

    class FakePart:
        def __init__(self, index):
            self.inline_data = FakeInlineData(index)
            self.text = None

    class FakeContent:
        def __init__(self, count):
            self.parts = [FakePart(index) for index in range(count)]

    class FakeCandidate:
        def __init__(self, count):
            self.content = FakeContent(count)

    class FakeResponse:
        def __init__(self, count):
            self.candidates = [FakeCandidate(count)]

    class FakeChat:
        def send_message(self, **kwargs):
            send_calls.append(kwargs)
            return FakeResponse(10)

    class FakeChats:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    service = GeminiRecontextImageService(
        chat_session_manager=object(),
        file_handler=object(),
        client=FakeClient(),
        use_vertex=True,
    )

    result = await service.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        number_of_images=10,
    )

    assert len(create_calls) == 1
    assert len(send_calls) == 1
    assert len(result) == 10
    assert "Return exactly 10 separate image parts" in send_calls[0]["message"][0].text
    assert getattr(create_calls[0]["config"], "image_config", None) is None
    assert getattr(create_calls[0]["config"], "safety_settings", None) is None


@pytest.mark.asyncio
async def test_gemini_recontext_service_returns_partial_official_outputs_with_warning_text():
    send_calls = []

    class FakeInlineData:
        def __init__(self, index):
            self.data = f"fake-image-{index}".encode()
            self.mime_type = "image/png"

    class FakePart:
        def __init__(self, index):
            self.inline_data = FakeInlineData(index)
            self.text = None

    class FakeContent:
        def __init__(self, count):
            self.parts = [FakePart(index) for index in range(count)]

    class FakeCandidate:
        def __init__(self, count):
            self.content = FakeContent(count)

    class FakeResponse:
        def __init__(self, count):
            self.candidates = [FakeCandidate(count)]

    class FakeChat:
        def send_message(self, **kwargs):
            send_calls.append(kwargs)
            return FakeResponse(7)

    class FakeChats:
        def create(self, **kwargs):
            return FakeChat()

    class FakeClient:
        chats = FakeChats()

    service = GeminiRecontextImageService(
        chat_session_manager=object(),
        file_handler=object(),
        client=FakeClient(),
        use_vertex=True,
    )

    result = await service.edit_image(
        prompt="put the product on a summer desk",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        number_of_images=10,
    )

    assert len(send_calls) == 1
    assert len(result) == 7
    assert result[0]["text"] == "模型返回 7/10 张图片，已显示实际返回结果。"
    assert "Return exactly 10 separate image parts" in send_calls[0]["message"][0].text


@pytest.mark.asyncio
async def test_recontext_rejects_imagen_edit_model_before_mask_edit_path(monkeypatch):
    coordinator = ImageEditCoordinator()

    monkeypatch.setattr(coordinator, "_require_vertex_ai", lambda _mode: None)
    monkeypatch.setattr(
        coordinator,
        "get_recontext_editor",
        lambda: pytest.fail("Recontext must not call Vertex edit_image for deprecated Imagen edit models"),
    )

    with pytest.raises(ValueError, match="requires a Gemini image model"):
        await coordinator.edit_image(
            prompt="put the product on a summer desk",
            model="imagen-3.0-capability-001",
            reference_images={"raw": "data:image/png;base64,AAAA"},
            mode="image-recontext",
            pool_kwargs={"use_vertex": True},
            chat_session_manager=object(),
            file_handler=object(),
            user_id="user-1",
            frontend_session_id="session-1",
        )


@pytest.mark.asyncio
async def test_gemini_image_model_routes_by_selected_model_not_edit_mode(monkeypatch):
    coordinator = ImageEditCoordinator()
    captured = {}

    async def fake_conversational_route(**kwargs):
        captured.update(kwargs)
        return [{"ok": True}]

    monkeypatch.setattr(
        coordinator,
        "_edit_with_conversational_image_service",
        fake_conversational_route,
    )

    result = await coordinator.edit_image(
        prompt="replace the marked object with a red bow",
        model="gemini-2.5-flash-image",
        reference_images={"raw": "data:image/png;base64,AAAA"},
        mode="image-inpainting",
        pool_kwargs={"use_vertex": True},
        chat_session_manager=object(),
        file_handler=object(),
        user_id="user-1",
        frontend_session_id="session-1",
    )

    assert result == [{"ok": True}]
    assert captured["model"] == "gemini-2.5-flash-image"
    assert captured["reference_images"] == {"raw": "data:image/png;base64,AAAA"}
