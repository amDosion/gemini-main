from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.ai import embedding


class FakeRagService:
    async def add_document(self, **_kwargs):
        return {
            "success": True,
            "document_id": "doc-1",
            "filename": "notes.txt",
            "chunk_count": 2,
            "total_chunks": 2,
            "total_documents": 1,
        }

    def search_similar_chunks(self, **_kwargs):
        return [
            {
                "text": "matching text",
                "source": "doc-1",
                "filename": "notes.txt",
                "similarity": 0.75,
                "chunk_id": "doc-1_chunk_0",
            }
        ]

    def get_user_documents(self, user_id: str):
        assert user_id == "user-1"
        return [
            {
                "filename": "notes.txt",
                "document_id": "doc-1",
                "chunk_count": 2,
                "added_at": "2026-06-12T00:00:00",
            }
        ]

    def get_stats(self, user_id: str):
        assert user_id == "user-1"
        return {
            "total_chunks": 2,
            "total_documents": 1,
            "documents": ["doc-1"],
        }

    def remove_document(self, user_id: str, document_id: str):
        assert user_id == "user-1"
        return document_id == "doc-1"

    def clear_user_documents(self, user_id: str):
        assert user_id == "user-1"


def _client(monkeypatch):
    app = FastAPI()
    app.include_router(embedding.router)
    app.dependency_overrides[embedding.require_current_user] = lambda: "user-1"
    monkeypatch.setattr(embedding, "EMBEDDING_AVAILABLE", True)
    monkeypatch.setattr(embedding, "rag_service", FakeRagService())
    return TestClient(app)


def test_embedding_add_document_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/embedding/add-document",
            json={
                "filename": "notes.txt",
                "content": "hello world",
                "api_key": "test-key",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["document_id"] == "doc-1"
    assert body["chunk_count"] == 2


def test_embedding_search_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/embedding/search",
            json={"query": "hello", "api_key": "test-key", "top_k": 1},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["similarity"] == 0.75


def test_embedding_documents_legacy_paths_share_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/embedding/documents/user-1")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["documents"][0]["document_id"] == "doc-1"
    assert body["stats"]["total_documents"] == 1


def test_embedding_document_delete_legacy_path_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.delete("/api/embedding/document/user-1/doc-1")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Document deleted"}


def test_embedding_clear_documents_legacy_path_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.delete("/api/embedding/documents/user-1")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "All documents cleared"}
