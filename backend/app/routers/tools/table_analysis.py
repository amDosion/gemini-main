"""Table analysis routes for CSV/XLSX datasets."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/table", tags=["table-analysis"])


class InlineTableAnalysisRequest(BaseModel):
    """Inline table analysis request."""

    file_name: str = Field(..., min_length=1, description="Input file name with extension.")
    content: str = Field(..., min_length=1, description="CSV text or base64 encoded XLSX content.")
    file_format: Literal["csv", "xlsx"] | None = Field(
        default=None,
        description="Optional explicit file format.",
    )
    content_encoding: Literal["plain", "base64"] = Field(
        default="plain",
        description="plain for CSV text, base64 for binary payloads.",
    )
    csv_encoding: str = Field(default="utf-8", description="CSV encoding.")
    sample_rows: int = Field(default=5, ge=1, le=100, description="Number of sample rows.")
    sheet_name: str | int | None = Field(default=0, description="Sheet index/name for XLSX.")


class TableAnalysisExportRequest(BaseModel):
    """Export request."""

    format: Literal["json", "markdown"] = Field(default="json")
    analysis: dict[str, Any]


@router.post("/analysis")
async def analyze_table(
    file: UploadFile = File(...),
    sample_rows: int = 5,
    csv_encoding: str = "utf-8",
    sheet_name: str | int | None = 0,
    user_id: str = Depends(require_current_user),
):
    """Analyze uploaded CSV/XLSX table and return structured summary."""
    _ = user_id
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
        logger.error("Unexpected table analysis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze table.") from exc


@router.post("/analysis/inline")
async def analyze_table_inline(
    request_body: InlineTableAnalysisRequest,
    user_id: str = Depends(require_current_user),
):
    """Analyze inline CSV/XLSX content."""
    _ = user_id
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
        logger.error("Unexpected inline table analysis error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze table.") from exc


@router.post("/analysis/export")
async def export_analysis(
    request_body: TableAnalysisExportRequest,
    user_id: str = Depends(require_current_user),
):
    """Export analysis result as json or markdown."""
    _ = user_id
    try:
        exported = export_table_analysis(
            analysis=request_body.analysis,
            export_format=request_body.format,
        )
    except InvalidTableInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected table export error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export analysis.") from exc

    if request_body.format == "json":
        return JSONResponse(content=exported)
    return PlainTextResponse(content=str(exported), media_type="text/markdown")
