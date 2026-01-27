"""
上传 Worker 池管理器

特性：
- 使用 Redis BRPOP 阻塞等待（无轮询，低 CPU）
- 自动重试（指数退避）
- 分布式锁（防止重复处理）
- 崩溃恢复（重启后自动恢复中断任务）
- 详细日志输出（每个步骤都有日志）
"""

import asyncio
import os
import sys
from typing import Optional, List
from datetime import datetime
import logging
import httpx
import base64

from ...core.database import SessionLocal
from ...core.config import settings
from ...models.db_models import UploadTask, StorageConfig, ActiveStorage, ChatSession
from ..storage.storage_service import StorageService
from ...core.encryption import decrypt_config
from .redis_queue_service import redis_queue

logger = logging.getLogger(__name__)


def log_print(message: str, level: str = "INFO"):
    """
    统一使用 logger 输出，确保立即刷新
    移除 sys.stderr.write() 避免被 Uvicorn 重定向
    """
    # 直接使用 logger（logger 已配置 FlushingStreamHandler）
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)


class UploadWorkerPool:
    """
    上传 Worker 池（按需调用模式）

    使用 Redis 队列 + 数据库持久化架构：
    - Redis BRPOP 阻塞等待任务（无轮询，0 CPU）
    - 数据库存储任务详情（持久化）
    - 分布式锁防止重复处理
    - 自动重试（指数退避）
    - 死信队列处理最终失败

    按需调用特性：
    - 没有任务时不运行任何 Worker
    - 任务入队时懒启动 Worker
    - 队列为空且无 pending 任务时 Worker 自动退出
    """

    def __init__(self):
        self.max_workers = settings.upload_queue_workers  # 最大并发数（目前单 Worker 模式）
        self.max_retries = settings.upload_queue_max_retries
        self.base_retry_delay = settings.upload_queue_retry_delay
        self.idle_timeout = 10  # 队列空闲超时（秒），超时后 Worker 退出

        self._running = False
        self._pool_running = False
        self._worker_task: Optional[asyncio.Task] = None  # 单 Worker 任务
        self._lock = asyncio.Lock()  # 保护 Worker 启动逻辑
        self._reconciler: asyncio.Task | None = None
        self._reconciler_started_at: Optional[float] = None  # reconciler 启动时间戳
        # 周期性补偿入队：避免"必须重启才触发恢复"
        self._reconcile_interval_s: float = float(os.getenv("UPLOAD_QUEUE_RECONCILE_INTERVAL", "15"))
        self._reconcile_limit: int = int(os.getenv("UPLOAD_QUEUE_RECONCILE_LIMIT", "500"))

    def is_reconciler_healthy(self, grace_period: float = 10.0) -> bool:
        """
        检查 reconciler 是否健康运行

        Args:
            grace_period: 启动宽限期（秒），在此期间视为健康

        Returns:
            True 如果 reconciler 健康运行
        """
        import time

        # 如果 pool 没有运行，不健康
        if not self._pool_running:
            return False

        # 如果 reconciler 为 None，不健康
        if self._reconciler is None:
            return False

        # 如果在宽限期内，视为健康（给新启动的 reconciler 时间）
        if self._reconciler_started_at is not None:
            elapsed = time.time() - self._reconciler_started_at
            if elapsed < grace_period:
                return True

        # 检查 Task 是否已完成
        if self._reconciler.done():
            return False

        return True

    async def ensure_worker_running(self):
        """
        确保有 Worker 在运行（懒启动）

        由 _submit_upload_task() 调用，入队后触发
        如果 Worker 没有运行或已完成，启动新的 Worker
        """
        async with self._lock:
            # 如果 Worker 没有运行，或者已完成，启动新的
            if self._worker_task is None or self._worker_task.done():
                self._running = True
                self._worker_task = asyncio.create_task(self._worker_loop())
                logger.warning("[WorkerPool] ✅ Worker 已启动（按需）")

    async def _has_pending_tasks(self) -> bool:
        """检查数据库中是否还有 pending/uploading 任务"""
        db = SessionLocal()
        try:
            count = db.query(UploadTask).filter(
                UploadTask.status.in_(['pending', 'uploading'])
            ).count()
            return count > 0
        finally:
            db.close()

    async def start(self):
        """
        启动 Worker 池（按需调用模式）

        只进行：
        1. 连接 Redis
        2. 恢复中断任务
        3. 如果有 pending 任务，启动 Worker

        不再预创建 Worker，Worker 会在任务入队时按需启动
        """
        if self._running:
            logger.warning("[WorkerPool] Worker pool already running")
            return

        # 使用 WARNING 级别确保日志可见
        logger.warning("=" * 80)
        logger.warning("[WorkerPool] STARTING UPLOAD WORKER POOL (ON-DEMAND MODE)...")
        logger.warning("=" * 80)

        # 连接 Redis
        logger.warning(f"[WorkerPool] Connecting to Redis: {settings.redis_host}:{settings.redis_port}")
        try:
            await redis_queue.connect()
            logger.warning("[WorkerPool] Redis connected successfully")
        except Exception as e:
            logger.error(f"[WorkerPool] Redis connection failed: {e}")
            raise

        # 恢复中断任务
        logger.warning("[WorkerPool] Recovering interrupted tasks...")
        recovered_count = await self._recover_tasks()
        logger.warning(f"[WorkerPool] Recovered {recovered_count} tasks")

        # 如果有 pending 任务，启动 Worker
        if await self._has_pending_tasks():
            logger.warning("[WorkerPool] Found pending tasks, starting worker...")
            await self.ensure_worker_running()
        else:
            logger.warning("[WorkerPool] No pending tasks, worker will start on-demand")

        logger.warning("=" * 80)
        logger.warning("[WorkerPool] WORKER POOL READY (ON-DEMAND MODE)")
        logger.warning("=" * 80)

        # ✅ 设置 _pool_running 标志，确保 reconciler 可以运行
        self._pool_running = True

        # 周期性补偿：把 DB 中 pending 且不在 Redis 队列的任务补回队列
        # 注意：reconciler 仍然需要运行，但它只补偿入队，不启动 Worker
        # Worker 会在 _submit_upload_task() 中按需启动
        if self._reconcile_interval_s > 0:
            import time
            self._reconciler = asyncio.create_task(self._reconcile_loop())
            self._reconciler_started_at = time.time()  # 记录启动时间
            logger.warning(
                f"[WorkerPool] Reconciler started (interval={self._reconcile_interval_s}s, limit={self._reconcile_limit})"
            )

    async def stop(self):
        """停止 Worker 池"""
        logger.warning("[WorkerPool] Stopping worker pool...")
        self._running = False
        self._pool_running = False
        self._reconciler_started_at = None  # 清除启动时间

        if self._reconciler:
            self._reconciler.cancel()
            await asyncio.gather(self._reconciler, return_exceptions=True)
            self._reconciler = None

        # 停止单 Worker（按需调用模式）
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        # TASK-002: 不再断开 Redis 连接，因为使用全局连接池
        # 连接由应用级别的全局连接池管理，在应用关闭时统一关闭
        # await redis_queue.disconnect()  # 已移除

        logger.warning("[WorkerPool] Worker pool stopped (Redis connection maintained by global pool)")

    async def _reconcile_loop(self):
        """周期性补偿入队（只处理 pending，不动 uploading）。"""
        while self._pool_running:
            try:
                await asyncio.sleep(self._reconcile_interval_s)
                if not self._pool_running:
                    break

                # Redis 不可用时跳过（等待 supervisor/下一轮）
                if redis_queue._redis is None:
                    continue

                requeued, failed = await self._reconcile_pending_tasks(limit=self._reconcile_limit)
                if requeued or failed:
                    logger.warning(
                        f"[WorkerPool] Reconcile tick: requeued_pending={requeued}, failed_pending={failed}"
                    )
                    # ✅ 如果有任务被重新入队，确保 Worker 正在运行
                    if requeued > 0:
                        await self.ensure_worker_running()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WorkerPool] Reconcile loop error: {e}")
                await asyncio.sleep(1)

    async def _reconcile_pending_tasks(self, limit: int = 500) -> tuple[int, int]:
        """
        补偿：把 DB 中 pending 且不在 Redis 队列里的任务重新入队。

        注意：不处理 uploading（避免把正在执行的任务错误回滚）。
        """
        db = SessionLocal()
        requeued_pending = 0
        failed_pending = 0

        try:
            pending_tasks = (
                db.query(UploadTask)
                .filter(UploadTask.status == 'pending')
                .order_by(UploadTask.created_at.desc())
                .limit(int(limit))
                .all()
            )

            for task in pending_tasks:
                task.priority = task.priority or 'normal'
                task.retry_count = task.retry_count or 0

                # 无有效来源的任务无法处理，直接标记失败（避免永远 pending）
                # ✅ 修复：检查所有source类型（包括source_ai_url和source_attachment_id）
                if not any([task.source_file_path, task.source_url, task.source_ai_url, task.source_attachment_id]):
                    task.status = 'failed'
                    task.error_message = "任务缺少 source（source_file_path/source_url/source_ai_url/source_attachment_id），无法处理"
                    task.completed_at = int(datetime.now().timestamp() * 1000)
                    failed_pending += 1
                    try:
                        await redis_queue.append_task_log(
                            task.id,
                            level="error",
                            message="task has no source (source_file_path/source_url/source_ai_url/source_attachment_id); marked as failed during reconcile",
                            source="reconcile",
                        )
                    except Exception:
                        pass
                    continue

                # 已在队列中则跳过
                try:
                    queued = await redis_queue.is_task_queued(task.id)
                except Exception:
                    queued = False

                if queued:
                    continue

                await redis_queue.enqueue(task.id, task.priority)
                requeued_pending += 1
                try:
                    await redis_queue.append_task_log(
                        task.id,
                        level="info",
                        message="reconciled pending task not present in Redis queue; re-enqueued",
                        source="reconcile",
                    )
                except Exception:
                    pass

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[WorkerPool] reconcile_pending_tasks failed: {e}")
        finally:
            db.close()

        return requeued_pending, failed_pending

    async def _recover_tasks(self) -> int:
        """恢复中断的任务，并补偿 pending 但未入队的任务"""
        db = SessionLocal()
        recovered_uploading = 0
        requeued_pending = 0
        failed_pending = 0

        try:
            # 1) 将 uploading 状态重置为 pending 并重新入队
            uploading_tasks = db.query(UploadTask).filter(
                UploadTask.status == 'uploading'
            ).all()

            for task in uploading_tasks:
                task.status = 'pending'
                task.priority = task.priority or 'normal'
                task.retry_count = task.retry_count or 0

                await redis_queue.enqueue(task.id, task.priority)
                await redis_queue.append_task_log(
                    task.id,
                    level="warn",
                    message="recovered from 'uploading' to 'pending' and re-enqueued",
                    source="recover",
                )
                log_print(f"[WorkerPool] 🔄 恢复任务(uploading): {task.id} ({task.filename})")
                recovered_uploading += 1

            # 2) 补偿：pending 但不在 Redis 队列里的任务重新入队（避免长期卡住）
            pending_tasks = db.query(UploadTask).filter(
                UploadTask.status == 'pending'
            ).order_by(
                UploadTask.created_at.desc()
            ).limit(1000).all()

            for task in pending_tasks:
                task.priority = task.priority or 'normal'
                task.retry_count = task.retry_count or 0

                # 无有效来源的任务无法处理，直接标记失败（避免永远 pending）
                if not any([task.source_file_path, task.source_url, task.source_ai_url, task.source_attachment_id]):
                    task.status = 'failed'
                    task.error_message = "任务缺少 source（source_file_path/source_url/source_ai_url/source_attachment_id），无法恢复入队"
                    task.completed_at = int(datetime.now().timestamp() * 1000)
                    await redis_queue.append_task_log(
                        task.id,
                        level="error",
                        message="task has no source_file_path/source_url; marked as failed during startup reconcile",
                        source="recover",
                    )
                    log_print(f"[WorkerPool] ❌ 标记失败(pending 无来源): {task.id} ({task.filename})", "ERROR")
                    failed_pending += 1
                    continue

                # 已在队列中则跳过，避免重复入队
                if await redis_queue.is_task_queued(task.id):
                    continue

                await redis_queue.enqueue(task.id, task.priority)
                await redis_queue.append_task_log(
                    task.id,
                    level="info",
                    message="reconciled pending task not present in Redis queue; re-enqueued",
                    source="recover",
                )
                log_print(f"[WorkerPool] 🔄 补偿入队(pending): {task.id} ({task.filename})")
                requeued_pending += 1

            db.commit()
        except Exception as e:
            log_print(f"[WorkerPool] ❌ 恢复/补偿任务失败: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()

        if recovered_uploading or requeued_pending or failed_pending:
            log_print(
                "[WorkerPool] 🔍 恢复摘要: "
                f"uploading->pending={recovered_uploading}, "
                f"pending补偿入队={requeued_pending}, "
                f"pending标记失败={failed_pending}"
            )

        return recovered_uploading + requeued_pending + failed_pending

    async def _worker_loop(self):
        """
        Worker 主循环（按需调用模式）

        特点：
        - 处理完所有任务后自动退出
        - 空闲超时后检查数据库，无 pending 任务则退出
        """
        worker_name = "Worker-0"
        logger.warning(f"[{worker_name}] Started (on-demand mode), processing tasks...")

        idle_count = 0
        max_idle_count = self.idle_timeout // 5  # 5秒一次检查，idle_timeout=10秒 → 2次

        while self._running:
            try:
                # 从 Redis 队列获取任务（阻塞等待，最多5秒）
                task_id = await redis_queue.dequeue(timeout=5)

                if task_id is None:
                    # 队列为空，增加空闲计数
                    idle_count += 1

                    # 检查是否还有 pending 任务（数据库中）
                    if idle_count >= max_idle_count:
                        if not await self._has_pending_tasks():
                            logger.warning(f"[{worker_name}] 队列为空且无 pending 任务，Worker 自动退出")
                            break
                        else:
                            # 有 pending 任务但不在队列中，可能需要 reconcile，继续等待
                            idle_count = 0
                    continue

                # 有任务，重置空闲计数
                idle_count = 0

                # ========== 收到任务 ==========
                logger.warning(f"[{worker_name}] ✅ Got task: {task_id}")
                await redis_queue.append_task_log(
                    task_id,
                    level="info",
                    message=f"{worker_name} received task",
                    source="worker",
                )

                # 获取分布式锁
                log_print(f"[{worker_name}] 🔒 获取分布式锁: {task_id}")
                if not await redis_queue.acquire_lock(task_id, worker_name):
                    log_print(f"[{worker_name}] ⚠️ 获取锁失败（任务可能被其他 Worker 处理）: {task_id}", "WARNING")
                    continue
                log_print(f"[{worker_name}] ✅ 获取锁成功: {task_id}")
                await redis_queue.append_task_log(
                    task_id,
                    level="info",
                    message=f"{worker_name} acquired lock",
                    source="worker",
                )

                # ✅ 获取锁后立即将任务置为 uploading，避免 Reconciler 在限流等待期间
                #    将「pending 且不在队列」的同一任务再次入队，导致重复处理、重复上传
                if not self._mark_task_uploading(task_id):
                    log_print(f"[{worker_name}] ⚠️ 任务不存在或非 pending，跳过: {task_id}", "WARNING")
                    await redis_queue.release_lock(task_id, worker_name)
                    continue
                log_print(f"[{worker_name}] 🔄 任务已置为 uploading（防 Reconciler 重复入队）")
                await redis_queue.append_task_log(
                    task_id,
                    level="info",
                    message="status changed: pending -> uploading (before rate limit)",
                    source="worker",
                    extra={"worker": worker_name},
                )

                try:
                    # 限流检查
                    log_print(f"[{worker_name}] ⏳ 等待限流令牌: {task_id}")
                    if not await redis_queue.wait_for_rate_token(max_wait=30):
                        log_print(f"[{worker_name}] ⚠️ 限流等待超时，回滚为 pending 并重新入队: {task_id}", "WARNING")
                        self._revert_task_to_pending(task_id)
                        await redis_queue.enqueue(task_id, 'normal')
                        continue
                    log_print(f"[{worker_name}] ✅ 获取限流令牌: {task_id}")

                    # 处理任务
                    log_print(f"[{worker_name}] 🔄 开始处理任务: {task_id}")
                    await self._process_task(task_id, worker_name)
                    log_print(f"[{worker_name}] ✅ 任务处理完成: {task_id}")

                finally:
                    # 释放锁
                    await redis_queue.release_lock(task_id, worker_name)
                    log_print(f"[{worker_name}] 🔓 释放分布式锁: {task_id}")

            except asyncio.CancelledError:
                log_print(f"[{worker_name}] ⏹️ 收到停止信号")
                break
            except Exception as e:
                log_print(f"[{worker_name}] ❌ 异常: {e}", "ERROR")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1)

        self._running = False
        log_print(f"[{worker_name}] 🛑 已退出（按需调用模式）")

    def _mark_task_uploading(self, task_id: str) -> bool:
        """
        将任务状态从 pending 置为 uploading（获取锁后立即调用）。
        用于避免 Reconciler 在限流等待期间把同一任务重新入队导致重复处理。
        """
        db = SessionLocal()
        try:
            n = db.query(UploadTask).filter(
                UploadTask.id == task_id,
                UploadTask.status == 'pending',
            ).update({UploadTask.status: 'uploading'}, synchronize_session=False)
            db.commit()
            return n > 0
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    def _revert_task_to_pending(self, task_id: str) -> bool:
        """限流等待超时回滚：uploading -> pending，便于重新入队后再次被处理。"""
        db = SessionLocal()
        try:
            n = db.query(UploadTask).filter(
                UploadTask.id == task_id,
                UploadTask.status == 'uploading',
            ).update({UploadTask.status: 'pending'}, synchronize_session=False)
            db.commit()
            return n > 0
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    async def _process_task(self, task_id: str, worker_name: str):
        """处理单个任务"""
        db = SessionLocal()
        try:
            # ========== 步骤 1: 查询任务详情 ==========
            log_print(f"[{worker_name}] 📋 查询任务详情: {task_id}")
            task = db.query(UploadTask).filter(UploadTask.id == task_id).first()

            if not task:
                log_print(f"[{worker_name}] ❌ 任务不存在: {task_id}", "ERROR")
                return

            if task.status not in ('pending', 'uploading'):
                log_print(f"[{worker_name}] ⚠️ 任务状态异常: {task_id}, status={task.status}", "WARNING")
                return

            log_print(f"[{worker_name}] 📋 任务详情:")
            log_print(f"    - 任务 ID: {task.id}")
            log_print(f"    - 文件名: {task.filename}")
            log_print(f"    - 优先级: {task.priority}")
            log_print(f"    - 重试次数: {task.retry_count or 0}")
            log_print(f"    - 文件路径: {task.source_file_path or 'None'}")
            log_print(f"    - 源 URL: {task.source_url or 'None'}")
            # ✅ 对于 BASE64 URL，只输出类型和长度，不输出完整内容
            if task.source_ai_url:
                if task.source_ai_url.startswith('data:'):
                    log_print(f"    - AI URL: Base64 Data URL (长度: {len(task.source_ai_url)} 字符)")
                else:
                    log_print(f"    - AI URL: {task.source_ai_url[:80] + '...' if len(task.source_ai_url) > 80 else task.source_ai_url}")
            else:
                log_print(f"    - AI URL: None")
            log_print(f"    - 复用附件ID: {task.source_attachment_id or 'None'}")

            # 状态已在主循环中置为 uploading（获取锁后、限流前），此处不再更新

            # ========== 步骤 2: 读取文件内容 ==========
            log_print(f"[{worker_name}] 📂 读取文件内容...")
            content = await self._get_file_content(task, worker_name)
            
            # ✅ 新增: 如果返回None → 表示复用附件，无需上传
            # ✅ Bug修复: 在检查 None 之后再记录文件大小，避免 TypeError
            if content is None:
                log_print(f"[{worker_name}] ✅ 附件复用，无需上传")
                
                # 查询已有附件并复用其云URL
                from ...models.db_models import MessageAttachment
                existing = db.query(MessageAttachment).filter_by(
                    id=task.source_attachment_id
                ).first()
                
                if existing and existing.url:
                    # 更新任务状态
                    task.target_url = existing.url
                    task.status = 'completed'
                    task.completed_at = int(datetime.now().timestamp() * 1000)
                    db.commit()
                    
                    # 更新当前附件的URL（指向同一云URL）
                    current_attachment = db.query(MessageAttachment).filter_by(
                        id=task.attachment_id
                    ).first()
                    if current_attachment:
                        current_attachment.url = existing.url
                        current_attachment.upload_status = 'completed'
                        db.commit()
                        log_print(f"[{worker_name}] ✅ 附件URL已更新: {task.attachment_id}")
                    
                    await self._handle_success(db, task, existing.url, worker_name)
                else:
                    raise Exception(f"Failed to reuse attachment: {task.source_attachment_id}")
                
                return  # 复用完成，无需上传
            
            # ✅ Bug修复: 只有在 content 不是 None 时才记录文件大小
            file_size = len(content)
            log_print(f"[{worker_name}] ✅ 文件读取成功，大小: {file_size / 1024:.2f} KB")

            # ========== 步骤 3: 获取存储配置 ==========
            log_print(f"[{worker_name}] ⚙️ 获取存储配置...")
            log_print(f"    - storage_id: {task.storage_id or 'None'}")
            log_print(f"    - session_id: {task.session_id or 'None'}")
            config = self._get_storage_config(db, task.storage_id, task.session_id)
            if not config:
                error_msg = (
                    f"存储配置不可用。"
                    f"请检查：1) 是否已配置存储（Settings → Storage），"
                    f"2) 存储配置是否已启用，"
                    f"3) 是否设置了激活存储。"
                    f"任务信息: storage_id={task.storage_id or 'None'}, "
                    f"session_id={task.session_id or 'None'}"
                )
                log_print(f"[{worker_name}] ❌ {error_msg}", level="ERROR")
                raise Exception(error_msg)
            log_print(f"[{worker_name}] ✅ 存储配置: {config.name} ({config.provider})")

            # ========== 步骤 4: 执行上传 ==========
            log_print(f"[{worker_name}] ☁️ 开始上传到云存储...")
            log_print(f"    - 提供商: {config.provider}")
            log_print(f"    - 文件名: {task.filename}")
            log_print(f"    - 文件大小: {file_size / 1024:.2f} KB")
            await redis_queue.append_task_log(
                task_id,
                level="info",
                message=f"upload started (provider={config.provider}, filename={task.filename}, size_kb={file_size / 1024:.2f})",
                source="worker",
                extra={"worker": worker_name},
            )
            
            upload_start = datetime.now()
            result = await StorageService.upload_file(
                filename=task.filename,
                content=content,
                content_type='image/png',
                provider=config.provider,
                config=config.config
            )
            upload_duration = (datetime.now() - upload_start).total_seconds()
            # ✅ Bug修复: result 是字典，需要转换为字符串再截断，或只显示关键信息
            result_str = str(result)
            result_preview = result_str

            # ========== 步骤 5: 处理上传结果 ==========
            if result.get('success'):
                url = result.get('url')
                log_print(f"[{worker_name}] ✅ 上传成功！")
                log_print(f"    - 耗时: {upload_duration:.2f} 秒")
                # 对于BASE64 URL，只输出类型和长度，不输出内容
                if url and url.startswith('data:'):
                    log_print(f"    - URL: Base64 Data URL (长度: {len(url)} 字符)")
                else:
                    log_print(f"    - URL: {url}")
                # 对于BASE64 URL，在日志中只记录类型，不记录完整内容
                url_log = f"Base64 Data URL (长度: {len(url)} 字符)" if url and url.startswith('data:') else str(url)
                await redis_queue.append_task_log(
                    task_id,
                    level="info",
                    message=f"upload succeeded (duration_s={upload_duration:.2f}, url={url_log})",
                    source="worker",
                    extra={"worker": worker_name},
                )
                await self._handle_success(db, task, url, worker_name)
            else:
                error = result.get('error', '上传失败')
                log_print(f"[{worker_name}] ❌ 上传失败: {error}", "ERROR")
                await redis_queue.append_task_log(
                    task_id,
                    level="error",
                    message=f"upload failed: {error}",
                    source="worker",
                    extra={"worker": worker_name},
                )
                raise Exception(error)

        except Exception as e:
            log_print(f"[{worker_name}] ❌ 任务处理异常: {e}", "ERROR")
            await redis_queue.append_task_log(
                task_id,
                level="error",
                message=f"task processing exception: {e}",
                source="worker",
                extra={"worker": worker_name},
            )
            await self._handle_failure(db, task_id, str(e), worker_name)
        finally:
            db.close()

    def _get_project_root(self):
        """
        获取项目根目录（使用统一的路径工具）
        
        用于 Docker 部署：所有路径都基于项目根目录的相对路径
        """
        from ...core.path_utils import get_project_root
        return get_project_root()

    async def _get_file_content(self, task: UploadTask, worker_name: str) -> Optional[bytes]:
        """
        Get file content from local file or URL
        
        支持4种source类型:
        1. source_file_path: 本地文件路径
        2. source_url: HTTP URL
        3. source_ai_url: AI返回URL（Base64或HTTP）【新增】
        4. source_attachment_id: 复用已有附件ID【新增】
        
        返回None表示无需上传（复用已有附件）
        
        所有路径都使用相对路径（相对于项目根目录），兼容 Docker 部署
        路径格式：backend/app/temp/...
        """
        from ...core.path_utils import resolve_relative_path, ensure_relative_path
        from ...models.db_models import MessageAttachment
        
        # 类型1: source_file_path（已有）
        if task.source_file_path:
            source_path = task.source_file_path
            
            # 使用统一的路径解析工具
            file_path = resolve_relative_path(source_path)

            if os.path.exists(file_path):
                # 显示相对路径（用于日志）
                rel_path = ensure_relative_path(source_path)
                log_print(f"[{worker_name}] 📂 Read from local file: {rel_path}")
                with open(file_path, 'rb') as f:
                    return f.read()
            else:
                rel_path = ensure_relative_path(source_path)
                log_print(f"[{worker_name}] ❌ File not found: {rel_path} (abs: {file_path})", "ERROR")
                raise Exception(f"File not found for source_file_path={source_path}")
        
        # 类型2: source_url（已有）
        elif task.source_url:
            log_print(f"[{worker_name}] 🌐 Download from URL: {task.source_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(task.source_url)
                response.raise_for_status()
                return response.content
        
        # 【新增】类型3: source_ai_url
        elif task.source_ai_url:
            ai_url = task.source_ai_url
            # ✅ 对于 BASE64 URL，只输出类型和长度，不输出完整内容
            if ai_url.startswith('data:'):
                log_print(f"[{worker_name}] 🤖 Process AI URL: Base64 Data URL (长度: {len(ai_url)} 字符)")
            else:
                log_print(f"[{worker_name}] 🤖 Process AI URL: {ai_url[:80] + '...' if len(ai_url) > 80 else ai_url}")
            
            # 判断是Base64 Data URL还是HTTP URL
            if ai_url.startswith('data:'):
                # Base64 Data URL
                log_print(f"[{worker_name}] 📦 Decoding Base64 Data URL...")
                mime_type, base64_str = self._parse_data_url(ai_url)
                image_bytes = base64.b64decode(base64_str)
                log_print(f"[{worker_name}] ✅ Base64 decoded, size: {len(image_bytes) / 1024:.2f} KB")
                return image_bytes
            else:
                # HTTP URL（Tongyi临时URL）
                log_print(f"[{worker_name}] 🌐 Download from AI HTTP URL...")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(ai_url)
                    response.raise_for_status()
                    return response.content
        
        # 【新增】类型4: source_attachment_id
        elif task.source_attachment_id:
            log_print(f"[{worker_name}] 🔄 Reusing attachment: {task.source_attachment_id}")
            
            # 需要数据库会话，从外部传入
            from ...models.db_models import MessageAttachment
            # 注意: 这里需要从外部传入db，但为了兼容性，我们创建一个新的会话
            reuse_db = SessionLocal()
            try:
                # 查询已有附件
                existing = reuse_db.query(MessageAttachment).filter_by(
                    id=task.source_attachment_id
                ).first()
            
                if not existing:
                    raise Exception(f"Attachment {task.source_attachment_id} not found")
                
                # 如果已有云URL且状态完成 → 无需重新上传
                if existing.url and existing.upload_status == 'completed':
                    # 直接复用云URL
                    log_print(f"[{worker_name}] ✅ Attachment already uploaded, reusing cloud URL: {existing.url}")
                    # 注意: task 和 current_attachment 需要使用传入的 db，这里我们返回 None
                    # 实际的状态更新在 _process_task 中处理
                    return None  # 特殊标记：无需上传
                else:
                    raise Exception(f"Attachment {task.source_attachment_id} not uploaded yet")
            finally:
                reuse_db.close()
        
        else:
            raise Exception("No file source available (all source fields are empty)")
    
    def _parse_data_url(self, data_url: str) -> tuple[str, str]:
        """
        解析Data URL
        
        返回: (mime_type, base64_str)
        """
        if not data_url.startswith('data:'):
            raise ValueError("Invalid data URL")
        
        # 格式: data:image/png;base64,iVBORw0KGgo...
        parts = data_url.split(',', 1)
        if len(parts) != 2:
            raise ValueError("Invalid data URL format")
        
        header = parts[0]  # data:image/png;base64
        base64_str = parts[1]
        
        # 提取MIME类型
        mime_match = header.split(':')[1].split(';')[0]
        mime_type = mime_match if mime_match else 'image/png'
        
        return mime_type, base64_str

    def _get_storage_config(self, db, storage_id: Optional[str], session_id: Optional[str] = None):
        """获取存储配置（自动解密敏感字段）"""
        if storage_id:
            config = db.query(StorageConfig).filter(StorageConfig.id == storage_id).first()
            if not config:
                logger.warning(f"[UploadWorkerPool] 指定的存储配置不存在: {storage_id}")
                return None
            if not config.enabled:
                logger.warning(f"[UploadWorkerPool] 指定的存储配置已禁用: {storage_id}")
                return None
        else:
            user_id = None
            if session_id:
                session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if session:
                    user_id = session.user_id
                    logger.debug(f"[UploadWorkerPool] 从会话获取 user_id: {user_id or 'None'}")
                else:
                    logger.warning(f"[UploadWorkerPool] 会话不存在: {session_id or 'None'}")

            if user_id:
                active = db.query(ActiveStorage).filter(ActiveStorage.user_id == user_id).first()
                if active:
                    logger.debug(f"[UploadWorkerPool] 找到用户激活存储: user_id={user_id}, storage_id={active.storage_id or 'None'}")
                else:
                    logger.warning(f"[UploadWorkerPool] 用户未设置激活存储: user_id={user_id}")
            else:
                logger.debug(f"[UploadWorkerPool] 尝试使用默认存储配置")
                active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()

            if active and active.storage_id:
                config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
                if not config:
                    logger.warning(f"[UploadWorkerPool] 激活存储配置不存在: storage_id={active.storage_id}")
                    return None
            else:
                logger.warning(f"[UploadWorkerPool] 未找到激活存储配置 (user_id={user_id or 'None'}, session_id={session_id or 'None'})")
                return None

        if not config.enabled:
            logger.warning(f"[UploadWorkerPool] 存储配置已禁用: {config.id if config else 'None'}")
            return None
        
        # ⚠️ 重要：解密配置中的敏感字段（accessKeyId, accessKeySecret 等）
        # 因为前端保存时使用 encrypt_config() 加密，后端使用时必须解密
        # ✅ Bug修复：不能直接修改 SQLAlchemy 模型对象，否则 db.commit() 会将明文写回数据库
        # 解决方案：从 session 中分离对象（expunge），然后修改副本
        try:
            decrypted_config_dict = decrypt_config(config.config)
            # 从 session 中分离对象，避免修改被持久化
            db.expunge(config)
            # 现在可以安全地修改 config.config，因为对象已从 session 中分离
            config.config = decrypted_config_dict
            logger.debug(f"[UploadWorkerPool] 已解密存储配置: {config.id} (provider={config.provider})")
        except Exception as e:
            logger.error(f"[UploadWorkerPool] 解密存储配置失败: {e}")
            # 如果解密失败，可能是未加密的历史数据，继续使用原配置
            # 但记录警告日志
            logger.warning(f"[UploadWorkerPool] 使用未解密的配置（可能是历史数据）: {config.id}")
            # 即使解密失败，也要 expunge 以避免意外修改
            db.expunge(config)
        
        return config

    async def _handle_success(self, db, task: UploadTask, url: str, worker_name: str):
        """处理成功"""
        now = int(datetime.now().timestamp() * 1000)

        # 更新任务状态
        log_print(f"[{worker_name}] 💾 更新任务状态: uploading → completed")
        task.status = 'completed'
        task.target_url = url
        task.completed_at = now
        db.commit()
        await self._log_task_db_state(task.id, stage="after_success_commit", worker_name=worker_name)
        await redis_queue.append_task_log(
            task.id,
            level="info",
            message="status changed: uploading -> completed",
            source="worker",
            extra={"worker": worker_name},
        )

        # Delete temp file (使用相对路径，兼容 Docker 部署)
        # 路径格式：backend/app/temp/...
        if task.source_file_path:
            from ...core.path_utils import resolve_relative_path, ensure_relative_path
            
            source_path = task.source_file_path
            file_path = resolve_relative_path(source_path)
            rel_path = ensure_relative_path(source_path)

            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    log_print(f"[{worker_name}] 🗑️ Temp file deleted: {rel_path}")
                except Exception as e:
                    log_print(f"[{worker_name}] ⚠️ Failed to delete temp file ({rel_path}): {e}", "WARNING")
            else:
                log_print(f"[{worker_name}] ⚠️ Temp file not found: {rel_path}", "WARNING")

        # 更新会话附件
        if task.session_id and task.message_id and task.attachment_id:
            log_print(f"[{worker_name}] 🔄 更新会话附件 URL...")
            await self._update_session_attachment(
                db, task.session_id, task.message_id, task.attachment_id, url, worker_name
            )

        # 更新 Redis 统计
        await redis_queue.update_stats("total_completed")

        log_print(f"[{worker_name}] ✅✅✅ 任务完成: {task.id}")
        log_print(f"    - 文件名: {task.filename}")
        log_print(f"    - 云存储 URL: {url}")

    async def _handle_failure(self, db, task_id: str, error: str, worker_name: str):
        """处理失败"""
        task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
        if not task:
            return

        # 递增重试次数
        retry_count = (task.retry_count or 0) + 1
        task.retry_count = retry_count
        task.error_message = f"{error} (重试 {retry_count}/{self.max_retries})"

        log_print(f"[{worker_name}] ⚠️ 任务失败: {task_id}", "WARNING")
        log_print(f"    - 错误: {error}")
        log_print(f"    - 重试次数: {retry_count}/{self.max_retries}")
        await redis_queue.append_task_log(
            task_id,
            level="warn",
            message=f"task failed: {error} (retry {retry_count}/{self.max_retries})",
            source="worker",
            extra={"worker": worker_name},
        )

        if retry_count < self.max_retries:
            # 指数退避
            delay = self.base_retry_delay * (2 ** (retry_count - 1))
            log_print(f"[{worker_name}] 🔄 将在 {delay} 秒后重试...")

            task.status = 'pending'
            db.commit()
            await self._log_task_db_state(task_id, stage="after_failure_commit_pending", worker_name=worker_name)

            # 延迟后重新入队
            await asyncio.sleep(delay)
            await redis_queue.enqueue(task_id, 'low')  # 重试任务低优先级
            await redis_queue.update_stats("total_retried")

            log_print(f"[{worker_name}] 🔄 任务已重新入队（低优先级）: {task_id}")
            await redis_queue.append_task_log(
                task_id,
                level="info",
                message=f"re-enqueued for retry (priority=low, delay_s={delay})",
                source="worker",
                extra={"worker": worker_name},
            )
        else:
            log_print(f"[{worker_name}] ❌❌❌ 任务最终失败（已达最大重试次数）: {task_id}", "ERROR")
            
            task.status = 'failed'
            task.completed_at = int(datetime.now().timestamp() * 1000)
            db.commit()
            await self._log_task_db_state(task_id, stage="after_failure_commit_failed", worker_name=worker_name)

            # 移入死信队列
            await redis_queue.move_to_dead_letter(task_id)
            await redis_queue.update_stats("total_failed")

            log_print(f"[{worker_name}] 📭 任务已移入死信队列: {task_id}")
            await redis_queue.append_task_log(
                task_id,
                level="error",
                message="moved to dead-letter queue",
                source="worker",
                extra={"worker": worker_name},
            )

    async def _log_task_db_state(self, task_id: str, stage: str, worker_name: str):
        """
        在单独的 DB session 中回读任务状态，写入任务日志。

        用于排查：Worker 已处理完成，但外部观察不到 upload_tasks 更新。
        """
        verify_db = SessionLocal()
        try:
            task = verify_db.query(UploadTask).filter(UploadTask.id == task_id).first()
            if not task:
                await redis_queue.append_task_log(
                    task_id,
                    level="warn",
                    message=f"db verify ({stage}): task not found",
                    source="db",
                    extra={"worker": worker_name},
                )
                return

            await redis_queue.append_task_log(
                task_id,
                level="info",
                message=(
                    f"db verify ({stage}): status={task.status}, "
                    f"target_url={'yes' if bool(task.target_url) else 'no'}, "
                    f"retry_count={task.retry_count}, "
                    f"completed_at={task.completed_at}"
                ),
                source="db",
                extra={"worker": worker_name},
            )
        except Exception as e:
            await redis_queue.append_task_log(
                task_id,
                level="error",
                message=f"db verify failed ({stage}): {e}",
                source="db",
                extra={"worker": worker_name},
            )
        finally:
            try:
                verify_db.close()
            except Exception:
                pass

    async def _update_session_attachment(
        self, db, session_id: str, message_id: str, attachment_id: str, url: str, worker_name: str
    ):
        """
        更新会话附件 (v3 架构)
        
        v3 架构：直接更新 message_attachments 表
        """
        from ...models.db_models import MessageAttachment
        
        attachment = db.query(MessageAttachment).filter(
            MessageAttachment.id == attachment_id
        ).first()
        
        if attachment:
            log_print(
                f"[{worker_name}] 📋 更新前附件状态: "
                f"user_id={attachment.user_id or 'None'}, "
                f"temp_url={'存在' if attachment.temp_url else 'None'}, "
                f"url={'存在' if attachment.url else 'None'}, "
                f"upload_status={attachment.upload_status}"
            )
            attachment.url = url
            attachment.upload_status = 'completed'
            attachment.temp_url = None  # ✅ 清空 temp_url，因为已上传到云存储
            db.commit()
            log_print(
                f"[{worker_name}] ✅ 附件表已更新: {attachment_id} "
                f"(url={url or 'None'}, status=completed, temp_url=cleared)"
            )
        else:
            log_print(f"[{worker_name}] ⚠️ 附件不存在: {attachment_id}", "WARNING")


# 全局单例
worker_pool = UploadWorkerPool()
