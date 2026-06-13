import pytest
from pydantic import ValidationError

from app.services.gemini.geminiapi import main as geminiapi_main


def test_layerdoc_accepts_canvas_at_pixel_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_DIMENSION", 16)
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_PIXELS", 16)

    doc = geminiapi_main.LayerDoc.model_validate(
        {
            "width": 4,
            "height": 4,
            "layers": [],
        }
    )

    assert doc.width == 4
    assert doc.height == 4


def test_layerdoc_rejects_canvas_over_pixel_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_DIMENSION", 16)
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_PIXELS", 16)

    with pytest.raises(ValidationError, match="LayerDoc canvas area"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 5,
                "height": 4,
                "layers": [],
            }
        )


def test_layerdoc_rejects_too_many_layers(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_LAYERS", 1)

    with pytest.raises(ValidationError, match="LayerDoc layers"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 16,
                "height": 16,
                "layers": [
                    {"id": "a", "type": "gradient"},
                    {"id": "b", "type": "gradient"},
                ],
            }
        )


def test_text_layer_rejects_large_local_bbox(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_DIMENSION", 16)
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_LOCAL_PIXELS", 16)

    with pytest.raises(ValidationError, match="TextLayer.bbox area"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 16,
                "height": 16,
                "layers": [
                    {
                        "id": "text",
                        "type": "text",
                        "text": "hello",
                        "bbox": [0, 0, 5, 4],
                    }
                ],
            }
        )


def test_shape_layer_rejects_non_positive_local_bbox(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_DIMENSION", 16)
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_LOCAL_PIXELS", 16)

    with pytest.raises(ValidationError, match="ShapeLayer.bbox dimensions"):
        geminiapi_main.LayerDoc.model_validate(
            {
                "width": 16,
                "height": 16,
                "layers": [
                    {
                        "id": "shape",
                        "type": "shape",
                        "shape": "rect",
                        "bbox": [0, 0, 0, 4],
                    }
                ],
            }
        )
