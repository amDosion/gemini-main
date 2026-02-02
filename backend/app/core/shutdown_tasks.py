"""
应用关闭任务模块

包含所有应用关闭时需要执行的清理任务。
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def close_browser_sessions(selenium_available: bool, log_prefixes: Dict[str, str]):
    """
    关闭所有浏览器会话

    Args:
        selenium_available: Selenium 是否可用
        log_prefixes: 日志前缀字典
    """
    if not selenium_available:
        return

    try:
        from ..services.gemini.common.browser import close_all_drivers
        close_all_drivers()
        logger.info(f"{log_prefixes['success']} All browser sessions closed on shutdown")
    except Exception as e:
        logger.error(f"{log_prefixes['error']} Error closing browser sessions: {e}")


async def stop_worker_pool(
    worker_pool: Any,
    worker_pool_available: bool,
    worker_mode: str,
    current_pid: int,
    supervisor_pid_key: str,
    log_prefixes: Dict[str, str]
):
    """
    停止 Worker 池并释放 supervisor 锁

    Args:
        worker_pool: Worker 池实例
        worker_pool_available: Worker 池是否可用
        worker_mode: Worker 模式
        current_pid: 当前进程 ID
        supervisor_pid_key: Redis 锁的 key
        log_prefixes: 日志前缀字典
    """
    if not (worker_pool_available and worker_mode == "embedded"):
        return

    # 停止 Worker 池
    logger.info(f"{log_prefixes['info']} Stopping upload worker pool...")
    try:
        await worker_pool.stop()
        logger.info(f"{log_prefixes['success']} Upload worker pool stopped gracefully")
    except Exception as e:
        logger.error(f"{log_prefixes['error']} Error stopping upload worker pool: {e}")

    # 释放 supervisor 锁，与主服务生命周期联动（主服务停止即释放）
    # Redis 可能为远程；若释放失败（网络等），锁靠 60s TTL 自动过期
    try:
        from ..services.common.redis_queue_service import redis_queue

        if redis_queue._redis:
            existing_pid = await redis_queue._redis.get(supervisor_pid_key)
            pid_str = (existing_pid.decode() if isinstance(existing_pid, bytes) else existing_pid) if existing_pid else None

            if pid_str == str(current_pid):
                await redis_queue._redis.delete(supervisor_pid_key)
                logger.info(f"{log_prefixes['success']} Supervisor lock released (PID: {current_pid})")
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to release supervisor lock on shutdown (Redis may be remote): {e}")


async def close_redis_pool(log_prefixes: Dict[str, str]):
    """
    关闭全局 Redis 连接池

    Args:
        log_prefixes: 日志前缀字典
    """
    try:
        from ..services.common.redis_queue_service import GlobalRedisConnectionPool

        global_redis_pool = GlobalRedisConnectionPool.get_instance()
        await global_redis_pool.close()
        logger.info(f"{log_prefixes['success']} Global Redis connection pool closed")
    except Exception as e:
        logger.error(f"{log_prefixes['error']} Error closing global Redis connection pool: {e}")


async def run_all_shutdown_tasks(
    worker_pool: Any,
    worker_pool_available: bool,
    worker_mode: str,
    current_pid: int,
    supervisor_pid_key: str,
    selenium_available: bool,
    log_prefixes: Dict[str, str]
):
    """
    执行所有关闭任务

    Args:
        worker_pool: Worker 池实例
        worker_pool_available: Worker 池是否可用
        worker_mode: Worker 模式
        current_pid: 当前进程 ID
        supervisor_pid_key: Redis 锁的 key
        selenium_available: Selenium 是否可用
        log_prefixes: 日志前缀字典
    """
    logger.info(f"{log_prefixes['info']} Starting shutdown sequence...")

    # 1. 关闭浏览器会话
    await close_browser_sessions(selenium_available, log_prefixes)

    # 2. 停止 Worker 池并释放锁
    await stop_worker_pool(
        worker_pool,
        worker_pool_available,
        worker_mode,
        current_pid,
        supervisor_pid_key,
        log_prefixes
    )

    # 3. 关闭 Redis 连接池
    await close_redis_pool(log_prefixes)

    logger.info(f"{log_prefixes['success']} Shutdown sequence completed")
