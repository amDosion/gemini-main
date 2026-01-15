"""
Imagen Configuration API Router

This module provides API endpoints for managing Imagen API configuration,
including switching between Gemini API and Vertex AI, testing connections,
and retrieving capabilities.

架构说明：
- GET /config: 通过 ProviderFactory.create("google") 获取 GoogleService，调用 get_imagen_capabilities()
- POST /config: 直接操作数据库配置（不需要 GoogleService）
- POST /test-connection: 直接使用子服务测试（因为测试的是用户提供的凭证，不是存储的凭证）
- POST /verify-vertex-ai: 直接使用 genai.Client（同上，测试用户提供的凭证）

Updated: 2026-01-14 - 统一通过 GoogleService 调用（get_imagen_config 端点）
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any, List
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.encryption import encrypt_data, decrypt_data, is_encrypted
from ...models.db_models import ImagenConfig, ConfigProfile, UserSettings
from ...services.common.provider_factory import ProviderFactory
from ...services.gemini.imagen_common import ConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/imagen", tags=["imagen"])


# ==================== Request/Response Models ====================

class ImagenConfigResponse(BaseModel):
    """Response model for Imagen configuration"""
    api_mode: Literal['gemini_api', 'vertex_ai'] = Field(alias='apiMode')
    capabilities: Dict[str, Any]
    gemini_api_configured: bool = Field(alias='geminiApiConfigured')
    vertex_ai_configured: bool = Field(alias='vertexAiConfigured')
    vertex_ai_project_id: Optional[str] = Field(default=None, alias='vertexAiProjectId')
    vertex_ai_location: Optional[str] = Field(default='us-central1', alias='vertexAiLocation')
    vertex_ai_credentials_json: Optional[str] = Field(default=None, alias='vertexAiCredentialsJson')
    hidden_models: List[str] = Field(default_factory=list, alias='hiddenModels')
    saved_models: List[Dict[str, Any]] = Field(default_factory=list, alias='savedModels')

    class Config:
        populate_by_name = True


class ImagenConfigUpdateRequest(BaseModel):
    """Request model for updating Imagen configuration"""
    apiMode: Literal['gemini_api', 'vertex_ai'] = Field(
        alias='api_mode',
        description="API mode to use for image generation"
    )
    
    # Gemini API config (optional, uses LLM API key if not provided)
    geminiApiKey: Optional[str] = Field(
        default=None,
        alias='gemini_api_key',
        description="Gemini API key (optional, uses LLM config if not provided)"
    )
    
    # Vertex AI config
    vertexAiProjectId: Optional[str] = Field(
        default=None,
        alias='vertex_ai_project_id',
        description="Google Cloud project ID (required for vertex_ai mode)"
    )
    vertexAiLocation: Optional[str] = Field(
        default='us-central1',
        alias='vertex_ai_location',
        description="Vertex AI location/region"
    )
    vertexAiCredentialsJson: Optional[str] = Field(
        default=None,
        alias='vertex_ai_credentials_json',
        description="Service account credentials JSON content (required for vertex_ai mode)"
    )
    hiddenModels: Optional[List[str]] = Field(
        default=None,
        alias='hidden_models',
        description="List of hidden model IDs"
    )
    savedModels: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        alias='saved_models',
        description="List of saved model configurations (ModelConfig[])"
    )
    
    class Config:
        populate_by_name = True  # Allow both camelCase and snake_case


class TestConnectionRequest(BaseModel):
    """Request model for testing API connection"""
    apiMode: Literal['gemini_api', 'vertex_ai'] = Field(alias='api_mode')
    
    # Gemini API credentials
    geminiApiKey: Optional[str] = Field(default=None, alias='gemini_api_key')
    
    # Vertex AI credentials
    vertexAiProjectId: Optional[str] = Field(default=None, alias='vertex_ai_project_id')
    vertexAiLocation: Optional[str] = Field(default='us-central1', alias='vertex_ai_location')
    vertexAiCredentialsJson: Optional[str] = Field(default=None, alias='vertex_ai_credentials_json')
    
    class Config:
        populate_by_name = True  # Allow both camelCase and snake_case


class TestConnectionResponse(BaseModel):
    """Response model for connection test"""
    success: bool
    api_mode: str
    message: str
    details: Optional[Dict[str, Any]] = None


class VertexAIModel(BaseModel):
    """Model information from Vertex AI"""
    id: str
    name: str
    display_name: Optional[str] = Field(default=None, alias='displayName')
    
    class Config:
        populate_by_name = True


class VerifyVertexAIRequest(BaseModel):
    """Request model for verifying Vertex AI connection and listing models"""
    projectId: str = Field(alias='project_id')
    location: str = Field(default='us-central1')
    credentialsJson: str = Field(alias='credentials_json')
    
    class Config:
        populate_by_name = True


class VerifyVertexAIResponse(BaseModel):
    """Response model for Vertex AI verification"""
    success: bool
    message: str
    models: List[VertexAIModel] = []


# ==================== Helper Functions ====================

async def _get_google_api_key(db: Session, user_id: str) -> Optional[str]:
    """
    Get Google API Key from database for the user.

    Priority:
    1. Active profile's API key
    2. Any Google profile's API key

    Returns:
        API key string or None if not found
    """
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    matching_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == 'google',
        ConfigProfile.user_id == user_id
    ).all()

    if not matching_profiles:
        return None

    # Priority: active profile
    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                api_key = profile.api_key
                if is_encrypted(api_key):
                    try:
                        return decrypt_data(api_key)
                    except Exception:
                        return api_key
                return api_key

    # Fallback: first matching profile
    for profile in matching_profiles:
        if profile.api_key:
            api_key = profile.api_key
            if is_encrypted(api_key):
                try:
                    return decrypt_data(api_key)
                except Exception:
                    return api_key
            return api_key

    return None


# ==================== API Endpoints ====================

@router.get("/config", response_model=ImagenConfigResponse, response_model_by_alias=True)
async def get_imagen_config(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current Imagen API configuration and capabilities for the authenticated user.

    通过 ProviderFactory.create("google") 获取 GoogleService，调用 get_imagen_capabilities()

    Returns:
        Current API mode, capabilities, and configuration status
    """
    try:
        # user_id 已通过依赖注入自动获取

        logger.info(f"[ImagenConfig] Getting configuration for user={user_id}")

        # ✅ 2. 查询用户的 Imagen 配置
        user_config = db.query(ImagenConfig).filter(ImagenConfig.user_id == user_id).first()

        # Default capabilities (used when no config or no API key)
        default_capabilities = {
            "supported_models": ["imagen-3.0-generate-001"],
            "max_images": 8,
            "supported_aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "person_generation_modes": ["dont_allow", "allow_adult"]
        }

        if not user_config:
            # Return default configuration if user hasn't set up yet
            logger.info(f"[ImagenConfig] No configuration found for user={user_id}, returning defaults")
            return ImagenConfigResponse(
                api_mode='gemini_api',
                capabilities=default_capabilities,
                gemini_api_configured=False,
                vertex_ai_configured=False,
                vertex_ai_project_id=None,
                vertex_ai_location='us-central1',
                vertex_ai_credentials_json=None,
                hidden_models=[],
                saved_models=[]
            )

        # ✅ 3. 获取 Google API Key
        api_key = await _get_google_api_key(db, user_id)

        # ✅ 4. 通过 ProviderFactory 创建 GoogleService 获取 capabilities
        capabilities = default_capabilities
        if api_key:
            try:
                service = ProviderFactory.create(
                    provider="google",
                    api_key=api_key,
                    user_id=user_id,
                    db=db
                )
                capabilities = service.get_imagen_capabilities()
                logger.info(f"[ImagenConfig] Got capabilities via GoogleService for user={user_id}")
            except Exception as e:
                logger.warning(
                    f"[ImagenConfig] Failed to get capabilities via GoogleService, using defaults: {e}"
                )

        # ✅ 5. 处理 Vertex AI 配置（解密凭证）
        vertex_ai_project_id = user_config.vertex_ai_project_id
        vertex_ai_location = user_config.vertex_ai_location or 'us-central1'
        vertex_ai_credentials_json = None
        if user_config.vertex_ai_credentials_json:
            try:
                if is_encrypted(user_config.vertex_ai_credentials_json):
                    vertex_ai_credentials_json = decrypt_data(
                        user_config.vertex_ai_credentials_json
                    )
                else:
                    vertex_ai_credentials_json = user_config.vertex_ai_credentials_json
            except Exception as e:
                logger.error(
                    f"[ImagenConfig] Failed to decrypt credentials for user={user_id}: {e}",
                    exc_info=True
                )

        # ✅ 6. 检查 API 配置状态
        gemini_api_configured = user_config.api_mode == 'gemini_api'
        vertex_ai_configured = (
            user_config.api_mode == 'vertex_ai' and
            bool(vertex_ai_project_id) and
            bool(vertex_ai_credentials_json)
        )

        logger.info(
            f"[ImagenConfig] Configuration retrieved: api_mode={user_config.api_mode}, "
            f"gemini_configured={gemini_api_configured}, "
            f"vertex_configured={vertex_ai_configured}"
        )

        return ImagenConfigResponse(
            api_mode=user_config.api_mode,
            capabilities=capabilities,
            gemini_api_configured=gemini_api_configured,
            vertex_ai_configured=vertex_ai_configured,
            vertex_ai_project_id=vertex_ai_project_id,
            vertex_ai_location=vertex_ai_location,
            vertex_ai_credentials_json=vertex_ai_credentials_json,
            hidden_models=user_config.hidden_models or [],
            saved_models=user_config.saved_models or []
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ImagenConfig] Failed to get configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Imagen configuration: {str(e)}"
        )


@router.post("/config")
async def update_imagen_config(
    request_body: ImagenConfigUpdateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Update Imagen API configuration for the authenticated user.
    
    Args:
        request_body: New configuration settings
    
    Returns:
        Success message and updated configuration
    """
    try:
        
        logger.info(
            f"[ImagenConfig] Updating configuration for user={user_id}, "
            f"api_mode={request_body.apiMode}"
        )
        
        # Validate configuration based on API mode
        if request_body.apiMode == 'gemini_api':
            # Gemini API mode uses the API key from ConfigProfile (LLM configuration)
            # No additional validation needed here
            pass
        elif request_body.apiMode == 'vertex_ai':
            if not request_body.vertexAiProjectId:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiProjectId is required for Vertex AI mode"
                )
            if not request_body.vertexAiCredentialsJson:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiCredentialsJson is required for Vertex AI mode"
                )
        
        # Query or create user configuration
        user_config = db.query(ImagenConfig).filter(ImagenConfig.user_id == user_id).first()
        
        if not user_config:
            # Create new configuration
            user_config = ImagenConfig(user_id=user_id)
            db.add(user_config)
        
        # Update configuration
        user_config.api_mode = request_body.apiMode
        
        if request_body.apiMode == 'vertex_ai':
            user_config.vertex_ai_project_id = request_body.vertexAiProjectId
            user_config.vertex_ai_location = request_body.vertexAiLocation or 'us-central1'
            
            # Encrypt credentials JSON before storing
            if request_body.vertexAiCredentialsJson:
                try:
                    encrypted_json = encrypt_data(request_body.vertexAiCredentialsJson)
                    user_config.vertex_ai_credentials_json = encrypted_json
                except Exception as e:
                    logger.error(f"[ImagenConfig] Failed to encrypt credentials: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to encrypt credentials"
                    )
            
            # Save model configurations (hidden_models and saved_models)
            # Always update these fields if provided (even if empty array)
            if hasattr(request_body, 'hiddenModels') and request_body.hiddenModels is not None:
                user_config.hidden_models = request_body.hiddenModels
                logger.info(
                    f"[ImagenConfig] Updated hidden_models for user={user_id}: {len(request_body.hiddenModels)} models"
                )
            elif request_body.apiMode == 'vertex_ai':
                # If not provided but in vertex_ai mode, initialize as empty array
                if user_config.hidden_models is None:
                    user_config.hidden_models = []
            
            if hasattr(request_body, 'savedModels') and request_body.savedModels is not None:
                user_config.saved_models = request_body.savedModels
                logger.info(
                    f"[ImagenConfig] Saved {len(request_body.savedModels)} model configurations for user={user_id}"
                )
            elif request_body.apiMode == 'vertex_ai':
                # If not provided but in vertex_ai mode, initialize as empty array
                if user_config.saved_models is None:
                    user_config.saved_models = []
        else:
            # Clear Vertex AI config when switching to Gemini API
            user_config.vertex_ai_project_id = None
            user_config.vertex_ai_location = 'us-central1'
            user_config.vertex_ai_credentials_json = None
            user_config.hidden_models = []
            user_config.saved_models = []
        
        # Commit to database
        db.commit()
        db.refresh(user_config)
        
        logger.info(
            f"[ImagenConfig] Configuration updated successfully: "
            f"api_mode={request_body.apiMode}, user={user_id}"
        )
        
        # Get updated configuration
        updated_config = await get_imagen_config(request, db)
        
        return {
            "success": True,
            "message": f"Imagen configuration updated to {request_body.apiMode} mode",
            "config": updated_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ImagenConfig] Failed to update configuration: {e}",
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update Imagen configuration: {str(e)}"
        )


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_imagen_connection(
    request_body: TestConnectionRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Test connection to Imagen API with provided credentials.

    架构说明：
    此端点直接使用 GeminiAPIImageGenerator/VertexAIImageGenerator 而非通过 GoogleService，
    因为测试的是用户提供的凭证（尚未存储到数据库），而不是已存储的凭证。
    这是配置验证功能，不同于执行业务操作的端点。

    Args:
        request_body: API credentials to test

    Returns:
        Connection test result with details
    """
    try:
        
        logger.info(
            f"[ImagenConfig] Testing connection for user={user_id}, "
            f"api_mode={request_body.apiMode}"
        )
        
        # Validate credentials based on API mode
        if request_body.apiMode == 'gemini_api':
            if not request_body.geminiApiKey:
                raise HTTPException(
                    status_code=400,
                    detail="geminiApiKey is required for testing Gemini API"
                )
        elif request_body.apiMode == 'vertex_ai':
            if not request_body.vertexAiProjectId:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiProjectId is required for testing Vertex AI"
                )
            if not request_body.vertexAiCredentialsJson:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiCredentialsJson is required for testing Vertex AI"
                )
        
        # Create temporary generator to test connection
        if request_body.apiMode == 'gemini_api':
            from ...services.gemini.imagen_gemini_api import GeminiAPIImageGenerator
            
            generator = GeminiAPIImageGenerator(
                api_key=request_body.geminiApiKey
            )
            
            # Test by getting supported models
            models = generator.get_supported_models()
            
            return TestConnectionResponse(
                success=True,
                api_mode='gemini_api',
                message="Successfully connected to Gemini API",
                details={
                    "supported_models": models,
                    "capabilities": generator.get_capabilities()
                }
            )
            
        else:  # vertex_ai
            from ...services.gemini.imagen_vertex_ai import VertexAIImageGenerator
            
            generator = VertexAIImageGenerator(
                project_id=request_body.vertexAiProjectId,
                location=request_body.vertexAiLocation,
                credentials_json=request_body.vertexAiCredentialsJson
            )
            
            # Test by getting supported models
            models = generator.get_supported_models()
            
            return TestConnectionResponse(
                success=True,
                api_mode='vertex_ai',
                message="Successfully connected to Vertex AI",
                details={
                    "project_id": request_body.vertexAiProjectId,
                    "location": request_body.vertexAiLocation,
                    "supported_models": models,
                    "capabilities": generator.get_capabilities()
                }
            )
        
    except HTTPException:
        raise
    except ConfigurationError as e:
        logger.warning(
            f"[ImagenConfig] Configuration error during connection test: {e}"
        )
        return TestConnectionResponse(
            success=False,
            api_mode=request_body.apiMode,
            message=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"[ImagenConfig] Connection test failed: {e}",
            exc_info=True
        )
        return TestConnectionResponse(
            success=False,
            api_mode=request_body.apiMode,
            message=f"Connection test failed: {str(e)}"
        )


@router.post("/verify-vertex-ai", response_model=VerifyVertexAIResponse)
async def verify_vertex_ai_connection(
    request_body: VerifyVertexAIRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify Vertex AI connection and list all available models.

    架构说明：
    此端点直接使用 genai.Client() 而非通过 GoogleService，
    因为测试的是用户提供的凭证（尚未存储到数据库），而不是已存储的凭证。
    这是配置验证功能，用于在保存配置前验证凭证有效性。

    This endpoint uses the Google GenAI SDK to list all models available
    in the specified Vertex AI project and location.

    Args:
        request_body: Vertex AI credentials (project ID, location, credentials JSON)
        request: FastAPI request object for user authentication
        db: Database session

    Returns:
        List of available models with their details
    """
    try:
        # user_id 已通过依赖注入自动获取
        
        logger.info(
            f"[ImagenConfig] Verifying Vertex AI connection: "
            f"project={request_body.projectId}, location={request_body.location}"
        )
        
        # Import Google GenAI SDK
        try:
            from google import genai
            import os
            import tempfile
            import json
        except ImportError as e:
            logger.error(f"[ImagenConfig] Failed to import Google GenAI SDK: {e}")
            raise HTTPException(
                status_code=500,
                detail="Google GenAI SDK not available"
            )
        
        # Create temporary credentials file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(request_body.credentialsJson)
            temp_credentials_path = temp_file.name
        
        try:
            # Set environment variables for Vertex AI
            os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
            os.environ['GOOGLE_CLOUD_PROJECT'] = request_body.projectId
            os.environ['GOOGLE_CLOUD_LOCATION'] = request_body.location
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
            
            # Initialize client
            client = genai.Client()
            
            # List all models
            models_list = client.models.list()
            
            # Convert to response format
            models = []
            for model in models_list:
                model_name = model.name if hasattr(model, 'name') else str(model)
                display_name = model.display_name if hasattr(model, 'display_name') else model_name
                
                models.append(VertexAIModel(
                    id=model_name,
                    name=model_name,
                    display_name=display_name
                ))
            
            logger.info(
                f"[ImagenConfig] Successfully listed {len(models)} models from Vertex AI"
            )
            
            return VerifyVertexAIResponse(
                success=True,
                message=f"Successfully connected to Vertex AI. Found {len(models)} models.",
                models=models
            )
            
        finally:
            # Clean up temporary credentials file
            try:
                os.unlink(temp_credentials_path)
            except Exception as e:
                logger.warning(f"[ImagenConfig] Failed to delete temp credentials file: {e}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ImagenConfig] Vertex AI verification failed: {e}",
            exc_info=True
        )
        return VerifyVertexAIResponse(
            success=False,
            message=f"Verification failed: {str(e)}",
            models=[]
        )
