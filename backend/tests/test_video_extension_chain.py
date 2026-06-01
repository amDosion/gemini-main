import pytest

from app.services.common import video_extension_chain
from app.services.common.video_extension_chain import run_last_frame_video_extension_chain


class _Frame:
    image_bytes = b"frame"
    mime_type = "image/png"


@pytest.mark.asyncio
async def test_extension_chain_generates_base_then_continuations_from_last_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    async def fake_generate(prompt: str, model: str, kwargs: dict) -> dict:
        calls.append({"prompt": prompt, "model": model, "kwargs": dict(kwargs)})
        index = len(calls) - 1
        return {
            "url": f"data:video/mp4;base64,c2VnbWVudC0{index}",
            "mime_type": "video/mp4",
            "job_id": f"job-{index}",
            "duration_seconds": 5,
            "filename": f"segment-{index}.mp4",
        }

    async def fake_load_video_bytes(source, *, fallback_mime_type="video/mp4", load_source_video=None):
        return b"video-bytes", fallback_mime_type

    async def fake_concat(segments, *, continuation_trim_seconds):
        assert continuation_trim_seconds == 1.0
        assert len(segments) == 3
        return b"joined"

    monkeypatch.setattr(video_extension_chain, "load_video_bytes_from_source", fake_load_video_bytes)
    monkeypatch.setattr(video_extension_chain, "extract_last_frame_image", lambda source: _Frame())
    monkeypatch.setattr(video_extension_chain, "concatenate_video_segments", fake_concat)

    result = await run_last_frame_video_extension_chain(
        provider_name="test",
        prompt="base prompt",
        model="text-video-model",
        request_kwargs={
            "seconds": "5",
            "resolution": "1080p",
            "storyboard_segments": ["segment one", "segment two"],
        },
        extension_count=2,
        generate_segment=fake_generate,
        continuation_model="image-video-model",
        segment_seconds=5,
    )

    assert [call["model"] for call in calls] == [
        "text-video-model",
        "image-video-model",
        "image-video-model",
    ]
    assert "source_image" not in calls[0]["kwargs"]
    assert calls[1]["kwargs"]["source_image"]["mime_type"] == "image/png"
    assert calls[2]["kwargs"]["source_image"]["mime_type"] == "image/png"
    assert "segment one" in calls[1]["prompt"]
    assert "segment two" in calls[2]["prompt"]
    assert result["continuation_strategy"] == "last_frame_bridge_chain"
    assert result["video_extension_count"] == 2
    assert result["video_extension_applied"] == 2
    assert result["segment_count"] == 3
    assert result["total_duration_seconds"] == 15
    assert result["extension_job_ids"] == ["job-0", "job-1", "job-2"]


@pytest.mark.asyncio
async def test_extension_chain_extends_existing_source_video_without_regenerating_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    async def fake_generate(prompt: str, model: str, kwargs: dict) -> dict:
        calls.append({"prompt": prompt, "model": model, "kwargs": dict(kwargs)})
        return {
            "url": "data:video/mp4;base64,Y29udGludWF0aW9u",
            "mime_type": "video/mp4",
            "job_id": "job-continuation",
            "duration_seconds": 8,
        }

    async def fake_load_video_bytes(source, *, fallback_mime_type="video/mp4", load_source_video=None):
        if isinstance(source, dict) and source.get("url") == "https://example.test/source.mp4":
            return b"source", "video/mp4"
        return b"continuation", fallback_mime_type

    async def fake_concat(segments, *, continuation_trim_seconds):
        assert [segment[0] for segment in segments] == [b"source", b"continuation"]
        return b"source-plus-continuation"

    monkeypatch.setattr(video_extension_chain, "load_video_bytes_from_source", fake_load_video_bytes)
    monkeypatch.setattr(video_extension_chain, "extract_last_frame_image", lambda source: _Frame())
    monkeypatch.setattr(video_extension_chain, "concatenate_video_segments", fake_concat)

    result = await run_last_frame_video_extension_chain(
        provider_name="test",
        prompt="continue source",
        model="image-video-model",
        request_kwargs={
            "source_video": {"url": "https://example.test/source.mp4"},
            "seconds": "8",
            "storyboard_segments": ["continue from last frame"],
        },
        extension_count=1,
        generate_segment=fake_generate,
        continuation_model="image-video-model",
        segment_seconds=8,
    )

    assert len(calls) == 1
    assert calls[0]["kwargs"]["source_image"]["url"].startswith("data:image/png;base64,")
    assert "source_video" not in calls[0]["kwargs"]
    assert result["segment_count"] == 2
    assert result["total_duration_seconds"] == 8
    assert result["continued_from_video"] is True


@pytest.mark.asyncio
async def test_extension_chain_generates_base_when_source_video_belongs_to_active_submode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    async def fake_generate(prompt: str, model: str, kwargs: dict) -> dict:
        calls.append({"prompt": prompt, "model": model, "kwargs": dict(kwargs)})
        return {
            "url": f"data:video/mp4;base64,c2VnbWVudC0{len(calls)}",
            "mime_type": "video/mp4",
            "job_id": f"job-{len(calls)}",
            "duration_seconds": 8,
        }

    async def fake_load_video_bytes(source, *, fallback_mime_type="video/mp4", load_source_video=None):
        return f"video-{len(calls)}".encode(), fallback_mime_type

    async def fake_concat(segments, *, continuation_trim_seconds):
        assert len(segments) == 2
        return b"joined-after-base"

    monkeypatch.setattr(video_extension_chain, "load_video_bytes_from_source", fake_load_video_bytes)
    monkeypatch.setattr(video_extension_chain, "extract_last_frame_image", lambda source: _Frame())
    monkeypatch.setattr(video_extension_chain, "concatenate_video_segments", fake_concat)

    result = await run_last_frame_video_extension_chain(
        provider_name="test",
        prompt="edit then continue",
        model="video-edit-model",
        request_kwargs={
            "source_video": {"url": "https://example.test/source.mp4"},
            "video_input_strategy": "video_edit",
            "seconds": "8",
        },
        extension_count=1,
        generate_segment=fake_generate,
        continuation_model="image-video-model",
        segment_seconds=8,
        treat_source_video_as_existing_base=False,
    )

    assert len(calls) == 2
    assert calls[0]["model"] == "video-edit-model"
    assert calls[0]["kwargs"]["source_video"]["url"] == "https://example.test/source.mp4"
    assert calls[1]["model"] == "image-video-model"
    assert "source_video" not in calls[1]["kwargs"]
    assert calls[1]["kwargs"]["source_image"]["mime_type"] == "image/png"
    assert result["continued_from_video"] is False
    assert result["total_duration_seconds"] == 16
