"""
图片扩展（Out-Painting）路由
只负责处理 HTTP 请求和响应，业务逻辑在 services/tongyi/image_expand.py

前端只需传递：
- image_url: 图片 URL
- api_key: DashScope API Key（可选，会从数据库获取）
- mode: 扩图模式（scale/offset/ratio）
- 对应模式的参数
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import logging

from ...core.database import SessionLocal
from ...core.user_context import require_user_id
from ...models.db_models import ConfigProfile, UserSettings
from ...core.encryption import decrypt_data, is_encrypted
from ...services.tongyi.image_expand import image_expand_service, OutPaintingResult

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
        logger.warning(f"[Image Expand] API key decryption failed: {e}")
        return api_key


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_tongyi_api_key(
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None
) -> str:
    """
    从数据库获取 Tongyi 的 API Key

    优先级：
    1. 请求参数（用于测试/覆盖）
    2. 数据库激活配置（必须匹配 tongyi provider）
    3. 数据库任意配置（匹配 tongyi provider）
    """
    provider = "tongyi"

    if request_api_key and request_api_key.strip():
        logger.info(f"[Image Expand] Using API key from request parameter (test/override mode)")
        return request_api_key

    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    matching_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == provider,
        ConfigProfile.user_id == user_id
    ).all()

    if not matching_profiles:
        raise HTTPException(
            status_code=401,
            detail=f"API Key not found for provider: {provider}. "
                   f"Please configure it in Settings → Profiles."
        )

    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                logger.info(f"[Image Expand] Using API key from active profile '{profile.name}'")
                return _decrypt_api_key(profile.api_key)

    for profile in matching_profiles:
        if profile.api_key:
            logger.info(f"[Image Expand] Using API key from profile '{profile.name}' (fallback)")
            return _decrypt_api_key(profile.api_key)

    raise HTTPException(
        status_code=401,
        detail=f"API Key not found for provider: {provider}. "
               f"Please configure it in Settings → Profiles."
    )


router = APIRouter(prefix="/api/generate/tongyi", tags=["Tongyi Image Expand"])


class OutPaintingRequest(BaseModel):
    """扩图请求参数"""
    image_url: str  # 图片 URL（支持云存储 URL）
    api_key: Optional[str] = None  # DashScope API Key（可选，会从数据库获取）
    
    # 扩图模式参数（三选一）
    mode: str = "scale"  # scale | offset | ratio
    
    # Scale 模式参数
    x_scale: Optional[float] = 2.0
    y_scale: Optional[float] = 2.0
    
    # Offset 模式参数
    left_offset: Optional[int] = 0
    right_offset: Optional[int] = 0
    top_offset: Optional[int] = 0
    bottom_offset: Optional[int] = 0
    
    # Ratio 模式参数
    angle: Optional[int] = 0
    output_ratio: Optional[str] = "16:9"


class OutPaintingResponse(BaseModel):
    """扩图响应"""
    success: bool
    task_id: Optional[str] = None
    output_url: Optional[str] = None
    error: Optional[str] = None


@router.post("/outpaint", response_model=OutPaintingResponse)
async def outpaint(
    request: OutPaintingRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
):
    """
    图片扩展（Out-Painting）接口

    直接调用 DashScope API，支持用户的云存储 URL

    请求参数：
    - image_url: 图片 URL（支持云存储 URL，如 https://img.dicry.com/...）
    - api_key: DashScope API Key（可选，会从数据库获取）
    - mode: 扩图模式（scale/offset/ratio）
    - 其他参数根据模式不同而不同

    返回：
    - success: 是否成功
    - output_url: 扩图结果 URL
    - error: 错误信息（如果失败）
    """
    try:
        # ✅ Step 1: 验证用户认证
        user_id = require_user_id(request_obj)

        # ✅ Step 2: 从数据库获取 API Key
        api_key = await get_tongyi_api_key(
            db=db,
            user_id=user_id,
            request_api_key=request.api_key
        )

        logger.info(f"[Image Expand] 收到扩图请求: mode={request.mode}, user_id={user_id}")

        # 3. 构建扩图参数
        parameters = image_expand_service.build_parameters(
            mode=request.mode,
            x_scale=request.x_scale or 2.0,
            y_scale=request.y_scale or 2.0,
            left_offset=request.left_offset or 0,
            right_offset=request.right_offset or 0,
            top_offset=request.top_offset or 0,
            bottom_offset=request.bottom_offset or 0,
            angle=request.angle or 0,
            output_ratio=request.output_ratio or "16:9"
        )

        # 4. 执行扩图任务（带备用方案）
        result: OutPaintingResult = image_expand_service.execute_with_fallback(
            image_url=request.image_url,
            api_key=api_key,  # ✅ 使用从数据库获取的 API Key
            parameters=parameters
        )
        
        # 3. 返回结果
        return OutPaintingResponse(
            success=result.success,
            task_id=result.task_id,
            output_url=result.output_url,
            error=result.error
        )
        
    except Exception as e:
        print(f"[OutPainting] 异常: {str(e)}")
        return OutPaintingResponse(success=False, error=str(e))
