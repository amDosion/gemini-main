"""
Image Segmentation Service (google-genai 版)

使用新版推荐的 google-genai SDK：
- client.models.segment_image() 方法
- 通过 client_pool 管理客户端（每用户独立）
- 仅支持 Vertex AI 模式

官方参考：
- SDK: https://github.com/googleapis/python-genai
- Model: image-segmentation-001 (仅 Vertex AI)
- 需要在 Model Garden 申请访问权限

功能：图片分割 (前景/背景/提示词/语义/交互式)
"""

import logging
import base64
import json
import io
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

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
    图片分割服务 (google-genai 版)

    使用新版 google-genai SDK 的 client.models.segment_image() 方法
    通过 client_pool 管理客户端，每用户独立

    官方 SDK 参考 (python-genai):
    - 模型: image-segmentation-001
    - API: client.models.segment_image()
    - 配置: types.SegmentImageConfig, types.SegmentImageSource
    - 注意: 只支持 Vertex AI client

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

    def __init__(self, user_id: Optional[str] = None, db: Optional[Session] = None):
        """
        初始化 SegmentationService

        使用 client_pool 管理客户端（参考其他服务如 ImagenCoordinator）

        Args:
            user_id: 用户 ID（用于从数据库获取 Vertex AI 配置）
            db: 数据库会话（SQLAlchemy Session）

        配置获取优先级：
        1. 从数据库获取用户的 VertexAIConfig（如果有 user_id 和 db）
        2. 回退到环境变量
        """
        self._user_id = user_id
        self._db = db
        self._config: Optional[Dict[str, Any]] = None
        self._client = None

        logger.info(f"[SegmentationService] Initialized with user_id={user_id if user_id else 'None'}")

    def _load_config(self) -> Dict[str, Any]:
        """
        从数据库或环境变量加载配置（遵循 ImagenCoordinator 的模式）

        Returns:
            配置字典，包含：
            - project_id: GCP 项目 ID
            - location: GCP 区域
            - credentials: service_account.Credentials 对象（如果有）
        """
        if self._config:
            return self._config

        config = {}

        # 尝试从数据库加载（如果有 user_id 和 db）
        if self._user_id and self._db:
            try:
                from ....models.db_models import VertexAIConfig
                from ....core.encryption import decrypt_data

                user_config = self._db.query(VertexAIConfig).filter(
                    VertexAIConfig.user_id == self._user_id
                ).first()

                if user_config and user_config.api_mode == 'vertex_ai':
                    logger.info(f"[SegmentationService] Using Vertex AI config from database for user={self._user_id}")

                    config['project_id'] = user_config.vertex_ai_project_id
                    config['location'] = user_config.vertex_ai_location or 'us-central1'

                    # 解密 credentials JSON（如果有）
                    if user_config.vertex_ai_credentials_json:
                        try:
                            credentials_json = decrypt_data(user_config.vertex_ai_credentials_json)

                            # 创建 credentials 对象
                            from google.oauth2 import service_account
                            credentials_info = json.loads(credentials_json)
                            credentials = service_account.Credentials.from_service_account_info(
                                credentials_info,
                                scopes=['https://www.googleapis.com/auth/cloud-platform']
                            )
                            config['credentials'] = credentials
                            logger.info(f"[SegmentationService] Successfully loaded Vertex AI credentials from database")
                        except Exception as e:
                            logger.error(f"[SegmentationService] Failed to decrypt/parse credentials: {e}")

                    self._config = config
                    return config
                else:
                    logger.info(f"[SegmentationService] No Vertex AI config in database for user={self._user_id}, falling back to environment")
            except Exception as e:
                logger.warning(f"[SegmentationService] Failed to load config from database: {e}")

        # 回退到环境变量
        try:
            from ....core.config import settings
            config['project_id'] = settings.gcp_project_id
            config['location'] = settings.gcp_location or 'us-central1'
            logger.info(f"[SegmentationService] Using config from environment variables")
        except Exception as e:
            logger.error(f"[SegmentationService] Failed to load config from environment: {e}")
            raise ValueError("GCP configuration not available")

        if not config.get('project_id'):
            raise ValueError("GCP_PROJECT_ID not configured (neither in database nor environment)")

        self._config = config
        return config

    def _get_client(self):
        """
        通过 client_pool 获取 Vertex AI 客户端

        Returns:
            google.genai.Client (底层客户端，支持 segment_image)
        """
        if self._client:
            return self._client

        config = self._load_config()
        project_id = config.get('project_id')
        location = config.get('location', 'us-central1')
        credentials = config.get('credentials')

        if not project_id:
            raise ValueError("GCP project_id is required for Vertex AI mode")

        if not credentials:
            raise ValueError(
                "Vertex AI credentials are required. Please configure Vertex AI credentials in settings."
            )

        # 使用 client_pool 获取客户端
        from ..client_pool import get_client_pool
        pool = get_client_pool()

        # 获取 Vertex AI 客户端（包装器）
        wrapper_client = pool.get_client(
            vertexai=True,
            project=project_id,
            location=location,
            credentials=credentials
        )

        # 获取底层的 google.genai.Client（支持 segment_image）
        if hasattr(wrapper_client, '_genai_client'):
            self._client = wrapper_client._genai_client
            logger.info(f"[SegmentationService] Got underlying genai client from pool")
        else:
            # 如果包装器没有 _genai_client，可能是直接的 genai.Client
            self._client = wrapper_client
            logger.info(f"[SegmentationService] Using client directly from pool")

        return self._client

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
        图片分割 - 使用 google-genai SDK 的 client.models.segment_image()

        官方参考：https://github.com/googleapis/python-genai

        Args:
            image_base64: Base64 编码的原图
            mode: 分割模式 (FOREGROUND, BACKGROUND, PROMPT, SEMANTIC, INTERACTIVE)
            prompt: 分割提示词 (PROMPT/SEMANTIC 模式需要)
            scribble_image_base64: 涂鸦图像 (INTERACTIVE 模式需要)
            model: 模型 ID
            max_predictions: 最大预测数量
            confidence_threshold: 置信度阈值 (0.0-1.0)
            mask_dilation: 掩码膨胀系数 (0.0-1.0)
            binary_color_threshold: 二值化阈值 (0-255), -1 表示返回灰度 "soft" mask

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

            # 获取 google.genai.Client
            client = self._get_client()

            # 导入 google.genai types
            from google.genai import types

            # 准备图像
            image_bytes = self._base64_to_bytes(image_base64)
            source_image = types.Image(image_bytes=image_bytes)

            # 准备 source（包含图像、提示词、涂鸦图像）
            source_kwargs = {"image": source_image}

            if prompt and mode in ['PROMPT', 'SEMANTIC']:
                source_kwargs["prompt"] = prompt

            if scribble_image_base64 and mode == 'INTERACTIVE':
                scribble_bytes = self._base64_to_bytes(scribble_image_base64)
                scribble_image = types.Image(image_bytes=scribble_bytes)
                source_kwargs["scribble_image"] = types.ScribbleImage(image=scribble_image)

            source = types.SegmentImageSource(**source_kwargs)

            # 准备 config
            # 转换模式字符串为 SegmentMode 枚举
            segment_mode = getattr(types.SegmentMode, mode, types.SegmentMode.FOREGROUND)

            config = types.SegmentImageConfig(
                mode=segment_mode,
                max_predictions=max_predictions,
                confidence_threshold=confidence_threshold,
                mask_dilation=mask_dilation,
                binary_color_threshold=binary_color_threshold,
            )

            logger.info(f"[SegmentationService] Calling segment_image: model={model}, mode={mode}, prompt={prompt}")

            # 调用 segment_image API
            response = client.models.segment_image(
                model=model,
                source=source,
                config=config,
            )

            # 处理结果
            masks = []
            if response.generated_masks and len(response.generated_masks) > 0:
                for mask_result in response.generated_masks:
                    # 获取 mask 图像
                    mask_image = mask_result.mask
                    if mask_image:
                        # 获取图像字节
                        if hasattr(mask_image, 'image_bytes') and mask_image.image_bytes:
                            mask_base64 = self._bytes_to_base64(mask_image.image_bytes)
                        elif hasattr(mask_image, '_pil_image') and mask_image._pil_image:
                            # 将 PIL Image 转换为字节
                            img_byte_arr = io.BytesIO()
                            mask_image._pil_image.save(img_byte_arr, format='PNG')
                            mask_bytes = img_byte_arr.getvalue()
                            mask_base64 = self._bytes_to_base64(mask_bytes)
                        else:
                            continue

                        # 提取标签
                        labels = []
                        if hasattr(mask_result, 'labels') and mask_result.labels:
                            for label_info in mask_result.labels:
                                labels.append(SegmentLabel(
                                    label=getattr(label_info, 'label', mode.lower()),
                                    score=float(getattr(label_info, 'score', 1.0))
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
        error_lower = error_msg.lower()

        if "SAFETY" in error_upper:
            return SegmentResult(success=False, error="Safety filter triggered. Please use a different image.")
        elif "QUOTA" in error_upper or "RESOURCE_EXHAUSTED" in error_upper:
            return SegmentResult(success=False, error="API quota exceeded. Please try again later.")
        elif "PERMISSION" in error_upper or "UNAUTHORIZED" in error_upper:
            return SegmentResult(success=False, error="Authentication error. Please check GCP credentials.")
        elif "only supported in the Vertex AI client" in error_lower:
            return SegmentResult(success=False, error="This feature requires Vertex AI mode. Please configure GCP credentials.")
        elif "404" in error_msg or "NOT_FOUND" in error_upper:
            # 404 错误通常表示模型没有访问权限
            return SegmentResult(
                success=False,
                error=(
                    "Model access denied (404). Please request access to 'image-segmentation-001' model "
                    "at: https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/image-segmentation-001"
                )
            )
        elif "deprecated" in error_lower:
            # 废弃警告（但仍可使用到 2026-06-24）
            logger.warning(
                "[SegmentationService] Image Segmentation feature is deprecated (June 24, 2025) "
                "and will be removed on June 24, 2026."
            )
            return SegmentResult(success=False, error=error_msg)
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
