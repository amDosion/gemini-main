"""
Inpainting Handler Module

This module implements the handler for Google Imagen inpainting mode.
Inpainting fills masked regions in an image with generated content.

Design:
- Delegates to existing image_edit services
- Validates parameters before execution
- Provides mode metadata
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class InpaintingHandler:
    """
    Handler for image inpainting operations.
    
    This handler fills masked regions in an image with generated content
    using Google Imagen.
    
    Example:
        >>> handler = InpaintingHandler()
        >>> result = await handler.execute({
        ...     "image": "base64_or_url",
        ...     "mask": "base64_mask",
        ...     "prompt": "fill with flowers",
        ...     "model": "imagen-3.0-generate-001"
        ... })
    """
    
    def __init__(self):
        """Initialize the inpainting handler."""
        logger.info("[InpaintingHandler] Initialized")
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute inpainting operation.
        
        Args:
            params: Operation parameters
                - image: Base64 encoded image or URL
                - mask: Base64 encoded mask image
                - prompt: Text prompt for inpainting
                - model: Model to use (default: imagen-3.0-generate-001)
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
            raise ValueError("Invalid parameters for inpainting")
        
        logger.info(f"[InpaintingHandler] Executing inpainting with model: {params.get('model', 'imagen-3.0-generate-001')}")
        
        # Import here to avoid circular dependencies
        from ..image_edit_coordinator import ImageEditCoordinator
        
        # Create coordinator and get editor
        coordinator = ImageEditCoordinator(
            user_id=params.get('user_id'),
            db=params.get('db')
        )
        editor = coordinator.get_editor()
        
        # Execute inpainting
        try:
            result = await editor.inpaint(
                image=params['image'],
                mask=params['mask'],
                prompt=params['prompt'],
                model=params.get('model', 'imagen-3.0-generate-001'),
                number_of_images=params.get('number_of_images', 1)
            )
            
            logger.info(f"[InpaintingHandler] Inpainting completed successfully")
            return result
        
        except Exception as e:
            logger.error(f"[InpaintingHandler] Inpainting failed: {e}")
            raise RuntimeError(f"Inpainting operation failed: {e}")
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate inpainting parameters.
        
        Args:
            params: Parameters to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Required parameters
        if 'image' not in params:
            logger.error("[InpaintingHandler] Missing required parameter: image")
            return False
        
        if 'mask' not in params:
            logger.error("[InpaintingHandler] Missing required parameter: mask")
            return False
        
        if 'prompt' not in params:
            logger.error("[InpaintingHandler] Missing required parameter: prompt")
            return False
        
        # Validate image format
        image = params['image']
        if not isinstance(image, str) or len(image) == 0:
            logger.error("[InpaintingHandler] Invalid image parameter")
            return False
        
        # Validate mask format
        mask = params['mask']
        if not isinstance(mask, str) or len(mask) == 0:
            logger.error("[InpaintingHandler] Invalid mask parameter")
            return False
        
        # Validate prompt
        prompt = params['prompt']
        if not isinstance(prompt, str) or len(prompt) == 0:
            logger.error("[InpaintingHandler] Invalid prompt parameter")
            return False
        
        logger.debug("[InpaintingHandler] Parameters validated successfully")
        return True
    
    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get inpainting mode information.
        
        Returns:
            Mode metadata
        """
        return {
            "mode_id": "image-inpainting",
            "name": "Image Inpainting",
            "description": "Fill masked regions in an image with generated content",
            "category": "image-editing",
            "required_params": ["image", "mask", "prompt"],
            "optional_params": ["model", "number_of_images"],
            "default_model": "imagen-3.0-generate-001",
            "supported_models": [
                "imagen-3.0-generate-001",
                "imagen-3.0-fast-generate-001"
            ],
            "platform_support": "either"  # Both Vertex AI and Developer API
        }
