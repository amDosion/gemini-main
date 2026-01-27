"""
Mask Edit Service (掩码编辑服务)

使用新版 google-genai SDK，通过 client_pool 统一管理客户端
基于官方 SDK 测试: test_edit_image.py

功能：
- 带掩码的图片编辑 (Inpaint/Outpaint)
- 自动掩码编辑 (前景/背景)
- 背景替换
- 风格/主题定制

模型：imagen-3.0-capability-001 (仅 Vertex AI)
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
class EditResult:
    """Edit 结果"""
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mime_type: str = "image/png"
    rai_reason: Optional[str] = None
    error: Optional[str] = None


class MaskEditService:
    """
    掩码编辑服务 (从 tryon_service 拆分)

    使用新版 google-genai SDK 和统一的 client_pool
    仅支持 Vertex AI 模式

    官方 SDK 参考:
    - 模型: imagen-3.0-capability-001, imagen-4.0-ingredients-preview
    - API: client.models.edit_image()
    - 配置: types.EditImageConfig

    编辑模式 (types.EditMode):
    - EDIT_MODE_INPAINT_INSERTION: 插入内容
    - EDIT_MODE_INPAINT_REMOVAL: 移除内容
    - EDIT_MODE_OUTPAINT: 扩展图像
    - EDIT_MODE_BGSWAP: 背景替换

    掩码模式 (mask_mode):
    - MASK_MODE_FOREGROUND: 前景
    - MASK_MODE_BACKGROUND: 背景
    - MASK_MODE_USER_PROVIDED: 用户提供
    """

    # 支持的模型
    SUPPORTED_MODELS = {
        'imagen-3.0-capability-001',  # 标准编辑模型
        'imagen-4.0-ingredients-preview',  # 高级编辑 (多参考图)
    }

    # 编辑模式
    EDIT_MODES = [
        'EDIT_MODE_INPAINT_INSERTION',
        'EDIT_MODE_INPAINT_REMOVAL',
        'EDIT_MODE_OUTPAINT',
        'EDIT_MODE_BGSWAP',
    ]

    # 掩码模式
    MASK_MODES = [
        'MASK_MODE_FOREGROUND',
        'MASK_MODE_BACKGROUND',
        'MASK_MODE_USER_PROVIDED',
    ]

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
                logger.error(f"[MaskEditService] Failed to load config: {e}")
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

        logger.debug(f"[MaskEditService] Got Vertex AI client: project={project_id}, location={location}")
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

    def edit_with_mask(
        self,
        image_base64: str,
        mask_base64: str,
        prompt: str,
        edit_mode: str = "EDIT_MODE_INPAINT_INSERTION",
        mask_dilation: float = 0.06,
        number_of_images: int = 1,
        model: str = "imagen-3.0-capability-001",
        negative_prompt: Optional[str] = None,
        guidance_scale: float = 15.0,
        output_mime_type: str = "image/png",
        output_compression_quality: int = 95,
        safety_filter_level: str = "BLOCK_MEDIUM_AND_ABOVE",
        person_generation: str = "ALLOW_ADULT",
        include_rai_reason: bool = True,
    ) -> EditResult:
        """
        带掩码的图片编辑 - 使用 edit_image API

        Args:
            image_base64: Base64 编码的原图
            mask_base64: Base64 编码的掩码 (白色=编辑区域)
            prompt: 编辑描述
            edit_mode: 编辑模式
            mask_dilation: 掩码膨胀系数 (0.0-1.0)
            number_of_images: 生成数量 (1-4)
            model: 模型 ID
            negative_prompt: 负面提示词
            guidance_scale: 引导比例 (1.0-20.0)
            output_mime_type: 输出格式
            output_compression_quality: JPEG 压缩质量 (1-100)
            safety_filter_level: 安全过滤级别
            person_generation: 人物生成设置
            include_rai_reason: 是否包含 RAI 原因

        Returns:
            EditResult
        """
        try:
            # 验证参数
            if edit_mode not in self.EDIT_MODES:
                return EditResult(
                    success=False,
                    error=f"Invalid edit_mode: {edit_mode}. Must be one of {self.EDIT_MODES}"
                )

            if model not in self.SUPPORTED_MODELS:
                logger.warning(f"[MaskEditService] Model {model} may not be supported")

            # 获取客户端
            client = self._get_vertex_client()

            # 准备图像
            image_bytes = self._base64_to_bytes(image_base64)
            mask_bytes = self._base64_to_bytes(mask_base64)

            prompt_log = f"{prompt[:50]}..." if len(prompt) > 50 else prompt
            logger.info(f"[MaskEditService] Edit with mask: mode={edit_mode}, prompt={prompt_log}")

            # 构建参考图像 (参考官方 SDK test_edit_image.py)
            raw_ref_image = types.RawReferenceImage(
                reference_id=1,
                reference_image=types.Image(image_bytes=image_bytes),
            )

            mask_ref_image = types.MaskReferenceImage(
                reference_id=2,
                reference_image=types.Image(image_bytes=mask_bytes),
                config=types.MaskReferenceConfig(
                    mask_mode='MASK_MODE_USER_PROVIDED',
                    mask_dilation=mask_dilation,
                ),
            )

            # 构建编辑配置
            config_kwargs = {
                "edit_mode": getattr(types.EditMode, edit_mode, types.EditMode.EDIT_MODE_INPAINT_INSERTION),
                "number_of_images": number_of_images,
                "guidance_scale": guidance_scale,
                "safety_filter_level": getattr(types.SafetyFilterLevel, safety_filter_level, types.SafetyFilterLevel.BLOCK_MEDIUM_AND_ABOVE),
                "person_generation": getattr(types.PersonGeneration, person_generation, types.PersonGeneration.ALLOW_ADULT),
                "include_rai_reason": include_rai_reason,
                "output_mime_type": output_mime_type,
                "output_compression_quality": output_compression_quality,
            }

            if negative_prompt:
                config_kwargs["negative_prompt"] = negative_prompt

            config = types.EditImageConfig(**config_kwargs)

            # 调用 edit_image API
            response = client.models.edit_image(
                model=model,
                prompt=prompt,
                reference_images=[raw_ref_image, mask_ref_image],
                config=config,
            )

            if response.generated_images and len(response.generated_images) > 0:
                result_image = response.generated_images[0].image
                result_base64 = self._bytes_to_base64(result_image.image_bytes)

                rai_reason = None
                if hasattr(response.generated_images[0], 'rai_reason'):
                    rai_reason = response.generated_images[0].rai_reason

                logger.info(f"[MaskEditService] Edit with mask successful")
                return EditResult(
                    success=True,
                    image=result_base64,
                    mime_type=output_mime_type,
                    rai_reason=rai_reason
                )
            else:
                return EditResult(success=False, error="No image generated")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[MaskEditService] Edit with mask error: {error_msg}")
            return self._handle_error(error_msg)

    def edit_without_mask(
        self,
        image_base64: str,
        prompt: str,
        edit_mode: str = "EDIT_MODE_INPAINT_INSERTION",
        mask_mode: str = "MASK_MODE_FOREGROUND",
        mask_dilation: float = 0.06,
        number_of_images: int = 1,
        model: str = "imagen-3.0-capability-001",
        **kwargs
    ) -> EditResult:
        """
        无需用户掩码的图片编辑 - 自动生成掩码

        Args:
            image_base64: Base64 编码的原图
            prompt: 编辑描述
            edit_mode: 编辑模式
            mask_mode: 自动掩码模式 (MASK_MODE_FOREGROUND/MASK_MODE_BACKGROUND)
            mask_dilation: 掩码膨胀系数
            number_of_images: 生成数量
            model: 模型 ID
            **kwargs: 其他配置参数

        Returns:
            EditResult
        """
        try:
            # 验证参数
            if edit_mode not in self.EDIT_MODES:
                return EditResult(
                    success=False,
                    error=f"Invalid edit_mode: {edit_mode}. Must be one of {self.EDIT_MODES}"
                )

            if mask_mode not in ['MASK_MODE_FOREGROUND', 'MASK_MODE_BACKGROUND']:
                return EditResult(
                    success=False,
                    error=f"Invalid mask_mode: {mask_mode}. Must be MASK_MODE_FOREGROUND or MASK_MODE_BACKGROUND"
                )

            # 获取客户端
            client = self._get_vertex_client()

            # 准备图像
            image_bytes = self._base64_to_bytes(image_base64)

            prompt_log = f"{prompt[:50]}..." if len(prompt) > 50 else prompt
            logger.info(f"[MaskEditService] Edit (auto-mask): mode={edit_mode}, mask={mask_mode}, prompt={prompt_log}")

            # 构建参考图像 - 只需原图，掩码自动生成
            raw_ref_image = types.RawReferenceImage(
                reference_id=1,
                reference_image=types.Image(image_bytes=image_bytes),
            )

            # 自动掩码配置 (不提供 reference_image)
            mask_ref_image = types.MaskReferenceImage(
                reference_id=2,
                config=types.MaskReferenceConfig(
                    mask_mode=mask_mode,
                    mask_dilation=mask_dilation,
                ),
            )

            # 构建编辑配置
            config_kwargs = {
                "edit_mode": getattr(types.EditMode, edit_mode, types.EditMode.EDIT_MODE_INPAINT_INSERTION),
                "number_of_images": number_of_images,
                "guidance_scale": kwargs.get("guidance_scale", 15.0),
                "safety_filter_level": getattr(
                    types.SafetyFilterLevel,
                    kwargs.get("safety_filter_level", "BLOCK_MEDIUM_AND_ABOVE"),
                    types.SafetyFilterLevel.BLOCK_MEDIUM_AND_ABOVE
                ),
                "person_generation": getattr(
                    types.PersonGeneration,
                    kwargs.get("person_generation", "ALLOW_ADULT"),
                    types.PersonGeneration.ALLOW_ADULT
                ),
                "include_rai_reason": kwargs.get("include_rai_reason", True),
                "output_mime_type": kwargs.get("output_mime_type", "image/png"),
                "output_compression_quality": kwargs.get("output_compression_quality", 95),
            }

            if kwargs.get("negative_prompt"):
                config_kwargs["negative_prompt"] = kwargs["negative_prompt"]

            config = types.EditImageConfig(**config_kwargs)

            # 调用 edit_image API
            response = client.models.edit_image(
                model=model,
                prompt=prompt,
                reference_images=[raw_ref_image, mask_ref_image],
                config=config,
            )

            if response.generated_images and len(response.generated_images) > 0:
                result_image = response.generated_images[0].image
                result_base64 = self._bytes_to_base64(result_image.image_bytes)

                rai_reason = None
                if hasattr(response.generated_images[0], 'rai_reason'):
                    rai_reason = response.generated_images[0].rai_reason

                logger.info(f"[MaskEditService] Edit (auto-mask) successful")
                return EditResult(
                    success=True,
                    image=result_base64,
                    mime_type=kwargs.get("output_mime_type", "image/png"),
                    rai_reason=rai_reason
                )
            else:
                return EditResult(success=False, error="No image generated")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[MaskEditService] Edit (auto-mask) error: {error_msg}")
            return self._handle_error(error_msg)

    def replace_background(
        self,
        image_base64: str,
        prompt: str,
        mask_dilation: float = 0.06,
        number_of_images: int = 1,
        model: str = "imagen-3.0-capability-001",
        **kwargs
    ) -> EditResult:
        """
        背景替换 (便捷方法)

        Args:
            image_base64: Base64 编码的原图
            prompt: 新背景描述
            mask_dilation: 掩码膨胀系数
            number_of_images: 生成数量
            model: 模型 ID
            **kwargs: 其他配置参数

        Returns:
            EditResult
        """
        return self.edit_without_mask(
            image_base64=image_base64,
            prompt=prompt,
            edit_mode="EDIT_MODE_BGSWAP",
            mask_mode="MASK_MODE_BACKGROUND",
            mask_dilation=mask_dilation,
            number_of_images=number_of_images,
            model=model,
            **kwargs
        )

    def inpaint_insertion(
        self,
        image_base64: str,
        mask_base64: str,
        prompt: str,
        model: str = "imagen-3.0-capability-001",
        **kwargs
    ) -> EditResult:
        """
        区域插入 (便捷方法)

        Args:
            image_base64: Base64 编码的原图
            mask_base64: Base64 编码的掩码
            prompt: 插入内容描述
            model: 模型 ID
            **kwargs: 其他配置参数

        Returns:
            EditResult
        """
        return self.edit_with_mask(
            image_base64=image_base64,
            mask_base64=mask_base64,
            prompt=prompt,
            edit_mode="EDIT_MODE_INPAINT_INSERTION",
            model=model,
            **kwargs
        )

    def inpaint_removal(
        self,
        image_base64: str,
        mask_base64: str,
        prompt: str = "Remove the object",
        model: str = "imagen-3.0-capability-001",
        **kwargs
    ) -> EditResult:
        """
        区域移除 (便捷方法)

        Args:
            image_base64: Base64 编码的原图
            mask_base64: Base64 编码的掩码
            prompt: 移除描述
            model: 模型 ID
            **kwargs: 其他配置参数

        Returns:
            EditResult
        """
        return self.edit_with_mask(
            image_base64=image_base64,
            mask_base64=mask_base64,
            prompt=prompt,
            edit_mode="EDIT_MODE_INPAINT_REMOVAL",
            model=model,
            **kwargs
        )

    def _handle_error(self, error_msg: str) -> EditResult:
        """统一的错误处理"""
        error_upper = error_msg.upper()

        if "SAFETY" in error_upper:
            return EditResult(success=False, error="Safety filter triggered. Please modify your prompt or image.")
        elif "QUOTA" in error_upper or "RESOURCE_EXHAUSTED" in error_upper:
            return EditResult(success=False, error="API quota exceeded. Please try again later.")
        elif "PERMISSION" in error_upper or "UNAUTHORIZED" in error_upper:
            return EditResult(success=False, error="Authentication error. Please check GCP credentials.")
        elif "only supported in the Vertex AI client" in error_msg.lower():
            return EditResult(success=False, error="This feature requires Vertex AI mode. Please configure GCP credentials.")
        else:
            return EditResult(success=False, error=error_msg)

    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return list(self.SUPPORTED_MODELS)

    def get_capabilities(self) -> Dict[str, Any]:
        """获取编辑功能的能力说明"""
        return {
            "edit_modes": self.EDIT_MODES,
            "mask_modes": self.MASK_MODES,
            "supported_models": list(self.SUPPORTED_MODELS),
            "mode_descriptions": {
                "EDIT_MODE_INPAINT_INSERTION": "Insert content into masked area",
                "EDIT_MODE_INPAINT_REMOVAL": "Remove content from masked area",
                "EDIT_MODE_OUTPAINT": "Extend image beyond boundaries",
                "EDIT_MODE_BGSWAP": "Replace background"
            },
            "config_options": {
                "mask_dilation": "Mask dilation factor (0.0-1.0)",
                "guidance_scale": "Guidance scale (1.0-20.0)",
                "negative_prompt": "Negative prompt for content to avoid",
                "number_of_images": "Number of images to generate (1-4)"
            }
        }


# 单例实例
mask_edit_service = MaskEditService()
