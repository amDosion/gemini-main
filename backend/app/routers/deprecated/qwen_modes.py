"""
Qwen Mode API Router

This module provides API endpoints for Qwen-specific advanced features (web search,
code interpreter, PDF parser) that frontend will call.

Endpoints:
- POST /api/qwen/search - Web search with Qwen
- POST /api/qwen/code-interpreter - Code execution with Qwen
- POST /api/qwen/pdf-parser - PDF parsing with Qwen

Created: 2026-01-11
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import uuid

from ...core.database import SessionLocal
from ...core.user_context import require_user_id
from ...models.db_models import ConfigProfile, UserSettings
from ...services.tongyi.chat import QwenNativeProvider
from ...core.encryption import decrypt_data, is_encrypted

logger = logging.getLogger(__name__)


def _decrypt_api_key(api_key: str) -> str:
    """解密 API Key（兼容未加密的历史数据）"""
    if not api_key:
        return api_key
    if not is_encrypted(api_key):
        return api_key
    try:
        return decrypt_data(api_key)
    except Exception as e:
        logger.warning(f"[Qwen Modes] API key decryption failed: {e}")
        return api_key

router = APIRouter(prefix="/api/qwen", tags=["qwen-modes"])


# ==================== Database Dependency ====================

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Request Models ====================

class SearchRequest(BaseModel):
    """Web search request model"""
    query: str = Field(..., description="Search query")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    model: Optional[str] = Field("qwen-max", description="Model to use")
    temperature: Optional[float] = Field(0.7, description="Temperature (0-2)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")


class CodeInterpreterRequest(BaseModel):
    """Code interpreter request model"""
    code: str = Field(..., description="Code to execute")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    model: Optional[str] = Field("qwen-max", description="Model to use")
    temperature: Optional[float] = Field(0.7, description="Temperature (0-2)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")


class PDFParserRequest(BaseModel):
    """PDF parser request model"""
    pdf_url: str = Field(..., description="URL to PDF file")
    query: str = Field(..., description="Query about the PDF")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    model: Optional[str] = Field("qwen-max", description="Model to use")
    temperature: Optional[float] = Field(0.7, description="Temperature (0-2)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")


# ==================== Helper Functions ====================

async def get_qwen_credentials(
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None
) -> str:
    """
    Get Qwen API credentials from database.
    
    Priority:
    1. Request parameter (for testing/override)
    2. Active profile in database
    3. Any Qwen profile in database
    
    Args:
        db: Database session
        user_id: Current user ID
        request_api_key: Optional API key from request
    
    Returns:
        API key
    
    Raises:
        HTTPException: If no API key found
    """
    # 1. Use request parameter if provided
    if request_api_key and request_api_key.strip():
        logger.info("[Qwen Modes] Using API key from request parameter")
        return request_api_key
    
    # 2. Get from database
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None
    
    matching_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == 'tongyi',
        ConfigProfile.user_id == user_id
    ).all()
    
    if not matching_profiles:
        raise HTTPException(
            status_code=401,
            detail="API Key not found for provider: tongyi. Please configure it in Settings → Profiles."
        )
    
    # Priority: active profile
    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                logger.info(f"[Qwen Modes] Using API key from active profile '{profile.name}'")
                return _decrypt_api_key(profile.api_key)

    # Fallback: first matching profile
    for profile in matching_profiles:
        if profile.api_key:
            logger.info(f"[Qwen Modes] Using API key from profile '{profile.name}' (fallback)")
            return _decrypt_api_key(profile.api_key)
    
    raise HTTPException(
        status_code=401,
        detail="API Key not found for provider: tongyi. Please configure it in Settings → Profiles."
    )


# ==================== API Endpoints ====================

@router.post("/search")
async def web_search(
    request_data: SearchRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Perform web search with Qwen.
    
    Request Body:
        {
            "query": "search query",
            "messages": [...],
            "model": "qwen-max",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    
    Response:
        {
            "content": "response with search results",
            "role": "assistant",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300
            },
            "search_results": [...],
            "request_id": "uuid"
        }
    """
    try:
        # Verify user authentication
        user_id = require_user_id(request)
        request_id = str(uuid.uuid4())
        
        logger.info(
            f"[Qwen Modes] Web search request: "
            f"user={user_id}, model={request_data.model}, request_id={request_id}"
        )
        
        # Get API credentials
        api_key = await get_qwen_credentials(db, user_id)
        
        # Create Qwen provider instance
        provider = QwenNativeProvider(
            api_key=api_key,
            connection_mode="official"  # Required for web search
        )
        
        # Prepare parameters
        params = {
            "enable_search": True,  # Enable web search
            "temperature": request_data.temperature,
        }
        
        if request_data.max_tokens:
            params["max_tokens"] = request_data.max_tokens
        
        # Execute chat with search
        result = await provider.chat(
            messages=request_data.messages,
            model=request_data.model,
            **params
        )
        
        # Add request ID to response
        result["request_id"] = request_id
        
        logger.info(f"[Qwen Modes] Web search completed: request_id={request_id}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Qwen Modes] Web search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/code-interpreter")
async def code_interpreter(
    request_data: CodeInterpreterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Execute code with Qwen code interpreter.
    
    Request Body:
        {
            "code": "print('hello')",
            "messages": [...],
            "model": "qwen-max",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    
    Response:
        {
            "content": "execution result",
            "role": "assistant",
            "usage": {...},
            "request_id": "uuid"
        }
    """
    try:
        # Verify user authentication
        user_id = require_user_id(request)
        request_id = str(uuid.uuid4())
        
        logger.info(
            f"[Qwen Modes] Code interpreter request: "
            f"user={user_id}, model={request_data.model}, request_id={request_id}"
        )
        
        # Get API credentials
        api_key = await get_qwen_credentials(db, user_id)
        
        # Create Qwen provider instance
        provider = QwenNativeProvider(
            api_key=api_key,
            connection_mode="official"  # Required for plugins
        )
        
        # Prepare parameters
        params = {
            "plugins": ["code_interpreter"],  # Enable code interpreter plugin
            "temperature": request_data.temperature,
        }
        
        if request_data.max_tokens:
            params["max_tokens"] = request_data.max_tokens
        
        # Execute chat with code interpreter
        result = await provider.chat(
            messages=request_data.messages,
            model=request_data.model,
            **params
        )
        
        # Add request ID to response
        result["request_id"] = request_id
        
        logger.info(f"[Qwen Modes] Code interpreter completed: request_id={request_id}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Qwen Modes] Code interpreter error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf-parser")
async def pdf_parser(
    request_data: PDFParserRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Parse PDF with Qwen PDF parser.
    
    Request Body:
        {
            "pdf_url": "https://example.com/file.pdf",
            "query": "summarize this PDF",
            "messages": [...],
            "model": "qwen-max",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    
    Response:
        {
            "content": "PDF analysis result",
            "role": "assistant",
            "usage": {...},
            "request_id": "uuid"
        }
    """
    try:
        # Verify user authentication
        user_id = require_user_id(request)
        request_id = str(uuid.uuid4())
        
        logger.info(
            f"[Qwen Modes] PDF parser request: "
            f"user={user_id}, model={request_data.model}, request_id={request_id}"
        )
        
        # Get API credentials
        api_key = await get_qwen_credentials(db, user_id)
        
        # Create Qwen provider instance
        provider = QwenNativeProvider(
            api_key=api_key,
            connection_mode="official"  # Required for plugins
        )
        
        # Prepare parameters
        params = {
            "plugins": {
                "pdf_extracter": {
                    "enable": True,
                    "url": request_data.pdf_url
                }
            },
            "temperature": request_data.temperature,
        }
        
        if request_data.max_tokens:
            params["max_tokens"] = request_data.max_tokens
        
        # Execute chat with PDF parser
        result = await provider.chat(
            messages=request_data.messages,
            model=request_data.model,
            **params
        )
        
        # Add request ID to response
        result["request_id"] = request_id
        
        logger.info(f"[Qwen Modes] PDF parser completed: request_id={request_id}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Qwen Modes] PDF parser error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
