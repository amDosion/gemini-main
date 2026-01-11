"""
Official Google GenAI SDK Integration Adapter

This module provides integration between the existing Gemini service architecture
and the official Google GenAI SDK compatibility layer.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Union, AsyncGenerator
from pathlib import Path

# Import official SDK compatibility layer
from .official import Client
from .official.types import (
    GenerateContentConfig,
    Content,
    Part,
    Tool,
    FunctionDeclaration,
    SafetySetting
)

logger = logging.getLogger(__name__)


class OfficialSDKAdapter:
    """
    Adapter to integrate official Google GenAI SDK with existing service architecture.
    
    This adapter provides a bridge between the existing GoogleService interface
    and the official SDK, enabling gradual migration and feature compatibility.
    """
    
    def __init__(self, api_key: str, use_vertex: bool = False, project: str = None, location: str = None):
        """
        Initialize the official SDK adapter.
        
        Args:
            api_key: Google API key
            use_vertex: Whether to use Vertex AI API
            project: Google Cloud project ID (for Vertex AI)
            location: Google Cloud location (for Vertex AI)
        """
        self.api_key = api_key
        self.use_vertex = use_vertex
        self.project = project
        self.location = location
        
        # Initialize official SDK client
        if use_vertex:
            self.client = Client(
                vertexai=True,
                project=project,
                location=location or 'us-central1'
            )
        else:
            self.client = Client(api_key=api_key)
        
        logger.info(f"[Official SDK Adapter] Initialized (vertex={use_vertex})")
    
    async def generate_content(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate content using the official SDK.
        
        Args:
            messages: List of message dictionaries
            model: Model name
            **kwargs: Additional parameters
            
        Returns:
            Response dictionary compatible with existing interface
        """
        try:
            # Convert messages to official SDK format
            contents = self._convert_messages_to_contents(messages)
            
            # Build generation config
            config = self._build_generation_config(**kwargs)
            
            # Generate content using official SDK
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            
            # Convert response back to existing format
            return self._convert_response_to_dict(response)
            
        except Exception as e:
            logger.error(f"[Official SDK Adapter] Error in generate_content: {e}")
            raise
    
    async def stream_generate_content(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream generate content using the official SDK.
        
        Args:
            messages: List of message dictionaries
            model: Model name
            **kwargs: Additional parameters
            
        Yields:
            Response chunks compatible with existing interface
        """
        try:
            # Convert messages to official SDK format
            contents = self._convert_messages_to_contents(messages)
            
            # Build generation config
            config = self._build_generation_config(**kwargs)
            
            # Stream generate content using official SDK
            stream = self.client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config
            )
            
            # Convert each chunk back to existing format
            for chunk in stream:
                yield self._convert_response_to_dict(chunk)
                
        except Exception as e:
            logger.error(f"[Official SDK Adapter] Error in stream_generate_content: {e}")
            raise
    
    def _convert_messages_to_contents(self, messages: List[Dict[str, Any]]) -> List[Content]:
        """
        Convert existing message format to official SDK Content format.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            List of Content objects
        """
        contents = []
        
        for message in messages:
            role = message.get('role', 'user')
            content_text = message.get('content', '')
            
            # Handle different content types
            if isinstance(content_text, str):
                parts = [Part.from_text(content_text)]
            elif isinstance(content_text, list):
                parts = []
                for item in content_text:
                    if isinstance(item, dict):
                        if 'text' in item:
                            parts.append(Part.from_text(item['text']))
                        elif 'image_url' in item:
                            # Handle image content
                            parts.append(Part.from_uri(
                                file_uri=item['image_url']['url'],
                                mime_type='image/jpeg'  # Default, should be detected
                            ))
                    else:
                        parts.append(Part.from_text(str(item)))
            else:
                parts = [Part.from_text(str(content_text))]
            
            contents.append(Content(role=role, parts=parts))
        
        return contents
    
    def _build_generation_config(self, **kwargs) -> Optional[GenerateContentConfig]:
        """
        Build GenerateContentConfig from kwargs.
        
        Args:
            **kwargs: Generation parameters
            
        Returns:
            GenerateContentConfig object or None
        """
        config_params = {}
        
        # Map common parameters
        if 'temperature' in kwargs:
            config_params['temperature'] = kwargs['temperature']
        if 'top_p' in kwargs:
            config_params['top_p'] = kwargs['top_p']
        if 'top_k' in kwargs:
            config_params['top_k'] = kwargs['top_k']
        if 'max_tokens' in kwargs:
            config_params['max_output_tokens'] = kwargs['max_tokens']
        if 'stop_sequences' in kwargs:
            config_params['stop_sequences'] = kwargs['stop_sequences']
        
        # Handle system instruction
        if 'system_instruction' in kwargs:
            config_params['system_instruction'] = kwargs['system_instruction']
        
        # Handle tools/functions
        if 'tools' in kwargs:
            tools = []
            for tool in kwargs['tools']:
                if isinstance(tool, dict) and 'function' in tool:
                    func_def = tool['function']
                    function_declaration = FunctionDeclaration(
                        name=func_def['name'],
                        description=func_def.get('description', ''),
                        parameters=func_def.get('parameters', {})
                    )
                    tools.append(Tool(function_declarations=[function_declaration]))
            if tools:
                config_params['tools'] = tools
        
        # Handle safety settings
        if 'safety_settings' in kwargs:
            safety_settings = []
            for setting in kwargs['safety_settings']:
                safety_settings.append(SafetySetting(
                    category=setting['category'],
                    threshold=setting['threshold']
                ))
            config_params['safety_settings'] = safety_settings
        
        return GenerateContentConfig(**config_params) if config_params else None
    
    def _convert_response_to_dict(self, response) -> Dict[str, Any]:
        """
        Convert official SDK response to existing dictionary format.
        
        Args:
            response: Official SDK response object
            
        Returns:
            Dictionary compatible with existing interface
        """
        result = {
            'choices': [],
            'usage': {}
        }
        
        # Convert candidates to choices
        for i, candidate in enumerate(response.candidates):
            choice = {
                'index': i,
                'message': {
                    'role': 'assistant',
                    'content': ''
                },
                'finish_reason': candidate.finish_reason
            }
            
            # Extract text content
            if candidate.content and candidate.content.parts:
                content_parts = []
                for part in candidate.content.parts:
                    if part.text:
                        content_parts.append(part.text)
                choice['message']['content'] = ''.join(content_parts)
            
            result['choices'].append(choice)
        
        # Add usage metadata if available
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            result['usage'] = response.usage_metadata
        
        return result
    
    async def create_deep_research_interaction(
        self,
        query: str,
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True
    ) -> Dict[str, Any]:
        """
        Create a Deep Research Agent interaction using the official SDK.
        
        Args:
            query: Research query
            agent: Agent name
            background: Whether to run in background
            
        Returns:
            Interaction result
        """
        try:
            interaction = self.client.interactions.create(
                input=query,
                agent=agent,
                background=background
            )
            
            return {
                'id': interaction.id,
                'status': interaction.status,
                'outputs': interaction.outputs or [],
                'error': interaction.error
            }
            
        except Exception as e:
            logger.error(f"[Official SDK Adapter] Error in deep research: {e}")
            raise
    
    async def get_interaction_status(self, interaction_id: str) -> Dict[str, Any]:
        """
        Get the status of a Deep Research interaction.
        
        Args:
            interaction_id: Interaction ID
            
        Returns:
            Interaction status
        """
        try:
            interaction = self.client.interactions.get(interaction_id)
            
            return {
                'id': interaction.id,
                'status': interaction.status,
                'outputs': interaction.outputs or [],
                'error': interaction.error
            }
            
        except Exception as e:
            logger.error(f"[Official SDK Adapter] Error getting interaction status: {e}")
            raise
    
    def close(self):
        """Close the official SDK client."""
        if hasattr(self.client, 'close'):
            self.client.close()
    
    async def aclose(self):
        """Async close the official SDK client."""
        if hasattr(self.client, 'aio') and hasattr(self.client.aio, 'aclose'):
            await self.client.aio.aclose()