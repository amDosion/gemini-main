"""W02R-015: PDF extraction must enforce an upload size cap (DoS protection).

The /api/pdf/extract route read the whole upload into memory with no maximum
size, so a large document could exhaust worker memory. A bounded read must
reject oversized uploads with 413 before parsing.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(monkeypatch, max_bytes):
    from app.routers.tools import pdf as pdf_mod

    pdf_mod.set_pdf_service(lambda **kwargs: {"ok": True}, lambda: [], True)
    monkeypatch.setattr(pdf_mod, "MAX_PDF_BYTES", max_bytes)
    app = FastAPI()
    app.include_router(pdf_mod.router)
    return TestClient(app, raise_server_exceptions=False)


def test_oversized_pdf_rejected(monkeypatch):
    client = _client(monkeypatch, max_bytes=16)
    files = {"file": ("big.pdf", b"%PDF-1.7" + b"x" * 100, "application/pdf")}
    data = {"template_type": "invoice", "api_key": "k", "model_id": "m"}
    resp = client.post("/api/pdf/extract", files=files, data=data)
    assert resp.status_code == 413


def test_small_pdf_passes_size_gate(monkeypatch):
    client = _client(monkeypatch, max_bytes=1024)
    files = {"file": ("small.pdf", b"%PDF-1.7 tiny", "application/pdf")}
    data = {"template_type": "invoice", "api_key": "k", "model_id": "m"}
    resp = client.post("/api/pdf/extract", files=files, data=data)
    assert resp.status_code != 413
