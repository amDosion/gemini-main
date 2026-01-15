"""PDF extraction routes"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form

router = APIRouter(prefix="/api/pdf", tags=["pdf"])

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
    
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    result = await extract_structured_data_from_pdf(
        pdf_bytes=pdf_bytes, template_type=template_type,
        api_key=api_key, model_id=model_id.strip(),
        additional_instructions=additional_instructions
    )
    return result
