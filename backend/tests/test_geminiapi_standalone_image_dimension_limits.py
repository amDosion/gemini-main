import base64
import io

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile

from app.services.gemini.geminiapi import main as geminiapi_main


def _png_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGBA", (width, height), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _upload_png(width: int, height: int) -> UploadFile:
    return UploadFile(filename="mask.png", file=io.BytesIO(_png_bytes(width, height)))


def _tight_image_limits(monkeypatch) -> None:
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_CANVAS_DIMENSION", 16)
    monkeypatch.setattr(geminiapi_main, "MAX_LAYERDOC_LOCAL_PIXELS", 16)


async def test_mask_vectorize_rejects_image_over_decoded_pixel_limit(monkeypatch):
    _tight_image_limits(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        await geminiapi_main.mask_vectorize(image=_upload_png(5, 4))

    assert exc_info.value.status_code == 413


async def test_render_compose_rejects_inline_raster_over_decoded_pixel_limit(monkeypatch):
    _tight_image_limits(monkeypatch)
    monkeypatch.setattr(geminiapi_main.app.state, "http_client", object(), raising=False)
    encoded = base64.b64encode(_png_bytes(5, 4)).decode("ascii")

    with pytest.raises(HTTPException) as exc_info:
        await geminiapi_main.render_compose(
            f'{{"width":16,"height":16,"layers":[{{"id":"r","type":"raster","png_base64":"{encoded}"}}]}}'
        )

    assert exc_info.value.status_code == 413


def test_render_layerdoc_rejects_asset_over_decoded_pixel_limit(monkeypatch):
    _tight_image_limits(monkeypatch)
    doc = geminiapi_main.LayerDoc.model_validate(
        {
            "width": 16,
            "height": 16,
            "layers": [
                {
                    "id": "asset",
                    "type": "raster",
                    "asset_url": "https://cdn.example.test/large.png",
                }
            ],
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        geminiapi_main._render_layerdoc_to_image(
            doc,
            preloaded_assets={"https://cdn.example.test/large.png": _png_bytes(5, 4)},
        )

    assert exc_info.value.status_code == 413
