import pytest

from app.services.gemini.agent import workflow_template_sample_service as sample_service
from app.services.gemini.agent.workflow_template_sample_service import (
    SAMPLE_TEMPLATE_ASSET_DIR,
    WorkflowTemplateSampleService,
)


def test_build_sample_input_inlines_trusted_remote_image_and_video_assets() -> None:
    service = WorkflowTemplateSampleService(db=None)  # type: ignore[arg-type]

    original_downloader = WorkflowTemplateSampleService._download_sample_remote_asset

    def _fake_download(url: str, *, asset_kind: str):
        if asset_kind == "image":
            return (b"image-bytes", "image/png")
        if asset_kind == "video":
            return (b"video-bytes", "video/mp4")
        return (b"audio-bytes", "audio/mpeg")

    WorkflowTemplateSampleService._download_sample_remote_asset = classmethod(  # type: ignore[method-assign]
        lambda cls, url, asset_kind: _fake_download(url, asset_kind=asset_kind)
    )
    try:
        sample_input = service.build_sample_input(
            {
                "id": "template-video-sample",
                "name": "Video Sample",
                "category": "多模态工作流",
                "config": {
                    "_templateMeta": {
                        "sampleInput": {
                            "imageUrl": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format",
                            "videoUrl": "https://storage.googleapis.com/cloud-samples-data/generative-ai/video/animals.mp4",
                            "task": "生成样例",
                        }
                    },
                    "nodes": [],
                },
            }
        )
    finally:
        WorkflowTemplateSampleService._download_sample_remote_asset = original_downloader  # type: ignore[assignment]

    assert str(sample_input["imageUrl"]).startswith("data:image/png;base64,")
    assert str(sample_input["videoUrl"]).startswith("data:video/mp4;base64,")


class _FakeStreamResponse:
    def __init__(self, status_code: int, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = dict(headers or {})
        self._chunks = list(chunks or [])

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield from self._chunks


class _FakeSampleAssetClient:
    def __init__(self, *, events, responses, **kwargs):
        self.events = events
        self.responses = responses
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def stream(self, method, url, *, headers):
        self.events.append(("stream", method, url, headers["User-Agent"]))
        return self.responses.pop(0)


def test_download_sample_remote_asset_installs_pinning_and_streams(monkeypatch) -> None:
    events = []
    responses = [
        _FakeStreamResponse(200, headers={"Content-Type": "image/png"}, chunks=[b"im", b"age"])
    ]

    def fake_client(**kwargs):
        return _FakeSampleAssetClient(events=events, responses=responses, **kwargs)

    def fake_pin(client):
        events.append(("pin", client.kwargs["timeout"]))

    monkeypatch.setattr(sample_service.httpx, "Client", fake_client)
    monkeypatch.setattr(sample_service, "pin_sync_client_for_outbound_guard", fake_pin)

    raw, mime_type = WorkflowTemplateSampleService._download_sample_remote_asset(
        "https://images.unsplash.com/photo-1",
        asset_kind="image",
    )

    assert raw == b"image"
    assert mime_type == "image/png"
    assert events == [
        ("pin", 20.0),
        (
            "stream",
            "GET",
            "https://images.unsplash.com/photo-1",
            "WorkflowTemplateSampleService/1.0",
        ),
    ]


def test_download_sample_remote_asset_rejects_untrusted_redirect(monkeypatch) -> None:
    events = []
    responses = [
        _FakeStreamResponse(302, headers={"Location": "https://evil.example/asset.png"})
    ]

    def fake_client(**kwargs):
        return _FakeSampleAssetClient(events=events, responses=responses, **kwargs)

    monkeypatch.setattr(sample_service.httpx, "Client", fake_client)
    monkeypatch.setattr(sample_service, "pin_sync_client_for_outbound_guard", lambda _client: None)

    with pytest.raises(ValueError, match="redirect host is not trusted"):
        WorkflowTemplateSampleService._download_sample_remote_asset(
            "https://images.unsplash.com/photo-1",
            asset_kind="image",
        )

    assert events == [
        (
            "stream",
            "GET",
            "https://images.unsplash.com/photo-1",
            "WorkflowTemplateSampleService/1.0",
        )
    ]


def test_build_sample_input_inlines_local_sample_assets_via_sample_scheme() -> None:
    first_frame = SAMPLE_TEMPLATE_ASSET_DIR / "video_first_frame_sample.jpg"
    last_frame = SAMPLE_TEMPLATE_ASSET_DIR / "video_last_frame_sample.jpg"
    source_video = SAMPLE_TEMPLATE_ASSET_DIR / "video_continuation_source_sample.mp4"
    assert first_frame.exists()
    assert last_frame.exists()
    assert source_video.exists()

    service = WorkflowTemplateSampleService(db=None)  # type: ignore[arg-type]

    sample_input = service.build_sample_input(
        {
            "config": {
                "_templateMeta": {
                    "sampleInput": {
                        "imageUrl": "sample://video_first_frame_sample.jpg",
                        "imageUrls": [
                            "sample://video_first_frame_sample.jpg",
                            "sample://video_last_frame_sample.jpg",
                        ],
                        "videoUrl": "sample://video_continuation_source_sample.mp4",
                    }
                }
            }
        }
    )

    assert str(sample_input["imageUrl"]).startswith("data:image/jpeg;base64,")
    assert str(sample_input["imageUrls"][0]).startswith("data:image/jpeg;base64,")
    assert str(sample_input["imageUrls"][1]).startswith("data:image/jpeg;base64,")
    assert str(sample_input["videoUrl"]).startswith("data:video/mp4;base64,")


def test_build_result_summary_includes_video_extension_and_subtitle_metadata() -> None:
    summary = WorkflowTemplateSampleService._build_result_summary(
        {
            "finalOutput": {
                "url": "/api/temp-images/video-1",
                "mime_type": "video/mp4",
                "continuation_strategy": "video_extension_chain",
                "video_extension_applied": 3,
                "total_duration_seconds": 29,
                "subtitle_mode": "vtt",
                "sidecar_files": [
                    {
                        "url": "/api/temp-images/subtitle-1",
                        "mime_type": "text/vtt",
                    }
                ],
            }
        }
    )

    assert summary["video_count"] == 1
    assert summary["video_extension_applied"] == 3
    assert summary["total_duration_seconds"] == 29
    assert summary["subtitle_mode"] == "vtt"
    assert summary["subtitle_file_count"] == 1
