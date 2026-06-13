import base64
import logging
from types import SimpleNamespace

import pytest

from app.services.gemini.agent.tools import image_tools
from app.services.gemini.google_service import GoogleService
from app.services.gemini.vertexai.segmentation_service import SegmentationService


class FakeGoogleService:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeImageEditService:
    def __init__(self):
        self.calls = []

    async def edit_image(self, **kwargs):
        self.calls.append(kwargs)
        return ["edited"]


class FailingGoogleService:
    async def chat(self, **_kwargs):
        raise RuntimeError("provider echoed https://cdn.example.com/private/image.png?token=secret-token")


class FailingImageEditService:
    async def edit_image(self, **_kwargs):
        raise RuntimeError(
            "provider echoed prompt=secret-token "
            "image=https://cdn.example.com/private/source.png?token=secret-token"
        )


def test_image_tool_reference_rejects_local_file_inputs():
    assert image_tools._validate_image_tool_reference("https://cdn.example.com/a.png")
    assert image_tools._validate_image_tool_reference("data:image/png;base64,AAAA")
    assert image_tools._validate_image_tool_reference("gs://bucket/a.png")
    assert image_tools._validate_image_tool_reference("files/abc123")

    for raw in ("file:///etc/passwd", "/etc/passwd", r"C:\Users\me\secret.png", "ftp://host/a.png"):
        with pytest.raises(ValueError, match="unsupported image reference"):
            image_tools._validate_image_tool_reference(raw)


def test_edit_image_reference_allows_provider_uri_and_inline_image_data():
    png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\npayload").decode("ascii")

    assert image_tools._validate_edit_image_reference(
        "files/abc123",
        field_name="reference_image",
    ) == "files/abc123"
    assert image_tools._validate_edit_image_reference(
        png_b64,
        field_name="reference_image",
    ) == png_b64

    for raw in ("file:///etc/passwd", "/tmp/a.png", r"C:\Users\me\a.png", "relative/a.png"):
        with pytest.raises(ValueError, match="unsupported reference_image"):
            image_tools._validate_edit_image_reference(raw, field_name="reference_image")


@pytest.mark.asyncio
async def test_analyze_image_rejects_local_reference_before_provider_call():
    raw_url = "file:///etc/passwd"
    service = FakeGoogleService({"text": "{}"})

    result = await image_tools.analyze_image(raw_url, service)

    assert "unsupported image reference" in result["error"]
    assert service.calls == []


@pytest.mark.asyncio
async def test_edit_image_rejects_local_reference_before_provider_call():
    service = FakeImageEditService()

    result = await image_tools.edit_image_with_imagen(
        prompt="edit",
        reference_image="file:///etc/passwd",
        google_service=service,
    )

    assert result["success"] is False
    assert "local file references are not allowed" in result["error"]
    assert service.calls == []


@pytest.mark.asyncio
async def test_edit_image_rejects_local_mask_before_provider_call():
    service = FakeImageEditService()

    result = await image_tools.edit_image_with_imagen(
        prompt="edit",
        reference_image="files/source-image",
        mask="/tmp/mask.png",
        google_service=service,
    )

    assert result["success"] is False
    assert "local file references are not allowed" in result["error"]
    assert service.calls == []


@pytest.mark.asyncio
async def test_analyze_image_logs_url_summary_without_signed_query(caplog):
    raw_url = (
        "https://cdn.example.com/private/image.png"
        "?token=secret-token&X-Amz-Signature=secret-signature"
        "#private-fragment"
    )
    service = FakeGoogleService(
        {
            "text": (
                '{"content":"ok","style":"photo",'
                '"quality":{"clarity":8,"color":7}}'
            )
        }
    )

    with caplog.at_level(logging.INFO, logger=image_tools.logger.name):
        result = await image_tools.analyze_image(raw_url, service)

    assert result["image_url"] == raw_url
    assert service.calls[0]["messages"][0]["content"][1]["file_data"]["file_uri"] == raw_url

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://cdn.example.com path_len=18 query_params=2 fragment=yes" in log_text
    assert raw_url not in log_text
    assert "/private/image.png" not in log_text
    assert "secret-token" not in log_text
    assert "secret-signature" not in log_text
    assert "private-fragment" not in log_text


@pytest.mark.asyncio
async def test_analyze_image_error_log_summarizes_without_exc_info(caplog):
    raw_url = "https://cdn.example.com/private/image.png?token=secret-token"

    with caplog.at_level(logging.ERROR, logger=image_tools.logger.name):
        result = await image_tools.analyze_image(raw_url, FailingGoogleService())

    assert "secret-token" in result["error"]
    records = [
        record
        for record in caplog.records
        if record.name == image_tools.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "https://cdn.example.com path_len=18 query_params=1 fragment=no" in log_text
    assert "<redacted analysis_error; length=" in log_text
    assert raw_url not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_edit_image_error_log_summarizes_prompt_and_reference_without_exc_info(caplog):
    prompt = "private edit prompt secret-token"
    raw_url = "https://cdn.example.com/private/source.png?token=secret-token"

    with caplog.at_level(logging.ERROR, logger=image_tools.logger.name):
        result = await image_tools.edit_image_with_imagen(
            prompt=prompt,
            reference_image=raw_url,
            google_service=FailingImageEditService(),
        )

    assert result["success"] is False
    assert "secret-token" in result["error"]
    records = [
        record
        for record in caplog.records
        if record.name == image_tools.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert "<redacted edit_error; length=" in log_text
    assert "https://cdn.example.com path_len=19 query_params=1 fragment=no" in log_text
    assert prompt not in log_text
    assert raw_url not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_generate_mask_logs_prompt_summary_without_prompt_content(caplog):
    raw_url = "data:image/png;base64,PRIVATE_IMAGE_DATA"
    mask_prompt = "remove the badge with access-token=secret-token"
    service = FakeGoogleService({"text": "mask description"})

    with caplog.at_level(logging.INFO, logger=image_tools.logger.name):
        result = await image_tools.generate_mask(raw_url, mask_prompt, service)

    assert result is None
    sent_content = service.calls[0]["messages"][0]["content"]
    assert mask_prompt in sent_content[0]["text"]
    assert sent_content[1]["file_data"]["file_uri"] == raw_url

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted mask_prompt; length={len(mask_prompt)}>" in log_text
    assert f"data:image/png; length={len(raw_url)}" in log_text
    assert mask_prompt not in log_text
    assert "secret-token" not in log_text
    assert "PRIVATE_IMAGE_DATA" not in log_text


@pytest.mark.asyncio
async def test_generate_mask_rejects_local_reference_before_provider_call():
    service = FakeGoogleService({"text": "mask description"})

    result = await image_tools.generate_mask(
        "file:///etc/passwd",
        "mask prompt",
        service,
    )

    assert result is None
    assert service.calls == []


def test_segmentation_service_logs_prompt_summary_without_prompt_content(monkeypatch, caplog):
    prompt = "segment the private employee badge access-token=secret-token"

    class FakeModels:
        def __init__(self):
            self.calls = []

        def segment_image(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(generated_masks=[])

    fake_models = FakeModels()
    service = SegmentationService()
    monkeypatch.setattr(service, "_get_client", lambda: SimpleNamespace(models=fake_models))

    with caplog.at_level(logging.INFO, logger="app.services.gemini.vertexai.segmentation_service"):
        result = service.segment_image(
            image_base64="AAAA",
            mode="PROMPT",
            prompt=prompt,
        )

    assert result.success is False
    assert fake_models.calls, "segment_image should still receive the validated prompt source"

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert prompt not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_google_service_segmentation_delegate_logs_prompt_summary(caplog):
    prompt = "segment confidential logo token=secret-token"
    captured = {}

    class FakeSegmentationService:
        async def segment_image(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return [{"mask": "ok"}]

    service = GoogleService.__new__(GoogleService)
    service.use_official_sdk = False
    service.segmentation_service = FakeSegmentationService()

    with caplog.at_level(logging.INFO, logger="app.services.gemini.google_service"):
        result = await GoogleService.segment_image(
            service,
            image_path="AAAA",
            model="image-segmentation-001",
            prompt=prompt,
            mask_mode="MASK_MODE_PROMPT",
            extra_flag=True,
        )

    assert result == [{"mask": "ok"}]
    assert captured["args"][2] == prompt

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert prompt not in log_text
    assert "secret-token" not in log_text
