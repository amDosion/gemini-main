"""
Google Mode API Router

This module provides API endpoints for Google-specific modes (outpainting, inpainting,
virtual try-on, etc.) that frontend will call.

架构说明：
- 所有操作通过 ProviderFactory.create("google") 获取 GoogleService
- GoogleService 作为统一协调层，负责分发到具体子服务
- 遵循"路由与逻辑分离"架构原则

Endpoints:
- GET /api/google/modes - List available modes
- POST /api/google/outpaint - Image outpainting (通过 GoogleService.expand_image)
- POST /api/google/inpaint - Image inpainting (通过 GoogleService.edit_image)
- POST /api/google/virtual-tryon - Virtual try-on (通过 GoogleService.virtual_tryon)

Created: 2026-01-11
Updated: 2026-01-14 - 统一通过 GoogleService 调用
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional
import logging
import uuid

from ...core.database import SessionLocal
from ...core.user_context import require_user_id
from ...models.db_models import ConfigProfile, UserSettings
from ...services.common.provider_factory import ProviderFactory
from ...core.encryption import decrypt_data, is_encrypted

logger = logging.getLogger(__name__)


def _decrypt_api_key(api_key: str) -> str:
    """解密 API Key（兼容未加密的历史数据）"""
    if not api_key:
        return api_key
    if not is_encrypted(api_key):
        return api_key
    try:
        return decrypt_data(api_key)
    except Exception as e:
        logger.warning(f"[Google Modes] API key decryption failed: {e}")
        return api_key

router = APIRouter(prefix="/api/google", tags=["google-modes"])


# ==================== Database Dependency ====================

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Request Models ====================

class OutpaintRequest(BaseModel):
    """Outpainting request model"""
    image: str = Field(..., description="Base64 encoded image or URL")
    prompt: str = Field(..., description="Prompt for outpainting")
    model: Optional[str] = Field("imagen-3.0-generate-001", description="Model to use")
    aspectRatio: Optional[str] = Field(None, description="Target aspect ratio (e.g., '16:9')")
    platform: Optional[str] = Field(None, description="Platform preference (vertex_ai or developer_api)")


class InpaintRequest(BaseModel):
    """Inpainting request model"""
    image: str = Field(..., description="Base64 encoded image or URL")
    mask: str = Field(..., description="Base64 encoded mask image")
    prompt: str = Field(..., description="Prompt for inpainting")
    model: Optional[str] = Field("imagen-3.0-generate-001", description="Model to use")
    platform: Optional[str] = Field(None, description="Platform preference (vertex_ai or developer_api)")


class VirtualTryonRequest(BaseModel):
    """Virtual try-on request model"""
    personImage: str = Field(..., description="Base64 encoded person image or URL")
    garmentImage: str = Field(..., description="Base64 encoded garment image or URL")
    model: Optional[str] = Field("imagen-3.0-generate-001", description="Model to use")
    platform: Optional[str] = Field(None, description="Platform preference (vertex_ai or developer_api)")


# ==================== Helper Functions ====================

async def get_google_credentials(
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None
) -> str:
    """
    Get Google API credentials from database.
    
    Priority:
    1. Request parameter (for testing/override)
    2. Active profile in database
    3. Any Google profile in database
    
    Args:
        db: Database session
        user_id: Current user ID
        request_api_key: Optional API key from request
    
    Returns:
        API key
    
    Raises:
        HTTPException: If no API key found
    """
    # 1. Use request parameter if provided
    if request_api_key and request_api_key.strip():
        logger.info("[Google Modes] Using API key from request parameter")
        return request_api_key
    
    # 2. Get from database
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None
    
    matching_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == 'google',
        ConfigProfile.user_id == user_id
    ).all()
    
    if not matching_profiles:
        raise HTTPException(
            status_code=401,
            detail="API Key not found for provider: google. Please configure it in Settings → Profiles."
        )
    
    # Priority: active profile
    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                logger.info(f"[Google Modes] Using API key from active profile '{profile.name}'")
                return _decrypt_api_key(profile.api_key)

    # Fallback: first matching profile
    for profile in matching_profiles:
        if profile.api_key:
            logger.info(f"[Google Modes] Using API key from profile '{profile.name}' (fallback)")
            return _decrypt_api_key(profile.api_key)
    
    raise HTTPException(
        status_code=401,
        detail="API Key not found for provider: google. Please configure it in Settings → Profiles."
    )


# ==================== Mode Definitions ====================

# 静态模式定义（用于 /modes 端点）
GOOGLE_MODES = [
    {
        "mode_id": "image-outpainting",
        "name": "Image Outpainting",
        "description": "Extend image boundaries by generating new content around the original image",
        "category": "image-editing",
        "required_params": ["image", "prompt"],
        "optional_params": ["model", "aspectRatio", "number_of_images"],
        "default_model": "imagen-3.0-generate-001",
        "supported_models": ["imagen-3.0-generate-001", "imagen-3.0-fast-generate-001"],
        "platform_support": "either"
    },
    {
        "mode_id": "image-inpainting",
        "name": "Image Inpainting",
        "description": "Fill masked regions in an image with generated content",
        "category": "image-editing",
        "required_params": ["image", "mask", "prompt"],
        "optional_params": ["model", "number_of_images"],
        "default_model": "imagen-3.0-generate-001",
        "supported_models": ["imagen-3.0-generate-001", "imagen-3.0-fast-generate-001"],
        "platform_support": "either"
    },
    {
        "mode_id": "virtual-try-on",
        "name": "Virtual Try-On",
        "description": "Replace clothing items on a person with new garments",
        "category": "image-editing",
        "required_params": ["personImage", "prompt"],
        "optional_params": ["mask", "target_clothing", "edit_mode", "mask_mode", "dilation"],
        "default_model": "imagen-3.0-capability-001",
        "supported_models": ["imagen-3.0-capability-001"],
        "platform_support": "vertex_ai_preferred"
    }
]


# ==================== API Endpoints ====================

@router.get("/modes")
async def list_google_modes(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    List all available Google modes.

    Returns:
        {
            "modes": [
                {
                    "mode_id": "image-outpainting",
                    "name": "Image Outpainting",
                    "description": "Extend image boundaries...",
                    "category": "image-editing",
                    "required_params": ["image", "prompt"],
                    "optional_params": ["aspectRatio", "platform"],
                    ...
                },
                ...
            ]
        }
    """
    try:
        # Verify user authentication
        user_id = require_user_id(request)
        logger.info(f"[Google Modes] Listing modes for user={user_id}")

        logger.info(f"[Google Modes] Found {len(GOOGLE_MODES)} modes")

        return {
            "modes": GOOGLE_MODES,
            "count": len(GOOGLE_MODES)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Google Modes] Error listing modes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outpaint")
async def outpaint_image(
    request_data: OutpaintRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Perform image outpainting using Google Imagen.

    通过 GoogleService.edit_image() 进行图像外扩。

    Request Body:
        {
            "image": "base64_or_url",
            "prompt": "extend the image...",
            "model": "imagen-3.0-generate-001",
            "aspectRatio": "16:9",  // optional
            "platform": "vertex_ai"  // optional
        }

    Response:
        {
            "images": ["base64_result"],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "request_id": "uuid"
        }
    """
    try:
        # ✅ 1. 用户认证
        user_id = require_user_id(request)
        request_id = str(uuid.uuid4())

        logger.info(
            f"[Google Modes] Outpaint request: "
            f"user={user_id}, model={request_data.model}, request_id={request_id}"
        )

        # ✅ 2. 获取 API Key
        api_key = await get_google_credentials(db, user_id)

        # ✅ 3. 通过 ProviderFactory 创建 GoogleService
        service = ProviderFactory.create(
            provider="google",
            api_key=api_key,
            user_id=user_id,
            db=db,
            request_id=request_id
        )

        # ✅ 4. 验证参数
        if not request_data.image or not request_data.prompt:
            raise HTTPException(
                status_code=400,
                detail="Missing required parameters: image and prompt are required"
            )

        # ✅ 5. 通过 GoogleService.edit_image() 进行外扩
        # 使用 edit_image 而不是 expand_image，因为 edit_image 支持 base64
        reference_images = {"raw": request_data.image}

        result = await service.edit_image(
            prompt=request_data.prompt,
            model=request_data.model or "imagen-3.0-generate-001",
            reference_images=reference_images,
            mode="image-outpainting",  # 外扩模式
            aspect_ratio=request_data.aspectRatio
        )

        # ✅ 6. 格式化响应
        images = [img.get("base64", img.get("url", "")) for img in result] if result else []

        response = {
            "images": images,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "request_id": request_id
        }

        logger.info(f"[Google Modes] Outpaint completed: request_id={request_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Google Modes] Outpaint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inpaint")
async def inpaint_image(
    request_data: InpaintRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Perform image inpainting using Google Imagen.

    通过 GoogleService.edit_image() 进行图像修复。

    Request Body:
        {
            "image": "base64_or_url",
            "mask": "base64_mask",
            "prompt": "fill the masked area...",
            "model": "imagen-3.0-generate-001",
            "platform": "vertex_ai"  // optional
        }

    Response:
        {
            "images": ["base64_result"],
            "usage": {...},
            "request_id": "uuid"
        }
    """
    try:
        # ✅ 1. 用户认证
        user_id = require_user_id(request)
        request_id = str(uuid.uuid4())

        logger.info(
            f"[Google Modes] Inpaint request: "
            f"user={user_id}, model={request_data.model}, request_id={request_id}"
        )

        # ✅ 2. 获取 API Key
        api_key = await get_google_credentials(db, user_id)

        # ✅ 3. 通过 ProviderFactory 创建 GoogleService
        service = ProviderFactory.create(
            provider="google",
            api_key=api_key,
            user_id=user_id,
            db=db,
            request_id=request_id
        )

        # ✅ 4. 验证参数
        if not request_data.image or not request_data.mask or not request_data.prompt:
            raise HTTPException(
                status_code=400,
                detail="Missing required parameters: image, mask, and prompt are required"
            )

        # ✅ 5. 通过 GoogleService.edit_image() 进行修复
        reference_images = {
            "raw": request_data.image,
            "mask": request_data.mask
        }

        result = await service.edit_image(
            prompt=request_data.prompt,
            model=request_data.model or "imagen-3.0-generate-001",
            reference_images=reference_images,
            mode="image-inpainting"  # 修复模式
        )

        # ✅ 6. 格式化响应
        images = [img.get("base64", img.get("url", "")) for img in result] if result else []

        response = {
            "images": images,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "request_id": request_id
        }

        logger.info(f"[Google Modes] Inpaint completed: request_id={request_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Google Modes] Inpaint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/virtual-tryon")
async def virtual_tryon(
    request_data: VirtualTryonRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Perform virtual try-on using Google Imagen.

    通过 GoogleService.virtual_tryon() 进行虚拟试穿。

    Request Body:
        {
            "personImage": "base64_or_url",
            "garmentImage": "base64_or_url",
            "model": "imagen-3.0-generate-001",
            "platform": "vertex_ai"  // optional
        }

    Response:
        {
            "images": ["base64_result"],
            "usage": {...},
            "request_id": "uuid"
        }
    """
    try:
        # ✅ 1. 用户认证
        user_id = require_user_id(request)
        request_id = str(uuid.uuid4())

        logger.info(
            f"[Google Modes] Virtual try-on request: "
            f"user={user_id}, model={request_data.model}, request_id={request_id}"
        )

        # ✅ 2. 获取 API Key
        api_key = await get_google_credentials(db, user_id)

        # ✅ 3. 通过 ProviderFactory 创建 GoogleService
        service = ProviderFactory.create(
            provider="google",
            api_key=api_key,
            user_id=user_id,
            db=db,
            request_id=request_id
        )

        # ✅ 4. 验证参数
        if not request_data.personImage:
            raise HTTPException(
                status_code=400,
                detail="Missing required parameter: personImage is required"
            )

        # ✅ 5. 通过 GoogleService.virtual_tryon() 进行试穿
        # 构建提示词（描述要试穿的服装）
        prompt = f"Try on the garment from the reference image"
        if request_data.garmentImage:
            # 如果有服装图片，添加到提示词中
            prompt = f"Replace clothing with the garment shown in the reference image"

        result = service.virtual_tryon(
            image_base64=request_data.personImage,
            mask_base64=None,  # 自动检测
            prompt=prompt,
            edit_mode="inpainting-insert",
            mask_mode="foreground",
            dilation=0.02,
            target_clothing="upper body clothing"
        )

        # ✅ 6. 格式化响应
        if result.success:
            response = {
                "images": [result.image],
                "mime_type": result.mime_type,
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                },
                "request_id": request_id
            }
            logger.info(f"[Google Modes] Virtual try-on completed: request_id={request_id}")
            return response
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Virtual try-on failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Google Modes] Virtual try-on error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
