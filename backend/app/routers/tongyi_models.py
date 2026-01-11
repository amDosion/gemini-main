"""
通义千问模型列表 API 路由

提供通义千问的模型列表功能，使用 qwen_native.py 获取可用模型。
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["tongyi-models"])


# ==================== 缓存机制 ====================

class ModelCache:
    """简单的内存缓存"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, tuple] = {}  # key -> (value, expire_time)
        self._ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[any]:
        """获取缓存值"""
        if key in self._cache:
            value, expire_time = self._cache[key]
            if time.time() < expire_time:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: any) -> None:
        """设置缓存值"""
        expire_time = time.time() + self._ttl
        self._cache[key] = (value, expire_time)
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()


# 全局缓存实例（TTL: 1 小时）
_model_cache = ModelCache(ttl_seconds=3600)


# ==================== 响应模型 ====================

class ModelCapabilities(BaseModel):
    """模型能力"""
    vision: bool
    reasoning: bool
    coding: bool
    search: bool


class ModelConfig(BaseModel):
    """模型配置"""
    id: str
    name: str
    description: str
    capabilities: ModelCapabilities
    baseModelId: str


class ModelsResponse(BaseModel):
    """模型列表响应"""
    models: List[ModelConfig]


# ==================== 模型元数据注册表 ====================

# 与前端 models.ts 保持一致
TONGYI_MODEL_REGISTRY: Dict[str, dict] = {
    "qwen-deep-research": {
        "name": "Qwen Deep Research",
        "description": "Specialized model for deep web research and complex query resolution.",
        "capabilities": {"vision": False, "reasoning": True, "coding": True, "search": True},
        "score": 110
    },
    "qwq-32b": {
        "name": "Qwen QwQ 32B",
        "description": "Reasoning-focused model with Deep Thinking capabilities.",
        "capabilities": {"vision": False, "reasoning": True, "coding": True, "search": False},
        "score": 105
    },
    "qwen-max": {
        "name": "Qwen Max",
        "description": "Alibaba's most capable large model. Excellent at complex reasoning.",
        "capabilities": {"vision": False, "reasoning": False, "coding": True, "search": True},
        "score": 100
    },
    "qwen-plus": {
        "name": "Qwen Plus",
        "description": "Balanced model with strong performance across various tasks.",
        "capabilities": {"vision": False, "reasoning": False, "coding": True, "search": True},
        "score": 90
    },
    "qwen-turbo": {
        "name": "Qwen Turbo",
        "description": "Fast and efficient model for quick responses.",
        "capabilities": {"vision": False, "reasoning": False, "coding": True, "search": True},
        "score": 80
    },
    "qwen-vl-max": {
        "name": "Qwen VL Max",
        "description": "Vision-language model with advanced image understanding.",
        "capabilities": {"vision": True, "reasoning": False, "coding": True, "search": False},
        "score": 95
    },
    "qwen-vl-plus": {
        "name": "Qwen VL Plus",
        "description": "Vision-language model for image analysis and understanding.",
        "capabilities": {"vision": True, "reasoning": False, "coding": True, "search": False},
        "score": 85
    },
    "wanx-v1": {
        "name": "Wanx V1",
        "description": "Text-to-image generation model.",
        "capabilities": {"vision": True, "reasoning": False, "coding": False, "search": False},
        "score": 70
    },
    "wanx-v2": {
        "name": "Wanx V2",
        "description": "Advanced text-to-image generation model.",
        "capabilities": {"vision": True, "reasoning": False, "coding": False, "search": False},
        "score": 75
    },
    "qwen-image-plus": {
        "name": "Qwen Image Plus",
        "description": "Enhanced image generation model.",
        "capabilities": {"vision": True, "reasoning": False, "coding": False, "search": False},
        "score": 72
    }
}


# ==================== 辅助函数 ====================

def convert_to_model_configs(model_configs: List[ModelConfig]) -> List[ModelConfig]:
    """
    转换模型配置
    
    将模型配置列表转换为带有注册表元数据的 ModelConfig 格式
    """
    models = []
    
    for model_config in model_configs:
        # 从注册表获取元数据
        if model_config.id in TONGYI_MODEL_REGISTRY:
            meta = TONGYI_MODEL_REGISTRY[model_config.id]
            models.append(ModelConfig(
                id=model_config.id,
                name=meta["name"],
                description=meta["description"],
                capabilities=ModelCapabilities(**meta["capabilities"]),
                baseModelId=model_config.id
            ))
        else:
            # 默认配置（未知模型）
            lower_id = model_config.id.lower()
            models.append(ModelConfig(
                id=model_config.id,
                name=model_config.id,
                description="DashScope Model",
                capabilities=ModelCapabilities(
                    vision="vl" in lower_id or "image" in lower_id or "wanx" in lower_id,
                    reasoning="qwq" in lower_id or "thinking" in lower_id,
                    coding=True,
                    search=False
                ),
                baseModelId=model_config.id
            ))
    
    # 排序（按注册表中的 score 降序）
    def get_score(model: ModelConfig) -> int:
        if model.id in TONGYI_MODEL_REGISTRY:
            return TONGYI_MODEL_REGISTRY[model.id].get("score", 0)
        return 0
    
    models.sort(key=get_score, reverse=True)
    
    return models


# ==================== API 端点 ====================

@router.get("/tongyi", response_model=ModelsResponse)
async def get_tongyi_models(
    apiKey: str = Query(..., description="DashScope API Key"),
    refresh: bool = Query(False, description="强制刷新缓存")
):
    """
    获取通义千问模型列表
    
    调用 qwen_native.py 获取可用模型列表，并转换为前端期望的格式。
    使用内存缓存（TTL: 1 小时）减少 API 调用。
    
    Args:
        apiKey: DashScope API Key
        refresh: 是否强制刷新缓存
    
    Returns:
        ModelsResponse: 模型列表
    """
    try:
        # 生成缓存 key（基于 API Key 的哈希，避免泄露）
        cache_key = f"models:{hash(apiKey)}"
        
        # 检查缓存
        if not refresh:
            cached = _model_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[Tongyi Models] Cache hit for key {cache_key[:16]}...")
                return ModelsResponse(models=cached)
        
        logger.info("[Tongyi Models] Fetching model list from API")
        
        # 1. 初始化 QwenNativeProvider
        try:
            from ..services.qwen_native import QwenNativeProvider
        except ImportError:
            try:
                from services.qwen_native import QwenNativeProvider
            except ImportError:
                from backend.app.services.qwen_native import QwenNativeProvider
        
        provider = QwenNativeProvider(api_key=apiKey)
        
        # 2. 获取模型列表
        model_configs = await provider.get_available_models()
        logger.info(f"[Tongyi Models] Got {len(model_configs)} models from API")
        
        # 3. 转换为 ModelConfig 格式（添加注册表元数据）
        models = convert_to_model_configs(model_configs)
        logger.info(f"[Tongyi Models] Converted to {len(models)} model configs")
        
        # 4. 存入缓存
        _model_cache.set(cache_key, models)
        logger.info(f"[Tongyi Models] Cached models for key {cache_key[:16]}...")
        
        return ModelsResponse(models=models)
    
    except Exception as e:
        logger.error(f"[Tongyi Models] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
