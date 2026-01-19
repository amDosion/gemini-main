"""
Logging configuration for the FastAPI backend application.

This module sets up structured logging with timestamps, log levels,
and proper formatting for better debugging and monitoring.
"""

import logging
import sys
import os
from datetime import datetime

# 全部使用 ASCII 前缀，避免表情符号在部分环境下显示异常
LOG_PREFIXES = {
    'search': '[SEARCH]',
    'webpage': '[PAGE]',
    'selenium': '[BROWSER]',
    'screenshot': '[SCREENSHOT]',
    'success': '[OK]',
    'error': '[ERROR]',
    'warning': '[WARN]',
    'info': '[INFO]',
    'startup': '[START]',
    'request': '[REQUEST]',
    'action': '[ACTION]',
    'navigate': '[NAV]',
}


class FlushingStreamHandler(logging.StreamHandler):
    """
    StreamHandler that immediately flushes after each emit.
    This fixes log buffering issues in Uvicorn and ensures real-time log output.
    """
    def __init__(self, stream=None):
        super().__init__(stream)
        # 确保使用 stderr（Uvicorn 默认使用 stderr）
        if stream is None:
            import sys
            self.stream = sys.stderr
    
    def emit(self, record):
        try:
            super().emit(record)
            self.flush()
            # 额外确保 stderr 被刷新
            if hasattr(self.stream, 'flush'):
                self.stream.flush()
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "backend", level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with console output and proper formatting.
    
    For most loggers, we just set the level and let them propagate to root logger.
    Only "main" logger gets its own handler to ensure startup logs are visible.

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Only "main" logger gets its own handler (for startup logs)
    # All other loggers will propagate to root logger
    if name == "main":
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # ✅ 使用 stderr 而不是 stdout（Uvicorn 默认使用 stderr）
        # Create flushing console handler with UTF-8 encoding for Windows compatibility
        console_handler = FlushingStreamHandler(sys.stderr)
        console_handler.setLevel(level)

        # Force UTF-8 encoding on Windows
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass  # If reconfigure fails, continue without it

        # Create formatter with timestamp
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)
        logger.propagate = False  # Don't propagate to avoid duplicates
    else:
        # For other loggers, just set level and let them propagate to root
        logger.propagate = True

    return logger


def setup_root_logger(level: int = logging.INFO) -> None:
    """
    Set up root logger to ensure all child loggers can output logs.
    
    This is important for modules that use logging.getLogger(__name__)
    without explicitly configuring handlers.
    
    Only sets the level, handler is added once to avoid duplicates.
    
    Args:
        level: Logging level (default: INFO)
    """
    import sys
    root_logger = logging.getLogger()
    
    # Only configure if not already configured
    if not root_logger.handlers:
        root_logger.setLevel(level)
        
        # ✅ 使用 stderr 而不是 stdout（Uvicorn 默认使用 stderr）
        # 这样可以确保日志不会被 Uvicorn 拦截
        console_handler = FlushingStreamHandler(sys.stderr)
        console_handler.setLevel(level)
        
        # Force UTF-8 encoding on Windows
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
        
        # Create formatter with timestamp
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        root_logger.addHandler(console_handler)
    else:
        # Just set level if handler already exists
        root_logger.setLevel(level)


# Setup root logger to ensure all child loggers work
# This will be called once, and child loggers will propagate to it
setup_root_logger()

# Create default logger instance for this module
# Note: "main" logger will have its own handler (propagate=False)
# All other loggers (using logging.getLogger(__name__)) will propagate to root logger
logger = setup_logger("backend")

# 确保所有常见的服务模块 logger 都设置了正确的级别
# 这样可以避免因为级别为 NOTSET (0) 而导致日志不显示
def ensure_service_loggers():
    """确保所有服务模块的 logger 都设置了正确的级别"""
    import sys
    service_modules = [
        "app.routers.core.modes",
        "app.routers.core.attachments",
        "app.services.gemini.google_service",
        "app.services.gemini.image_generator",
        "app.services.gemini.imagen_coordinator",
        "app.services.gemini.imagen_gemini_api",
        "app.services.gemini.imagen_vertex_ai",
        "app.services.tongyi.tongyi_service",
        "app.services.tongyi.image_generation",
        "app.services.common.attachment_service",
        "app.core.credential_manager",
        "app.services.common.provider_factory",
    ]
    
    for module_name in service_modules:
        service_logger = logging.getLogger(module_name)
        # 如果级别是 NOTSET (0)，设置为 INFO
        if service_logger.level == 0:
            service_logger.setLevel(logging.INFO)
        # 确保 propagate 为 True
        service_logger.propagate = True

# 在模块导入时确保服务 logger 配置正确
ensure_service_loggers()
