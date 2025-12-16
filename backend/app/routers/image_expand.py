"""
图片扩展（Out-Painting）路由
只负责处理 HTTP 请求和响应，业务逻辑在 services/image_expand_service.py

前端只需传递：
- image_url: 图片 URL
- api_key: DashScope API Key
- mode: 扩图模式（scale/offset/ratio）
- 对应模式的参数
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..services.image_expand_service import image_expand_service, OutPaintingResult

router = APIRouter(prefix="/api/image", tags=["image-expand"])


class OutPaintingRequest(BaseModel):
    """扩图请求参数"""
    image_url: str  # 图片 URL（支持云存储 URL）
    api_key: str    # DashScope API Key
    
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


@router.post("/out-painting", response_model=OutPaintingResponse)
async def out_painting(request: OutPaintingRequest):
    """
    图片扩展（Out-Painting）接口
    
    直接调用 DashScope API，支持用户的云存储 URL
    
    请求参数：
    - image_url: 图片 URL（支持云存储 URL，如 https://img.dicry.com/...）
    - api_key: DashScope API Key
    - mode: 扩图模式（scale/offset/ratio）
    - 其他参数根据模式不同而不同
    
    返回：
    - success: 是否成功
    - output_url: 扩图结果 URL
    - error: 错误信息（如果失败）
    """
    try:
        # 1. 构建扩图参数
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
        
        # 2. 执行扩图任务（带备用方案）
        result: OutPaintingResult = image_expand_service.execute_with_fallback(
            image_url=request.image_url,
            api_key=request.api_key,
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
