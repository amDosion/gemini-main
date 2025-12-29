"""
通义千问聊天 API 路由

提供通义千问的聊天功能，使用 qwen_native.py 调用 DashScope API。
支持文本模型和视觉模型（qwen-vl-*）。
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["tongyi-chat"])


# ==================== 请求模型 ====================

class Attachment(BaseModel):
    """附件模型（图片）"""
    id: str
    mimeType: str
    name: str
    url: Optional[str] = None  # 图片 URL
    tempUrl: Optional[str] = None  # 临时 URL（DashScope 上传）
    fileUri: Optional[str] = None  # 文件 URI


class Message(BaseModel):
    """消息模型"""
    role: str  # "user" | "model" | "system"
    content: str
    isError: Optional[bool] = False
    attachments: Optional[List[Attachment]] = None  # 附件列表


class ChatOptions(BaseModel):
    """聊天选项"""
    enableSearch: Optional[bool] = False
    enableThinking: Optional[bool] = False
    temperature: Optional[float] = 1.0
    maxTokens: Optional[int] = None


class ChatRequest(BaseModel):
    """聊天请求"""
    modelId: str
    messages: List[Message]
    message: str
    attachments: Optional[List[Attachment]] = None  # 当前消息的附件
    options: ChatOptions
    apiKey: str


# ==================== 辅助函数 ====================

def is_vision_model(model_id: str) -> bool:
    """判断是否为视觉模型"""
    lower_id = model_id.lower()
    return "-vl-" in lower_id or lower_id.endswith("-vl")


def get_image_url(attachment: Attachment) -> Optional[str]:
    """
    从附件中获取图片 URL
    
    优先级：tempUrl > url > fileUri
    """
    if attachment.tempUrl:
        return attachment.tempUrl
    if attachment.url:
        return attachment.url
    if attachment.fileUri:
        return attachment.fileUri
    return None


def convert_messages(history: List[Message], current_message: str) -> List[dict]:
    """
    转换消息格式（文本模型）
    
    前端格式:
    {
      role: "user" | "model" | "system",
      content: str,
      isError: bool
    }
    
    qwen_native.py 格式:
    {
      "role": "user" | "assistant" | "system",
      "content": str
    }
    """
    messages = []
    
    # 转换历史消息
    for msg in history:
        # 跳过错误消息
        if msg.isError:
            continue
        
        # 跳过空消息
        if not msg.content:
            continue
        
        # 转换角色名称
        role = msg.role
        if role == "model":
            role = "assistant"
        
        messages.append({
            "role": role,
            "content": msg.content
        })
    
    # 添加当前消息
    if current_message:
        messages.append({
            "role": "user",
            "content": current_message
        })
    
    return messages


def convert_multimodal_messages(
    history: List[Message], 
    current_message: str,
    current_attachments: Optional[List[Attachment]] = None
) -> List[dict]:
    """
    转换消息格式（视觉模型 - 多模态）
    
    MultiModalConversation 格式:
    {
      "role": "user" | "assistant" | "system",
      "content": [
        {"image": "http://xxx.jpg"},
        {"text": "描述这张图片"}
      ]
    }
    """
    messages = []
    
    # 转换历史消息
    for msg in history:
        if msg.isError:
            continue
        
        role = msg.role
        if role == "model":
            role = "assistant"
        
        # 构建多模态内容
        content = []
        
        # 添加历史消息中的图片附件
        if msg.attachments:
            for att in msg.attachments:
                img_url = get_image_url(att)
                if img_url and att.mimeType.startswith("image/"):
                    content.append({"image": img_url})
        
        # 添加文本内容
        if msg.content:
            content.append({"text": msg.content})
        
        # 跳过空消息
        if not content:
            continue
        
        messages.append({
            "role": role,
            "content": content
        })
    
    # 添加当前消息
    if current_message or current_attachments:
        content = []
        
        # 添加当前消息的图片附件
        if current_attachments:
            for att in current_attachments:
                img_url = get_image_url(att)
                if img_url and att.mimeType.startswith("image/"):
                    content.append({"image": img_url})
                    logger.info(f"[Tongyi Chat] Added image: {img_url[:50]}...")
        
        # 添加文本内容
        if current_message:
            content.append({"text": current_message})
        
        if content:
            messages.append({
                "role": "user",
                "content": content
            })
    
    return messages


def convert_to_stream_update(chunk: dict) -> dict:
    """
    转换响应格式
    
    qwen_native.py 格式:
    {
      "content": str,
      "chunk_type": "reasoning" | "content" | "done",
      "prompt_tokens": int,
      "completion_tokens": int,
      "total_tokens": int,
      "search_results": List[dict]
    }
    
    前端格式:
    {
      "text": str,
      "chunk_type": "reasoning" | "content" | "done",
      "usage": {...},
      "groundingMetadata": {...}
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
    
    # 转换搜索结果
    if chunk.get("search_results"):
        result["groundingMetadata"] = {
            "groundingChunks": [
                {
                    "web": {
                        "uri": item.get("url", ""),
                        "title": item.get("title", "Source")
                    }
                }
                for item in chunk["search_results"]
            ]
        }
    
    return result


# ==================== API 端点 ====================

@router.post("/tongyi")
async def chat_tongyi(request: ChatRequest):
    """
    通义千问聊天 API
    
    接收前端的聊天请求，调用 qwen_native.py 进行流式聊天，
    并将响应转换为前端期望的格式。
    
    支持：
    - 文本模型（qwen-max, qwen-plus 等）
    - 视觉模型（qwen-vl-max, qwen-vl-plus 等）
    
    Args:
        request: 聊天请求
    
    Returns:
        StreamingResponse: SSE 流式响应
    """
    try:
        # 判断是否为视觉模型
        is_vision = is_vision_model(request.modelId)
        
        # 记录请求信息
        logger.info(
            f"[Tongyi Chat] model={request.modelId}, "
            f"vision={is_vision}, "
            f"search={request.options.enableSearch}, "
            f"thinking={request.options.enableThinking}, "
            f"attachments={len(request.attachments) if request.attachments else 0}"
        )
        
        # 1. 初始化 QwenNativeProvider
        try:
            from ..services.qwen_native import QwenNativeProvider
        except ImportError:
            try:
                from services.qwen_native import QwenNativeProvider
            except ImportError:
                from backend.app.services.qwen_native import QwenNativeProvider
        
        provider = QwenNativeProvider(
            api_key=request.apiKey,
            connection_mode="official"
        )
        
        # 2. 根据模型类型转换消息格式
        if is_vision:
            messages = convert_multimodal_messages(
                request.messages, 
                request.message,
                request.attachments
            )
            logger.info(f"[Tongyi Chat] Converted {len(messages)} multimodal messages")
        else:
            messages = convert_messages(request.messages, request.message)
            logger.info(f"[Tongyi Chat] Converted {len(messages)} text messages")
        
        # 3. 调用流式聊天
        async def generate():
            try:
                if is_vision:
                    # 视觉模型：使用多模态流式 API
                    import asyncio
                    
                    # 同步迭代器转异步
                    def sync_stream():
                        return provider._sync_stream_multimodal_chat(
                            messages=messages,
                            model=request.modelId,
                            temperature=request.options.temperature,
                            max_tokens=request.options.maxTokens
                        )
                    
                    # 在线程池中运行同步迭代器
                    loop = asyncio.get_event_loop()
                    sync_iter = await loop.run_in_executor(None, sync_stream)
                    
                    for chunk in sync_iter:
                        # 格式化多模态响应
                        formatted = provider._format_multimodal_stream_chunk(chunk)
                        stream_update = convert_to_stream_update(formatted)
                        
                        if stream_update.get("chunk_type") == "done":
                            usage = stream_update.get("usage", {})
                            logger.info(
                                f"[Tongyi Chat VL] usage: "
                                f"prompt={usage.get('prompt_tokens', 0)}, "
                                f"completion={usage.get('completion_tokens', 0)}"
                            )
                        
                        yield f"data: {json.dumps(stream_update, ensure_ascii=False)}\n\n"
                else:
                    # 文本模型：使用标准流式 API
                    async for chunk in provider.stream_chat(
                        messages=messages,
                        model=request.modelId,
                        enable_search=request.options.enableSearch,
                        enable_thinking=request.options.enableThinking,
                        temperature=request.options.temperature,
                        max_tokens=request.options.maxTokens
                    ):
                        # 4. 转换响应格式
                        stream_update = convert_to_stream_update(chunk)
                        
                        # 记录 usage 信息
                        if stream_update.get("chunk_type") == "done":
                            usage = stream_update.get("usage", {})
                            logger.info(
                                f"[Tongyi Chat] usage: "
                                f"prompt={usage.get('prompt_tokens', 0)}, "
                                f"completion={usage.get('completion_tokens', 0)}, "
                                f"total={usage.get('total_tokens', 0)}"
                            )
                        
                        # 发送 SSE 数据
                        yield f"data: {json.dumps(stream_update, ensure_ascii=False)}\n\n"
            
            except Exception as e:
                logger.error(f"[Tongyi Chat] Stream error: {e}", exc_info=True)
                # 发送错误信息
                error_update = {
                    "text": f"\n\n❌ **Error**: {str(e)}\n",
                    "chunk_type": "content"
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
    
    except Exception as e:
        logger.error(f"[Tongyi Chat] Request error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
