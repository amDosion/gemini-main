"""
Mask Edit Service (掩码编辑服务)

使用 Vertex AI edit_image API 进行带掩码的图片编辑。
统一有状态接口模式：构造函数绑定凭据，与 gen 模式一致。

功能：
- 带掩码的图片编辑 (Inpaint/Outpaint)
- 自动掩码编辑 (前景/背景)
- 背景替换

模型：imagen-3.0-capability-001, imagen-4.0-ingredients-preview (仅 Vertex AI)

路由：
- image-mask-edit → ImageEditCoordinator → MaskEditService.edit_image()

架构：
  MaskEditService 是 VertexAIEditBase 的薄包装器，仅设置掩码编辑相关的默认值，
  然后委托给基类的 edit_image() 共享管线（_build_config → _build_reference_images → _process_response）。
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .vertex_edit_base import VertexAIEditBase

logger = logging.getLogger(__name__)


@dataclass
class EditResult:
    """Edit 结果 (向后兼容，内部不再使用)"""
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mime_type: str = "image/png"
    rai_reason: Optional[str] = None
    error: Optional[str] = None


class MaskEditService(VertexAIEditBase):
    """
    掩码编辑服务

    继承 VertexAIEditBase，使用统一的共享管线：
    - 构造函数: __init__(project_id, location, credentials_json)
    - 接口: edit_image(prompt, reference_images, config) -> List[Dict[str, Any]]

    本服务仅设置掩码编辑的默认参数，然后委托给基类的 edit_image()：
    - guidance_scale: 15.0
    - output_mime_type: image/png
    - output_compression_quality: 95
    - safety_filter_level: BLOCK_MEDIUM_AND_ABOVE
    - person_generation: ALLOW_ADULT
    - 无用户掩码时自动使用 MASK_MODE_FOREGROUND

    支持的编辑模式 (types.EditMode):
    - EDIT_MODE_INPAINT_INSERTION: 插入内容
    - EDIT_MODE_INPAINT_REMOVAL: 移除内容
    - EDIT_MODE_OUTPAINT: 扩展图像
    - EDIT_MODE_BGSWAP: 背景替换

    掩码模式 (mask_mode):
    - MASK_MODE_FOREGROUND: 前景
    - MASK_MODE_BACKGROUND: 背景
    - MASK_MODE_USER_PROVIDED: 用户提供 (通过 reference_images['mask'])
    """

    # 默认编辑模式 → EDIT_MODE_INPAINT_INSERTION
    DEFAULT_EDIT_MODE = 'mask_edit'

    # 支持的模型
    SUPPORTED_MODELS = {
        'imagen-3.0-capability-001',
        'imagen-4.0-ingredients-preview',
    }

    # 编辑模式列表
    EDIT_MODES = [
        'EDIT_MODE_INPAINT_INSERTION',
        'EDIT_MODE_INPAINT_REMOVAL',
        'EDIT_MODE_OUTPAINT',
        'EDIT_MODE_BGSWAP',
    ]

    # 掩码模式列表
    MASK_MODES = [
        'MASK_MODE_FOREGROUND',
        'MASK_MODE_BACKGROUND',
        'MASK_MODE_USER_PROVIDED',
    ]

    def edit_image(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        掩码编辑接口（薄包装器）

        设置掩码编辑特有的默认参数，然后委托给基类的 edit_image()。
        基类负责完整的共享管线：
        _build_config → _build_reference_images → API 调用 → _process_response

        Args:
            prompt: 编辑描述
            reference_images: 参考图片字典
                必需: 'raw' (原图 Base64)
                可选: 'mask' (掩码 Base64，提供时使用 MASK_MODE_USER_PROVIDED)
            config: 配置字典
                - editMode/edit_mode: 编辑模式 (默认 EDIT_MODE_INPAINT_INSERTION)
                - maskMode/mask_mode: 自动掩码模式 (默认 MASK_MODE_FOREGROUND)
                - maskDilation/mask_dilation: 掩码膨胀系数 (默认 0.06)
                - model: 模型 ID
                - number_of_images/numberOfImages: 生成数量
                - negativePrompt/negative_prompt: 负面提示词
                - guidance_scale: 引导比例 (默认 15.0)
                - output_mime_type: 输出格式 (默认 image/png)
                - output_compression_quality: 压缩质量 (默认 95)
                - safety_filter_level: 安全过滤级别 (默认 BLOCK_MEDIUM_AND_ABOVE)
                - person_generation: 人物生成设置 (默认 ALLOW_ADULT)

        Returns:
            List[Dict[str, Any]] — 与所有服务统一的返回格式
        """
        # Validate raw image is present
        raw = reference_images.get('raw')
        if not raw:
            raise ValueError("mask edit requires 'raw' image in reference_images")

        # ── Step 1: Normalize camelCase → snake_case ──
        # Must normalize BEFORE setdefault(), otherwise snake_case defaults
        # shadow frontend camelCase values (e.g. guidanceScale: 20 ignored because
        # setdefault('guidance_scale', 15.0) runs first and _build_config prefers snake_case).
        effective_config = self._normalize_config(config or {})

        # ── Step 2: Mask-edit specific defaults (only applied if not set by frontend) ──
        effective_config.setdefault('guidance_scale', 15.0)
        effective_config.setdefault('output_mime_type', 'image/png')
        effective_config.setdefault('output_compression_quality', 95)
        effective_config.setdefault('safety_filter_level', 'block_some')
        effective_config.setdefault('person_generation', 'allow_adult')

        # Auto-mask: if no user mask provided and no mask_mode specified, default to FOREGROUND
        has_mask = 'mask' in reference_images and reference_images.get('mask')
        if not has_mask:
            if not effective_config.get('mask_mode'):
                effective_config['mask_mode'] = 'MASK_MODE_FOREGROUND'

        logger.info(
            f"[MaskEditService] edit_image(): has_mask={has_mask}, "
            f"edit_mode={effective_config.get('edit_mode') or effective_config.get('editMode') or self.DEFAULT_EDIT_MODE}"
        )

        # Delegate to base class shared pipeline
        return super().edit_image(prompt, reference_images, effective_config)

    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return list(self.SUPPORTED_MODELS)

    def get_capabilities(self) -> Dict[str, Any]:
        """获取掩码编辑功能的能力说明"""
        return {
            'api_type': 'vertex_ai',
            'supports_editing': True,
            "edit_modes": self.EDIT_MODES,
            "mask_modes": self.MASK_MODES,
            "supported_models": list(self.SUPPORTED_MODELS),
            "mode_descriptions": {
                "EDIT_MODE_INPAINT_INSERTION": "Insert content into masked area",
                "EDIT_MODE_INPAINT_REMOVAL": "Remove content from masked area",
                "EDIT_MODE_OUTPAINT": "Extend image beyond boundaries",
                "EDIT_MODE_BGSWAP": "Replace background"
            },
        }
