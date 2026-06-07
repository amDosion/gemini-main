"""PDF extraction routes"""
import os

from fastapi import APIRouter, HTTPException, File, UploadFile, Form

router = APIRouter(prefix="/api/pdf", tags=["pdf"])

# W02R-015: cap PDF uploads so a large document cannot exhaust worker memory.
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_UPLOAD_BYTES", str(25 * 1024 * 1024)))  # 25 MiB

# Service references (set in main.py)
extract_structured_data_from_pdf = None
get_available_templates = None
PDF_EXTRACTION_AVAILABLE = False


def set_pdf_service(extract_func, templates_func, available: bool):
    global extract_structured_data_from_pdf, get_available_templates, PDF_EXTRACTION_AVAILABLE
    extract_structured_data_from_pdf = extract_func
    get_available_templates = templates_func
    PDF_EXTRACTION_AVAILABLE = available


@router.get("/templates")
async def get_pdf_templates():
    if not PDF_EXTRACTION_AVAILABLE:
        raise HTTPException(status_code=503, detail="PDF extraction not available")
    return {"success": True, "templates": get_available_templates()}


@router.post("/extract")
async def extract_pdf_data(
    file: UploadFile = File(...),
    template_type: str = Form(...),
    api_key: str = Form(...),
    additional_instructions: str = Form(""),
    model_id: str = Form(...)
):
    if not PDF_EXTRACTION_AVAILABLE:
        raise HTTPException(status_code=503, detail="PDF extraction not available")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
    
    # W02R-015: bounded read (read at most MAX_PDF_BYTES+1) so an oversized upload
    # is rejected without buffering the whole body into memory.
    pdf_bytes = await file.read(MAX_PDF_BYTES + 1)
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds maximum size of {MAX_PDF_BYTES // (1024 * 1024)}MB",
        )
    
    result = await extract_structured_data_from_pdf(
        pdf_bytes=pdf_bytes, template_type=template_type,
        api_key=api_key, model_id=model_id.strip(),
        additional_instructions=additional_instructions
    )
    return result
