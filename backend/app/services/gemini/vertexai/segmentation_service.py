"""
Image Segmentation Service (重构版)

使用新版 google-genai SDK，通过 client_pool 统一管理客户端
基于官方 SDK 测试: test_segment_image.py

功能：图片分割 (前景/背景/提示词/语义/交互式)
模型：image-segmentation-001 (仅 Vertex AI)
"""

import logging
import base64
import io
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from google.genai import types

from ..client_pool import get_client_pool

logger = logging.getLogger(__name__)


@dataclass
class SegmentLabel:
    """分割标签"""
    label: str
    score: float


@dataclass
class SegmentMask:
    """分割掩码"""
    mask: str  # Base64 编码的掩码图像
    labels: List[SegmentLabel] = field(default_factory=list)


@dataclass
class SegmentResult:
    """Segmentation 结果"""
    success: bool
    masks: List[SegmentMask] = field(default_factory=list)
    error: Optional[str] = None


class SegmentationService:
    """
    图片分割服务 (重构版)

    使用新版 google-genai SDK 和统一的 client_pool
    仅支持 Vertex AI 模式

    官方 SDK 参考:
    - 模型: image-segmentation-001
    - API: client.models.segment_image()
    - 配置: types.SegmentImageConfig, types.SegmentImageSource

    支持的分割模式 (types.SegmentMode):
    - FOREGROUND: 前景分割
    - BACKGROUND: 背景分割
    - PROMPT: 基于提示词分割
    - SEMANTIC: 语义分割
    - INTERACTIVE: 交互式分割 (需要 scribble_image)
    """

    # 支持的模型
    SUPPORTED_MODELS = {
        'image-segmentation-001',  # 官方推荐
    }

    # 支持的分割模式
    SEGMENT_MODES = [
        'FOREGROUND',
        'BACKGROUND',
        'PROMPT',
        'SEMANTIC',
        'INTERACTIVE',
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
                logger.error(f"[SegmentationService] Failed to load config: {e}")
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

        logger.debug(f"[SegmentationService] Got Vertex AI client: project={project_id}, location={location}")
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

    def segment_image(
        self,
        image_base64: str,
        mode: str = "FOREGROUND",
        prompt: Optional[str] = None,
        scribble_image_base64: Optional[str] = None,
        model: str = "image-segmentation-001",
        max_predictions: int = 5,
        confidence_threshold: float = 0.02,
        mask_dilation: float = 0.02,
        binary_color_threshold: int = 98,
    ) -> SegmentResult:
        """
        图片分割 - 使用 segment_image API

        Args:
            image_base64: Base64 编码的原图
            mode: 分割模式 (FOREGROUND, BACKGROUND, PROMPT, SEMANTIC, INTERACTIVE)
            prompt: 分割提示词 (PROMPT/SEMANTIC 模式需要)
            scribble_image_base64: 涂鸦图像 (INTERACTIVE 模式需要)
            model: 模型 ID
            max_predictions: 最大预测数量
            confidence_threshold: 置信度阈值 (0.0-1.0)
            mask_dilation: 掩码膨胀系数 (0.0-1.0)
            binary_color_threshold: 二值化阈值 (0-255)

        Returns:
            SegmentResult
        """
        try:
            # 验证参数
            if mode not in self.SEGMENT_MODES:
                return SegmentResult(
                    success=False,
                    error=f"Invalid mode: {mode}. Must be one of {self.SEGMENT_MODES}"
                )

            if mode in ['PROMPT', 'SEMANTIC'] and not prompt:
                return SegmentResult(
                    success=False,
                    error=f"Mode {mode} requires a prompt"
                )

            if mode == 'INTERACTIVE' and not scribble_image_base64:
                return SegmentResult(
                    success=False,
                    error="INTERACTIVE mode requires scribble_image_base64"
                )

            if model not in self.SUPPORTED_MODELS:
                logger.warning(f"[SegmentationService] Model {model} may not be supported")

            # 获取客户端
            client = self._get_vertex_client()

            # 准备图像
            image_bytes = self._base64_to_bytes(image_base64)

            logger.info(f"[SegmentationService] Segment: mode={mode}, prompt={prompt}")

            # 构建 source (参考官方 SDK test_segment_image.py)
            source_kwargs = {
                "image": types.Image(image_bytes=image_bytes),
            }

            if prompt and mode in ['PROMPT', 'SEMANTIC']:
                source_kwargs["prompt"] = prompt

            if scribble_image_base64 and mode == 'INTERACTIVE':
                scribble_bytes = self._base64_to_bytes(scribble_image_base64)
                source_kwargs["scribble_image"] = types.ScribbleImage(
                    image=types.Image(image_bytes=scribble_bytes)
                )

            source = types.SegmentImageSource(**source_kwargs)

            # 构建配置
            segment_mode = getattr(types.SegmentMode, mode, types.SegmentMode.FOREGROUND)
            config = types.SegmentImageConfig(
                mode=segment_mode,
                max_predictions=max_predictions,
                confidence_threshold=confidence_threshold,
                mask_dilation=mask_dilation,
                binary_color_threshold=binary_color_threshold,
            )

            # 调用 segment_image API
            response = client.models.segment_image(
                model=model,
                source=source,
                config=config,
            )

            # 处理结果
            masks = []
            if response.generated_masks and len(response.generated_masks) > 0:
                for generated_mask in response.generated_masks:
                    if generated_mask.mask and generated_mask.mask.image_bytes:
                        mask_base64 = self._bytes_to_base64(generated_mask.mask.image_bytes)

                        # 提取标签
                        labels = []
                        if hasattr(generated_mask, 'labels') and generated_mask.labels:
                            for label_info in generated_mask.labels:
                                labels.append(SegmentLabel(
                                    label=getattr(label_info, 'label', mode.lower()),
                                    score=getattr(label_info, 'score', 1.0)
                                ))

                        masks.append(SegmentMask(
                            mask=mask_base64,
                            labels=labels if labels else [SegmentLabel(label=mode.lower(), score=1.0)]
                        ))

                logger.info(f"[SegmentationService] Segmentation successful: {len(masks)} masks")
                return SegmentResult(success=True, masks=masks)
            else:
                return SegmentResult(success=False, error="No segmentation result")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[SegmentationService] Segmentation error: {error_msg}")
            return self._handle_error(error_msg)

    def segment_foreground(
        self,
        image_base64: str,
        model: str = "image-segmentation-001",
        **kwargs
    ) -> SegmentResult:
        """前景分割 (便捷方法)"""
        return self.segment_image(
            image_base64=image_base64,
            mode="FOREGROUND",
            model=model,
            **kwargs
        )

    def segment_background(
        self,
        image_base64: str,
        model: str = "image-segmentation-001",
        **kwargs
    ) -> SegmentResult:
        """背景分割 (便捷方法)"""
        return self.segment_image(
            image_base64=image_base64,
            mode="BACKGROUND",
            model=model,
            **kwargs
        )

    def segment_by_prompt(
        self,
        image_base64: str,
        prompt: str,
        model: str = "image-segmentation-001",
        **kwargs
    ) -> SegmentResult:
        """基于提示词分割 (便捷方法)"""
        return self.segment_image(
            image_base64=image_base64,
            mode="PROMPT",
            prompt=prompt,
            model=model,
            **kwargs
        )

    def segment_semantic(
        self,
        image_base64: str,
        prompt: str,
        model: str = "image-segmentation-001",
        **kwargs
    ) -> SegmentResult:
        """语义分割 (便捷方法)"""
        return self.segment_image(
            image_base64=image_base64,
            mode="SEMANTIC",
            prompt=prompt,
            model=model,
            **kwargs
        )

    def segment_interactive(
        self,
        image_base64: str,
        scribble_image_base64: str,
        model: str = "image-segmentation-001",
        **kwargs
    ) -> SegmentResult:
        """交互式分割 (便捷方法)"""
        return self.segment_image(
            image_base64=image_base64,
            mode="INTERACTIVE",
            scribble_image_base64=scribble_image_base64,
            model=model,
            **kwargs
        )

    def segment_image_from_path(
        self,
        image_path: str,
        mode: str = "FOREGROUND",
        model: str = "image-segmentation-001",
        **kwargs
    ) -> SegmentResult:
        """
        从文件路径分割图片 (兼容旧接口)

        Args:
            image_path: 图片文件路径
            mode: 分割模式
            model: 模型 ID
            **kwargs: 其他参数

        Returns:
            SegmentResult
        """
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            image_base64 = self._bytes_to_base64(image_bytes)
            return self.segment_image(
                image_base64=image_base64,
                mode=mode,
                model=model,
                **kwargs
            )
        except Exception as e:
            return SegmentResult(success=False, error=f"Failed to read image: {str(e)}")

    def _handle_error(self, error_msg: str) -> SegmentResult:
        """统一的错误处理"""
        error_upper = error_msg.upper()

        if "SAFETY" in error_upper:
            return SegmentResult(success=False, error="Safety filter triggered. Please use a different image.")
        elif "QUOTA" in error_upper or "RESOURCE_EXHAUSTED" in error_upper:
            return SegmentResult(success=False, error="API quota exceeded. Please try again later.")
        elif "PERMISSION" in error_upper or "UNAUTHORIZED" in error_upper:
            return SegmentResult(success=False, error="Authentication error. Please check GCP credentials.")
        elif "only supported in the Vertex AI client" in error_msg.lower():
            return SegmentResult(success=False, error="This feature requires Vertex AI mode. Please configure GCP credentials.")
        else:
            return SegmentResult(success=False, error=error_msg)

    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return list(self.SUPPORTED_MODELS)

    def get_capabilities(self) -> Dict[str, Any]:
        """获取分割功能的能力说明"""
        return {
            "modes": self.SEGMENT_MODES,
            "supported_models": list(self.SUPPORTED_MODELS),
            "mode_descriptions": {
                "FOREGROUND": "Segment the foreground objects",
                "BACKGROUND": "Segment the background",
                "PROMPT": "Segment based on text prompt",
                "SEMANTIC": "Semantic segmentation with class labels",
                "INTERACTIVE": "Interactive segmentation with scribble guidance"
            },
            "config_options": {
                "max_predictions": "Maximum number of predictions",
                "confidence_threshold": "Confidence threshold (0.0-1.0)",
                "mask_dilation": "Mask dilation factor (0.0-1.0)",
                "binary_color_threshold": "Binary color threshold (0-255)"
            }
        }


# 单例实例
segmentation_service = SegmentationService()
