"""
Adapter Pattern Implementation for Legacy Compatibility

This module implements the adapter pattern to bridge between the legacy Gemini service
implementation and the new official SDK compatibility layer. This ensures that existing
code can continue to work while new code can use the official SDK interfaces.
"""

from typing import Any, Dict, List, Optional, Union, AsyncGenerator
import logging
from ..agent.types import (
    GenerateContentConfig,
    GenerateContentResponse,
    File,
    UploadFileConfig,
    Content,
    Part
)

logger = logging.getLogger(__name__)


class LegacyToOfficialAdapter:
    """
    Adapter to convert legacy Gemini service calls to official SDK format.
    
    This adapter allows legacy code to continue working while internally using
    the new official SDK compatibility layer.
    """
    
    def __init__(self, official_client):
        """
        Initialize the adapter with an official client.
        
        Args:
            official_client: Instance of the official Client
        """
        self.official_client = official_client
        
    def adapt_chat_request(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Adapt legacy chat request to official format.
        
        Args:
            messages: Legacy message format
            model: Model name
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with official SDK parameters
        """
        # Convert legacy messages to official Content format
        contents = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if isinstance(content, str):
                parts = [Part(text=content)]
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(Part(text=item))
                    elif isinstance(item, dict):
                        if 'text' in item:
                            parts.append(Part(text=item['text']))
                        elif 'image_url' in item:
                            # Handle image content
                            # TODO: Convert image URL to FileData
                            pass
            else:
                parts = [Part(text=str(content))]
            
            contents.append(Content(role=role, parts=parts))
        
        # Build configuration
        config = GenerateContentConfig()
        
        # Map legacy parameters to official config
        if 'temperature' in kwargs:
            config.temperature = kwargs['temperature']
        if 'max_tokens' in kwargs:
            config.max_output_tokens = kwargs['max_tokens']
        if 'top_p' in kwargs:
            config.top_p = kwargs['top_p']
        if 'top_k' in kwargs:
            config.top_k = kwargs['top_k']
        if 'stop' in kwargs:
            config.stop_sequences = kwargs['stop']
        
        return {
            'model': model,
            'contents': contents,
            'config': config
        }
    
    def adapt_chat_response(
        self,
        official_response: GenerateContentResponse
    ) -> Dict[str, Any]:
        """
        Adapt official response to legacy format.
        
        Args:
            official_response: Official SDK response
            
        Returns:
            Dictionary in legacy format
        """
        # Extract the main content
        content = ""
        if official_response.candidates:
            candidate = official_response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        content += part.text
        
        # Build legacy response format
        return {
            'choices': [{
                'message': {
                    'role': 'assistant',
                    'content': content
                },
                'finish_reason': official_response.candidates[0].finish_reason if official_response.candidates else None
            }],
            'usage': {
                'total_tokens': official_response.usage_metadata.get('total_token_count', 0) if official_response.usage_metadata else 0,
                'prompt_tokens': official_response.usage_metadata.get('prompt_token_count', 0) if official_response.usage_metadata else 0,
                'completion_tokens': official_response.usage_metadata.get('candidates_token_count', 0) if official_response.usage_metadata else 0,
            } if official_response.usage_metadata else {}
        }
    
    def adapt_file_upload_request(
        self,
        file_path: str,
        display_name: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adapt legacy file upload request to official format.
        
        Args:
            file_path: Path to file
            display_name: Display name for file
            mime_type: MIME type of file
            
        Returns:
            Dictionary with official SDK parameters
        """
        config = UploadFileConfig()
        if display_name:
            config.display_name = display_name
        if mime_type:
            config.mime_type = mime_type
        
        return {
            'file': file_path,
            'config': config
        }
    
    def adapt_file_upload_response(
        self,
        official_file: File
    ) -> Dict[str, Any]:
        """
        Adapt official file response to legacy format.
        
        Args:
            official_file: Official SDK File object
            
        Returns:
            Dictionary in legacy format
        """
        return {
            'name': official_file.name,
            'display_name': official_file.display_name,
            'mime_type': official_file.mime_type,
            'size_bytes': official_file.size_bytes,
            'uri': official_file.uri,
            'state': official_file.state,
            'create_time': official_file.create_time,
            'update_time': official_file.update_time,
            'expiration_time': official_file.expiration_time
        }


class OfficialToLegacyAdapter:
    """
    Adapter to convert official SDK calls to legacy format.
    
    This adapter allows new code using official SDK interfaces to work with
    the existing legacy infrastructure when needed.
    """
    
    def __init__(self, legacy_service):
        """
        Initialize the adapter with a legacy service.
        
        Args:
            legacy_service: Instance of the legacy GoogleService
        """
        self.legacy_service = legacy_service
    
    async def generate_content(
        self,
        model: str,
        contents: Union[str, List[Content]],
        config: Optional[GenerateContentConfig] = None
    ) -> GenerateContentResponse:
        """
        Generate content using legacy service but return official format.
        
        Args:
            model: Model name
            contents: Content to generate from
            config: Generation configuration
            
        Returns:
            GenerateContentResponse in official format
        """
        # Convert official format to legacy format
        messages = []
        
        if isinstance(contents, str):
            messages.append({'role': 'user', 'content': contents})
        elif isinstance(contents, list):
            for content in contents:
                if isinstance(content, Content):
                    text_parts = []
                    for part in content.parts:
                        if part.text:
                            text_parts.append(part.text)
                    if text_parts:
                        messages.append({
                            'role': content.role,
                            'content': ' '.join(text_parts)
                        })
        
        # Convert config to legacy parameters
        kwargs = {}
        if config:
            if config.temperature is not None:
                kwargs['temperature'] = config.temperature
            if config.max_output_tokens is not None:
                kwargs['max_tokens'] = config.max_output_tokens
            if config.top_p is not None:
                kwargs['top_p'] = config.top_p
            if config.top_k is not None:
                kwargs['top_k'] = config.top_k
            if config.stop_sequences:
                kwargs['stop'] = config.stop_sequences
        
        # Call legacy service
        legacy_response = await self.legacy_service.chat(messages, model, **kwargs)
        
        # Convert legacy response to official format
        candidates = []
        if 'choices' in legacy_response:
            for choice in legacy_response['choices']:
                message = choice.get('message', {})
                content_text = message.get('content', '')
                
                candidate_content = Content(
                    role='model',
                    parts=[Part(text=content_text)]
                )
                
                from ..agent.types import Candidate
                candidate = Candidate(
                    content=candidate_content,
                    finish_reason=choice.get('finish_reason')
                )
                candidates.append(candidate)
        
        return GenerateContentResponse(
            candidates=candidates,
            usage_metadata=legacy_response.get('usage', {})
        )
    
    async def upload_file(
        self,
        file: Union[str, bytes],
        config: Optional[UploadFileConfig] = None
    ) -> File:
        """
        Upload file using legacy service but return official format.
        
        Args:
            file: File path or bytes
            config: Upload configuration
            
        Returns:
            File in official format
        """
        # Convert to legacy parameters
        display_name = config.display_name if config else None
        mime_type = config.mime_type if config else None
        
        # Call legacy service
        legacy_response = await self.legacy_service.upload_file(
            file_path=file if isinstance(file, str) else None,
            display_name=display_name,
            mime_type=mime_type
        )
        
        # Convert to official format
        return File(
            name=legacy_response.get('name', ''),
            display_name=legacy_response.get('display_name'),
            mime_type=legacy_response.get('mime_type', ''),
            size_bytes=legacy_response.get('size_bytes', 0),
            create_time=legacy_response.get('create_time', ''),
            update_time=legacy_response.get('update_time', ''),
            expiration_time=legacy_response.get('expiration_time'),
            sha256_hash=b'',  # TODO: Get actual hash
            uri=legacy_response.get('uri', ''),
            state=legacy_response.get('state', 'ACTIVE')
        )


def create_legacy_adapter(official_client) -> LegacyToOfficialAdapter:
    """
    Factory function to create a legacy adapter.
    
    Args:
        official_client: Official SDK client instance
        
    Returns:
        Configured LegacyToOfficialAdapter
    """
    return LegacyToOfficialAdapter(official_client)


def create_official_adapter(legacy_service) -> OfficialToLegacyAdapter:
    """
    Factory function to create an official adapter.
    
    Args:
        legacy_service: Legacy service instance
        
    Returns:
        Configured OfficialToLegacyAdapter
    """
    return OfficialToLegacyAdapter(legacy_service)