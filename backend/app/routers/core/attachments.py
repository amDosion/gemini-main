"""
附件相关路由

提供临时代理端点，用于避免向前端传输Base64 Data URL
以及附件相关的API端点
"""

from fastapi import APIRouter, HTTPException, Depends
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
    activeImageUrl: str
    sessionId: str
    messages: Optional[List[Dict[str, Any]]] = None  # 可选，如果不传则后端从数据库查询


class CloudUrlResponse(BaseModel):
    """云URL响应"""
    url: Optional[str] = None
    uploadStatus: str


@router.get("/temp-images/{attachment_id}")
async def get_temp_image(
    attachment_id: str,
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
    # 查询附件
    attachment = db.query(MessageAttachment).filter_by(
        id=attachment_id,
        user_id=current_user  # ✅ 权限检查：验证用户是否有权限访问该附件
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # 检查temp_url
    if not attachment.temp_url:
        # temp_url为空 → 可能已上传完成，返回云URL重定向
        if attachment.url and attachment.upload_status == 'completed':
            return RedirectResponse(url=attachment.url)
        else:
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
    try:
        attachment_service = AttachmentService(db)
        
        resolved = await attachment_service.resolve_continuity_attachment(
            active_image_url=request_body.activeImageUrl,
            session_id=request_body.sessionId,
            user_id=user_id,
            messages=request_body.messages or []
        )
        
        if not resolved:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        return {
            "attachmentId": resolved["attachment_id"],
            "url": resolved["url"],
            "status": resolved["status"],
            "taskId": resolved.get("task_id")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Attachments] Failed to resolve continuity: {e}", exc_info=True)
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
            uploadStatus=attachment.upload_status or "pending"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Attachments] Failed to get cloud URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
