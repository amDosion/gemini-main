"""
Outpainting Handler Module

This module implements the handler for Google Imagen outpainting mode.
Outpainting extends image boundaries by generating new content around the original image.

Design:
- Delegates to existing image_edit services
- Validates parameters before execution
- Provides mode metadata
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class OutpaintingHandler:
    """
    Handler for image outpainting operations.
    
    This handler extends image boundaries by generating new content
    around the original image using Google Imagen.
    
    Example:
        >>> handler = OutpaintingHandler()
        >>> result = await handler.execute({
        ...     "image": "base64_or_url",
        ...     "prompt": "extend the beach scene",
        ...     "model": "imagen-3.0-generate-001"
        ... })
    """
    
    def __init__(self):
        """Initialize the outpainting handler."""
        logger.info("[OutpaintingHandler] Initialized")
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute outpainting operation.
        
        Args:
            params: Operation parameters
                - image: Base64 encoded image or URL
                - prompt: Text prompt for outpainting
                - model: Model to use (default: imagen-3.0-generate-001)
                - aspect_ratio: Target aspect ratio (optional)
                - number_of_images: Number of images to generate (default: 1)
        
        Returns:
            Operation result:
                - images: List of generated images (base64)
                - usage: Token usage information
        
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If operation fails
        """
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters for outpainting")
        
        logger.info(f"[OutpaintingHandler] Executing outpainting with model: {params.get('model', 'imagen-3.0-generate-001')}")
        
        # Import here to avoid circular dependencies
        from ..image_edit_coordinator import ImageEditCoordinator
        
        # Create coordinator and get editor
        coordinator = ImageEditCoordinator(
            user_id=params.get('user_id'),
            db=params.get('db')
        )
        editor = coordinator.get_editor()
        
        # Execute outpainting
        try:
            result = await editor.outpaint(
                image=params['image'],
                prompt=params['prompt'],
                model=params.get('model', 'imagen-3.0-generate-001'),
                aspect_ratio=params.get('aspect_ratio'),
                number_of_images=params.get('number_of_images', 1)
            )
            
            logger.info(f"[OutpaintingHandler] Outpainting completed successfully")
            return result
        
        except Exception as e:
            logger.error(f"[OutpaintingHandler] Outpainting failed: {e}")
            raise RuntimeError(f"Outpainting operation failed: {e}")
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate outpainting parameters.
        
        Args:
            params: Parameters to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Required parameters
        if 'image' not in params:
            logger.error("[OutpaintingHandler] Missing required parameter: image")
            return False
        
        if 'prompt' not in params:
            logger.error("[OutpaintingHandler] Missing required parameter: prompt")
            return False
        
        # Validate image format
        image = params['image']
        if not isinstance(image, str) or len(image) == 0:
            logger.error("[OutpaintingHandler] Invalid image parameter")
            return False
        
        # Validate prompt
        prompt = params['prompt']
        if not isinstance(prompt, str) or len(prompt) == 0:
            logger.error("[OutpaintingHandler] Invalid prompt parameter")
            return False
        
        logger.debug("[OutpaintingHandler] Parameters validated successfully")
        return True
    
    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get outpainting mode information.
        
        Returns:
            Mode metadata
        """
        return {
            "mode_id": "image-outpainting",
            "name": "Image Outpainting",
            "description": "Extend image boundaries by generating new content around the original image",
            "category": "image-editing",
            "required_params": ["image", "prompt"],
            "optional_params": ["model", "aspect_ratio", "number_of_images"],
            "default_model": "imagen-3.0-generate-001",
            "supported_models": [
                "imagen-3.0-generate-001",
                "imagen-3.0-fast-generate-001"
            ],
            "platform_support": "either"  # Both Vertex AI and Developer API
        }
