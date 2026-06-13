import pytest
from pydantic import ValidationError

from app.services.gemini.geminiapi import main as geminiapi_main


def test_text_layer_rejects_overlong_text(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_TEXT_CHARS", 4)

    with pytest.raises(ValidationError, match="TextLayer.text"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 16,
                "height": 16,
                "layers": [
                    {
                        "id": "text",
                        "type": "text",
                        "text": "12345",
                        "bbox": [0, 0, 4, 4],
                    }
                ],
            }
        )


def test_shape_layer_rejects_overlong_svg_path(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_SVG_PATH_CHARS", 8)

    with pytest.raises(ValidationError, match="ShapeLayer.svg_path_d"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 16,
                "height": 16,
                "layers": [
                    {
                        "id": "shape",
                        "type": "shape",
                        "shape": "path",
                        "bbox": [0, 0, 4, 4],
                        "svg_path_d": "M 0 0 L 1 1",
                    }
                ],
            }
        )


def test_raster_layer_rejects_overlong_mask_svg_path(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_SVG_PATH_CHARS", 8)

    with pytest.raises(ValidationError, match="RasterLayer.mask_svg_path"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 16,
                "height": 16,
                "layers": [
                    {
                        "id": "raster",
                        "type": "raster",
                        "mask_svg_path": "M 0 0 L 1 1",
                    }
                ],
            }
        )


def test_svg_path_renderer_returns_none_for_overlong_path(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_SVG_PATH_CHARS", 8)

    mask = geminiapi_main._render_svg_path_to_mask("M 0 0 L 1 1", 4, 4)

    assert mask is None
