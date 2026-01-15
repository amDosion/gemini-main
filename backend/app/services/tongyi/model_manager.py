"""
Model Manager Module for Tongyi (Qwen)

Handles fetching and managing available models using two-tier merge strategy:
1. OpenAI Compatible API (dynamic - ~167 text models)
2. Official Bailian Models JSON (static - 187 models from official docs)
"""

import logging
import json
import os
from typing import List
from openai import AsyncOpenAI

from ..common.model_capabilities import ModelConfig, build_model_config

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Manages model listing for Tongyi provider.
    
    Uses two-tier merge strategy:
    1. OpenAI Compatible API (dynamic)
    2. Official Bailian Models JSON (static)
    """
    
    def __init__(self, api_key: str, api_url: str = None):
        """
        Initialize model manager.
        
        Args:
            api_key: Tongyi API key
            api_url: Optional custom API URL (defaults to DashScope compatible endpoint)
        """
        self.api_key = api_key
        self.api_url = api_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    def _load_official_models(self) -> List[str]:
        """
        Load models from official Bailian JSON file.
        
        Returns:
            List of model IDs from official documentation
        """
        try:
            # 获取 JSON 文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, "aliyun_bailian_models.json")
            
            if not os.path.exists(json_path):
                logger.warning(f"[Tongyi ModelManager] Official models JSON not found: {json_path}")
                return []
            
            # 读取 JSON 文件
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取所有模型名称
            model_ids = []
            for category, models in data.items():
                for model in models:
                    model_id = model.get('模型名称')
                    if model_id:
                        model_ids.append(model_id)
            
            logger.info(f"[Tongyi ModelManager] Loaded {len(model_ids)} models from official JSON")
            return model_ids
        
        except Exception as e:
            logger.error(f"[Tongyi ModelManager] Failed to load official models JSON: {e}")
            return []
    
    async def get_available_models(self) -> List[ModelConfig]:
        """
        Get list of available models using two-tier merge strategy.
        
        Returns:
            List of ModelConfig objects (deduplicated and sorted)
        """
        # 使用 set 存储模型 ID 字符串（用于去重）
        all_model_ids = set()
        
        # ==================== Tier 1: OpenAI Compatible API ====================
        try:
            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_url,
                timeout=30.0
            )
            
            models_response = await client.models.list()
            api_model_ids = [model.id for model in models_response.data]
            all_model_ids.update(api_model_ids)
            
            if api_model_ids:
                logger.info(f"[Tongyi ModelManager] Tier 1 (API): Fetched {len(api_model_ids)} models")
            else:
                logger.warning("[Tongyi ModelManager] Tier 1 (API): Empty model list returned")
        
        except Exception as e:
            logger.warning(f"[Tongyi ModelManager] Tier 1 (API) failed: {e}")
        
        # ==================== Tier 2: Official Bailian Models JSON ====================
        official_model_ids = self._load_official_models()
        
        if official_model_ids:
            official_count_before = len(all_model_ids)
            all_model_ids.update(official_model_ids)
            official_added = len(all_model_ids) - official_count_before
            
            if official_added > 0:
                logger.info(f"[Tongyi ModelManager] Tier 2 (Official JSON): Added {official_added} models")

        # ==================== Build ModelConfig Objects ====================
        if all_model_ids:
            sorted_model_ids = sorted(list(all_model_ids))
            model_configs = [build_model_config("tongyi", model_id) for model_id in sorted_model_ids]
            logger.info(f"[Tongyi ModelManager] Final merged list: {len(model_configs)} models")
            return model_configs
        else:
            logger.warning("[Tongyi ModelManager] All tiers failed, returning empty list")
            return []
