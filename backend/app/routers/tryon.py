"""
Virtual Try-On 路由
提供服装虚拟试穿的 API 端点

支持两种模式：
1. 带掩码编辑：使用 Vertex AI Imagen 3 进行精确的掩码区域编辑
2. 智能编辑：使用 Gemini API 自动识别并替换服装（不需要掩码）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# 使用相对导入
try:
    from ..services.gemini.tryon_service import tryon_service, TryOnResult
except ImportError:
    try:
        from services.gemini.tryon_service import tryon_service, TryOnResult
    except ImportError:
        from backend.app.services.gemini.tryon_service import tryon_service, TryOnResult

router = APIRouter(prefix="/api/tryon", tags=["tryon"])


class TryOnEditRequest(BaseModel):
    """Try-On 编辑请求"""
    image: str  # Base64 编码的原图（可带或不带 data:image/xxx;base64, 前缀）
    mask: Optional[str] = None  # Base64 编码的掩码（可选）
    prompt: str  # 服装描述
    edit_mode: str = "inpainting-insert"  # 编辑模式
    mask_mode: str = "foreground"  # 掩码模式
    dilation: float = 0.02  # 膨胀系数
    api_key: Optional[str] = None  # Gemini API Key（用于备用方案）
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
    api_key: str  # Gemini API Key

    class Config:
        json_schema_extra = {
            "example": {
                "image": "base64_encoded_image_data...",
                "target": "upper body clothing",
                "api_key": "your_gemini_api_key"
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


@router.post("/edit", response_model=TryOnEditResponse)
async def edit_image(request: TryOnEditRequest) -> TryOnEditResponse:
    """
    Virtual Try-On 图像编辑接口
    
    使用 Vertex AI Imagen 3 或 Gemini API 进行服装替换
    
    请求参数：
    - image: Base64 编码的原图
    - mask: Base64 编码的掩码（可选，如果不提供则使用 Gemini 智能编辑）
    - prompt: 服装描述（如 "A dark green jacket"）
    - edit_mode: 编辑模式（inpainting-insert/inpainting-remove）
    - mask_mode: 掩码模式（foreground/background）
    - dilation: 掩码膨胀系数（0.0-1.0）
    - api_key: Gemini API Key（用于备用方案）
    - target_clothing: 目标服装类型
    
    返回：
    - success: 是否成功
    - image: Base64 编码的结果图
    - mimeType: 图片 MIME 类型
    - error: 错误信息（如果失败）
    """
    try:
        from ..services.gemini.tryon_service import validate_image
        
        print(f"[TryOn] Received edit request: prompt={request.prompt[:50]}...")
        print(f"[TryOn] Has mask: {request.mask is not None}, target: {request.target_clothing}")

        # 验证图像
        is_valid, error_msg = validate_image(request.image)
        if not is_valid:
            return TryOnEditResponse(
                success=False,
                error=f"图像验证失败: {error_msg}"
            )

        result: TryOnResult = tryon_service.edit_with_mask(
            image_base64=request.image,
            mask_base64=request.mask,
            prompt=request.prompt,
            edit_mode=request.edit_mode,
            mask_mode=request.mask_mode,
            dilation=request.dilation,
            api_key=request.api_key,
            target_clothing=request.target_clothing
        )

        return TryOnEditResponse(
            success=result.success,
            image=result.image,
            mimeType=result.mime_type,
            error=result.error
        )

    except Exception as e:
        print(f"[TryOn] Edit error: {str(e)}")
        return TryOnEditResponse(
            success=False,
            error=str(e)
        )


@router.post("/segment", response_model=TryOnSegmentResponse)
async def segment_clothing(request: TryOnSegmentRequest) -> TryOnSegmentResponse:
    """
    服装分割接口
    
    使用 Gemini API 进行服装区域分割
    
    请求参数：
    - image: Base64 编码的图片
    - target: 分割目标（clothing/upper/lower/full）
    - api_key: Gemini API Key
    
    返回：
    - success: 是否成功
    - segments: 分割结果列表
    - error: 错误信息（如果失败）
    
    注意：此接口主要用于调试和预览，实际的分割逻辑在前端实现
    """
    try:
        from google import genai
        import json

        # 创建客户端
        client = genai.Client(api_key=request.api_key)

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

        print(f"[TryOn] Segmenting: target={request.target}")

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
            # 尝试解析 JSON
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
                
                print(f"[TryOn] Segmentation successful: {len(segments)} segments found")
                return TryOnSegmentResponse(
                    success=True,
                    segments=segments
                )
            except json.JSONDecodeError as e:
                print(f"[TryOn] JSON parse error: {e}")
                return TryOnSegmentResponse(
                    success=False,
                    error=f"Failed to parse segmentation response: {str(e)}"
                )

        return TryOnSegmentResponse(
            success=False,
            error="No segmentation result from Gemini"
        )

    except Exception as e:
        print(f"[TryOn] Segment error: {str(e)}")
        return TryOnSegmentResponse(
            success=False,
            error=str(e)
        )


@router.post("/upscale", response_model=UpscaleResponse)
async def upscale_image(request: UpscaleRequest) -> UpscaleResponse:
    """
    图像超分辨率接口
    
    使用 Imagen 4 进行图像超分辨率处理
    
    请求参数：
    - image: Base64 编码的原图
    - upscale_factor: 放大倍数（2 或 4）
    - add_watermark: 是否添加水印
    
    返回：
    - success: 是否成功
    - image: Base64 编码的高分辨率图像
    - mimeType: 图片 MIME 类型
    - original_resolution: 原始分辨率
    - upscaled_resolution: 放大后分辨率
    - error: 错误信息（如果失败）
    
    限制：
    - 输出分辨率不能超过 17 megapixels
    """
    try:
        from PIL import Image as PILImage
        import io
        import base64
        from ..services.gemini.tryon_service import validate_image
        
        print(f"[TryOn] Received upscale request: factor={request.upscale_factor}x")
        
        # 验证图像
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
        image_bytes = base64.b64decode(image_base64)
        img = PILImage.open(io.BytesIO(image_bytes))
        original_width, original_height = img.size
        original_resolution = f"{original_width}x{original_height}"
        
        # 计算目标分辨率
        new_width = original_width * request.upscale_factor
        new_height = original_height * request.upscale_factor
        upscaled_resolution = f"{new_width}x{new_height}"
        
        # 调用服务
        result: TryOnResult = tryon_service.upscale_image(
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
    
    except Exception as e:
        print(f"[TryOn] Upscale error: {str(e)}")
        return UpscaleResponse(
            success=False,
            error=str(e)
        )


@router.get("/status")
async def get_status():
    """
    获取 Try-On 服务状态
    
    返回：
    - vertex_ai_available: Vertex AI 是否可用
    - gemini_available: Gemini API 是否可用
    - gcp_configured: GCP 是否已配置
    """
    try:
        from ..core.config import settings
        gcp_configured = bool(settings.gcp_project_id)
    except:
        gcp_configured = False

    try:
        from ..services.gemini.tryon_service import VERTEX_AI_AVAILABLE, GENAI_AVAILABLE
    except ImportError:
        try:
            from services.gemini.tryon_service import VERTEX_AI_AVAILABLE, GENAI_AVAILABLE
        except ImportError:
            from backend.app.services.gemini.tryon_service import VERTEX_AI_AVAILABLE, GENAI_AVAILABLE

    return {
        "vertex_ai_available": VERTEX_AI_AVAILABLE,
        "gemini_available": GENAI_AVAILABLE,
        "gcp_configured": gcp_configured
    }
