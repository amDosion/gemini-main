"""
Vertex AI implementation for image editing.

This module provides image editing using Vertex AI with service account authentication.
Supports 6 reference image types and 4 edit modes.
"""

import logging
import base64
import os
import tempfile
from typing import Dict, Any, List, Optional

from .image_edit_base import BaseImageEditor
from .image_edit_common import (
    decode_base64_image,
    validate_edit_mode,
    validate_reference_images,
    validate_number_of_images,
    validate_aspect_ratio,
    validate_guidance_scale,
    validate_output_mime_type,
    validate_safety_filter_level,
    validate_person_generation,
    encode_image_to_base64,
    NotSupportedError,
    VALID_EDIT_MODES,
    VALID_REFERENCE_IMAGE_TYPES,
    VALID_ASPECT_RATIOS
)

logger = logging.getLogger(__name__)

# Model mapping: User-facing model IDs → Vertex AI model IDs
# Vertex AI only supports specific model IDs for image editing
# Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/image/edit-images
MODEL_MAPPING = {
    # Nano-Banana series → imagen-3.0-capability-001
    'nano-banana-pro-preview': 'imagen-3.0-capability-001',
    'nano-banana-pro': 'imagen-3.0-capability-001',
    'nano-banana-preview': 'imagen-3.0-capability-001',
    'nano-banana': 'imagen-3.0-capability-001',
    
    # Gemini image models → imagen-3.0-capability-001
    'gemini-3-pro-image-preview': 'imagen-3.0-capability-001',
    'gemini-3.0-pro-image-preview': 'imagen-3.0-capability-001',
    'gemini-3-pro-image': 'imagen-3.0-capability-001',
    'gemini-3.0-pro-image': 'imagen-3.0-capability-001',
    'gemini-2.5-flash-image': 'imagen-3.0-capability-001',
    'gemini-2.5-flash-image-preview': 'imagen-3.0-capability-001',
    'gemini-2.5-pro-image': 'imagen-3.0-capability-001',
    'gemini-2.5-pro-image-preview': 'imagen-3.0-capability-001',
    
    # Imagen models (pass through)
    'imagen-3.0-capability-001': 'imagen-3.0-capability-001',
    'imagen-3.0-generate-001': 'imagen-3.0-capability-001',
}

# Default model for image editing
DEFAULT_EDIT_MODEL = 'imagen-3.0-capability-001'

# Import Google GenAI SDK
try:
    from google.genai import types as genai_types
    from google import genai as google_genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")


class VertexAIImageEditor(BaseImageEditor):
    """
    Image editor using Vertex AI.
    
    Features:
    - Service account authentication
    - Supports all 6 reference image types
    - Supports 4 edit modes
    - Requires Google Cloud project and credentials
    """

    
    def __init__(
        self,
        project_id: str,
        location: str,
        credentials_json: str
    ):
        """
        Initialize Vertex AI image editor.
        
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
        
        logger.info(f"[VertexAIImageEditor] Initialized with project={project_id}, location={location}")
    
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
            logger.info("[VertexAIImageEditor] Client initialized successfully")
        except Exception as e:
            logger.error(f"[VertexAIImageEditor] Failed to initialize client: {e}")
            raise RuntimeError(f"Failed to initialize Vertex AI client: {e}")

    
    def edit_image(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Edit images using Vertex AI.
        
        Args:
            prompt: Text description of the desired edit
            reference_images: Dictionary mapping reference image types to Base64 strings
            config: Optional configuration dictionary
        
        Returns:
            List of Base64-encoded edited image strings
        """
        self._ensure_initialized()
        self.validate_parameters(prompt, reference_images, config)
        
        logger.info(f"[VertexAIImageEditor] Editing image: prompt={prompt[:50]}...")
        
        # Build configuration
        edit_config = self._build_config(config or {})
        
        # Build reference images
        ref_images = self._build_reference_images(reference_images)
        
        # Get model from config
        user_model = (config or {}).get('model', DEFAULT_EDIT_MODEL)
        
        # Map user-facing model ID to Vertex AI model ID
        vertex_model = MODEL_MAPPING.get(user_model, DEFAULT_EDIT_MODEL)
        
        if user_model != vertex_model:
            logger.info(
                f"[VertexAIImageEditor] Model mapping: {user_model} → {vertex_model}"
            )
        
        try:
            # Call Vertex AI edit_image API (correct SDK method for image editing)
            # Reference: https://googleapis.github.io/python-genai/ - edit_image method
            response = self._client.models.edit_image(
                model=vertex_model,
                prompt=prompt,
                reference_images=ref_images,
                config=edit_config
            )
            
            if not response.generated_images:
                raise RuntimeError("No images generated")
            
            # Process results
            return self._process_response(response, config or {})
            
        except Exception as e:
            logger.error(f"[VertexAIImageEditor] Editing failed: {e}")
            raise RuntimeError(f"Image editing failed: {e}")

    
    def _build_config(self, config: Dict[str, Any]) -> 'genai_types.EditImageConfig':
        """Build Vertex AI EditImageConfig from parameters."""
        config_kwargs = {}
        
        # Edit mode (required for some operations)
        edit_mode = config.get('edit_mode')
        if edit_mode:
            # Map string to enum
            mode_map = {
                'inpainting-insert': genai_types.EditMode.EDIT_MODE_INPAINT_INSERTION,
                'inpainting-remove': genai_types.EditMode.EDIT_MODE_INPAINT_REMOVAL,
                'outpainting': genai_types.EditMode.EDIT_MODE_OUTPAINT,
                'product-image': genai_types.EditMode.EDIT_MODE_PRODUCT_IMAGE
            }
            if edit_mode in mode_map:
                config_kwargs['edit_mode'] = mode_map[edit_mode]
        
        # Number of images
        number_of_images = config.get('number_of_images', 1)
        config_kwargs['number_of_images'] = min(max(number_of_images, 1), 4)
        
        # Aspect ratio
        aspect_ratio = config.get('aspect_ratio')
        if aspect_ratio:
            config_kwargs['aspect_ratio'] = aspect_ratio
        
        # Guidance scale
        guidance_scale = config.get('guidance_scale')
        if guidance_scale is not None:
            config_kwargs['guidance_scale'] = float(guidance_scale)
        
        # Output MIME type
        output_mime_type = config.get('output_mime_type', 'image/jpeg')
        config_kwargs['output_mime_type'] = output_mime_type
        
        # Safety filter level
        safety_filter_level = config.get('safety_filter_level')
        if safety_filter_level:
            level_map = {
                'block_most': genai_types.SafetyFilterLevel.BLOCK_MOST,
                'block_some': genai_types.SafetyFilterLevel.BLOCK_MEDIUM_AND_ABOVE,
                'block_few': genai_types.SafetyFilterLevel.BLOCK_ONLY_HIGH,
                'block_fewest': genai_types.SafetyFilterLevel.BLOCK_NONE
            }
            if safety_filter_level in level_map:
                config_kwargs['safety_filter_level'] = level_map[safety_filter_level]
        
        # Person generation
        person_generation = config.get('person_generation')
        if person_generation:
            person_map = {
                'dont_allow': genai_types.PersonGeneration.DONT_ALLOW,
                'allow_adult': genai_types.PersonGeneration.ALLOW_ADULT,
                'allow_all': genai_types.PersonGeneration.ALLOW_ALL
            }
            if person_generation in person_map:
                config_kwargs['person_generation'] = person_map[person_generation]
        
        # Include RAI reason
        config_kwargs['include_rai_reason'] = config.get('include_rai_reason', True)
        
        logger.info(f"[VertexAIImageEditor] Config: {config_kwargs}")
        
        return genai_types.EditImageConfig(**config_kwargs)

    
    def _build_reference_images(self, reference_images: Dict[str, str]) -> List:
        """
        Build reference image objects for Vertex AI.
        
        Supports 6 reference image types:
        - raw: Base image to edit
        - mask: Mask for inpainting
        - control: Control image for guided generation
        - style: Style reference
        - subject: Subject reference
        - content: Content reference
        """
        ref_images = []
        reference_id = 1
        
        # Process each reference image type
        for ref_type, base64_data in reference_images.items():
            # Decode Base64 to bytes
            image_bytes = decode_base64_image(base64_data)
            
            # Save to temp file (required by SDK)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            
            try:
                # Create Image object from file
                image = genai_types.Image.from_file(location=tmp_path)
                
                # Create appropriate reference image type
                if ref_type == 'raw':
                    ref_image = genai_types.RawReferenceImage(
                        reference_id=reference_id,
                        reference_image=image
                    )
                elif ref_type == 'mask':
                    ref_image = genai_types.MaskReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.MaskReferenceConfig(
                            mask_mode='MASK_MODE_USER_PROVIDED',
                            mask_dilation=0.06
                        )
                    )
                elif ref_type == 'control':
                    ref_image = genai_types.ControlReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.ControlReferenceConfig(
                            control_type='CONTROL_TYPE_SCRIBBLE',
                            enable_control_image_computation=False
                        )
                    )
                elif ref_type == 'style':
                    ref_image = genai_types.StyleReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.StyleReferenceConfig(
                            style_description='style reference'
                        )
                    )
                elif ref_type == 'subject':
                    ref_image = genai_types.SubjectReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.SubjectReferenceConfig(
                            subject_type='SUBJECT_TYPE_PRODUCT',
                            subject_description='subject reference'
                        )
                    )
                elif ref_type == 'content':
                    ref_image = genai_types.ContentReferenceImage(
                        reference_id=reference_id,
                        reference_image=image
                    )
                else:
                    logger.warning(f"[VertexAIImageEditor] Unknown reference type: {ref_type}")
                    continue
                
                ref_images.append(ref_image)
                reference_id += 1
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        logger.info(f"[VertexAIImageEditor] Built {len(ref_images)} reference images")
        return ref_images

    
    def _process_response(self, response, config: Dict[str, Any]) -> List[str]:
        """Process Vertex AI response and extract edited images."""
        output_mime_type = config.get('output_mime_type', 'image/jpeg')
        results = []
        
        for idx, generated_image in enumerate(response.generated_images):
            # Check for RAI filtering
            if hasattr(generated_image, 'rai_filtered_reason') and generated_image.rai_filtered_reason:
                logger.warning(f"[VertexAIImageEditor] Image {idx} filtered: {generated_image.rai_filtered_reason}")
                continue
            
            if not generated_image.image:
                continue
            
            if not hasattr(generated_image.image, 'image_bytes') or generated_image.image.image_bytes is None:
                logger.warning(f"[VertexAIImageEditor] Image {idx} has no image_bytes")
                continue
            
            # Save to temp file and read back
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                generated_image.image.save(tmp_path)
                with open(tmp_path, 'rb') as f:
                    image_bytes = f.read()
                b64_data = encode_image_to_base64(image_bytes)
                
                results.append(b64_data)
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
                raise RuntimeError(f"All images filtered by content policy: {first_reason}")
            else:
                raise RuntimeError("No valid images generated")
        
        logger.info(f"[VertexAIImageEditor] Generated {len(results)} edited images")
        return results

    
    def validate_parameters(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validate Vertex AI specific parameters.
        
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate prompt
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt must be a non-empty string")
        
        # Validate reference images
        validate_reference_images(reference_images)
        
        if config:
            # Validate edit mode
            edit_mode = config.get('edit_mode')
            validate_edit_mode(edit_mode)
            
            # Validate number of images
            number_of_images = config.get('number_of_images')
            validate_number_of_images(number_of_images)
            
            # Validate aspect ratio
            aspect_ratio = config.get('aspect_ratio')
            validate_aspect_ratio(aspect_ratio)
            
            # Validate guidance scale
            guidance_scale = config.get('guidance_scale')
            validate_guidance_scale(guidance_scale)
            
            # Validate output MIME type
            output_mime_type = config.get('output_mime_type')
            validate_output_mime_type(output_mime_type)
            
            # Validate safety filter level
            safety_filter_level = config.get('safety_filter_level')
            validate_safety_filter_level(safety_filter_level)
            
            # Validate person generation
            person_generation = config.get('person_generation')
            validate_person_generation(person_generation)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get Vertex AI image editing capabilities."""
        return {
            'api_type': 'vertex_ai',
            'supports_editing': True,
            'supported_edit_modes': VALID_EDIT_MODES,
            'supported_reference_types': VALID_REFERENCE_IMAGE_TYPES,
            'max_images': 4,
            'aspect_ratios': VALID_ASPECT_RATIOS,
            'guidance_scale_range': (0, 100)
        }
    
    def get_supported_models(self) -> List[str]:
        """Get supported Imagen models for editing."""
        return [
            'imagen-3.0-capability-001',
            'imagen-4.0-ingredients-preview'
        ]
