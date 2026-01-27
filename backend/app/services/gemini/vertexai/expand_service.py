"""
Image Expand Service

Handles image expansion (outpainting) using Imagen models.
Based on official Google GenAI SDK.
"""

import logging
import base64
import os
import tempfile
from typing import Dict, Any, List, Optional

from ..common.sdk_initializer import SDKInitializer
from ..common.parameter_validation import ImageServiceValidator

logger = logging.getLogger(__name__)

# 使用新版 google-genai SDK
try:
    from google.genai import types as genai_types
    GENAI_TYPES_AVAILABLE = True
except ImportError:
    GENAI_TYPES_AVAILABLE = False


class ExpandService:
    """
    Handles image expansion (outpainting) functionality.
    
    Supports various expansion modes:
    - Scale mode: Expand by scale factors
    - Offset mode: Expand by pixel offsets
    - Ratio mode: Expand to specific aspect ratios
    """
    
    def __init__(self, sdk_initializer: SDKInitializer):
        """
        Initialize expand service.
        
        Args:
            sdk_initializer: SDK initializer instance
        """
        self.sdk_initializer = sdk_initializer
        self.validator = ImageServiceValidator("Expand Service")

        # 支持的 Imagen 模型（根据 Google API 实际可用模型更新）
        self.expand_models = {
            # Imagen 4.0 系列（推荐使用）
            'imagen-4.0-generate-001',  # ✅ Imagen 4.0 标准版
            'imagen-4.0-ultra-generate-001',  # Imagen 4.0 Ultra 高质量版
            'imagen-4.0-fast-generate-001',  # Imagen 4.0 Fast 快速版
            # Imagen 3.0 系列（已弃用，保留以兼容旧代码）
            'imagen-3.0-generate-001',  # ⚠️ 已不可用
            'imagen-3.0-generate-002',  # ⚠️ 已不可用
        }
    
    def _extract_image_path(self, reference_images: Optional[Dict[str, Any]], **kwargs) -> str:
        """
        从 reference_images 或 kwargs 中提取图片路径
        
        Args:
            reference_images: 参考图片字典 {'raw': image_path or image_url}
            **kwargs: 额外参数（可能包含 image_path）
        
        Returns:
            图片路径或 URL
        """
        image_path = None
        
        if reference_images:
            image_path = reference_images.get("raw")
        
        # 从 kwargs 中获取（兼容旧接口）
        if not image_path:
            image_path = kwargs.get("image_path")
        
        if not image_path:
            raise ValueError("expand_image requires 'raw' image in reference_images or 'image_path' in kwargs")
        
        return image_path
    
    async def expand_image(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        统一的图片扩展接口 - 处理参数提取
        
        Args:
            prompt: Description of what to add in expanded areas
            model: Model identifier (required)
            reference_images: Reference images dict {'raw': image_path or image_url}
            **kwargs: Additional parameters:
                - mode: Expansion mode ('scale', 'offset', 'ratio')
                - image_path: Path to the image (alternative to reference_images)
                - expand_prompt: Alternative prompt parameter
                - 其他扩展参数（x_scale, y_scale, left_offset, etc.）
        
        Returns:
            List of expanded images
        """
        # 获取图片路径
        image_path = self._extract_image_path(reference_images, **kwargs)
        
        expand_prompt = kwargs.get("expand_prompt", prompt)
        mode = kwargs.get("mode", "scale")
        
        logger.info(f"[Expand Service] Image expansion: model={model}, mode={mode}")
        return await self._expand_image_internal(image_path, expand_prompt, model, mode, **kwargs)
    
    async def _expand_image_internal(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,  # 移除硬编码默认值，由前端传递
        mode: str = "scale",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Expand image using outpainting.
        
        Args:
            image_path: Path to the image to expand
            expand_prompt: Description of what to add in expanded areas
            mode: Expansion mode ('scale', 'offset', 'ratio')
            model: Model to use for expansion - must be provided by caller
            **kwargs: Additional parameters including:
                - x_scale, y_scale: Scale factors (for scale mode)
                - left_offset, right_offset, top_offset, bottom_offset: Pixel offsets (for offset mode)
                - output_ratio: Target aspect ratio (for ratio mode)
                - angle: Rotation angle (for ratio mode)
                - best_quality: Use best quality settings
                - limit_image_size: Limit output image size
        
        Returns:
            List of expanded images
        """
        try:
            # 确保 SDK 已初始化
            self.sdk_initializer.ensure_initialized()
            
            # 参数验证
            self._validate_expand_parameters(image_path, expand_prompt, model, mode, **kwargs)
            
            logger.info(f"[Expand Service] Image expansion: model={model}, mode={mode}")
            logger.info(f"[Expand Service] Parameters validated successfully")
            
            # 添加详细的参数日志
            prompt_log = f"expand_prompt='{expand_prompt[:30]}...'" if len(expand_prompt) > 30 else f"expand_prompt='{expand_prompt}'"
            
            # 根据模式记录不同的参数
            if mode == "scale":
                mode_params = f"x_scale={kwargs.get('x_scale', 1.5)}, y_scale={kwargs.get('y_scale', 1.5)}"
            elif mode == "offset":
                mode_params = (f"left_offset={kwargs.get('left_offset', 0)}, "
                             f"right_offset={kwargs.get('right_offset', 0)}, "
                             f"top_offset={kwargs.get('top_offset', 0)}, "
                             f"bottom_offset={kwargs.get('bottom_offset', 0)}")
            elif mode == "ratio":
                mode_params = f"output_ratio={kwargs.get('output_ratio', '16:9')}, angle={kwargs.get('angle', 0)}"
            else:
                mode_params = "unknown_mode_parameters"
            
            logger.info(
                f"[Expand Service] Received parameters: "
                f"{prompt_log}, "
                f"{mode_params}, "
                f"number_of_images={kwargs.get('number_of_images', 1)}, "
                f"guidance_scale={kwargs.get('guidance_scale', 7.5)}"
            )
            
            if not GENAI_TYPES_AVAILABLE:
                raise RuntimeError("google.genai.types not available")
            
            # Check if model supports expansion
            if model not in self.expand_models:
                logger.warning(f"[Expand Service] Model {model} may not support expansion, trying anyway")
            
            # Build expansion configuration based on mode
            if mode == "scale":
                return await self._expand_by_scale(image_path, expand_prompt, model, **kwargs)
            elif mode == "offset":
                return await self._expand_by_offset(image_path, expand_prompt, model, **kwargs)
            elif mode == "ratio":
                return await self._expand_by_ratio(image_path, expand_prompt, model, **kwargs)
            else:
                raise ValueError(f"Unsupported expansion mode: {mode}")
        
        except Exception as e:
            logger.error(f"[Expand Service] Image expansion error: {e}", exc_info=True)
            raise
    
    async def _expand_by_scale(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Expand image by scale factors."""
        x_scale = kwargs.get('x_scale', 1.5)
        y_scale = kwargs.get('y_scale', 1.5)
        
        logger.info(f"[Expand Service] Scale expansion: x={x_scale}, y={y_scale}")
        
        # Build edit configuration for outpainting
        config = genai_types.EditImageConfig(
            edit_mode="EDIT_MODE_OUTPAINT",
            number_of_images=kwargs.get('number_of_images', 1),
            guidance_scale=kwargs.get('guidance_scale', 7.5),
            person_generation=kwargs.get('person_generation', 'ALLOW_ADULT'),
            include_rai_reason=kwargs.get('include_rai_reason', True),
            include_safety_attributes=kwargs.get('include_safety_attributes', True),
            output_mime_type=kwargs.get('output_mime_type', 'image/png'),
            output_compression_quality=kwargs.get('output_compression_quality', 95)
        )
        
        # Create reference image with scale configuration
        reference_image = genai_types.RawReferenceImage(
            reference_id=1,
            reference_image=genai_types.Image.from_file(location=image_path)
        )
        
        response = self.sdk_initializer.client.models.edit_image(
            model=model,
            prompt=expand_prompt,
            reference_images=[reference_image],
            config=config
        )
        
        return await self._process_expansion_results(response, "scale", x_scale=x_scale, y_scale=y_scale)
    
    async def _expand_by_offset(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Expand image by pixel offsets."""
        left_offset = kwargs.get('left_offset', 0)
        right_offset = kwargs.get('right_offset', 0)
        top_offset = kwargs.get('top_offset', 0)
        bottom_offset = kwargs.get('bottom_offset', 0)
        
        logger.info(f"[Expand Service] Offset expansion: left={left_offset}, right={right_offset}, top={top_offset}, bottom={bottom_offset}")
        
        # Calculate total expansion
        total_width_expansion = left_offset + right_offset
        total_height_expansion = top_offset + bottom_offset
        
        if total_width_expansion == 0 and total_height_expansion == 0:
            raise ValueError("At least one offset must be greater than 0")
        
        # Build edit configuration for outpainting
        config = genai_types.EditImageConfig(
            edit_mode="EDIT_MODE_OUTPAINT",
            number_of_images=kwargs.get('number_of_images', 1),
            guidance_scale=kwargs.get('guidance_scale', 7.5),
            person_generation=kwargs.get('person_generation', 'ALLOW_ADULT'),
            include_rai_reason=kwargs.get('include_rai_reason', True),
            include_safety_attributes=kwargs.get('include_safety_attributes', True),
            output_mime_type=kwargs.get('output_mime_type', 'image/png'),
            output_compression_quality=kwargs.get('output_compression_quality', 95)
        )
        
        # Create reference image
        reference_image = genai_types.RawReferenceImage(
            reference_id=1,
            reference_image=genai_types.Image.from_file(location=image_path)
        )
        
        response = self.sdk_initializer.client.models.edit_image(
            model=model,
            prompt=expand_prompt,
            reference_images=[reference_image],
            config=config
        )
        
        return await self._process_expansion_results(
            response, "offset",
            left_offset=left_offset,
            right_offset=right_offset,
            top_offset=top_offset,
            bottom_offset=bottom_offset
        )
    
    async def _expand_by_ratio(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Expand image to specific aspect ratio."""
        output_ratio = kwargs.get('output_ratio', '16:9')
        angle = kwargs.get('angle', 0)
        
        logger.info(f"[Expand Service] Ratio expansion: ratio={output_ratio}, angle={angle}")
        
        # Parse aspect ratio
        try:
            width_ratio, height_ratio = map(int, output_ratio.split(':'))
        except ValueError:
            raise ValueError(f"Invalid aspect ratio format: {output_ratio}. Use format like '16:9'")
        
        # Build edit configuration for outpainting
        config = genai_types.EditImageConfig(
            edit_mode="EDIT_MODE_OUTPAINT",
            number_of_images=kwargs.get('number_of_images', 1),
            aspect_ratio=output_ratio,
            guidance_scale=kwargs.get('guidance_scale', 7.5),
            person_generation=kwargs.get('person_generation', 'ALLOW_ADULT'),
            include_rai_reason=kwargs.get('include_rai_reason', True),
            include_safety_attributes=kwargs.get('include_safety_attributes', True),
            output_mime_type=kwargs.get('output_mime_type', 'image/png'),
            output_compression_quality=kwargs.get('output_compression_quality', 95)
        )
        
        # Create reference image
        reference_image = genai_types.RawReferenceImage(
            reference_id=1,
            reference_image=genai_types.Image.from_file(location=image_path)
        )
        
        response = self.sdk_initializer.client.models.edit_image(
            model=model,
            prompt=expand_prompt,
            reference_images=[reference_image],
            config=config
        )
        
        return await self._process_expansion_results(
            response, "ratio",
            output_ratio=output_ratio,
            angle=angle
        )
    
    async def _process_expansion_results(
        self,
        response,
        mode: str,
        **metadata
    ) -> List[Dict[str, Any]]:
        """Process expansion results."""
        results = []
        
        if response.generated_images:
            for idx, generated_image in enumerate(response.generated_images):
                # Check for RAI filtering first
                if hasattr(generated_image, 'rai_filtered_reason') and generated_image.rai_filtered_reason:
                    logger.warning(f"[Expand Service] Image {idx} was filtered by RAI: {generated_image.rai_filtered_reason}")
                    continue
                
                if not generated_image.image:
                    continue
                
                # Check if image_bytes is actually present
                if not hasattr(generated_image.image, 'image_bytes') or generated_image.image.image_bytes is None:
                    logger.warning(f"[Expand Service] Image {idx} has no image_bytes, skipping")
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
                        "expansion_mode": mode,
                        "size": len(image_bytes)
                    }
                    
                    # Add mode-specific metadata
                    result.update(metadata)
                    
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
    
    def _validate_expand_parameters(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,
        mode: str,
        **kwargs
    ) -> None:
        """
        Validate parameters for image expansion using standardized validation.
        
        Args:
            image_path: Path to the image to expand
            expand_prompt: Description of what to add in expanded areas
            model: Model to use for expansion
            mode: Expansion mode
            **kwargs: Additional parameters
        
        Raises:
            ParameterValidationError: If any parameter is invalid
        """
        # Validate required parameters with enhanced error messages
        self.validator.validate_required_string('image_path', image_path)
        self.validator.validate_required_string('expand_prompt', expand_prompt, max_length=2000)
        self.validator.validate_model(model, list(self.expand_models))
        self.validator.validate_choice('mode', mode, self.validator.EXPANSION_MODES)
        
        # Validate mode-specific parameters
        if mode == "scale":
            self._validate_scale_parameters(**kwargs)
        elif mode == "offset":
            self._validate_offset_parameters(**kwargs)
        elif mode == "ratio":
            self._validate_ratio_parameters(**kwargs)
        
        # Validate common parameters
        self._validate_common_parameters(**kwargs)
        
        logger.info(f"[Expand Service] Parameter validation passed for mode: {mode}")
    
    def _validate_scale_parameters(self, **kwargs) -> None:
        """Validate parameters for scale mode using standardized validation."""
        x_scale = kwargs.get('x_scale', 1.5)
        y_scale = kwargs.get('y_scale', 1.5)
        
        self.validator.validate_numeric_range(
            'x_scale', x_scale, min_value=1.0, max_value=3.0, value_type=float
        )
        self.validator.validate_numeric_range(
            'y_scale', y_scale, min_value=1.0, max_value=3.0, value_type=float
        )
    
    def _validate_offset_parameters(self, **kwargs) -> None:
        """Validate parameters for offset mode using standardized validation."""
        offsets = {
            'left_offset': kwargs.get('left_offset', 0),
            'right_offset': kwargs.get('right_offset', 0),
            'top_offset': kwargs.get('top_offset', 0),
            'bottom_offset': kwargs.get('bottom_offset', 0)
        }
        
        # Validate each offset
        for name, value in offsets.items():
            self.validator.validate_numeric_range(
                name, value, min_value=0, max_value=1000, value_type=int
            )
        
        # At least one offset must be greater than 0
        if all(offset == 0 for offset in offsets.values()):
            from ..common.parameter_validation import ParameterValidationError
            raise ParameterValidationError(
                parameter='offsets',
                value=offsets,
                message="At least one offset must be greater than 0 for offset mode",
                suggestion="Set at least one of left_offset, right_offset, top_offset, or bottom_offset to a value greater than 0",
                service="Expand Service"
            )
    
    def _validate_ratio_parameters(self, **kwargs) -> None:
        """Validate parameters for ratio mode."""
        output_ratio = kwargs.get('output_ratio', '16:9')
        angle = kwargs.get('angle', 0)
        
        # Validate aspect ratio format
        if not isinstance(output_ratio, str) or ':' not in output_ratio:
            raise ValueError(f"Invalid output_ratio format: {output_ratio}. Use format like '16:9'")
        
        try:
            width_ratio, height_ratio = map(int, output_ratio.split(':'))
            if width_ratio <= 0 or height_ratio <= 0:
                raise ValueError("Aspect ratio values must be positive integers")
        except ValueError as e:
            raise ValueError(f"Invalid aspect ratio format: {output_ratio}. Use format like '16:9'. Error: {e}")
        
        # Validate supported ratios
        supported_ratios = ["1:1", "3:4", "4:3", "9:16", "16:9"]
        if output_ratio not in supported_ratios:
            logger.warning(f"[Expand Service] Aspect ratio {output_ratio} may not be supported. Supported ratios: {supported_ratios}")
        
        # Validate angle
        if not isinstance(angle, (int, float)) or angle < 0 or angle >= 360:
            raise ValueError(f"Invalid angle: {angle}. Must be a number between 0 and 359")
    
    def _validate_common_parameters(self, **kwargs) -> None:
        """Validate common parameters for all modes."""
        # Validate number_of_images
        number_of_images = kwargs.get('number_of_images', 1)
        if not isinstance(number_of_images, int) or number_of_images < 1 or number_of_images > 4:
            raise ValueError(f"Invalid number_of_images: {number_of_images}. Must be an integer between 1 and 4")
        
        # Validate guidance_scale
        guidance_scale = kwargs.get('guidance_scale', 7.5)
        if not isinstance(guidance_scale, (int, float)) or guidance_scale < 1.0 or guidance_scale > 20.0:
            raise ValueError(f"Invalid guidance_scale: {guidance_scale}. Must be a number between 1.0 and 20.0")
        
        # Validate person_generation
        person_generation = kwargs.get('person_generation', 'ALLOW_ADULT')
        valid_person_settings = ['ALLOW_ADULT', 'ALLOW_MINOR', 'BLOCK_ALL']
        if person_generation not in valid_person_settings:
            raise ValueError(f"Invalid person_generation: {person_generation}. Must be one of {valid_person_settings}")
        
        # Validate output_compression_quality
        quality = kwargs.get('output_compression_quality', 95)
        if not isinstance(quality, int) or quality < 1 or quality > 100:
            raise ValueError(f"Invalid output_compression_quality: {quality}. Must be an integer between 1 and 100")
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported models for image expansion."""
        return list(self.expand_models)
    
    def get_expansion_capabilities(self) -> Dict[str, Any]:
        """Get expansion capabilities and limitations."""
        return {
            "modes": ["scale", "offset", "ratio"],
            "scale_mode": {
                "min_scale": 1.1,
                "max_scale": 3.0,
                "supports_different_xy": True
            },
            "offset_mode": {
                "max_offset_pixels": 1000,
                "supports_all_directions": True
            },
            "ratio_mode": {
                "supported_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
                "supports_rotation": True,
                "max_angle": 360
            },
            "output_formats": ["image/png", "image/jpeg"],
            "max_output_resolution": "4K"
        }