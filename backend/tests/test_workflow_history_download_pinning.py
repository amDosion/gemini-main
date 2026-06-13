from app.services.agent import workflow_history_image_service as image_service
from app.services.agent import workflow_history_media_service as media_service


class _FakeResponse:
    status_code = 200
    content = b"payload"

    def __init__(self, content_type: str):
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None


class _FakeSyncClient:
    def __init__(self, *, events, content_type: str, **kwargs):
        self.events = events
        self.content_type = content_type
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, url, *, headers):
        self.events.append(("get", url, headers["User-Agent"]))
        return _FakeResponse(self.content_type)


def test_workflow_history_image_external_download_installs_dns_pinning(monkeypatch):
    events = []

    def fake_client(**kwargs):
        return _FakeSyncClient(events=events, content_type="image/png", **kwargs)

    def fake_pin(client):
        events.append(("pin", client.kwargs["timeout"]))

    monkeypatch.setattr(image_service.httpx, "Client", fake_client)
    monkeypatch.setattr(image_service, "validate_outbound_http_url", lambda url: url)
    monkeypatch.setattr(image_service, "pin_sync_client_for_outbound_guard", fake_pin)

    payload, content_type, final_url = image_service._download_workflow_image_binary(
        "https://cdn.example.com/image.png",
        "https://app.example.com",
        inherited_headers={"Authorization": "Bearer secret"},
    )

    assert payload == b"payload"
    assert content_type == "image/png"
    assert final_url == "https://cdn.example.com/image.png"
    assert events == [
        ("pin", image_service._WORKFLOW_IMAGE_REQUEST_TIMEOUT_SECONDS),
        ("get", "https://cdn.example.com/image.png", "WorkflowHistoryImageDownloader/1.0"),
    ]


def test_workflow_history_image_previews_reject_svg_data_url():
    result = image_service.build_workflow_image_previews(
        "exec-svg-preview",
        ["data:image/svg+xml;base64,PHN2Zy8+"],
        "https://app.example.com",
        inherited_headers={},
    )

    assert result["images"] == []
    assert result["skippedCount"] == 1
    assert result["skipped"][0]["sourceUrl"].startswith("data:image/svg+xml;base64,")
    assert result["skipped"][0]["error"] == "unsupported preview mime type: image/svg+xml"


def test_workflow_history_media_external_download_installs_dns_pinning(monkeypatch):
    events = []

    def fake_client(**kwargs):
        return _FakeSyncClient(events=events, content_type="video/mp4", **kwargs)

    def fake_pin(client):
        events.append(("pin", client.kwargs["timeout"]))

    monkeypatch.setattr(media_service.httpx, "Client", fake_client)
    monkeypatch.setattr(media_service, "validate_outbound_http_url", lambda url: url)
    monkeypatch.setattr(media_service, "pin_sync_client_for_outbound_guard", fake_pin)

    payload, content_type, final_url = media_service.download_workflow_media_binary(
        "https://cdn.example.com/video.mp4",
        "https://app.example.com",
        inherited_headers={"Cookie": "session=secret"},
        media_kind="video",
    )

    assert payload == b"payload"
    assert content_type == "video/mp4"
    assert final_url == "https://cdn.example.com/video.mp4"
    assert events == [
        ("pin", media_service._WORKFLOW_MEDIA_REQUEST_TIMEOUT_SECONDS),
        ("get", "https://cdn.example.com/video.mp4", "WorkflowHistoryMediaDownloader/1.0"),
    ]


def test_workflow_history_media_download_accepts_base64_data_url():
    payload, content_type, final_url = media_service.download_workflow_media_binary(
        "data:audio/wav;base64,YWJj",
        "https://app.example.com",
        inherited_headers={},
        media_kind="audio",
    )

    assert payload == b"abc"
    assert content_type == "audio/wav"
    assert final_url == "data:audio/wav;base64,YWJj"


def test_workflow_history_media_download_rejects_non_base64_data_url():
    try:
        media_service.download_workflow_media_binary(
            "data:audio/wav,raw-bytes",
            "https://app.example.com",
            inherited_headers={},
            media_kind="audio",
        )
    except ValueError as exc:
        assert str(exc) == "inline media data urls must be base64 encoded"
    else:
        raise AssertionError("non-base64 inline media must be rejected")


def test_workflow_history_media_download_rejects_invalid_base64_payload():
    try:
        media_service.download_workflow_media_binary(
            "data:video/mp4;base64,not-valid!",
            "https://app.example.com",
            inherited_headers={},
            media_kind="video",
        )
    except ValueError as exc:
        assert str(exc) == "invalid base64 media payload"
    else:
        raise AssertionError("invalid base64 inline media must be rejected")


def test_workflow_history_media_download_rejects_oversized_inline_payload():
    try:
        media_service.download_workflow_media_binary(
            "data:audio/wav;base64,YWJjZA==",
            "https://app.example.com",
            inherited_headers={},
            media_kind="audio",
            max_bytes=3,
        )
    except ValueError as exc:
        assert str(exc) == "inline media data too large (> 3 bytes)"
    else:
        raise AssertionError("oversized inline media must be rejected")


def test_workflow_history_media_previews_skip_oversized_inline_payload():
    result = media_service.build_workflow_media_previews(
        "exec-audio-preview",
        "audio",
        ["data:audio/wav;base64,YWJjZA=="],
        "https://app.example.com",
        "/api/workflows/history/exec-audio-preview/audio/items/{index}",
        max_bytes_per_item=3,
    )

    assert result["items"] == []
    assert result["skippedCount"] == 1
    assert result["skipped"][0]["sourceUrl"].startswith("data:audio/wav;base64,")
    assert result["skipped"][0]["error"] == "inline media data too large (> 3 bytes)"
