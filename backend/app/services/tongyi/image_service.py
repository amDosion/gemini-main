"""
通义图像服务 - 管理层/协调层

⚠️ 已废弃 (Deprecated)

此模块已被废弃，保留仅为向后兼容。
新代码应该通过 TongyiService 协调器调用 ImageGenerationService。

架构变更说明：
- 旧架构: TongyiService → TongyiImageService → ImageGenerationService（冗余中间层）
- 新架构: TongyiService → ImageGenerationService（直接委托）

Updated: 2026-01-14 - 标记为废弃，推荐使用 TongyiService.generate_image()

原职责:
1. 协调各个图像服务层模块
2. 管理服务实例缓存
3. 处理错误和重试
"""
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass

from .image_generation import (
    ImageGenerationService,
    ImageGenerationRequest,
    ImageGenerationResult
)

logger = logging.getLogger(__name__)


@dataclass
class GenerateImageParams:
    """图像生成参数（管理层入参）"""
    model_id: str
    prompt: str
    aspect_ratio: str = "1:1"
    resolution: str = "1.25K"
    num_images: int = 1
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    style: Optional[str] = None


class TongyiImageService:
    """
    通义图像服务 - 管理层

    作为协调器，管理所有图像相关操作:
    - 文生图 (generate_image) - 由本类协调
    - 图像编辑 - 由 routers/image_edit.py 直接调用 image_edit.py
    - 图像扩展 - 由 routers/image_expand.py 直接调用 image_expand.py
    - 文件上传 - 由各服务模块按需调用 file_upload.py
    """

    # 服务实例缓存（按 api_key）
    _cache: Dict[str, 'TongyiImageService'] = {}

    def __init__(self, api_key: str):
        """
        初始化管理层

        Args:
            api_key: DashScope API Key（由路由层从数据库获取后传入）
        """
        self.api_key = api_key

        # 初始化服务层
        self._generation_service = ImageGenerationService(api_key)

        logger.info("[TongyiImageService] 管理层初始化完成")

    @classmethod
    def get_instance(cls, api_key: str) -> 'TongyiImageService':
        """
        获取服务实例（带缓存）

        Args:
            api_key: API Key

        Returns:
            TongyiImageService 实例
        """
        if api_key not in cls._cache:
            cls._cache[api_key] = cls(api_key)
            logger.info(f"[TongyiImageService] 创建新实例，缓存数量: {len(cls._cache)}")
        return cls._cache[api_key]

    @classmethod
    def clear_cache(cls, api_key: Optional[str] = None):
        """清除缓存"""
        if api_key:
            cls._cache.pop(api_key, None)
        else:
            cls._cache.clear()

    async def generate_image(self, params: GenerateImageParams) -> List[ImageGenerationResult]:
        """
        生成图像

        Args:
            params: 生成参数

        Returns:
            图像生成结果列表
        """
        logger.info(f"[TongyiImageService] 开始生成图像: model={params.model_id}")

        request = ImageGenerationRequest(
            model_id=params.model_id,
            prompt=params.prompt,
            aspect_ratio=params.aspect_ratio,
            resolution=params.resolution,
            num_images=params.num_images,
            negative_prompt=params.negative_prompt,
            seed=params.seed,
            style=params.style,
        )

        try:
            results = await self._generation_service.generate(request)
            logger.info(f"[TongyiImageService] 生成完成: {len(results)} 张图片")
            return results
        except Exception as e:
            logger.error(f"[TongyiImageService] 生成失败: {str(e)}")
            raise

    async def close(self):
        """关闭所有服务"""
        await self._generation_service.close()
