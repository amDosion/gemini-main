"""
应用生命周期管理模块

简化的 lifespan 函数，协调启动和关闭任务。
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Dict, Any, Callable

from .startup_tasks import run_all_startup_tasks
from .cleanup_tasks import start_cleanup_tasks, stop_cleanup_tasks
from .worker_supervisor import start_worker_supervisor, stop_worker_supervisor
from .shutdown_tasks import run_all_shutdown_tasks

logger = logging.getLogger(__name__)


def create_lifespan(
    worker_pool: Any,
    worker_pool_available: bool,
    selenium_available: bool,
    log_prefixes: Dict[str, str]
) -> Callable[[FastAPI], Any]:
    """
    创建应用生命周期管理器

    Args:
        worker_pool: Worker 池实例
        worker_pool_available: Worker 池是否可用
        selenium_available: Selenium 是否可用
        log_prefixes: 日志前缀字典

    Returns:
        Callable: 接收 FastAPI app 参数的 lifespan 函数
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        应用生命周期管理器

        Args:
            app: FastAPI 应用实例

        Yields:
            None: 应用启动后 yield，关闭时继续执行
        """
        # ========================================================================
        # 启动阶段
        # ========================================================================
        logger.info("=" * 60)
        logger.info("🚀 Starting Gemini Chat Backend...")
        logger.info("=" * 60)

        # 执行所有启动任务
        startup_result = await run_all_startup_tasks(
            worker_pool=worker_pool,
            worker_pool_available=worker_pool_available,
            log_prefixes=log_prefixes
        )

        worker_mode = startup_result['worker_mode']
        current_pid = startup_result['current_pid']
        supervisor_pid_key = "worker_pool:supervisor:pid"

        # 启动后台清理任务
        cleanup_tasks = start_cleanup_tasks(
            selenium_available=selenium_available,
            log_prefixes=log_prefixes
        )

        # 启动 Worker 池监督任务
        supervisor_task = start_worker_supervisor(
            worker_pool=worker_pool,
            worker_pool_available=worker_pool_available,
            worker_mode=worker_mode,
            current_pid=current_pid,
            log_prefixes=log_prefixes
        )

        logger.info("=" * 60)
        logger.info("✅ Gemini Chat Backend started successfully")
        logger.info("=" * 60)

        # ========================================================================
        # 应用运行阶段
        # ========================================================================
        yield

        # ========================================================================
        # 关闭阶段
        # ========================================================================
        logger.info("=" * 60)
        logger.info("🛑 Shutting down Gemini Chat Backend...")
        logger.info("=" * 60)

        # 停止后台清理任务
        await stop_cleanup_tasks(cleanup_tasks, log_prefixes)

        # 停止 Worker 池监督任务
        await stop_worker_supervisor(supervisor_task, log_prefixes)

        # 执行所有关闭任务
        await run_all_shutdown_tasks(
            worker_pool=worker_pool,
            worker_pool_available=worker_pool_available,
            worker_mode=worker_mode,
            current_pid=current_pid,
            supervisor_pid_key=supervisor_pid_key,
            selenium_available=selenium_available,
            log_prefixes=log_prefixes
        )

        logger.info("=" * 60)
        logger.info("✅ Gemini Chat Backend shut down successfully")
        logger.info("=" * 60)

    return lifespan
