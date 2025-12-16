"""
FastAPI Backend for Gemini Chat Application
Clean architecture: main.py only handles initialization and router registration
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Core imports
from .core.database import Base, engine
from .core.logger import setup_logger, LOG_PREFIXES

logger = setup_logger("main")

# ============================================================================
# Database Initialization
# ============================================================================
from .models import ConfigProfile, UserSettings, ChatSession, Persona, History, StorageConfig, ActiveStorage, UploadTask
Base.metadata.create_all(bind=engine)
logger.info(f"{LOG_PREFIXES['info']} Database tables initialized")

# ============================================================================
# Service Availability Detection
# ============================================================================
SELENIUM_AVAILABLE = False
PDF_EXTRACTION_AVAILABLE = False
EMBEDDING_AVAILABLE = False

# Browser service
try:
    from .services.browser import selenium_browse, SELENIUM_AVAILABLE as _SEL
    SELENIUM_AVAILABLE = _SEL
except ImportError as e:
    logger.warning(f"Browser module not available: {e}")
    selenium_browse = None

# PDF service
try:
    from .services.pdf_extractor import extract_structured_data_from_pdf, get_available_templates
    PDF_EXTRACTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"PDF module not available: {e}")
    extract_structured_data_from_pdf = None
    get_available_templates = None

# Embedding service
try:
    from .services.embedding_service import rag_service
    EMBEDDING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Embedding module not available: {e}")
    rag_service = None

# ============================================================================
# FastAPI Application
# ============================================================================
app = FastAPI(
    title="Gemini Chat Backend",
    description="Backend API for browser automation, web scraping, and PDF extraction",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Router Registration (All routes defined in routers/ directory)
# ============================================================================
from .routers import health, storage, browse, pdf, embedding, dashscope_proxy, sessions, profiles, personas

# Set service availability for routers
health.set_availability(SELENIUM_AVAILABLE, PDF_EXTRACTION_AVAILABLE, EMBEDDING_AVAILABLE)
browse.set_browser_service(selenium_browse, SELENIUM_AVAILABLE)
pdf.set_pdf_service(extract_structured_data_from_pdf, get_available_templates, PDF_EXTRACTION_AVAILABLE)
embedding.set_embedding_service(rag_service, EMBEDDING_AVAILABLE)

# Register all routers
app.include_router(health.router)
app.include_router(storage.router)
app.include_router(sessions.router)
app.include_router(profiles.router)
app.include_router(personas.router)
app.include_router(browse.router)
app.include_router(pdf.router)
app.include_router(embedding.router)
app.include_router(dashscope_proxy.router)

# ============================================================================
# Startup Logging
# ============================================================================
logger.info("=" * 60)
logger.info(">>> Gemini Chat Backend Starting...")
logger.info("=" * 60)
logger.info(f"Selenium: {'[YES]' if SELENIUM_AVAILABLE else '[NO]'}")
logger.info(f"PDF Extraction: {'[YES]' if PDF_EXTRACTION_AVAILABLE else '[NO]'}")
logger.info(f"Embedding: {'[YES]' if EMBEDDING_AVAILABLE else '[NO]'}")
logger.info("=" * 60)
logger.info(f"{LOG_PREFIXES['info']} All routers registered")

# ============================================================================
# Entry Point
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
