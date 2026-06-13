import json

import pytest
from fastapi import HTTPException

from app.services.gemini.geminiapi import main as geminiapi_main


def _raster_doc(png_base64: str) -> str:
    return json.dumps(
        {
            "width": 16,
            "height": 16,
            "layers": [
                {
                    "id": "raster",
                    "type": "raster",
                    "png_base64": png_base64,
                }
            ],
        }
    )


def test_decode_inline_image_base64_limited_accepts_payload_at_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_INLINE_IMAGE_BYTES", 3)

    decoded = geminiapi_main._decode_inline_image_base64_limited(
        "QUJD",
        field_name="RasterLayer.png_base64",
    )

    assert decoded == b"ABC"


def test_decode_inline_image_base64_limited_rejects_encoded_payload_over_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_INLINE_IMAGE_BYTES", 3)

    with pytest.raises(HTTPException) as exc_info:
        geminiapi_main._decode_inline_image_base64_limited(
            "QUJDRA==",
            field_name="RasterLayer.png_base64",
        )

    assert exc_info.value.status_code == 413


async def test_render_compose_preserves_inline_base64_413(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_INLINE_IMAGE_BYTES", 3)
    monkeypatch.setattr(geminiapi_main.app.state, "http_client", object(), raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await geminiapi_main.render_compose(_raster_doc("QUJDRA=="))

    assert exc_info.value.status_code == 413
