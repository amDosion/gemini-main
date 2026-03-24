"""
Grok 服务模块

架构说明：
- GrokService: 主协调器，统一入口（通过 ProviderFactory.create("grok") 获取）
- 所有子服务由 GrokService 协调，不应直接调用

子服务（由 GrokService 委托）：
- ChatHandler: 聊天服务
- ImageGenerator: 图片生成服务
- ImageEditor: 图片编辑服务
- VideoGenerator: 视频生成服务
- ModelManager: 模型管理服务
"""

from .grok_service import GrokService

__all__ = [
    "GrokService",
]
