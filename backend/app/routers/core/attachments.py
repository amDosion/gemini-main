"""
附件相关路由

提供临时代理端点，用于避免向前端传输Base64 Data URL
以及附件相关的API端点
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import base64
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...models.db_models import MessageAttachment
from ...services.common.attachment_service import AttachmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["attachments"])


# ==================== Request/Response Models ====================

class ResolveContinuityRequest(BaseModel):
    """解析CONTINUITY附件的请求"""
    active_image_url: str
    session_id: str
    messages: Optional[List[Dict[str, Any]]] = None  # 可选，如果不传则后端从数据库查询


class CloudUrlResponse(BaseModel):
    """云URL响应"""
    url: Optional[str] = None
    upload_status: str


@router.get("/temp-images/{attachment_id}")
async def get_temp_image(
    attachment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_current_user)
):
    """
    临时图片代理端点
    
    用途: 将存储在temp_url中的Base64 Data URL转为HTTP响应
    生命周期: 直到Worker Pool上传完成或会话结束
    
    参数:
        attachment_id: 附件ID
    
    返回:
        - Base64 Data URL: 解码后的图片字节流
        - HTTP URL: 重定向到该URL
    """
    # ✅ 记录请求详情（包括 token 来源，用于诊断 user_id 不一致问题）
    auth_header = request.headers.get("Authorization")
    cookie_token = request.cookies.get("access_token")
    
    token_source = "未知"
    if auth_header:
        token_source = "Authorization header"
    elif cookie_token:
        token_source = "Cookie (access_token)"
    else:
        token_source = "无 token"
    
    logger.info(
        f"[TempImage] 收到请求: attachment_id={attachment_id[:8]}..., "
        f"user_id={current_user[:8]}..., "
        f"token来源={token_source}, "
        f"有Authorization header={'是' if auth_header else '否'}, "
        f"有Cookie token={'是' if cookie_token else '否'}"
    )
    
    # ✅ 先查询附件（不限制 user_id），用于诊断
    attachment_any = db.query(MessageAttachment).filter_by(
        id=attachment_id
    ).first()
    
    if not attachment_any:
        logger.warning(f"[TempImage] ❌ 附件不存在: attachment_id={attachment_id[:8]}...")
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # ✅ 详细比较 user_id（用于诊断）
    attachment_user_id = attachment_any.user_id or ""
    current_user_id = current_user or ""
    
    logger.info(
        f"[TempImage] 🔍 权限检查详情: "
        f"attachment.user_id长度={len(attachment_user_id)}, "
        f"current_user长度={len(current_user_id)}, "
        f"是否相等={attachment_user_id == current_user_id}, "
        f"attachment.user_id完整值={repr(attachment_user_id)}, "
        f"current_user完整值={repr(current_user_id)}"
    )
    
    # ✅ 检查 user_id 是否匹配
    if attachment_user_id != current_user_id:
        logger.warning(
            f"[TempImage] ❌ 权限检查失败: "
            f"attachment.user_id={repr(attachment_user_id)}, "
            f"current_user={repr(current_user_id)}, "
            f"差异位置: {_find_first_diff(attachment_user_id, current_user_id) if attachment_user_id and current_user_id else 'N/A'}"
        )
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    attachment = attachment_any
    logger.info(
        f"[TempImage] ✅ 附件找到: "
        f"user_id={attachment.user_id[:8]}..., "
        f"temp_url={'存在' if attachment.temp_url else 'None'}, "
        f"url={'存在' if attachment.url else 'None'}, "
        f"upload_status={attachment.upload_status}"
    )

    # 检查temp_url
    if not attachment.temp_url:
        # temp_url为空 → 可能已上传完成，返回云URL重定向
        if attachment.url and attachment.upload_status == 'completed':
            logger.info(f"[TempImage] ✅ 上传已完成，重定向到云URL: {attachment.url[:80]}...")
            return RedirectResponse(url=attachment.url)
        else:
            logger.warning(
                f"[TempImage] ❌ Temp URL不可用: "
                f"url={'存在' if attachment.url else 'None'}, "
                f"upload_status={attachment.upload_status}"
            )
            raise HTTPException(status_code=404, detail="Temp URL not available")

    # 判断temp_url类型
    temp_url = attachment.temp_url

    if temp_url.startswith('data:'):
        # Base64 Data URL → 解码并返回
        try:
            mime_type, base64_str = parse_data_url(temp_url)
            image_bytes = base64.b64decode(base64_str)

            logger.info(f"[TempImage] Serving Base64 image: {attachment_id[:8]}... (size: {len(image_bytes) / 1024:.2f} KB)")

            return Response(
                content=image_bytes,
                media_type=mime_type,
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
        except Exception as e:
            logger.error(f"[TempImage] Failed to decode Base64: {attachment_id[:8]}...: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid Base64 data URL: {str(e)}")
    
    elif temp_url.startswith('http'):
        # HTTP URL → 重定向（Tongyi临时URL）
        logger.info(f"[TempImage] Redirecting to HTTP URL: {attachment_id[:8]}...")
        return RedirectResponse(url=temp_url)
    
    else:
        raise HTTPException(status_code=400, detail="Invalid temp URL format")


def _find_first_diff(s1: str, s2: str) -> str:
    """找到两个字符串第一个不同的位置（用于诊断）"""
    if not s1 or not s2:
        return f"s1长度={len(s1)}, s2长度={len(s2)}"
    min_len = min(len(s1), len(s2))
    for i in range(min_len):
        if s1[i] != s2[i]:
            return f"位置{i}: '{s1[i]}' vs '{s2[i]}'"
    if len(s1) != len(s2):
        return f"长度不同: {len(s1)} vs {len(s2)}"
    return "完全相同"


def parse_data_url(data_url: str) -> tuple[str, str]:
    """
    解析Data URL
    
    返回: (mime_type, base64_str)
    
    格式: data:image/png;base64,iVBORw0KGgo...
    """
    if not data_url.startswith('data:'):
        raise ValueError("Invalid data URL")

    # 格式: data:image/png;base64,iVBORw0KGgo...
    parts = data_url.split(',', 1)
    if len(parts) != 2:
        raise ValueError("Invalid data URL format")

    header = parts[0]  # data:image/png;base64
    base64_str = parts[1]

    # 提取MIME类型
    mime_match = header.split(':')[1].split(';')[0]
    mime_type = mime_match if mime_match else 'image/png'

    return mime_type, base64_str


@router.post("/attachments/resolve-continuity")
async def resolve_continuity(
    request_body: ResolveContinuityRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(require_current_user)
):
    """
    解析CONTINUITY LOGIC的附件
    
    用途: Edit模式CONTINUITY LOGIC - 后端负责查找和解析
    
    请求体:
    {
      "activeImageUrl": "blob:http://localhost:3000/xxx",
      "sessionId": "session-123",
      "messages": [...]  // 可选，如果不传则后端从数据库查询
    }
    
    响应:
    {
      "attachmentId": "att-123",
      "url": "https://storage.example.com/xxx.png",  // 云URL
      "status": "completed",
      "taskId": null
    }
    """
    import time
    start_time = time.time()
    
    try:
        # ✅ 详细日志：记录请求信息
        url_type = "Blob" if request_body.active_image_url.startswith("blob:") else \
                   "Base64" if request_body.active_image_url.startswith("data:") else \
                   "HTTP" if request_body.active_image_url.startswith("http") else "未知"
        logger.info(
            f"[Attachments] ========== 开始解析CONTINUITY附件 =========="
        )
        logger.info(
            f"[Attachments] 📥 请求参数: "
            f"user_id={user_id[:8]}..., "
            f"session_id={request_body.session_id[:8] if request_body.session_id else 'None'}..., "
            f"active_image_url类型={url_type}, "
            f"active_image_url长度={len(request_body.active_image_url)}, "
            f"messages数量={len(request_body.messages) if request_body.messages else 0}"
        )
        
        attachment_service = AttachmentService(db)
        
        # ✅ 详细日志：调用解析方法
        logger.info(f"[Attachments] 🔍 调用 AttachmentService.resolve_continuity_attachment()...")
        resolved = await attachment_service.resolve_continuity_attachment(
            active_image_url=request_body.active_image_url,
            session_id=request_body.session_id,
            user_id=user_id,
            messages=request_body.messages or []
        )
        
        elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒
        
        if not resolved:
            logger.warning(f"[Attachments] ❌ 未找到匹配的附件 (耗时: {elapsed_time:.2f}ms)")
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # ✅ 详细日志：显示解析结果
        has_cloud_url = resolved["status"] == "completed" and resolved["url"] and resolved["url"].startswith("http")
        logger.info(
            f"[Attachments] ✅ CONTINUITY附件解析成功 (耗时: {elapsed_time:.2f}ms):"
        )
        logger.info(
            f"[Attachments]     - attachment_id: {resolved['attachment_id'][:8]}..."
        )
        logger.info(
            f"[Attachments]     - status: {resolved['status']}"
        )
        logger.info(
            f"[Attachments]     - hasCloudUrl: {has_cloud_url}"
        )
        logger.info(
            f"[Attachments]     - url: {resolved['url'][:80] + '...' if resolved['url'] and len(resolved['url']) > 80 else resolved['url'] or 'None'}"
        )
        logger.info(
            f"[Attachments]     - taskId: {resolved.get('task_id', 'None')[:8] + '...' if resolved.get('task_id') else 'None'}"
        )
        logger.info(
            f"[Attachments] ========== CONTINUITY附件解析完成 =========="
        )
        
        return {
            "attachment_id": resolved["attachment_id"],
            "url": resolved["url"],
            "status": resolved["status"],
            "task_id": resolved.get("task_id")
        }
    except HTTPException:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"[Attachments] ❌ HTTP异常 (耗时: {elapsed_time:.2f}ms)")
        raise
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"[Attachments] ❌ 解析失败 (耗时: {elapsed_time:.2f}ms): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/attachments/{attachment_id}/cloud-url")
async def get_cloud_url(
    attachment_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(require_current_user)
):
    """
    获取附件的云存储URL
    
    用途: 替代前端的tryFetchCloudUrl
    
    响应:
    {
      "url": "https://storage.example.com/xxx.png",
      "uploadStatus": "completed"
    }
    """
    try:
        attachment_service = AttachmentService(db)
        
        cloud_url = await attachment_service.get_cloud_url(
            attachment_id=attachment_id,
            user_id=user_id
        )
        
        # 查询附件状态
        attachment = db.query(MessageAttachment).filter_by(
            id=attachment_id,
            user_id=user_id
        ).first()
        
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        return CloudUrlResponse(
            url=cloud_url,
            upload_status=attachment.upload_status or "pending"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Attachments] Failed to get cloud URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
