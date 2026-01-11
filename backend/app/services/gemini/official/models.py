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

"""Models API implementation for Google Gen AI SDK."""

import json
import logging
from typing import Any, AsyncIterator, Iterator, Optional, Union
from urllib.parse import urlencode

from ._common import get_value_by_path as getv
from ._common import set_value_by_path as setv
from .types import (
    GenerateContentConfig,
    GenerateContentResponse,
    Content,
    Part,
    Candidate,
    HttpOptions
)

logger = logging.getLogger('google_genai.models')


# Transformer functions for API compatibility
def _GenerateContentParameters_to_mldev(api_client, parameter_model):
    """Convert GenerateContentParameters to MLDev API format."""
    request_dict = {}
    
    # Convert contents
    if parameter_model.contents:
        contents = []
        for content in parameter_model.contents:
            if isinstance(content, str):
                contents.append({
                    'role': 'user',
                    'parts': [{'text': content}]
                })
            elif isinstance(content, Content):
                content_dict = {
                    'role': content.role,
                    'parts': []
                }
                for part in content.parts:
                    if part.text:
                        content_dict['parts'].append({'text': part.text})
                    elif part.inline_data:
                        content_dict['parts'].append({
                            'inlineData': {
                                'mimeType': part.inline_data.mime_type,
                                'data': part.inline_data.data
                            }
                        })
                contents.append(content_dict)
        request_dict['contents'] = contents
    
    # Convert config
    if parameter_model.config:
        config = parameter_model.config
        generation_config = {}
        
        if config.temperature is not None:
            generation_config['temperature'] = config.temperature
        if config.top_p is not None:
            generation_config['topP'] = config.top_p
        if config.top_k is not None:
            generation_config['topK'] = config.top_k
        if config.max_output_tokens is not None:
            generation_config['maxOutputTokens'] = config.max_output_tokens
        if config.stop_sequences:
            generation_config['stopSequences'] = config.stop_sequences
        
        if generation_config:
            request_dict['generationConfig'] = generation_config
        
        # System instruction
        if config.system_instruction:
            if isinstance(config.system_instruction, str):
                request_dict['systemInstruction'] = {
                    'role': 'user',
                    'parts': [{'text': config.system_instruction}]
                }
            else:
                request_dict['systemInstruction'] = config.system_instruction
        
        # Tools
        if config.tools:
            tools = []
            for tool in config.tools:
                tool_dict = {'functionDeclarations': []}
                for func_decl in tool.function_declarations:
                    tool_dict['functionDeclarations'].append({
                        'name': func_decl.name,
                        'description': func_decl.description,
                        'parameters': func_decl.parameters
                    })
                tools.append(tool_dict)
            request_dict['tools'] = tools
        
        # Safety settings
        if config.safety_settings:
            safety_settings = []
            for setting in config.safety_settings:
                safety_settings.append({
                    'category': setting.category,
                    'threshold': setting.threshold
                })
            request_dict['safetySettings'] = safety_settings
    
    # Add URL template
    request_dict['_url'] = {'model': parameter_model.model}
    
    return request_dict


def _GenerateContentParameters_to_vertex(api_client, parameter_model):
    """Convert GenerateContentParameters to Vertex AI API format."""
    # For now, use the same format as MLDev
    # In a real implementation, this would have Vertex-specific transformations
    return _GenerateContentParameters_to_mldev(api_client, parameter_model)


def _GenerateContentResponse_from_mldev(response_dict):
    """Convert MLDev API response to internal format."""
    return response_dict


def _GenerateContentResponse_from_vertex(response_dict):
    """Convert Vertex AI API response to internal format."""
    return response_dict


class Models:
    """Synchronous Models API."""
    
    def __init__(self, api_client):
        self._api_client = api_client
    
    def generate_content(
        self,
        *,
        model: str,
        contents: Union[str, Content, list],
        config: Optional[GenerateContentConfig] = None,
    ) -> GenerateContentResponse:
        """Generate content using the specified model.
        
        Args:
            model: The model to use for generation
            contents: The input content(s)
            config: Optional configuration for generation
            
        Returns:
            GenerateContentResponse with the generated content
        """
        # Create parameter model
        from .types import _GenerateContentParameters
        parameter_model = _GenerateContentParameters(
            model=model,
            contents=contents,
            config=config
        )
        
        # Convert to API request format
        if self._api_client.vertexai:
            request_dict = _GenerateContentParameters_to_vertex(
                self._api_client, parameter_model
            )
            path = '{model}:generateContent'.format_map(request_dict.get('_url', {}))
        else:
            request_dict = _GenerateContentParameters_to_mldev(
                self._api_client, parameter_model
            )
            path = '{model}:generateContent'.format_map(request_dict.get('_url', {}))
        
        # Handle query parameters
        query_params = request_dict.get('_query')
        if query_params:
            path = f'{path}?{urlencode(query_params)}'
        
        # Remove internal keys
        request_dict.pop('_url', None)
        request_dict.pop('_query', None)
        request_dict.pop('config', None)
        
        # Get HTTP options
        http_options = None
        if config and hasattr(config, 'http_options'):
            http_options = config.http_options
        
        # Make API request
        response = self._api_client.request('post', path, request_dict, http_options)
        
        # Parse response
        response_dict = {} if not response.body else json.loads(response.body)
        
        if self._api_client.vertexai:
            response_dict = _GenerateContentResponse_from_vertex(response_dict)
        else:
            response_dict = _GenerateContentResponse_from_mldev(response_dict)
        
        # Create response object
        return_value = GenerateContentResponse._from_response(
            response=response_dict, 
            kwargs=parameter_model.model_dump() if hasattr(parameter_model, 'model_dump') else {}
        )
        
        # Verify response
        self._api_client._verify_response(return_value)
        return return_value
    
    def generate_content_stream(
        self,
        *,
        model: str,
        contents: Union[str, Content, list],
        config: Optional[GenerateContentConfig] = None,
    ) -> Iterator[GenerateContentResponse]:
        """Generate content using streaming.
        
        Args:
            model: The model to use for generation
            contents: The input content(s)
            config: Optional configuration for generation
            
        Yields:
            GenerateContentResponse chunks
        """
        # Create parameter model
        from .types import _GenerateContentParameters
        parameter_model = _GenerateContentParameters(
            model=model,
            contents=contents,
            config=config
        )
        
        # Convert to API request format
        if self._api_client.vertexai:
            request_dict = _GenerateContentParameters_to_vertex(
                self._api_client, parameter_model
            )
            path = '{model}:streamGenerateContent?alt=sse'.format_map(request_dict.get('_url', {}))
        else:
            request_dict = _GenerateContentParameters_to_mldev(
                self._api_client, parameter_model
            )
            path = '{model}:streamGenerateContent?alt=sse'.format_map(request_dict.get('_url', {}))
        
        # Handle query parameters
        query_params = request_dict.get('_query')
        if query_params:
            path = f'{path}&{urlencode(query_params)}'
        
        # Remove internal keys
        request_dict.pop('_url', None)
        request_dict.pop('_query', None)
        request_dict.pop('config', None)
        
        # Get HTTP options
        http_options = None
        if config and hasattr(config, 'http_options'):
            http_options = config.http_options
        
        # Make streaming API request
        response_stream = self._api_client.request_streamed('post', path, request_dict, http_options)
        
        # Process each chunk
        for response in response_stream:
            response_dict = {} if not response.body else json.loads(response.body)
            
            if self._api_client.vertexai:
                response_dict = _GenerateContentResponse_from_vertex(response_dict)
            else:
                response_dict = _GenerateContentResponse_from_mldev(response_dict)
            
            # Create response object
            return_value = GenerateContentResponse._from_response(
                response=response_dict,
                kwargs=parameter_model.model_dump() if hasattr(parameter_model, 'model_dump') else {}
            )
            
            # Verify response
            self._api_client._verify_response(return_value)
            yield return_value
    def count_tokens(
        self,
        *,
        model: str,
        contents: Union[str, Content, list],
        config: Optional[GenerateContentConfig] = None,
    ) -> dict:
        """Count tokens for the given contents.
        
        Args:
            model: The model to use for token counting
            contents: The input content(s)
            config: Optional configuration
            
        Returns:
            Token count information
        """
        # Create parameter model
        from .types import _CountTokensParameters
        parameter_model = _CountTokensParameters(
            model=model,
            contents=contents,
            config=config
        )
        
        # Convert to API request format
        if self._api_client.vertexai:
            request_dict = _CountTokensParameters_to_vertex(
                self._api_client, parameter_model
            )
            path = '{model}:countTokens'.format_map(request_dict.get('_url', {}))
        else:
            request_dict = _CountTokensParameters_to_mldev(
                self._api_client, parameter_model
            )
            path = '{model}:countTokens'.format_map(request_dict.get('_url', {}))
        
        # Handle query parameters
        query_params = request_dict.get('_query')
        if query_params:
            path = f'{path}?{urlencode(query_params)}'
        
        # Remove internal keys
        request_dict.pop('_url', None)
        request_dict.pop('_query', None)
        request_dict.pop('config', None)
        
        # Get HTTP options
        http_options = None
        if config and hasattr(config, 'http_options'):
            http_options = config.http_options
        
        # Make API request
        response = self._api_client.request('post', path, request_dict, http_options)
        
        # Parse response
        response_dict = {} if not response.body else json.loads(response.body)
        
        if self._api_client.vertexai:
            response_dict = _CountTokensResponse_from_vertex(response_dict)
        else:
            response_dict = _CountTokensResponse_from_mldev(response_dict)
        
        return response_dict


class AsyncModels:
    """Asynchronous Models API."""
    
    def __init__(self, api_client):
        self._api_client = api_client
    
    async def generate_content(
        self,
        *,
        model: str,
        contents: Union[str, Content, list],
        config: Optional[GenerateContentConfig] = None,
    ) -> GenerateContentResponse:
        """Async version of generate_content."""
        # Create parameter model
        from .types import _GenerateContentParameters
        parameter_model = _GenerateContentParameters(
            model=model,
            contents=contents,
            config=config
        )
        
        # Convert to API request format
        if self._api_client.vertexai:
            request_dict = _GenerateContentParameters_to_vertex(
                self._api_client, parameter_model
            )
            path = '{model}:generateContent'.format_map(request_dict.get('_url', {}))
        else:
            request_dict = _GenerateContentParameters_to_mldev(
                self._api_client, parameter_model
            )
            path = '{model}:generateContent'.format_map(request_dict.get('_url', {}))
        
        # Handle query parameters
        query_params = request_dict.get('_query')
        if query_params:
            path = f'{path}?{urlencode(query_params)}'
        
        # Remove internal keys
        request_dict.pop('_url', None)
        request_dict.pop('_query', None)
        request_dict.pop('config', None)
        
        # Get HTTP options
        http_options = None
        if config and hasattr(config, 'http_options'):
            http_options = config.http_options
        
        # Make async API request
        response = await self._api_client.async_request('post', path, request_dict, http_options)
        
        # Parse response
        response_dict = {} if not response.body else json.loads(response.body)
        
        if self._api_client.vertexai:
            response_dict = _GenerateContentResponse_from_vertex(response_dict)
        else:
            response_dict = _GenerateContentResponse_from_mldev(response_dict)
        
        # Create response object
        return_value = GenerateContentResponse._from_response(
            response=response_dict,
            kwargs=parameter_model.model_dump() if hasattr(parameter_model, 'model_dump') else {}
        )
        
        # Verify response
        self._api_client._verify_response(return_value)
        return return_value
    
    async def generate_content_stream(
        self,
        *,
        model: str,
        contents: Union[str, Content, list],
        config: Optional[GenerateContentConfig] = None,
    ) -> AsyncIterator[GenerateContentResponse]:
        """Async version of generate_content_stream."""
        # Create parameter model
        from .types import _GenerateContentParameters
        parameter_model = _GenerateContentParameters(
            model=model,
            contents=contents,
            config=config
        )
        
        # Convert to API request format
        if self._api_client.vertexai:
            request_dict = _GenerateContentParameters_to_vertex(
                self._api_client, parameter_model
            )
            path = '{model}:streamGenerateContent?alt=sse'.format_map(request_dict.get('_url', {}))
        else:
            request_dict = _GenerateContentParameters_to_mldev(
                self._api_client, parameter_model
            )
            path = '{model}:streamGenerateContent?alt=sse'.format_map(request_dict.get('_url', {}))
        
        # Handle query parameters
        query_params = request_dict.get('_query')
        if query_params:
            path = f'{path}&{urlencode(query_params)}'
        
        # Remove internal keys
        request_dict.pop('_url', None)
        request_dict.pop('_query', None)
        request_dict.pop('config', None)
        
        # Get HTTP options
        http_options = None
        if config and hasattr(config, 'http_options'):
            http_options = config.http_options
        
        # Make async streaming API request
        response_stream = await self._api_client.async_request_streamed('post', path, request_dict, http_options)
        
        # Process each chunk
        async for response in response_stream:
            response_dict = {} if not response.body else json.loads(response.body)
            
            if self._api_client.vertexai:
                response_dict = _GenerateContentResponse_from_vertex(response_dict)
            else:
                response_dict = _GenerateContentResponse_from_mldev(response_dict)
            
            # Create response object
            return_value = GenerateContentResponse._from_response(
                response=response_dict,
                kwargs=parameter_model.model_dump() if hasattr(parameter_model, 'model_dump') else {}
            )
            
            # Verify response
            self._api_client._verify_response(return_value)
            yield return_value
    
    async def count_tokens(
        self,
        *,
        model: str,
        contents: Union[str, Content, list],
        config: Optional[GenerateContentConfig] = None,
    ) -> dict:
        """Async version of count_tokens."""
        # Create parameter model
        from .types import _CountTokensParameters
        parameter_model = _CountTokensParameters(
            model=model,
            contents=contents,
            config=config
        )
        
        # Convert to API request format
        if self._api_client.vertexai:
            request_dict = _CountTokensParameters_to_vertex(
                self._api_client, parameter_model
            )
            path = '{model}:countTokens'.format_map(request_dict.get('_url', {}))
        else:
            request_dict = _CountTokensParameters_to_mldev(
                self._api_client, parameter_model
            )
            path = '{model}:countTokens'.format_map(request_dict.get('_url', {}))
        
        # Handle query parameters
        query_params = request_dict.get('_query')
        if query_params:
            path = f'{path}?{urlencode(query_params)}'
        
        # Remove internal keys
        request_dict.pop('_url', None)
        request_dict.pop('_query', None)
        request_dict.pop('config', None)
        
        # Get HTTP options
        http_options = None
        if config and hasattr(config, 'http_options'):
            http_options = config.http_options
        
        # Make async API request
        response = await self._api_client.async_request('post', path, request_dict, http_options)
        
        # Parse response
        response_dict = {} if not response.body else json.loads(response.body)
        
        if self._api_client.vertexai:
            response_dict = _CountTokensResponse_from_vertex(response_dict)
        else:
            response_dict = _CountTokensResponse_from_mldev(response_dict)
        
        return response_dict


# Additional transformer functions needed for token counting
def _CountTokensParameters_to_mldev(api_client, parameter_model):
    """Convert CountTokensParameters to MLDev API format."""
    request_dict = {}
    
    # Convert contents (same as generate_content)
    if parameter_model.contents:
        contents = []
        for content in parameter_model.contents:
            if isinstance(content, str):
                contents.append({
                    'role': 'user',
                    'parts': [{'text': content}]
                })
            elif isinstance(content, Content):
                content_dict = {
                    'role': content.role,
                    'parts': []
                }
                for part in content.parts:
                    if part.text:
                        content_dict['parts'].append({'text': part.text})
                    elif part.inline_data:
                        content_dict['parts'].append({
                            'inlineData': {
                                'mimeType': part.inline_data.mime_type,
                                'data': part.inline_data.data
                            }
                        })
                contents.append(content_dict)
        request_dict['contents'] = contents
    
    # Add URL template
    request_dict['_url'] = {'model': parameter_model.model}
    
    return request_dict


def _CountTokensParameters_to_vertex(api_client, parameter_model):
    """Convert CountTokensParameters to Vertex AI API format."""
    return _CountTokensParameters_to_mldev(api_client, parameter_model)


def _CountTokensResponse_from_mldev(response_dict):
    """Convert MLDev API response to internal format."""
    return response_dict


def _CountTokensResponse_from_vertex(response_dict):
    """Convert Vertex AI API response to internal format."""
    return response_dict