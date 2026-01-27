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

from ..base.imagen_base import BaseImageGenerator
from ..base.imagen_common import (
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
        import time
        import sys
        start_time = time.time()
        
        logger.info(f"[VertexAIImageGenerator] ========== 开始生成图片 ==========")
        logger.info(f"[VertexAIImageGenerator] 📥 请求参数:")
        logger.info(f"[VertexAIImageGenerator]     - model: {model}")
        logger.info(f"[VertexAIImageGenerator]     - prompt: {prompt[:100] + '...' if len(prompt) > 100 else prompt}")
        logger.info(f"[VertexAIImageGenerator]     - prompt长度: {len(prompt)}")
        for key, value in kwargs.items():
            if key in ['number_of_images', 'aspect_ratio', 'image_size', 'output_mime_type', 'image_style']:
                logger.info(f"[VertexAIImageGenerator]     - {key}: {value}")
        
        self._ensure_initialized()
        logger.info(f"[VertexAIImageGenerator] ✅ 客户端已初始化")
        
        logger.info(f"[VertexAIImageGenerator] 🔄 [步骤1] 验证参数...")
        self.validate_parameters(**kwargs)
        logger.info(f"[VertexAIImageGenerator] ✅ [步骤1] 参数验证通过")
        
        # Extract short model name from full path if needed
        # e.g., "publishers/google/models/gemini-3-pro-image-preview" -> "gemini-3-pro-image-preview"
        short_model_name = model.split('/')[-1] if '/' in model else model
        logger.info(f"[VertexAIImageGenerator] 🔄 [步骤2] 提取模型名称: {short_model_name}")
        
        # Check if this is a model that uses generate_content API
        uses_generate_content = short_model_name in GENERATE_CONTENT_MODELS
        logger.info(f"[VertexAIImageGenerator] 🔄 [步骤3] 检查API类型...")
        logger.info(f"[VertexAIImageGenerator]     - 使用 generate_content API: {uses_generate_content}")
        
        if uses_generate_content:
            # Use generate_content for Gemini/Veo models
            logger.info(f"[VertexAIImageGenerator] 🔄 [步骤4] 使用 Gemini generate_content API...")
            results = await self._generate_with_gemini(short_model_name, prompt, **kwargs)
        else:
            # Use generate_images for Imagen models
            logger.info(f"[VertexAIImageGenerator] 🔄 [步骤4] 使用 Imagen generate_images API...")
            results = await self._generate_with_imagen(short_model_name, prompt, **kwargs)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[VertexAIImageGenerator] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
        logger.info(f"[VertexAIImageGenerator]     - 返回图片数量: {len(results)}")
        
        return results
    
    async def _generate_with_imagen(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Generate images using Imagen models (generate_images API)."""
        import time
        start_time = time.time()
        
        logger.info(f"[VertexAIImageGenerator] 🔄 [Imagen] 开始使用 Imagen API 生成图片...")
        logger.info(f"[VertexAIImageGenerator]     - model: {model}")
        
        # Build configuration (传递 model 参数以便检查是否支持 image_size)
        logger.info(f"[VertexAIImageGenerator] 🔄 [Imagen] 构建配置...")
        config = self._build_config(model=model, **kwargs)
        logger.info(f"[VertexAIImageGenerator] ✅ [Imagen] 配置构建完成")
        
        # Apply style to prompt if specified
        image_style = kwargs.get('image_style')
        effective_prompt = prompt
        if image_style and image_style.lower() != "none":
            effective_prompt = f"{prompt}, style: {image_style}"
            logger.info(f"[VertexAIImageGenerator] ✅ [Imagen] 应用样式: {image_style}")
        
        try:
            logger.info(f"[VertexAIImageGenerator] 🔄 [Imagen] 调用 Vertex AI generate_images()...")
            logger.info(f"[VertexAIImageGenerator]     - model: {model}")
            logger.info(f"[VertexAIImageGenerator]     - effective_prompt长度: {len(effective_prompt)}")
            
            api_start = time.time()
            # Call Vertex AI generate_images API
            response = self._client.models.generate_images(
                model=model,
                prompt=effective_prompt,
                config=config
            )
            api_time = (time.time() - api_start) * 1000
            logger.info(f"[VertexAIImageGenerator] ✅ [Imagen] API调用完成 (耗时: {api_time:.2f}ms)")
            
            if not response.generated_images:
                logger.error(f"[VertexAIImageGenerator] ❌ [Imagen] API未返回图片")
                raise APIError("No images generated", api_type="vertex_ai")
            
            logger.info(f"[VertexAIImageGenerator]     - 返回图片数量: {len(response.generated_images)}")
            
            logger.info(f"[VertexAIImageGenerator] 🔄 [Imagen] 处理响应结果...")
            results = self._process_response(response, **kwargs)
            process_time = (time.time() - start_time) * 1000
            logger.info(f"[VertexAIImageGenerator] ✅ [Imagen] 响应处理完成 (耗时: {process_time:.2f}ms)")
            logger.info(f"[VertexAIImageGenerator]     - 最终返回图片数量: {len(results)}")
            
            return results
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            # ✅ 避免在异常日志中输出完整的 BASE64 内容
            error_msg = str(e)
            # 如果错误信息中包含 BASE64 数据，截断它
            if 'data:image' in error_msg or 'base64' in error_msg.lower():
                import re
                error_msg = re.sub(r'data:image[^,]+,\s*[A-Za-z0-9+/]{100,}', 'data:image/...base64...[TRUNCATED]', error_msg)
            logger.error(f"[VertexAIImageGenerator] ❌ [Imagen] 生成失败 (耗时: {total_time:.2f}ms): {error_msg}")
            raise APIError(
                f"Image generation failed: {error_msg}",
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
        import time
        start_time = time.time()
        
        logger.info(f"[VertexAIImageGenerator] 🔄 [Gemini] 开始使用 Gemini generate_content API 生成图片...")
        logger.info(f"[VertexAIImageGenerator]     - model: {model}")
        
        try:
            # Build Gemini configuration
            logger.info(f"[VertexAIImageGenerator] 🔄 [Gemini] 构建配置...")
            aspect_ratio = kwargs.get('aspect_ratio', '1:1')
            image_size = kwargs.get('image_size', '1K')
            # Default to PNG format for best quality (no compression)
            output_mime_type = kwargs.get('output_mime_type', 'image/png')
            number_of_images = min(max(kwargs.get('number_of_images', 1), 1), 8)
            
            logger.info(f"[VertexAIImageGenerator]     - aspect_ratio: {aspect_ratio}")
            logger.info(f"[VertexAIImageGenerator]     - image_size: {image_size}")
            logger.info(f"[VertexAIImageGenerator]     - output_mime_type: {output_mime_type}")
            logger.info(f"[VertexAIImageGenerator]     - number_of_images: {number_of_images}")
            
            # Apply style to prompt if specified
            image_style = kwargs.get('image_style')
            effective_prompt = prompt
            if image_style and image_style.lower() != "none":
                effective_prompt = f"{prompt}, style: {image_style}"
                logger.info(f"[VertexAIImageGenerator] ✅ [Gemini] 应用样式: {image_style}")
            
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
            
            logger.info(f"[VertexAIImageGenerator] ✅ [Gemini] 配置构建完成")
            
            # Generate images (may need multiple calls for multiple images)
            logger.info(f"[VertexAIImageGenerator] 🔄 [Gemini] 开始生成 {number_of_images} 张图片...")
            results = []
            for i in range(number_of_images):
                logger.info(f"[VertexAIImageGenerator] 🔄 [Gemini] 生成第 {i+1}/{number_of_images} 张图片...")
                api_start = time.time()
                response = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_content_config
                )
                api_time = (time.time() - api_start) * 1000
                logger.info(f"[VertexAIImageGenerator] ✅ [Gemini] 第 {i+1} 张图片API调用完成 (耗时: {api_time:.2f}ms)")
                
                # Extract image from response
                if response.candidates:
                    for candidate in response.candidates:
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    image_bytes = part.inline_data.data
                                    image_size_kb = len(image_bytes) / 1024
                                    b64_data = encode_image_to_base64(image_bytes)
                                    
                                    result = {
                                        "url": f"data:{output_mime_type};base64,{b64_data}",
                                        "mimeType": output_mime_type,
                                        "index": len(results),
                                        "size": len(image_bytes)
                                    }
                                    results.append(result)
                                    logger.info(f"[VertexAIImageGenerator] ✅ [Gemini] 第 {len(results)} 张图片处理完成 (大小: {image_size_kb:.2f} KB)")
                else:
                    logger.warning(f"[VertexAIImageGenerator] ⚠️ [Gemini] 第 {i+1} 张图片API未返回candidates")
            
            if not results:
                logger.error(f"[VertexAIImageGenerator] ❌ [Gemini] 未生成任何图片")
                raise APIError("No images generated from Gemini model", api_type="vertex_ai")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[VertexAIImageGenerator] ✅ [Gemini] 生成完成 (总耗时: {total_time:.2f}ms)")
            logger.info(f"[VertexAIImageGenerator]     - 最终返回图片数量: {len(results)}")
            return results
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            # ✅ 避免在异常日志中输出完整的 BASE64 内容
            error_msg = str(e)
            # 如果错误信息中包含 BASE64 数据，截断它
            if 'data:image' in error_msg or 'base64' in error_msg.lower():
                import re
                error_msg = re.sub(r'data:image[^,]+,\s*[A-Za-z0-9+/]{100,}', 'data:image/...base64...[TRUNCATED]', error_msg)
            logger.error(f"[VertexAIImageGenerator] ❌ [Gemini] 生成失败 (耗时: {total_time:.2f}ms): {error_msg}")
            raise APIError(
                f"Gemini image generation failed: {error_msg}",
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
                    f"[VertexAIImageGenerator] Model {model} does not support image_size parameter, "
                    f"skipping to avoid 'sampleImageSize is not adjustable' error"
                )
            else:
                # 对支持的模型传递 image_size 参数
                config_kwargs["image_size"] = image_size
                logger.info(f"[VertexAIImageGenerator] Using image_size={image_size} for model={model}")
        
        # Add compression quality for JPEG (default 100 = no compression)
        if output_mime_type == 'image/jpeg':
            compression_quality = kwargs.get('output_compression_quality', 100)
            config_kwargs["output_compression_quality"] = compression_quality
        
        # ✅ Add enhance_prompt parameter (default: true in Vertex AI)
        # 官方文档：使用基于 LLM 的重写提示功能，默认值为 true
        # 只有 Vertex AI 支持此参数，Gemini API 不支持
        enhance_prompt = kwargs.get('enhance_prompt')
        if enhance_prompt is not None:
            config_kwargs["enhance_prompt"] = enhance_prompt
            logger.info(f"[VertexAIImageGenerator] enhance_prompt={enhance_prompt}")
        
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
                
                # ✅ 提取增强后的提示词（如果启用了 enhance_prompt）
                # 调试：打印 generated_image 的所有属性
                logger.info(f"[VertexAIImageGenerator] Image {idx} attributes: {[attr for attr in dir(generated_image) if not attr.startswith('_')]}")
                
                # 尝试多种可能的字段名
                enhanced_prompt_value = None
                if hasattr(generated_image, 'enhanced_prompt') and generated_image.enhanced_prompt:
                    enhanced_prompt_value = generated_image.enhanced_prompt
                    logger.info(f"[VertexAIImageGenerator] ✅ Found enhanced_prompt: {enhanced_prompt_value[:100]}...")
                elif hasattr(generated_image, 'prompt') and generated_image.prompt:
                    # REST API 返回的字段名可能是 'prompt'
                    enhanced_prompt_value = generated_image.prompt
                    logger.info(f"[VertexAIImageGenerator] ✅ Found prompt: {enhanced_prompt_value[:100]}...")
                else:
                    logger.info(f"[VertexAIImageGenerator] ⚠️ No enhanced_prompt found in response")
                
                if enhanced_prompt_value:
                    result["enhancedPrompt"] = enhanced_prompt_value
                
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
        """
        Get Vertex AI capabilities.
        
        Returns:
            Dictionary containing:
            - api_type: 'vertex_ai'
            - supported_models: List of supported model IDs
            - max_images: Maximum number of images per request
            - supported_aspect_ratios: List of supported aspect ratios
            - aspect_ratios: Same as supported_aspect_ratios (backward compatibility)
            - image_sizes: List of supported image sizes
            - person_generation_modes: List of supported person generation modes
        """
        # Get supported models dynamically
        try:
            supported_models = self.get_supported_models()
        except Exception as e:
            logger.warning(f"[VertexAIImageGenerator] Failed to get supported models: {e}, using fallback list")
            # Fallback to static list if dynamic fetch fails
            supported_models = [
                'imagen-4.0-generate-001',
                'imagen-4.0-fast-generate-001',
                'imagen-4.0-ultra-generate-001',
                'imagen-3.0-generate-002',
                'imagen-3.0-generate-001',
                'imagen-3.0-fast-generate-001',
                'gemini-3-pro-image-preview',
                'gemini-2.5-flash-image-preview',
                'veo-3.1-generate-preview',
                'veo-3.1-fast-generate-preview'
            ]
        
        return {
            'api_type': 'vertex_ai',
            'supported_models': supported_models,  # ✅ 新增：支持的模型列表
            'max_images': 4,
            'supported_aspect_ratios': VALID_ASPECT_RATIOS,  # ✅ 新增：标准字段名
            'aspect_ratios': VALID_ASPECT_RATIOS,  # 保留向后兼容
            'image_sizes': VALID_IMAGE_SIZES,
            'person_generation_modes': ['dont_allow', 'allow_adult']  # ✅ 新增：根据官方文档，Imagen 4.0 支持 Person generation
        }
    
    def get_supported_models(self) -> List[str]:
        """
        Get supported image generation models from Vertex AI.
        
        Returns list of model short names (without 'publishers/google/models/' prefix).
        
        Note: Only includes actual image generation models, excludes:
        - Image editing models (capability-*, ingredients-*)
        - Image segmentation models (segmentation-*)
        - Image classification/detection models (classification-*, detection-*)
        - Special purpose models (product-recontext-*, virtual-try-on-*)
        """
        try:
            self._ensure_initialized()
            
            # List all models from Vertex AI
            models_list = self._client.models.list()
            
            # Extract model names and filter for image generation models only
            supported_models = []
            excluded_keywords = [
                'capability',  # 编辑模型：imagen-3.0-capability-001
                'ingredients',  # 编辑模型：imagen-4.0-ingredients-*
                'segmentation',  # 分割模型：image-segmentation-001
                'classification',  # 分类模型：imageclassification-*
                'detection',  # 检测模型：imageobjectdetection-*
                'recontext',  # 特殊用途：imagen-product-recontext-*
                'virtual-try-on',  # 特殊用途：virtual-try-on-*
                'product-recognizer',  # 产品识别
                'watermarkdetector',  # 水印检测
                'earth-ai-imagery',  # 地球AI图像（特殊用途）
            ]
            
            for model in models_list:
                model_name = model.name if hasattr(model, 'name') else str(model)
                
                # Extract short name from full path
                short_name = model_name.split('/')[-1] if '/' in model_name else model_name
                short_name_lower = short_name.lower()
                
                # Skip excluded models
                if any(excluded in short_name_lower for excluded in excluded_keywords):
                    continue
                
                # Include only actual image generation models
                # 1. Imagen generate models (imagen-*-generate-*)
                if short_name_lower.startswith('imagen-') and 'generate' in short_name_lower:
                    supported_models.append(short_name)
                # 2. Gemini image models (gemini-*-image-*)
                elif 'gemini' in short_name_lower and 'image' in short_name_lower:
                    supported_models.append(short_name)
                # 3. Veo video/image generation models (veo-*-generate-*)
                elif short_name_lower.startswith('veo-') and 'generate' in short_name_lower:
                    supported_models.append(short_name)
                # 4. Legacy imagegeneration model (if exists)
                elif short_name_lower == 'imagegeneration':
                    supported_models.append(short_name)
            
            # Sort models for consistent output
            supported_models.sort()
            
            logger.info(f"[VertexAIImageGenerator] Found {len(supported_models)} image generation models")
            if supported_models:
                logger.debug(f"[VertexAIImageGenerator] Models: {', '.join(supported_models[:10])}{'...' if len(supported_models) > 10 else ''}")
            
            return supported_models
            
        except Exception as e:
            logger.warning(f"[VertexAIImageGenerator] Failed to list models dynamically: {e}")
            # Fallback to static list of core generation models
            return [
                'imagen-4.0-generate-001',
                'imagen-4.0-fast-generate-001',
                'imagen-4.0-ultra-generate-001',
                'imagen-3.0-generate-001',
                'imagen-3.0-generate-002',
                'imagen-3.0-fast-generate-001',
                'gemini-3-pro-image-preview',
                'gemini-2.5-flash-image-preview',
                'gemini-2.5-flash-image',
                'veo-3.1-generate-001',
                'veo-3.1-fast-generate-001',
                'veo-3.0-generate-001',
                'veo-3.0-fast-generate-001',
                'veo-2.0-generate-001'
            ]
