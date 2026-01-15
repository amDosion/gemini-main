"""
Common Services Module

This module contains shared services and utilities used across all providers:
- Base classes and interfaces
- Provider configuration and factory
- Error handling
- Model capabilities
- Client selection
- API key management
- Embedding services
- State management
- Tool orchestration
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
from .api_key_service import APIKeyService
from .embedding_service import RAGService, DocumentChunk, VectorStore
from .interactions_manager import InteractionsManager, get_interactions_manager
from .progress_tracker import ProgressTracker
from .state_manager import StateManager
from .tool_orchestrator import ToolOrchestrator
from .upload_worker_pool import UploadWorkerPool
from .init_service import assemble_messages_v3
from .auth_service import AuthService
from .redis_queue_service import RedisQueueService

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
    "APIKeyService",
    "RAGService",
    "DocumentChunk",
    "VectorStore",
    "InteractionsManager",
    "get_interactions_manager",
    "ProgressTracker",
    "StateManager",
    "ToolOrchestrator",
    "UploadWorkerPool",
    "assemble_messages_v3",
    "AuthService",
    "RedisQueueService",
]
