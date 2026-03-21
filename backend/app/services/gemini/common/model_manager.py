"""
Model Manager Module

Handles fetching and managing available models.
"""

import logging
import time
import json
import asyncio
import urllib.error
import urllib.request
from typing import List, Optional

from ...common.model_capabilities import ModelConfig, build_model_config

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Manages model listing and capabilities.
    
    Uses stdlib HTTP requests to fetch models from Google REST API.
    """
    
    def __init__(self, api_key: str, api_url: Optional[str] = None):
        """
        Initialize model manager.
        
        Args:
            api_key: Google API key
            api_url: Optional custom API URL
        """
        self.api_key = api_key
        self.api_url = api_url
    
    async def get_available_models(self) -> List[ModelConfig]:
        """
        Get list of available models with capabilities.
        
        Returns:
            List of ModelConfig objects
        """
        try:
            logger.info("[Model Manager] Fetching available models via HTTP - START")
            start_time = time.time()
            
            # 构建 URL
            if self.api_url and '/v1beta' in self.api_url:
                base_url = self.api_url
            else:
                base_url = "https://generativelanguage.googleapis.com/v1beta"
            
            url = f"{base_url}/models"
            logger.info(f"[Model Manager] Requesting models from: {base_url}/models")
            
            # 使用 asyncio.to_thread() 将同步 HTTP 调用包装为异步
            def _call_http() -> str:
                request = urllib.request.Request(
                    url,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Accept": "application/json",
                    },
                )
                try:
                    with urllib.request.urlopen(request, timeout=10.0) as response:
                        return response.read().decode("utf-8", errors="replace")
                except urllib.error.HTTPError as exc:
                    error_body = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"Google API HTTP {exc.code}: {error_body[:500]}"
                    ) from exc
                except urllib.error.URLError as exc:
                    raise RuntimeError(
                        f"Google API request failed: {exc.reason}"
                    ) from exc
            
            try:
                stdout = await asyncio.wait_for(
                    asyncio.to_thread(_call_http),
                    timeout=12.0
                )
                logger.info(
                    f"[Model Manager] request completed in {time.time() - start_time:.2f}s"
                )
            except asyncio.TimeoutError:
                logger.error("[Model Manager] request timed out after 12 seconds")
                raise TimeoutError(
                    "Google API request timed out. Please check your network connection."
                )
            
            # 解析 JSON 响应
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError as e:
                logger.error(f"[Model Manager] Failed to parse JSON response: {e}")
                logger.error(f"[Model Manager] Raw response (first 500 chars): {stdout[:500]}")
                raise ValueError(f"Invalid JSON response from Google API: {e}")
            
            # ✅ 检查是否有错误响应
            if 'error' in data:
                error_info = data.get('error', {})
                error_message = error_info.get('message', 'Unknown error')
                error_code = error_info.get('code', 'Unknown code')
                logger.error(f"[Model Manager] Google API returned an error: {error_code} - {error_message}")
                raise ValueError(f"Google API error ({error_code}): {error_message}")
            
            # ✅ 检查响应格式
            if 'models' not in data or not isinstance(data['models'], list):
                logger.error("[Model Manager] Invalid response format")
                logger.error(f"[Model Manager] Response keys: {list(data.keys())}")
                logger.error(f"[Model Manager] Response content (first 1000 chars): {json.dumps(data, indent=2)[:1000]}")
                raise ValueError(f"Invalid response format: missing 'models' array. Response keys: {list(data.keys())}")
            
            # 构建 ModelConfig
            model_configs = []
            total_models = len(data['models'])

            logger.debug(f"[Model Manager] Processing {total_models} models from API")

            for model in data['models']:
                try:
                    model_id = model.get('name', '')
                    if model_id.startswith('models/'):
                        model_id = model_id.replace('models/', '')

                    display_name = model.get('displayName', None)
                    model_configs.append(build_model_config("google", model_id, display_name=display_name))
                except Exception as e:
                    logger.warning(f"[Model Manager] Failed to process model {model}: {e}")
                    continue

            elapsed = time.time() - start_time
            logger.info(
                f"[Model Manager] Loaded {len(model_configs)}/{total_models} models "
                f"via HTTP in {elapsed:.2f}s"
            )

            return model_configs
        
        except TimeoutError:
            raise
        except Exception as e:
            logger.error(
                f"[Model Manager] Error fetching models via HTTP: {e}",
                exc_info=True,
            )
            raise
