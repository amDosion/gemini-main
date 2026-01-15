"""
OpenAI 图片生成器

处理 OpenAI 的图片生成操作（DALL-E）。
"""
from typing import Dict, Any, Optional
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    OpenAI 图片生成器
    
    负责处理所有图片生成相关的操作。
    """
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        """
        初始化图片生成器
        
        Args:
            api_key: OpenAI API key
            base_url: Optional custom API URL
            **kwargs: Additional parameters (timeout, max_retries, etc.)
        """
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        
        # Create AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3)
        )
        
        logger.info(f"[OpenAI ImageGenerator] Initialized with base_url={self.base_url}")
    
    async def generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        使用 DALL-E 生成图片
        
        Args:
            prompt: 图片描述文本
            model: 使用的模型 ('dall-e-2' 或 'dall-e-3')
            **kwargs: 额外参数:
                - size (str): 图片尺寸 ('1024x1024', '1792x1024', '1024x1792')
                - quality (str): 图片质量 ('standard' 或 'hd')
                - style (str): 图片风格 ('vivid' 或 'natural')
                - n (int): 生成图片数量 (1-10)
        
        Returns:
            图片结果列表（统一格式，即使只有一张图片也返回列表）
        """
        try:
            logger.info(f"[OpenAI ImageGenerator] Image generation: model={model}, prompt={prompt[:50]}...")
            
            # Call DALL-E API
            response = await self.client.images.generate(
                model=model,
                prompt=prompt,
                **kwargs
            )
            
            # 转换为统一格式（列表）
            results = []
            for item in response.data:
                results.append({
                    "url": item.url,
                    "revised_prompt": item.revised_prompt if hasattr(item, 'revised_prompt') else None,
                    "mime_type": "image/png"
                })
            
            logger.info(f"[OpenAI ImageGenerator] Image generated: {len(results)} image(s)")
            
            return results
        
        except Exception as e:
            logger.error(f"[OpenAI ImageGenerator] Image generation error: {e}", exc_info=True)
            raise
