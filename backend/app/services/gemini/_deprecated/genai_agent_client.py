"""
GenAI Client 封装和池管理

提供：
- get_genai_client: 获取或创建 GenAI Client
- clear_client_pool: 清理 Gemini API 客户端
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def get_genai_client(
    api_key: str,
    model: Optional[str] = None,
    **kwargs
) -> Any:
    """
    从统一 GeminiClientPool 获取 GenAI Client
    
    Args:
        api_key: Google API Key
        model: 模型名称（可选，仅用于日志）
        **kwargs: 保留参数（当前未使用）
        
    Returns:
        google.genai.Client 实例
    """
    try:
        from ..client_pool import get_client_pool

        pool = get_client_pool()
        client = pool.get_client(api_key=api_key, vertexai=False)
        logger.debug(f"[GenAI Client] Retrieved unified pooled client for model: {model or 'default'}")
        return client

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
    """清理统一池中 Gemini API 客户端。"""
    from ..client_pool import get_client_pool

    pool = get_client_pool()
    closed_count = 0
    for cache_key in list(pool.list_clients().keys()):
        if cache_key.startswith("gemini:"):
            if pool.close_client(cache_key):
                closed_count += 1
    logger.info(f"[GenAI Client] Cleared unified Gemini client entries: {closed_count}")
