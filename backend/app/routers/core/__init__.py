"""
核心路由模块

包含统一入口路由：
- chat.py: 统一聊天路由 /api/modes/{provider}/chat
- modes.py: 统一模式路由 /api/modes/{provider}/{mode}
- attachments.py: 附件路由 /api/temp-images/{attachment_id}
"""

from .chat import router as chat
from .modes import router as modes
from . import attachments

__all__ = ["chat", "modes", "attachments"]
