"""Lightweight batch job orchestration for PDF/table workloads."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

BatchWorkloadHandler = Callable[[Dict[str, Any]], Any | Awaitable[Any]]


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class BatchJobItem:
    id: str
    workload: str
    payload: Dict[str, Any]
    label: str
    status: str = "pending"
    attempts: int = 0
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    error: Optional[str] = None
    result: Any = None


@dataclass
class BatchJob:
    id: str
    user_id: str
    items: list[BatchJobItem] = field(default_factory=list)
    status: str = "queued"
    stop_on_error: bool = True
    item_timeout_seconds: Optional[float] = None
    created_at: int = field(default_factory=_now_ms)
    updated_at: int = field(default_factory=_now_ms)
    enqueued: bool = False
    cancel_requested: bool = False


class BatchJobError(Exception):
    """Base batch job error."""


class BatchJobNotFoundError(BatchJobError):
    """Raised when job id does not exist for current user."""


class BatchJobConflictError(BatchJobError):
    """Raised when operation conflicts with current job state."""


class BatchJobValidationError(BatchJobError):
    """Raised for invalid request payload or state transition."""


class BatchJobDependencyError(BatchJobError):
    """Raised when handler dependency is unavailable."""


class BatchJobOrchestrator:
    """Async in-memory queue orchestrator."""

    def __init__(self, handlers: Optional[Dict[str, BatchWorkloadHandler]] = None):
        self._handlers: Dict[str, BatchWorkloadHandler] = dict(handlers or {})
        self._jobs: Dict[str, BatchJob] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._drain_task: Optional[asyncio.Task[None]] = None

    def register_handler(self, workload: str, handler: BatchWorkloadHandler) -> None:
        normalized = str(workload or "").strip().lower()
        if not normalized:
            raise BatchJobValidationError("workload cannot be empty")
        self._handlers[normalized] = handler

    async def submit_job(
        self,
        *,
        user_id: str,
        items: list[Dict[str, Any]],
        stop_on_error: bool = True,
        item_timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not items:
            raise BatchJobValidationError("Batch job requires at least one item.")

        normalized_timeout: Optional[float] = None
        if item_timeout_seconds is not None:
            try:
                parsed_timeout = float(item_timeout_seconds)
            except Exception as exc:
                raise BatchJobValidationError("item_timeout_seconds must be a positive number.") from exc
            if parsed_timeout <= 0:
                raise BatchJobValidationError("item_timeout_seconds must be a positive number.")
            normalized_timeout = parsed_timeout

        normalized_items: list[BatchJobItem] = []
        for raw_item in items:
            workload = str(raw_item.get("workload") or "").strip().lower()
            payload = raw_item.get("payload")
            label = str(raw_item.get("label") or workload or "batch-item").strip()
            if not workload:
                raise BatchJobValidationError("Batch item workload is required.")
            if workload not in self._handlers:
                raise BatchJobValidationError(f"Unsupported batch workload: {workload}")
            if not isinstance(payload, dict):
                raise BatchJobValidationError("Batch item payload must be an object.")
            normalized_items.append(
                BatchJobItem(
                    id=str(raw_item.get("id") or uuid4()),
                    workload=workload,
                    payload=dict(payload),
                    label=label,
                )
            )

        job_id = str(uuid4())
        job = BatchJob(
            id=job_id,
            user_id=user_id,
            items=normalized_items,
            status="queued",
            stop_on_error=bool(stop_on_error),
            item_timeout_seconds=normalized_timeout,
            created_at=_now_ms(),
            updated_at=_now_ms(),
        )

        async with self._lock:
            self._jobs[job_id] = job
            await self._enqueue_locked(job)
            snapshot = self._serialize_progress_locked(job)

        self._ensure_drainer_started()
        return snapshot

    async def get_progress(self, *, user_id: str, job_id: str) -> Dict[str, Any]:
        async with self._lock:
            job = self._get_job_locked(user_id=user_id, job_id=job_id)
            return self._serialize_progress_locked(job)

    async def retry_job(
        self,
        *,
        user_id: str,
        job_id: str,
        include_completed: bool = False,
    ) -> Dict[str, Any]:
        async with self._lock:
            job = self._get_job_locked(user_id=user_id, job_id=job_id)
            if job.status == "running":
                raise BatchJobConflictError("Cannot retry while batch job is running.")

            reset_count = 0
            for item in job.items:
                if item.status in {"failed", "cancelled"} or (include_completed and item.status == "completed"):
                    item.status = "pending"
                    item.error = None
                    item.result = None
                    item.started_at = None
                    item.completed_at = None
                    reset_count += 1

            if reset_count <= 0:
                raise BatchJobValidationError("No failed/cancelled/completed items available for retry.")

            job.cancel_requested = False
            job.status = "queued"
            job.updated_at = _now_ms()
            await self._enqueue_locked(job)
            snapshot = self._serialize_progress_locked(job)

        self._ensure_drainer_started()
        return snapshot

    async def resume_job(
        self,
        *,
        user_id: str,
        job_id: str,
        skip_failed: bool = True,
    ) -> Dict[str, Any]:
        async with self._lock:
            job = self._get_job_locked(user_id=user_id, job_id=job_id)
            if job.status == "running":
                raise BatchJobConflictError("Batch job is already running.")
            if job.status == "cancelled":
                raise BatchJobConflictError("Batch job was cancelled. Use retry to restart.")

            has_failed = any(item.status == "failed" for item in job.items)
            has_pending = any(item.status == "pending" for item in job.items)
            if has_failed and not skip_failed:
                raise BatchJobValidationError("Resume blocked by failed items. Use retry first.")
            if not has_pending:
                if has_failed:
                    raise BatchJobValidationError("No pending items left. Use retry to rerun failed items.")
                raise BatchJobValidationError("Batch job has already completed.")

            job.cancel_requested = False
            job.status = "queued"
            job.updated_at = _now_ms()
            await self._enqueue_locked(job)
            snapshot = self._serialize_progress_locked(job)

        self._ensure_drainer_started()
        return snapshot

    async def cancel_job(self, *, user_id: str, job_id: str) -> Dict[str, Any]:
        async with self._lock:
            job = self._get_job_locked(user_id=user_id, job_id=job_id)
            if job.status in {"completed", "failed", "cancelled"}:
                return self._serialize_progress_locked(job)

            self._cancel_job_locked(job, now=_now_ms(), reason="Batch job cancelled by user.")
            return self._serialize_progress_locked(job)

    async def get_summary(self, *, user_id: str, job_id: str) -> Dict[str, Any]:
        async with self._lock:
            job = self._get_job_locked(user_id=user_id, job_id=job_id)
            return self._serialize_summary_locked(job)

    def _ensure_drainer_started(self) -> None:
        if self._drain_task and not self._drain_task.done():
            return
        loop = asyncio.get_running_loop()
        self._drain_task = loop.create_task(self._drain_queue(), name="batch-job-drainer")

    async def _enqueue_locked(self, job: BatchJob) -> None:
        if job.status == "cancelled" or job.cancel_requested:
            return
        if job.enqueued:
            return
        await self._queue.put(job.id)
        job.enqueued = True
        job.status = "queued"
        job.updated_at = _now_ms()

    @staticmethod
    def _cancel_job_locked(job: BatchJob, *, now: int, reason: str) -> None:
        job.cancel_requested = True
        job.enqueued = False
        job.status = "cancelled"
        job.updated_at = now
        for item in job.items:
            if item.status not in {"pending", "running"}:
                continue
            item.status = "cancelled"
            item.error = reason
            item.result = None
            item.completed_at = now

    async def _drain_queue(self) -> None:
        while True:
            try:
                job_id = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            try:
                await self._process_job(job_id)
            except Exception as exc:
                logger.error("[BatchJob] Unhandled drain error for %s: %s", job_id, exc, exc_info=True)
            finally:
                self._queue.task_done()

    async def _process_job(self, job_id: str) -> None:
        while True:
            async with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return

                job.enqueued = False
                if job.cancel_requested:
                    self._cancel_job_locked(job, now=_now_ms(), reason="Batch job cancelled by user.")
                    return
                if job.status not in {"queued", "running"}:
                    return

                next_item: Optional[BatchJobItem] = None
                for candidate in job.items:
                    if candidate.status == "pending":
                        next_item = candidate
                        break

                if next_item is None:
                    self._finalize_job_locked(job)
                    return

                now = _now_ms()
                job.status = "running"
                job.updated_at = now
                next_item.status = "running"
                next_item.started_at = now
                next_item.completed_at = None
                next_item.error = None
                next_item.attempts += 1
                item_id = next_item.id
                workload = next_item.workload
                payload = dict(next_item.payload)
                timeout_seconds = job.item_timeout_seconds

            try:
                result = await self._invoke_handler(
                    workload,
                    payload,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                if isinstance(exc, asyncio.TimeoutError):
                    if timeout_seconds is not None:
                        error_text = f"Batch item timed out after {timeout_seconds:.3f}s"
                    else:
                        error_text = "Batch item timed out."
                else:
                    error_text = str(exc) or exc.__class__.__name__
                async with self._lock:
                    job = self._jobs.get(job_id)
                    if job is None:
                        return
                    if job.cancel_requested:
                        self._cancel_job_locked(job, now=_now_ms(), reason="Batch job cancelled by user.")
                        return
                    item = self._find_item(job, item_id)
                    if item and item.status == "running":
                        item.status = "failed"
                        item.error = error_text
                        item.result = None
                        item.completed_at = _now_ms()
                    job.updated_at = _now_ms()

                    if job.stop_on_error:
                        job.status = "paused"
                        return

                    if any(candidate.status == "pending" for candidate in job.items):
                        job.status = "queued"
                        continue

                    self._finalize_job_locked(job)
                    return

            async with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                if job.cancel_requested:
                    self._cancel_job_locked(job, now=_now_ms(), reason="Batch job cancelled by user.")
                    return
                item = self._find_item(job, item_id)
                if item and item.status == "running":
                    item.status = "completed"
                    item.error = None
                    item.result = result
                    item.completed_at = _now_ms()
                job.updated_at = _now_ms()

                if any(candidate.status == "pending" for candidate in job.items):
                    job.status = "queued"
                    continue

                self._finalize_job_locked(job)
                return

    async def _invoke_handler(
        self,
        workload: str,
        payload: Dict[str, Any],
        *,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        handler = self._handlers.get(workload)
        if handler is None:
            raise BatchJobDependencyError(f"No handler registered for workload '{workload}'.")
        result = handler(payload)
        if inspect.isawaitable(result):
            if timeout_seconds is not None:
                return await asyncio.wait_for(result, timeout=timeout_seconds)
            return await result
        return result

    @staticmethod
    def _find_item(job: BatchJob, item_id: str) -> Optional[BatchJobItem]:
        for item in job.items:
            if item.id == item_id:
                return item
        return None

    @staticmethod
    def _status_counts(items: list[BatchJobItem]) -> Dict[str, int]:
        counts = {
            "total": len(items),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for item in items:
            status = str(item.status or "").strip().lower()
            if status in counts:
                counts[status] += 1
        return counts

    @staticmethod
    def _finalize_job_locked(job: BatchJob) -> None:
        has_failed = any(item.status == "failed" for item in job.items)
        has_cancelled = any(item.status == "cancelled" for item in job.items)
        has_pending = any(item.status in {"pending", "running"} for item in job.items)
        if has_pending:
            job.status = "running"
        elif job.cancel_requested or has_cancelled:
            job.status = "cancelled"
        elif has_failed:
            job.status = "failed"
        else:
            job.status = "completed"
        job.updated_at = _now_ms()
        job.enqueued = False

    def _get_job_locked(self, *, user_id: str, job_id: str) -> BatchJob:
        job = self._jobs.get(job_id)
        if not job or job.user_id != user_id:
            raise BatchJobNotFoundError("Batch job not found.")
        return job

    def _serialize_progress_locked(self, job: BatchJob) -> Dict[str, Any]:
        counts = self._status_counts(job.items)
        processed = counts["completed"] + counts["failed"] + counts["cancelled"]
        total = max(counts["total"], 1)
        progress_percent = int((processed * 100) / total)
        if job.status in {"completed", "failed", "cancelled"}:
            progress_percent = 100
        if progress_percent < 0:
            progress_percent = 0
        if progress_percent > 100:
            progress_percent = 100

        return {
            "job_id": job.id,
            "status": job.status,
            "progress_percent": progress_percent,
            "stop_on_error": bool(job.stop_on_error),
            "cancel_requested": bool(job.cancel_requested),
            "item_timeout_seconds": job.item_timeout_seconds,
            "counts": counts,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "items": [
                {
                    "item_id": item.id,
                    "label": item.label,
                    "workload": item.workload,
                    "status": item.status,
                    "attempts": item.attempts,
                    "error": item.error,
                    "started_at": item.started_at,
                    "completed_at": item.completed_at,
                }
                for item in job.items
            ],
        }

    def _serialize_summary_locked(self, job: BatchJob) -> Dict[str, Any]:
        counts = self._status_counts(job.items)
        table_rows_total = 0
        table_columns_total = 0
        completed_summaries: list[Dict[str, Any]] = []

        for item in job.items:
            if item.status != "completed":
                continue
            summary_payload = self._summarize_item_result(item)
            if summary_payload is not None:
                completed_summaries.append(
                    {
                        "item_id": item.id,
                        "label": item.label,
                        "workload": item.workload,
                        "summary": summary_payload,
                    }
                )
            if item.workload == "table_analysis" and isinstance(item.result, dict):
                table_summary = item.result.get("summary")
                if isinstance(table_summary, dict):
                    row_count = table_summary.get("row_count")
                    column_count = table_summary.get("column_count")
                    if isinstance(row_count, int):
                        table_rows_total += row_count
                    if isinstance(column_count, int):
                        table_columns_total += column_count

        return {
            "job_id": job.id,
            "status": job.status,
            "item_timeout_seconds": job.item_timeout_seconds,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "counts": counts,
            "failed_item_ids": [item.id for item in job.items if item.status == "failed"],
            "cancelled_item_ids": [item.id for item in job.items if item.status == "cancelled"],
            "table_metrics": {
                "total_rows": table_rows_total,
                "total_columns": table_columns_total,
            },
            "completed_items": completed_summaries,
        }

    @staticmethod
    def _summarize_item_result(item: BatchJobItem) -> Optional[Dict[str, Any]]:
        result = item.result
        if not isinstance(result, dict):
            return None

        if item.workload == "table_analysis":
            summary = result.get("summary")
            if not isinstance(summary, dict):
                return None
            output: Dict[str, Any] = {}
            for key in ("row_count", "column_count", "missing_cell_count", "missing_cell_rate"):
                if key in summary:
                    output[key] = summary.get(key)
            return output or None

        if item.workload == "pdf_extract":
            data = result.get("data")
            if isinstance(data, dict):
                keys = list(data.keys())
                return {
                    "success": bool(result.get("success", True)),
                    "field_count": len(keys),
                    "fields_preview": keys[:8],
                }
            return {"success": bool(result.get("success", True))}

        keys = list(result.keys())
        return {"keys_preview": keys[:8]}


def create_batch_job_orchestrator(
    handlers: Optional[Dict[str, BatchWorkloadHandler]] = None,
) -> BatchJobOrchestrator:
    return BatchJobOrchestrator(handlers=handlers)
