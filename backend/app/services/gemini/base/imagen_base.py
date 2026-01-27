"""
Abstract base class for Imagen image generators.

This module defines the interface that all Imagen implementations must follow,
enabling independent optimization of Gemini API and Vertex AI implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseImageGenerator(ABC):
    """
    Abstract base class for image generators.
    
    All Imagen implementations (Gemini API, Vertex AI) must inherit from this class
    and implement its abstract methods. This ensures a consistent interface while
    allowing independent optimization of each implementation.
    """
    
    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate images based on text prompt.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use for generation
            **kwargs: Additional generation parameters
        
        Returns:
            List of generated images with metadata
            Each dict contains: url, mimeType, index, size, and optional safety_attributes
        
        Raises:
            ParameterValidationError: If parameters are invalid
            APIError: If API call fails
            ContentPolicyError: If content is blocked by safety filters
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, **kwargs) -> None:
        """
        Validate generation parameters for this specific API.
        
        Args:
            **kwargs: Parameters to validate
        
        Raises:
            ParameterValidationError: If any parameter is invalid
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get API-specific capabilities and limitations.
        
        Returns:
            Dictionary containing:
            - api_type: 'gemini_api' or 'vertex_ai'
            - max_images: Maximum number of images per request
            - aspect_ratios: List of supported aspect ratios
            - image_sizes: List of supported image sizes
            - person_generation: List of supported person generation values
            - supports_allow_all: Whether 'allow_all' is supported
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of models supported by this implementation.
        
        Returns:
            List of model names
        """
        pass
