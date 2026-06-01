import pytest

from app.services.tongyi.speech_generation import TongyiSpeechGenerationService
from app.services.tongyi.virtual_tryon import TongyiVirtualTryOnService


class _CapturingSpeechService(TongyiSpeechGenerationService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        self.payload = {}

    async def _post(self, payload: dict) -> dict:
        self.payload = payload
        return {
            "request_id": "req-123",
            "output": {
                "audio": {
                    "url": "https://example.test/speech.wav",
                },
            },
        }


@pytest.mark.asyncio
async def test_tongyi_speech_payload_uses_qwen_tts_contract() -> None:
    service = _CapturingSpeechService()

    result = await service.generate_speech(
        text="你好，欢迎使用语音合成。",
        model="qwen-tts",
        voice="Cherry",
    )

    assert service.payload == {
        "model": "qwen-tts",
        "input": {
            "text": "你好，欢迎使用语音合成。",
            "voice": "Cherry",
        },
    }
    assert result["url"] == "https://example.test/speech.wav"
    assert result["mime_type"] == "audio/wav"
    assert result["voice"] == "Cherry"


class _CapturingTryOnService(TongyiVirtualTryOnService):
    def __init__(self) -> None:
        super().__init__(api_key="test-key", poll_interval=0)
        self.payload = {}

    async def _post_task(self, payload: dict) -> dict:
        self.payload = payload
        return {"output": {"task_id": "tryon-task", "task_status": "PENDING"}}

    async def _poll_task(self, task_id: str) -> dict:
        return {
            "output": {
                "task_id": task_id,
                "task_status": "SUCCEEDED",
                "image_url": "https://example.test/tryon.jpg",
            }
        }


@pytest.mark.asyncio
async def test_tongyi_tryon_maps_first_two_images_to_person_and_garment() -> None:
    service = _CapturingTryOnService()

    result = await service.virtual_tryon(
        {
            "raw": [
                {"url": "https://example.test/person.png"},
                {"url": "https://example.test/garment.png"},
            ]
        },
        model="aitryon-plus",
        resolution=1024,
        restore_face=False,
    )

    assert service.payload == {
        "model": "aitryon-plus",
        "input": {
            "person_image_url": "https://example.test/person.png",
            "top_garment_url": "https://example.test/garment.png",
        },
        "parameters": {
            "resolution": 1024,
            "restore_face": False,
        },
    }
    assert result["url"] == "https://example.test/tryon.jpg"
    assert result["mime_type"] == "image/jpeg"
