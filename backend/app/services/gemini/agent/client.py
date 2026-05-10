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
from types import TracebackType
from typing import Optional, Union, Tuple, Dict, Any
import logging

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

from ..http_options import HttpOptions, HttpOptionsDict
from ..client_pool import get_client_pool
from .models import Models, AsyncModels

logger = logging.getLogger('google_genai.client')


class AsyncClient:
    """Client for making asynchronous (non-blocking) requests."""

    def __init__(self, client):
        """Initialize async client wrapper.

        Args:
            client: The underlying google.genai.Client instance
                （来自 GeminiClientPool；本类不持有生命周期）
        """
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
        """No-op：底层 google.genai.Client 由 GeminiClientPool 管理生命周期。

        包装类不持有底层 client 的关闭权——若此处 close，会把池里被其他调用方
        共享的 client 一并关闭。pool.close_all() 是关闭整个池的统一入口。
        """
        return None

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
        
        # 底层 google.genai.Client 统一从 GeminiClientPool 获取——
        # 同 (vertexai, api_key/project/location/credentials, http_options) 配置在
        # 进程内复用同一原生 client，HttpOptions 的转换、ADC vs service account 的
        # 分支、project/location 校验均在 pool 内部统一处理（见
        # services/gemini/client_pool.py:get_client / _to_genai_http_options）。
        self._genai_client = get_client_pool().get_client(
            api_key=self._api_key,
            vertexai=self._vertexai,
            project=self._project,
            location=self._location,
            credentials=self._credentials,
            http_options=self._http_options,
        )

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
        """No-op：底层 google.genai.Client 由 GeminiClientPool 管理生命周期。

        与 AsyncClient.aclose() 同理——包装类不真关底层，避免破坏池中共享。
        如需统一释放进程内全部 client，调 ``GeminiClientPool.close_all()``。
        """
        return None

    def __enter__(self) -> 'Client':
        return self

    def __exit__(
        self,
        exc_type: Optional[Exception],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()
