import logging
from types import SimpleNamespace

import httpx
import pytest

from app.services.gemini.vertexai.expand_service import ExpandService
from app.services.gemini.vertexai.vertex_edit_base import VertexAIEditBase
from app.services.grok import image_generator as grok_image_generator_module
from app.services.grok.image_generator import ImageGenerator as GrokImageGenerator
from app.services.openai.chat_handler import ChatHandler as OpenAIChatHandler
from app.services.openai.image_editor import ImageEditor as OpenAIImageEditor
from app.services.openai.image_generator import ImageGenerator as OpenAIImageGenerator
from app.services.openai.model_manager import ModelManager as OpenAIModelManager
from app.services.openai.openai_service import OpenAIService
from app.services.openai.speech_generator import SpeechGenerator as OpenAISpeechGenerator
from app.services.openai.video_generator import VideoGenerator as OpenAIVideoGenerator
from app.services.tongyi import image_edit as tongyi_image_edit_module
from app.services.tongyi import image_expand as tongyi_image_expand_module
from app.services.tongyi.image_edit import ImageEditService
from app.services.tongyi.image_expand import ImageExpandService as TongyiImageExpandService
from app.services.tongyi.image_generation import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageGenerationService,
)


class _FakeOpenAIImagesClient:
    def __init__(self, generate_error=None):
        self.calls = []
        self.generate_error = generate_error

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.generate_error is not None:
            raise self.generate_error
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json="base64-image",
                    revised_prompt="provider revised prompt",
                )
            ]
        )


class _FakeOpenAIClient:
    def __init__(self, *, generate_error=None):
        self.images = _FakeOpenAIImagesClient(generate_error=generate_error)


@pytest.mark.asyncio
async def test_openai_image_generation_logs_prompt_summary_but_sends_raw_prompt(caplog):
    prompt = "private campaign concept with access-token=secret-token"
    base_url = "https://openai.example.test/private-token-path/v1"
    fake_client = _FakeOpenAIClient()
    generator = OpenAIImageGenerator(
        api_key="test-key",
        base_url=base_url,
        client=fake_client,  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.INFO, logger="app.services.openai.image_generator"):
        results = await generator.generate_image(prompt, "gpt-image-2", number_of_images=1)

    assert results[0]["url"].startswith("data:image/png;base64,")
    assert fake_client.images.calls[0]["prompt"] == prompt

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert "https://openai.example.test path_len=22 query_params=0 fragment=no" in log_text
    assert prompt not in log_text
    assert "secret-token" not in log_text
    assert "private-token-path" not in log_text


@pytest.mark.asyncio
async def test_openai_image_generation_error_log_is_summarized(caplog):
    error_text = "image provider failure with secret-token"
    fake_client = _FakeOpenAIClient(generate_error=RuntimeError(error_text))
    generator = OpenAIImageGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR, logger="app.services.openai.image_generator"):
        with pytest.raises(RuntimeError, match="image provider failure"):
            await generator.generate_image("private prompt", "gpt-image-2", number_of_images=1)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_openai_components_log_summarized_base_url(caplog):
    base_url = "https://openai.example.test/private-token-path/v1"
    fake_client = _FakeOpenAIClient()

    with caplog.at_level(logging.INFO):
        OpenAIService(api_key="test-key", api_url=base_url)
        OpenAIChatHandler(api_key="test-key", base_url=base_url, client=fake_client)
        OpenAIImageGenerator(api_key="test-key", base_url=base_url, client=fake_client)
        OpenAIImageEditor(api_key="test-key", base_url=base_url, client=fake_client)
        OpenAIVideoGenerator(api_key="test-key", base_url=base_url)
        OpenAISpeechGenerator(api_key="test-key", base_url=base_url, client=fake_client)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "private-token-path" not in log_text
    assert log_text.count("https://openai.example.test path_len=22 query_params=0 fragment=no") >= 6


class _FakeOpenAISpeech:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return b"audio-bytes"


class _FakeOpenAIAudio:
    def __init__(self, error=None):
        self.speech = _FakeOpenAISpeech(error=error)


class _FakeOpenAISpeechClient:
    def __init__(self, error=None):
        self.audio = _FakeOpenAIAudio(error=error)


@pytest.mark.asyncio
async def test_openai_speech_logs_text_summary_but_sends_raw_text(caplog):
    text = "private narration text with access-token=secret-token"
    fake_client = _FakeOpenAISpeechClient()
    generator = OpenAISpeechGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with caplog.at_level(logging.INFO, logger="app.services.openai.speech_generator"):
        result = await generator.generate_speech(text, voice="alloy")

    assert result["url"].startswith("data:audio/mpeg;base64,")
    assert fake_client.audio.speech.calls[0]["input"] == text

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted text; length={len(text)}>" in log_text
    assert text not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_openai_speech_error_log_is_summarized(caplog):
    error_text = "speech provider failure with secret-token"
    fake_client = _FakeOpenAISpeechClient(error=RuntimeError(error_text))
    generator = OpenAISpeechGenerator(api_key="test-key", client=fake_client)  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR, logger="app.services.openai.speech_generator"):
        with pytest.raises(RuntimeError, match="speech provider failure"):
            await generator.generate_speech("private narration", voice="alloy")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private narration" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


class _FakeOpenAICompletions:
    def __init__(self, error):
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        raise self.error


class _FakeOpenAIChat:
    def __init__(self, error):
        self.completions = _FakeOpenAICompletions(error)


class _FakeOpenAIChatClient:
    def __init__(self, error):
        self.chat = _FakeOpenAIChat(error)


async def _collect_stream(agen):
    return [chunk async for chunk in agen]


@pytest.mark.asyncio
async def test_openai_chat_error_log_is_summarized(caplog):
    error_text = "chat provider failure with secret-token"
    handler = OpenAIChatHandler(
        api_key="test-key",
        client=_FakeOpenAIChatClient(RuntimeError(error_text)),  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.ERROR, logger="app.services.openai.chat_handler"):
        with pytest.raises(RuntimeError, match="chat provider failure"):
            await handler.chat([{"role": "user", "content": "private prompt"}], "gpt-5")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_openai_stream_chat_error_log_and_chunk_are_summarized(caplog):
    error_text = "stream provider failure with secret-token"
    handler = OpenAIChatHandler(
        api_key="test-key",
        client=_FakeOpenAIChatClient(RuntimeError(error_text)),  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.ERROR, logger="app.services.openai.chat_handler"):
        chunks = await _collect_stream(
            handler.stream_chat([{"role": "user", "content": "private prompt"}], "gpt-5")
        )

    assert chunks[0]["chunk_type"] == "error"
    assert chunks[0]["error"] == "OpenAI stream chat failed"
    assert chunks[1]["chunk_type"] == "done"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_openai_image_edit_error_log_is_summarized(monkeypatch, caplog):
    error_text = "image edit provider failure with secret-token"
    editor = OpenAIImageEditor(api_key="test-key", client=_FakeOpenAIClient())  # type: ignore[arg-type]

    async def fake_extract_image_files(*args, **kwargs):
        return []

    async def fake_extract_mask_file(*args, **kwargs):
        return None

    async def fake_call_edit_api(*args, **kwargs):
        raise RuntimeError(error_text)

    monkeypatch.setattr(editor, "_extract_image_files", fake_extract_image_files)
    monkeypatch.setattr(editor, "_extract_mask_file", fake_extract_mask_file)
    monkeypatch.setattr(editor, "_call_edit_image_api", fake_call_edit_api)

    with caplog.at_level(logging.ERROR, logger="app.services.openai.image_editor"):
        with pytest.raises(RuntimeError, match="image edit provider failure"):
            await editor.edit_image("private edit prompt", "gpt-image-2")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private edit prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


class _FakeOpenAIModels:
    def __init__(self, error):
        self.error = error

    async def list(self):
        raise self.error


class _FakeOpenAIModelsClient:
    def __init__(self, error):
        self.models = _FakeOpenAIModels(error)


@pytest.mark.asyncio
async def test_openai_model_manager_error_log_is_summarized(caplog):
    error_text = "models provider failure with secret-token"
    manager = OpenAIModelManager(client=_FakeOpenAIModelsClient(RuntimeError(error_text)))  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR, logger="app.services.openai.model_manager"):
        with pytest.raises(RuntimeError, match="models provider failure"):
            await manager.get_available_models()

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


class _FakeGrokResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"url": "https://cdn.example.test/result.png"}]}


class _FakeGrokHTTPErrorResponse:
    def __init__(self, text: str, status_code: int = 502):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        raise httpx.HTTPStatusError(
            "provider failed",
            request=httpx.Request("POST", "https://grok.example.test/v1/images/generations"),
            response=self,
        )


class _FakeGrokAsyncClient:
    calls = []
    response = _FakeGrokResponse()

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, *, json, headers):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.response


@pytest.mark.asyncio
async def test_grok_image_generation_logs_prompt_summary_but_sends_raw_prompt(monkeypatch, caplog):
    prompt = "private visual prompt token=secret-token"
    _FakeGrokAsyncClient.calls = []
    _FakeGrokAsyncClient.response = _FakeGrokResponse()
    monkeypatch.setattr(grok_image_generator_module.httpx, "AsyncClient", _FakeGrokAsyncClient)
    generator = GrokImageGenerator(api_key="test-key", base_url="https://grok.example.test/v1")

    with caplog.at_level(logging.INFO, logger="app.services.grok.image_generator"):
        results = await generator.generate_image(prompt, "grok-imagine-1.0", n=1)

    assert results[0]["url"] == "https://cdn.example.test/result.png"
    assert _FakeGrokAsyncClient.calls[0]["json"]["prompt"] == prompt

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert prompt not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_grok_image_generation_http_error_logs_response_summary(monkeypatch, caplog):
    response_text = "provider error body with secret-token and private prompt"
    _FakeGrokAsyncClient.calls = []
    _FakeGrokAsyncClient.response = _FakeGrokHTTPErrorResponse(response_text)
    monkeypatch.setattr(grok_image_generator_module.httpx, "AsyncClient", _FakeGrokAsyncClient)
    generator = GrokImageGenerator(api_key="test-key", base_url="https://grok.example.test/v1")

    with caplog.at_level(logging.ERROR, logger="app.services.grok.image_generator"):
        with pytest.raises(httpx.HTTPStatusError):
            await generator.generate_image("private prompt", "grok-imagine-1.0", n=1)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted provider_error; length={len(response_text)}>" in log_text
    assert response_text not in log_text
    assert "secret-token" not in log_text
    assert "private prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


class _NoNetworkTongyiGenerationService(ImageGenerationService):
    def __init__(self):
        super().__init__(api_key="test-key")
        self.captured_request = None

    async def _generate_z_image(self, request):
        self.captured_request = request
        return [ImageGenerationResult(url="https://cdn.example.test/output.png")]


@pytest.mark.asyncio
async def test_tongyi_image_generation_logs_prompt_summaries_but_keeps_request_prompt(caplog):
    prompt = "private product shoot prompt token=secret-token"
    negative_prompt = "avoid confidential watermark token=negative-secret"
    service = _NoNetworkTongyiGenerationService()

    with caplog.at_level(logging.INFO, logger="app.services.tongyi.image_generation"):
        results = await service.generate(
            ImageGenerationRequest(
                model_id="z-image",
                prompt=prompt,
                negative_prompt=negative_prompt,
            )
        )

    assert results[0].url == "https://cdn.example.test/output.png"
    assert service.captured_request is not None
    assert service.captured_request.prompt == prompt
    assert service.captured_request.negative_prompt == negative_prompt

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert f"<redacted negative_prompt; length={len(negative_prompt)}>" in log_text
    assert prompt not in log_text
    assert negative_prompt not in log_text
    assert "secret-token" not in log_text
    assert "negative-secret" not in log_text


@pytest.mark.asyncio
async def test_tongyi_image_edit_logs_oss_url_summary_without_raw_url(caplog):
    image_url = "oss://dashscope/private/source.png?token=secret-token"
    service = ImageEditService(api_key="test-key")

    with caplog.at_level(logging.INFO, logger="app.services.tongyi.image_edit"):
        result = await service.process_reference_image(image_url, model="qwen-image-edit-plus")

    assert result == image_url

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"oss reference; length={len(image_url)}" in log_text
    assert image_url not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_tongyi_image_edit_logs_remote_upload_success_summary(monkeypatch, caplog):
    image_url = "https://cdn.example.test/private/source.png?token=secret-token#frag"
    oss_url = "oss://dashscope/private/uploaded.png?token=oss-secret"
    calls = []

    async def fake_upload_to_dashscope_async(*, image_url, api_key, model):
        calls.append({"image_url": image_url, "api_key": api_key, "model": model})
        return SimpleNamespace(success=True, oss_url=oss_url)

    monkeypatch.setattr(
        tongyi_image_edit_module,
        "upload_to_dashscope_async",
        fake_upload_to_dashscope_async,
    )
    service = ImageEditService(api_key="test-key")

    with caplog.at_level(logging.INFO, logger="app.services.tongyi.image_edit"):
        result = await service.process_reference_image(image_url, model="qwen-image-edit-plus")

    assert result == oss_url
    assert calls == [
        {
            "image_url": image_url,
            "api_key": "test-key",
            "model": "qwen-image-edit-plus",
        }
    ]

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://cdn.example.test path_len=19 query_params=1 fragment=yes" in log_text
    assert f"oss reference; length={len(oss_url)}" in log_text
    assert image_url not in log_text
    assert oss_url not in log_text
    assert "secret-token" not in log_text
    assert "oss-secret" not in log_text


@pytest.mark.asyncio
async def test_tongyi_image_edit_logs_local_upload_success_summary(
    monkeypatch,
    tmp_path,
    caplog,
):
    local_url = "/api/storage/local-files/private/source.png?token=secret-token"
    local_file = tmp_path / "source.png"
    local_file.write_bytes(b"local-image-bytes")
    oss_url = "oss://dashscope/private/local-upload.png?token=oss-secret"
    calls = []

    def fake_resolve_local_public_file_path(value):
        assert value == local_url
        return local_file

    async def fake_upload_bytes_to_dashscope_async(image_data, filename, api_key, model):
        calls.append(
            {
                "image_data": image_data,
                "filename": filename,
                "api_key": api_key,
                "model": model,
            }
        )
        return SimpleNamespace(success=True, oss_url=oss_url)

    monkeypatch.setattr(
        tongyi_image_edit_module,
        "resolve_local_public_file_path",
        fake_resolve_local_public_file_path,
    )
    monkeypatch.setattr(
        tongyi_image_edit_module,
        "upload_bytes_to_dashscope_async",
        fake_upload_bytes_to_dashscope_async,
    )
    service = ImageEditService(api_key="test-key")

    with caplog.at_level(logging.INFO, logger="app.services.tongyi.image_edit"):
        result = await service.process_reference_image(local_url, model="qwen-image-edit-plus")

    assert result == oss_url
    assert calls[0]["image_data"] == b"local-image-bytes"
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["model"] == "qwen-image-edit-plus"

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"relative reference; length={len(local_url)}" in log_text
    assert f"oss reference; length={len(oss_url)}" in log_text
    assert local_url not in log_text
    assert oss_url not in log_text
    assert "secret-token" not in log_text
    assert "oss-secret" not in log_text


@pytest.mark.asyncio
async def test_tongyi_image_edit_api_error_logs_response_summary(monkeypatch, caplog):
    error_text = "upstream echoed https://cdn.example.test/source.png?token=secret-token"

    class FakeResponse:
        status_code = 400
        text = error_text

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(tongyi_image_edit_module.httpx, "AsyncClient", FakeClient)
    service = ImageEditService(api_key="test-key")

    with caplog.at_level(logging.ERROR, logger="app.services.tongyi.image_edit"):
        with pytest.raises(Exception) as exc_info:
            await service.call_api(
                "https://dashscope.example.test/edit",
                {"input": {"image": "https://cdn.example.test/source.png?token=secret-token"}},
                use_oss_resolve=False,
            )

    error_result = str(exc_info.value)
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted dashscope_error; length={len(error_text)}>" in error_result
    assert f"<redacted dashscope_error; length={len(error_text)}>" in log_text
    assert "secret-token" not in error_result
    assert "secret-token" not in log_text
    assert "cdn.example.test/source.png" not in error_result
    assert "cdn.example.test/source.png" not in log_text


def test_tongyi_image_edit_extract_failure_logs_response_shape_without_values(caplog):
    service = ImageEditService(api_key="test-key")
    response_data = {
        "output": {
            "unexpected": [
                {
                    "image_url": "https://cdn.example.test/source.png?token=secret-token",
                    "prompt": "private prompt text",
                }
            ]
        }
    }

    with caplog.at_level(logging.ERROR, logger="app.services.tongyi.image_edit"):
        with pytest.raises(Exception):
            service.extract_image_urls(response_data, "qwen-image-edit-plus")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "dict_keys=1" in log_text
    assert "output_keys=1" in log_text
    assert "secret-token" not in log_text
    assert "cdn.example.test/source.png" not in log_text
    assert "private prompt text" not in log_text


def test_tongyi_image_expand_download_logs_url_summary_but_fetches_raw_url(monkeypatch, caplog):
    image_url = "https://cdn.example.test/private/source.png?token=secret-token#frag"
    calls = []

    class _FakeResponse:
        status_code = 200
        content = b"image-bytes"

    def fake_get_with_guard(url, timeout):
        calls.append({"url": url, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(
        tongyi_image_expand_module,
        "sync_get_with_redirect_guard",
        fake_get_with_guard,
    )

    with caplog.at_level(logging.INFO, logger="app.services.tongyi.image_expand"):
        result = TongyiImageExpandService.download_image(image_url)

    assert result == b"image-bytes"
    assert calls == [{"url": image_url, "timeout": 30}]

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://cdn.example.test path_len=19 query_params=1 fragment=yes" in log_text
    assert image_url not in log_text
    assert "secret-token" not in log_text
    assert "#frag" not in log_text


@pytest.mark.asyncio
async def test_gemini_expand_download_error_logs_url_summary(monkeypatch, caplog):
    from app.services.gemini.vertexai import expand_service as expand_service_module

    image_url = "https://cdn.example.test/private/source.png?token=secret-token#frag"

    async def fake_get_with_redirect_guard(_client, url, max_redirects):
        raise expand_service_module.httpx.RequestError(f"failed for {url}")

    monkeypatch.setattr(
        expand_service_module,
        "get_with_redirect_guard",
        fake_get_with_redirect_guard,
    )
    service = ExpandService()

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.vertexai.expand_service"):
        with pytest.raises(ValueError) as exc_info:
            await service._load_image_from_path(image_url)

    expected_summary = "https://cdn.example.test path_len=19 query_params=1 fragment=yes"
    error_text = str(exc_info.value)
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert expected_summary in error_text
    assert expected_summary in log_text
    assert image_url not in error_text
    assert image_url not in log_text
    assert "secret-token" not in error_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_gemini_expand_missing_local_file_error_summarizes_url():
    image_url = "/api/storage/local-files/private/source.png?token=secret-token"
    service = ExpandService()

    with pytest.raises(ValueError) as exc_info:
        await service._load_image_from_path(image_url)

    error_text = str(exc_info.value)
    assert f"relative reference; length={len(image_url)}" in error_text
    assert image_url not in error_text
    assert "secret-token" not in error_text


@pytest.mark.asyncio
async def test_gemini_expand_top_level_error_log_is_summarized(monkeypatch, caplog):
    prompt = "private expand prompt secret-token"
    service = ExpandService()

    monkeypatch.setattr(service, "_validate_expand_parameters", lambda *_args, **_kwargs: None)

    async def fake_expand_by_scale(*_args, **_kwargs):
        raise RuntimeError("provider echoed secret-token")

    monkeypatch.setattr(service, "_expand_by_scale", fake_expand_by_scale)

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.vertexai.expand_service"):
        with pytest.raises(RuntimeError):
            await service._expand_image_internal(
                "https://cdn.example.test/source.png?token=secret-token",
                prompt,
                model="imagen-3.0-capability-001",
                mode="scale",
            )

    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.vertexai.expand_service"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted expand_error; length=" in log_text
    assert "secret-token" not in log_text
    assert prompt not in log_text
    assert all(record.exc_info is None for record in records)


class _FakeVertexEditModels:
    def __init__(self):
        self.calls = []

    def edit_image(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(generated_images=[object()])


class _FakeVertexEditService(VertexAIEditBase):
    def __init__(self):
        self.models = _FakeVertexEditModels()
        self._client = SimpleNamespace(models=self.models)

    def _ensure_initialized(self):
        return None

    def validate_parameters(self, prompt, reference_images, config):
        return None

    def _apply_service_defaults(self, config):
        return config

    def _build_config(self, config):
        return SimpleNamespace()

    def _build_reference_images(self, reference_images, effective_config):
        return []

    def _process_response(self, response, output_mime_type="image/png"):
        return [{"url": "data:image/png;base64,ok"}]


def test_vertex_edit_base_logs_prompt_summary_but_sends_raw_prompt(caplog):
    prompt = "private edit prompt token=secret-token"
    service = _FakeVertexEditService()

    with caplog.at_level(logging.INFO, logger="app.services.gemini.vertexai.vertex_edit_base"):
        result = service.edit_image(prompt, reference_images={"image": "AAAA"}, config={})

    assert result == [{"url": "data:image/png;base64,ok"}]
    assert service.models.calls[0]["prompt"] == prompt

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted prompt; length={len(prompt)}>" in log_text
    assert prompt not in log_text
    assert "secret-token" not in log_text


def test_gemini_expand_parameter_error_redacts_long_prompt_value():
    prompt = "private expand prompt token=secret-token " * 80
    service = ExpandService()

    with pytest.raises(Exception) as exc_info:
        service._validate_expand_parameters(
            image_path="data:image/png;base64,AAAA",
            expand_prompt=prompt,
            model=next(iter(service.expand_models)),
            mode="scale",
        )

    error_text = str(exc_info.value)
    assert prompt not in error_text
    assert "secret-token" not in error_text
