"""
ARQ Worker 定义

此文件定义 ARQ Worker 配置和任务处理函数。
Worker 会在 main.py 启动时自动启动（通过 multiprocessing）。

用法（独立运行）:
    arq backend.app.arq_worker.WorkerSettings
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入环境变量加载（必须在其他导入之前）
try:
    from backend.app.core.env_loader import _ENV_LOADED  # noqa: F401
except ImportError:
    try:
        from app.core.env_loader import _ENV_LOADED  # noqa: F401
    except ImportError:
        from core.env_loader import _ENV_LOADED  # noqa: F401

from backend.app.core.logger import setup_logger, LOG_PREFIXES
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.db_models import UploadTask, MessageAttachment
from backend.app.services.storage.storage_service import StorageService
from backend.app.services.common.redis_queue_service import redis_queue
from datetime import datetime

# ARQ 导入
try:
    from arq.connections import RedisSettings
except ImportError:
    RedisSettings = None
    logger = setup_logger("arq_worker")
    logger.error(f"{LOG_PREFIXES['error']} ARQ is not installed. Please install it: pip install arq")
else:
    logger = setup_logger("arq_worker")


async def upload_file(ctx: dict, task_id: str) -> Dict[str, Any]:
    """
    上传文件任务（ARQ 任务函数）

    Args:
        ctx: ARQ 上下文（包含 redis 连接等）
        task_id: 上传任务 ID

    Returns:
        任务结果字典
    """
    db = SessionLocal()
    worker_name = "ARQ-Worker"
    
    try:
        logger.info(f"[{worker_name}] 📋 开始处理任务: {task_id}")
        
        # 查询任务详情
        task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
        if not task:
            error_msg = f"任务不存在: {task_id}"
            logger.error(f"[{worker_name}] ❌ {error_msg}")
            return {"success": False, "error": error_msg}

        if task.status != 'pending':
            logger.warning(f"[{worker_name}] ⚠️ 任务状态异常: {task_id}, status={task.status}")
            return {"success": False, "error": f"任务状态异常: {task.status}"}

        # 更新状态为 uploading
        logger.info(f"[{worker_name}] 🔄 更新任务状态: pending → uploading")
        task.status = 'uploading'
        db.commit()
        
        # 记录日志到 Redis
        try:
            await redis_queue.append_task_log(
                task_id,
                level="info",
                message="status changed: pending -> uploading (ARQ)",
                source="arq_worker",
                extra={"worker": worker_name},
            )
        except Exception as e:
            logger.warning(f"[{worker_name}] ⚠️ 无法记录日志到 Redis: {e}")

        # 获取文件内容（复用现有逻辑）
        from backend.app.services.common.upload_worker_pool import UploadWorkerPool
        worker_pool = UploadWorkerPool()
        content = await worker_pool._get_file_content(task, worker_name)
        
        # 检查是否复用附件
        if content is None:
            logger.info(f"[{worker_name}] ✅ 附件复用，无需上传")
            
            # 查询已有附件并复用其云URL
            existing = db.query(MessageAttachment).filter_by(
                id=task.source_attachment_id
            ).first()
            
            if existing and existing.url:
                # 更新任务状态
                task.target_url = existing.url
                task.status = 'completed'
                task.completed_at = int(datetime.now().timestamp() * 1000)
                db.commit()
                
                # 更新当前附件的URL
                current_attachment = db.query(MessageAttachment).filter_by(
                    id=task.attachment_id
                ).first()
                if current_attachment:
                    current_attachment.url = existing.url
                    current_attachment.upload_status = 'completed'
                    db.commit()
                
                # 处理成功
                await worker_pool._handle_success(db, task, existing.url, worker_name)
                return {"success": True, "url": existing.url, "reused": True}
            else:
                error_msg = f"无法复用附件: {task.source_attachment_id}"
                logger.error(f"[{worker_name}] ❌ {error_msg}")
                raise Exception(error_msg)
        
        file_size = len(content)
        logger.info(f"[{worker_name}] ✅ 文件读取成功，大小: {file_size / 1024:.2f} KB")

        # 获取存储配置（复用现有逻辑）
        config = worker_pool._get_storage_config(db, task.storage_id, task.session_id)
        if not config:
            error_msg = (
                f"存储配置不可用。"
                f"请检查：1) 是否已配置存储（Settings → Storage），"
                f"2) 存储配置是否已启用，"
                f"3) 是否设置了激活存储。"
            )
            logger.error(f"[{worker_name}] ❌ {error_msg}")
            raise Exception(error_msg)
        
        logger.info(f"[{worker_name}] ✅ 存储配置: {config.name} ({config.provider})")

        # 执行上传
        logger.info(f"[{worker_name}] ☁️ 开始上传到云存储...")
        upload_start = datetime.now()
        
        result = await StorageService.upload_file(
            filename=task.filename,
            content=content,
            content_type='image/png',
            provider=config.provider,
            config=config.config
        )
        
        upload_duration = (datetime.now() - upload_start).total_seconds()

        # 处理上传结果
        if result.get('success'):
            url = result.get('url')
            logger.info(f"[{worker_name}] ✅ 上传成功！耗时: {upload_duration:.2f} 秒")
            
            # 记录日志
            try:
                url_log = f"Base64 Data URL (长度: {len(url)} 字符)" if url and url.startswith('data:') else str(url)
                await redis_queue.append_task_log(
                    task_id,
                    level="info",
                    message=f"upload succeeded (duration_s={upload_duration:.2f}, url={url_log})",
                    source="arq_worker",
                    extra={"worker": worker_name},
                )
            except Exception as e:
                logger.warning(f"[{worker_name}] ⚠️ 无法记录日志到 Redis: {e}")
            
            # 处理成功
            await worker_pool._handle_success(db, task, url, worker_name)
            return {"success": True, "url": url, "duration": upload_duration}
        else:
            error = result.get('error', '上传失败')
            logger.error(f"[{worker_name}] ❌ 上传失败: {error}")
            
            # 记录日志
            try:
                await redis_queue.append_task_log(
                    task_id,
                    level="error",
                    message=f"upload failed: {error}",
                    source="arq_worker",
                    extra={"worker": worker_name},
                )
            except Exception as e:
                logger.warning(f"[{worker_name}] ⚠️ 无法记录日志到 Redis: {e}")
            
            raise Exception(error)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{worker_name}] ❌ 任务处理异常: {error_msg}")
        
        # 更新任务状态为失败
        try:
            task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
            if task:
                task.status = 'failed'
                task.error_message = error_msg
                db.commit()
        except Exception as e2:
            logger.error(f"[{worker_name}] ❌ 无法更新任务状态: {e2}")
        
        # 记录日志
        try:
            await redis_queue.append_task_log(
                task_id,
                level="error",
                message=f"task processing exception: {error_msg}",
                source="arq_worker",
                extra={"worker": worker_name},
            )
        except Exception:
            pass
        
        # ARQ 会自动重试（根据配置）
        raise
    finally:
        db.close()


async def startup(ctx: dict):
    """Worker 启动时执行"""
    logger.info("=" * 60)
    logger.info("🚀 ARQ Worker starting...")
    logger.info("=" * 60)
    
    # 初始化 Redis 连接（如果需要）
    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
            logger.info(f"{LOG_PREFIXES['success']} Redis connection established")
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Redis connection failed: {e}")


async def shutdown(ctx: dict):
    """Worker 关闭时执行"""
    logger.info("=" * 60)
    logger.info("🛑 ARQ Worker shutting down...")
    logger.info("=" * 60)
    
    # 关闭 Redis 连接（如果需要）
    try:
        # 注意：不关闭全局连接池，由主进程管理
        pass
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Error during shutdown: {e}")


# ARQ Worker 配置
if RedisSettings:
    class WorkerSettings:
        """ARQ Worker 配置"""

        # Redis 连接
        redis_settings = RedisSettings(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            database=settings.redis_db,
        )

        # 注册任务函数
        functions = [upload_file]

        # 生命周期钩子
        on_startup = startup
        on_shutdown = shutdown

        # 任务配置
        max_jobs = int(settings.upload_queue_workers)  # 最大并发任务数
        job_timeout = 300  # 任务超时（秒）
        max_tries = int(settings.upload_queue_max_retries)  # 最大重试次数
        retry_delay = float(settings.upload_queue_retry_delay)  # 重试延迟（秒）

        # 健康检查
        health_check_interval = 30

        # 队列名称
        queue_name = 'upload:arq'
else:
    # ARQ 未安装时的占位类
    class WorkerSettings:
        """ARQ Worker 配置（ARQ 未安装）"""
        pass
