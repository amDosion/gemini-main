import hashlib

from app.core.config import Settings
from app.services.common.embedding_service import generate_document_id


def test_default_backend_host_is_loopback(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)

    assert Settings().host == "127.0.0.1"


def test_backend_host_can_be_explicitly_overridden(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")

    assert Settings().host == "0.0.0.0"


def test_document_id_uses_sha256_content_fingerprint():
    expected = hashlib.sha256("document text".encode()).hexdigest()[:8]

    assert generate_document_id("doc.txt", "document text") == f"doc.txt_{expected}"
