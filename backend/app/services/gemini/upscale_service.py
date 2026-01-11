"""
Image Upscale Service

Handles image upscaling using Imagen models.
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


class UpscaleService:
    """
    Handles image upscaling functionality.
    
    Supports upscaling images by 2x or 4x using Imagen models.
    """
    
    def __init__(self, sdk_initializer: SDKInitializer):
        """
        Initialize upscale service.
        
        Args:
            sdk_initializer: SDK initializer instance
        """
        self.sdk_initializer = sdk_initializer
        self.validator = ImageServiceValidator("Upscale Service")

        # 支持的 Imagen 模型（根据 Google API 实际可用模型更新）
        self.upscale_models = {
            # Imagen 4.0 系列（推荐使用）
            'imagen-4.0-generate-001',  # ✅ Imagen 4.0 标准版
            'imagen-4.0-ultra-generate-001',  # Imagen 4.0 Ultra 高质量版
            'imagen-4.0-fast-generate-001',  # Imagen 4.0 Fast 快速版
            # Imagen 3.0 系列（已弃用，保留以兼容旧代码）
            'imagen-3.0-generate-001',  # ⚠️ 已不可用
            'imagen-3.0-generate-002',  # ⚠️ 已不可用
        }
        
        # 支持的放大倍数
        self.valid_upscale_factors = ['x2', 'x4']
    
    async def upscale_image(
        self,
        image_path: str,
        upscale_factor: str,  # 移除硬编码默认值，由前端传递
        model: str,  # 移除硬编码默认值，由前端传递
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Upscale image resolution by 2x or 4x.
        
        Args:
            image_path: Path to the image to upscale
            upscale_factor: Upscale factor ('x2' or 'x4') - must be provided by caller
            model: Model to use for upscaling - must be provided by caller
            **kwargs: Additional parameters including:
                - include_rai_reason: Include RAI reason in response
                - enhance_input_image: Enhance input image before upscaling
                - image_preservation_factor: How much to preserve original image (0.0-1.0)
                - output_mime_type: Output format ('image/png', 'image/jpeg')
                - output_compression_quality: JPEG compression quality (1-100)
                - person_generation: Person generation setting
        
        Returns:
            List of upscaled images
        """
        if not GENAI_TYPES_AVAILABLE:
            raise RuntimeError("google.genai.types not available")
        
        try:
            self.sdk_initializer.ensure_initialized()
            
            # 参数验证
            self._validate_upscale_parameters(image_path, upscale_factor, model, **kwargs)
            
            logger.info(f"[Upscale Service] Image upscaling: factor={upscale_factor}, model={model}")
            logger.info(f"[Upscale Service] Parameters validated successfully")
            
            # 添加详细的参数日志
            logger.info(
                f"[Upscale Service] Received kwargs: "
                f"image_preservation_factor={kwargs.get('image_preservation_factor')}, "
                f"enhance_input_image={kwargs.get('enhance_input_image')}, "
                f"output_mime_type={kwargs.get('output_mime_type')}, "
                f"output_compression_quality={kwargs.get('output_compression_quality')}, "
                f"person_generation={kwargs.get('person_generation')}"
            )
            
            # Validate upscale factor
            if upscale_factor not in self.valid_upscale_factors:
                raise ValueError(f"Invalid upscale factor: {upscale_factor}. Must be one of {self.valid_upscale_factors}")
            
            # Check if model supports upscaling
            if model not in self.upscale_models:
                logger.warning(f"[Upscale Service] Model {model} may not support upscaling, trying anyway")
            
            # Build upscale configuration
            config = genai_types.UpscaleImageConfig(
                include_rai_reason=kwargs.get('include_rai_reason', True),
                enhance_input_image=kwargs.get('enhance_input_image', True),
                image_preservation_factor=kwargs.get('image_preservation_factor', 0.5),
                output_mime_type=kwargs.get('output_mime_type', 'image/png'),
                output_compression_quality=kwargs.get('output_compression_quality', 95),
                person_generation=kwargs.get('person_generation', 'ALLOW_ADULT')
            )
            
            # Load image using correct API
            image = genai_types.Image.from_file(location=image_path)
            
            response = self.sdk_initializer.client.models.upscale_image(
                model=model,
                image=image,
                upscale_factor=upscale_factor,
                config=config
            )
            
            # Process results
            results = []
            if response.generated_images:
                for idx, generated_image in enumerate(response.generated_images):
                    # Check for RAI filtering first
                    if hasattr(generated_image, 'rai_filtered_reason') and generated_image.rai_filtered_reason:
                        logger.warning(f"[Upscale Service] Image {idx} was filtered by RAI: {generated_image.rai_filtered_reason}")
                        continue
                    
                    if not generated_image.image:
                        continue
                    
                    # Check if image_bytes is actually present
                    if not hasattr(generated_image.image, 'image_bytes') or generated_image.image.image_bytes is None:
                        logger.warning(f"[Upscale Service] Image {idx} has no image_bytes, skipping")
                        continue
                    
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    try:
                        generated_image.image.save(tmp_path)
                        with open(tmp_path, 'rb') as f:
                            image_bytes = f.read()
                        b64_data = base64.b64encode(image_bytes).decode('utf-8')
                        
                        result = {
                            "url": f"data:image/png;base64,{b64_data}",
                            "mimeType": "image/png",
                            "index": idx,
                            "upscale_factor": upscale_factor,
                            "size": len(image_bytes)
                        }
                        
                        # Add safety attributes if available
                        if hasattr(generated_image, 'safety_attributes') and generated_image.safety_attributes:
                            safety_attrs = {}
                            # content_type (内部使用)
                            if hasattr(generated_image.safety_attributes, 'content_type'):
                                safety_attrs["content_type"] = generated_image.safety_attributes.content_type
                            # categories (RAI 类别列表)
                            if hasattr(generated_image.safety_attributes, 'categories'):
                                safety_attrs["categories"] = generated_image.safety_attributes.categories
                            # scores (每个类别的分数列表)
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
            
            return results
            
        except Exception as e:
            logger.error(f"[Upscale Service] Image upscaling error: {e}", exc_info=True)
            raise
    
    def _validate_upscale_parameters(
        self,
        image_path: str,
        upscale_factor: str,
        model: str,
        **kwargs
    ) -> None:
        """
        Validate parameters for image upscaling using standardized validation.
        
        Args:
            image_path: Path to the image to upscale
            upscale_factor: Upscale factor ('x2' or 'x4')
            model: Model to use for upscaling
            **kwargs: Additional parameters
        
        Raises:
            ParameterValidationError: If any parameter is invalid
        """
        # Validate required parameters with enhanced error messages
        self.validator.validate_required_string('image_path', image_path)
        self.validator.validate_upscale_factor(upscale_factor)
        self.validator.validate_model(model, list(self.upscale_models))
        
        # Validate optional parameters
        self._validate_upscale_optional_parameters(**kwargs)
        
        logger.info(f"[Upscale Service] Parameter validation passed for upscale_factor: {upscale_factor}, model: {model}")
    
    def _validate_upscale_optional_parameters(self, **kwargs) -> None:
        """Validate optional parameters for upscaling using standardized validation."""
        # Validate image_preservation_factor
        preservation_factor = kwargs.get('image_preservation_factor')
        if preservation_factor is not None:
            self.validator.validate_numeric_range(
                'image_preservation_factor',
                preservation_factor,
                min_value=0.0,
                max_value=1.0,
                value_type=float
            )
        
        # Validate output_compression_quality
        quality = kwargs.get('output_compression_quality')
        if quality is not None:
            self.validator.validate_compression_quality(quality)
        
        # Validate output_mime_type
        mime_type = kwargs.get('output_mime_type')
        if mime_type is not None:
            self.validator.validate_mime_type(mime_type)
        
        # Note: person_generation validation removed - parameter no longer used
        # The API will use its default value (allow_adult)
        
        # Validate boolean parameters
        for param_name in ['include_rai_reason', 'enhance_input_image']:
            param_value = kwargs.get(param_name)
            if param_value is not None:
                self.validator.validate_boolean(param_name, param_value)
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported models for image upscaling."""
        return list(self.upscale_models)
    
    def get_upscale_capabilities(self) -> Dict[str, Any]:
        """Get upscaling capabilities and limitations."""
        return {
            "upscale_factors": self.valid_upscale_factors,
            "max_input_resolution": "2K",
            "max_output_resolution": "8K",
            "supported_formats": ["image/png", "image/jpeg"],
            "enhancement_options": {
                "enhance_input_image": "Enhance input before upscaling",
                "image_preservation_factor": "Control how much to preserve original (0.0-1.0)"
            },
            "quality_options": {
                "output_compression_quality": "JPEG quality (1-100)"
            }
        }