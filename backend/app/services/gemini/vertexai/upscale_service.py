"""
Image Upscale Service (重构版)

使用新版 google-genai SDK，通过 client_pool 统一管理客户端
基于官方 SDK 测试: test_upscale_image.py

功能：图片放大 (2x/4x)
模型：imagen-4.0-upscale-preview (仅 Vertex AI)
"""

import logging
import base64
import io
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from google.genai import types

from ..client_pool import get_client_pool

logger = logging.getLogger(__name__)


@dataclass
class UpscaleResult:
    """Upscale 结果"""
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mime_type: str = "image/png"
    original_size: Optional[tuple] = None
    upscaled_size: Optional[tuple] = None
    error: Optional[str] = None


class UpscaleService:
    """
    图片放大服务 (重构版)

    使用新版 google-genai SDK 和统一的 client_pool
    仅支持 Vertex AI 模式

    官方 SDK 参考:
    - 模型: imagen-4.0-upscale-preview
    - API: client.models.upscale_image()
    - 配置: types.UpscaleImageConfig
    """

    # 支持的模型
    SUPPORTED_MODELS = {
        'imagen-4.0-upscale-preview',  # 推荐
    }

    # 支持的放大倍数
    VALID_UPSCALE_FACTORS = ['x2', 'x4']

    # 最大输出分辨率 (像素)
    MAX_OUTPUT_MEGAPIXELS = 17

    def __init__(self):
        self._project_id = None
        self._location = None
        self._initialized = False

    def _get_config(self) -> tuple:
        """获取 GCP 配置"""
        if not self._initialized:
            try:
                from ...core.config import settings
                self._project_id = settings.gcp_project_id
                self._location = settings.gcp_location or "us-central1"
                self._initialized = True
            except Exception as e:
                logger.error(f"[UpscaleService] Failed to load config: {e}")
                raise ValueError("GCP configuration not available")

        if not self._project_id:
            raise ValueError("GCP_PROJECT_ID not configured")

        return self._project_id, self._location

    def _get_vertex_client(self):
        """获取 Vertex AI 客户端 (通过 client_pool)"""
        project_id, location = self._get_config()

        pool = get_client_pool()
        client = pool.get_client(
            vertexai=True,
            project=project_id,
            location=location
        )

        logger.debug(f"[UpscaleService] Got Vertex AI client: project={project_id}, location={location}")
        return client

    def _clean_base64(self, data: str) -> str:
        """清理 Base64 前缀"""
        if data.startswith('data:'):
            return data.split(',', 1)[1]
        return data

    def _bytes_to_base64(self, data: bytes) -> str:
        """字节转 Base64"""
        return base64.b64encode(data).decode('utf-8')

    def _base64_to_bytes(self, data: str) -> bytes:
        """Base64 转字节"""
        return base64.b64decode(self._clean_base64(data))

    def _check_resolution_limit(
        self,
        image_bytes: bytes,
        upscale_factor: str
    ) -> tuple:
        """
        检查分辨率限制

        Returns:
            (original_size, new_size, error_message)
        """
        try:
            from PIL import Image as PILImage
            img = PILImage.open(io.BytesIO(image_bytes))
            original_width, original_height = img.size

            factor = 2 if upscale_factor == "x2" else 4
            new_width = original_width * factor
            new_height = original_height * factor
            new_megapixels = (new_width * new_height) / 1_000_000

            if new_megapixels > self.MAX_OUTPUT_MEGAPIXELS:
                return (
                    (original_width, original_height),
                    (new_width, new_height),
                    f"Output resolution {new_megapixels:.2f}MP exceeds limit {self.MAX_OUTPUT_MEGAPIXELS}MP"
                )

            return (
                (original_width, original_height),
                (new_width, new_height),
                None
            )
        except Exception as e:
            return None, None, f"Failed to check image resolution: {str(e)}"

    def upscale_image(
        self,
        image_base64: str,
        upscale_factor: str = "x2",
        model: str = "imagen-4.0-upscale-preview",
        output_mime_type: str = "image/png",
        output_compression_quality: int = 95,
        enhance_input_image: bool = True,
        image_preservation_factor: float = 0.6,
        include_rai_reason: bool = True,
        safety_filter_level: str = "BLOCK_LOW_AND_ABOVE",
        person_generation: str = "ALLOW_ADULT",
    ) -> UpscaleResult:
        """
        图片放大 - 使用 upscale_image API

        Args:
            image_base64: Base64 编码的原图
            upscale_factor: 放大倍数 ("x2" 或 "x4")
            model: 模型 ID
            output_mime_type: 输出格式 ("image/png" 或 "image/jpeg")
            output_compression_quality: JPEG 压缩质量 (1-100)
            enhance_input_image: 是否增强输入图像
            image_preservation_factor: 图像保留因子 (0.0-1.0)
            include_rai_reason: 是否包含 RAI 原因
            safety_filter_level: 安全过滤级别
            person_generation: 人物生成设置

        Returns:
            UpscaleResult
        """
        try:
            # 验证参数
            if upscale_factor not in self.VALID_UPSCALE_FACTORS:
                return UpscaleResult(
                    success=False,
                    error=f"Invalid upscale factor: {upscale_factor}. Must be one of {self.VALID_UPSCALE_FACTORS}"
                )

            if model not in self.SUPPORTED_MODELS:
                logger.warning(f"[UpscaleService] Model {model} may not be supported")

            # 获取客户端
            client = self._get_vertex_client()

            # 准备图像
            image_bytes = self._base64_to_bytes(image_base64)

            # 检查分辨率限制
            original_size, new_size, error = self._check_resolution_limit(image_bytes, upscale_factor)
            if error:
                return UpscaleResult(
                    success=False,
                    original_size=original_size,
                    error=error
                )

            logger.info(
                f"[UpscaleService] Upscale: {original_size[0]}x{original_size[1]} -> "
                f"{new_size[0]}x{new_size[1]} ({upscale_factor})"
            )

            # 构建配置 (参考官方 SDK test_upscale_image.py)
            config = types.UpscaleImageConfig(
                include_rai_reason=include_rai_reason,
                person_generation=getattr(types.PersonGeneration, person_generation, types.PersonGeneration.ALLOW_ADULT),
                safety_filter_level=getattr(types.SafetyFilterLevel, safety_filter_level, types.SafetyFilterLevel.BLOCK_LOW_AND_ABOVE),
                output_mime_type=output_mime_type,
                output_compression_quality=output_compression_quality,
                enhance_input_image=enhance_input_image,
                image_preservation_factor=image_preservation_factor,
            )

            # 调用 upscale_image API
            response = client.models.upscale_image(
                model=model,
                image=types.Image(image_bytes=image_bytes),
                upscale_factor=upscale_factor,
                config=config,
            )

            if response.generated_images and len(response.generated_images) > 0:
                result_image = response.generated_images[0].image
                result_base64 = self._bytes_to_base64(result_image.image_bytes)

                logger.info(f"[UpscaleService] Upscale successful")
                return UpscaleResult(
                    success=True,
                    image=result_base64,
                    mime_type=output_mime_type,
                    original_size=original_size,
                    upscaled_size=new_size
                )
            else:
                return UpscaleResult(success=False, error="No image generated")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[UpscaleService] Upscale error: {error_msg}")
            return self._handle_error(error_msg)

    def upscale_image_from_path(
        self,
        image_path: str,
        upscale_factor: str = "x2",
        model: str = "imagen-4.0-upscale-preview",
        **kwargs
    ) -> UpscaleResult:
        """
        从文件路径放大图片 (兼容旧接口)

        Args:
            image_path: 图片文件路径
            upscale_factor: 放大倍数
            model: 模型 ID
            **kwargs: 其他参数

        Returns:
            UpscaleResult
        """
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            image_base64 = self._bytes_to_base64(image_bytes)
            return self.upscale_image(
                image_base64=image_base64,
                upscale_factor=upscale_factor,
                model=model,
                **kwargs
            )
        except Exception as e:
            return UpscaleResult(success=False, error=f"Failed to read image: {str(e)}")

    def _handle_error(self, error_msg: str) -> UpscaleResult:
        """统一的错误处理"""
        error_upper = error_msg.upper()

        if "SAFETY" in error_upper:
            return UpscaleResult(success=False, error="Safety filter triggered. Please use a different image.")
        elif "QUOTA" in error_upper or "RESOURCE_EXHAUSTED" in error_upper:
            return UpscaleResult(success=False, error="API quota exceeded. Please try again later.")
        elif "PERMISSION" in error_upper or "UNAUTHORIZED" in error_upper:
            return UpscaleResult(success=False, error="Authentication error. Please check GCP credentials.")
        elif "only supported in the Vertex AI client" in error_msg.lower():
            return UpscaleResult(success=False, error="This feature requires Vertex AI mode. Please configure GCP credentials.")
        else:
            return UpscaleResult(success=False, error=error_msg)

    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return list(self.SUPPORTED_MODELS)

    def get_capabilities(self) -> Dict[str, Any]:
        """获取放大功能的能力说明"""
        return {
            "upscale_factors": self.VALID_UPSCALE_FACTORS,
            "max_output_megapixels": self.MAX_OUTPUT_MEGAPIXELS,
            "supported_formats": ["image/png", "image/jpeg"],
            "supported_models": list(self.SUPPORTED_MODELS),
            "config_options": {
                "enhance_input_image": "Enhance input before upscaling",
                "image_preservation_factor": "Control how much to preserve original (0.0-1.0)",
                "output_compression_quality": "JPEG quality (1-100)",
                "person_generation": "ALLOW_ADULT, DONT_ALLOW, etc.",
                "safety_filter_level": "BLOCK_LOW_AND_ABOVE, BLOCK_MEDIUM_AND_ABOVE, etc."
            }
        }


# 单例实例
upscale_service = UpscaleService()
