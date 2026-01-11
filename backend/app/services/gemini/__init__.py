"""
Gemini Service Module

This module provides Google Gemini provider services with enhanced capabilities.

Architecture:
- google_service.py: Main coordinator
- sdk_initializer.py: SDK initialization
- chat_handler.py: Chat operations
- image_generator.py: Image generation
- model_manager.py: Model listing
- file_handler.py: File upload/download operations (NEW)
- function_handler.py: Function calling and tool integration (NEW)
- schema_handler.py: Structured JSON response handling (NEW)
- token_handler.py: Token counting and cost estimation (NEW)
- message_converter.py: Message format conversion
- response_parser.py: Response parsing
- config_builder.py: Configuration building

New Features (P0):
- Files API: Multi-modal file processing
- Function Calling: Tool integration and external API calls
- JSON Schema Response: Structured output formatting
- Token Management: Usage tracking and cost control
"""

from .google_service import GoogleService
from .file_handler import FileHandler
from .function_handler import FunctionHandler, FunctionCallingMode
from .schema_handler import SchemaHandler, CommonSchemas
from .token_handler import TokenHandler, TokenCount, ModelPricing, ModelLimits

__all__ = [
    'GoogleService',
    'FileHandler',
    'FunctionHandler', 
    'FunctionCallingMode',
    'SchemaHandler',
    'CommonSchemas',
    'TokenHandler',
    'TokenCount',
    'ModelPricing',
    'ModelLimits'
]
