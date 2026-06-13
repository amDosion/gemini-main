"""Table analysis routes for CSV/XLSX datasets."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, JsonValue

from ...core.dependencies import require_current_user
from ...services.common.table_analysis_service import (
    InvalidTableInputError,
    TableAnalysisDependencyError,
    TableAnalysisError,
    UnsupportedTableFormatError,
    analyze_inline_table_content,
    analyze_table_bytes,
    export_table_analysis,
)
from ...utils.log_sanitization import summarize_text_for_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/table", tags=["table-analysis"])
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"
FREE_TEXT_PATTERN = r"^[\s\S]*$"
MAX_INLINE_TABLE_CONTENT = 28_000_000
MAX_TABLE_COLUMNS = 10_000


class InlineTableAnalysisRequest(BaseModel):
    """Inline table analysis request."""

    file_name: str = Field(
        ...,
        min_length=1,
        max_length=512,
        pattern=NO_CONTROL_CHARS_PATTERN,
        description="Input file name with extension.",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=MAX_INLINE_TABLE_CONTENT,
        pattern=FREE_TEXT_PATTERN,
        description="CSV text or base64 encoded XLSX content.",
    )
    file_format: Literal["csv", "xlsx"] | None = Field(
        default=None,
        description="Optional explicit file format.",
    )
    content_encoding: Literal["plain", "base64"] = Field(
        default="plain",
        description="plain for CSV text, base64 for binary payloads.",
    )
    csv_encoding: str = Field(
        default="utf-8",
        max_length=64,
        pattern=NO_CONTROL_CHARS_PATTERN,
        description="CSV encoding.",
    )
    sample_rows: int = Field(default=5, ge=1, le=100, description="Number of sample rows.")
    sheet_name: str | int | None = Field(
        default=0,
        max_length=256,
        description="Sheet index/name for XLSX.",
    )


class TableAnalysisExportRequest(BaseModel):
    """Export request."""

    format: Literal["json", "markdown"] = Field(default="json")
    analysis: dict[str, JsonValue] = Field(max_length=128)


class TableAnalysisResponse(BaseModel):
    summary: dict[str, JsonValue] = Field(max_length=64)
    fields: list[dict[str, JsonValue]] = Field(max_length=MAX_TABLE_COLUMNS)
    numeric_summary: dict[str, JsonValue] = Field(max_length=MAX_TABLE_COLUMNS)
    categorical_summary: dict[str, JsonValue] = Field(max_length=MAX_TABLE_COLUMNS)
    datetime_summary: dict[str, JsonValue] = Field(max_length=MAX_TABLE_COLUMNS)
    outlier_summary: dict[str, JsonValue] = Field(max_length=MAX_TABLE_COLUMNS)
    correlation_summary: dict[str, JsonValue] = Field(max_length=64)
    quality_flags: dict[str, JsonValue] = Field(max_length=64)
    column_groups: dict[str, JsonValue] = Field(max_length=16)
    sample_rows: list[dict[str, JsonValue]] = Field(max_length=100)
    evidence: dict[str, JsonValue] = Field(max_length=16)


@router.post("/analysis", response_model=TableAnalysisResponse)
async def analyze_table(
    file: UploadFile = File(...),
    sample_rows: int = Query(default=5, ge=1, le=100),
    csv_encoding: str = Query(default="utf-8", max_length=64, pattern=NO_CONTROL_CHARS_PATTERN),
    sheet_name: str | int | None = Query(default=0, max_length=256),
    user_id: str = Depends(require_current_user),
):
    """Analyze uploaded CSV/XLSX table and return structured summary."""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        return analyze_table_bytes(
            file_bytes=file_bytes,
            file_name=file.filename,
            file_format=None,
            sample_rows=sample_rows,
            csv_encoding=csv_encoding,
            sheet_name=sheet_name,
        )
    except UnsupportedTableFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except TableAnalysisDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidTableInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TableAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "Unexpected table analysis error: user=%s file=%s error=%s",
            summarize_text_for_log(user_id, label="user_id"),
            summarize_text_for_log(file.filename, label="file_name"),
            summarize_text_for_log(exc, label="table_analysis_error"),
        )
        raise HTTPException(status_code=500, detail="Failed to analyze table.") from exc


@router.post("/analysis/inline", response_model=TableAnalysisResponse)
async def analyze_table_inline(
    request_body: InlineTableAnalysisRequest,
    user_id: str = Depends(require_current_user),
):
    """Analyze inline CSV/XLSX content."""
    try:
        return analyze_inline_table_content(
            file_name=request_body.file_name,
            content=request_body.content,
            file_format=request_body.file_format,
            content_encoding=request_body.content_encoding,
            sample_rows=request_body.sample_rows,
            csv_encoding=request_body.csv_encoding,
            sheet_name=request_body.sheet_name,
        )
    except UnsupportedTableFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except TableAnalysisDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidTableInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TableAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "Unexpected inline table analysis error: user=%s file=%s error=%s",
            summarize_text_for_log(user_id, label="user_id"),
            summarize_text_for_log(request_body.file_name, label="file_name"),
            summarize_text_for_log(exc, label="inline_table_analysis_error"),
        )
        raise HTTPException(status_code=500, detail="Failed to analyze table.") from exc


@router.post(
    "/analysis/export",
    responses={
        200: {
            "description": "Exported table analysis",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/TableAnalysisResponse"}},
                "text/markdown": {"schema": {"type": "string", "maxLength": 1_000_000}},
            },
        }
    },
)
async def export_analysis(
    request_body: TableAnalysisExportRequest,
    user_id: str = Depends(require_current_user),
):
    """Export analysis result as json or markdown."""
    try:
        exported = export_table_analysis(
            analysis=request_body.analysis,
            export_format=request_body.format,
        )
    except InvalidTableInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "Unexpected table export error: user=%s format=%s error=%s",
            summarize_text_for_log(user_id, label="user_id"),
            request_body.format,
            summarize_text_for_log(exc, label="table_export_error"),
        )
        raise HTTPException(status_code=500, detail="Failed to export analysis.") from exc

    if request_body.format == "json":
        return JSONResponse(content=exported)
    return PlainTextResponse(content=str(exported), media_type="text/markdown")
