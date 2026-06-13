import pytest
from pydantic import ValidationError

from app.services.gemini.geminiapi import main as geminiapi_main


def test_generate_image_request_rejects_too_many_images():
    with pytest.raises(ValidationError):
        geminiapi_main.GenerateImageReq(
            prompt="make image",
            number_of_images=geminiapi_main.MAX_GENERATE_IMAGES + 1,
        )


def test_generate_image_request_rejects_unsupported_mime():
    with pytest.raises(ValidationError):
        geminiapi_main.GenerateImageReq(
            prompt="make image",
            output_mime_type="image/gif",
        )


def test_generate_image_request_rejects_overlong_prompt():
    with pytest.raises(ValidationError):
        geminiapi_main.GenerateImageReq(
            prompt="x" * (geminiapi_main.MAX_GENERATE_PROMPT_CHARS + 1)
        )


def test_layout_suggest_request_rejects_overlong_goal():
    with pytest.raises(ValidationError):
        geminiapi_main.LayoutSuggestReq(
            goal="x" * (geminiapi_main.MAX_LAYOUT_GOAL_CHARS + 1)
        )


def test_layout_suggest_request_rejects_canvas_area_over_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_DIMENSION", 16)
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_PIXELS", 16)

    with pytest.raises(ValidationError, match="LayoutSuggestReq canvas area"):
        geminiapi_main.LayoutSuggestReq(canvas_w=5, canvas_h=4)


def test_layout_suggest_request_rejects_too_many_text_boxes():
    with pytest.raises(ValidationError):
        geminiapi_main.LayoutSuggestReq(
            max_text_boxes=geminiapi_main.MAX_LAYOUT_TEXT_BOXES + 1
        )
