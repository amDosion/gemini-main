"""
Virtual Try-On 路由
提供服装虚拟试穿的 API 端点

支持两种模式：
1. 带掩码编辑：使用 Vertex AI Imagen 3 进行精确的掩码区域编辑
2. 智能编辑：使用 Gemini API 自动识别并替换服装（不需要掩码）

✅ 已修改为通过 GoogleService 协调者调用，不再直接调用 tryon_service
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.user_context import require_user_id
from ...models.db_models import ConfigProfile, UserSettings
from ...core.encryption import decrypt_data, is_encrypted

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tryon", tags=["tryon"])


# ==================== Helper Functions ====================

def _decrypt_api_key(api_key: str) -> str:
    """解密 API Key（兼容未加密的历史数据）"""
    if not api_key:
        return api_key
    if not is_encrypted(api_key):
        return api_key
    try:
        return decrypt_data(api_key)
    except Exception as e:
        logger.warning(f"[TryOn] API key decryption failed: {e}")
        return api_key


async def get_google_api_key(
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None
) -> str:
    """
    获取 Google API Key

    优先级：
    1. 请求参数（用于测试/覆盖）
    2. 数据库激活配置
    3. 数据库任意 Google 配置
    """
    # 1. 优先使用请求参数
    if request_api_key and request_api_key.strip():
        logger.info("[TryOn] Using API key from request")
        return request_api_key

    # 2. 从数据库获取
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    # 查询所有 Google 配置
    google_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == "google",
        ConfigProfile.user_id == user_id
    ).all()

    if not google_profiles:
        raise HTTPException(
            status_code=401,
            detail="Google API Key not found. Please configure it in Settings → Profiles."
        )

    # 优先使用激活配置
    if active_profile_id:
        for profile in google_profiles:
            if profile.id == active_profile_id and profile.api_key:
                logger.info(f"[TryOn] Using active profile '{profile.name}' for Google")
                return _decrypt_api_key(profile.api_key)

    # 回退：使用第一个有 API Key 的配置
    for profile in google_profiles:
        if profile.api_key:
            logger.info(f"[TryOn] Using profile '{profile.name}' for Google (fallback)")
            return _decrypt_api_key(profile.api_key)

    raise HTTPException(
        status_code=401,
        detail="Google API Key not found. Please configure it in Settings → Profiles."
    )


# ==================== Request/Response Models ====================

class TryOnEditRequest(BaseModel):
    """Try-On 编辑请求"""
    image: str  # Base64 编码的原图（可带或不带 data:image/xxx;base64, 前缀）
    mask: Optional[str] = None  # Base64 编码的掩码（可选）
    prompt: str  # 服装描述
    edit_mode: str = "inpainting-insert"  # 编辑模式
    mask_mode: str = "foreground"  # 掩码模式
    dilation: float = 0.02  # 膨胀系数
    api_key: Optional[str] = None  # Gemini API Key（可选，会从数据库获取）
    target_clothing: str = "upper body clothing"  # 目标服装类型

    class Config:
        json_schema_extra = {
            "example": {
                "image": "base64_encoded_image_data...",
                "mask": "base64_encoded_mask_data...",
                "prompt": "A dark green jacket with white shirt inside",
                "edit_mode": "inpainting-insert",
                "mask_mode": "foreground",
                "dilation": 0.02,
                "target_clothing": "upper body clothing"
            }
        }


class TryOnEditResponse(BaseModel):
    """Try-On 编辑响应"""
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mimeType: str = "image/png"
    error: Optional[str] = None


class TryOnSegmentRequest(BaseModel):
    """服装分割请求"""
    image: str  # Base64 编码的图片
    target: str = "clothing"  # 分割目标（clothing/upper/lower/full）
    api_key: Optional[str] = None  # Gemini API Key（可选，会从数据库获取）

    class Config:
        json_schema_extra = {
            "example": {
                "image": "base64_encoded_image_data...",
                "target": "upper body clothing"
            }
        }


class SegmentationResult(BaseModel):
    """分割结果"""
    box_2d: list[float]  # 边界框 [y0, x0, y1, x1]（归一化到 1000）
    mask: str  # Base64 编码的掩码
    label: str  # 标签


class TryOnSegmentResponse(BaseModel):
    """服装分割响应"""
    success: bool
    segments: Optional[list[SegmentationResult]] = None
    error: Optional[str] = None


class UpscaleRequest(BaseModel):
    """Upscale 请求"""
    image: str  # Base64 编码的原图
    upscale_factor: int = 2  # 放大倍数（2 或 4）
    add_watermark: bool = False  # 是否添加水印
    api_key: Optional[str] = None  # API Key（可选，会从数据库获取）

    class Config:
        json_schema_extra = {
            "example": {
                "image": "base64_encoded_image_data...",
                "upscale_factor": 2,
                "add_watermark": False
            }
        }


class UpscaleResponse(BaseModel):
    """Upscale 响应"""
    success: bool
    image: Optional[str] = None  # Base64 编码的高分辨率图像
    mimeType: str = "image/png"
    original_resolution: Optional[str] = None  # 原始分辨率（如 "1024x1024"）
    upscaled_resolution: Optional[str] = None  # 放大后分辨率（如 "4096x4096"）
    error: Optional[str] = None


# ==================== API Endpoints ====================

@router.post("/edit", response_model=TryOnEditResponse)
async def edit_image(
    request: TryOnEditRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
) -> TryOnEditResponse:
    """
    Virtual Try-On 图像编辑接口

    使用 Vertex AI Imagen 3 或 Gemini API 进行服装替换

    ✅ 通过 GoogleService 协调者调用
    """
    try:
        # ✅ 1. 用户认证
        user_id = require_user_id(request_obj)
        logger.info(f"[TryOn] Edit request from user: {user_id}")

        # ✅ 2. 获取 API Key
        api_key = await get_google_api_key(
            db=db,
            user_id=user_id,
            request_api_key=request.api_key
        )

        # ✅ 3. 通过 ProviderFactory 创建 GoogleService
        from ...services.common.provider_factory import ProviderFactory
        service = ProviderFactory.create(
            provider="google",
            api_key=api_key,
            user_id=user_id,
            db=db
        )

        # ✅ 4. 验证图像
        from ...services.gemini.tryon_service import validate_image
        is_valid, error_msg = validate_image(request.image)
        if not is_valid:
            return TryOnEditResponse(
                success=False,
                error=f"图像验证失败: {error_msg}"
            )

        logger.info(f"[TryOn] Calling GoogleService.virtual_tryon: prompt={request.prompt[:50]}...")

        # ✅ 5. 调用 GoogleService.virtual_tryon()
        result = service.virtual_tryon(
            image_base64=request.image,
            mask_base64=request.mask,
            prompt=request.prompt,
            edit_mode=request.edit_mode,
            mask_mode=request.mask_mode,
            dilation=request.dilation,
            target_clothing=request.target_clothing
        )

        return TryOnEditResponse(
            success=result.success,
            image=result.image,
            mimeType=result.mime_type,
            error=result.error
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TryOn] Edit error: {str(e)}", exc_info=True)
        return TryOnEditResponse(
            success=False,
            error=str(e)
        )


@router.post("/segment", response_model=TryOnSegmentResponse)
async def segment_clothing(
    request: TryOnSegmentRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
) -> TryOnSegmentResponse:
    """
    服装分割接口

    使用 Gemini API 进行服装区域分割

    注意：此接口主要用于调试和预览，实际的分割逻辑在前端实现
    """
    try:
        # ✅ 1. 用户认证
        user_id = require_user_id(request_obj)
        logger.info(f"[TryOn] Segment request from user: {user_id}")

        # ✅ 2. 获取 API Key
        api_key = await get_google_api_key(
            db=db,
            user_id=user_id,
            request_api_key=request.api_key
        )

        # ✅ 3. 使用 Gemini API 进行分割
        # 注意：此功能使用原生 Gemini API，未通过 GoogleService
        # 因为 GoogleService.segment_image() 使用文件路径，不适合 base64
        from google import genai
        import json

        client = genai.Client(api_key=api_key)

        # 清理 Base64 前缀
        image_base64 = request.image
        if image_base64.startswith('data:'):
            image_base64 = image_base64.split(',', 1)[1]

        # 构建分割 prompt
        target_map = {
            "upper": "upper body clothing (shirt, jacket, top, hoodie)",
            "lower": "lower body clothing (pants, skirt, shorts)",
            "full": "full body outfit (all clothing items)",
            "clothing": "all clothing items"
        }
        target_desc = target_map.get(request.target, request.target)

        segment_prompt = f"""Give the segmentation masks for {target_desc} in this image.
Output a JSON list of segmentation masks where each entry contains:
- the 2D bounding box in the key 'box_2d' as [y0, x0, y1, x1] normalized to 1000
- the segmentation mask in key 'mask' as a base64 encoded PNG image
- the text label in the key 'label'

Only output the JSON array, no other text."""

        logger.info(f"[TryOn] Segmenting: target={request.target}")

        # 调用 Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                {
                    "parts": [
                        {"inline_data": {"mime_type": "image/png", "data": image_base64}},
                        {"text": segment_prompt}
                    ]
                }
            ]
        )

        # 解析响应
        if response.candidates and len(response.candidates) > 0:
            text = response.candidates[0].content.parts[0].text
            try:
                # 清理可能的 markdown 代码块
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]

                segments_data = json.loads(text.strip())
                segments = [
                    SegmentationResult(
                        box_2d=seg.get("box_2d", [0, 0, 1000, 1000]),
                        mask=seg.get("mask", ""),
                        label=seg.get("label", "clothing")
                    )
                    for seg in segments_data
                ]

                logger.info(f"[TryOn] Segmentation successful: {len(segments)} segments found")
                return TryOnSegmentResponse(
                    success=True,
                    segments=segments
                )
            except json.JSONDecodeError as e:
                logger.warning(f"[TryOn] JSON parse error: {e}")
                return TryOnSegmentResponse(
                    success=False,
                    error=f"Failed to parse segmentation response: {str(e)}"
                )

        return TryOnSegmentResponse(
            success=False,
            error="No segmentation result from Gemini"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TryOn] Segment error: {str(e)}", exc_info=True)
        return TryOnSegmentResponse(
            success=False,
            error=str(e)
        )


@router.post("/upscale", response_model=UpscaleResponse)
async def upscale_image(
    request: UpscaleRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
) -> UpscaleResponse:
    """
    图像超分辨率接口

    使用 Imagen 4 进行图像超分辨率处理

    ✅ 通过 GoogleService 协调者调用
    """
    try:
        # ✅ 1. 用户认证
        user_id = require_user_id(request_obj)
        logger.info(f"[TryOn] Upscale request from user: {user_id}")

        # ✅ 2. 获取 API Key
        api_key = await get_google_api_key(
            db=db,
            user_id=user_id,
            request_api_key=request.api_key
        )

        # ✅ 3. 通过 ProviderFactory 创建 GoogleService
        from ...services.common.provider_factory import ProviderFactory
        service = ProviderFactory.create(
            provider="google",
            api_key=api_key,
            user_id=user_id,
            db=db
        )

        # ✅ 4. 验证图像
        from ...services.gemini.tryon_service import validate_image
        is_valid, error_msg = validate_image(request.image)
        if not is_valid:
            return UpscaleResponse(
                success=False,
                error=f"图像验证失败: {error_msg}"
            )

        # 清理 Base64 前缀
        image_base64 = request.image
        if image_base64.startswith('data:'):
            image_base64 = image_base64.split(',', 1)[1]

        # 获取原始分辨率
        from PIL import Image as PILImage
        import io
        import base64

        image_bytes = base64.b64decode(image_base64)
        img = PILImage.open(io.BytesIO(image_bytes))
        original_width, original_height = img.size
        original_resolution = f"{original_width}x{original_height}"

        # 计算目标分辨率
        new_width = original_width * request.upscale_factor
        new_height = original_height * request.upscale_factor
        upscaled_resolution = f"{new_width}x{new_height}"

        logger.info(f"[TryOn] Calling GoogleService.tryon_upscale: factor={request.upscale_factor}x")

        # ✅ 5. 调用 GoogleService.tryon_upscale()
        result = service.tryon_upscale(
            image_base64=image_base64,
            upscale_factor=request.upscale_factor,
            add_watermark=request.add_watermark
        )

        return UpscaleResponse(
            success=result.success,
            image=result.image,
            mimeType=result.mime_type,
            original_resolution=original_resolution,
            upscaled_resolution=upscaled_resolution if result.success else None,
            error=result.error
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TryOn] Upscale error: {str(e)}", exc_info=True)
        return UpscaleResponse(
            success=False,
            error=str(e)
        )


@router.get("/status")
async def get_status(
    request_obj: Request,
    db: Session = Depends(get_db)
):
    """
    获取 Try-On 服务状态

    返回：
    - vertex_ai_available: Vertex AI 是否可用
    - gemini_available: Gemini API 是否可用
    - gcp_configured: GCP 是否已配置
    - authenticated: 用户是否已认证
    """
    # 检查用户认证
    try:
        user_id = require_user_id(request_obj)
        authenticated = True
    except:
        authenticated = False

    # 检查 GCP 配置
    try:
        from ...core.config import settings
        gcp_configured = bool(settings.gcp_project_id)
    except:
        gcp_configured = False

    # 检查服务可用性
    try:
        from ...services.gemini.tryon_service import VERTEX_AI_AVAILABLE, GENAI_AVAILABLE
    except ImportError:
        VERTEX_AI_AVAILABLE = False
        GENAI_AVAILABLE = False

    return {
        "vertex_ai_available": VERTEX_AI_AVAILABLE,
        "gemini_available": GENAI_AVAILABLE,
        "gcp_configured": gcp_configured,
        "authenticated": authenticated
    }
