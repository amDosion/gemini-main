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
    import time
    import sys
    
    # ✅ 立即输出日志，确保能看到请求到达（使用多种方式确保输出）
    request_start_time = time.time()
    logger.info(f"[Modes] ========== 开始处理模式请求 ==========")
    logger.info(f"[Modes] 📥 请求到达: {provider}/{mode}")
    # 同时使用 print 作为备用（确保能看到输出）
    print(f"[Modes] ========== 开始处理模式请求 ==========", file=sys.stderr, flush=True)
    print(f"[Modes] 📥 请求到达: {provider}/{mode}", file=sys.stderr, flush=True)
    
    try:
        logger.info(f"[Modes] 📥 请求信息:")
        print(f"[Modes] 📥 请求信息:", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - provider: {provider}")
        print(f"[Modes]     - provider: {provider}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - mode: {mode}")
        print(f"[Modes]     - mode: {mode}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - user_id: {user_id[:8]}...")
        print(f"[Modes]     - user_id: {user_id[:8]}...", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - modelId: {request_body.modelId}")
        print(f"[Modes]     - modelId: {request_body.modelId}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - prompt长度: {len(request_body.prompt)}")
        print(f"[Modes]     - prompt长度: {len(request_body.prompt)}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - attachments数量: {len(request_body.attachments) if request_body.attachments else 0}")
        print(f"[Modes]     - attachments数量: {len(request_body.attachments) if request_body.attachments else 0}", file=sys.stderr, flush=True)

        # ✅ 1. 获取凭证
        logger.info(f"[Modes] 🔄 [步骤1] 获取提供商凭证...")
        print(f"[Modes] 🔄 [步骤1] 获取提供商凭证...", file=sys.stderr, flush=True)
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
        print(f"[Modes] ✅ [步骤1] 凭证获取完成 (耗时: {credential_time:.2f}ms)", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - api_key: {'已设置' if api_key else 'None'}")
        print(f"[Modes]     - api_key: {'已设置' if api_key else 'None'}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - api_url: {api_url[:80] + '...' if api_url and len(api_url) > 80 else api_url or 'None'}")
        print(f"[Modes]     - api_url: {api_url[:80] + '...' if api_url and len(api_url) > 80 else api_url or 'None'}", file=sys.stderr, flush=True)

        # ✅ 2. 创建提供商服务（如 GoogleService）
        logger.info(f"[Modes] 🔄 [步骤2] 创建提供商服务...")
        print(f"[Modes] 🔄 [步骤2] 创建提供商服务...", file=sys.stderr, flush=True)
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
        print(f"[Modes] ✅ [步骤2] 服务创建完成 (耗时: {service_time:.2f}ms)", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - service类型: {service_type}")
        print(f"[Modes]     - service类型: {service_type}", file=sys.stderr, flush=True)

        # ✅ 3. 根据 mode 获取服务方法名
        logger.info(f"[Modes] 🔄 [步骤3] 获取服务方法名...")
        print(f"[Modes] 🔄 [步骤3] 获取服务方法名...", file=sys.stderr, flush=True)
        method_name = get_service_method(mode)
        if not method_name:
            logger.error(f"[Modes] ❌ [步骤3] 不支持的模式: {mode}")
            print(f"[Modes] ❌ [步骤3] 不支持的模式: {mode}", file=sys.stderr, flush=True)
            raise ValueError(f"Unsupported mode: {mode}")
        logger.info(f"[Modes] ✅ [步骤3] 方法名: {method_name}")
        print(f"[Modes] ✅ [步骤3] 方法名: {method_name}", file=sys.stderr, flush=True)

        # ✅ 4. 检查服务是否支持该方法
        logger.info(f"[Modes] 🔄 [步骤4] 检查服务是否支持方法...")
        print(f"[Modes] 🔄 [步骤4] 检查服务是否支持方法...", file=sys.stderr, flush=True)
        if not hasattr(service, method_name):
            logger.error(f"[Modes] ❌ [步骤4] 服务不支持方法: {service_type}.{method_name}")
            print(f"[Modes] ❌ [步骤4] 服务不支持方法: {service_type}.{method_name}", file=sys.stderr, flush=True)
            raise ValueError(f"Provider '{provider}' does not support method '{method_name}' for mode '{mode}'")
        logger.info(f"[Modes] ✅ [步骤4] 服务支持方法: {service_type}.{method_name}")
        print(f"[Modes] ✅ [步骤4] 服务支持方法: {service_type}.{method_name}", file=sys.stderr, flush=True)

        # ✅ 5. 准备参数
        logger.info(f"[Modes] 🔄 [步骤5] 准备调用参数...")
        print(f"[Modes] 🔄 [步骤5] 准备调用参数...", file=sys.stderr, flush=True)
        param_start = time.time()
        method = getattr(service, method_name)
        
        # 构建调用参数
        params = {
            "model": request_body.modelId,
            "prompt": request_body.prompt,
        }
        logger.info(f"[Modes]     - 基础参数已设置: model={params['model']}, prompt长度={len(params['prompt'])}")
        print(f"[Modes]     - 基础参数已设置: model={params['model']}, prompt长度={len(params['prompt'])}", file=sys.stderr, flush=True)
        
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
            print(f"[Modes]     - 已添加 options 参数: {len(options_dict)} 个", file=sys.stderr, flush=True)
        
        # 添加 extra 参数
        if request_body.extra:
            params.update(request_body.extra)
            logger.info(f"[Modes]     - 已添加 extra 参数: {len(request_body.extra)} 个")
            print(f"[Modes]     - 已添加 extra 参数: {len(request_body.extra)} 个", file=sys.stderr, flush=True)
        
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
            print(f"[Modes] ========== 开始处理Edit模式的CONTINUITY LOGIC ==========", file=sys.stderr, flush=True)
            logger.info(f"[Modes] 📥 CONTINUITY参数:")
            print(f"[Modes] 📥 CONTINUITY参数:", file=sys.stderr, flush=True)
            logger.info(f"[Modes]     - method_name: {method_name}")
            print(f"[Modes]     - method_name: {method_name}", file=sys.stderr, flush=True)
            url_type = 'Blob' if request_body.options.activeImageUrl.startswith('blob:') else 'Base64' if request_body.options.activeImageUrl.startswith('data:') else 'HTTP' if request_body.options.activeImageUrl.startswith('http') else '未知'
            logger.info(f"[Modes]     - activeImageUrl类型: {url_type}")
            print(f"[Modes]     - activeImageUrl类型: {url_type}", file=sys.stderr, flush=True)
            logger.info(f"[Modes]     - activeImageUrl长度: {len(request_body.options.activeImageUrl)}")
            print(f"[Modes]     - activeImageUrl长度: {len(request_body.options.activeImageUrl)}", file=sys.stderr, flush=True)
            
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息列表
            session_id = request_body.options.frontend_session_id or request_body.options.sessionId
            if session_id:
                logger.info(f"[Modes] 🔍 获取会话ID和消息列表...")
                print(f"[Modes] 🔍 获取会话ID和消息列表...", file=sys.stderr, flush=True)
                logger.info(f"[Modes]     - session_id: {session_id[:8]}...")
                print(f"[Modes]     - session_id: {session_id[:8]}...", file=sys.stderr, flush=True)
                
                # 从 extra 中获取 messages，如果为空则从数据库查询
                messages = []
                if request_body.extra and "messages" in request_body.extra:
                    messages = request_body.extra["messages"]
                    logger.info(f"[Modes]     - 从 extra 中获取 messages: {len(messages)} 条")
                    print(f"[Modes]     - 从 extra 中获取 messages: {len(messages)} 条", file=sys.stderr, flush=True)
                elif session_id:
                    # 从数据库查询会话的所有消息（用于CONTINUITY LOGIC查找附件）
                    logger.info(f"[Modes]     - 从数据库查询会话消息...")
                    print(f"[Modes]     - 从数据库查询会话消息...", file=sys.stderr, flush=True)
                    from ...models.db_models import Message
                    db_messages = db.query(Message).filter_by(session_id=session_id).order_by(Message.timestamp.asc()).all()
                    messages = [msg.to_dict() for msg in db_messages if hasattr(msg, 'to_dict')]
                    logger.info(f"[Modes]     - 从数据库查询到 {len(messages)} 条消息")
                    print(f"[Modes]     - 从数据库查询到 {len(messages)} 条消息", file=sys.stderr, flush=True)
                
                # 解析 CONTINUITY 附件
                logger.info(f"[Modes] 🔄 调用 AttachmentService.resolve_continuity_attachment()...")
                print(f"[Modes] 🔄 调用 AttachmentService.resolve_continuity_attachment()...", file=sys.stderr, flush=True)
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
                    print(f"[Modes] ✅ CONTINUITY附件解析成功 (耗时: {continuity_elapsed:.2f}ms):", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - attachment_id: {resolved['attachment_id'][:8]}...")
                    print(f"[Modes]     - attachment_id: {resolved['attachment_id'][:8]}...", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - status: {resolved['status']}")
                    print(f"[Modes]     - status: {resolved['status']}", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - hasCloudUrl: {has_cloud_url}")
                    print(f"[Modes]     - hasCloudUrl: {has_cloud_url}", file=sys.stderr, flush=True)
                    url_display = resolved['url'][:80] + '...' if resolved['url'] and len(resolved['url']) > 80 else resolved['url'] or 'None'
                    logger.info(f"[Modes]     - url: {url_display}")
                    print(f"[Modes]     - url: {url_display}", file=sys.stderr, flush=True)
                    task_id_display = resolved.get('task_id', 'None')[:8] + '...' if resolved.get('task_id') else 'None'
                    logger.info(f"[Modes]     - taskId: {task_id_display}")
                    print(f"[Modes]     - taskId: {task_id_display}", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - 已添加到 reference_images.raw")
                    print(f"[Modes]     - 已添加到 reference_images.raw", file=sys.stderr, flush=True)
                    logger.info(f"[Modes] ========== CONTINUITY LOGIC处理完成 ==========")
                    print(f"[Modes] ========== CONTINUITY LOGIC处理完成 ==========", file=sys.stderr, flush=True)
                else:
                    logger.warning(f"[Modes] ⚠️ CONTINUITY附件解析失败 (耗时: {continuity_elapsed:.2f}ms): 未找到匹配的附件")
                    print(f"[Modes] ⚠️ CONTINUITY附件解析失败 (耗时: {continuity_elapsed:.2f}ms): 未找到匹配的附件", file=sys.stderr, flush=True)
            else:
                logger.warning(f"[Modes] ⚠️ 跳过CONTINUITY LOGIC: 未提供 session_id")
                print(f"[Modes] ⚠️ 跳过CONTINUITY LOGIC: 未提供 session_id", file=sys.stderr, flush=True)
        
        # **特殊处理**：对于需要文件数据的方法（pdf-extract, virtual-try-on, segment-clothing 等）
        # 从 attachments 中提取数据
        if request_body.attachments:
            logger.info(f"[Modes]     - 处理 attachments: {len(request_body.attachments)} 个")
            print(f"[Modes]     - 处理 attachments: {len(request_body.attachments)} 个", file=sys.stderr, flush=True)
            reference_images = convert_attachments_to_reference_images(request_body.attachments)
            if reference_images:
                params["reference_images"] = reference_images
                logger.info(f"[Modes]     - 已转换 reference_images: {len(reference_images)} 个")
                print(f"[Modes]     - 已转换 reference_images: {len(reference_images)} 个", file=sys.stderr, flush=True)
            
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
        print(f"[Modes] ✅ [步骤5] 参数准备完成 (耗时: {param_time:.2f}ms)", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - 最终参数数量: {len(params)}")
        print(f"[Modes]     - 最终参数数量: {len(params)}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - 参数键: {list(params.keys())}")
        print(f"[Modes]     - 参数键: {list(params.keys())}", file=sys.stderr, flush=True)

        # ✅ 6. 调用服务方法（服务内部会分发到子服务）
        logger.info(f"[Modes] 🔄 [步骤6] 调用服务方法: {service_type}.{method_name}()...")
        print(f"[Modes] 🔄 [步骤6] 调用服务方法: {service_type}.{method_name}()...", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - 参数数量: {len(params)}")
        print(f"[Modes]     - 参数数量: {len(params)}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - 关键参数:")
        print(f"[Modes]     - 关键参数:", file=sys.stderr, flush=True)
        logger.info(f"[Modes]         - model: {params.get('model', 'None')}")
        print(f"[Modes]         - model: {params.get('model', 'None')}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]         - prompt: {params.get('prompt', 'None')[:100] + '...' if params.get('prompt') and len(params.get('prompt', '')) > 100 else params.get('prompt', 'None')}")
        print(f"[Modes]         - prompt: {params.get('prompt', 'None')[:100] + '...' if params.get('prompt') and len(params.get('prompt', '')) > 100 else params.get('prompt', 'None')}", file=sys.stderr, flush=True)
        if 'number_of_images' in params:
            logger.info(f"[Modes]         - number_of_images: {params.get('number_of_images')}")
            print(f"[Modes]         - number_of_images: {params.get('number_of_images')}", file=sys.stderr, flush=True)
        if 'aspect_ratio' in params:
            logger.info(f"[Modes]         - aspect_ratio: {params.get('aspect_ratio')}")
            print(f"[Modes]         - aspect_ratio: {params.get('aspect_ratio')}", file=sys.stderr, flush=True)
        if 'image_size' in params:
            logger.info(f"[Modes]         - image_size: {params.get('image_size')}")
            print(f"[Modes]         - image_size: {params.get('image_size')}", file=sys.stderr, flush=True)
        if 'reference_images' in params:
            ref_images = params.get('reference_images', {})
            logger.info(f"[Modes]         - reference_images: {len(ref_images)} 个引用图片")
            print(f"[Modes]         - reference_images: {len(ref_images)} 个引用图片", file=sys.stderr, flush=True)
        
        method_start = time.time()
        result = await method(**params)
        method_time = (time.time() - method_start) * 1000
        
        logger.info(f"[Modes] ✅ [步骤6] 服务方法调用完成 (耗时: {method_time:.2f}ms)")
        print(f"[Modes] ✅ [步骤6] 服务方法调用完成 (耗时: {method_time:.2f}ms)", file=sys.stderr, flush=True)
        if isinstance(result, list):
            logger.info(f"[Modes]     - 返回结果: {len(result)} 个图片")
            print(f"[Modes]     - 返回结果: {len(result)} 个图片", file=sys.stderr, flush=True)
        elif isinstance(result, dict):
            logger.info(f"[Modes]     - 返回结果: 字典格式")
            print(f"[Modes]     - 返回结果: 字典格式", file=sys.stderr, flush=True)
            if 'images' in result:
                logger.info(f"[Modes]     - 图片数量: {len(result.get('images', []))}")
                print(f"[Modes]     - 图片数量: {len(result.get('images', []))}", file=sys.stderr, flush=True)
        else:
            logger.info(f"[Modes]     - 返回结果类型: {type(result).__name__}")
            print(f"[Modes]     - 返回结果类型: {type(result).__name__}", file=sys.stderr, flush=True)

        # ✅ 7. **新增**：处理图片生成和编辑的结果（使用 AttachmentService）
        # 对于 image-gen 和 image-edit 模式，处理返回的图片
        if method_name in ["generate_image", "edit_image"]:
            logger.info(f"[Modes] 🔄 [步骤7] 处理图片生成/编辑结果...")
            print(f"[Modes] 🔄 [步骤7] 处理图片生成/编辑结果...", file=sys.stderr, flush=True)
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息ID
            session_id = None
            message_id = None
            if request_body.options:
                session_id = request_body.options.frontend_session_id or request_body.options.sessionId
                message_id = request_body.options.message_id
            
            logger.info(f"[Modes]     - session_id: {session_id[:8] + '...' if session_id else 'None'}")
            print(f"[Modes]     - session_id: {session_id[:8] + '...' if session_id else 'None'}", file=sys.stderr, flush=True)
            logger.info(f"[Modes]     - message_id: {message_id[:8] + '...' if message_id else 'None'}")
            print(f"[Modes]     - message_id: {message_id[:8] + '...' if message_id else 'None'}", file=sys.stderr, flush=True)
            
            # ✅ 如果缺少 messageId，记录警告但继续处理（不阻塞）
            if not message_id:
                logger.warning(f"[Modes] ⚠️ 缺少 message_id，附件将不会保存到数据库")
                print(f"[Modes] ⚠️ 缺少 message_id，附件将不会保存到数据库", file=sys.stderr, flush=True)
            
            if session_id and message_id:
                processed_images = []
                
                # 处理返回的图片列表
                # 结果格式可能是 List[Dict] 或 List[ImageGenerationResult]
                images = result if isinstance(result, list) else result.get("images", []) if isinstance(result, dict) else []
                logger.info(f"[Modes]     - 需要处理的图片数量: {len(images)}")
                print(f"[Modes]     - 需要处理的图片数量: {len(images)}", file=sys.stderr, flush=True)
                
                for idx, img in enumerate(images):
                    logger.info(f"[Modes] 🔄 [步骤7] 处理第 {idx+1}/{len(images)} 张图片...")
                    print(f"[Modes] 🔄 [步骤7] 处理第 {idx+1}/{len(images)} 张图片...", file=sys.stderr, flush=True)
                    
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
                    print(f"[Modes]     - 图片URL类型: {url_type}", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - mime_type: {mime_type}")
                    print(f"[Modes]     - mime_type: {mime_type}", file=sys.stderr, flush=True)
                    
                    # 使用 AttachmentService 处理AI返回的图片
                    prefix = "generated" if method_name == "generate_image" else "edited"
                    logger.info(f"[Modes]     - 调用 AttachmentService.process_ai_result()...")
                    print(f"[Modes]     - 调用 AttachmentService.process_ai_result()...", file=sys.stderr, flush=True)
                    processed = await attachment_service.process_ai_result(
                        ai_url=ai_url,
                        mime_type=mime_type,
                        session_id=session_id,
                        message_id=message_id,
                        user_id=user_id,
                        prefix=prefix
                    )
                    
                    logger.info(f"[Modes] ✅ [步骤7] 第 {idx+1} 张图片处理完成:")
                    print(f"[Modes] ✅ [步骤7] 第 {idx+1} 张图片处理完成:", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - attachment_id: {processed['attachment_id'][:8]}...")
                    print(f"[Modes]     - attachment_id: {processed['attachment_id'][:8]}...", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - status: {processed['status']}")
                    print(f"[Modes]     - status: {processed['status']}", file=sys.stderr, flush=True)
                    logger.info(f"[Modes]     - task_id: {processed.get('task_id', 'None')[:8] + '...' if processed.get('task_id') else 'None'}")
                    print(f"[Modes]     - task_id: {processed.get('task_id', 'None')[:8] + '...' if processed.get('task_id') else 'None'}", file=sys.stderr, flush=True)
                    
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
                print(f"[Modes] ✅ [步骤7] 所有图片处理完成: {len(processed_images)} 张", file=sys.stderr, flush=True)
            else:
                logger.warning(f"[Modes] ⚠️ [步骤7] 跳过附件处理: 缺少 session_id 或 message_id")
                print(f"[Modes] ⚠️ [步骤7] 跳过附件处理: 缺少 session_id 或 message_id", file=sys.stderr, flush=True)
        
        # ✅ 8. 返回响应
        total_time = (time.time() - request_start_time) * 1000
        logger.info(f"[Modes] ========== 模式请求处理完成 (总耗时: {total_time:.2f}ms) ==========")
        print(f"[Modes] ========== 模式请求处理完成 (总耗时: {total_time:.2f}ms) ==========", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - provider: {provider}")
        print(f"[Modes]     - provider: {provider}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - mode: {mode}")
        print(f"[Modes]     - mode: {mode}", file=sys.stderr, flush=True)
        logger.info(f"[Modes]     - 成功: True")
        print(f"[Modes]     - 成功: True", file=sys.stderr, flush=True)
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
