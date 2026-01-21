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

# Get logger - it will propagate to root logger which has handler configured
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Ensure propagation is enabled (default is True, but make it explicit)
logger.propagate = True

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
        reference_images 字典，格式：
        - 如果只有 URL：{'raw': 'data:image/png;base64,...'}
        - 如果有 attachment_id：{'raw': {'url': 'data:image/png;base64,...', 'attachment_id': 'xxx', 'mimeType': 'image/png'}}
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
        
        # ✅ 如果有 attachment_id，传递字典格式（包含 attachment_id 和 url）
        # 如果没有 attachment_id，传递字符串格式（向后兼容）
        if attachment.id:
            ref_data = {
                'url': image_data,
                'attachment_id': attachment.id,
                'mimeType': attachment.mimeType or 'image/png'
            }
        else:
            ref_data = image_data  # 向后兼容：只传递 URL 字符串
        
        # 根据 role 设置键名
        if attachment.role == 'mask':
            reference_images['mask'] = ref_data
        else:
            # 默认作为 raw 图片（如果还没有 raw）
            if 'raw' not in reference_images:
                reference_images['raw'] = ref_data
            else:
                # 如果有多个非 mask 图片，使用列表或追加
                if isinstance(reference_images.get('raw'), list):
                    reference_images['raw'].append(ref_data)
                else:
                    reference_images['raw'] = [reference_images['raw'], ref_data]
    
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
    import time
    import sys
    
    # ✅ 立即输出日志，确保能看到请求到达（使用多种方式确保输出）
    request_start_time = time.time()
    logger.info(f"[Modes] ========== 开始处理模式请求 ==========")
    logger.info(f"[Modes] 📥 请求到达: {provider}/{mode}")
    # 同时使用 print 作为备用（确保能看到输出）
    
    try:
        # ✅ 记录 token 来源（用于诊断 user_id 不一致问题）
        auth_header = request.headers.get("Authorization")
        cookie_token = request.cookies.get("access_token")
        token_source = "未知"
        if auth_header:
            token_source = "Authorization header"
        elif cookie_token:
            token_source = "Cookie (access_token)"
        else:
            token_source = "无 token"
        
        logger.info(f"[Modes] 📥 请求信息:")
        logger.info(f"[Modes]     - provider: {provider}")
        logger.info(f"[Modes]     - mode: {mode}")
        logger.info(f"[Modes]     - user_id: {user_id[:8]}...")
        logger.info(f"[Modes]     - token来源: {token_source}")
        logger.info(f"[Modes]     - 有Authorization header: {'是' if auth_header else '否'}")
        logger.info(f"[Modes]     - 有Cookie token: {'是' if cookie_token else '否'}")
        logger.info(f"[Modes]     - modelId: {request_body.modelId}")
        logger.info(f"[Modes]     - prompt长度: {len(request_body.prompt)}")
        logger.info(f"[Modes]     - attachments数量: {len(request_body.attachments) if request_body.attachments else 0}")

        # ✅ 1. 获取凭证
        logger.info(f"[Modes] 🔄 [步骤1] 获取提供商凭证...")
        credential_start = time.time()
        api_key, api_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request_body.apiKey,
            request_base_url=request_body.options.baseUrl if request_body.options else None
        )
        credential_time = (time.time() - credential_start) * 1000
        logger.info(f"[Modes] ✅ [步骤1] 凭证获取完成 (耗时: {credential_time:.2f}ms)")
        logger.info(f"[Modes]     - api_key: {'已设置' if api_key else 'None'}")
        logger.info(f"[Modes]     - api_url: {api_url[:80] + '...' if api_url and len(api_url) > 80 else api_url or 'None'}")

        # ✅ 2. 创建提供商服务（如 GoogleService）
        logger.info(f"[Modes] 🔄 [步骤2] 创建提供商服务...")
        service_start = time.time()
        service = ProviderFactory.create(
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            user_id=user_id,
            db=db
        )
        service_time = (time.time() - service_start) * 1000
        service_type = type(service).__name__
        logger.info(f"[Modes] ✅ [步骤2] 服务创建完成 (耗时: {service_time:.2f}ms)")
        logger.info(f"[Modes]     - service类型: {service_type}")

        # ✅ 3. 根据 mode 获取服务方法名
        logger.info(f"[Modes] 🔄 [步骤3] 获取服务方法名...")
        method_name = get_service_method(mode)
        if not method_name:
            logger.error(f"[Modes] ❌ [步骤3] 不支持的模式: {mode}")
            raise ValueError(f"Unsupported mode: {mode}")
        logger.info(f"[Modes] ✅ [步骤3] 方法名: {method_name}")

        # ✅ 4. 检查服务是否支持该方法
        logger.info(f"[Modes] 🔄 [步骤4] 检查服务是否支持方法...")
        if not hasattr(service, method_name):
            logger.error(f"[Modes] ❌ [步骤4] 服务不支持方法: {service_type}.{method_name}")
            raise ValueError(f"Provider '{provider}' does not support method '{method_name}' for mode '{mode}'")
        logger.info(f"[Modes] ✅ [步骤4] 服务支持方法: {service_type}.{method_name}")

        # ✅ 5. 准备参数
        logger.info(f"[Modes] 🔄 [步骤5] 准备调用参数...")
        param_start = time.time()
        method = getattr(service, method_name)
        
        # 构建调用参数
        params = {
            "model": request_body.modelId,
            "prompt": request_body.prompt,
        }
        logger.info(f"[Modes]     - 基础参数已设置: model={params['model']}, prompt长度={len(params['prompt'])}")
        
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
            logger.info(f"[Modes]     - 已添加 options 参数: {len(options_dict)} 个")
        
        # 添加 extra 参数
        if request_body.extra:
            params.update(request_body.extra)
            logger.info(f"[Modes]     - 已添加 extra 参数: {len(request_body.extra)} 个")
        
        # **重要**：对于 edit_image 方法，需要传递 mode 参数
        # GoogleService.edit_image() 会根据 mode 参数智能分发到不同的子服务
        if method_name == "edit_image":
            # 将 URL 路径中的 mode 参数传递给 edit_image 方法
            params["mode"] = mode
        
        # ✅ **新增**：处理 Edit 模式的 CONTINUITY LOGIC
        # 如果提供了 activeImageUrl，使用 AttachmentService 解析
        if method_name == "edit_image" and request_body.options and request_body.options.activeImageUrl:
            import time
            continuity_start_time = time.time()
            
            logger.info(f"[Modes] ========== 开始处理Edit模式的CONTINUITY LOGIC ==========")
            logger.info(f"[Modes] 📥 CONTINUITY参数:")
            logger.info(f"[Modes]     - method_name: {method_name}")
            url_type = 'Blob' if request_body.options.activeImageUrl.startswith('blob:') else 'Base64' if request_body.options.activeImageUrl.startswith('data:') else 'HTTP' if request_body.options.activeImageUrl.startswith('http') else '未知'
            logger.info(f"[Modes]     - activeImageUrl类型: {url_type}")
            logger.info(f"[Modes]     - activeImageUrl长度: {len(request_body.options.activeImageUrl)}")
            
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息列表
            session_id = request_body.options.frontend_session_id or request_body.options.sessionId
            if session_id:
                logger.info(f"[Modes] 🔍 获取会话ID和消息列表...")
                logger.info(f"[Modes]     - session_id: {session_id[:8]}...")
                
                # 从 extra 中获取 messages，如果为空则从数据库查询
                messages = []
                if request_body.extra and "messages" in request_body.extra:
                    messages = request_body.extra["messages"]
                    logger.info(f"[Modes]     - 从 extra 中获取 messages: {len(messages)} 条")
                elif session_id:
                    # 从数据库查询会话的所有消息（用于CONTINUITY LOGIC查找附件）
                    logger.info(f"[Modes]     - 从数据库查询会话消息...")
                    from ...models.db_models import Message
                    db_messages = db.query(Message).filter_by(session_id=session_id).order_by(Message.timestamp.asc()).all()
                    messages = [msg.to_dict() for msg in db_messages if hasattr(msg, 'to_dict')]
                    logger.info(f"[Modes]     - 从数据库查询到 {len(messages)} 条消息")
                
                # 解析 CONTINUITY 附件
                logger.info(f"[Modes] 🔄 调用 AttachmentService.resolve_continuity_attachment()...")
                resolved = await attachment_service.resolve_continuity_attachment(
                    active_image_url=request_body.options.activeImageUrl,
                    session_id=session_id,
                    user_id=user_id,
                    messages=messages
                )
                
                continuity_elapsed = (time.time() - continuity_start_time) * 1000
                
                if resolved:
                    # 将解析的附件添加到 reference_images
                    if "reference_images" not in params:
                        params["reference_images"] = {}
                    params["reference_images"]["raw"] = resolved["url"]
                    
                    has_cloud_url = resolved["status"] == "completed" and resolved["url"] and resolved["url"].startswith("http")
                    logger.info(f"[Modes] ✅ CONTINUITY附件解析成功 (耗时: {continuity_elapsed:.2f}ms):")
                    logger.info(f"[Modes]     - attachment_id: {resolved['attachment_id'][:8]}...")
                    logger.info(f"[Modes]     - status: {resolved['status']}")
                    logger.info(f"[Modes]     - hasCloudUrl: {has_cloud_url}")
                    url_display = resolved['url'][:80] + '...' if resolved['url'] and len(resolved['url']) > 80 else resolved['url'] or 'None'
                    logger.info(f"[Modes]     - url: {url_display}")
                    task_id_display = resolved.get('task_id', 'None')[:8] + '...' if resolved.get('task_id') else 'None'
                    logger.info(f"[Modes]     - taskId: {task_id_display}")
                    logger.info(f"[Modes]     - 已添加到 reference_images.raw")
                    logger.info(f"[Modes] ========== CONTINUITY LOGIC处理完成 ==========")
                else:
                    logger.warning(f"[Modes] ⚠️ CONTINUITY附件解析失败 (耗时: {continuity_elapsed:.2f}ms): 未找到匹配的附件")
            else:
                logger.warning(f"[Modes] ⚠️ 跳过CONTINUITY LOGIC: 未提供 session_id")
        
        # **特殊处理**：对于需要文件数据的方法（pdf-extract, virtual-try-on, segment-clothing 等）
        # 从 attachments 中提取数据
        if request_body.attachments:
            logger.info(f"[Modes]     - 处理 attachments: {len(request_body.attachments)} 个")
            reference_images = convert_attachments_to_reference_images(request_body.attachments)
            
            # ✅ 如果有 attachment_id，查找数据库中的附件信息
            if reference_images and 'raw' in reference_images:
                raw_data = reference_images['raw']
                if isinstance(raw_data, dict) and 'attachment_id' in raw_data:
                    attachment_id = raw_data['attachment_id']
                    
                    # 从数据库查询附件信息
                    from ...models.db_models import MessageAttachment
                    db_attachment = db.query(MessageAttachment).filter_by(
                        id=attachment_id,
                        user_id=user_id
                    ).first()
                    
                    if db_attachment:
                        logger.info(f"[Modes] ✅ 找到数据库中的附件: attachment_id={attachment_id[:8]}...")
                        logger.info(f"[Modes]     - upload_status: {db_attachment.upload_status}")
                        logger.info(f"[Modes]     - has_url: {bool(db_attachment.url)}")
                        logger.info(f"[Modes]     - has_temp_url: {bool(db_attachment.temp_url)}")
                        
                        # ✅ 如果已上传完成，优先使用 url（云端永久 URL）
                        if db_attachment.upload_status == 'completed' and db_attachment.url:
                            raw_data['url'] = db_attachment.url
                            logger.info(f"[Modes]     - 使用云存储 URL: {db_attachment.url[:60]}...")
                        # ✅ 如果未上传完成，使用 temp_url（Base64）
                        elif db_attachment.temp_url:
                            raw_data['url'] = db_attachment.temp_url
                            logger.info(f"[Modes]     - 使用临时 URL (Base64)")
                        
                        # 更新 reference_images
                        reference_images['raw'] = raw_data
                    else:
                        logger.warning(f"[Modes] ⚠️ 未找到数据库中的附件: attachment_id={attachment_id[:8]}...")
            
            if reference_images:
                params["reference_images"] = reference_images
                logger.info(f"[Modes]     - 已转换 reference_images: {len(reference_images)} 个")
            
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
        
        param_time = (time.time() - param_start) * 1000
        logger.info(f"[Modes] ✅ [步骤5] 参数准备完成 (耗时: {param_time:.2f}ms)")
        logger.info(f"[Modes]     - 最终参数数量: {len(params)}")
        logger.info(f"[Modes]     - 参数键: {list(params.keys())}")

        # ✅ 6. 调用服务方法（服务内部会分发到子服务）
        logger.info(f"[Modes] 🔄 [步骤6] 调用服务方法: {service_type}.{method_name}()...")
        logger.info(f"[Modes]     - 参数数量: {len(params)}")
        logger.info(f"[Modes]     - 关键参数:")
        logger.info(f"[Modes]         - model: {params.get('model', 'None')}")
        logger.info(f"[Modes]         - prompt: {params.get('prompt', 'None')[:100] + '...' if params.get('prompt') and len(params.get('prompt', '')) > 100 else params.get('prompt', 'None')}")
        if 'number_of_images' in params:
            logger.info(f"[Modes]         - number_of_images: {params.get('number_of_images')}")
        if 'aspect_ratio' in params:
            logger.info(f"[Modes]         - aspect_ratio: {params.get('aspect_ratio')}")
        if 'image_size' in params:
            logger.info(f"[Modes]         - image_size: {params.get('image_size')}")
        if 'reference_images' in params:
            ref_images = params.get('reference_images', {})
            logger.info(f"[Modes]         - reference_images: {len(ref_images)} 个引用图片")
        
        method_start = time.time()
        try:
            result = await method(**params)
        except Exception as method_error:
            # ✅ 捕获图片生成/编辑时的错误（如 API Key 过期、API 错误等）
            method_time = (time.time() - method_start) * 1000
            logger.error(f"[Modes] ❌ [步骤6] 服务方法调用失败 (耗时: {method_time:.2f}ms): {method_error}")
            
            # 对于图片生成/编辑模式，需要返回友好的错误信息
            if method_name in ["generate_image", "edit_image"]:
                # 检查是否是 API 相关错误
                from ...services.gemini.imagen_common import APIError
                if isinstance(method_error, APIError):
                    error_message = str(method_error)
                    # 提取原始错误信息（如果是 API Key 过期等）
                    if hasattr(method_error, 'original_error'):
                        orig_error = method_error.original_error
                        if orig_error and 'API key' in str(orig_error):
                            error_message = "API Key 已过期或无效，请更新 API Key"
                    raise HTTPException(
                        status_code=400,
                        detail=f"图片生成失败: {error_message}"
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"图片生成失败: {str(method_error)}"
                    )
            else:
                # 其他模式，直接抛出原始异常
                raise
        
        method_time = (time.time() - method_start) * 1000
        
        logger.info(f"[Modes] ✅ [步骤6] 服务方法调用完成 (耗时: {method_time:.2f}ms)")
        if isinstance(result, list):
            logger.info(f"[Modes]     - 返回结果: {len(result)} 个图片")
        elif isinstance(result, dict):
            logger.info(f"[Modes]     - 返回结果: 字典格式")
            if 'images' in result:
                logger.info(f"[Modes]     - 图片数量: {len(result.get('images', []))}")
        else:
            logger.info(f"[Modes]     - 返回结果类型: {type(result).__name__}")

        # ✅ 7. **新增**：处理图片生成和编辑的结果（使用 AttachmentService）
        # 对于 image-gen 和 image-edit 模式，处理返回的图片
        if method_name in ["generate_image", "edit_image"]:
            logger.info(f"[Modes] 🔄 [步骤7] 处理图片生成/编辑结果...")
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息ID
            session_id = None
            message_id = None
            if request_body.options:
                session_id = request_body.options.frontend_session_id or request_body.options.sessionId
                message_id = request_body.options.message_id
            
            logger.info(f"[Modes]     - session_id: {session_id[:8] + '...' if session_id else 'None'}")
            logger.info(f"[Modes]     - message_id: {message_id[:8] + '...' if message_id else 'None'}")
            
            # ✅ 如果缺少 messageId，记录警告但继续处理（不阻塞）
            if not message_id:
                logger.warning(f"[Modes] ⚠️ 缺少 message_id，附件将不会保存到数据库")
            
            if session_id and message_id:
                processed_images = []
                
                # 处理返回的图片列表
                # 结果格式可能是 List[Dict] 或 List[ImageGenerationResult]
                images = result if isinstance(result, list) else result.get("images", []) if isinstance(result, dict) else []
                logger.info(f"[Modes]     - 需要处理的图片数量: {len(images)}")
                
                for idx, img in enumerate(images):
                    logger.info(f"[Modes] 🔄 [步骤7] 处理第 {idx+1}/{len(images)} 张图片...")
                    
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
                        logger.warning(f"[Modes] ⚠️ 第 {idx+1} 张图片缺少URL，跳过")
                        continue
                    
                    url_type = "Base64" if ai_url.startswith('data:') else "HTTP" if ai_url.startswith('http') else "其他"
                    logger.info(f"[Modes]     - 图片URL类型: {url_type}")
                    logger.info(f"[Modes]     - mime_type: {mime_type}")
                    
                    # 使用 AttachmentService 处理AI返回的图片
                    prefix = "generated" if method_name == "generate_image" else "edited"
                    logger.info(f"[Modes]     - 调用 AttachmentService.process_ai_result()...")
                    processed = await attachment_service.process_ai_result(
                        ai_url=ai_url,
                        mime_type=mime_type,
                        session_id=session_id,
                        message_id=message_id,
                        user_id=user_id,
                        prefix=prefix
                    )
                    
                    logger.info(f"[Modes] ✅ [步骤7] 第 {idx+1} 张图片处理完成:")
                    logger.info(f"[Modes]     - attachment_id: {processed['attachment_id'][:8]}...")
                    logger.info(f"[Modes]     - status: {processed['status']}")
                    logger.info(f"[Modes]     - task_id: {processed.get('task_id', 'None')[:8] + '...' if processed.get('task_id') else 'None'}")
                    
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
                
                logger.info(f"[Modes] ✅ [步骤7] 所有图片处理完成: {len(processed_images)} 张")
            else:
                logger.warning(f"[Modes] ⚠️ [步骤7] 跳过附件处理: 缺少 session_id 或 message_id")
        
        # ✅ 8. 返回响应
        total_time = (time.time() - request_start_time) * 1000
        logger.info(f"[Modes] ========== 模式请求处理完成 (总耗时: {total_time:.2f}ms) ==========")
        logger.info(f"[Modes]     - provider: {provider}")
        logger.info(f"[Modes]     - mode: {mode}")
        logger.info(f"[Modes]     - 成功: True")
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
