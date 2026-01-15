"""
已废弃路由模块

这些路由已迁移到统一路由（core/modes.py 或 core/chat.py），
保留在此目录以提供向后兼容性。

已废弃的路由：
- generate.py: 已迁移到 core/modes.py
- image_edit.py: 已迁移到 core/modes.py
- image_expand.py: 已迁移到 core/modes.py
- tryon.py: 已迁移到 core/modes.py
- google_modes.py: 已迁移到 core/modes.py
- qwen_modes.py: 已迁移到 core/modes.py
- tongyi_chat.py: 已迁移到 core/chat.py

注意：这些路由仍然可用，但会在响应中添加 deprecation 警告。
建议前端尽快迁移到新的统一路由。
"""

__all__ = []
