"""
Image Expand Service (重构版)

Handles image expansion (outpainting) and upscaling using Imagen models.
Based on official Google GenAI SDK.

功能：
1. Outpaint (扩图) - 使用 imagen-3.0-capability-001
2. Upscale (放大) - 使用 imagen-4.0-upscale-preview
"""

import logging
import base64
import os
import io
import json
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union

import aiohttp

from ..common.sdk_initializer import SDKInitializer
from ..common.parameter_validation import ImageServiceValidator

logger = logging.getLogger(__name__)

# 使用新版 google-genai SDK
try:
    from google.genai import types as genai_types
    GENAI_TYPES_AVAILABLE = True
except ImportError:
    GENAI_TYPES_AVAILABLE = False

# PIL for image manipulation
try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ExpandService:
    """
    Handles image expansion (outpainting) functionality.

    Supports various expansion modes:
    - Scale mode: Expand by scale factors
    - Offset mode: Expand by pixel offsets
    - Ratio mode: Expand to specific aspect ratios

    Note: Outpainting 需要 Vertex AI 模式，因为 Gemini API 不支持 EDIT_MODE_OUTPAINT
    """

    def __init__(
        self,
        sdk_initializer: Optional[SDKInitializer] = None,
        user_id: Optional[str] = None,
        db = None
    ):
        """
        Initialize expand service.

        支持两种初始化模式：
        1. 传递 sdk_initializer（向后兼容，但可能不支持 outpainting）
        2. 传递 user_id 和 db（推荐，支持从数据库加载 Vertex AI 配置）

        Args:
            sdk_initializer: SDK initializer instance (可选，向后兼容)
            user_id: 用户 ID（用于从数据库获取 Vertex AI 配置）
            db: 数据库会话（SQLAlchemy Session）
        """
        self.sdk_initializer = sdk_initializer
        self._user_id = user_id
        self._db = db
        self._config: Optional[Dict[str, Any]] = None
        self._vertex_client = None  # Vertex AI 客户端
        self.validator = ImageServiceValidator("Expand Service")

        logger.info(f"[Expand Service] Initialized with user_id={user_id if user_id else 'None'}")

        # ========================================
        # 模型配置
        # ========================================

        # Outpaint/Edit 专用模型 (官方 SDK: imagen-3.0-capability-001)
        self.edit_models = {
            'imagen-3.0-capability-001',  # ✅ 官方编辑模型（推荐）
        }

        # Upscale 专用模型
        self.upscale_models = {
            'imagen-4.0-upscale-preview',  # ✅ 官方放大模型
        }

        # 生成模型（兼容旧代码，但不推荐用于 outpaint）
        self.expand_models = {
            'imagen-3.0-capability-001',  # ✅ 推荐用于 outpaint
            'imagen-4.0-generate-001',  # 生成模型（可能不支持 outpaint）
            'imagen-4.0-ultra-generate-001',
            'imagen-4.0-fast-generate-001',
        }

        # Upscale 配置
        self.VALID_UPSCALE_FACTORS = ['x2', 'x3', 'x4']
        self.MAX_OUTPUT_MEGAPIXELS = 17

    def _load_config(self) -> Dict[str, Any]:
        """
        从数据库或环境变量加载 Vertex AI 配置（遵循 SegmentationService 的模式）

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
                    logger.info(f"[Expand Service] Using Vertex AI config from database for user={self._user_id}")

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
                            logger.info(f"[Expand Service] Successfully loaded Vertex AI credentials from database")
                        except Exception as e:
                            logger.error(f"[Expand Service] Failed to decrypt/parse credentials: {e}")

                    self._config = config
                    return config
                else:
                    logger.info(f"[Expand Service] No Vertex AI config in database for user={self._user_id if self._user_id else 'None'}, falling back to environment")
            except Exception as e:
                logger.warning(f"[Expand Service] Failed to load config from database: {e}")

        # 回退到环境变量
        try:
            from ....core.config import settings
            config['project_id'] = settings.gcp_project_id
            config['location'] = settings.gcp_location or 'us-central1'
            logger.info(f"[Expand Service] Using config from environment variables")
        except Exception as e:
            logger.error(f"[Expand Service] Failed to load config from environment: {e}")
            raise ValueError("GCP configuration not available")

        if not config.get('project_id'):
            raise ValueError("GCP_PROJECT_ID not configured (neither in database nor environment)")

        self._config = config
        return config

    def _get_vertex_client(self):
        """
        获取 Vertex AI 客户端（用于 outpainting 等需要 Vertex AI 的操作）

        Returns:
            google.genai.Client (Vertex AI 模式)
        """
        if self._vertex_client:
            return self._vertex_client

        config = self._load_config()
        project_id = config.get('project_id')
        location = config.get('location', 'us-central1')
        credentials = config.get('credentials')

        if not project_id:
            raise ValueError("GCP project_id is required for Vertex AI mode (outpainting)")

        if not credentials:
            raise ValueError(
                "Vertex AI credentials are required for outpainting. "
                "Please configure Vertex AI credentials in settings."
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

        # 获取底层的 google.genai.Client（支持 edit_image）
        if hasattr(wrapper_client, '_genai_client'):
            self._vertex_client = wrapper_client._genai_client
            logger.info(f"[Expand Service] Got underlying Vertex AI genai client from pool")
        else:
            # 如果包装器没有 _genai_client，可能是直接的 genai.Client
            self._vertex_client = wrapper_client
            logger.info(f"[Expand Service] Using Vertex AI client directly from pool")

        return self._vertex_client

    def _extract_image_path(self, reference_images: Optional[Dict[str, Any]], **kwargs) -> str:
        """
        从 reference_images 或 kwargs 中提取图片路径

        Args:
            reference_images: 参考图片字典 {'raw': image_path or image_url or dict}
            **kwargs: 额外参数（可能包含 image_path）

        Returns:
            图片路径或 URL
        """
        image_path = None

        if reference_images:
            raw_data = reference_images.get("raw")
            # ✅ 处理字典格式（modes.py 传递的新格式：{'url': ..., 'attachment_id': ...}）
            if isinstance(raw_data, dict):
                image_path = raw_data.get("url")
                logger.info(f"[Expand Service] Extracted image_path from dict format, attachment_id={raw_data.get('attachment_id')}")
            elif isinstance(raw_data, str):
                image_path = raw_data
            elif isinstance(raw_data, list) and len(raw_data) > 0:
                # 处理多图情况，取第一张
                first_item = raw_data[0]
                if isinstance(first_item, dict):
                    image_path = first_item.get("url")
                else:
                    image_path = first_item

        # 从 kwargs 中获取（兼容旧接口）
        if not image_path:
            image_path = kwargs.get("image_path")

        if not image_path:
            raise ValueError("expand_image requires 'raw' image in reference_images or 'image_path' in kwargs")

        return image_path

    async def _load_image_from_path(self, image_path: str) -> Tuple[bytes, str]:
        """
        从各种路径格式加载图片字节

        支持的格式：
        - data: base64 编码
        - http:// 或 https:// URL（使用 aiohttp 下载）
        - 本地文件路径

        Args:
            image_path: 图片路径或 URL

        Returns:
            (image_bytes, mime_type)
        """
        if image_path.startswith('data:'):
            # Base64 编码: data:image/png;base64,xxxxx
            if ',' in image_path:
                header, b64_data = image_path.split(',', 1)
                # 提取 mime_type: data:image/png;base64 -> image/png
                mime_type = header.replace('data:', '').split(';')[0] if ';' in header else 'image/png'
            else:
                b64_data = image_path
                mime_type = 'image/png'
            image_bytes = base64.b64decode(b64_data)
            return image_bytes, mime_type

        elif image_path.startswith('http://') or image_path.startswith('https://'):
            # HTTP URL：需要下载图片（参考 ConversationalImageEditService.send_edit_message）
            logger.info(f"[Expand Service] 下载 HTTP URL 图片: {image_path[:60]}...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_path, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            image_bytes = await response.read()
                            mime_type = response.headers.get('Content-Type', 'image/png')
                            # 清理 mime_type（可能包含 charset 等额外信息）
                            if ';' in mime_type:
                                mime_type = mime_type.split(';')[0].strip()
                            logger.info(f"[Expand Service] ✅ HTTP URL 下载成功，大小: {len(image_bytes)} bytes, mime_type: {mime_type}")
                            return image_bytes, mime_type
                        else:
                            raise ValueError(f"HTTP {response.status}: Failed to download image from {image_path[:60]}...")
            except aiohttp.ClientError as e:
                logger.error(f"[Expand Service] ❌ HTTP URL 下载失败: {e}")
                raise ValueError(f"Failed to download image from URL: {str(e)}")

        else:
            # 本地文件路径
            if not os.path.exists(image_path):
                raise ValueError(f"Image file not found: {image_path}")
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            # 根据扩展名推断 mime_type
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp'}
            mime_type = mime_map.get(ext, 'image/png')
            return image_bytes, mime_type

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
        
        expand_prompt = kwargs.pop("expand_prompt", prompt)  # ✅ 使用 pop 避免重复传递
        mode = kwargs.pop("mode", "scale")  # ✅ 使用 pop 避免重复传递

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
            elif mode == "upscale":
                mode_params = f"upscale_factor={kwargs.get('upscale_factor', 'x2')}"
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
            elif mode == "upscale":
                # 调用 upscale_image 方法
                upscale_factor = kwargs.get('upscale_factor', 'x2')
                upscale_model = kwargs.get('upscale_model', 'imagen-4.0-upscale-preview')
                return await self.upscale_image(
                    image_path=image_path,
                    upscale_factor=upscale_factor,
                    model=upscale_model,
                    **kwargs
                )
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
        """
        Expand image by scale factors.

        使用官方 SDK 方式：padding + mask
        """
        x_scale = kwargs.get('x_scale', 1.5)
        y_scale = kwargs.get('y_scale', 1.5)

        logger.info(f"[Expand Service] Scale expansion: x={x_scale}, y={y_scale}")

        if not PIL_AVAILABLE:
            raise RuntimeError("PIL is required for scale expansion")

        # ✅ 使用统一的图片加载方法（支持 data:, http://, 本地文件）
        image_bytes, mime_type = await self._load_image_from_path(image_path)
        source_image = PILImage.open(io.BytesIO(image_bytes))

        orig_width, orig_height = source_image.size

        # 计算目标尺寸
        target_width = int(orig_width * x_scale)
        target_height = int(orig_height * y_scale)

        # 确保尺寸是 8 的倍数
        target_width = (target_width // 8) * 8
        target_height = (target_height // 8) * 8

        logger.info(f"[Expand Service] Scale target: {orig_width}x{orig_height} -> {target_width}x{target_height}")

        # 使用编辑模型
        edit_model = model if model in self.edit_models else 'imagen-3.0-capability-001'

        # ✅ 将图片字节转换为 data: 格式，供 _pad_image_for_outpaint 使用
        b64_data = base64.b64encode(image_bytes).decode('utf-8')
        image_data_url = f"data:{mime_type};base64,{b64_data}"

        # 创建 padded 图像和 mask
        padded_bytes, mask_bytes = self._pad_image_for_outpaint(
            image_data_url, target_width, target_height
        )

        # 构建配置
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
        config_kwargs = dict(
            edit_mode="EDIT_MODE_OUTPAINT",
            number_of_images=kwargs.get('number_of_images', 1),
            include_rai_reason=kwargs.get('include_rai_reason', True),
            output_mime_type=output_mime_type,
        )

        if kwargs.get('negative_prompt'):
            config_kwargs['negative_prompt'] = kwargs['negative_prompt']
        if kwargs.get('seed') and kwargs['seed'] != -1:
            config_kwargs['seed'] = kwargs['seed']
        if output_mime_type == 'image/jpeg':
            config_kwargs['output_compression_quality'] = kwargs.get('output_compression_quality', 95)

        config = genai_types.EditImageConfig(**config_kwargs)

        # 创建 reference images
        raw_ref_image = genai_types.RawReferenceImage(
            reference_id=1,
            reference_image=genai_types.Image(image_bytes=padded_bytes)
        )

        mask_ref_image = genai_types.MaskReferenceImage(
            reference_id=2,
            reference_image=genai_types.Image(image_bytes=mask_bytes),
            config=genai_types.MaskReferenceConfig(
                mask_mode="MASK_MODE_USER_PROVIDED",
                mask_dilation=kwargs.get('mask_dilation', 0.03),
            )
        )

        # ✅ 使用 Vertex AI 客户端（outpainting 需要 Vertex AI）
        vertex_client = self._get_vertex_client()
        response = vertex_client.models.edit_image(
            model=edit_model,
            prompt=expand_prompt or "",
            reference_images=[raw_ref_image, mask_ref_image],
            config=config
        )

        return await self._process_expansion_results(
            response, "scale",
            x_scale=x_scale,
            y_scale=y_scale,
            original_size=(orig_width, orig_height),
            target_size=(target_width, target_height)
        )
    
    async def _expand_by_offset(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Expand image by pixel offsets.

        使用官方 SDK 方式：padding + mask
        """
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

        if not PIL_AVAILABLE:
            raise RuntimeError("PIL is required for offset expansion")

        # ✅ 使用统一的图片加载方法（支持 data:, http://, 本地文件）
        image_bytes, mime_type = await self._load_image_from_path(image_path)
        source_image = PILImage.open(io.BytesIO(image_bytes))

        orig_width, orig_height = source_image.size

        # 计算目标尺寸
        target_width = orig_width + left_offset + right_offset
        target_height = orig_height + top_offset + bottom_offset

        # 确保尺寸是 8 的倍数
        target_width = (target_width // 8) * 8
        target_height = (target_height // 8) * 8

        logger.info(f"[Expand Service] Offset target: {orig_width}x{orig_height} -> {target_width}x{target_height}")

        # 使用编辑模型
        edit_model = model if model in self.edit_models else 'imagen-3.0-capability-001'

        # ✅ 将图片字节转换为 data: 格式，供 _pad_image_with_offset 使用
        b64_data = base64.b64encode(image_bytes).decode('utf-8')
        image_data_url = f"data:{mime_type};base64,{b64_data}"

        # 创建带偏移的 padded 图像和 mask
        padded_bytes, mask_bytes = self._pad_image_with_offset(
            image_data_url, target_width, target_height,
            left_offset, right_offset, top_offset, bottom_offset
        )

        # 构建配置
        output_mime_type = kwargs.get('output_mime_type', 'image/png')
        config_kwargs = dict(
            edit_mode="EDIT_MODE_OUTPAINT",
            number_of_images=kwargs.get('number_of_images', 1),
            include_rai_reason=kwargs.get('include_rai_reason', True),
            output_mime_type=output_mime_type,
        )

        if kwargs.get('negative_prompt'):
            config_kwargs['negative_prompt'] = kwargs['negative_prompt']
        if kwargs.get('seed') and kwargs['seed'] != -1:
            config_kwargs['seed'] = kwargs['seed']
        if output_mime_type == 'image/jpeg':
            config_kwargs['output_compression_quality'] = kwargs.get('output_compression_quality', 95)

        config = genai_types.EditImageConfig(**config_kwargs)

        # 创建 reference images
        raw_ref_image = genai_types.RawReferenceImage(
            reference_id=1,
            reference_image=genai_types.Image(image_bytes=padded_bytes)
        )

        mask_ref_image = genai_types.MaskReferenceImage(
            reference_id=2,
            reference_image=genai_types.Image(image_bytes=mask_bytes),
            config=genai_types.MaskReferenceConfig(
                mask_mode="MASK_MODE_USER_PROVIDED",
                mask_dilation=kwargs.get('mask_dilation', 0.03),
            )
        )

        # ✅ 使用 Vertex AI 客户端（outpainting 需要 Vertex AI）
        vertex_client = self._get_vertex_client()
        response = vertex_client.models.edit_image(
            model=edit_model,
            prompt=expand_prompt or "",
            reference_images=[raw_ref_image, mask_ref_image],
            config=config
        )

        return await self._process_expansion_results(
            response, "offset",
            left_offset=left_offset,
            right_offset=right_offset,
            top_offset=top_offset,
            bottom_offset=bottom_offset,
            original_size=(orig_width, orig_height),
            target_size=(target_width, target_height)
        )
    
    async def _expand_by_ratio(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Expand image to specific aspect ratio.

        使用改进的 outpaint_with_ratio 方法（官方 SDK 方式：padding + mask）
        """
        output_ratio = kwargs.get('output_ratio', '16:9')

        logger.info(f"[Expand Service] Ratio expansion: ratio={output_ratio}")

        # 使用编辑模型（如果传入的是生成模型，切换到编辑模型）
        edit_model = model
        if model not in self.edit_models:
            edit_model = 'imagen-3.0-capability-001'
            logger.info(f"[Expand Service] Switching to edit model: {edit_model}")

        # 调用改进的 outpaint_with_ratio 方法
        return await self.outpaint_with_ratio(
            image_path=image_path,
            target_ratio=output_ratio,
            prompt=expand_prompt,
            model=edit_model,
            **kwargs
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
                        "mime_type": "image/png",
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
        # expand_prompt 是可选的，如果为空则使用默认空字符串（API 会自动推断扩展内容）
        if expand_prompt and len(expand_prompt) > 2000:
            from ..common.parameter_validation import ParameterValidationError
            raise ParameterValidationError(
                parameter='expand_prompt',
                value=expand_prompt[:50] + '...',
                message=f"Parameter 'expand_prompt' is too long ({len(expand_prompt)} characters)",
                valid_range="0 to 2000 characters",
                suggestion="Shorten the prompt to 2000 characters or less",
                service=self.validator.service_name
            )
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
            "max_output_resolution": "4K",
            # 新增 upscale 能力
            "upscale": {
                "factors": self.VALID_UPSCALE_FACTORS,
                "max_output_megapixels": self.MAX_OUTPUT_MEGAPIXELS,
                "models": list(self.upscale_models)
            }
        }

    # ========================================
    # Upscale 功能 (整合自 upscale_service.py)
    # ========================================

    async def upscale_image(
        self,
        image_path: str,
        upscale_factor: str = "x2",
        model: str = "imagen-4.0-upscale-preview",
        output_mime_type: str = "image/png",
        output_compression_quality: int = 95,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        图片放大 - 使用 upscale_image API

        Args:
            image_path: 图片路径或 base64 编码
            upscale_factor: 放大倍数 ("x2", "x3", "x4")
            model: 模型 ID (默认 imagen-4.0-upscale-preview)
            output_mime_type: 输出格式 ("image/png" 或 "image/jpeg")
            output_compression_quality: JPEG 压缩质量 (1-100)
            **kwargs: 其他参数
                - enhance_input_image: 是否增强输入图像
                - image_preservation_factor: 图像保留因子 (0.0-1.0)

        Returns:
            List of upscaled images
        """
        try:
            # 验证参数
            if upscale_factor not in self.VALID_UPSCALE_FACTORS:
                raise ValueError(f"Invalid upscale factor: {upscale_factor}. Must be one of {self.VALID_UPSCALE_FACTORS}")

            if model not in self.upscale_models:
                logger.warning(f"[Expand Service] Model {model} may not support upscaling")

            logger.info(f"[Expand Service] Upscale: factor={upscale_factor}, model={model}")

            # ✅ 使用统一的图片加载方法（支持 data:, http://, 本地文件）
            image_bytes, _ = await self._load_image_from_path(image_path)
            image = genai_types.Image(image_bytes=image_bytes)

            # 检查分辨率限制（传入已加载的 image_bytes）
            original_size, new_size, error = self._check_upscale_resolution(image_bytes, upscale_factor)
            if error:
                raise ValueError(error)

            logger.info(f"[Expand Service] Upscale: {original_size} -> {new_size}")

            # 构建配置
            config_kwargs = dict(
                include_rai_reason=kwargs.get('include_rai_reason', True),
                person_generation=getattr(
                    genai_types.PersonGeneration,
                    kwargs.get('person_generation', 'ALLOW_ADULT'),
                    genai_types.PersonGeneration.ALLOW_ADULT
                ),
                safety_filter_level=getattr(
                    genai_types.SafetyFilterLevel,
                    kwargs.get('safety_filter_level', 'BLOCK_LOW_AND_ABOVE'),
                    genai_types.SafetyFilterLevel.BLOCK_LOW_AND_ABOVE
                ),
                output_mime_type=output_mime_type,
                enhance_input_image=kwargs.get('enhance_input_image', True),
                image_preservation_factor=kwargs.get('image_preservation_factor', 0.6),
            )

            if output_mime_type == 'image/jpeg':
                config_kwargs['output_compression_quality'] = output_compression_quality

            config = genai_types.UpscaleImageConfig(**config_kwargs)

            # ✅ 使用 Vertex AI 客户端
            vertex_client = self._get_vertex_client()
            response = vertex_client.models.upscale_image(
                model=model,
                image=image,
                upscale_factor=upscale_factor,
                config=config,
            )

            # 处理结果
            results = []
            if response.generated_images:
                for idx, generated_image in enumerate(response.generated_images):
                    if generated_image.image and generated_image.image.image_bytes:
                        b64_data = base64.b64encode(generated_image.image.image_bytes).decode('utf-8')
                        mime = output_mime_type
                        results.append({
                            "url": f"data:{mime};base64,{b64_data}",
                            "mime_type": mime,
                            "index": idx,
                            "mode": "upscale",
                            "upscale_factor": upscale_factor,
                            "original_size": original_size,
                            "upscaled_size": new_size,
                        })

            if not results:
                raise ValueError("No image generated from upscale")

            logger.info(f"[Expand Service] Upscale successful: {len(results)} images")
            return results

        except Exception as e:
            logger.error(f"[Expand Service] Upscale error: {e}", exc_info=True)
            raise

    def _check_upscale_resolution(
        self,
        image_path_or_bytes: Union[bytes, str],
        upscale_factor: str
    ) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]], Optional[str]]:
        """
        检查放大后的分辨率是否超出限制

        Args:
            image_path_or_bytes: 图片路径（str）或图片字节（bytes）
            upscale_factor: 放大倍数

        Returns:
            (original_size, new_size, error_message)
        """
        if not PIL_AVAILABLE:
            return None, None, None  # 无法检查，跳过

        try:
            # ✅ 支持直接传入 bytes（已由 _load_image_from_path 加载）
            if isinstance(image_path_or_bytes, bytes):
                img = PILImage.open(io.BytesIO(image_path_or_bytes))
            elif isinstance(image_path_or_bytes, str) and image_path_or_bytes.startswith('data:'):
                b64_data = image_path_or_bytes.split(',', 1)[1] if ',' in image_path_or_bytes else image_path_or_bytes
                img = PILImage.open(io.BytesIO(base64.b64decode(b64_data)))
            else:
                # 本地文件路径（注意：HTTP URL 应该先通过 _load_image_from_path 转换为 bytes）
                img = PILImage.open(image_path_or_bytes)

            original_width, original_height = img.size
            factor = {"x2": 2, "x3": 3, "x4": 4}.get(upscale_factor, 2)
            new_width = original_width * factor
            new_height = original_height * factor
            new_megapixels = (new_width * new_height) / 1_000_000

            if new_megapixels > self.MAX_OUTPUT_MEGAPIXELS:
                return (
                    (original_width, original_height),
                    (new_width, new_height),
                    f"Output resolution {new_megapixels:.2f}MP exceeds limit {self.MAX_OUTPUT_MEGAPIXELS}MP"
                )

            return (original_width, original_height), (new_width, new_height), None

        except Exception as e:
            logger.warning(f"[Expand Service] Failed to check resolution: {e}")
            return None, None, None

    # ========================================
    # 改进的 Outpaint 实现 (使用官方 SDK 方式)
    # ========================================

    def _pad_image_for_outpaint(
        self,
        image_path: str,
        target_width: int,
        target_height: int,
        horizontal_offset: float = 0.0,
        vertical_offset: float = 0.0,
    ) -> Tuple[bytes, bytes]:
        """
        对图像进行 padding 以准备 outpaint

        Args:
            image_path: 原图路径或 base64
            target_width: 目标宽度
            target_height: 目标高度
            horizontal_offset: 水平偏移比例 (-0.5 到 0.5)
            vertical_offset: 垂直偏移比例 (-0.5 到 0.5)

        Returns:
            (padded_image_bytes, mask_bytes)
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL is required for outpaint padding")

        # 加载原图
        if image_path.startswith('data:'):
            b64_data = image_path.split(',', 1)[1] if ',' in image_path else image_path
            image_bytes = base64.b64decode(b64_data)
            source_image = PILImage.open(io.BytesIO(image_bytes))
        else:
            source_image = PILImage.open(image_path)

        orig_width, orig_height = source_image.size

        # 如果原图比目标大，先缩放
        if orig_width > target_width or orig_height > target_height:
            source_image.thumbnail((target_width, target_height))
            orig_width, orig_height = source_image.size

        # 计算插入位置
        base_x = (target_width - orig_width) // 2
        base_y = (target_height - orig_height) // 2

        # 应用偏移
        insert_x = base_x + int(horizontal_offset * target_width)
        insert_y = base_y + int(vertical_offset * target_height)

        # 确保不超出边界
        insert_x = max(0, min(insert_x, target_width - orig_width))
        insert_y = max(0, min(insert_y, target_height - orig_height))

        # 创建 padded 图像 (黑色背景)
        padded_image = PILImage.new('RGB', (target_width, target_height), (0, 0, 0))
        padded_image.paste(source_image, (insert_x, insert_y))

        # 创建 mask (白色=需要生成，黑色=保留原图)
        mask = PILImage.new('L', (target_width, target_height), 255)
        # 在原图位置填充黑色
        mask_region = PILImage.new('L', (orig_width, orig_height), 0)
        mask.paste(mask_region, (insert_x, insert_y))

        # 转换为 bytes
        img_buffer = io.BytesIO()
        padded_image.save(img_buffer, format='PNG')
        padded_bytes = img_buffer.getvalue()

        mask_buffer = io.BytesIO()
        mask.save(mask_buffer, format='PNG')
        mask_bytes = mask_buffer.getvalue()

        return padded_bytes, mask_bytes

    def _pad_image_with_offset(
        self,
        image_path: str,
        target_width: int,
        target_height: int,
        left_offset: int,
        right_offset: int,
        top_offset: int,
        bottom_offset: int,
    ) -> Tuple[bytes, bytes]:
        """
        使用精确像素偏移对图像进行 padding

        Args:
            image_path: 原图路径或 base64
            target_width: 目标宽度
            target_height: 目标高度
            left_offset: 左侧扩展像素
            right_offset: 右侧扩展像素
            top_offset: 顶部扩展像素
            bottom_offset: 底部扩展像素

        Returns:
            (padded_image_bytes, mask_bytes)
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL is required for offset padding")

        # 加载原图
        if image_path.startswith('data:'):
            b64_data = image_path.split(',', 1)[1] if ',' in image_path else image_path
            image_bytes = base64.b64decode(b64_data)
            source_image = PILImage.open(io.BytesIO(image_bytes))
        else:
            source_image = PILImage.open(image_path)

        orig_width, orig_height = source_image.size

        # 计算插入位置 (原图放在 left_offset, top_offset 位置)
        insert_x = left_offset
        insert_y = top_offset

        # 创建 padded 图像 (黑色背景)
        padded_image = PILImage.new('RGB', (target_width, target_height), (0, 0, 0))
        padded_image.paste(source_image, (insert_x, insert_y))

        # 创建 mask (白色=需要生成，黑色=保留原图)
        mask = PILImage.new('L', (target_width, target_height), 255)
        # 在原图位置填充黑色
        mask_region = PILImage.new('L', (orig_width, orig_height), 0)
        mask.paste(mask_region, (insert_x, insert_y))

        # 转换为 bytes
        img_buffer = io.BytesIO()
        padded_image.save(img_buffer, format='PNG')
        padded_bytes = img_buffer.getvalue()

        mask_buffer = io.BytesIO()
        mask.save(mask_buffer, format='PNG')
        mask_bytes = mask_buffer.getvalue()

        return padded_bytes, mask_bytes

    async def outpaint_with_ratio(
        self,
        image_path: str,
        target_ratio: str,
        prompt: str = "",
        model: str = "imagen-3.0-capability-001",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        使用目标比例进行 outpaint (官方 SDK 方式)

        Args:
            image_path: 原图路径
            target_ratio: 目标比例 ("16:9", "9:16", "1:1", "3:4", "4:3")
            prompt: 扩展区域描述（可选）
            model: 编辑模型
            **kwargs: 其他参数

        Returns:
            List of expanded images
        """
        try:
            if not PIL_AVAILABLE:
                raise RuntimeError("PIL is required for outpaint")

            logger.info(f"[Expand Service] Outpaint with ratio: {target_ratio}, model={model}")

            # 解析比例
            try:
                w_ratio, h_ratio = map(int, target_ratio.split(':'))
            except ValueError:
                raise ValueError(f"Invalid ratio format: {target_ratio}")

            # ✅ 使用统一的图片加载方法（支持 data:, http://, 本地文件）
            image_bytes, mime_type = await self._load_image_from_path(image_path)
            source_image = PILImage.open(io.BytesIO(image_bytes))

            orig_width, orig_height = source_image.size

            # 计算目标尺寸（保持原图完整，扩展到目标比例）
            target_aspect = w_ratio / h_ratio
            orig_aspect = orig_width / orig_height

            if target_aspect > orig_aspect:
                # 需要横向扩展
                target_width = int(orig_height * target_aspect)
                target_height = orig_height
            else:
                # 需要纵向扩展
                target_width = orig_width
                target_height = int(orig_width / target_aspect)

            # 确保尺寸是 8 的倍数
            target_width = (target_width // 8) * 8
            target_height = (target_height // 8) * 8

            logger.info(f"[Expand Service] Target size: {target_width}x{target_height}")

            # 获取偏移参数
            h_offset = kwargs.get('horizontal_offset', 0.0)
            v_offset = kwargs.get('vertical_offset', 0.0)

            # ✅ 将图片字节转换为 data: 格式，供 _pad_image_for_outpaint 使用
            b64_data = base64.b64encode(image_bytes).decode('utf-8')
            image_data_url = f"data:{mime_type};base64,{b64_data}"

            # 创建 padded 图像和 mask
            padded_bytes, mask_bytes = self._pad_image_for_outpaint(
                image_data_url, target_width, target_height, h_offset, v_offset
            )

            # 构建配置
            output_mime_type = kwargs.get('output_mime_type', 'image/png')
            config_kwargs = dict(
                edit_mode="EDIT_MODE_OUTPAINT",
                number_of_images=kwargs.get('number_of_images', 1),
                include_rai_reason=kwargs.get('include_rai_reason', True),
                output_mime_type=output_mime_type,
            )

            if kwargs.get('negative_prompt'):
                config_kwargs['negative_prompt'] = kwargs['negative_prompt']
            if kwargs.get('seed') and kwargs['seed'] != -1:
                config_kwargs['seed'] = kwargs['seed']
            if output_mime_type == 'image/jpeg':
                config_kwargs['output_compression_quality'] = kwargs.get('output_compression_quality', 95)

            config = genai_types.EditImageConfig(**config_kwargs)

            # 创建 reference images
            raw_ref_image = genai_types.RawReferenceImage(
                reference_id=1,
                reference_image=genai_types.Image(image_bytes=padded_bytes)
            )

            mask_ref_image = genai_types.MaskReferenceImage(
                reference_id=2,
                reference_image=genai_types.Image(image_bytes=mask_bytes),
                config=genai_types.MaskReferenceConfig(
                    mask_mode="MASK_MODE_USER_PROVIDED",
                    mask_dilation=kwargs.get('mask_dilation', 0.03),
                )
            )

            # ✅ 使用 Vertex AI 客户端
            vertex_client = self._get_vertex_client()
            response = vertex_client.models.edit_image(
                model=model,
                prompt=prompt or "",
                reference_images=[raw_ref_image, mask_ref_image],
                config=config,
            )

            return await self._process_expansion_results(
                response, "outpaint_ratio",
                target_ratio=target_ratio,
                original_size=(orig_width, orig_height),
                target_size=(target_width, target_height)
            )

        except Exception as e:
            logger.error(f"[Expand Service] Outpaint error: {e}", exc_info=True)
            raise