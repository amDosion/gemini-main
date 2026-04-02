from app.services.agent.workflow_engine.image_pipeline import resolve_video_resolution
from app.services.agent.workflow_engine.media import build_video_generate_kwargs


class _DummyEngine:
    def _get_tool_arg(self, tool_args, *keys):
        for key in keys:
            if key in tool_args:
                return tool_args[key]
        return None

    def _to_int(self, value, default=None, minimum=None, maximum=None):
        if value in (None, ""):
            return default
        parsed = int(value)
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def _to_bool(self, value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return default

    def _extract_first_video_url(self, value):
        if isinstance(value, dict):
            return value.get("url")
        return value

    def _extract_first_image_url(self, value):
        if isinstance(value, dict):
            return value.get("url")
        return value

    def _resolve_video_resolution(self, value):
        return resolve_video_resolution(self, value)


def test_resolve_video_resolution_returns_official_google_resolution_tokens() -> None:
    engine = _DummyEngine()

    assert resolve_video_resolution(engine, "1K") == "720p"
    assert resolve_video_resolution(engine, "720p") == "720p"
    assert resolve_video_resolution(engine, "2K") == "1080p"
    assert resolve_video_resolution(engine, "1080p") == "1080p"
    assert resolve_video_resolution(engine, "4K") == "4k"
    assert resolve_video_resolution(engine, "2160p") == "4k"


def test_build_video_generate_kwargs_preserves_official_video_controls() -> None:
    engine = _DummyEngine()

    kwargs = build_video_generate_kwargs(
        engine,
        {
            "aspect_ratio": "16:9",
            "resolution": "4K",
            "duration_seconds": 8,
            "video_extension_count": 3,
            "negative_prompt": "no blur",
            "prompt_extend": True,
            "generate_audio": False,
            "person_generation": "allow_adult",
            "subtitle_mode": "vtt",
            "subtitle_language": "en-US",
            "subtitle_script": "Intro line",
            "storyboard_prompt": "Shot 1 close-up. Shot 2 model walk.",
            "source_video": {"provider_file_uri": "files/demo-video"},
        },
    )

    assert kwargs["resolution"] == "4k"
    assert kwargs["duration_seconds"] == 8
    assert kwargs["video_extension_count"] == 3
    assert kwargs["generate_audio"] is False
    assert kwargs["person_generation"] == "allow_adult"
    assert kwargs["subtitle_mode"] == "vtt"
    assert kwargs["subtitle_language"] == "en-US"
    assert kwargs["subtitle_script"] == "Intro line"
    assert kwargs["storyboard_prompt"] == "Shot 1 close-up. Shot 2 model walk."
    assert kwargs["source_video"]["provider_file_uri"] == "files/demo-video"
