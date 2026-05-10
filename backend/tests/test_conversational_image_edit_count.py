import asyncio

import pytest

from app.services.gemini.geminiapi.conversational_image_edit_service import (
    ConversationalImageEditService,
)


class _FakeSession:
    chat_id = "chat-1"
    is_active = True
    model_name = "gemini-3.1-flash-image-preview"
    config_json = None


class _FakeChatSessionManager:
    def __init__(self, chat=None):
        self._chat_cache = {}
        self.chat = chat

    def list_user_chat_sessions(self, user_id, frontend_session_id):
        return [_FakeSession()]

    def get_chat_session(self, chat_id):
        return _FakeSession()

    def get_chat_object_from_cache(self, chat_id):
        return self.chat


@pytest.mark.asyncio
async def test_chat_edit_forwards_number_of_images_to_send_config(monkeypatch):
    captured = {}
    service = ConversationalImageEditService(
        chat_session_manager=_FakeChatSessionManager(),
        file_handler=object(),
    )

    async def fake_send_edit_message(**kwargs):
        captured["config"] = kwargs["config"]
        return {
            "images": [{"url": "data:image/png;base64,aGVsbG8=", "mime_type": "image/png"}],
            "thoughts": [],
            "text": None,
            "enhanced_prompt": None,
        }

    monkeypatch.setattr(service, "send_edit_message", fake_send_edit_message)

    await service.edit_image(
        prompt="make it brighter",
        model="gemini-3.1-flash-image-preview",
        reference_images={"raw": "data:image/png;base64,aGVsbG8="},
        user_id="user-1",
        frontend_session_id="session-1",
        number_of_images=3,
        image_aspect_ratio="1:1",
    )

    assert captured["config"]["number_of_images"] == 3


class _FakeInlineData:
    data = b"fake-image-bytes"
    mime_type = "image/png"


class _FakeImagePart:
    inline_data = _FakeInlineData()
    text = None
    thought = False


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeCandidate:
    def __init__(self, parts):
        self.content = _FakeContent(parts)


class _FakeResponse:
    def __init__(self):
        self.parts = []
        self.candidates = [
            _FakeCandidate([_FakeImagePart()]),
            _FakeCandidate([_FakeImagePart()]),
        ]


class _FakeSingleImageResponse:
    def __init__(self):
        self.parts = []
        self.candidates = [
            _FakeCandidate([_FakeImagePart()]),
        ]


class _FakeChat:
    def __init__(self):
        self.config = None

    async def send_message(self, message, config=None):
        self.config = config
        return _FakeResponse()


@pytest.mark.asyncio
async def test_chat_edit_extracts_all_candidate_images_and_uses_single_candidate_count():
    chat = _FakeChat()
    service = ConversationalImageEditService(
        chat_session_manager=_FakeChatSessionManager(chat=chat),
        file_handler=object(),
    )

    result = await service._send_edit_message_internal(
        chat_id="chat-1",
        prompt="make variations",
        reference_images=None,
        config={"number_of_images": 2},
        chat_session=_FakeSession(),
        model_name="gemini-3.1-flash-image-preview",
        should_include_image=False,
        client=object(),
    )

    assert getattr(chat.config, "candidate_count", None) == 1
    assert len(result["images"]) == 2


class _FakeChatWithoutMultiCandidateSupport:
    def __init__(self):
        self.candidate_counts = []

    async def send_message(self, message, config=None):
        candidate_count = getattr(config, "candidate_count", None)
        self.candidate_counts.append(candidate_count)
        if candidate_count and candidate_count > 1:
            raise RuntimeError(
                "400 INVALID_ARGUMENT. {'error': {'message': "
                "'Multiple candidates is not enabled for this model'}}"
            )
        return _FakeSingleImageResponse()


@pytest.mark.asyncio
async def test_chat_edit_uses_repeated_single_image_requests_for_multiple_images(monkeypatch):
    service = ConversationalImageEditService(
        chat_session_manager=_FakeChatSessionManager(),
        file_handler=object(),
    )
    monkeypatch.setattr(service, "_get_client", lambda: object())
    calls = []
    active_calls = 0
    max_active_calls = 0

    async def fake_send_edit_message_internal(**kwargs):
        nonlocal active_calls, max_active_calls
        assert kwargs["config"]["number_of_images"] == 1
        assert kwargs["skip_cache"] is True
        assert kwargs["cache_chat_object"] is False
        calls.append(kwargs)
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        await asyncio.sleep(0.01)
        active_calls -= 1
        return {
            "images": [{"url": "data:image/png;base64,aGVsbG8=", "mime_type": "image/png"}],
            "thoughts": [],
            "text": None,
            "enhanced_prompt": None,
        }

    monkeypatch.setattr(
        service,
        "_send_edit_message_internal",
        fake_send_edit_message_internal,
    )

    result = await service.send_edit_message(
        chat_id="chat-1",
        prompt="make variations",
        reference_images=None,
        config={"number_of_images": 3},
        user_id="user-1",
        frontend_session_id="session-1",
    )

    assert len(calls) == 3
    assert max_active_calls > 1
    assert len(result["images"]) == 3
