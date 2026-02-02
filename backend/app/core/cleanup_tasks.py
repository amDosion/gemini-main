"""
后台清理任务模块

包含定期执行的清理任务，如清理过期 tokens、浏览器会话等。
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


async def periodic_token_cleanup_task(log_prefixes: Dict[str, str]):
    """
    定期清理过期的 refresh_tokens

    每 24 小时执行一次，删除过期或已撤销超过 7 天的 refresh tokens。

    Args:
        log_prefixes: 日志前缀字典
    """
    # 首次等待 1 小时后再开始清理（避免启动时立即执行）
    await asyncio.sleep(60 * 60)  # 1 小时

    while True:
        try:
            from .database import SessionLocal
            from ..models.db_models import RefreshToken

            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)
                cleanup_threshold = now - timedelta(days=7)
                deleted_count = db.query(RefreshToken).filter(
                    (RefreshToken.expires_at < now) |
                    (
                        (RefreshToken.revoked_at.isnot(None)) &
                        (RefreshToken.revoked_at < cleanup_threshold)
                    )
                ).delete()
                db.commit()

                if deleted_count > 0:
                    logger.info(f"{log_prefixes['info']} Periodic cleanup: removed {deleted_count} expired/revoked refresh tokens")
            finally:
                db.close()

            # 等待 24 小时后再次清理
            await asyncio.sleep(24 * 60 * 60)  # 24 小时

        except asyncio.CancelledError:
            logger.info(f"{log_prefixes['info']} Token cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"{log_prefixes['error']} Periodic token cleanup failed: {e}")
            # 出错后等待 1 小时再重试
            await asyncio.sleep(60 * 60)


async def browser_session_cleanup_task(selenium_available: bool, log_prefixes: Dict[str, str]):
    """
    定期清理浏览器会话

    Args:
        selenium_available: Selenium 是否可用
        log_prefixes: 日志前缀字典
    """
    if not selenium_available:
        return

    while True:
        try:
            await asyncio.sleep(30 * 60)  # 每 30 分钟检查一次
            try:
                from ..services.gemini.common.browser import cleanup_inactive_sessions
                cleanup_inactive_sessions()
            except Exception as e:
                logger.warning(f"{log_prefixes['warning']} Browser session cleanup failed: {e}")
        except asyncio.CancelledError:
            logger.info(f"{log_prefixes['info']} Browser cleanup task cancelled")
            break


def start_cleanup_tasks(
    selenium_available: bool,
    log_prefixes: Dict[str, str]
) -> Dict[str, asyncio.Task]:
    """
    启动所有后台清理任务

    Args:
        selenium_available: Selenium 是否可用
        log_prefixes: 日志前缀字典

    Returns:
        Dict[str, asyncio.Task]: 任务名称 -> 任务对象的字典
    """
    tasks = {}

    # 1. Token 清理任务
    cleanup_task = asyncio.create_task(periodic_token_cleanup_task(log_prefixes))
    tasks['token_cleanup'] = cleanup_task
    logger.info(f"{log_prefixes['success']} Periodic refresh token cleanup task started")

    # 2. 浏览器会话清理任务
    if selenium_available:
        browser_cleanup_task = asyncio.create_task(
            browser_session_cleanup_task(selenium_available, log_prefixes)
        )
        tasks['browser_cleanup'] = browser_cleanup_task
        logger.info(f"{log_prefixes['success']} Browser session cleanup task started")

    return tasks


async def stop_cleanup_tasks(tasks: Dict[str, asyncio.Task], log_prefixes: Dict[str, str]):
    """
    停止所有后台清理任务

    Args:
        tasks: 任务名称 -> 任务对象的字典
        log_prefixes: 日志前缀字典
    """
    logger.info(f"{log_prefixes['info']} Stopping cleanup tasks...")

    for task_name, task in tasks.items():
        if task and not task.done():
            task.cancel()
            logger.debug(f"{log_prefixes['info']} Cancelled {task_name} task")

    # 等待所有任务完成取消
    await asyncio.gather(*tasks.values(), return_exceptions=True)

    logger.info(f"{log_prefixes['success']} All cleanup tasks stopped")
