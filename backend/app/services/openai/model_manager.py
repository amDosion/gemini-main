"""
OpenAI 模型管理器

处理 OpenAI 的模型列表获取。
"""
from typing import List
import logging
from openai import AsyncOpenAI
from ..common.model_capabilities import ModelConfig, Capabilities

logger = logging.getLogger(__name__)


class ModelManager:
    """
    OpenAI 模型管理器
    
    负责获取和管理可用模型列表。
    """
    
    def __init__(self, client: AsyncOpenAI):
        """
        初始化模型管理器
        
        Args:
            client: AsyncOpenAI 客户端实例
        """
        self.client = client
        logger.info("[OpenAI ModelManager] Initialized")
    
    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表
        
        Returns:
            ModelConfig 对象列表
        """
        try:
            logger.info("[OpenAI ModelManager] Fetching available models")
            
            # Get models from OpenAI API
            models = await self.client.models.list()
            
            result = []
            for model in models.data:
                model_id = model.id
                lower_id = model_id.lower()
                
                # 推断能力
                vision = any(kw in lower_id for kw in ["vision", "gpt-4o", "gpt-4-turbo"])
                reasoning = any(kw in lower_id for kw in ["o1", "o3"])
                coding = any(kw in lower_id for kw in ["code", "codex"])
                
                result.append(ModelConfig(
                    id=model_id,
                    name=model_id,
                    description=f"OpenAI model: {model_id}",
                    capabilities=Capabilities(
                        vision=vision,
                        search=False,
                        reasoning=reasoning,
                        coding=coding
                    ),
                    context_window=None
                ))
            
            logger.info(f"[OpenAI ModelManager] Found {len(result)} models")
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI ModelManager] Error fetching models: {e}", exc_info=True)
            raise
