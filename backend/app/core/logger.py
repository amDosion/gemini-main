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
    def emit(self, record):
        try:
            super().emit(record)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "backend", level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with console output and proper formatting.

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create flushing console handler with UTF-8 encoding for Windows compatibility
    console_handler = FlushingStreamHandler(sys.stdout)
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

    return logger


# Create default logger instance
logger = setup_logger()
