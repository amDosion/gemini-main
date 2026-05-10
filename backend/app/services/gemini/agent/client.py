# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Official Google GenAI SDK Compatible Client Implementation

基于官方 google.genai.Client 的兼容层实现。
使用官方的 google.genai.Client，而不是旧版 google-generativeai / Vertex AI 生成式模块。
"""

import asyncio
import os
import json
import warnings
from types import TracebackType
from typing import Optional, Union, Tuple, Dict, Any
import logging

_WRAPPER_DEPRECATION_MSG = (
    "app.services.gemini.agent.client.{cls} 已弃用。请改用 "
    "`from app.services.gemini.client_pool import get_client_pool; "
    "client = get_client_pool().get_client(api_key=..., vertexai=...)`。"
    "包装类不走统一连接池，且其内部 Models 类对当前 google-genai SDK 已 broken。"
)

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

from .types import HttpOptions, HttpOptionsDict

logger = logging.getLogger(__name__)


# get_vertex_ai_credentials_from_db 已迁出到 services.gemini.credentials。
# 这里只保留 re-export，让旧路径
#     from app.services.gemini.agent.client import get_vertex_ai_credentials_from_db
# 仍然可用。新代码请直接从 services.gemini.credentials 导入。
from ..credentials import get_vertex_ai_credentials_from_db  # noqa: F401  (backward-compat re-export)

from .models import Models, AsyncModels
logger = logging.getLogger('google_genai.client')


class AsyncClient:
    """Client for making asynchronous (non-blocking) requests."""

    def __init__(self, client):
        """Initialize async client wrapper.

        Args:
            client: The underlying google.genai.Client instance
        """
        warnings.warn(
            _WRAPPER_DEPRECATION_MSG.format(cls="AsyncClient"),
            DeprecationWarning,
            stacklevel=2,
        )
        self._client = client
        self._models = AsyncModels(client)

    @property
    def models(self) -> AsyncModels:
        return self._models

    @property
    def interactions(self):
        """Access to interactions API (native SDK)."""
        return self._client.aio.interactions

    async def aclose(self) -> None:
        """Closes the async client explicitly."""
        # Official SDK may not have aclose, so we check
        if hasattr(self._client, 'aclose'):
            await self._client.aclose()

    async def __aenter__(self) -> 'AsyncClient':
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Exception],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.aclose()


class Client:
    """Client for making synchronous requests.
    
    基于官方 google.genai.Client 的兼容层。
    支持 Vertex AI 和 Gemini API 两种模式。
    """

    def __init__(
        self,
        *,
        vertexai: Optional[bool] = None,
        api_key: Optional[str] = None,
        credentials = None,  # Service account credentials (for Vertex AI ADC mode)
        project: Optional[str] = None,
        location: Optional[str] = None,
        debug_config = None,
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None,
    ):
        """Initialize the client.
        
        Args:
            vertexai: Whether to use Vertex AI (default: False)
            api_key: Google API key (for Gemini API or Vertex AI Express mode)
            credentials: Google Cloud credentials (for Vertex AI)
            project: Google Cloud project ID (for Vertex AI)
            location: Google Cloud location (for Vertex AI, default: us-central1)
            debug_config: Debug configuration
            http_options: HTTP options (timeout, headers, etc.)
        """
        warnings.warn(
            _WRAPPER_DEPRECATION_MSG.format(cls="Client"),
            DeprecationWarning,
            stacklevel=2,
        )

        if not GENAI_AVAILABLE:
            raise ImportError(
                "google.genai package is not available. "
                "Please install it with: pip install google-genai"
            )

        # Store configuration
        self._vertexai = vertexai or False
        self._api_key = api_key or os.environ.get('GOOGLE_API_KEY')
        self._credentials = credentials
        self._project = project or os.environ.get('GOOGLE_CLOUD_PROJECT')
        self._location = location or os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Process HTTP options
        if isinstance(http_options, dict):
            http_options = HttpOptions(**http_options)
        self._http_options = http_options or HttpOptions()
        
        # Validate required parameters
        if not self._vertexai and not self._api_key:
            raise ValueError(
                'Missing API key! To use the Google AI API, '
                'provide api_key argument or set GOOGLE_API_KEY environment variable.'
            )
        
        if self._vertexai and not (self._project and self._location):
            # For Vertex AI Express mode, api_key is sufficient
            if not self._api_key:
                raise ValueError(
                    'Missing project or location! To use Vertex AI, '
                    'provide project and location arguments or set environment variables, '
                    'or provide api_key for Vertex AI Express mode.'
                )
        
        # Create official google.genai.Client
        client_kwargs = {}
        
        if self._vertexai:
            client_kwargs['vertexai'] = True
            # Vertex AI 模式：通过 google.genai.Client(vertexai=True, ...)
            # 使用 project/location 和 OAuth2 credentials 或 ADC。
            if self._project and self._location:
                # 使用 project 和 location（用于构建路径）
                client_kwargs['project'] = self._project
                client_kwargs['location'] = self._location
                
                # 如果有 credentials（service account），使用它（推荐方式）
                if self._credentials:
                    client_kwargs['credentials'] = self._credentials
                    logger.info("[Client] Using Vertex AI with project/location and service account credentials")
                else:
                    # 使用 ADC（Application Default Credentials）
                    # 不传递 api_key，让 SDK 自动使用 ADC
                    # 需要环境中有 GOOGLE_APPLICATION_CREDENTIALS 或运行 gcloud auth application-default login
                    logger.info("[Client] Using Vertex AI ADC mode (project/location)")
                    logger.info("[Client] Make sure GOOGLE_APPLICATION_CREDENTIALS is set or run 'gcloud auth application-default login'")
            else:
                raise ValueError(
                    'For Vertex AI mode, project and location are required. '
                    'Please provide both project and location, and ensure ADC is configured '
                    '(GOOGLE_APPLICATION_CREDENTIALS environment variable or gcloud auth application-default login).'
                )
        else:
            # Gemini API 模式：只需要 api_key
            if self._api_key:
                client_kwargs['api_key'] = self._api_key
            else:
                raise ValueError('api_key is required for Gemini API mode')
        
        # Add HTTP options if provided
        if self._http_options:
            # Convert our HttpOptions to google.genai.types.HttpOptions
            try:
                from google.genai import types as genai_types
                retry_options = getattr(self._http_options, "retry_options", None)
                genai_retry_options = None
                if retry_options:
                    genai_retry_options = genai_types.HttpRetryOptions(
                        attempts=retry_options.attempts,
                        initial_delay=retry_options.initial_delay,
                        max_delay=retry_options.max_delay,
                        exp_base=retry_options.exp_base,
                        jitter=retry_options.jitter,
                    )

                genai_http_options = genai_types.HttpOptions(
                    api_version=getattr(self._http_options, "api_version", None),
                    base_url=getattr(self._http_options, "base_url", None),
                    headers=getattr(self._http_options, "headers", None),
                    timeout=getattr(self._http_options, "timeout", None),
                    retry_options=genai_retry_options,
                )
                client_kwargs['http_options'] = genai_http_options
            except ImportError:
                logger.warning("Could not import google.genai.types, http_options may not work correctly")
        
        # Create the official client
        self._genai_client = genai.Client(**client_kwargs)
        
        # 注意：Vertex AI 模式使用 ADC 或 credentials，不需要覆盖 prepare_options
        # 官方 SDK 会自动处理认证（使用 ADC 或传递的 credentials）
        
        # Initialize modules (native SDK interactions, legacy model wrappers)
        self._aio = AsyncClient(self._genai_client)
        self._models = Models(self._genai_client)

    @property
    def vertexai(self) -> bool:
        """Returns whether the client is using the Vertex AI API."""
        return self._vertexai

    @property
    def aio(self) -> AsyncClient:
        """Access to async client."""
        return self._aio

    @property
    def models(self) -> Models:
        """Access to models API."""
        return self._models

    @property
    def interactions(self):
        """Access to interactions API (native SDK)."""
        return self._genai_client.interactions

    def close(self) -> None:
        """Closes the synchronous client explicitly."""
        if hasattr(self._genai_client, 'close'):
            self._genai_client.close()

    def __enter__(self) -> 'Client':
        return self

    def __exit__(
        self,
        exc_type: Optional[Exception],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()
