"""
Virtual Try-On Handler Module

This module implements the handler for Google Imagen virtual try-on mode.
Virtual try-on replaces clothing items on a person with new garments.

Design:
- Delegates to existing tryon_service
- Validates parameters before execution
- Provides mode metadata
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class VirtualTryonHandler:
    """
    Handler for virtual try-on operations.
    
    This handler replaces clothing items on a person with new garments
    using Google Imagen.
    
    Example:
        >>> handler = VirtualTryonHandler()
        >>> result = await handler.execute({
        ...     "image": "base64_or_url",
        ...     "mask": "base64_mask",  # Optional
        ...     "prompt": "red summer dress",
        ...     "target_clothing": "upper body clothing"
        ... })
    """
    
    def __init__(self):
        """Initialize the virtual try-on handler."""
        logger.info("[VirtualTryonHandler] Initialized")
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute virtual try-on operation.
        
        Args:
            params: Operation parameters
                - image: Base64 encoded image or URL
                - prompt: Text prompt describing the clothing
                - mask: Base64 encoded mask image (optional, for Vertex AI)
                - target_clothing: Target clothing type (default: "upper body clothing")
                - edit_mode: Edit mode for Vertex AI (default: "inpainting-insert")
                - mask_mode: Mask mode for Vertex AI (default: "foreground")
                - dilation: Mask dilation for Vertex AI (default: 0.02)
                - api_key: Gemini API key for fallback (optional)
        
        Returns:
            Operation result:
                - success: Boolean indicating success
                - image: Generated image (base64)
                - mime_type: Image MIME type
                - error: Error message (if failed)
        
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If operation fails
        """
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters for virtual try-on")
        
        logger.info(f"[VirtualTryonHandler] Executing virtual try-on: target={params.get('target_clothing', 'upper body clothing')}")
        
        # Import here to avoid circular dependencies
        from ..tryon_service import tryon_service
        
        # Execute virtual try-on
        try:
            result = tryon_service.edit_with_mask(
                image_base64=params['image'],
                mask_base64=params.get('mask'),
                prompt=params['prompt'],
                edit_mode=params.get('edit_mode', 'inpainting-insert'),
                mask_mode=params.get('mask_mode', 'foreground'),
                dilation=params.get('dilation', 0.02),
                api_key=params.get('api_key'),
                target_clothing=params.get('target_clothing', 'upper body clothing')
            )
            
            if result.success:
                logger.info(f"[VirtualTryonHandler] Virtual try-on completed successfully")
                return {
                    "success": True,
                    "images": [result.image],  # Wrap in list for consistency
                    "mime_type": result.mime_type,
                    "usage": {}  # TryOnService doesn't return usage info
                }
            else:
                logger.error(f"[VirtualTryonHandler] Virtual try-on failed: {result.error}")
                raise RuntimeError(f"Virtual try-on operation failed: {result.error}")
        
        except Exception as e:
            logger.error(f"[VirtualTryonHandler] Virtual try-on failed: {e}")
            raise RuntimeError(f"Virtual try-on operation failed: {e}")
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate virtual try-on parameters.
        
        Args:
            params: Parameters to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Required parameters
        if 'image' not in params:
            logger.error("[VirtualTryonHandler] Missing required parameter: image")
            return False
        
        if 'prompt' not in params:
            logger.error("[VirtualTryonHandler] Missing required parameter: prompt")
            return False
        
        # Validate image format
        image = params['image']
        if not isinstance(image, str) or len(image) == 0:
            logger.error("[VirtualTryonHandler] Invalid image parameter")
            return False
        
        # Validate prompt
        prompt = params['prompt']
        if not isinstance(prompt, str) or len(prompt) == 0:
            logger.error("[VirtualTryonHandler] Invalid prompt parameter")
            return False
        
        # Validate mask if provided
        if 'mask' in params:
            mask = params['mask']
            if mask is not None and (not isinstance(mask, str) or len(mask) == 0):
                logger.error("[VirtualTryonHandler] Invalid mask parameter")
                return False
        
        logger.debug("[VirtualTryonHandler] Parameters validated successfully")
        return True
    
    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get virtual try-on mode information.
        
        Returns:
            Mode metadata
        """
        return {
            "mode_id": "virtual-try-on",
            "name": "Virtual Try-On",
            "description": "Replace clothing items on a person with new garments",
            "category": "image-editing",
            "required_params": ["image", "prompt"],
            "optional_params": [
                "mask",
                "target_clothing",
                "edit_mode",
                "mask_mode",
                "dilation",
                "api_key"
            ],
            "default_model": "imagen-3.0-capability-001",
            "supported_models": [
                "imagen-3.0-capability-001"
            ],
            "platform_support": "vertex_ai_preferred",  # Vertex AI preferred, Gemini API fallback
            "notes": "Mask is optional. If not provided, Gemini API will be used for automatic clothing detection."
        }
