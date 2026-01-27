"""
ARQ 任务队列服务

提供 ARQ 任务入队功能，用于替代原有的 Redis 队列。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ARQ 连接池（全局单例）
_arq_redis_pool = None


async def get_arq_pool():
    """获取 ARQ Redis 连接池（单例）"""
    global _arq_redis_pool
    
    if _arq_redis_pool is None:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            from ..core.config import settings
            
            _arq_redis_pool = await create_pool(
                RedisSettings(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password or None,
                    database=settings.redis_db,
                )
            )
            logger.info("[ARQQueue] ARQ Redis connection pool created")
        except ImportError:
            logger.error("[ARQQueue] ARQ is not installed. Please install it: pip install arq")
            raise RuntimeError("ARQ is not installed")
        except Exception as e:
            logger.error(f"[ARQQueue] Failed to create ARQ pool: {e}")
            raise
    
    return _arq_redis_pool


async def enqueue_arq_job(task_id: str, priority: str = 'normal') -> Optional[str]:
    """
    使用 ARQ 入队任务
    
    Args:
        task_id: 任务 ID
        priority: 优先级（high/normal/low），ARQ 不直接支持优先级，但可以用于日志
        
    Returns:
        job_id (ARQ 的任务 ID)，如果失败返回 None
    """
    try:
        redis = await get_arq_pool()
        
        # 入队任务到 ARQ
        job = await redis.enqueue_job(
            'upload_file',  # 任务函数名（在 arq_worker.py 中定义）
            task_id,        # 任务参数
            _job_id=task_id,  # 使用任务 ID 作为 job_id，防止重复
            _queue_name='upload:arq',  # 队列名称（与 WorkerSettings 中的 queue_name 一致）
        )
        
        if job:
            logger.info(f"[ARQQueue] Task enqueued to ARQ: task_id={task_id}, job_id={job.job_id}, priority={priority}")
            return job.job_id
        else:
            logger.error(f"[ARQQueue] Failed to enqueue task to ARQ: task_id={task_id}")
            return None
            
    except Exception as e:
        logger.error(f"[ARQQueue] Error enqueueing task to ARQ: {e}")
        import traceback
        traceback.print_exc()
        return None


async def close_arq_pool():
    """关闭 ARQ Redis 连接池"""
    global _arq_redis_pool
    
    if _arq_redis_pool:
        try:
            await _arq_redis_pool.close()
            logger.info("[ARQQueue] ARQ Redis connection pool closed")
        except Exception as e:
            logger.error(f"[ARQQueue] Error closing ARQ pool: {e}")
        finally:
            _arq_redis_pool = None
