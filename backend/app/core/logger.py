"""
Logging configuration for the FastAPI backend application.

This module sets up structured logging with timestamps, log levels,
and proper formatting for better debugging and monitoring.
"""

import logging
import sys
import os
import threading
import time
from datetime import datetime
from typing import Optional

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


class DatabaseLoggingFilter(logging.Filter):
    """
    日志过滤器：根据数据库配置决定是否显示日志
    
    从 SystemConfig 表中读取 enable_logging 字段（布尔值）：
    - True: 显示日志
    - False: 不显示日志
    
    使用缓存机制，避免每次都查询数据库（缓存时间：30秒）
    """
    
    def __init__(self):
        super().__init__()
        self._cached_value: Optional[bool] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 30.0  # 缓存时间：30秒
        self._lock = threading.Lock()
        self._default_value: bool = True  # 默认值：显示日志（向后兼容）
    
    def _get_enable_logging_from_db(self) -> bool:
        """
        从数据库读取 enable_logging 配置
        
        Returns:
            bool: True 表示显示日志，False 表示不显示日志
        """
        try:
            from .database import SessionLocal
            from ..models.db_models import SystemConfig
            
            db = SessionLocal()
            try:
                config = db.query(SystemConfig).filter(SystemConfig.id == 1).first()
                if config and hasattr(config, 'enable_logging'):
                    return bool(config.enable_logging)
                # 如果字段不存在，返回默认值
                return self._default_value
            finally:
                db.close()
        except Exception as e:
            # 如果查询失败（数据库未初始化、表不存在等），返回默认值
            # 不记录错误，避免循环依赖
            return self._default_value
    
    def _get_cached_value(self) -> bool:
        """
        获取缓存的配置值，如果缓存过期则重新查询数据库
        
        Returns:
            bool: enable_logging 配置值
        """
        current_time = time.time()
        
        with self._lock:
            # 检查缓存是否有效
            if (self._cached_value is not None and 
                current_time - self._cache_timestamp < self._cache_ttl):
                return self._cached_value
            
            # 缓存过期或不存在，重新查询数据库
            try:
                self._cached_value = self._get_enable_logging_from_db()
                self._cache_timestamp = current_time
                return self._cached_value
            except Exception:
                # 查询失败，使用默认值
                return self._default_value
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
            
        Returns:
            bool: True 表示允许记录，False 表示不允许记录
        """
        # 从数据库读取配置（带缓存）
        enable_logging = self._get_cached_value()
        
        # 如果 enable_logging 为 False，不显示日志
        if not enable_logging:
            return False
        
        # 如果 enable_logging 为 True，显示日志
        return True
    
    def refresh_cache(self):
        """
        手动刷新缓存（用于配置更新后立即生效）
        """
        with self._lock:
            self._cached_value = None
            self._cache_timestamp = 0


# 全局日志过滤器实例
_logging_filter = DatabaseLoggingFilter()


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
        
        # ✅ 添加数据库日志过滤器
        console_handler.addFilter(_logging_filter)

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

    ✅ 修复日志重复问题：清除所有现有 handler，确保只有一个

    Args:
        level: Logging level (default: INFO)
    """
    import sys
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # ✅ 修复：始终清除所有现有 handlers，避免重复日志
    # 这解决了 uvicorn 等可能添加额外 handler 导致日志重复的问题
    if root_logger.handlers:
        # 记录现有 handlers 数量（用于调试）
        existing_count = len(root_logger.handlers)
        root_logger.handlers.clear()
        # 不输出日志，避免循环

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

    # ✅ 添加数据库日志过滤器
    console_handler.addFilter(_logging_filter)

    # ✅ 添加唯一标识，方便调试
    console_handler.set_name("gemini_root_handler")

    root_logger.addHandler(console_handler)


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


def refresh_logging_config_cache():
    """
    刷新日志配置缓存

    当 SystemConfig.enable_logging 在数据库中更新后，调用此函数可以立即生效
    而不需要等待缓存过期（默认30秒）

    使用场景：
    - 在更新 SystemConfig.enable_logging 后调用
    - 在系统配置管理界面更新后调用
    """
    _logging_filter.refresh_cache()


def diagnose_logger_handlers(logger_name: str = None) -> dict:
    """
    诊断 logger handler 配置（用于调试日志重复问题）

    Args:
        logger_name: 要诊断的 logger 名称，None 表示 root logger

    Returns:
        包含 handler 信息的字典
    """
    target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()

    handlers_info = []
    for h in target_logger.handlers:
        handler_info = {
            "class": h.__class__.__name__,
            "name": getattr(h, 'name', None) or getattr(h, '_name', 'unnamed'),
            "level": logging.getLevelName(h.level),
            "stream": getattr(h, 'stream', None).__class__.__name__ if hasattr(h, 'stream') else None,
            "formatter": h.formatter._fmt if h.formatter else None,
        }
        handlers_info.append(handler_info)

    return {
        "logger_name": logger_name or "root",
        "level": logging.getLevelName(target_logger.level),
        "propagate": target_logger.propagate,
        "handlers_count": len(target_logger.handlers),
        "handlers": handlers_info,
    }
