"""
Ollama 模型管理 API 路由

提供模型列表、详情、删除、下载等管理功能。
所有端点使用 /api/ollama 前缀。

设计说明:
- 使用查询参数传递 base_url；Ollama API key 仅通过 X-Ollama-Api-Key header 传递
- 下载端点使用 SSE 流式响应返回进度
- 错误处理遵循 FastAPI 标准异常格式
"""
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, JsonValue
import json
import logging

from ...services.common.provider_factory import ProviderFactory
from ...utils.log_sanitization import summarize_text_for_log
from ...utils.url_security import UnsafeURLError

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
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"
BASE_URL_PATTERN = r"^[^\x00-\x1F\x7F]*$"


# ==================== 请求/响应模型 ====================

class PullModelRequest(BaseModel):
    """模型下载请求"""
    model: str = Field(min_length=1, max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    base_url: str = Field(default="http://localhost:11434", max_length=4096, pattern=BASE_URL_PATTERN)


class DeleteModelResponse(BaseModel):
    """模型删除响应"""
    success: bool
    message: str = Field(max_length=512)


class OllamaModelDetailsResponse(BaseModel):
    format: str = Field(default="", max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    family: str = Field(default="", max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    parameter_size: str = Field(default="", max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    quantization_level: str = Field(default="", max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)


class OllamaModelResponse(BaseModel):
    name: str = Field(default="", max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    model: str = Field(default="", max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    size: int = Field(default=0, ge=0, le=9_000_000_000_000_000)
    digest: str = Field(default="", max_length=512, pattern=NO_CONTROL_CHARS_PATTERN)
    modified_at: str = Field(default="", max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    details: OllamaModelDetailsResponse = Field(default_factory=OllamaModelDetailsResponse)


class OllamaModelsResponse(BaseModel):
    models: list[OllamaModelResponse] = Field(max_length=10_000)


class OllamaModelInfoResponse(BaseModel):
    modelfile: str = Field(max_length=1_000_000)
    parameters: str = Field(max_length=1_000_000)
    template: str = Field(max_length=1_000_000)
    details: OllamaModelDetailsResponse
    model_info: dict[str, JsonValue] = Field(max_length=10_000)
    capabilities: list[str] = Field(max_length=64)


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
        api_url=_validate_ollama_base_url(base_url)
    )


def _validate_ollama_base_url(base_url: str) -> str:
    try:
        validated = ProviderFactory._validate_provider_api_url("ollama", base_url)
    except UnsafeURLError as exc:
        raise _http_error(
            status_code=400,
            code="ollama_base_url_rejected",
            message="Ollama base URL rejected by SSRF policy",
            details={"reason": str(exc)},
        ) from exc
    return str(validated or base_url)


def _http_error(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Optional[dict] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )


def _safe_error_details(exc: Exception, **extra) -> dict:
    details = {
        "error_type": type(exc).__name__,
        "error": summarize_text_for_log(exc, label="error"),
    }
    details.update(extra)
    return details


# ==================== API 端点 ====================

@router.get("/models", response_model=OllamaModelsResponse)
async def list_models(
    base_url: str = Query(
        default="http://localhost:11434",
        max_length=4096,
        pattern=BASE_URL_PATTERN,
        description="Ollama API 地址",
    ),
    api_key: Optional[str] = Header(
        default=None,
        alias="X-Ollama-Api-Key",
        max_length=4096,
        pattern=NO_CONTROL_CHARS_PATTERN,
        description="Ollama API 密钥",
    ),
):
    """
    获取本地模型列表
    
    调用 Ollama /api/tags 端点获取所有本地模型。
    
    Returns:
        models: 模型列表，每个模型包含 name, size, digest, modified_at, details
    """
    service: Optional[OllamaService] = None
    try:
        service = _get_ollama_service(base_url, api_key)
        models = await service.get_available_models_detailed()
        return {"models": models}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[Ollama API] Failed to list models: %s",
            summarize_text_for_log(e, label="error"),
        )
        raise _http_error(
            status_code=503,
            code="ollama_service_unavailable",
            message="Ollama service unavailable",
            details=_safe_error_details(e),
        )
    finally:
        if service is not None:
            await service.close()


@router.get("/models/{name:path}", response_model=OllamaModelInfoResponse)
async def get_model_info(
    name: str = Path(..., min_length=1, max_length=256, pattern=NO_CONTROL_CHARS_PATTERN),
    base_url: str = Query(
        default="http://localhost:11434",
        max_length=4096,
        pattern=BASE_URL_PATTERN,
        description="Ollama API 地址",
    ),
    api_key: Optional[str] = Header(
        default=None,
        alias="X-Ollama-Api-Key",
        max_length=4096,
        pattern=NO_CONTROL_CHARS_PATTERN,
        description="Ollama API 密钥",
    ),
):
    """
    获取模型详情
    
    调用 Ollama /api/show 端点获取模型详细信息。
    
    Args:
        name: 模型名称 (如 llama3:latest)
    
    Returns:
        模型详情，包含 modelfile, parameters, template, details, model_info, capabilities
    """
    service: Optional[OllamaService] = None
    try:
        service = _get_ollama_service(base_url, api_key)
        model_info = await service.get_model_info(name)
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
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "404" in error_str:
            raise _http_error(
                status_code=404,
                code="ollama_model_not_found",
                message="Model not found",
                details={"model": summarize_text_for_log(name, label="model")},
            )

        logger.error(
            "[Ollama API] Failed to get model info for %s: %s",
            summarize_text_for_log(name, label="model"),
            summarize_text_for_log(e, label="error"),
        )
        raise _http_error(
            status_code=503,
            code="ollama_service_unavailable",
            message="Ollama service unavailable",
            details=_safe_error_details(e, model=summarize_text_for_log(name, label="model")),
        )
    finally:
        if service is not None:
            await service.close()


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


@router.delete("/models/{name:path}", response_model=DeleteModelResponse)
async def delete_model(
    name: str = Path(..., min_length=1, max_length=256, pattern=NO_CONTROL_CHARS_PATTERN),
    base_url: str = Query(
        default="http://localhost:11434",
        max_length=4096,
        pattern=BASE_URL_PATTERN,
        description="Ollama API 地址",
    ),
    api_key: Optional[str] = Header(
        default=None,
        alias="X-Ollama-Api-Key",
        max_length=4096,
        pattern=NO_CONTROL_CHARS_PATTERN,
        description="Ollama API 密钥",
    ),
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
    service: Optional[OllamaService] = None
    try:
        service = _get_ollama_service(base_url, api_key)
        await service.delete_model(name)
        return DeleteModelResponse(
            success=True,
            message=f"Model '{name}' deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "404" in error_str:
            raise _http_error(
                status_code=404,
                code="ollama_model_not_found",
                message="Model not found",
                details={"model": summarize_text_for_log(name, label="model")},
            )

        logger.error(
            "[Ollama API] Failed to delete model %s: %s",
            summarize_text_for_log(name, label="model"),
            summarize_text_for_log(e, label="error"),
        )
        raise _http_error(
            status_code=500,
            code="ollama_model_delete_failed",
            message="Failed to delete model",
            details=_safe_error_details(e, model=summarize_text_for_log(name, label="model")),
        )
    finally:
        if service is not None:
            await service.close()


@router.post(
    "/pull",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-sent Ollama pull progress events",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "maxLength": 1_000_000,
                    }
                }
            },
        }
    },
)
async def pull_model(
    request: PullModelRequest,
    api_key: Optional[str] = Header(
        default=None,
        alias="X-Ollama-Api-Key",
        max_length=4096,
        pattern=NO_CONTROL_CHARS_PATTERN,
        description="Ollama API 密钥",
    ),
):
    """
    下载模型 (SSE 流式响应)
    
    调用 Ollama /api/pull 端点下载模型，使用 SSE 返回下载进度。
    
    Request Body:
        model: 模型名称 (如 llama3:latest)
        base_url: Ollama API 地址
    
    Returns:
        SSE 流，每个事件包含:
        - status: 状态描述
        - digest: 当前下载的文件摘要 (可选)
        - total: 总大小 bytes (可选)
        - completed: 已完成大小 bytes (可选)
    """
    validated_base_url = _validate_ollama_base_url(request.base_url)

    async def generate_progress():
        service = None
        try:
            service = _get_ollama_service(validated_base_url, api_key)
            
            async for progress in service.pull_model(request.model):
                # 转换为 SSE 格式
                yield f"data: {json.dumps(progress)}\n\n"
            
            # 发送完成事件
            yield f"data: {json.dumps({'status': 'success'})}\n\n"
        
        except Exception as e:
            error_msg = summarize_text_for_log(e, label="error")
            logger.error(
                "[Ollama API] Pull failed for %s: %s",
                summarize_text_for_log(request.model, label="model"),
                error_msg,
            )
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
