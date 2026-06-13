"""Embedding/RAG routes"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.dependencies import require_current_user

router = APIRouter(prefix="/api/embedding", tags=["embedding"])
FREE_TEXT_PATTERN = r"^[\s\S]*$"
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"

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


class AddDocumentResponse(BaseModel):
    success: bool
    error: Optional[str] = Field(default=None, max_length=4096, pattern=FREE_TEXT_PATTERN)
    document_id: Optional[str] = Field(default=None, max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    filename: Optional[str] = Field(default=None, max_length=512, pattern=NO_CONTROL_CHARS_PATTERN)
    chunk_count: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    total_chunks: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    total_documents: Optional[int] = Field(default=None, ge=0, le=1_000_000)


class SearchResultResponse(BaseModel):
    text: str = Field(max_length=200_000, pattern=FREE_TEXT_PATTERN)
    source: str = Field(max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    filename: str = Field(max_length=512, pattern=NO_CONTROL_CHARS_PATTERN)
    similarity: float = Field(ge=-1, le=1)
    chunk_id: str = Field(max_length=512, pattern=NO_CONTROL_CHARS_PATTERN)


class SearchResponse(BaseModel):
    success: bool
    results: list[SearchResultResponse] = Field(max_length=1_000)
    count: int = Field(ge=0, le=1_000)


class EmbeddingStatsResponse(BaseModel):
    total_chunks: int = Field(ge=0, le=10_000_000)
    total_documents: int = Field(ge=0, le=1_000_000)
    documents: list[str] = Field(max_length=1_000_000)


class DocumentsResponse(BaseModel):
    success: bool
    documents: list[dict[str, Any]] = Field(max_length=1_000_000)
    stats: EmbeddingStatsResponse


class EmbeddingMessageResponse(BaseModel):
    success: bool
    message: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)


@router.post("/add-document", response_model=AddDocumentResponse)
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


@router.post("/search", response_model=SearchResponse)
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


@router.get("/documents", response_model=DocumentsResponse)
@router.get("/documents/{legacy_user_id}", response_model=DocumentsResponse)
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


@router.delete("/document/{document_id}", response_model=EmbeddingMessageResponse)
@router.delete("/document/{legacy_user_id}/{document_id}", response_model=EmbeddingMessageResponse)
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


@router.delete("/documents", response_model=EmbeddingMessageResponse)
@router.delete("/documents/{legacy_user_id}", response_model=EmbeddingMessageResponse)
async def clear_user_documents(
    legacy_user_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
):
    _validate_legacy_user_id(legacy_user_id, user_id)
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Embedding service not available")
    rag_service.clear_user_documents(user_id)
    return {"success": True, "message": "All documents cleared"}
