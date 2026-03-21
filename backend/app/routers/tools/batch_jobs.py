"""Batch job orchestration routes for PDF/table workloads."""

from __future__ import annotations

import base64
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.dependencies import require_current_user
from ...services.common.batch_job_orchestrator import (
    BatchJobConflictError,
    BatchJobDependencyError,
    BatchJobNotFoundError,
    BatchJobValidationError,
    create_batch_job_orchestrator,
)
from ...services.common.table_analysis_service import analyze_inline_table_content
from . import pdf as pdf_router_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch-jobs", tags=["batch-jobs"])


class BatchJobItemRequest(BaseModel):
    workload: Literal["table_analysis", "pdf_extract"] = Field(default="table_analysis")
    label: str | None = Field(default=None, description="Optional display label.")
    file_name: str = Field(..., min_length=1, description="Input file name.")
    content: str = Field(..., min_length=1, description="Inline content (csv text or base64 binary).")
    content_encoding: Literal["plain", "base64"] = Field(default="plain")

    # table_analysis payload
    file_format: Literal["csv", "xlsx"] | None = Field(default=None)
    csv_encoding: str = Field(default="utf-8")
    sample_rows: int = Field(default=5, ge=1, le=100)
    sheet_name: str | int | None = Field(default=0)

    # pdf_extract payload
    template_type: str = Field(default="invoice")
    model_id: str | None = Field(default=None)
    api_key: str | None = Field(default=None)
    additional_instructions: str = Field(default="")

    # testing/debug metadata
    meta: dict[str, Any] | None = Field(default=None)


class BatchSubmitRequest(BaseModel):
    items: list[BatchJobItemRequest] = Field(..., min_length=1, max_length=200)
    stop_on_error: bool = Field(default=True)
    item_timeout_seconds: float | None = Field(default=None, gt=0, le=3600)


class BatchRetryRequest(BaseModel):
    include_completed: bool = Field(default=False)


class BatchResumeRequest(BaseModel):
    skip_failed: bool = Field(default=True)


async def _table_analysis_handler(payload: dict[str, Any]) -> dict[str, Any]:
    return analyze_inline_table_content(
        file_name=str(payload.get("file_name") or "table.csv"),
        content=str(payload.get("content") or ""),
        file_format=payload.get("file_format"),
        content_encoding=payload.get("content_encoding") or "plain",
        sample_rows=int(payload.get("sample_rows") or 5),
        csv_encoding=str(payload.get("csv_encoding") or "utf-8"),
        sheet_name=payload.get("sheet_name"),
    )


async def _pdf_extract_handler(payload: dict[str, Any]) -> dict[str, Any]:
    if not pdf_router_module.PDF_EXTRACTION_AVAILABLE or not callable(pdf_router_module.extract_structured_data_from_pdf):
        raise BatchJobDependencyError("PDF extraction not available.")

    content = str(payload.get("content") or "").strip()
    if not content:
        raise BatchJobValidationError("PDF batch content is empty.")

    encoding = str(payload.get("content_encoding") or "base64").strip().lower()
    if encoding != "base64":
        raise BatchJobValidationError("PDF batch content must be base64 encoded.")

    try:
        pdf_bytes = base64.b64decode(content, validate=True)
    except Exception as exc:
        raise BatchJobValidationError("Invalid base64 content for PDF batch item.") from exc

    api_key = str(payload.get("api_key") or "").strip()
    model_id = str(payload.get("model_id") or "").strip()
    if not api_key:
        raise BatchJobValidationError("api_key is required for pdf_extract workload.")
    if not model_id:
        raise BatchJobValidationError("model_id is required for pdf_extract workload.")

    template_type = str(payload.get("template_type") or "invoice").strip() or "invoice"
    additional_instructions = str(payload.get("additional_instructions") or "")
    return await pdf_router_module.extract_structured_data_from_pdf(
        pdf_bytes=pdf_bytes,
        template_type=template_type,
        api_key=api_key,
        model_id=model_id,
        additional_instructions=additional_instructions,
    )


_batch_job_orchestrator = create_batch_job_orchestrator()
_batch_job_orchestrator.register_handler("table_analysis", _table_analysis_handler)
_batch_job_orchestrator.register_handler("pdf_extract", _pdf_extract_handler)


def _build_batch_submit_item(item: BatchJobItemRequest) -> dict[str, Any]:
    return {
        "workload": item.workload,
        "label": item.label or item.file_name,
        "payload": {
            "file_name": item.file_name,
            "content": item.content,
            "content_encoding": item.content_encoding,
            "file_format": item.file_format,
            "csv_encoding": item.csv_encoding,
            "sample_rows": item.sample_rows,
            "sheet_name": item.sheet_name,
            "template_type": item.template_type,
            "model_id": item.model_id,
            "api_key": item.api_key,
            "additional_instructions": item.additional_instructions,
            "meta": item.meta or {},
        },
    }


@router.post("/submit")
async def submit_batch_job(
    request_body: BatchSubmitRequest,
    user_id: str = Depends(require_current_user),
):
    try:
        items = [_build_batch_submit_item(item) for item in request_body.items]
        return await _batch_job_orchestrator.submit_job(
            user_id=user_id,
            items=items,
            stop_on_error=request_body.stop_on_error,
            item_timeout_seconds=request_body.item_timeout_seconds,
        )
    except BatchJobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BatchJobDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected batch submit error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit batch job.") from exc


@router.get("/{job_id}/progress")
async def get_batch_job_progress(
    job_id: str,
    user_id: str = Depends(require_current_user),
):
    try:
        return await _batch_job_orchestrator.get_progress(user_id=user_id, job_id=job_id)
    except BatchJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected batch progress error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query batch progress.") from exc


@router.post("/{job_id}/retry")
async def retry_batch_job(
    job_id: str,
    request_body: BatchRetryRequest | None = None,
    user_id: str = Depends(require_current_user),
):
    body = request_body or BatchRetryRequest()
    try:
        return await _batch_job_orchestrator.retry_job(
            user_id=user_id,
            job_id=job_id,
            include_completed=body.include_completed,
        )
    except BatchJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BatchJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BatchJobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected batch retry error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retry batch job.") from exc


@router.post("/{job_id}/resume")
async def resume_batch_job(
    job_id: str,
    request_body: BatchResumeRequest | None = None,
    user_id: str = Depends(require_current_user),
):
    body = request_body or BatchResumeRequest()
    try:
        return await _batch_job_orchestrator.resume_job(
            user_id=user_id,
            job_id=job_id,
            skip_failed=body.skip_failed,
        )
    except BatchJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BatchJobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BatchJobValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected batch resume error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resume batch job.") from exc


@router.post("/{job_id}/cancel")
async def cancel_batch_job(
    job_id: str,
    user_id: str = Depends(require_current_user),
):
    try:
        return await _batch_job_orchestrator.cancel_job(user_id=user_id, job_id=job_id)
    except BatchJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected batch cancel error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel batch job.") from exc


@router.get("/{job_id}/summary")
async def get_batch_job_summary(
    job_id: str,
    user_id: str = Depends(require_current_user),
):
    try:
        return await _batch_job_orchestrator.get_summary(user_id=user_id, job_id=job_id)
    except BatchJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected batch summary error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to build batch summary.") from exc
