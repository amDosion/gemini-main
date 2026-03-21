"""
Base Provider Service Module

This module defines the abstract base class for all AI provider services.
All provider implementations must inherit from BaseProviderService and implement
the required abstract methods.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from abc import ABC, abstractmethod

from .model_capabilities import ModelConfig


class BaseProviderService(ABC):
    """
    Abstract base class for AI Provider services.
    
    All provider implementations (OpenAI, Google, Ollama, etc.) must inherit from
    this class and implement the required abstract methods.
    
    Attributes:
        api_key (str): API key for the provider
        api_url (Optional[str]): Custom API URL (if different from default)
        kwargs (Dict[str, Any]): Additional configuration parameters
    """
    
    def __init__(self, api_key: str, api_url: Optional[str] = None, **kwargs):
        """
        Initialize the provider service.
        
        Args:
            api_key: API key for authentication
            api_url: Optional custom API URL
            **kwargs: Additional configuration parameters:
                - timeout (float): Request timeout in seconds (default: 120.0)
                - max_retries (int): Maximum number of retries (default: 3)
                - max_tokens (int): Maximum tokens to generate
                - temperature (float): Sampling temperature (0.0-2.0)
        
        Raises:
            ValueError: If api_key is empty or None
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        
        self.api_key = api_key
        self.api_url = api_url
        self.kwargs = kwargs
    
    @abstractmethod
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat request and get a complete response (non-streaming).
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: Model identifier to use
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        
        Returns:
            Dict containing:
                - content: The response text
                - role: The role of the responder (usually 'assistant')
                - usage: Token usage information
                - model: The model used
                - finish_reason: Why the generation stopped
        
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass
    
    @abstractmethod
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a chat request and stream the response.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: Model identifier to use
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        
        Yields:
            Dict containing:
                - content: Incremental response text
                - chunk_type: Type of chunk ('content', 'reasoning', 'done', 'error')
                - finish_reason: (optional) Why the generation stopped
                - prompt_tokens: (optional) Number of prompt tokens
                - completion_tokens: (optional) Number of completion tokens
                - total_tokens: (optional) Total tokens used
                - error: (optional) Error message if chunk_type is 'error'
        
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[ModelConfig]:
        """
        Get list of available models for this provider.
        
        Returns:
            List of ModelConfig objects with complete model information
        
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this provider.
        
        Returns:
            Provider name (e.g., 'OpenAI', 'Google', 'Ollama')
        
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass
    
    # Optional methods - providers can override if they support these features
    
    async def generate_image(
        self, 
        prompt: str, 
        model: str, 
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            model: Model identifier to use
            **kwargs: Additional parameters (size, quality, style, etc.)
        
        Returns:
            List of Dict containing:
                - url: URL of the generated image
                - revised_prompt: (optional) Revised prompt used
                - mime_type: (optional) Image MIME type
        
        Raises:
            NotImplementedError: If provider doesn't support image generation
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} does not support image generation"
        )
    
    async def generate_video(
        self, 
        prompt: str, 
        model: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a video from a text prompt.
        
        Args:
            prompt: Text description of the video to generate
            model: Model identifier to use
            **kwargs: Additional parameters (duration, resolution, etc.)
        
        Returns:
            Dict containing:
                - url: URL of the generated video
                - duration: Video duration in seconds
        
        Raises:
            NotImplementedError: If provider doesn't support video generation
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} does not support video generation"
        )

    async def understand_video(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Understand / analyze a video input with a multimodal model.

        Args:
            prompt: Analysis instruction
            model: Model identifier to use
            **kwargs: Additional parameters (source_video, output format, etc.)

        Returns:
            Dict containing:
                - text: Human-readable summary
                - analysis: Structured analysis payload when available

        Raises:
            NotImplementedError: If provider doesn't support video understanding
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} does not support video understanding"
        )

    async def delete_video(
        self,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Delete a generated / uploaded video asset at provider storage.

        Args:
            **kwargs: Provider-specific delete target metadata

        Returns:
            Dict containing delete status metadata

        Raises:
            NotImplementedError: If provider doesn't support video deletion
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} does not support video deletion"
        )
    
    async def generate_speech(
        self, 
        text: str, 
        voice: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate speech audio from text.
        
        Args:
            text: Text to convert to speech
            voice: Voice identifier to use
            **kwargs: Additional parameters (speed, format, etc.)
        
        Returns:
            Dict containing:
                - url: URL of the generated audio
                - format: Audio format (mp3, wav, etc.)
        
        Raises:
            NotImplementedError: If provider doesn't support speech generation
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} does not support speech generation"
        )
    
    async def upload_file(
        self, 
        file: bytes, 
        filename: str, 
        **kwargs
    ) -> str:
        """
        Upload a file to the provider's storage.
        
        Args:
            file: File content as bytes
            filename: Name of the file
            **kwargs: Additional parameters (purpose, etc.)
        
        Returns:
            File ID or URL that can be used in subsequent requests
        
        Raises:
            NotImplementedError: If provider doesn't support file upload
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} does not support file upload"
        )
