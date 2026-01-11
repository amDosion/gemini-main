"""
Image Segmentation Service

Handles image segmentation using Imagen models.
Based on official Google GenAI SDK.
"""

import logging
import base64
import os
import tempfile
from typing import Dict, Any, List, Optional

from .sdk_initializer import SDKInitializer
from .parameter_validation import ImageServiceValidator

logger = logging.getLogger(__name__)

# 使用新版 google-genai SDK
try:
    from google.genai import types as genai_types
    GENAI_TYPES_AVAILABLE = True
except ImportError:
    GENAI_TYPES_AVAILABLE = False


class SegmentationService:
    """
    Handles image segmentation functionality.
    
    Supports segmenting objects in images and creating masks.
    """
    
    def __init__(self, sdk_initializer: SDKInitializer):
        """
        Initialize segmentation service.
        
        Args:
            sdk_initializer: SDK initializer instance
        """
        self.sdk_initializer = sdk_initializer
        self.validator = ImageServiceValidator("Segmentation Service")
        
        # 支持的分割模型
        self.segmentation_models = {
            'image-segmentation-001'
        }
        
        # 支持的掩码模式
        self.valid_mask_modes = [
            'MASK_MODE_FOREGROUND',
            'MASK_MODE_BACKGROUND'
        ]
    
    async def segment_image(
        self,
        image_path: str,
        model: str,  # 移除硬编码默认值，由前端传递
        prompt: Optional[str] = None,
        mask_mode: str = "MASK_MODE_FOREGROUND",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Segment objects in an image and create masks.
        
        Args:
            image_path: Path to the image to segment
            prompt: Optional text prompt for guided segmentation
            mask_mode: Segmentation mode ('MASK_MODE_FOREGROUND', 'MASK_MODE_BACKGROUND')
            model: Model to use for segmentation - must be provided by caller
            **kwargs: Additional parameters including:
                - scribble_image_path: Path to scribble image for guided segmentation
        
        Returns:
            List of generated masks
        """
        if not GENAI_TYPES_AVAILABLE:
            raise RuntimeError("google.genai.types not available")
        
        try:
            self.sdk_initializer.ensure_initialized()
            
            # 参数验证
            self._validate_segmentation_parameters(image_path, model, prompt, mask_mode, **kwargs)
            
            logger.info(f"[Segmentation Service] Image segmentation: model={model}, mode={mask_mode}")
            logger.info(f"[Segmentation Service] Parameters validated successfully")
            
            # 添加详细的参数日志
            prompt_log = f"prompt='{prompt[:30]}...'" if prompt and len(prompt) > 30 else f"prompt='{prompt}'"
            scribble_path = kwargs.get('scribble_image_path')
            logger.info(
                f"[Segmentation Service] Received parameters: "
                f"{prompt_log}, "
                f"scribble_image_path={scribble_path}"
            )
            
            # Validate mask mode
            if mask_mode not in self.valid_mask_modes:
                raise ValueError(f"Invalid mask mode: {mask_mode}. Must be one of {self.valid_mask_modes}")
            
            # Check if model supports segmentation
            if model not in self.segmentation_models:
                logger.warning(f"[Segmentation Service] Model {model} may not support segmentation, trying anyway")
            
            # Build source configuration
            source_kwargs = {
                "image": genai_types.Image.from_file(location=image_path)
            }
            
            if prompt:
                source_kwargs["prompt"] = prompt
            
            # Handle scribble image if provided
            scribble_path = kwargs.get('scribble_image_path')
            if scribble_path:
                source_kwargs["scribble_image"] = genai_types.ScribbleImage.from_file(scribble_path)
            
            source = genai_types.SegmentImageSource(**source_kwargs)
            
            config = genai_types.SegmentImageConfig(
                mask_mode=mask_mode
            )
            
            response = self.sdk_initializer.client.models.segment_image(
                model=model,
                source=source,
                config=config
            )
            
            # Process results
            results = []
            if response.generated_masks:
                for idx, generated_mask in enumerate(response.generated_masks):
                    if generated_mask.mask:
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                            tmp_path = tmp.name
                        
                        try:
                            generated_mask.mask.save(tmp_path)
                            with open(tmp_path, 'rb') as f:
                                mask_bytes = f.read()
                            b64_data = base64.b64encode(mask_bytes).decode('utf-8')
                            
                            result = {
                                "url": f"data:image/png;base64,{b64_data}",
                                "mimeType": "image/png",
                                "index": idx,
                                "mask_mode": mask_mode,
                                "size": len(mask_bytes)
                            }
                            
                            # Add prompt if used
                            if prompt:
                                result["prompt"] = prompt
                            
                            results.append(result)
                        finally:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
            
            return results
            
        except Exception as e:
            logger.error(f"[Segmentation Service] Image segmentation error: {e}", exc_info=True)
            raise
    
    def _validate_segmentation_parameters(
        self,
        image_path: str,
        model: str,
        prompt: Optional[str],
        mask_mode: str,
        **kwargs
    ) -> None:
        """
        Validate parameters for image segmentation using standardized validation.
        
        Args:
            image_path: Path to the image to segment
            model: Model to use for segmentation
            prompt: Optional text prompt for guided segmentation
            mask_mode: Segmentation mode
            **kwargs: Additional parameters
        
        Raises:
            ParameterValidationError: If any parameter is invalid
        """
        # Validate required parameters with enhanced error messages
        self.validator.validate_required_string('image_path', image_path)
        self.validator.validate_model(model, list(self.segmentation_models))
        self.validator.validate_choice('mask_mode', mask_mode, self.valid_mask_modes)
        
        # Validate optional prompt
        if prompt is not None:
            self.validator.validate_required_string('prompt', prompt, max_length=1000)
        
        # Validate scribble image path if provided
        scribble_path = kwargs.get('scribble_image_path')
        if scribble_path is not None:
            self.validator.validate_required_string('scribble_image_path', scribble_path)
        
        logger.info(f"[Segmentation Service] Parameter validation passed for model: {model}, mask_mode: {mask_mode}")
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported models for image segmentation."""
        return list(self.segmentation_models)
    
    def get_segmentation_capabilities(self) -> Dict[str, Any]:
        """Get segmentation capabilities and limitations."""
        return {
            "mask_modes": self.valid_mask_modes,
            "supports_text_prompt": True,
            "supports_scribble_guidance": True,
            "output_formats": ["image/png"],
            "max_input_resolution": "4K",
            "guidance_options": {
                "text_prompt": "Describe what to segment",
                "scribble_image": "Provide scribble guidance image"
            }
        }