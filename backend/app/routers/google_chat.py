"""
Google (Gemini) 聊天 API 路由

提供 Google Gemini 的聊天功能，使用 google_service.py 调用 Google API。
参考 tongyi_chat.py 的实现，统一在后端处理消息转换，避免前后端重复处理。
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
import json
import logging

from ..core.database import SessionLocal
from ..core.user_context import require_user_id
from ..models.db_models import ConfigProfile, UserSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["google-chat"])


# ==================== 数据库依赖 ====================

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 请求模型 ====================

class Attachment(BaseModel):
    """附件模型（图片、文件等）"""
    id: str
    mimeType: str
    name: str
    url: Optional[str] = None
    tempUrl: Optional[str] = None
    fileUri: Optional[str] = None


class Message(BaseModel):
    """消息模型"""
    role: str  # "user" | "model" | "system"
    content: str
    isError: Optional[bool] = False
    attachments: Optional[List[Attachment]] = None


class ChatOptions(BaseModel):
    """聊天选项"""
    temperature: Optional[float] = 1.0
    maxTokens: Optional[int] = None
    topP: Optional[float] = None
    topK: Optional[int] = None
    enableSearch: Optional[bool] = False
    enableThinking: Optional[bool] = False
    enableCodeExecution: Optional[bool] = False
    enableGrounding: Optional[bool] = False
    baseUrl: Optional[str] = None


class ChatRequest(BaseModel):
    """聊天请求"""
    modelId: str
    messages: List[Message]
    message: str
    attachments: Optional[List[Attachment]] = None
    options: Optional[ChatOptions] = None
    apiKey: Optional[str] = None  # 可选，用于测试/覆盖
    stream: Optional[bool] = True


# ==================== 辅助函数 ====================

async def get_provider_credentials(
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None,
    request_base_url: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    从数据库获取 Google Provider 的凭证（API Key 和 Base URL）
    
    优先级：
    1. 请求参数（用于测试/覆盖）
    2. 数据库激活配置（必须匹配 provider）
    3. 数据库任意配置（匹配 provider）
    """
    # 1. 优先使用请求参数（用于测试/验证连接场景）
    if request_api_key and request_api_key.strip():
        logger.info(f"[Google Chat] Using API key from request parameter (test/override mode)")
        return request_api_key, request_base_url
    
    # 2. 从数据库获取
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
    
    # 优先使用激活配置（如果匹配 provider）
    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                logger.info(f"[Google Chat] Using API key from active profile '{profile.name}'")
                return profile.api_key, profile.base_url
    
    # 回退：使用第一个匹配的配置
    for profile in matching_profiles:
        if profile.api_key:
            logger.info(f"[Google Chat] Using API key from profile '{profile.name}' (fallback)")
            return profile.api_key, profile.base_url
    
    raise HTTPException(
        status_code=401,
        detail="API Key not found for provider: google. Please configure it in Settings → Profiles."
    )


def convert_messages(history: List[Message], current_message: str) -> List[Dict[str, Any]]:
    """
    过滤和清理消息（不转换角色名称）
    
    职责：
    - 过滤错误消息（isError=True）
    - 过滤空消息
    - 保持原始角色名称不变
    
    输入格式（前端）:
        Message[] = [
            {role: "user"|"model"|"system", content: str, isError: bool}
        ]
    
    输出格式（保持角色名称）:
        [{"role": "user"|"model"|"system", "content": str}]
    
    注意：
    - Router Layer 只负责过滤，不负责转换
    - Service Layer 负责将消息转换为 Google API 格式
    - 角色名称保持不变，避免重复转换（model -> assistant -> model）
    """
    messages = []
    
    # 转换历史消息
    for msg in history:
        # 跳过错误消息
        if msg.isError:
            continue
        
        # 跳过空消息
        if not msg.content or not msg.content.strip():
            continue
        
        # ✅ 保持原始角色名称，不转换
        messages.append({
            "role": msg.role,  # 直接使用，不转换
            "content": msg.content
        })
    
    # 添加当前消息
    if current_message and current_message.strip():
        messages.append({
            "role": "user",
            "content": current_message
        })
    
    logger.info(f"[Google Chat] convert_messages: {len(history)} history -> {len(messages)} messages")
    
    return messages


def convert_to_stream_update(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    转换响应格式
    
    Google Service 格式:
    {
      "content": str,
      "chunk_type": "content" | "done" | "error",
      "prompt_tokens": int,
      "completion_tokens": int,
      "total_tokens": int,
      "finish_reason": str
    }
    
    前端格式:
    {
      "text": str,
      "chunk_type": "content" | "done" | "error",
      "usage": {...},
      "finish_reason": str
    }
    """
    result = {
        "text": chunk.get("content", ""),
        "chunk_type": chunk.get("chunk_type", "content")
    }
    
    # 添加 usage 信息（仅在 done chunk）
    if chunk.get("chunk_type") == "done":
        result["usage"] = {
            "prompt_tokens": chunk.get("prompt_tokens", 0),
            "completion_tokens": chunk.get("completion_tokens", 0),
            "total_tokens": chunk.get("total_tokens", 0)
        }
        if chunk.get("finish_reason"):
            result["finish_reason"] = chunk["finish_reason"]
    
    # 错误处理
    if chunk.get("error"):
        result["error"] = chunk["error"]
        result["chunk_type"] = "error"
    
    return result


# ==================== API 端点 ====================

@router.post("/google")
async def chat_google(
    request: ChatRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
):
    """
    Google Gemini 聊天 API
    
    接收前端的聊天请求，调用 google_service.py 进行流式聊天，
    并将响应转换为前端期望的格式。
    
    统一在后端处理消息转换，避免前后端重复处理。
    
    Args:
        request: 聊天请求
        request_obj: FastAPI Request 对象（用于获取用户认证）
        db: 数据库会话
    
    Returns:
        StreamingResponse: SSE 流式响应
    """
    try:
        # ✅ 验证用户认证
        user_id = require_user_id(request_obj)
        
        # 记录请求信息
        logger.info(
            f"[Google Chat] model={request.modelId}, "
            f"stream={request.stream}, "
            f"messages={len(request.messages)}, "
            f"user_id={user_id}"
        )
        
        # ✅ 从数据库获取 API key 和 base URL
        api_key, db_base_url = await get_provider_credentials(
            db=db,
            user_id=user_id,
            request_api_key=request.apiKey,
            request_base_url=request.options.baseUrl if request.options else None
        )
        
        # ✅ 优先使用数据库中的 base_url，如果没有则使用请求中的
        base_url = db_base_url
        if not base_url and request.options and request.options.baseUrl:
            base_url = request.options.baseUrl
        
        # ✅ 创建 GoogleService 实例
        from ..services.provider_factory import ProviderFactory
        
        try:
            service = ProviderFactory.create(
                provider='google',
                api_key=api_key,
                api_url=base_url,
                timeout=120.0
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # ✅ 统一在后端转换消息格式（避免前后端重复处理）
        messages = convert_messages(request.messages, request.message)
        logger.info(f"[Google Chat] Converted {len(messages)} messages (from {len(request.messages)} history)")
        
        # ✅ 防御性检查：确保至少有一条消息
        if not messages:
            logger.error("[Google Chat] No messages after conversion!")
            raise HTTPException(status_code=400, detail="No valid messages to send")
        
        # ✅ 准备选项
        options = {}
        if request.options:
            # 基础选项
            if request.options.temperature is not None:
                options["temperature"] = request.options.temperature
            if request.options.maxTokens is not None:
                options["max_tokens"] = request.options.maxTokens
            if request.options.topP is not None:
                options["top_p"] = request.options.topP
            if request.options.topK is not None:
                options["top_k"] = request.options.topK
            
            # ✅ 工具选项（统一 SDK 方案）
            if request.options.enableSearch is not None:
                options["enable_search"] = request.options.enableSearch
            if request.options.enableThinking is not None:
                options["enable_thinking"] = request.options.enableThinking
            if request.options.enableCodeExecution is not None:
                options["enable_code_execution"] = request.options.enableCodeExecution
            if request.options.enableGrounding is not None:
                options["enable_grounding"] = request.options.enableGrounding
        
        # ✅ 流式响应处理
        if request.stream:
            async def generate():
                try:
                    async for chunk in service.stream_chat(
                        messages=messages,
                        model=request.modelId,
                        **options
                    ):
                        # 转换响应格式
                        stream_update = convert_to_stream_update(chunk)
                        
                        # 记录 usage 信息
                        if stream_update.get("chunk_type") == "done":
                            usage = stream_update.get("usage", {})
                            logger.info(
                                f"[Google Chat] usage: "
                                f"prompt={usage.get('prompt_tokens', 0)}, "
                                f"completion={usage.get('completion_tokens', 0)}, "
                                f"total={usage.get('total_tokens', 0)}"
                            )
                        
                        # 发送 SSE 数据
                        yield f"data: {json.dumps(stream_update, ensure_ascii=False)}\n\n"
                
                except Exception as e:
                    logger.error(f"[Google Chat] Stream error: {e}", exc_info=True)
                    # 发送错误信息
                    error_update = {
                        "text": f"\n\n❌ **Error**: {str(e)}\n",
                        "chunk_type": "error",
                        "error": str(e)
                    }
                    yield f"data: {json.dumps(error_update, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
                }
            )
        
        # ✅ 非流式响应
        else:
            response = await service.chat(
                messages=messages,
                model=request.modelId,
                **options
            )
            
            if response.get("usage"):
                usage = response["usage"]
                logger.info(
                    f"[Google Chat] usage: "
                    f"prompt={usage.get('prompt_tokens', 0)}, "
                    f"completion={usage.get('completion_tokens', 0)}, "
                    f"total={usage.get('total_tokens', 0)}"
                )
            
            return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Google Chat] Request error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

