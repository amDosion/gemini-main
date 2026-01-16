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
    mimeType: str
    name: str
    url: Optional[str] = None
    tempUrl: Optional[str] = None
    fileUri: Optional[str] = None


class Message(BaseModel):
    """Message model"""
    role: str  # "user" | "assistant" | "system"
    content: str
    isError: Optional[bool] = False
    attachments: Optional[List[Attachment]] = None


class ChatOptions(BaseModel):
    """Chat options"""
    temperature: Optional[float] = 1.0
    maxTokens: Optional[int] = None
    topP: Optional[float] = None
    topK: Optional[int] = None
    enableSearch: Optional[bool] = False
    enableThinking: Optional[bool] = False
    baseUrl: Optional[str] = None  # Custom API URL


class ChatRequest(BaseModel):
    """Chat request"""
    modelId: str
    messages: List[Message]
    message: str
    attachments: Optional[List[Attachment]] = None
    options: Optional[ChatOptions] = None
    apiKey: Optional[str] = None  # Optional, will try to get from database/env
    stream: Optional[bool] = True  # Default to streaming


# ==================== Helper Functions ====================

def convert_messages_to_provider_format(
    history: List[Message], 
    current_message: str,
    provider: str = None
) -> List[Dict[str, Any]]:
    """
    Convert frontend message format to provider format.
    
    Role conversion rules:
    - Google/Gemini: Keep "model" as "model" (Gemini API expects "model")
    - OpenAI-compatible: Convert "model" to "assistant" (OpenAI API expects "assistant")
    - Default: Convert "model" to "assistant" for backward compatibility
    """
    messages = []
    
    # Determine if provider is Google (needs "model" role)
    is_google = provider and provider in ["google", "google-custom"]
    
    for msg in history:
        if msg.isError:
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
        messages.append({
            "role": "user",
            "content": current_message
        })
    
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
    user_id: str = Depends(require_current_user),  # ✅ 自动注入 user_id
    db: Session = Depends(get_db)
):
    """
    Chat API endpoint for all providers.
    
    Supports both streaming and non-streaming responses.
    """
    try:
        # user_id 已通过依赖注入自动获取，无需手动调用
        
        logger.info(
            f"[Chat] provider={provider}, "
            f"model={request.modelId}, "
            f"stream={request.stream}, "
            f"messages={len(request.messages)}, "
            f"user_id={user_id}"
        )
        
        # ✅ 从数据库获取 API key 和 base URL（与 models.py 保持一致）
        api_key, db_base_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request.apiKey,
            request_base_url=request.options.baseUrl if request.options else None
        )
        
        # ✅ 优先使用数据库中的 base_url，如果没有则使用请求中的
        base_url = db_base_url
        if not base_url and request.options and request.options.baseUrl:
            base_url = request.options.baseUrl
        
        # Create provider service
        from ...services.common.provider_factory import ProviderFactory
        
        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                api_url=base_url,
                timeout=120.0
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Convert messages (pass provider to handle role conversion correctly)
        messages = convert_messages_to_provider_format(
            request.messages,
            request.message,
            provider=provider
        )
        
        # Prepare options
        options = {}
        if request.options:
            if request.options.temperature is not None:
                options["temperature"] = request.options.temperature
            if request.options.maxTokens is not None:
                options["max_tokens"] = request.options.maxTokens
            if request.options.topP is not None:
                options["top_p"] = request.options.topP
            if request.options.topK is not None:
                options["top_k"] = request.options.topK
        
        # Streaming response
        if request.stream:
            async def generate():
                try:
                    async for chunk in service.stream_chat(
                        messages=messages,
                        model=request.modelId,
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
                model=request.modelId,
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
