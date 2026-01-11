"""
Abstract base class for image editors.

This module defines the interface that all image editing implementations must follow,
enabling independent optimization of Gemini API and Vertex AI implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseImageEditor(ABC):
    """
    Abstract base class for image editors.
    
    All image editing implementations (Gemini API, Vertex AI) must inherit from this class
    and implement its abstract methods. This ensures a consistent interface while
    allowing independent optimization of each implementation.
    
    Image editing supports 6 reference image types:
    - raw (Required): Base image to edit
    - mask (Optional): Mask for inpainting operations
    - control (Optional): Control image for guided generation
    - style (Optional): Style reference for style transfer
    - subject (Optional): Subject reference for subject-aware editing
    - content (Optional): Content reference for content-aware editing
    """
    
    @abstractmethod
    def edit_image(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Edit images based on text prompt and reference images.
        
        Args:
            prompt: Text description of the desired edit
            reference_images: Dictionary mapping reference image types to Base64-encoded images
                Required key: 'raw' (base image)
                Optional keys: 'mask', 'control', 'style', 'subject', 'content'
            config: Optional configuration dictionary containing:
                - edit_mode: 'inpainting-insert', 'inpainting-remove', 'outpainting', 'product-image'
                - number_of_images: 1-4 (default: 1)
                - aspect_ratio: '1:1', '3:4', '4:3', '9:16', '16:9'
                - guidance_scale: 0-100 (controls adherence to prompt)
                - output_mime_type: 'image/png', 'image/jpeg'
                - safety_filter_level: 'block_most', 'block_some', 'block_few', 'block_fewest'
                - person_generation: 'dont_allow', 'allow_adult', 'allow_all'
        
        Returns:
            List of Base64-encoded edited image strings
        
        Raises:
            ValueError: If parameters are invalid
            NotSupportedError: If feature is not supported by this implementation
            RuntimeError: If API call fails
        
        Example:
            >>> editor = VertexAIImageEditor(project_id="my-project", location="us-central1")
            >>> reference_images = {
            ...     "raw": "base64_encoded_image_data",
            ...     "mask": "base64_encoded_mask_data"
            ... }
            >>> config = {
            ...     "edit_mode": "inpainting-insert",
            ...     "number_of_images": 2,
            ...     "aspect_ratio": "1:1"
            ... }
            >>> images = editor.edit_image("Add a red car", reference_images, config)
        """
        pass
    
    @abstractmethod
    def validate_parameters(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validate editing parameters for this specific API.
        
        Args:
            prompt: Text description of the desired edit
            reference_images: Dictionary mapping reference image types to Base64-encoded images
            config: Optional configuration dictionary
        
        Raises:
            ValueError: If any parameter is invalid
        
        Example:
            >>> editor.validate_parameters(
            ...     prompt="Add a red car",
            ...     reference_images={"raw": "base64_data"},
            ...     config={"edit_mode": "inpainting-insert"}
            ... )
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get API-specific capabilities and limitations.
        
        Returns:
            Dictionary containing:
            - api_type: 'gemini_api' or 'vertex_ai'
            - supports_editing: Whether image editing is supported
            - supported_edit_modes: List of supported edit modes
            - supported_reference_types: List of supported reference image types
            - max_images: Maximum number of images per request
            - aspect_ratios: List of supported aspect ratios
            - guidance_scale_range: Tuple of (min, max) guidance scale values
        
        Example:
            >>> capabilities = editor.get_capabilities()
            >>> print(capabilities)
            {
                'api_type': 'vertex_ai',
                'supports_editing': True,
                'supported_edit_modes': ['inpainting-insert', 'inpainting-remove', 'outpainting', 'product-image'],
                'supported_reference_types': ['raw', 'mask', 'control', 'style', 'subject', 'content'],
                'max_images': 4,
                'aspect_ratios': ['1:1', '3:4', '4:3', '9:16', '16:9'],
                'guidance_scale_range': (0, 100)
            }
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of models supported by this implementation.
        
        Returns:
            List of model names that support image editing
        
        Example:
            >>> models = editor.get_supported_models()
            >>> print(models)
            ['imagen-3.0-generate-001', 'imagen-3.0-fast-generate-001']
        """
        pass
