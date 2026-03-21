"""
Common Services Module

This module contains shared services and utilities used across all providers:
- Base classes and interfaces
- Provider configuration and factory
- Error handling
- Model capabilities
- Client selection
- Embedding services
- And other common utilities

Updated: 2026-01-14 - Organized into common/ directory
"""

from .base_provider import BaseProviderService
from .provider_config import ProviderConfig
from .provider_factory import ProviderFactory
from .errors import (
    ProviderError,
    OperationError,
    ClientCreationError,
    ConfigurationError,
    ErrorContext,
    ExecutionTimer,
    RequestIDManager
)
from .model_capabilities import ModelConfig, build_model_config
from .client_selector import ClientSelector, ClientSelectorFactory
from .progress_tracker import ProgressTracker

try:  # pragma: no cover - optional dependency surface
    from .embedding_service import RAGService, DocumentChunk, VectorStore
except Exception:  # pragma: no cover - optional dependency surface
    RAGService = None  # type: ignore
    DocumentChunk = None  # type: ignore
    VectorStore = None  # type: ignore

try:  # pragma: no cover - optional dependency surface
    from .interactions_manager import InteractionsManager, get_interactions_manager
except Exception:  # pragma: no cover - optional dependency surface
    InteractionsManager = None  # type: ignore
    get_interactions_manager = None  # type: ignore

try:  # pragma: no cover - optional dependency surface
    from .upload_worker_pool import UploadWorkerPool
except Exception:  # pragma: no cover - optional dependency surface
    UploadWorkerPool = None  # type: ignore

try:  # pragma: no cover - optional dependency surface
    from .init_service import assemble_messages_v3
except Exception:  # pragma: no cover - optional dependency surface
    assemble_messages_v3 = None  # type: ignore

try:  # pragma: no cover - optional dependency surface
    from .auth_service import AuthService
except Exception:  # pragma: no cover - optional dependency surface
    AuthService = None  # type: ignore

try:  # pragma: no cover - optional dependency surface
    from .redis_queue_service import RedisQueueService
except Exception:  # pragma: no cover - optional dependency surface
    RedisQueueService = None  # type: ignore

__all__ = [
    # Base classes
    "BaseProviderService",
    "ModelConfig",
    "build_model_config",
    # Provider management
    "ProviderConfig",
    "ProviderFactory",
    # Error handling
    "ProviderError",
    "OperationError",
    "ClientCreationError",
    "ConfigurationError",
    "ErrorContext",
    "ExecutionTimer",
    "RequestIDManager",
    # Client selection
    "ClientSelector",
    "ClientSelectorFactory",
    # Services
    "RAGService",
    "DocumentChunk",
    "VectorStore",
    "InteractionsManager",
    "get_interactions_manager",
    "ProgressTracker",
    "UploadWorkerPool",
    "assemble_messages_v3",
    "AuthService",
    "RedisQueueService",
]
