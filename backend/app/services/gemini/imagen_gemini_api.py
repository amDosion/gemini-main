"""
Gemini API implementation for Imagen image generation.

This module provides image generation using the Gemini API with simple API key authentication.
Note: person_generation parameter has been removed. The API uses its default value
(allow_adult), which allows normal adult and children images without NSFW content.
"""

import logging
import base64
import os
import tempfile
from typing import Dict, Any, List, Optional

from .imagen_base import BaseImageGenerator
from .imagen_common import (
    validate_aspect_ratio,
    validate_image_size,
    encode_image_to_base64,
    ParameterValidationError,
    APIError,
    ContentPolicyError,
    VALID_ASPECT_RATIOS,
    VALID_IMAGE_SIZES
)

logger = logging.getLogger(__name__)

# Import Google GenAI SDK
try:
    from google.genai import types as genai_types
    from google import genai as google_genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")


class GeminiAPIImageGenerator(BaseImageGenerator):
    """
    Image generator using Gemini API.
    
    Features:
    - Simple authentication with API key only
    - Supports most Imagen parameters
    - person_generation parameter removed (API uses default: allow_adult)
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini API image generator.
        
        Args:
            api_key: Gemini API key
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("google.genai not available. Install with: pip install google-genai")
        
        self.api_key = api_key
        self._client = None
        self._initialized = False
        
        logger.info("[GeminiAPIImageGenerator] Initialized with API key")
    
    def _ensure_initialized(self):
        """Ensure client is initialized (lazy loading)."""
        if self._initialized:
            return
        
        try:
            self._client = google_genai.Client(api_key=self.api_key)
            self._initialized = True
            logger.info("[GeminiAPIImageGenerator] Client initialized successfully")
        except Exception as e:
            logger.error(f"[GeminiAPIImageGenerator] Failed to initialize client: {e}")
            raise APIError(
                f"Failed to initialize Gemini API client: {e}",
                api_type="gemini_api",
                original_error=e
            )
    
    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate images using Gemini API.
        
        Supported parameters:
        - number_of_images (1-4)
        - aspect_ratio ('1:1', '3:4', '4:3', '9:16', '16:9')
        - image_size ('1K', '2K')
        - output_mime_type ('image/png', 'image/jpeg')
        - output_compression_quality (1-100)
        - include_rai_reason (bool)
        - image_style (str)
        
        Note: person_generation parameter has been removed. The API will use
        its default value (allow_adult), which allows normal adult and children
        images without NSFW content.
        
        Args:
            prompt: Text description of the image
            model: Model to use
            **kwargs: Additional parameters
        
        Returns:
            List of generated images
        """
        self._ensure_initialized()
        self.validate_parameters(**kwargs)
        
        logger.info(f"[GeminiAPIImageGenerator] Generating image: model={model}, prompt={prompt[:50]}...")
        
        # Build configuration
        config = self._build_config(**kwargs)
        
        # Apply style to prompt if specified
        image_style = kwargs.get('image_style')
        effective_prompt = prompt
        if image_style and image_style.lower() != "none":
            effective_prompt = f"{prompt}, style: {image_style}"
            logger.info(f"[GeminiAPIImageGenerator] Applied style: {image_style}")
        
        try:
            # Call Gemini API
            response = self._client.models.generate_images(
                model=model,
                prompt=effective_prompt,
                config=config
            )
            
            if not response.generated_images:
                raise APIError("No images generated", api_type="gemini_api")
            
            # Process results
            return self._process_response(response, **kwargs)
            
        except Exception as e:
            logger.error(f"[GeminiAPIImageGenerator] Generation failed: {e}")
            raise APIError(
                f"Image generation failed: {e}",
                api_type="gemini_api",
                original_error=e
            )
    
    def _build_config(self, **kwargs) -> 'genai_types.GenerateImagesConfig':
        """Build Gemini API configuration from parameters."""
        number_of_images = kwargs.get('number_of_images', 1)
        number_of_images = min(max(number_of_images, 1), 4)
        
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        include_rai_reason = kwargs.get('include_rai_reason', True)
        output_mime_type = kwargs.get('output_mime_type', 'image/jpeg')
        
        config_kwargs = {
            "number_of_images": number_of_images,
            "aspect_ratio": aspect_ratio,
            "output_mime_type": output_mime_type,
            "include_rai_reason": include_rai_reason,
        }
        
        # Add optional parameters
        image_size = kwargs.get('image_size')
        if image_size and image_size in VALID_IMAGE_SIZES:
            config_kwargs["image_size"] = image_size
        
        logger.info(f"[GeminiAPIImageGenerator] Config: {config_kwargs}")
        
        return genai_types.GenerateImagesConfig(**config_kwargs)
    
    def _process_response(
        self,
        response,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Process Gemini API response and extract images."""
        output_mime_type = kwargs.get('output_mime_type', 'image/jpeg')
        results = []
        
        for idx, generated_image in enumerate(response.generated_images):
            # Check for RAI filtering
            if hasattr(generated_image, 'rai_filtered_reason') and generated_image.rai_filtered_reason:
                logger.warning(f"[GeminiAPIImageGenerator] Image {idx} filtered: {generated_image.rai_filtered_reason}")
                continue
            
            if not generated_image.image:
                continue
            
            if not hasattr(generated_image.image, 'image_bytes') or generated_image.image.image_bytes is None:
                logger.warning(f"[GeminiAPIImageGenerator] Image {idx} has no image_bytes")
                continue
            
            # Save to temp file and read back
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                generated_image.image.save(tmp_path)
                with open(tmp_path, 'rb') as f:
                    image_bytes = f.read()
                b64_data = encode_image_to_base64(image_bytes)
                
                result = {
                    "url": f"data:{output_mime_type};base64,{b64_data}",
                    "mimeType": output_mime_type,
                    "index": idx,
                    "size": len(image_bytes)
                }
                
                # Add safety attributes if available
                if hasattr(generated_image, 'safety_attributes') and generated_image.safety_attributes:
                    safety_attrs = {}
                    if hasattr(generated_image.safety_attributes, 'content_type'):
                        safety_attrs["content_type"] = generated_image.safety_attributes.content_type
                    if hasattr(generated_image.safety_attributes, 'categories'):
                        safety_attrs["categories"] = generated_image.safety_attributes.categories
                    if hasattr(generated_image.safety_attributes, 'scores'):
                        safety_attrs["scores"] = generated_image.safety_attributes.scores
                    if safety_attrs:
                        result["safety_attributes"] = safety_attrs
                
                # Add RAI reason if available
                if hasattr(generated_image, 'rai_reason') and generated_image.rai_reason:
                    result["rai_reason"] = generated_image.rai_reason
                
                results.append(result)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        # Check if any images were successfully generated
        if not results:
            filtered_count = sum(
                1 for img in response.generated_images
                if hasattr(img, 'rai_filtered_reason') and img.rai_filtered_reason
            )
            if filtered_count > 0:
                first_reason = next(
                    (img.rai_filtered_reason for img in response.generated_images
                     if hasattr(img, 'rai_filtered_reason') and img.rai_filtered_reason),
                    "Unknown reason"
                )
                raise ContentPolicyError(f"All images filtered by content policy: {first_reason}")
            else:
                raise APIError("No valid images generated", api_type="gemini_api")
        
        return results
    
    def validate_parameters(self, **kwargs) -> None:
        """
        Validate Gemini API specific parameters.
        
        Raises:
            ParameterValidationError: If parameters are invalid
        """
        # Validate aspect ratio
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        validate_aspect_ratio(aspect_ratio)
        
        # Validate image size
        image_size = kwargs.get('image_size')
        validate_image_size(image_size)
        
        # Note: person_generation parameter has been removed.
        # The API will use its default value (allow_adult).
        
        # Validate number of images
        number_of_images = kwargs.get('number_of_images', 1)
        if not isinstance(number_of_images, int) or number_of_images < 1 or number_of_images > 4:
            raise ParameterValidationError(
                f"Invalid number_of_images: {number_of_images}. Must be 1-4"
            )
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get Gemini API capabilities."""
        return {
            'api_type': 'gemini_api',
            'max_images': 4,
            'aspect_ratios': VALID_ASPECT_RATIOS,
            'image_sizes': VALID_IMAGE_SIZES,
            'person_generation': None,  # Parameter removed, API uses default
            'supports_allow_all': False
        }
    
    def get_supported_models(self) -> List[str]:
        """Get supported Imagen models."""
        return [
            'imagen-4.0-generate-001',
            'imagen-3.0-generate-002'
        ]
