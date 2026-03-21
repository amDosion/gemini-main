"""
Document Embedding and RAG Service

This module provides functionality for document vectorization and retrieval-augmented generation (RAG)
using Google Gemini embeddings.
"""

from typing import List, Dict, Any, Optional
import json
import hashlib
from datetime import datetime
import numpy as np

try:
    from google import genai
except Exception:  # pragma: no cover - optional dependency
    genai = None  # type: ignore


# ============================================================================
# Data Models
# ============================================================================

class DocumentChunk:
    """Represents a chunk of text from a document"""
    def __init__(self, text: str, source: str, chunk_id: str, metadata: Optional[Dict] = None):
        self.text = text
        self.source = source
        self.chunk_id = chunk_id
        self.metadata = metadata or {}
        self.embedding: Optional[List[float]] = None
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'source': self.source,
            'chunk_id': self.chunk_id,
            'metadata': self.metadata,
            'embedding': self.embedding,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        chunk = cls(
            text=data['text'],
            source=data['source'],
            chunk_id=data['chunk_id'],
            metadata=data.get('metadata', {})
        )
        chunk.embedding = data.get('embedding')
        chunk.created_at = data.get('created_at', datetime.now().isoformat())
        return chunk


class VectorStore:
    """Simple in-memory vector store for document chunks"""
    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self.documents: Dict[str, Dict[str, Any]] = {}  # document_id -> metadata

    def add_chunks(self, chunks: List[DocumentChunk]):
        """Add chunks to the vector store"""
        self.chunks.extend(chunks)

    def add_document(self, document_id: str, metadata: Dict[str, Any]):
        """Register a document in the store"""
        self.documents[document_id] = metadata

    def get_chunks_by_source(self, source: str) -> List[DocumentChunk]:
        """Get all chunks from a specific source"""
        return [chunk for chunk in self.chunks if chunk.source == source]

    def remove_document(self, document_id: str):
        """Remove a document and all its chunks"""
        self.chunks = [chunk for chunk in self.chunks if chunk.source != document_id]
        if document_id in self.documents:
            del self.documents[document_id]

    def clear(self):
        """Clear all documents and chunks"""
        self.chunks.clear()
        self.documents.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        return {
            'total_chunks': len(self.chunks),
            'total_documents': len(self.documents),
            'documents': list(self.documents.keys())
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the vector store"""
        return {
            'chunks': [chunk.to_dict() for chunk in self.chunks],
            'documents': self.documents
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VectorStore':
        """Deserialize the vector store"""
        store = cls()
        store.chunks = [DocumentChunk.from_dict(chunk_data) for chunk_data in data.get('chunks', [])]
        store.documents = data.get('documents', {})
        return store


# ============================================================================
# Text Processing Functions
# ============================================================================

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: The text to chunk
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # If this is not the last chunk, try to break at a sentence or word boundary
        if end < len(text):
            # Try to find a sentence boundary
            for delimiter in ['. ', '! ', '? ', '\n\n', '\n']:
                last_delim = text[start:end].rfind(delimiter)
                if last_delim != -1:
                    end = start + last_delim + len(delimiter)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start position, accounting for overlap
        start = end - chunk_overlap if end < len(text) else end

    return chunks


def generate_document_id(filename: str, content: str) -> str:
    """Generate a unique ID for a document"""
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{filename}_{content_hash}"


# ============================================================================
# Embedding Functions
# ============================================================================

def get_embedding(text: str, api_key: str, model: str = "text-embedding-004") -> List[float]:
    """
    Generate an embedding for the given text using Gemini.

    Args:
        text: The text to embed
        api_key: Google AI API key
        model: The embedding model to use

    Returns:
        List of floats representing the embedding vector
    """
    if genai is None:
        raise ImportError(
            "google.genai is required for embedding operations. Install the Google GenAI SDK first."
        )
    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(model=model, contents=text)
    return response.embeddings[0].values


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0 to 1)
    """
    vec1_array = np.array(vec1)
    vec2_array = np.array(vec2)

    dot_product = np.dot(vec1_array, vec2_array)
    norm1 = np.linalg.norm(vec1_array)
    norm2 = np.linalg.norm(vec2_array)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


# ============================================================================
# RAG Service
# ============================================================================

class RAGService:
    """Service for Retrieval-Augmented Generation"""

    def __init__(self):
        self.vector_stores: Dict[str, VectorStore] = {}  # user_id -> VectorStore

    def get_or_create_store(self, user_id: str) -> VectorStore:
        """Get or create a vector store for a user"""
        if user_id not in self.vector_stores:
            self.vector_stores[user_id] = VectorStore()
        return self.vector_stores[user_id]

    async def add_document(
        self,
        user_id: str,
        filename: str,
        content: str,
        api_key: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100
    ) -> Dict[str, Any]:
        """
        Add a document to the user's vector store.

        Args:
            user_id: User identifier
            filename: Name of the document
            content: Document content
            api_key: Google AI API key
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Dictionary with document metadata and statistics
        """
        store = self.get_or_create_store(user_id)

        # Generate document ID
        document_id = generate_document_id(filename, content)

        # Check if document already exists
        if document_id in store.documents:
            return {
                'success': False,
                'error': 'Document already exists',
                'document_id': document_id
            }

        # Chunk the document
        text_chunks = chunk_text(content, chunk_size, chunk_overlap)

        # Create DocumentChunk objects and generate embeddings
        chunks = []
        for i, text in enumerate(text_chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            chunk = DocumentChunk(
                text=text,
                source=document_id,
                chunk_id=chunk_id,
                metadata={'filename': filename, 'chunk_index': i}
            )

            # Generate embedding
            try:
                chunk.embedding = get_embedding(text, api_key)
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to generate embedding: {str(e)}'
                }

            chunks.append(chunk)

        # Add to store
        store.add_chunks(chunks)
        store.add_document(document_id, {
            'filename': filename,
            'document_id': document_id,
            'chunk_count': len(chunks),
            'added_at': datetime.now().isoformat()
        })

        return {
            'success': True,
            'document_id': document_id,
            'filename': filename,
            'chunk_count': len(chunks),
            'total_chunks': len(store.chunks),
            'total_documents': len(store.documents)
        }

    def search_similar_chunks(
        self,
        user_id: str,
        query: str,
        api_key: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for chunks similar to the query.

        Args:
            user_id: User identifier
            query: Search query
            api_key: Google AI API key
            top_k: Number of top results to return

        Returns:
            List of most similar chunks with similarity scores
        """
        store = self.get_or_create_store(user_id)

        if not store.chunks:
            return []

        # Generate query embedding
        try:
            query_embedding = get_embedding(query, api_key)
        except Exception as e:
            raise ValueError(f"Failed to generate query embedding: {str(e)}")

        # Calculate similarities
        similarities = []
        for chunk in store.chunks:
            if chunk.embedding:
                similarity = cosine_similarity(query_embedding, chunk.embedding)
                similarities.append({
                    'chunk': chunk,
                    'similarity': similarity
                })

        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        top_chunks = similarities[:top_k]

        # Format results
        results = []
        for item in top_chunks:
            chunk = item['chunk']
            results.append({
                'text': chunk.text,
                'source': chunk.source,
                'filename': chunk.metadata.get('filename', 'Unknown'),
                'similarity': item['similarity'],
                'chunk_id': chunk.chunk_id
            })

        return results

    def get_user_documents(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all documents for a user"""
        store = self.get_or_create_store(user_id)
        return list(store.documents.values())

    def remove_document(self, user_id: str, document_id: str) -> bool:
        """Remove a document from the user's store"""
        store = self.get_or_create_store(user_id)
        if document_id in store.documents:
            store.remove_document(document_id)
            return True
        return False

    def clear_user_documents(self, user_id: str):
        """Clear all documents for a user"""
        if user_id in self.vector_stores:
            self.vector_stores[user_id].clear()

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user's vector store"""
        store = self.get_or_create_store(user_id)
        return store.get_stats()


# Global RAG service instance
rag_service = RAGService()
