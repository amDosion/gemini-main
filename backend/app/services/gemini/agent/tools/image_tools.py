"""
Image Tools - 图像编辑工具

提供：
- analyze_image: 使用 Gemini Vision 分析图像
- edit_image_with_imagen: 使用 Imagen 编辑图像
- generate_mask: 生成编辑掩码（如果需要）
"""

import logging
from typing import Dict, Any, Optional
import json
import re
import base64
import binascii

from .....utils.attachment_handler import is_base64_image_url, is_http_url
from .....utils.log_sanitization import (
    summarize_text_for_log,
    summarize_url_for_log,
)

logger = logging.getLogger(__name__)


_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_MAX_INLINE_EDIT_IMAGE_BYTES = 20 * 1024 * 1024
_IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",
)


def _is_local_file_reference(value: str) -> bool:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    return (
        lowered.startswith("file:")
        or normalized.startswith(("/", "\\", "~"))
        or _WINDOWS_ABSOLUTE_PATH_RE.match(normalized) is not None
    )


def _validate_image_tool_reference(image_url: str) -> str:
    normalized = str(image_url or "").strip()
    if not normalized:
        raise ValueError("image_url is required")

    if _is_local_file_reference(normalized):
        raise ValueError(
            "unsupported image reference; use http(s), data:image, gs://, or files/ provider URI"
        )

    if is_base64_image_url(normalized) or is_http_url(normalized):
        return normalized

    lowered = normalized.lower()
    if lowered.startswith("gs://") or normalized.startswith("files/"):
        return normalized

    raise ValueError(
        "unsupported image reference; use http(s), data:image, gs://, or files/ provider URI"
    )


def _is_plain_base64_image_reference(value: str) -> bool:
    normalized = str(value or "").strip()
    max_base64_chars = ((_MAX_INLINE_EDIT_IMAGE_BYTES + 2) // 3) * 4 + 16
    if not normalized or len(normalized) > max_base64_chars:
        return False
    try:
        payload = base64.b64decode(normalized, validate=True)
    except (ValueError, binascii.Error):
        return False
    if len(payload) > _MAX_INLINE_EDIT_IMAGE_BYTES:
        return False
    return payload.startswith(_IMAGE_SIGNATURES)


def _validate_edit_image_reference(image_ref: str, *, field_name: str) -> str:
    normalized = str(image_ref or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    if _is_local_file_reference(normalized):
        raise ValueError(
            f"unsupported {field_name}; local file references are not allowed"
        )

    lowered = normalized.lower()
    if (
        is_http_url(normalized)
        or is_base64_image_url(normalized)
        or lowered.startswith("gs://")
        or normalized.startswith("files/")
        or _is_plain_base64_image_reference(normalized)
    ):
        return normalized

    raise ValueError(
        f"unsupported {field_name}; use http(s), data:image, gs://, files/, or inline image data"
    )


async def analyze_image(
    image_url: str,
    google_service: Any,
    model: str = "gemini-2.0-flash-exp"
) -> Dict[str, Any]:
    """
    使用 Gemini Vision 分析图像
    
    Args:
        image_url: 图像引用（支持 http(s), data:image/..., gs://, files/...）
        google_service: GoogleService 实例
        model: 使用的模型
        
    Returns:
        分析结果（包含内容、风格、质量等信息）
    """
    log_image_url = summarize_url_for_log(image_url)
    try:
        safe_image_url = _validate_image_tool_reference(image_url)
        logger.info("[ImageTools] Analyzing image: %s", log_image_url)
        
        # 构建分析提示
        analysis_prompt = """请详细分析这张图像，并提供以下信息：
1. 图像内容描述（对象、场景、人物等）
2. 图像风格（写实、卡通、抽象等）
3. 图像质量评估（分辨率、清晰度、色彩等，评分 1-10）
4. 编辑可行性分析（哪些部分可以编辑，哪些不建议编辑）
5. 编辑建议

请以 JSON 格式返回：
{
    "content": "图像内容描述",
    "style": "图像风格",
    "quality": {
        "resolution": "分辨率信息",
        "clarity": 清晰度评分（1-10）,
        "color": 色彩质量评分（1-10）
    },
    "editable_regions": ["可编辑区域列表"],
    "recommendations": ["编辑建议"]
}"""
        
        # 构建消息（包含图像）
        messages = [{
            "role": "user",
            "content": [
                {"text": analysis_prompt},
                {
                    "file_data": {
                        "file_uri": safe_image_url,
                        "mime_type": "image/jpeg"  # 可以根据实际类型调整
                    }
                }
            ]
        }]
        
        # 调用 Gemini Vision API
        response = await google_service.chat(
            messages=messages,
            model=model
        )
        
        # 提取文本响应
        text = response.get("text", "")
        if not text:
            if "candidates" in response and len(response["candidates"]) > 0:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    texts = [
                        part.get("text", "")
                        for part in candidate["content"]["parts"]
                        if "text" in part
                    ]
                    text = " ".join(texts)
        
        # 尝试解析 JSON
        try:
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                analysis_result = json.loads(json_match.group())
            else:
                # 回退：返回原始文本
                analysis_result = {
                    "raw_analysis": text,
                    "content": "无法解析",
                    "style": "未知",
                    "quality": {"clarity": 5, "color": 5}
                }
        except json.JSONDecodeError:
            analysis_result = {
                "raw_analysis": text,
                "content": "无法解析 JSON",
                "style": "未知",
                "quality": {"clarity": 5, "color": 5}
            }
        
        analysis_result["image_url"] = image_url
        
        logger.info(f"[ImageTools] Image analysis completed")
        return analysis_result
        
    except Exception as e:
        logger.error(
            "[ImageTools] Error analyzing image: image=%s error=%s",
            log_image_url,
            summarize_text_for_log(e, label="analysis_error"),
        )
        return {
            "error": str(e),
            "image_url": image_url
        }


async def edit_image_with_imagen(
    prompt: str,
    reference_image: str,
    google_service: Any,
    mask: Optional[str] = None,
    edit_mode: str = "inpainting",
    model: str = "imagen-3.0-generate-001"
) -> Dict[str, Any]:
    """
    使用 Imagen 编辑图像
    
    Args:
        prompt: 编辑提示
        reference_image: 参考图像 URL 或 Base64
        google_service: GoogleService 实例
        mask: 掩码图像（可选）
        edit_mode: 编辑模式（inpainting, outpainting, background-edit等）
        model: 使用的模型
        
    Returns:
        编辑结果（包含编辑后的图像 URL）
    """
    log_reference_image = summarize_url_for_log(reference_image)
    log_prompt = summarize_text_for_log(prompt, label="prompt")
    log_mask = summarize_url_for_log(mask) if str(mask or "").strip() else None
    try:
        safe_reference_image = _validate_edit_image_reference(
            reference_image,
            field_name="reference_image",
        )
        safe_mask = (
            _validate_edit_image_reference(mask, field_name="mask")
            if str(mask or "").strip()
            else None
        )
        logger.info(f"[ImageTools] Editing image with mode: {edit_mode}")
        
        # 准备 reference_images 字典
        reference_images: Dict[str, Any] = {
            "raw": safe_reference_image
        }
        
        if safe_mask:
            reference_images["mask"] = safe_mask
        
        # 调用 GoogleService.edit_image
        result = await google_service.edit_image(
            prompt=prompt,
            model=model,
            reference_images=reference_images,
            mode=edit_mode
        )
        
        logger.info(f"[ImageTools] Image editing completed: {len(result)} images")
        
        return {
            "success": True,
            "edited_images": result,
            "edit_mode": edit_mode,
            "prompt": prompt
        }
        
    except Exception as e:
        logger.error(
            "[ImageTools] Error editing image: reference=%s prompt=%s mask=%s error=%s",
            log_reference_image,
            log_prompt,
            log_mask or "None",
            summarize_text_for_log(e, label="edit_error"),
        )
        return {
            "success": False,
            "error": str(e),
            "edit_mode": edit_mode
        }


async def generate_mask(
    image_url: str,
    mask_prompt: str,
    google_service: Any,
    model: str = "gemini-2.0-flash-exp"
) -> Optional[str]:
    """
    生成编辑掩码（如果需要）
    
    注意：这是一个简化实现，实际可能需要使用专门的掩码生成服务
    
    Args:
        image_url: 图像 URL
        mask_prompt: 掩码描述（要编辑的区域）
        google_service: GoogleService 实例
        model: 使用的模型
        
    Returns:
        掩码图像 URL 或 Base64（如果生成成功）
    """
    log_image_url = summarize_url_for_log(image_url)
    log_mask_prompt = summarize_text_for_log(mask_prompt, label="mask_prompt")
    try:
        safe_image_url = _validate_image_tool_reference(image_url)
        logger.info(
            "[ImageTools] Generating mask for: %s image=%s",
            log_mask_prompt,
            log_image_url,
        )
        
        # 使用 Gemini Vision 分析图像并生成掩码描述
        prompt = f"""根据以下描述，为图像生成编辑掩码区域：
{mask_prompt}

请描述需要编辑的区域（位置、大小、形状等）。
"""
        
        messages = [{
            "role": "user",
            "content": [
                {"text": prompt},
                {
                    "file_data": {
                        "file_uri": safe_image_url,
                        "mime_type": "image/jpeg"
                    }
                }
            ]
        }]
        
        response = await google_service.chat(
            messages=messages,
            model=model
        )
        
        # 提取响应
        text = response.get("text", "")
        
        # 简化实现：返回掩码描述
        # 实际应该生成实际的掩码图像
        logger.warning("[ImageTools] Mask generation is simplified - returning description only")
        
        return None  # 实际应该返回掩码图像 URL
        
    except Exception as e:
        logger.error(
            "[ImageTools] Error generating mask: image=%s prompt=%s error=%s",
            log_image_url,
            log_mask_prompt,
            summarize_text_for_log(e, label="mask_error"),
        )
        return None
