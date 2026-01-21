"""
Image Generator Module (Backward Compatibility Wrapper)

This module provides backward compatibility for existing code while delegating
to the new coordinator-based architecture that supports both Gemini API and Vertex AI.

For new code, consider using ImagenCoordinator directly for better control.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator
from sqlalchemy.orm import Session

from .imagen_coordinator import ImagenCoordinator
from .imagen_common import ContentPolicyError

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    Backward compatibility wrapper for image generation.
    
    This class maintains the original API while delegating to the new
    coordinator-based architecture. It automatically selects between
    Gemini API and Vertex AI based on user configuration or environment.
    
    For new code, consider using ImagenCoordinator directly.
    """
    
    def __init__(self, api_key: str = None, user_id: str = None, db: Session = None):
        """
        Initialize image generator.
        
        Args:
            api_key: Gemini API key (optional, for backward compatibility)
            user_id: User ID for loading user-specific configuration
            db: Database session for loading user configuration
        
        Note: The api_key parameter is maintained for backward compatibility.
        When user_id and db are provided, configuration is loaded from database.
        Otherwise, falls back to environment variables.
        """
        # Store API key for potential use
        self._api_key = api_key
        self._user_id = user_id
        self._db = db
        
        # ✅ 初始化 coordinator 时传递已解密的 API Key（如果提供）
        # 这样 coordinator 就不需要从数据库重新加载和解密
        self._coordinator = ImagenCoordinator(user_id=user_id, db=db, api_key=api_key)
        
        logger.info(f"[ImageGenerator] Initialized with coordinator-based architecture, user_id={user_id}, api_key_provided={api_key is not None}")
    
    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate image(s) using Imagen or Gemini models.
        
        This method delegates to the appropriate implementation (Gemini API or Vertex AI)
        based on environment configuration.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use (must be provided by caller, no default)
            **kwargs: Additional parameters including:
                - number_of_images: Number of images to generate (1-4)
                - aspect_ratio: Image aspect ratio ('1:1', '9:16', '16:9', '4:3', '3:4')
                - image_size: Image resolution ('1K', '2K')
                - image_style: Style to apply to the image
                - person_generation: (Deprecated - parameter removed, API uses default 'allow_adult')
                - include_rai_reason: Include RAI reason in response
                - output_mime_type: Output format ('image/png', 'image/jpeg')
                - output_compression_quality: JPEG compression quality (1-100)
        
        Returns:
            List of dicts with url, mimeType, index, size, and optional safety_attributes
        """
        import time
        start_time = time.time()
        
        logger.info(f"[ImageGenerator] ========== 开始图片生成 ==========")
        logger.info(f"[ImageGenerator] 📥 请求参数:")
        logger.info(f"[ImageGenerator]     - model: {model}")
        logger.info(f"[ImageGenerator]     - prompt: {prompt[:100] + '...' if len(prompt) > 100 else prompt}")
        logger.info(f"[ImageGenerator]     - prompt长度: {len(prompt)}")
        logger.info(f"[ImageGenerator]     - user_id: {self._user_id[:8] + '...' if self._user_id else 'None'}")
        for key, value in kwargs.items():
            if key in ['number_of_images', 'aspect_ratio', 'image_size', 'output_mime_type', 'image_style']:
                logger.info(f"[ImageGenerator]     - {key}: {value}")
        
        try:
            # Convert parameters based on API mode
            logger.info(f"[ImageGenerator] 🔄 [步骤1] 转换参数格式...")
            kwargs = self._convert_parameters_for_api(kwargs)
            logger.info(f"[ImageGenerator] ✅ [步骤1] 参数转换完成")
            
            # Get the appropriate generator from coordinator
            logger.info(f"[ImageGenerator] 🔄 [步骤2] 从 Coordinator 获取生成器...")
            generator = self._coordinator.get_generator()
            generator_type = type(generator).__name__
            logger.info(f"[ImageGenerator] ✅ [步骤2] 生成器获取完成: {generator_type}")
            
            # Delegate to the generator
            logger.info(f"[ImageGenerator] 🔄 [步骤3] 委托给生成器.generate_image()...")
            delegate_start = time.time()
            result = await generator.generate_image(prompt, model, **kwargs)
            delegate_time = (time.time() - delegate_start) * 1000
            logger.info(f"[ImageGenerator] ✅ [步骤3] 生成器调用完成 (耗时: {delegate_time:.2f}ms)")
            
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[ImageGenerator] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
            logger.info(f"[ImageGenerator]     - 返回图片数量: {len(result) if isinstance(result, list) else 'N/A'}")
            
            return result
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            logger.error(f"[ImageGenerator] ❌ 图片生成失败 (耗时: {total_time:.2f}ms): {e}", exc_info=True)
            raise
    
    # Parameter name mapping (camelCase -> snake_case)
    PARAM_MAPPING = {
        'numberOfImages': 'number_of_images',
        'imageAspectRatio': 'aspect_ratio',
        'aspectRatio': 'aspect_ratio',
        'imageResolution': 'image_size',
        'outputMimeType': 'output_mime_type',
        'negativePrompt': 'negative_prompt',
        # imageStyle maps to image_style (no change needed, already snake_case compatible)
    }
    
    def _convert_parameters_for_api(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert camelCase parameters to snake_case for Google SDK compatibility.
        Also removes deprecated parameters.
        
        Args:
            kwargs: Parameters that may be in camelCase or snake_case format
            
        Returns:
            Dictionary with all parameters converted to snake_case
        """
        result = {}
        
        for key, value in kwargs.items():
            # Skip deprecated parameters
            if key == 'person_generation':
                logger.info(
                    "[ImageGenerator] Removing person_generation parameter "
                    "(using API default: allow_adult)"
                )
                continue
            
            # Convert camelCase to snake_case if mapping exists
            new_key = self.PARAM_MAPPING.get(key, key)
            
            # If both versions exist, camelCase takes priority (first occurrence wins)
            if new_key not in result:
                result[new_key] = value
        
        # Set default output_mime_type to PNG if not specified
        if 'output_mime_type' not in result:
            result['output_mime_type'] = 'image/png'
        
        return result
    
    async def generate_image_stream(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate images with streaming progress updates.
        
        This is a simulated streaming interface for image generation,
        providing progress updates during the generation process.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use
            **kwargs: Additional parameters
        
        Yields:
            Progress updates and final results
        """
        try:
            # Yield initial progress
            yield {
                "type": "progress",
                "stage": "initializing",
                "progress": 0.0,
                "message": "Initializing image generation..."
            }
            
            await asyncio.sleep(0.1)
            
            yield {
                "type": "progress", 
                "stage": "processing",
                "progress": 0.3,
                "message": "Processing prompt and configuration..."
            }
            
            await asyncio.sleep(0.2)
            
            yield {
                "type": "progress",
                "stage": "generating", 
                "progress": 0.7,
                "message": "Generating image(s)..."
            }
            
            # Perform actual generation
            results = await self.generate_image(prompt, model, **kwargs)
            
            yield {
                "type": "progress",
                "stage": "finalizing",
                "progress": 0.9, 
                "message": "Finalizing results..."
            }
            
            await asyncio.sleep(0.1)
            
            # Yield final results
            yield {
                "type": "complete",
                "stage": "complete",
                "progress": 1.0,
                "message": "Image generation complete",
                "results": results
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "stage": "error",
                "progress": 0.0,
                "message": f"Image generation failed: {str(e)}",
                "error": str(e)
            }
            raise
    
    def get_supported_models(self) -> Dict[str, List[str]]:
        """
        Get list of supported models for different image operations.

        Returns:
            Dictionary mapping operation types to supported models
        """
        return {
            "generate": [
                "imagen-4.0-generate-001",
                "imagen-3.0-generate-002"
            ]
        }
    
    def get_model_capabilities(self, model: str) -> Dict[str, Any]:
        """
        Get capabilities and limitations for a specific model.

        Args:
            model: Model name

        Returns:
            Dictionary with model capabilities
        """
        capabilities = {
            "imagen-4.0-generate-001": {
                "max_images": 4,
                "aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
                "image_sizes": ["1K", "2K"],
                "supports_style": True,
                "max_prompt_length": 2000
            },
            "imagen-3.0-generate-002": {
                "max_images": 4,
                "aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
                "image_sizes": ["1K", "2K"],
                "supports_style": True,
                "max_prompt_length": 2000
            }
        }

        return capabilities.get(model, {
            "max_images": 1,
            "aspect_ratios": ["1:1"],
            "image_sizes": ["1K"],
            "supports_style": False,
            "max_prompt_length": 1000
        })
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get capabilities of the current API mode.
        
        Returns:
            Capabilities dictionary from the coordinator
        """
        return self._coordinator.get_capabilities()
    
    def get_current_api_mode(self) -> str:
        """
        Get the current API mode.
        
        Returns:
            'gemini_api' or 'vertex_ai'
        """
        return self._coordinator.get_current_api_mode()
