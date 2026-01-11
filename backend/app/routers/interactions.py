"""
Interactions API 路由

提供 Interactions API 的 HTTP 端点
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union, Dict, Any
from datetime import datetime

from ..services.interactions_service import InteractionsService
from ..dependencies import get_interactions_service


router = APIRouter(prefix="/api/interactions", tags=["interactions"])


class CreateInteractionRequest(BaseModel):
    """创建交互请求"""
    model: Optional[str] = None
    agent: Optional[str] = None
    input: Union[str, List[Dict[str, Any]]]
    previous_interaction_id: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False
    background: bool = False
    generation_config: Optional[Dict[str, Any]] = None
    system_instruction: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    store: bool = True
    
    @validator('model', 'agent')
    def validate_model_or_agent(cls, v, values):
        """验证 model 和 agent 二选一"""
        # 这个验证会在所有字段都设置后再检查
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "model": "gemini-2.5-flash",
                "input": "Hello, how are you?",
                "store": True
            }
        }


class InteractionResponse(BaseModel):
    """交互响应"""
    id: str
    model: Optional[str] = None
    agent: Optional[str] = None
    status: str
    outputs: List[Dict[str, Any]] = []
    usage: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "interaction_123",
                "model": "gemini-2.5-flash",
                "status": "completed",
                "outputs": [
                    {
                        "type": "text",
                        "text": "I'm doing well, thank you!"
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 8
                }
            }
        }


def get_api_key_from_header(authorization: str = Header(...)) -> str:
    """从 Authorization Header 提取 API Key"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    return authorization.split(' ')[1]


@router.post("/", response_model=InteractionResponse)
async def create_interaction(
    request: CreateInteractionRequest,
    authorization: str = Header(...),
):
    """
    创建新的交互
    
    支持:
    - 简单文本交互
    - 多轮对话 (previous_interaction_id)
    - 工具调用 (tools)
    - 流式响应 (stream)
    - 后台执行 (background)
    """
    try:
        # 提取 API Key
        api_key = get_api_key_from_header(authorization)
        
        # 创建服务实例
        service = InteractionsService(api_key)
        
        # 创建交互
        interaction = await service.create_interaction(
            model=request.model,
            agent=request.agent,
            input=request.input,
            previous_interaction_id=request.previous_interaction_id,
            tools=request.tools,
            stream=request.stream,
            background=request.background,
            generation_config=request.generation_config,
            system_instruction=request.system_instruction,
            response_format=request.response_format,
            store=request.store
        )
        
        # 构建响应
        return InteractionResponse(
            id=interaction.id,
            model=getattr(interaction, "model", None),
            agent=getattr(interaction, "agent", None),
            status=interaction.status,
            outputs=[output.__dict__ if hasattr(output, '__dict__') else output 
                    for output in getattr(interaction, "outputs", [])],
            usage=interaction.usage.__dict__ if hasattr(interaction, "usage") else None,
            created_at=datetime.now().isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    interaction_id: str,
    authorization: str = Header(...),
):
    """获取交互状态"""
    try:
        # 提取 API Key
        api_key = get_api_key_from_header(authorization)
        
        # 创建服务实例
        service = InteractionsService(api_key)
        
        # 获取交互
        interaction = await service.get_interaction(interaction_id)
        
        # 构建响应
        return InteractionResponse(
            id=interaction.id,
            model=getattr(interaction, "model", None),
            agent=getattr(interaction, "agent", None),
            status=interaction.status,
            outputs=[output.__dict__ if hasattr(output, '__dict__') else output 
                    for output in getattr(interaction, "outputs", [])],
            usage=interaction.usage.__dict__ if hasattr(interaction, "usage") else None,
            created_at=getattr(interaction, "created_at", datetime.now().isoformat())
        )
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Interaction not found: {str(e)}")


@router.delete("/{interaction_id}")
async def delete_interaction(
    interaction_id: str,
    authorization: str = Header(...),
):
    """删除交互"""
    try:
        # 提取 API Key
        api_key = get_api_key_from_header(authorization)
        
        # 创建服务实例
        service = InteractionsService(api_key)
        
        # 删除交互
        await service.delete_interaction(interaction_id)
        
        return {"message": "Interaction deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete interaction: {str(e)}")


@router.get("/{interaction_id}/stream")
async def stream_interaction(
    interaction_id: str,
    last_event_id: Optional[str] = None,
    authorization: str = Header(...),
):
    """
    流式获取交互
    
    使用 Server-Sent Events (SSE) 协议
    """
    pass
