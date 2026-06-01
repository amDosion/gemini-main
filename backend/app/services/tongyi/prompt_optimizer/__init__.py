"""
Prompt 优化模块

提供文生图、图像编辑和视频的 Prompt 智能优化功能。

模块结构:
- language_detector: 语言检测（中文/英文）
- generation_optimizer: 文生图 Prompt 优化
- edit_optimizer: 图像编辑 Prompt 优化
- video_optimizer: 视频 Prompt 优化

使用方式:
    from .prompt_optimizer import (
        GenerationPromptOptimizer,
        EditPromptOptimizer,
        detect_language,
    )

    # 文生图优化
    optimizer = GenerationPromptOptimizer(api_key)
    result = await optimizer.optimize("一只可爱的猫咪")

    # 编辑优化
    edit_optimizer = EditPromptOptimizer(api_key)
    result = await edit_optimizer.optimize("将背景改为海滩", image_url)
"""

from .language_detector import detect_language, get_magic_suffix
from .generation_optimizer import (
    GenerationPromptOptimizer,
    PromptOptimizeResult,
    PromptOptimizerConfig,
)
from .edit_optimizer import (
    EditPromptOptimizer,
    EditPromptOptimizeResult,
)
from .video_optimizer import (
    VideoPromptOptimizer,
    VideoPromptOptimizeResult,
)

__all__ = [
    # 语言检测
    "detect_language",
    "get_magic_suffix",
    # 文生图优化
    "GenerationPromptOptimizer",
    "PromptOptimizeResult",
    "PromptOptimizerConfig",
    # 编辑优化
    "EditPromptOptimizer",
    "EditPromptOptimizeResult",
    # 视频优化
    "VideoPromptOptimizer",
    "VideoPromptOptimizeResult",
]
