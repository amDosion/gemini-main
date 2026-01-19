"""
统一模式路由

所有非聊天模式都通过此路由处理。
路由层只负责：
1. 接收请求
2. 参数验证
3. 用户认证（使用 Depends）
4. 获取凭证
5. 创建提供商服务（ProviderFactory）
6. 根据 mode 调用服务方法
7. 返回响应

不包含任何业务逻辑，业务逻辑在服务层。
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import json
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.credential_manager import get_provider_credentials
from ...core.mode_method_mapper import get_service_method, is_streaming_mode, is_image_edit_mode
from ...services.common.provider_factory import ProviderFactory
from ...services.common.attachment_service import AttachmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modes", tags=["modes"])


# ==================== Request/Response Models ====================

class Attachment(BaseModel):
    """Attachment model (images, files, etc.)"""
    id: Optional[str] = None
    mimeType: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None
    tempUrl: Optional[str] = None
    fileUri: Optional[str] = None
    base64Data: Optional[str] = None
    role: Optional[str] = None  # 'mask' for mask images, etc.


class ModeOptions(BaseModel):
    """Mode options - flexible dict-like structure"""
    baseUrl: Optional[str] = None
    temperature: Optional[float] = None
    maxTokens: Optional[int] = None
    topP: Optional[float] = None
    topK: Optional[int] = None
    enableSearch: Optional[bool] = None
    enableThinking: Optional[bool] = None
    # Image generation options
    size: Optional[str] = None
    quality: Optional[str] = None
    style: Optional[str] = None
    numberOfImages: Optional[int] = None
    aspectRatio: Optional[str] = None
    imageAspectRatio: Optional[str] = None
    imageResolution: Optional[str] = None
    imageStyle: Optional[str] = None
    # Image editing options
    edit_mode: Optional[str] = None
    number_of_images: Optional[int] = None
    frontend_session_id: Optional[str] = None
    sessionId: Optional[str] = None  # Alias for frontend_session_id
    message_id: Optional[str] = None  # 消息ID（用于附件关联）
    # ✅ Edit模式新增字段
    activeImageUrl: Optional[str] = None  # CONTINUITY LOGIC用
    # Other options
    negativePrompt: Optional[str] = None
    guidanceScale: Optional[float] = None
    seed: Optional[int] = None
    # Allow additional fields
    class Config:
        extra = "allow"


class ModeRequest(BaseModel):
    """统一模式请求"""
    modelId: str
    prompt: str
    attachments: Optional[List[Attachment]] = None
    options: Optional[ModeOptions] = None
    apiKey: Optional[str] = None  # Optional, will try to get from database
    extra: Optional[Dict[str, Any]] = None  # Additional parameters


class ModeResponse(BaseModel):
    """统一模式响应"""
    success: bool
    data: Any
    provider: str
    mode: str
    error: Optional[str] = None


# ==================== Helper Functions ====================

def convert_attachments_to_reference_images(attachments: Optional[List[Attachment]]) -> Dict[str, Any]:
    """
    将 attachments 转换为 reference_images 字典格式
    
    Args:
        attachments: 附件列表
        
    Returns:
        reference_images 字典，格式：{'raw': base64_image, 'mask': base64_mask, ...}
    """
    if not attachments:
        return {}
    
    reference_images = {}
    for attachment in attachments:
        # 获取图片数据（优先级：url > tempUrl > fileUri > base64Data）
        image_data = None
        if attachment.url:
            image_data = attachment.url
        elif attachment.tempUrl:
            image_data = attachment.tempUrl
        elif attachment.fileUri:
            image_data = attachment.fileUri
        elif attachment.base64Data:
            image_data = attachment.base64Data
        
        if not image_data:
            continue
        
        # 根据 role 设置键名
        if attachment.role == 'mask':
            reference_images['mask'] = image_data
        else:
            # 默认作为 raw 图片（如果还没有 raw）
            if 'raw' not in reference_images:
                reference_images['raw'] = image_data
            else:
                # 如果有多个非 mask 图片，使用列表或追加
                if isinstance(reference_images.get('raw'), list):
                    reference_images['raw'].append(image_data)
                else:
                    reference_images['raw'] = [reference_images['raw'], image_data]
    
    return reference_images


# ==================== API Endpoints ====================

@router.post("/{provider}/{mode}")
async def handle_mode(
    provider: str,
    mode: str,
    request_body: ModeRequest,
    request: Request,
    user_id: str = Depends(require_current_user),  # ✅ 自动注入 user_id
    db: Session = Depends(get_db)
):
    """
    统一的模式处理端点

    根据 provider 和 mode 参数，直接调用提供商服务的对应方法。
    服务内部会根据 mode 分发到子服务。

    Args:
        provider: 提供商名称 (google, tongyi, openai, etc.)
        mode: 模式名称 (image-gen, image-edit, video-gen, etc.)
        request_body: 请求体
        request: FastAPI 请求对象
        user_id: 用户 ID（自动注入）
        db: 数据库会话

    Returns:
        ModeResponse: 统一的响应格式
    """
    try:
        logger.info(f"[Modes] Request: provider={provider}, mode={mode}, user_id={user_id}")

        # ✅ 1. 获取凭证
        api_key, api_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request_body.apiKey,
            request_base_url=request_body.options.baseUrl if request_body.options else None
        )

        # ✅ 2. 创建提供商服务（如 GoogleService）
        service = ProviderFactory.create(
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            user_id=user_id,
            db=db
        )

        # ✅ 3. 根据 mode 获取服务方法名
        method_name = get_service_method(mode)
        if not method_name:
            raise ValueError(f"Unsupported mode: {mode}")

        # ✅ 4. 检查服务是否支持该方法
        if not hasattr(service, method_name):
            raise ValueError(f"Provider '{provider}' does not support method '{method_name}' for mode '{mode}'")

        # ✅ 5. 准备参数
        method = getattr(service, method_name)
        
        # 构建调用参数
        params = {
            "model": request_body.modelId,
            "prompt": request_body.prompt,
        }
        
        # **特殊处理**：根据方法类型调整参数
        # - generate_speech 需要 text 和 voice 参数
        if method_name == "generate_speech":
            params["text"] = request_body.prompt
            # 从 options 中获取 voice，如果没有则使用默认值
            if request_body.options and hasattr(request_body.options, "voice") and request_body.options.voice:
                params["voice"] = request_body.options.voice
            else:
                params["voice"] = "alloy"  # 默认语音
        
        # 添加 options 中的参数
        if request_body.options:
            options_dict = request_body.options.dict(exclude_none=True)
            # 对于 generate_speech，voice 已经在上面处理，避免重复
            if method_name == "generate_speech" and "voice" in options_dict:
                options_dict.pop("voice", None)
            params.update(options_dict)
        
        # 添加 extra 参数
        if request_body.extra:
            params.update(request_body.extra)
        
        # **重要**：对于 edit_image 方法，需要传递 mode 参数
        # GoogleService.edit_image() 会根据 mode 参数智能分发到不同的子服务
        if method_name == "edit_image":
            # 将 URL 路径中的 mode 参数传递给 edit_image 方法
            params["mode"] = mode
        
        # ✅ **新增**：处理 Edit 模式的 CONTINUITY LOGIC
        # 如果提供了 activeImageUrl，使用 AttachmentService 解析
        if method_name == "edit_image" and request_body.options and request_body.options.activeImageUrl:
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息列表
            session_id = request_body.options.frontend_session_id or request_body.options.sessionId
            if session_id:
                # 从 extra 中获取 messages，如果为空则从数据库查询
                messages = []
                if request_body.extra and "messages" in request_body.extra:
                    messages = request_body.extra["messages"]
                elif session_id:
                    # 从数据库查询会话的所有消息（用于CONTINUITY LOGIC查找附件）
                    from ...models.db_models import Message
                    db_messages = db.query(Message).filter_by(session_id=session_id).order_by(Message.timestamp.asc()).all()
                    messages = [msg.to_dict() for msg in db_messages if hasattr(msg, 'to_dict')]
                
                # 解析 CONTINUITY 附件
                resolved = await attachment_service.resolve_continuity_attachment(
                    active_image_url=request_body.options.activeImageUrl,
                    session_id=session_id,
                    user_id=user_id,
                    messages=messages
                )
                
                if resolved:
                    # 将解析的附件添加到 reference_images
                    if "reference_images" not in params:
                        params["reference_images"] = {}
                    params["reference_images"]["raw"] = resolved["url"]
                    logger.info(f"[Modes] CONTINUITY attachment resolved: {resolved['attachment_id'][:8]}...")
        
        # **特殊处理**：对于需要文件数据的方法（pdf-extract, virtual-try-on, segment-clothing 等）
        # 从 attachments 中提取数据
        if request_body.attachments:
            reference_images = convert_attachments_to_reference_images(request_body.attachments)
            if reference_images:
                params["reference_images"] = reference_images
            
            # 对于 segment-clothing，需要从 attachments 中提取图像数据
            if method_name == "segment_clothing":
                # 查找图像附件并添加到 reference_images
                for attachment in request_body.attachments:
                    if attachment.mimeType and "image" in attachment.mimeType.lower():
                        # 如果有 base64Data，直接使用
                        if attachment.base64Data:
                            image_data = attachment.base64Data
                            if image_data.startswith("data:"):
                                image_data = image_data.split(",", 1)[1]
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["raw"] = image_data
                        # 如果有 URL，需要下载（在服务层处理）
                        elif attachment.url or attachment.tempUrl:
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["raw_url"] = attachment.url or attachment.tempUrl
                        break
                # 从 extra 中获取 target_clothing
                if request_body.extra and "target_clothing" in request_body.extra:
                    params["target_clothing"] = request_body.extra["target_clothing"]
            
            # 对于 pdf-extract，需要从 attachments 中提取 PDF 数据
            if method_name == "extract_pdf_data":
                # 查找 PDF 附件
                for attachment in request_body.attachments:
                    if attachment.mimeType and "pdf" in attachment.mimeType.lower():
                        # 如果有 base64Data，直接使用
                        if attachment.base64Data:
                            import base64
                            # 移除 data URI 前缀（如果有）
                            pdf_data = attachment.base64Data
                            if pdf_data.startswith("data:"):
                                pdf_data = pdf_data.split(",", 1)[1]
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["pdf_bytes"] = base64.b64decode(pdf_data)
                        # 如果有 URL，需要下载（在服务层处理）
                        elif attachment.url or attachment.tempUrl:
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["pdf_url"] = attachment.url or attachment.tempUrl
                        break

        # ✅ 6. 调用服务方法（服务内部会分发到子服务）
        result = await method(**params)

        # ✅ 7. **新增**：处理图片生成和编辑的结果（使用 AttachmentService）
        # 对于 image-gen 和 image-edit 模式，处理返回的图片
        if method_name in ["generate_image", "edit_image"]:
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息ID
            session_id = None
            message_id = None
            if request_body.options:
                session_id = request_body.options.frontend_session_id or request_body.options.sessionId
                message_id = request_body.options.message_id
            
            # ✅ 如果缺少 messageId，记录警告但继续处理（不阻塞）
            if not message_id:
                logger.warning(f"[Modes] Missing message_id for {method_name}, attachment will not be saved to database")
            
            if session_id and message_id:
                processed_images = []
                
                # 处理返回的图片列表
                # 结果格式可能是 List[Dict] 或 List[ImageGenerationResult]
                images = result if isinstance(result, list) else result.get("images", []) if isinstance(result, dict) else []
                
                for img in images:
                    # 提取图片URL和MIME类型
                    # 支持多种格式：Dict 或 ImageGenerationResult
                    if isinstance(img, dict):
                        ai_url = img.get("url") or img.get("image")
                        mime_type = img.get("mimeType") or img.get("mime_type", "image/png")
                        filename = img.get("filename")  # ✅ 提取 filename（如果有）
                    else:
                        # ImageGenerationResult 对象
                        ai_url = img.url if hasattr(img, "url") else None
                        mime_type = img.mime_type if hasattr(img, "mime_type") else "image/png"
                        filename = img.filename if hasattr(img, "filename") else None
                    
                    if not ai_url:
                        logger.warning(f"[Modes] Image result missing URL: {img}")
                        continue
                    
                    # 使用 AttachmentService 处理AI返回的图片
                    prefix = "generated" if method_name == "generate_image" else "edited"
                    processed = await attachment_service.process_ai_result(
                        ai_url=ai_url,
                        mime_type=mime_type,
                        session_id=session_id,
                        message_id=message_id,
                        user_id=user_id,
                        prefix=prefix
                    )
                    
                    # ✅ 构建响应格式（包含完整字段）
                    processed_images.append({
                        "url": processed["display_url"],  # 显示URL（前端立即显示）
                        "attachmentId": processed["attachment_id"],
                        "uploadStatus": processed["status"],
                        "taskId": processed["task_id"],
                        "mimeType": mime_type,  # ✅ 新增：MIME类型
                        "filename": filename or f"{prefix}-{processed['attachment_id'][:8]}.png"  # ✅ 新增：文件名（修复：使用正确的格式）
                    })
                
                # 更新结果
                if isinstance(result, dict):
                    result["images"] = processed_images
                else:
                    result = processed_images
                
                logger.info(f"[Modes] Processed {len(processed_images)} images with AttachmentService")
        
        # ✅ 8. 返回响应
        logger.info(f"[Modes] Success: provider={provider}, mode={mode}")
        return ModeResponse(
            success=True,
            data=result,
            provider=provider,
            mode=mode
        )

    except ValueError as e:
        logger.warning(f"[Modes] Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Modes] Error: provider={provider}, mode={mode}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{provider}/{mode}/stream")
async def handle_mode_stream(
    provider: str,
    mode: str,
    request_body: ModeRequest,
    request: Request,
    user_id: str = Depends(require_current_user),  # ✅ 自动注入 user_id
    db: Session = Depends(get_db)
):
    """
    统一的流式模式处理端点

    支持流式响应的模式（如聊天）

    Args:
        provider: 提供商名称
        mode: 模式名称
        request_body: 请求体
        request: FastAPI 请求对象
        user_id: 用户 ID（自动注入）
        db: 数据库会话

    Returns:
        StreamingResponse: SSE 流式响应
    """
    try:
        logger.info(f"[Modes] Stream request: provider={provider}, mode={mode}, user_id={user_id}")

        # ✅ 1. 获取凭证
        api_key, api_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request_body.apiKey,
            request_base_url=request_body.options.baseUrl if request_body.options else None
        )

        # ✅ 2. 创建提供商服务
        service = ProviderFactory.create(
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            user_id=user_id,
            db=db
        )

        # ✅ 3. 获取服务方法
        method_name = get_service_method(mode)
        if not method_name or not is_streaming_mode(mode):
            raise ValueError(f"Mode '{mode}' does not support streaming")

        method = getattr(service, method_name)
        if not method:
            raise ValueError(f"Provider '{provider}' does not support method '{method_name}'")

        # ✅ 4. 准备参数
        params = {
            "model": request_body.modelId,
        }
        
        # 对于聊天模式，需要 messages 参数
        if mode == "chat":
            # 将 attachments 转换为 messages 格式
            if request_body.attachments:
                params["messages"] = request_body.attachments
            else:
                # 如果没有 attachments，使用 prompt 作为消息
                params["messages"] = [{"role": "user", "content": request_body.prompt}]
        else:
            params["prompt"] = request_body.prompt
        
        # 添加 options 中的参数
        if request_body.options:
            options_dict = request_body.options.dict(exclude_none=True)
            params.update(options_dict)
        
        # 添加 extra 参数
        if request_body.extra:
            params.update(request_body.extra)

        # ✅ 5. 流式响应
        async def generate():
            try:
                # 调用流式方法
                async for chunk in method(**params):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"[Modes] Stream error: {e}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Modes] Stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
