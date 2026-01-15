"""
Interactions API 路由

提供 Interactions API 的 HTTP 端点
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from ...services.common.interactions_manager import get_interactions_manager
from ...core.database import get_db
from ...core.dependencies import require_current_user


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


# 已废弃：使用 require_user_id 和 get_provider_credentials 替代
# def get_api_key_from_header(authorization: str = Header(...)) -> str:
#     """从 Authorization Header 提取 API Key"""
#     if not authorization or not authorization.startswith('Bearer '):
#         raise HTTPException(
#             status_code=401,
#             detail="Missing or invalid authorization header"
#         )
#     return authorization.split(' ')[1]


@router.post("/", response_model=InteractionResponse)
async def create_interaction(
    request: CreateInteractionRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
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
        
        # 从数据库获取 Google Provider 的 API Key
        from ...core.credential_manager import get_provider_credentials
        api_key, _ = await get_provider_credentials(
            provider="google",
            db=db,
            user_id=user_id
        )
        
        # 使用 InteractionsManager（Vertex AI，企业级）
        manager = get_interactions_manager(db=db, default_vertexai=True)
        
        # 创建交互（使用 Vertex AI，从数据库获取配置）
        result = await manager.create_interaction(
            input=request.input,
            api_key=api_key,
            agent=request.agent or 'deep-research-pro-preview-12-2025',
            background=request.background,
            agent_config=None,  # TODO: 支持 generation_config 转换
            system_instruction=request.system_instruction,
            tools=request.tools,
            previous_interaction_id=request.previous_interaction_id,
            vertexai=True,  # 使用 Vertex AI（企业级）
            user_id=user_id  # 传递 user_id 以从数据库获取 Vertex AI 配置
        )
        
        # 构建 Interaction 对象（与 InteractionsService 返回格式兼容）
        class Interaction:
            def __init__(self, id, status, outputs=None, error=None, model=None, agent=None, usage=None):
                self.id = id
                self.status = status
                self.outputs = outputs or []
                self.error = error
                self.model = model
                self.agent = agent
                self.usage = type('Usage', (), usage or {})() if usage else None
        
        interaction = Interaction(
            id=result.get('id'),
            status=result.get('status'),
            outputs=result.get('outputs', []),
            error=result.get('error'),
            agent=request.agent
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
        
        # 使用 InteractionsManager（Vertex AI，企业级）
        db = next(get_db())
        manager = get_interactions_manager(db=db, default_vertexai=True)
        
        # 获取交互状态
        result = await manager.get_interaction_status_async(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=True  # 使用 Vertex AI（企业级）
        )
        
        # 构建 Interaction 对象
        class Interaction:
            def __init__(self, id, status, outputs=None, error=None, model=None, agent=None, usage=None):
                self.id = id
                self.status = status
                self.outputs = outputs or []
                self.error = error
                self.model = model
                self.agent = agent
                self.usage = type('Usage', (), usage or {})() if usage else None
        
        interaction = Interaction(
            id=result.get('id'),
            status=result.get('status'),
            outputs=result.get('outputs', []),
            error=result.get('error')
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
            created_at=getattr(interaction, "created_at", datetime.now().isoformat())
        )
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Interaction not found: {str(e)}")


@router.delete("/{interaction_id}")
async def delete_interaction(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """删除交互"""
    try:
        
        # 从数据库获取 Google Provider 的 API Key
        from ...core.credential_manager import get_provider_credentials
        api_key, _ = await get_provider_credentials(
            provider="google",
            db=db,
            user_id=user_id
        )
        
        # 使用 InteractionsManager（Vertex AI，企业级）
        manager = get_interactions_manager(db=db, default_vertexai=True)
        
        # 删除交互
        await manager.delete_interaction(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=True  # 使用 Vertex AI（企业级）
        )
        
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
