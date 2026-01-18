"""
Vertex AI implementation for Imagen image generation.

This module provides image generation using Vertex AI with service account authentication.
Supports both Imagen models (using generate_images) and Gemini image models (using generate_content).
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
    ConfigurationError,
    VALID_ASPECT_RATIOS,
    VALID_IMAGE_SIZES
)

logger = logging.getLogger(__name__)

# Gemini image models that use generate_content() method
GEMINI_IMAGE_MODELS = {
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-image-preview',
    'gemini-2.5-pro-image',
    'gemini-2.5-pro-image-preview',
    'gemini-3-pro-image',
    'gemini-3-pro-image-preview',
    'gemini-3.0-pro-image',
    'gemini-3.0-pro-image-preview',
}

# Veo video/image models (also use generate_content)
VEO_MODELS = {
    'veo-3.1-generate-preview',
    'veo-3.1-fast-generate-preview',
}

# All models that use generate_content API
GENERATE_CONTENT_MODELS = GEMINI_IMAGE_MODELS | VEO_MODELS

# Default model for image generation
DEFAULT_GENERATE_MODEL = 'imagen-3.0-generate-002'

# Import Google GenAI SDK
try:
    from google.genai import types as genai_types
    from google import genai as google_genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")


class VertexAIImageGenerator(BaseImageGenerator):
    """
    Image generator using Vertex AI.
    
    Features:
    - Service account authentication
    - Supports both Imagen and Gemini image models
    - Requires Google Cloud project and credentials
    """
    
    def __init__(
        self,
        project_id: str,
        location: str,
        credentials_json: str
    ):
        """
        Initialize Vertex AI image generator.
        
        Args:
            project_id: Google Cloud project ID
            location: Vertex AI location/region (e.g., 'us-central1')
            credentials_json: Service account credentials JSON content
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("google.genai not available. Install with: pip install google-genai")
        
        self.project_id = project_id
        self.location = location
        self.credentials_json = credentials_json
        self._client = None
        self._initialized = False
        
        # Validate credentials JSON
        import json
        try:
            self.credentials_info = json.loads(credentials_json)
            if 'type' not in self.credentials_info or self.credentials_info['type'] != 'service_account':
                raise ValueError("Invalid service account JSON: missing 'type' field or not a service account")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        
        logger.info(f"[VertexAIImageGenerator] Initialized with project={project_id}, location={location}")
    
    def _ensure_initialized(self):
        """Ensure client is initialized (lazy loading)."""
        if self._initialized:
            return
        
        try:
            from google.oauth2 import service_account
            
            # Create credentials from JSON info
            credentials = service_account.Credentials.from_service_account_info(
                self.credentials_info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Initialize client with credentials
            self._client = google_genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=credentials
            )
            self._initialized = True
            logger.info("[VertexAIImageGenerator] Client initialized successfully")
        except Exception as e:
            logger.error(f"[VertexAIImageGenerator] Failed to initialize client: {e}")
            raise ConfigurationError(f"Failed to initialize Vertex AI client: {e}")
    
    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate images using Vertex AI.
        
        Args:
            prompt: Text description of the image
            model: Model to use (can be full path or short name)
            **kwargs: Additional parameters
        
        Returns:
            List of generated images
        """
        self._ensure_initialized()
        self.validate_parameters(**kwargs)
        
        # Extract short model name from full path if needed
        # e.g., "publishers/google/models/gemini-3-pro-image-preview" -> "gemini-3-pro-image-preview"
        short_model_name = model.split('/')[-1] if '/' in model else model
        
        logger.info(f"[VertexAIImageGenerator] Generating image: model={short_model_name}, prompt={prompt[:50]}...")
        
        # Check if this is a model that uses generate_content API
        uses_generate_content = short_model_name in GENERATE_CONTENT_MODELS
        
        if uses_generate_content:
            # Use generate_content for Gemini/Veo models
            return await self._generate_with_gemini(short_model_name, prompt, **kwargs)
        else:
            # Use generate_images for Imagen models
            return await self._generate_with_imagen(short_model_name, prompt, **kwargs)
    
    async def _generate_with_imagen(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Generate images using Imagen models (generate_images API)."""
        # Build configuration
        config = self._build_config(**kwargs)
        
        # Apply style to prompt if specified
        image_style = kwargs.get('image_style')
        effective_prompt = prompt
        if image_style and image_style.lower() != "none":
            effective_prompt = f"{prompt}, style: {image_style}"
            logger.info(f"[VertexAIImageGenerator] Applied style: {image_style}")
        
        try:
            # Call Vertex AI generate_images API
            response = self._client.models.generate_images(
                model=model,
                prompt=effective_prompt,
                config=config
            )
            
            if not response.generated_images:
                raise APIError("No images generated", api_type="vertex_ai")
            
            # Process results
            return self._process_response(response, **kwargs)
            
        except Exception as e:
            logger.error(f"[VertexAIImageGenerator] Imagen generation failed: {e}")
            raise APIError(
                f"Image generation failed: {e}",
                api_type="vertex_ai",
                original_error=e
            )
    
    async def _generate_with_gemini(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Generate images using Gemini image models (generate_content API)."""
        try:
            # Build Gemini configuration
            aspect_ratio = kwargs.get('aspect_ratio', '1:1')
            image_size = kwargs.get('image_size', '1K')
            # Default to PNG format for best quality (no compression)
            output_mime_type = kwargs.get('output_mime_type', 'image/png')
            number_of_images = min(max(kwargs.get('number_of_images', 1), 1), 8)
            
            # Apply style to prompt if specified
            image_style = kwargs.get('image_style')
            effective_prompt = prompt
            if image_style and image_style.lower() != "none":
                effective_prompt = f"{prompt}, style: {image_style}"
                logger.info(f"[VertexAIImageGenerator] Applied style: {image_style}")
            
            # Create content parts
            text_part = genai_types.Part.from_text(text=effective_prompt)
            contents = [genai_types.Content(role="user", parts=[text_part])]
            
            # Build generation config
            generate_content_config = genai_types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                max_output_tokens=32768,
                response_modalities=["TEXT", "IMAGE"],
                safety_settings=[
                    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
                ],
                image_config=genai_types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                    output_mime_type=output_mime_type,
                )
            )
            
            logger.info(f"[VertexAIImageGenerator] Gemini config: aspect_ratio={aspect_ratio}, size={image_size}")
            
            # Generate images (may need multiple calls for multiple images)
            results = []
            for i in range(number_of_images):
                response = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_content_config
                )
                
                # Extract image from response
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    image_bytes = part.inline_data.data
                                    b64_data = encode_image_to_base64(image_bytes)
                                    
                                    result = {
                                        "url": f"data:{output_mime_type};base64,{b64_data}",
                                        "mimeType": output_mime_type,
                                        "index": len(results),
                                        "size": len(image_bytes)
                                    }
                                    results.append(result)
                                    logger.info(f"[VertexAIImageGenerator] Generated Gemini image {len(results)}")
            
            if not results:
                raise APIError("No images generated from Gemini model", api_type="vertex_ai")
            
            logger.info(f"[VertexAIImageGenerator] Generated {len(results)} Gemini images")
            return results
            
        except Exception as e:
            logger.error(f"[VertexAIImageGenerator] Gemini generation failed: {e}")
            raise APIError(
                f"Gemini image generation failed: {e}",
                api_type="vertex_ai",
                original_error=e
            )
    
    def _build_config(self, **kwargs) -> 'genai_types.GenerateImagesConfig':
        """Build Vertex AI configuration from parameters."""
        number_of_images = kwargs.get('number_of_images', 1)
        number_of_images = min(max(number_of_images, 1), 4)
        
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        include_rai_reason = kwargs.get('include_rai_reason', True)
        # Default to PNG format for best quality (no compression)
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
        
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
        
        # Add compression quality for JPEG (default 100 = no compression)
        if output_mime_type == 'image/jpeg':
            compression_quality = kwargs.get('output_compression_quality', 100)
            config_kwargs["output_compression_quality"] = compression_quality
        
        logger.info(f"[VertexAIImageGenerator] Config: {config_kwargs}")
        
        return genai_types.GenerateImagesConfig(**config_kwargs)
    
    def _process_response(
        self,
        response,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Process Vertex AI response and extract images."""
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
        results = []
        
        for idx, generated_image in enumerate(response.generated_images):
            # Check for RAI filtering
            if hasattr(generated_image, 'rai_filtered_reason') and generated_image.rai_filtered_reason:
                logger.warning(f"[VertexAIImageGenerator] Image {idx} filtered: {generated_image.rai_filtered_reason}")
                continue
            
            if not generated_image.image:
                continue
            
            if not hasattr(generated_image.image, 'image_bytes') or generated_image.image.image_bytes is None:
                logger.warning(f"[VertexAIImageGenerator] Image {idx} has no image_bytes")
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
                raise APIError("No valid images generated", api_type="vertex_ai")
        
        logger.info(f"[VertexAIImageGenerator] Generated {len(results)} images")
        return results
    
    def validate_parameters(self, **kwargs) -> None:
        """
        Validate Vertex AI specific parameters.
        
        Raises:
            ParameterValidationError: If parameters are invalid
        """
        # Validate aspect ratio
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        validate_aspect_ratio(aspect_ratio)
        
        # Validate image size
        image_size = kwargs.get('image_size')
        validate_image_size(image_size)
        
        # Validate number of images
        number_of_images = kwargs.get('number_of_images', 1)
        if not isinstance(number_of_images, int) or number_of_images < 1 or number_of_images > 4:
            raise ParameterValidationError(
                f"Invalid number_of_images: {number_of_images}. Must be 1-4"
            )
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get Vertex AI capabilities."""
        return {
            'api_type': 'vertex_ai',
            'max_images': 4,
            'aspect_ratios': VALID_ASPECT_RATIOS,
            'image_sizes': VALID_IMAGE_SIZES
        }
    
    def get_supported_models(self) -> List[str]:
        """
        Get supported models from Vertex AI.
        
        Returns list of model short names (without 'publishers/google/models/' prefix).
        """
        try:
            self._ensure_initialized()
            
            # List all models from Vertex AI
            models_list = self._client.models.list()
            
            # Extract model names and filter for image-related models
            supported_models = []
            for model in models_list:
                model_name = model.name if hasattr(model, 'name') else str(model)
                
                # Extract short name from full path
                short_name = model_name.split('/')[-1] if '/' in model_name else model_name
                
                # Filter for image generation models
                if any(keyword in short_name.lower() for keyword in ['imagen', 'image', 'veo']):
                    supported_models.append(short_name)
            
            logger.info(f"[VertexAIImageGenerator] Found {len(supported_models)} image models")
            return supported_models
            
        except Exception as e:
            logger.warning(f"[VertexAIImageGenerator] Failed to list models dynamically: {e}")
            # Fallback to static list
            return [
                'imagen-4.0-generate-001',
                'imagen-3.0-generate-002',
                'gemini-3-pro-image-preview',
                'gemini-2.5-flash-image-preview',
                'veo-3.1-generate-preview',
                'veo-3.1-fast-generate-preview'
            ]
