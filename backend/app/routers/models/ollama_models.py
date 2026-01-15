"""
Ollama 模型管理 API 路由

提供模型列表、详情、删除、下载等管理功能。
所有端点使用 /api/ollama 前缀。

设计说明:
- 使用查询参数传递 base_url 和 api_key (与前端配置一致)
- 下载端点使用 SSE 流式响应返回进度
- 错误处理遵循 FastAPI 标准异常格式
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import logging

# 导入 OllamaService
try:
    from ...services.ollama import OllamaService
except ImportError:
    try:
        from services.ollama import OllamaService
    except ImportError:
        from backend.app.services.ollama import OllamaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ollama", tags=["ollama"])


# ==================== 请求/响应模型 ====================

class PullModelRequest(BaseModel):
    """模型下载请求"""
    model: str
    base_url: str = "http://localhost:11434"
    api_key: Optional[str] = None


class DeleteModelResponse(BaseModel):
    """模型删除响应"""
    success: bool
    message: str


# ==================== 辅助函数 ====================

def _get_ollama_service(base_url: str, api_key: Optional[str] = None) -> OllamaService:
    """
    创建 OllamaService 实例
    
    Args:
        base_url: Ollama API 地址
        api_key: API 密钥 (可选)
    
    Returns:
        OllamaService 实例
    """
    return OllamaService(
        api_key=api_key or "ollama",
        api_url=base_url
    )


# ==================== API 端点 ====================

@router.get("/models")
async def list_models(
    base_url: str = Query(default="http://localhost:11434", description="Ollama API 地址"),
    api_key: Optional[str] = Query(default=None, description="API 密钥")
):
    """
    获取本地模型列表
    
    调用 Ollama /api/tags 端点获取所有本地模型。
    
    Returns:
        models: 模型列表，每个模型包含 name, size, digest, modified_at, details
    """
    try:
        service = _get_ollama_service(base_url, api_key)
        models = await service.get_available_models_detailed()
        await service.close()
        
        return {"models": models}
    
    except Exception as e:
        logger.error(f"[Ollama API] Failed to list models: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Ollama service unavailable",
                "detail": str(e)
            }
        )


@router.get("/models/{name:path}")
async def get_model_info(
    name: str,
    base_url: str = Query(default="http://localhost:11434", description="Ollama API 地址"),
    api_key: Optional[str] = Query(default=None, description="API 密钥")
):
    """
    获取模型详情
    
    调用 Ollama /api/show 端点获取模型详细信息。
    
    Args:
        name: 模型名称 (如 llama3:latest)
    
    Returns:
        模型详情，包含 modelfile, parameters, template, details, model_info, capabilities
    """
    try:
        service = _get_ollama_service(base_url, api_key)
        model_info = await service.get_model_info(name)
        await service.close()
        
        # 转换为 API 响应格式
        return {
            "modelfile": model_info.modelfile or "",
            "parameters": model_info.parameters or "",
            "template": model_info.template or "",
            "details": {
                "format": model_info.details.get("format", "") if model_info.details else "",
                "family": model_info.details.get("family", "") if model_info.details else "",
                "parameter_size": model_info.details.get("parameter_size", "") if model_info.details else "",
                "quantization_level": model_info.details.get("quantization_level", "") if model_info.details else ""
            },
            "model_info": model_info.model_info or {},
            "capabilities": _extract_capabilities(model_info)
        }
    
    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "404" in error_str:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Model not found",
                    "model": name
                }
            )
        
        logger.error(f"[Ollama API] Failed to get model info for {name}: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Ollama service unavailable",
                "detail": str(e)
            }
        )


def _extract_capabilities(model_info) -> list:
    """从模型信息中提取能力列表"""
    capabilities = ["completion"]  # 所有模型都支持补全
    
    if model_info.capabilities:
        if model_info.capabilities.supports_vision:
            capabilities.append("vision")
        if model_info.capabilities.supports_tools:
            capabilities.append("tools")
        if model_info.capabilities.supports_thinking:
            capabilities.append("thinking")
    
    return capabilities


@router.delete("/models/{name:path}")
async def delete_model(
    name: str,
    base_url: str = Query(default="http://localhost:11434", description="Ollama API 地址"),
    api_key: Optional[str] = Query(default=None, description="API 密钥")
) -> DeleteModelResponse:
    """
    删除模型
    
    调用 Ollama /api/delete 端点删除本地模型。
    
    Args:
        name: 模型名称 (如 llama3:latest)
    
    Returns:
        success: 是否成功
        message: 操作消息
    """
    try:
        service = _get_ollama_service(base_url, api_key)
        await service.delete_model(name)
        await service.close()
        
        return DeleteModelResponse(
            success=True,
            message=f"Model '{name}' deleted successfully"
        )
    
    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "404" in error_str:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Model not found",
                    "model": name
                }
            )
        
        logger.error(f"[Ollama API] Failed to delete model {name}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e)
            }
        )


@router.post("/pull")
async def pull_model(request: PullModelRequest):
    """
    下载模型 (SSE 流式响应)
    
    调用 Ollama /api/pull 端点下载模型，使用 SSE 返回下载进度。
    
    Request Body:
        model: 模型名称 (如 llama3:latest)
        base_url: Ollama API 地址
        api_key: API 密钥 (可选)
    
    Returns:
        SSE 流，每个事件包含:
        - status: 状态描述
        - digest: 当前下载的文件摘要 (可选)
        - total: 总大小 bytes (可选)
        - completed: 已完成大小 bytes (可选)
    """
    async def generate_progress():
        service = None
        try:
            service = _get_ollama_service(request.base_url, request.api_key)
            
            async for progress in service.pull_model(request.model):
                # 转换为 SSE 格式
                yield f"data: {json.dumps(progress)}\n\n"
            
            # 发送完成事件
            yield f"data: {json.dumps({'status': 'success'})}\n\n"
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Ollama API] Pull failed for {request.model}: {error_msg}")
            yield f"data: {json.dumps({'status': 'error', 'error': error_msg})}\n\n"
        
        finally:
            if service:
                await service.close()
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
