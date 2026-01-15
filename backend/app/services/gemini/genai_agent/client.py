"""
GenAI Client 封装和池管理

提供：
- get_genai_client: 获取或创建 GenAI Client
- GenAIClientPool: 客户端池管理
"""

import logging
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# 全局客户端池
_client_pool: Dict[str, Any] = {}


def get_genai_client(
    api_key: str,
    model: Optional[str] = None,
    **kwargs
) -> Any:
    """
    获取或创建 GenAI Client
    
    Args:
        api_key: Google API Key
        model: 模型名称（可选）
        **kwargs: 其他客户端参数
        
    Returns:
        google.genai.Client 实例
    """
    try:
        import google.genai as genai
        
        # 使用 API Key 作为缓存键
        cache_key = f"{api_key}:{model or 'default'}"
        
        if cache_key not in _client_pool:
            # 创建新客户端
            client = genai.Client(api_key=api_key)
            _client_pool[cache_key] = client
            logger.info(f"[GenAI Client] Created new client for model: {model or 'default'}")
        else:
            logger.debug(f"[GenAI Client] Reusing existing client for model: {model or 'default'}")
        
        return _client_pool[cache_key]
        
    except ImportError:
        logger.error("[GenAI Client] google.genai package not available")
        raise ImportError(
            "google.genai package is required for Gemini API mode. "
            "Install it with: pip install google-genai"
        )
    except Exception as e:
        logger.error(f"[GenAI Client] Failed to create client: {e}", exc_info=True)
        raise


def clear_client_pool():
    """清空客户端池"""
    global _client_pool
    _client_pool.clear()
    logger.info("[GenAI Client] Client pool cleared")
