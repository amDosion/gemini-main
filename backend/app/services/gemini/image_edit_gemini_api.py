"""
Gemini API implementation for image editing.

This module provides a stub implementation that raises NotSupportedError,
as image editing is only supported in Vertex AI, not in the Gemini API.
"""

import logging
from typing import Dict, Any, List, Optional

from .image_edit_base import BaseImageEditor
from .image_edit_common import NotSupportedError

logger = logging.getLogger(__name__)


class GeminiAPIImageEditor(BaseImageEditor):
    """
    Image editor stub for Gemini API.
    
    Image editing is NOT supported by the Gemini API.
    This class exists to provide a consistent interface and clear error messages.
    
    All edit_image() calls will raise NotSupportedError with instructions
    to use Vertex AI instead.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini API image editor stub.
        
        Args:
            api_key: Gemini API key (not used, but required for interface consistency)
        """
        self.api_key = api_key
        logger.info("[GeminiAPIImageEditor] Initialized (image editing not supported)")
    
    def edit_image(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Attempt to edit images using Gemini API.
        
        This method always raises NotSupportedError because image editing
        is not supported by the Gemini API.
        
        Args:
            prompt: Text description of the desired edit
            reference_images: Dictionary mapping reference image types to Base64 strings
            config: Optional configuration dictionary
        
        Returns:
            Never returns (always raises exception)
        
        Raises:
            NotSupportedError: Always raised with instructions to use Vertex AI
        """
        logger.warning("[GeminiAPIImageEditor] Image editing attempted but not supported")
        raise NotSupportedError(
            "Image editing is not supported by the Gemini API. "
            "Please configure Vertex AI (project_id, location, credentials) "
            "in your settings to use image editing features.",
            api_type="gemini_api"
        )

    
    def validate_parameters(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validate parameters (stub implementation).
        
        Since image editing is not supported, this method does nothing.
        The actual error will be raised when edit_image() is called.
        
        Args:
            prompt: Text description of the desired edit
            reference_images: Dictionary mapping reference image types to Base64 strings
            config: Optional configuration dictionary
        """
        # No validation needed since edit_image() will raise NotSupportedError
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get Gemini API image editing capabilities.
        
        Returns a dictionary indicating that image editing is not supported.
        
        Returns:
            Dictionary with supports_editing=False
        """
        return {
            'api_type': 'gemini_api',
            'supports_editing': False,
            'supported_edit_modes': [],
            'supported_reference_types': [],
            'max_images': 0,
            'aspect_ratios': [],
            'guidance_scale_range': (0, 0),
            'error_message': (
                "Image editing is not supported by the Gemini API. "
                "Please configure Vertex AI to use image editing features."
            )
        }
    
    def get_supported_models(self) -> List[str]:
        """
        Get supported models for image editing.
        
        Returns an empty list since image editing is not supported.
        
        Returns:
            Empty list
        """
        return []
