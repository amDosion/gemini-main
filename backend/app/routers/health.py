"""Health check routes"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])

# 这些变量会在 main.py 中设置
SELENIUM_AVAILABLE = False
PDF_EXTRACTION_AVAILABLE = False
EMBEDDING_AVAILABLE = False


def set_availability(selenium: bool, pdf: bool, embedding: bool):
    global SELENIUM_AVAILABLE, PDF_EXTRACTION_AVAILABLE, EMBEDDING_AVAILABLE
    SELENIUM_AVAILABLE = selenium
    PDF_EXTRACTION_AVAILABLE = pdf
    EMBEDDING_AVAILABLE = embedding


@router.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Gemini Chat Backend API",
        "selenium_available": SELENIUM_AVAILABLE,
        "pdf_extraction_available": PDF_EXTRACTION_AVAILABLE,
        "embedding_available": EMBEDDING_AVAILABLE
    }


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,
        "embedding": EMBEDDING_AVAILABLE,
        "version": "1.0.0"
    }
