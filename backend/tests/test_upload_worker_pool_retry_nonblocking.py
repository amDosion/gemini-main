"""
对抗验证测试（RED-first）：upload-worker 集群修复

覆盖：
- B1: _handle_failure 重试路径不得在单 worker 事件循环中 inline `await asyncio.sleep(delay)`
       阻塞整个退避窗口；必须以「延迟重新入队」的方式让 worker 循环在退避期间
       继续抽取/处理其它任务。重试计数与退避语义、幂等性保持不变。
"""

import asyncio
import time

import logging

import pytest

from app.services.common.upload_worker_pool import UploadWorkerPool


async def _async_noop(*args, **kwargs):
    return None


class _FakeTask:
    """最小化 UploadTask 替身。"""

    def __init__(self, task_id, retry_count=0):
        self.id = task_id
        self.retry_count = retry_count
        self.error_message = None
        self.status = "uploading"
        self.completed_at = None
        self.target_url = None
        self.source_file_path = None


class _RecordingQueue:
    """记录 enqueue 顺序/时间戳的假 redis_queue。"""

    def __init__(self):
        self.enqueued = []  # (task_id, priority, monotonic_ts)
        self.stats = {}
        self.dead = []
        self.logs = []

    async def enqueue(self, task_id, priority="normal"):
        self.enqueued.append((task_id, priority, time.monotonic()))
        return len(self.enqueued)

    async def update_stats(self, field, increment=1):
        self.stats[field] = self.stats.get(field, 0) + increment

    async def append_task_log(self, *args, **kwargs):
        self.logs.append((args, kwargs))
        return None

    async def move_to_dead_letter(self, task_id):
        self.dead.append(task_id)


class _FakeDB:
    def __init__(self, task):
        self._task = task

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._task

    def commit(self):
        return None


class _WorkerLoopQueue:
    """
    驱动 _worker_loop 的假队列：按 FIFO 顺序交付预置 task_id，
    交付完毕后 dequeue 返回 None。acquire_lock/release_lock/限流恒成功。
    记录 enqueue 顺序与时间戳。
    """

    def __init__(self, task_ids):
        self._pending = list(task_ids)
        self.enqueued = []  # (task_id, priority, monotonic_ts)
        self.stats = {}
        self.dead = []

    async def dequeue(self, timeout=5):
        if self._pending:
            return self._pending.pop(0)
        return None

    async def append_task_log(self, *args, **kwargs):
        return None

    async def acquire_lock(self, task_id, worker_id, ttl=60):
        return True

    async def release_lock(self, task_id, worker_id):
        return True

    async def wait_for_rate_token(self, max_wait=30):
        return True

    async def enqueue(self, task_id, priority="normal"):
        self.enqueued.append((task_id, priority, time.monotonic()))
        return len(self.enqueued)

    async def update_stats(self, field, increment=1):
        self.stats[field] = self.stats.get(field, 0) + increment

    async def move_to_dead_letter(self, task_id):
        self.dead.append(task_id)


@pytest.mark.asyncio
async def test_worker_keeps_draining_during_backoff(monkeypatch):
    """
    B1 对抗验证（worker-loop 级别）：

    单 worker 顺序处理队列。task-A 处理失败触发退避重试，task-B 排在其后。
    若 _handle_failure 在退避窗口内 inline `await asyncio.sleep(delay)`，
    则单 worker 循环被卡住，task-B 必须等到 A 的退避窗口结束后才会被 dequeue/处理。

    断言：task-B 在 task-A 的退避窗口（>=0.5s）结束之前就完成处理，
    证明退避不再阻塞 worker 循环对其它任务的抽取。
    """
    pool = UploadWorkerPool()
    pool.max_retries = 3
    pool.base_retry_delay = 0.5  # task-A retry -> 退避 0.5s
    pool._running = True

    fake_queue = _WorkerLoopQueue(["task-A", "task-B"])
    monkeypatch.setattr(
        "app.services.common.upload_worker_pool.redis_queue", fake_queue
    )
    monkeypatch.setattr(pool, "_log_task_db_state", _async_noop)
    # _mark_task_uploading 是同步 DB 写，桩为恒真（无 DB）
    monkeypatch.setattr(pool, "_mark_task_uploading", lambda task_id: True)

    completed = {}

    async def fake_process_task(task_id, worker_name):
        if task_id == "task-A":
            # 触发失败 -> 退避重试路径
            task = _FakeTask("task-A", retry_count=0)
            await pool._handle_failure(_FakeDB(task), "task-A", "boom", worker_name)
        else:
            completed[task_id] = time.monotonic()
            # B 处理完成后停掉 worker，避免无限循环
            pool._running = False

    monkeypatch.setattr(pool, "_process_task", fake_process_task)

    start = time.monotonic()
    await asyncio.wait_for(pool._worker_loop(), timeout=3.0)

    assert "task-B" in completed, "task-B 应被处理"
    b_elapsed = completed["task-B"] - start
    assert b_elapsed < 0.4, (
        f"task-B 在 task-A 退避窗口结束前未完成 (elapsed={b_elapsed:.3f}s)，"
        f"说明退避仍 inline 阻塞了单 worker 循环（B1 未修复）"
    )

    # 行为保持：task-A 最终被延迟重新入队（低优先级），退避语义保持
    deadline = time.monotonic() + 1.5
    while not fake_queue.enqueued and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    assert fake_queue.enqueued, "task-A 应被延迟重新入队"
    enq_task, enq_priority, enq_ts = fake_queue.enqueued[0]
    assert enq_task == "task-A"
    assert enq_priority == "low"
    assert (enq_ts - start) >= 0.45, "重新入队应在退避延迟之后发生（退避语义保持）"
    assert fake_queue.stats.get("total_retried") == 1


@pytest.mark.asyncio
async def test_retry_requeue_not_double_processed(monkeypatch):
    """B1 幂等：单次失败只产生一次延迟重新入队，不得重复入队。"""
    pool = UploadWorkerPool()
    pool.max_retries = 3
    pool.base_retry_delay = 0.1

    fake_queue = _RecordingQueue()
    monkeypatch.setattr(
        "app.services.common.upload_worker_pool.redis_queue", fake_queue
    )
    monkeypatch.setattr(pool, "_log_task_db_state", _async_noop)

    task = _FakeTask("task-B", retry_count=0)
    await pool._handle_failure(_FakeDB(task), "task-B", "boom", "Worker-0")

    deadline = time.monotonic() + 1.0
    while not fake_queue.enqueued and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    # 再多等一会，确保不会二次入队
    await asyncio.sleep(0.2)
    assert len(fake_queue.enqueued) == 1, "单次失败应只重新入队一次（幂等）"


@pytest.mark.asyncio
async def test_max_retries_moves_to_dead_letter(monkeypatch):
    """退避路径之外的语义保持：达到最大重试次数应进入死信，不再重新入队。"""
    pool = UploadWorkerPool()
    pool.max_retries = 3
    pool.base_retry_delay = 0.1

    fake_queue = _RecordingQueue()
    monkeypatch.setattr(
        "app.services.common.upload_worker_pool.redis_queue", fake_queue
    )
    monkeypatch.setattr(pool, "_log_task_db_state", _async_noop)

    # retry_count=2 -> +1 = 3 == max_retries -> 死信
    task = _FakeTask("task-C", retry_count=2)
    await pool._handle_failure(_FakeDB(task), "task-C", "boom", "Worker-0")
    # 给任何潜在的延迟任务一点时间（确认不会入队）
    await asyncio.sleep(0.2)

    assert task.status == "failed"
    assert fake_queue.dead == ["task-C"]
    assert fake_queue.enqueued == []
    assert fake_queue.stats.get("total_failed") == 1


@pytest.mark.asyncio
async def test_handle_failure_sanitizes_error_diagnostics(monkeypatch, caplog):
    """Failure diagnostics must not persist signed URLs or token-shaped values."""
    pool = UploadWorkerPool()
    pool.max_retries = 1

    fake_queue = _RecordingQueue()
    monkeypatch.setattr(
        "app.services.common.upload_worker_pool.redis_queue", fake_queue
    )
    monkeypatch.setattr(pool, "_log_task_db_state", _async_noop)

    task = _FakeTask("task-D", retry_count=0)
    signed_url = (
        "https://cdn.example.com/private.png"
        "?X-Amz-Signature=secret-signature&token=secret-token#private-fragment"
    )
    raw_error = (
        f"provider failed for {signed_url} with "
        "Bearer abcd1234567890SECRET and api_key=sk-1234567890SECRET"
    )

    with caplog.at_level(logging.INFO, logger="app.services.common.upload_worker_pool"):
        await pool._handle_failure(_FakeDB(task), "task-D", raw_error, "Worker-0")

    queue_messages = "\n".join(kwargs.get("message", "") for _args, kwargs in fake_queue.logs)
    persisted_and_logged = "\n".join([task.error_message or "", caplog.text, queue_messages])

    assert "http(len=" in persisted_and_logged
    assert "Bearer abcd...redacted" in persisted_and_logged
    assert "api_key=sk-1...redacted" in persisted_and_logged
    assert signed_url not in persisted_and_logged
    assert "secret-signature" not in persisted_and_logged
    assert "secret-token" not in persisted_and_logged
    assert "private-fragment" not in persisted_and_logged
    assert "1234567890SECRET" not in persisted_and_logged
