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
        
        Uses PathUtils to resolve file path for better compatibility across different environments.
        
        Returns:
            List of model IDs from official documentation
        """
        logger.info("[Tongyi ModelManager] ========== 开始加载官方模型JSON文件 ==========")
        json_path = None
        tried_paths = []
        
        try:
            # 方法1: 使用 PathUtils 解析相对路径（推荐方式）
            try:
                from ...core.path_utils import resolve_relative_path
                relative_path = "backend/app/services/tongyi/aliyun_bailian_models.json"
                candidate_path = resolve_relative_path(relative_path)
                tried_paths.append(("PathUtils", candidate_path))
                logger.info(f"[Tongyi ModelManager] [方法1] PathUtils路径: {candidate_path}")
                logger.info(f"[Tongyi ModelManager] [方法1] 文件存在: {os.path.exists(candidate_path)}")
                
                if os.path.exists(candidate_path):
                    json_path = candidate_path
                    logger.info(f"[Tongyi ModelManager] ✅ [方法1] 成功找到JSON文件: {json_path}")
            except Exception as e:
                logger.warning(f"[Tongyi ModelManager] [方法1] PathUtils方法失败: {e}")
            
            # 方法2: 使用 __file__ 相对路径（回退方案）
            if not json_path:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                candidate_path = os.path.join(current_dir, "aliyun_bailian_models.json")
                tried_paths.append(("__file__ relative", candidate_path))
                logger.info(f"[Tongyi ModelManager] [方法2] __file__路径: {candidate_path}")
                logger.info(f"[Tongyi ModelManager] [方法2] 文件存在: {os.path.exists(candidate_path)}")
                
                if os.path.exists(candidate_path):
                    json_path = candidate_path
                    logger.info(f"[Tongyi ModelManager] ✅ [方法2] 成功找到JSON文件: {json_path}")
            
            # 如果所有方法都失败，记录详细信息
            if not json_path:
                logger.error(
                    f"[Tongyi ModelManager] ❌ 官方模型JSON文件未找到！尝试的路径:\n" +
                    "\n".join([f"  - {method}: {path} (exists: {os.path.exists(path)})" 
                              for method, path in tried_paths])
                )
                logger.error(f"[Tongyi ModelManager] 当前 __file__: {__file__}")
                logger.error(f"[Tongyi ModelManager] 当前工作目录: {os.getcwd()}")
                logger.error("[Tongyi ModelManager] ========== JSON文件加载失败 ==========")
                return []
            
            # 读取 JSON 文件
            logger.info(f"[Tongyi ModelManager] 📂 正在读取JSON文件: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取所有模型名称
            model_ids = []
            category_counts = {}
            for category, models in data.items():
                category_count = 0
                for model in models:
                    model_id = model.get('模型名称')
                    if model_id:
                        model_ids.append(model_id)
                        category_count += 1
                category_counts[category] = category_count
                logger.info(f"[Tongyi ModelManager]   - {category}: {category_count} 个模型")
            
            logger.info(f"[Tongyi ModelManager] ✅ 成功加载 {len(model_ids)} 个模型 from JSON: {json_path}")
            logger.info("[Tongyi ModelManager] ========== JSON文件加载完成 ==========")
            return model_ids
        
        except json.JSONDecodeError as e:
            logger.error(f"[Tongyi ModelManager] ❌ JSON解析错误 in {json_path}: {e}")
            logger.error("[Tongyi ModelManager] ========== JSON文件加载失败 ==========")
            return []
        except Exception as e:
            logger.error(
                f"[Tongyi ModelManager] ❌ 加载官方模型JSON失败: {e}\n"
                f"尝试的路径: {tried_paths}\n"
                f"当前 __file__: {__file__}",
                exc_info=True
            )
            logger.error("[Tongyi ModelManager] ========== JSON文件加载失败 ==========")
            return []
    
    async def get_available_models(self) -> List[ModelConfig]:
        """
        Get list of available models using two-tier merge strategy.
        
        Returns:
            List of ModelConfig objects (deduplicated and sorted)
        """
        logger.info("[Tongyi ModelManager] ========== 开始获取可用模型列表 ==========")
        # 使用 set 存储模型 ID 字符串（用于去重）
        all_model_ids = set()
        
        # ==================== Tier 1: OpenAI Compatible API ====================
        logger.info("[Tongyi ModelManager] [Tier 1] 开始从OpenAI兼容API获取模型...")
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
                logger.info(f"[Tongyi ModelManager] ✅ [Tier 1] 从API获取 {len(api_model_ids)} 个模型")
            else:
                logger.warning("[Tongyi ModelManager] ⚠️ [Tier 1] API返回空模型列表")
        
        except Exception as e:
            logger.warning(f"[Tongyi ModelManager] ❌ [Tier 1] API获取失败: {e}")
        
        # ==================== Tier 2: Official Bailian Models JSON ====================
        logger.info("[Tongyi ModelManager] [Tier 2] 开始从官方JSON文件加载模型...")
        official_model_ids = self._load_official_models()
        
        if official_model_ids:
            official_count_before = len(all_model_ids)
            all_model_ids.update(official_model_ids)
            official_added = len(all_model_ids) - official_count_before
            
            if official_added > 0:
                logger.info(f"[Tongyi ModelManager] ✅ [Tier 2] 从JSON添加 {official_added} 个新模型")
                logger.info(f"[Tongyi ModelManager]   - JSON文件模型总数: {len(official_model_ids)}")
                logger.info(f"[Tongyi ModelManager]   - 合并前模型数: {official_count_before}")
                logger.info(f"[Tongyi ModelManager]   - 合并后模型数: {len(all_model_ids)}")
            else:
                logger.info(f"[Tongyi ModelManager] ℹ️ [Tier 2] JSON中的 {len(official_model_ids)} 个模型已全部存在于API结果中")
        else:
            logger.warning("[Tongyi ModelManager] ❌ [Tier 2] 未能从JSON文件加载任何模型")

        # ==================== Build ModelConfig Objects ====================
        if all_model_ids:
            sorted_model_ids = sorted(list(all_model_ids))
            model_configs = [build_model_config("tongyi", model_id) for model_id in sorted_model_ids]
            logger.info(f"[Tongyi ModelManager] ✅ 最终合并列表: {len(model_configs)} 个模型")
            logger.info(f"[Tongyi ModelManager]   - 来源统计:")
            logger.info(f"[Tongyi ModelManager]     * API获取: {len(api_model_ids) if 'api_model_ids' in locals() else 0} 个")
            logger.info(f"[Tongyi ModelManager]     * JSON文件: {len(official_model_ids)} 个")
            logger.info(f"[Tongyi ModelManager]     * 合并去重后: {len(model_configs)} 个")
            logger.info("[Tongyi ModelManager] ========== 模型列表获取完成 ==========")
            return model_configs
        else:
            logger.warning("[Tongyi ModelManager] ❌ 所有层级都失败，返回空列表")
            logger.warning("[Tongyi ModelManager] ========== 模型列表获取失败 ==========")
            return []
