"""
Official Google GenAI SDK Compatibility Layer

This module provides 100% compatible interfaces with the official Google GenAI SDK.
It implements the same client architecture, type system, and API patterns as the
official SDK while maintaining compatibility with our existing infrastructure.

Architecture:
- Client/AsyncClient: Main client classes with dual sync/async support
- Types: Complete type definitions extracted from official SDK
- Models: Content generation and streaming APIs
- Interactions: Deep Research Agent and other advanced features

Usage:
    from backend.app.services.gemini.official import Client
    from backend.app.services.gemini.official import types
    
    # Sync client
    client = Client(api_key='your-api-key')
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents='Hello world'
    )
    
    # Async client
    async_client = client.aio
    response = await async_client.models.generate_content(
        model='gemini-2.0-flash', 
        contents='Hello world'
    )
"""

# Re-export the official SDK compatibility layer
from .client import Client, AsyncClient
from . import types
from .models import Models, AsyncModels
from .interactions import InteractionsResource, AsyncInteractionsResource

__all__ = [
    # Main clients
    'Client',
    'AsyncClient',
    
    # API modules
    'Models',
    'AsyncModels',
    'InteractionsResource', 
    'AsyncInteractionsResource',
    
    # Type module
    'types',
]

# Version info
__version__ = '1.0.0'
__author__ = 'Gemini Service Team'
__description__ = 'Official Google GenAI SDK Compatibility Layer'