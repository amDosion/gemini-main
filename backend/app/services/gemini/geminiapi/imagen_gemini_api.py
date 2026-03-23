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

from ..base.imagen_base import BaseImageGenerator
from ..client_pool import get_client_pool
from ..base.imagen_common import (
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

# Models that use generate_content() API instead of generate_images()
# These are native Gemini models that support image output via response_modalities
GENERATE_CONTENT_MODELS = {
    # Gemini image models
    'gemini-2.5-flash-image',
    'gemini-2.5-flash-image-preview',
    'gemini-2.5-pro-image',
    'gemini-2.5-pro-image-preview',
    'gemini-3-pro-image',
    'gemini-3-pro-image-preview',
    'gemini-3.0-pro-image',
    'gemini-3.0-pro-image-preview',
    'gemini-3.1-flash-image-preview',
}

def _is_generate_content_model(model: str) -> bool:
    """Check if model should use generate_content instead of generate_images."""
    short_name = model.split('/')[-1] if '/' in model else model
    lower = short_name.lower()
    # Exact match
    if short_name in GENERATE_CONTENT_MODELS:
        return True
    # Pattern match: nano-banana series, gemini-*-image-*
    if 'nano-banana' in lower:
        return True
    if 'gemini' in lower and 'image' in lower:
        return True
    return False

# Import Google GenAI SDK
try:
    from google.genai import types as genai_types
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
            pool = get_client_pool()
            self._client = pool.get_client(api_key=self.api_key, vertexai=False)
            self._initialized = True
            logger.info("[GeminiAPIImageGenerator] Client initialized from unified pool")
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
        import time
        import sys
        start_time = time.time()
        
        logger.info(f"[GeminiAPIImageGenerator] ========== 开始生成图片 ==========")
        logger.info(f"[GeminiAPIImageGenerator] 📥 请求参数:")
        logger.info(f"[GeminiAPIImageGenerator]     - model: {model}")
        logger.info(f"[GeminiAPIImageGenerator]     - prompt: {prompt[:100] + '...' if len(prompt) > 100 else prompt}")
        logger.info(f"[GeminiAPIImageGenerator]     - prompt长度: {len(prompt)}")
        for key, value in kwargs.items():
            if key in ['number_of_images', 'aspect_ratio', 'image_size', 'output_mime_type', 'image_style']:
                logger.info(f"[GeminiAPIImageGenerator]     - {key}: {value}")
        
        self._ensure_initialized()
        logger.info(f"[GeminiAPIImageGenerator] ✅ 客户端已初始化")
        
        # Route: native Gemini models skip Imagen validation (different limits)
        if _is_generate_content_model(model):
            logger.info(f"[GeminiAPIImageGenerator] 🔄 [步骤1] Gemini native model, skipping Imagen validation")
        else:
            logger.info(f"[GeminiAPIImageGenerator] 🔄 [步骤1] 验证参数...")
            self.validate_parameters(**kwargs)
            logger.info(f"[GeminiAPIImageGenerator] ✅ [步骤1] 参数验证通过")
        
        logger.info(f"[GeminiAPIImageGenerator] 🔄 [步骤2] 构建配置...")
        config = self._build_config(model=model, **kwargs)
        logger.info(f"[GeminiAPIImageGenerator] ✅ [步骤2] 配置构建完成")
        
        # Apply style to prompt if specified
        image_style = kwargs.get('image_style')
        effective_prompt = prompt
        if image_style and image_style.lower() != "none":
            effective_prompt = f"{prompt}, style: {image_style}"
            logger.info(f"[GeminiAPIImageGenerator] ✅ 应用样式: {image_style}")
        
        try:
            # Route: native Gemini models use generate_content, Imagen models use generate_images
            if _is_generate_content_model(model):
                logger.info(f"[GeminiAPIImageGenerator] 🔄 [步骤3] 使用 generate_content API (native Gemini model)...")
                results = await self._generate_with_content(model, effective_prompt, **kwargs)
            else:
                logger.info(f"[GeminiAPIImageGenerator] 🔄 [步骤3] 使用 generate_images API (Imagen model)...")
                logger.info(f"[GeminiAPIImageGenerator]     - model: {model}")
                logger.info(f"[GeminiAPIImageGenerator]     - effective_prompt长度: {len(effective_prompt)}")
                
                api_start = time.time()
                response = self._client.models.generate_images(
                    model=model,
                    prompt=effective_prompt,
                    config=config
                )
                api_time = (time.time() - api_start) * 1000
                logger.info(f"[GeminiAPIImageGenerator] ✅ [步骤3] API调用完成 (耗时: {api_time:.2f}ms)")
                
                if not response.generated_images:
                    logger.error(f"[GeminiAPIImageGenerator] ❌ API未返回图片")
                    raise APIError("No images generated", api_type="gemini_api")
                
                logger.info(f"[GeminiAPIImageGenerator]     - 返回图片数量: {len(response.generated_images)}")
                
                logger.info(f"[GeminiAPIImageGenerator] 🔄 [步骤4] 处理响应结果...")
                results = self._process_response(response, **kwargs)
            process_time = (time.time() - start_time) * 1000
            logger.info(f"[GeminiAPIImageGenerator] ✅ [步骤4] 响应处理完成 (耗时: {process_time:.2f}ms)")
            logger.info(f"[GeminiAPIImageGenerator]     - 最终返回图片数量: {len(results)}")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[GeminiAPIImageGenerator] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
            
            return results
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            logger.error(f"[GeminiAPIImageGenerator] ❌ 生成失败 (耗时: {total_time:.2f}ms): {e}", exc_info=True)
            raise APIError(
                f"Image generation failed: {e}",
                api_type="gemini_api",
                original_error=e
            )
    
    async def _generate_with_content(self, model: str, prompt: str, **kwargs) -> List[Dict[str, Any]]:
        """Generate images using Gemini generate_content API (for native Gemini image models)."""
        import time
        start_time = time.time()

        aspect_ratio = kwargs.get('image_aspect_ratio') or kwargs.get('aspect_ratio', '1:1')
        image_size = kwargs.get('image_resolution') or kwargs.get('image_size')
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
        output_compression_quality = kwargs.get('output_compression_quality')
        number_of_images = min(max(kwargs.get('number_of_images', 1), 1), 8)
        enhance_prompt = kwargs.get('enhance_prompt', False)
        enhance_prompt_model = kwargs.get('enhance_prompt_model')

        image_style = kwargs.get('image_style')
        effective_prompt = prompt
        if image_style and image_style.lower() != "none":
            effective_prompt = f"{prompt}, style: {image_style}"

        # Two-stage prompt enhancement (same as conversational_image_edit_service)
        enhanced_prompt_text = None
        if enhance_prompt:
            try:
                enhanced = await self._enhance_prompt(effective_prompt, enhance_prompt_model)
                if enhanced:
                    logger.info(f"[GeminiAPIImageGenerator] ✅ Enhanced prompt (len={len(enhanced)})")
                    enhanced_prompt_text = enhanced
                    effective_prompt = enhanced
            except Exception as e:
                logger.warning(f"[GeminiAPIImageGenerator] Prompt enhancement failed, using original: {e}")

        text_part = genai_types.Part.from_text(text=effective_prompt)
        contents = [genai_types.Content(role="user", parts=[text_part])]

        generate_config = genai_types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],

            image_config=genai_types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
        )

        logger.info(f"[GeminiAPIImageGenerator] 🔄 [Gemini] model={model}, images={number_of_images}")

        # Generate images: single = direct call, multiple = concurrent calls
        if number_of_images == 1:
            # Single image: direct generate_content (fastest)
            try:
                api_start = time.time()
                response = self._client.models.generate_content(
                    model=model, contents=contents, config=generate_config,
                )
                api_time = (time.time() - api_start) * 1000
                logger.info(f"[GeminiAPIImageGenerator] ✅ [Gemini] Single image done ({api_time:.0f}ms)")
                results = self._extract_images_from_response(response, output_mime_type)
                if not results:
                    raise APIError("No image generated", api_type="gemini_api")
                if enhanced_prompt_text:
                    for r in results:
                        r["enhanced_prompt"] = enhanced_prompt_text
            except APIError:
                raise
            except Exception as e:
                raise APIError(f"Image generation failed: {e}", api_type="gemini_api", original_error=e)
        else:
            # Multiple images: concurrent independent requests
            import asyncio
            
            async def _gen_one(idx):
                try:
                    resp = await asyncio.to_thread(
                        self._client.models.generate_content,
                        model=model, contents=contents, config=generate_config,
                    )
                    imgs = self._extract_images_from_response(resp, output_mime_type)
                    if imgs:
                        logger.info(f"[GeminiAPIImageGenerator] ✅ [Gemini] Image {idx+1}/{number_of_images} done")
                    return imgs
                except Exception as e:
                    logger.warning(f"[GeminiAPIImageGenerator] ⚠️ Image {idx+1}/{number_of_images} failed: {e}")
                    return []

            logger.info(f"[GeminiAPIImageGenerator] 🔄 [Gemini] Launching {number_of_images} concurrent requests...")
            all_results = await asyncio.gather(*[_gen_one(i) for i in range(number_of_images)])
            
            results = []
            for batch in all_results:
                for img in batch:
                    img["index"] = len(results)
                    results.append(img)
            
            failures = sum(1 for r in all_results if not r)
            if not results:
                raise APIError(f"All {number_of_images} generations failed", api_type="gemini_api")
            if enhanced_prompt_text:
                for r in results:
                    r["enhanced_prompt"] = enhanced_prompt_text
            if failures > 0:
                logger.info(f"[GeminiAPIImageGenerator] Partial: {len(results)}/{number_of_images} ({failures} failed)")

        total_time = (time.time() - start_time) * 1000
        logger.info(f"[GeminiAPIImageGenerator] ✅ [Gemini] Total: {len(results)} images ({total_time:.0f}ms)")
        return results

    def _extract_images_from_response(self, response, output_mime_type='image/png'):
        images = []
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                            image_bytes = part.inline_data.data
                            b64_data = encode_image_to_base64(image_bytes)
                            mime = getattr(part.inline_data, 'mime_type', None) or output_mime_type
                            images.append({
                                "url": f"data:{mime};base64,{b64_data}",
                                "mime_type": mime,
                                "index": 0,
                                "size": len(image_bytes),
                            })
        return images

    async def _enhance_prompt(self, prompt: str, model_hint: str = None) -> str:
        """Two-stage prompt enhancement using a text model."""
        enhance_model = model_hint or 'gemini-2.5-flash'
        self._ensure_initialized()
        try:
            response = self._client.models.generate_content(
                model=enhance_model,
                contents=[
                    f"You are a professional image generation prompt enhancer. "
                    f"Rewrite the following prompt to be more direct, specific, and visually actionable. "
                    f"Return ONLY the enhanced prompt text, no explanations.\n\n"
                    f"Original prompt: {prompt}"
                ],
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"[GeminiAPIImageGenerator] _enhance_prompt error: {e}")
        return prompt

    def _build_config(self, **kwargs) -> 'genai_types.GenerateImagesConfig':
        """Build Gemini API configuration from parameters."""
        number_of_images = kwargs.get('number_of_images', 1)
        number_of_images = min(max(number_of_images, 1), 4)
        
        aspect_ratio = kwargs.get('image_aspect_ratio') or kwargs.get('aspect_ratio', '1:1')
        # Default to PNG format for best quality (no compression)
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
        
        config_kwargs = {
            "number_of_images": number_of_images,
            "aspect_ratio": aspect_ratio,
            "output_mime_type": output_mime_type,
        }
        
        # Add optional parameters
        # ⚠️ 注意：某些模型（如 imagen-4.0-generate-001）不支持 image_size 参数
        # 如果传递了不支持的参数，API 会返回 "sampleImageSize is not adjustable" 错误
        # 解决方案：只对支持该参数的模型传递 image_size
        image_size = kwargs.get('image_size')
        model = kwargs.get('model', '')
        
        # 检查模型是否支持 image_size 参数
        # imagen-4.0-generate-001 不支持 image_size（会报错 "sampleImageSize is not adjustable"）
        # imagen-3.0-generate-002 支持 image_size
        models_that_do_not_support_image_size = [
            'imagen-4.0-generate-001',
            'imagen-4.0',  # 所有 4.0 版本都不支持
        ]
        
        if image_size and image_size in VALID_IMAGE_SIZES:
            # 检查模型是否在不支持列表中
            if any(unsupported_model in model for unsupported_model in models_that_do_not_support_image_size):
                logger.warning(
                    f"[GeminiAPIImageGenerator] Model {model} does not support image_size parameter, "
                    f"skipping to avoid 'sampleImageSize is not adjustable' error"
                )
            else:
                # 对支持的模型传递 image_size 参数
                config_kwargs["image_size"] = image_size
                logger.info(f"[GeminiAPIImageGenerator] Using image_size={image_size} for model={model}")
        
        # Add compression quality for JPEG (default 100 = no compression)
        if output_mime_type == 'image/jpeg':
            compression_quality = kwargs.get('output_compression_quality', 100)
            config_kwargs["output_compression_quality"] = compression_quality
        
        logger.info(f"[GeminiAPIImageGenerator] Config: {config_kwargs}")
        
        return genai_types.GenerateImagesConfig(**config_kwargs)
    
    def _process_response(
        self,
        response,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Process Gemini API response and extract images."""
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
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
                    "mime_type": output_mime_type,
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
                
                # ✅ 提取增强后的提示词（如果启用了 enhance_prompt）
                if hasattr(generated_image, 'enhanced_prompt') and generated_image.enhanced_prompt:
                    result["enhanced_prompt"] = generated_image.enhanced_prompt
                
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
