"""Embedding/RAG routes"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.dependencies import require_current_user

router = APIRouter(prefix="/api/embedding", tags=["embedding"])

# Service reference (set in main.py)
rag_service = None
EMBEDDING_AVAILABLE = False


def set_embedding_service(service, available: bool):
    global rag_service, EMBEDDING_AVAILABLE
    rag_service = service
    EMBEDDING_AVAILABLE = available


class AddDocumentRequest(BaseModel):
    filename: str
    content: str
    api_key: str
    chunk_size: int = 500
    chunk_overlap: int = 100


class SearchRequest(BaseModel):
    query: str
    api_key: str
    top_k: int = 3


@router.post("/add-document")
async def add_document(
    request: AddDocumentRequest,
    user_id: str = Depends(require_current_user),
):
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    result = await rag_service.add_document(
        user_id=user_id, filename=request.filename, content=request.content,
        api_key=request.api_key, chunk_size=request.chunk_size, chunk_overlap=request.chunk_overlap
    )
    return result


@router.post("/search")
async def search_documents(
    request: SearchRequest,
    user_id: str = Depends(require_current_user),
):
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    results = rag_service.search_similar_chunks(
        user_id=user_id, query=request.query, api_key=request.api_key, top_k=request.top_k
    )
    return {"success": True, "results": results, "count": len(results)}


def _validate_legacy_user_id(legacy_user_id: Optional[str], user_id: str) -> None:
    if legacy_user_id and legacy_user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot access other user's documents")


@router.get("/documents")
@router.get("/documents/{legacy_user_id}")
async def get_user_documents(
    legacy_user_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
):
    _validate_legacy_user_id(legacy_user_id, user_id)
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    documents = rag_service.get_user_documents(user_id)
    stats = rag_service.get_stats(user_id)
    return {"success": True, "documents": documents, "stats": stats}


@router.delete("/document/{document_id}")
@router.delete("/document/{legacy_user_id}/{document_id}")
async def delete_document(
    document_id: str,
    legacy_user_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
):
    _validate_legacy_user_id(legacy_user_id, user_id)
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    success = rag_service.remove_document(user_id, document_id)
    if success:
        return {"success": True, "message": "Document deleted"}
    raise HTTPException(status_code=404, detail="Document not found")


@router.delete("/documents")
@router.delete("/documents/{legacy_user_id}")
async def clear_user_documents(
    legacy_user_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
):
    _validate_legacy_user_id(legacy_user_id, user_id)
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    rag_service.clear_user_documents(user_id)
    return {"success": True, "message": "All documents cleared"}
