# Services module

# 向后兼容：从 gemini 子模块导出 GoogleService
from .gemini import GoogleService

__all__ = ['GoogleService']
