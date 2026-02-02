"""
Chat API Router

This module provides a chat API endpoint that works with all AI providers.
It handles both streaming and non-streaming responses, and integrates with the
ProviderFactory to create appropriate service instances.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
import json
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.credential_manager import get_provider_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modes", tags=["chat"])


# ==================== Request Models ====================

class Attachment(BaseModel):
    """Attachment model (images, files, etc.)"""
    id: str
    mime_type: str
    name: str
    url: Optional[str] = None
    temp_url: Optional[str] = None
    file_uri: Optional[str] = None
    base64_data: Optional[str] = None  # 直接 Base64 数据（不含 data: 前缀）
    google_file_uri: Optional[str] = None  # Google Files API URI


class Message(BaseModel):
    """Message model"""
    role: str  # "user" | "assistant" | "system"
    content: str
    is_error: Optional[bool] = False
    attachments: Optional[List[Attachment]] = None


class ChatOptions(BaseModel):
    """Chat options"""
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    enable_search: Optional[bool] = False
    enable_thinking: Optional[bool] = False
    base_url: Optional[str] = None  # Custom API URL


class ChatRequest(BaseModel):
    """Chat request"""
    model_id: str
    messages: List[Message]
    message: str
    attachments: Optional[List[Attachment]] = None
    options: Optional[ChatOptions] = None
    api_key: Optional[str] = None  # Optional, will try to get from database/env
    stream: Optional[bool] = True  # Default to streaming


# ==================== Helper Functions ====================

def convert_messages_to_provider_format(
    history: List[Message],
    current_message: str,
    provider: str = None,
    current_attachments: Optional[List[Attachment]] = None
) -> List[Dict[str, Any]]:
    """
    Convert frontend message format to provider format.

    Role conversion rules:
    - Google/Gemini: Keep "model" as "model" (Gemini API expects "model")
    - OpenAI-compatible: Convert "model" to "assistant" (OpenAI API expects "assistant")
    - Default: Convert "model" to "assistant" for backward compatibility

    Attachment handling:
    - current_attachments are injected into the last user message
    - Supports inline_data (Base64) and file_data (Google Files API URI)
    """
    messages = []

    # Determine if provider is Google (needs "model" role)
    is_google = provider and provider in ["google", "google-custom"]

    for msg in history:
        if msg.is_error:
            continue
        if not msg.content:
            continue

        role = msg.role
        # Only convert "model" to "assistant" for non-Google providers
        if role == "model" and not is_google:
            role = "assistant"
        # For Google, keep "model" as "model" (Gemini API requirement)

        messages.append({
            "role": role,
            "content": msg.content
        })

    if current_message:
        msg_dict: Dict[str, Any] = {
            "role": "user",
            "content": current_message
        }
        # 注入当前消息的附件数据
        if current_attachments:
            msg_dict["attachments"] = [
                {
                    "mime_type": att.mime_type,
                    "url": att.url,
                    "temp_url": att.temp_url,
                    "file_uri": att.file_uri or att.google_file_uri,
                    "base64_data": att.base64_data,
                }
                for att in current_attachments
                if att.mime_type  # 只包含有效 MIME 类型的附件
            ]
        messages.append(msg_dict)

    return messages


def convert_chunk_to_frontend_format(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Convert provider chunk format to frontend format."""
    result = {
        "text": chunk.get("content", ""),
        "chunk_type": chunk.get("chunk_type", "content")
    }
    
    if chunk.get("chunk_type") == "done":
        result["usage"] = {
            "prompt_tokens": chunk.get("prompt_tokens", 0),
            "completion_tokens": chunk.get("completion_tokens", 0),
            "total_tokens": chunk.get("total_tokens", 0)
        }
        if chunk.get("finish_reason"):
            result["finish_reason"] = chunk["finish_reason"]
    
    if chunk.get("error"):
        result["error"] = chunk["error"]
    
    return result


# ==================== API Endpoints ====================

@router.post("/{provider}/chat")
async def chat_with_provider(
    provider: str,
    request: ChatRequest,
    request_obj: Request,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat API endpoint for all providers.
    
    Supports both streaming and non-streaming responses.
    """
    try:
        attachment_count = len(request.attachments) if request.attachments else 0
        logger.info(
            f"[Chat] provider={provider}, "
            f"model={request.model_id}, "
            f"stream={request.stream}, "
            f"messages={len(request.messages)}, "
            f"attachments={attachment_count}, "
            f"user_id={user_id}"
        )
        
        # 从数据库获取 API key 和 base URL
        api_key, db_base_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request.api_key,
            request_base_url=request.options.base_url if request.options else None
        )
        
        # 优先使用数据库中的 base_url
        base_url = db_base_url
        if not base_url and request.options and request.options.base_url:
            base_url = request.options.base_url
        
        # Create provider service
        from ...services.common.provider_factory import ProviderFactory
        
        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                api_url=base_url,
                user_id=user_id,
                db=db,
                timeout=120.0
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Convert messages
        messages = convert_messages_to_provider_format(
            request.messages,
            request.message,
            provider=provider,
            current_attachments=request.attachments
        )
        
        # Prepare options
        options = {}
        if request.options:
            if request.options.temperature is not None:
                options["temperature"] = request.options.temperature
            if request.options.max_tokens is not None:
                options["max_tokens"] = request.options.max_tokens
            if request.options.top_p is not None:
                options["top_p"] = request.options.top_p
            if request.options.top_k is not None:
                options["top_k"] = request.options.top_k
        
        # Streaming response
        if request.stream:
            async def generate():
                try:
                    async for chunk in service.stream_chat(
                        messages=messages,
                        model=request.model_id,
                        **options
                    ):
                        frontend_chunk = convert_chunk_to_frontend_format(chunk)
                        
                        if frontend_chunk.get("chunk_type") == "done":
                            usage = frontend_chunk.get("usage", {})
                            logger.info(
                                f"[Chat] {provider} usage: "
                                f"prompt={usage.get('prompt_tokens', 0)}, "
                                f"completion={usage.get('completion_tokens', 0)}, "
                                f"total={usage.get('total_tokens', 0)}"
                            )
                        
                        yield f"data: {json.dumps(frontend_chunk, ensure_ascii=False)}\n\n"
                
                except Exception as e:
                    logger.error(f"[Chat] Stream error: {e}", exc_info=True)
                    error_chunk = {
                        "text": "",
                        "chunk_type": "error",
                        "error": str(e)
                    }
                    yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        # Non-streaming response
        else:
            response = await service.chat(
                messages=messages,
                model=request.model_id,
                **options
            )
            
            if response.get("usage"):
                usage = response["usage"]
                logger.info(
                    f"[Chat] {provider} usage: "
                    f"prompt={usage.get('prompt_tokens', 0)}, "
                    f"completion={usage.get('completion_tokens', 0)}, "
                    f"total={usage.get('total_tokens', 0)}"
                )
            
            return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Chat] Request error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
