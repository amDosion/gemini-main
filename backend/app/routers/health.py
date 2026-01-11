"""Health check routes"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])

# 服务可用性标志（在 main.py 中通过 set_availability() 设置）
SELENIUM_AVAILABLE = False
PDF_EXTRACTION_AVAILABLE = False
EMBEDDING_AVAILABLE = False
WORKER_POOL_AVAILABLE = False


def set_availability(
    selenium: bool,
    pdf: bool,
    embedding: bool,
    worker_pool: bool = False
):
    """
    设置服务可用性标志
    
    Args:
        selenium: Selenium 浏览器服务是否可用
        pdf: PDF 提取服务是否可用
        embedding: 向量嵌入服务是否可用
        worker_pool: 上传 Worker 池是否可用
    """
    global SELENIUM_AVAILABLE, PDF_EXTRACTION_AVAILABLE, EMBEDDING_AVAILABLE, WORKER_POOL_AVAILABLE
    SELENIUM_AVAILABLE = selenium
    PDF_EXTRACTION_AVAILABLE = pdf
    EMBEDDING_AVAILABLE = embedding
    WORKER_POOL_AVAILABLE = worker_pool


@router.get("/")
async def root():
    """根路径健康检查端点"""
    return {
        "status": "ok",
        "message": "Gemini Chat Backend API",
        "selenium_available": SELENIUM_AVAILABLE,
        "pdf_extraction_available": PDF_EXTRACTION_AVAILABLE,
        "embedding_available": EMBEDDING_AVAILABLE,
        "upload_worker_pool_available": WORKER_POOL_AVAILABLE
    }


@router.get("/health")
async def health_check():
    """详细健康检查端点"""
    return {
        "status": "healthy",
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,
        "embedding": EMBEDDING_AVAILABLE,
        "upload_worker_pool": WORKER_POOL_AVAILABLE,
        "version": "1.0.0"
    }
