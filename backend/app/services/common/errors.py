"""
Unified Error Handling for Provider Services

This module defines a unified error hierarchy for all provider operations.
All provider-specific errors should inherit from ProviderError and include
structured context for debugging and monitoring.

Design Principles:
1. Structured Context: All errors include providerId, clientType, operation, and context dict
2. Error Recovery: Support retry and fallback strategies
3. Structured Logging: Include request IDs and execution time
4. Type Safety: Use dataclasses for error context
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field
import logging
import time
import uuid

logger = logging.getLogger(__name__)


# ==================== Error Context ====================

@dataclass
class ErrorContext:
    """
    Structured context for provider errors.
    
    Attributes:
        provider_id: Provider identifier (e.g., 'google', 'qwen', 'ollama')
        client_type: Client type ('primary', 'secondary', 'single')
        operation: Operation type (e.g., 'chat', 'stream', 'image_edit', 'model_list')
        request_id: Unique request identifier for tracing
        user_id: Optional user identifier
        model: Optional model identifier
        platform: Optional platform (e.g., 'vertex_ai', 'developer_api')
        execution_time_ms: Optional execution time in milliseconds
        additional_context: Additional context as key-value pairs
    """
    provider_id: str
    client_type: Literal['primary', 'secondary', 'single']
    operation: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    execution_time_ms: Optional[float] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging."""
        return {
            'provider_id': self.provider_id,
            'client_type': self.client_type,
            'operation': self.operation,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'model': self.model,
            'platform': self.platform,
            'execution_time_ms': self.execution_time_ms,
            **self.additional_context
        }


# ==================== Base Error Class ====================

class ProviderError(Exception):
    """
    Base class for all provider errors.
    
    All provider-specific errors should inherit from this class and include
    structured context for debugging and monitoring.
    
    Attributes:
        message: Human-readable error message
        context: Structured error context
        original_error: Original exception (if wrapped)
        recoverable: Whether error is recoverable (retry/fallback possible)
    """
    
    def __init__(
        self,
        message: str,
        context: ErrorContext,
        original_error: Optional[Exception] = None,
        recoverable: bool = False
    ):
        self.message = message
        self.context = context
        self.original_error = original_error
        self.recoverable = recoverable
        
        # Log error with structured context
        self._log_error()
        
        # Call parent constructor
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message with context."""
        parts = [
            f"[{self.context.provider_id}]",
            f"[{self.context.operation}]",
            f"[{self.context.client_type}]",
            self.message
        ]
        if self.context.request_id:
            parts.append(f"(request_id={self.context.request_id})")
        return " ".join(parts)
    
    def _log_error(self):
        """Log error with structured context."""
        log_data = {
            'error_type': self.__class__.__name__,
            'error_message': self.message,  # Renamed from 'message' to avoid LogRecord conflict
            'recoverable': self.recoverable,
            **self.context.to_dict()
        }
        
        if self.original_error:
            log_data['original_error'] = str(self.original_error)
            log_data['original_error_type'] = type(self.original_error).__name__
        
        logger.error(f"Provider error: {self._format_message()}", extra=log_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'provider_id': self.context.provider_id,
            'operation': self.context.operation,
            'request_id': self.context.request_id,
            'recoverable': self.recoverable
        }


# ==================== Specific Error Classes ====================

class ClientCreationError(ProviderError):
    """
    Error during client creation or initialization.
    
    Examples:
    - Invalid API key
    - Missing configuration
    - Network connection failure during initialization
    - SDK initialization failure
    """
    
    def __init__(
        self,
        message: str,
        context: ErrorContext,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            context=context,
            original_error=original_error,
            recoverable=False  # Client creation errors are typically not recoverable
        )


class OperationError(ProviderError):
    """
    Error during provider operation execution.
    
    Examples:
    - API call failure
    - Invalid request parameters
    - Rate limit exceeded
    - Model not found
    - Timeout
    """
    
    def __init__(
        self,
        message: str,
        context: ErrorContext,
        original_error: Optional[Exception] = None,
        recoverable: bool = True  # Operation errors may be recoverable
    ):
        super().__init__(
            message=message,
            context=context,
            original_error=original_error,
            recoverable=recoverable
        )


class ConfigurationError(ProviderError):
    """
    Error in provider configuration.
    
    Examples:
    - Missing required configuration field
    - Invalid configuration value
    - Configuration validation failure
    """
    
    def __init__(
        self,
        message: str,
        context: ErrorContext,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            context=context,
            original_error=original_error,
            recoverable=False  # Configuration errors are not recoverable
        )


# ==================== Specific Operation Errors ====================

class APIKeyError(OperationError):
    """API key is invalid or missing."""
    
    def __init__(self, context: ErrorContext, original_error: Optional[Exception] = None):
        super().__init__(
            message="Invalid or missing API key",
            context=context,
            original_error=original_error,
            recoverable=False
        )


class RateLimitError(OperationError):
    """Rate limit exceeded."""
    
    def __init__(
        self,
        context: ErrorContext,
        retry_after: Optional[int] = None,
        original_error: Optional[Exception] = None
    ):
        message = "Rate limit exceeded"
        if retry_after:
            message += f" (retry after {retry_after}s)"
            context.additional_context['retry_after'] = retry_after
        
        super().__init__(
            message=message,
            context=context,
            original_error=original_error,
            recoverable=True  # Can retry after waiting
        )


class ModelNotFoundError(OperationError):
    """Requested model does not exist."""
    
    def __init__(self, context: ErrorContext, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Model not found: {context.model}",
            context=context,
            original_error=original_error,
            recoverable=False
        )


class InvalidRequestError(OperationError):
    """Request parameters are invalid."""
    
    def __init__(
        self,
        context: ErrorContext,
        validation_errors: Optional[Dict[str, str]] = None,
        original_error: Optional[Exception] = None
    ):
        message = "Invalid request parameters"
        if validation_errors:
            context.additional_context['validation_errors'] = validation_errors
        
        super().__init__(
            message=message,
            context=context,
            original_error=original_error,
            recoverable=False
        )


class TimeoutError(OperationError):
    """Operation timed out."""
    
    def __init__(
        self,
        context: ErrorContext,
        timeout_seconds: Optional[float] = None,
        original_error: Optional[Exception] = None
    ):
        message = "Operation timed out"
        if timeout_seconds:
            message += f" after {timeout_seconds}s"
            context.additional_context['timeout_seconds'] = timeout_seconds
        
        super().__init__(
            message=message,
            context=context,
            original_error=original_error,
            recoverable=True  # Can retry
        )


# ==================== Error Recovery Strategies ====================

@dataclass
class RetryConfig:
    """
    Configuration for retry strategy.
    
    Attributes:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff (e.g., 2 for doubling)
        jitter: Whether to add random jitter to delay
    """
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ErrorRecoveryStrategy:
    """
    Error recovery strategies for provider operations.
    
    Supports:
    1. Retry with exponential backoff
    2. Fallback to secondary client (for dual-client providers)
    3. Graceful degradation
    """
    
    @staticmethod
    def should_retry(error: ProviderError, attempt: int, config: RetryConfig) -> bool:
        """
        Determine if operation should be retried.
        
        Args:
            error: Provider error
            attempt: Current attempt number (0-indexed)
            config: Retry configuration
        
        Returns:
            True if should retry, False otherwise
        """
        # Don't retry if error is not recoverable
        if not error.recoverable:
            return False
        
        # Don't retry if max retries exceeded
        if attempt >= config.max_retries:
            return False
        
        # Retry for specific error types
        if isinstance(error, (RateLimitError, TimeoutError)):
            return True
        
        # Retry for generic operation errors
        if isinstance(error, OperationError):
            return True
        
        return False
    
    @staticmethod
    def calculate_delay(attempt: int, config: RetryConfig) -> float:
        """
        Calculate delay before next retry.
        
        Args:
            attempt: Current attempt number (0-indexed)
            config: Retry configuration
        
        Returns:
            Delay in seconds
        """
        import random
        
        # Exponential backoff
        delay = config.initial_delay * (config.exponential_base ** attempt)
        
        # Cap at max delay
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter:
            delay *= (0.5 + random.random())  # Random factor between 0.5 and 1.5
        
        return delay
    
    @staticmethod
    def should_fallback_to_secondary(error: ProviderError) -> bool:
        """
        Determine if should fallback to secondary client.
        
        Args:
            error: Provider error
        
        Returns:
            True if should fallback, False otherwise
        """
        # Only fallback for primary client errors
        if error.context.client_type != 'primary':
            return False
        
        # Fallback for recoverable operation errors
        if isinstance(error, OperationError) and error.recoverable:
            return True
        
        return False


# ==================== Request ID Management ====================

class RequestIDManager:
    """
    Manage request IDs for tracing.
    
    Request IDs are propagated through the entire request lifecycle
    for debugging and monitoring.
    """
    
    @staticmethod
    def generate() -> str:
        """Generate a new request ID."""
        return str(uuid.uuid4())
    
    @staticmethod
    def from_headers(headers: Dict[str, str]) -> Optional[str]:
        """Extract request ID from HTTP headers."""
        return headers.get('X-Request-ID') or headers.get('x-request-id')


# ==================== Execution Time Tracking ====================

class ExecutionTimer:
    """
    Track execution time for operations.
    
    Supports both context manager usage and direct instantiation.
    
    Usage as context manager:
        with ExecutionTimer() as timer:
            # ... perform operation ...
            pass
        execution_time_ms = timer.elapsed_ms()
    
    Usage as direct instantiation:
        timer = ExecutionTimer()
        # ... perform operation ...
        execution_time_ms = timer.elapsed_ms()
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
    
    def __enter__(self):
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and record end time."""
        self.end_time = time.time()
        return False  # Don't suppress exceptions
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        end = self.end_time if self.end_time else time.time()
        return (end - self.start_time) * 1000
    
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
