"""
Worker 池监督任务模块

负责监控 Worker 池的健康状态，并在需要时重启。
"""

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def worker_pool_supervisor_task(
    worker_pool: Any,
    current_pid: int,
    supervisor_pid_key: str,
    log_prefixes: Dict[str, str]
):
    """
    Worker 池监督任务

    定期检查 Worker 池的健康状态，如果不健康则重启。
    使用 Redis 锁防止多个实例同时运行。

    Args:
        worker_pool: Worker 池实例
        current_pid: 当前进程 ID
        supervisor_pid_key: Redis 锁的 key
        log_prefixes: 日志前缀字典
    """
    backoff_s = 1.0
    check_interval = 30.0  # 检查间隔（秒）
    reconciler_grace_period = 15.0  # reconciler 启动宽限期（秒）

    # 检查是否已有其他 supervisor 实例在运行（使用 Redis 锁）
    # 注意：Redis 常部署在远程服务器，与应用不同机。不得用本机 PID 存活判断抢锁，
    # 否则多机部署时会误覆盖他机持锁。锁依赖 60s TTL 在 crash/reload 后自动过期。
    try:
        from ..services.common.redis_queue_service import redis_queue

        if redis_queue._redis:
            lock_acquired = await redis_queue._redis.set(
                supervisor_pid_key,
                str(current_pid),
                ex=60,
                nx=True  # 只在 key 不存在时设置
            )

            if not lock_acquired:
                existing_pid = await redis_queue._redis.get(supervisor_pid_key)
                pid_str = (existing_pid.decode() if isinstance(existing_pid, bytes) else existing_pid) if existing_pid else None

                if pid_str and pid_str != str(current_pid):
                    logger.warning(
                        f"{log_prefixes['warning']} Supervisor lock held by another PID ({pid_str}), "
                        f"current PID {current_pid}. Skipping supervisor. "
                        "If the other process exited (e.g. reload/kill), lock expires in 60s."
                    )
                    return  # 退出，不启动 supervisor

                await redis_queue._redis.set(supervisor_pid_key, str(current_pid), ex=60)
            else:
                logger.info(f"[Supervisor] Acquired supervisor lock (PID: {current_pid})")
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to check supervisor lock (Redis may be remote): {e}. Continuing anyway.")

    # 启动宽限期：等待 reconciler 稳定启动后再开始检查
    await asyncio.sleep(20.0)
    logger.info(f"[Supervisor] Grace period ended, starting monitoring. PID: {current_pid}, _pool_running={worker_pool._pool_running}")

    # 锁由主服务 shutdown 时统一释放，确保与主服务生命周期联动
    while True:
        try:
            # 续期锁，确保其他进程知道当前 supervisor 还在运行
            if redis_queue._redis:
                try:
                    await redis_queue._redis.set(supervisor_pid_key, str(current_pid), ex=60)
                except Exception:
                    pass  # 锁续期失败不影响主逻辑

            # 使用 is_reconciler_healthy() 方法进行健康检查
            # 该方法会考虑启动宽限期，避免误判
            is_healthy = worker_pool.is_reconciler_healthy(grace_period=reconciler_grace_period)

            if not is_healthy:
                logger.warning(f"{log_prefixes['warning']} Worker pool reconciler not healthy; restarting pool...")
                try:
                    await worker_pool.stop()
                except Exception as e:
                    logger.error(f"{log_prefixes['error']} Error stopping worker pool: {e}")

                await worker_pool.start()
                logger.info(f"{log_prefixes['success']} Worker pool restarted by supervisor (on-demand mode)")
                backoff_s = 1.0

                # 重启后给额外的宽限期
                await asyncio.sleep(reconciler_grace_period)

            await asyncio.sleep(check_interval)

        except asyncio.CancelledError:
            logger.info(f"{log_prefixes['info']} Worker pool supervisor task cancelled")
            break
        except Exception as e:
            logger.error(f"{log_prefixes['error']} Worker pool supervisor error: {e}")
            await asyncio.sleep(backoff_s)
            backoff_s = min(backoff_s * 2.0, 60.0)


def start_worker_supervisor(
    worker_pool: Any,
    worker_pool_available: bool,
    worker_mode: str,
    current_pid: int,
    log_prefixes: Dict[str, str]
) -> Optional[asyncio.Task]:
    """
    启动 Worker 池监督任务

    Args:
        worker_pool: Worker 池实例
        worker_pool_available: Worker 池是否可用
        worker_mode: Worker 模式
        current_pid: 当前进程 ID
        log_prefixes: 日志前缀字典

    Returns:
        Optional[asyncio.Task]: 监督任务对象，如果未启动则返回 None
    """
    if not (worker_pool_available and worker_mode == "embedded"):
        return None

    supervisor_pid_key = "worker_pool:supervisor:pid"
    supervisor_task = asyncio.create_task(
        worker_pool_supervisor_task(
            worker_pool=worker_pool,
            current_pid=current_pid,
            supervisor_pid_key=supervisor_pid_key,
            log_prefixes=log_prefixes
        )
    )

    logger.info(f"{log_prefixes['success']} Worker pool supervisor task started")
    return supervisor_task


async def stop_worker_supervisor(
    supervisor_task: Optional[asyncio.Task],
    log_prefixes: Dict[str, str]
):
    """
    停止 Worker 池监督任务

    Args:
        supervisor_task: 监督任务对象
        log_prefixes: 日志前缀字典
    """
    if supervisor_task and not supervisor_task.done():
        supervisor_task.cancel()
        await asyncio.gather(supervisor_task, return_exceptions=True)
        logger.info(f"{log_prefixes['info']} Worker pool supervisor stopped")
