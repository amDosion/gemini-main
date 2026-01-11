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

"""Official Google GenAI SDK Compatible Client Implementation"""

import asyncio
import os
from types import TracebackType
from typing import Optional, Union, cast
import logging

from .types import HttpOptions, HttpOptionsDict
from .models import Models, AsyncModels
from .interactions import InteractionsResource, AsyncInteractionsResource

logger = logging.getLogger('google_genai.client')


class AsyncClient:
    """Client for making asynchronous (non-blocking) requests."""

    def __init__(self, api_client):
        self._api_client = api_client
        self._models = AsyncModels(self._api_client)
        self._interactions = AsyncInteractionsResource(self._api_client)

    @property
    def models(self) -> AsyncModels:
        return self._models

    @property
    def interactions(self) -> AsyncInteractionsResource:
        return self._interactions

    async def aclose(self) -> None:
        """Closes the async client explicitly."""
        if hasattr(self._api_client, 'aclose'):
            await self._api_client.aclose()

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
    """Client for making synchronous requests."""

    def __init__(
        self,
        *,
        vertexai: Optional[bool] = None,
        api_key: Optional[str] = None,
        credentials = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
        debug_config = None,
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None,
    ):
        """Initialize the client."""
        
        # Store configuration
        self._vertexai = vertexai or False
        self._api_key = api_key or os.environ.get('GOOGLE_API_KEY')
        self._credentials = credentials
        self._project = project or os.environ.get('GOOGLE_CLOUD_PROJECT')
        self._location = location or os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Validate required parameters
        if not self._vertexai and not self._api_key:
            raise ValueError(
                'Missing API key! To use the Google AI API, '
                'provide api_key argument or set GOOGLE_API_KEY environment variable.'
            )
        
        if self._vertexai and not (self._project and self._location):
            raise ValueError(
                'Missing project or location! To use Vertex AI, '
                'provide project and location arguments or set environment variables.'
            )
        
        # Process HTTP options
        if isinstance(http_options, dict):
            http_options = HttpOptions(**http_options)
        self._http_options = http_options or HttpOptions()
        
        # Create a simple API client wrapper
        self._api_client = SimpleApiClient(
            vertexai=self._vertexai,
            api_key=self._api_key,
            project=self._project,
            location=self._location,
            http_options=self._http_options
        )
        
        # Initialize modules
        self._aio = AsyncClient(self._api_client)
        self._models = Models(self._api_client)
        self._interactions = InteractionsResource(self._api_client)

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
    def interactions(self) -> InteractionsResource:
        """Access to interactions API."""
        return self._interactions

    def close(self) -> None:
        """Closes the synchronous client explicitly."""
        if hasattr(self._api_client, 'close'):
            self._api_client.close()

    def __enter__(self) -> 'Client':
        return self

    def __exit__(
        self,
        exc_type: Optional[Exception],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()


class SimpleApiClient:
    """Simple API client wrapper for basic functionality."""
    
    def __init__(
        self,
        vertexai: bool = False,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
        http_options: Optional[HttpOptions] = None
    ):
        self.vertexai = vertexai
        self.api_key = api_key
        self.project = project
        self.location = location
        self._http_options = http_options or HttpOptions()
        
        # Set base URL based on API type
        if self.vertexai:
            if self.location == 'global':
                self.base_url = 'https://aiplatform.googleapis.com/'
            else:
                self.base_url = f'https://{self.location}-aiplatform.googleapis.com/'
            self.api_version = 'v1beta1'
        else:
            self.base_url = 'https://generativelanguage.googleapis.com/'
            self.api_version = 'v1beta'
    
    def close(self):
        """Close the client."""
        pass
    
    async def aclose(self):
        """Close the async client."""
        pass
    
    def request(self, method: str, path: str, data: dict = None, http_options = None):
        """Make a synchronous HTTP request."""
        # This is a simplified implementation
        # In a real implementation, this would use httpx or requests
        from types import SimpleNamespace
        
        # Mock response for testing
        mock_response_data = {
            'candidates': [{
                'content': {
                    'role': 'model',
                    'parts': [{'text': 'This is a mock response from the official SDK client.'}]
                },
                'finishReason': 'STOP'
            }]
        }
        
        response = SimpleNamespace()
        response.body = str(mock_response_data).replace("'", '"')
        response.headers = {'content-type': 'application/json'}
        return response
    
    async def async_request(self, method: str, path: str, data: dict = None, http_options = None):
        """Make an asynchronous HTTP request."""
        # For now, just call the sync version
        return self.request(method, path, data, http_options)
    
    def request_streamed(self, method: str, path: str, data: dict = None, http_options = None):
        """Make a synchronous streaming HTTP request."""
        # Mock streaming response
        chunks = [
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'Mock '}]}}]},
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'streaming '}]}}]},
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'response.'}]}}]},
        ]
        
        from types import SimpleNamespace
        for chunk_data in chunks:
            response = SimpleNamespace()
            response.body = str(chunk_data).replace("'", '"')
            response.headers = {'content-type': 'application/json'}
            yield response
    
    async def async_request_streamed(self, method: str, path: str, data: dict = None, http_options = None):
        """Make an asynchronous streaming HTTP request."""
        # For now, just call the sync version and convert to async
        for chunk in self.request_streamed(method, path, data, http_options):
            yield chunk
    
    def _verify_response(self, response):
        """Verify the response is valid."""
        # Basic validation - in a real implementation this would check for errors
        pass