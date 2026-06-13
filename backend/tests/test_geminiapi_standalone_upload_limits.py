import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.services.gemini.geminiapi import main as geminiapi_main


def _upload(data: bytes, filename: str = "image.png") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data))


async def test_read_upload_file_limited_accepts_payload_at_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_IMAGE_UPLOAD_BYTES", 4)

    data = await geminiapi_main._read_upload_file_limited(_upload(b"1234"))

    assert data == b"1234"


async def test_read_upload_file_limited_rejects_payload_over_limit(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_IMAGE_UPLOAD_BYTES", 4)

    with pytest.raises(HTTPException) as exc_info:
        await geminiapi_main._read_upload_file_limited(_upload(b"12345"))

    assert exc_info.value.status_code == 413


async def test_mask_vectorize_batch_reports_oversized_file_without_vectorizing(monkeypatch):
    monkeypatch.setattr(geminiapi_main, "MAX_IMAGE_UPLOAD_BYTES", 4)

    result = await geminiapi_main.mask_vectorize_batch(images=[_upload(b"12345", "big.png")])
    payload = result.body.decode("utf-8")

    assert '"total":1' in payload
    assert '"success_count":0' in payload
    assert "maximum size" in payload
