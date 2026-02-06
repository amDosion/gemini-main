"""
Vertex AI Configuration API Router

This module provides API endpoints for managing Vertex AI configuration,
including switching between Gemini API and Vertex AI, testing connections,
and retrieving capabilities.

架构说明：
- GET /config: 通过 ProviderFactory.create("google") 获取 GoogleService，调用 get_imagen_capabilities()
- POST /config: 直接操作数据库配置（不需要 GoogleService）
- POST /test-connection: 直接使用子服务测试（因为测试的是用户提供的凭证，不是存储的凭证）
- POST /verify-vertex-ai: 直接使用 genai.Client（同上，测试用户提供的凭证）

Updated: 2026-01-15 - 重命名为 vertex_ai_config，数据表名称改为 vertex_ai_configs
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any, List
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.encryption import encrypt_data, decrypt_data, is_encrypted
from ...models.db_models import VertexAIConfig, ConfigProfile, UserSettings
from ...services.common.provider_factory import ProviderFactory
from ...services.gemini.base.imagen_common import ConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vertex-ai", tags=["vertex-ai"])


# ============================================
# 静态模型列表 - 这些模型可能不在 Vertex AI API 返回中，但确实存在
# ============================================
STATIC_VERTEX_AI_MODELS: List[str] = [
    # Imagen 图像生成模型
    "imagen-3.0-generate-001",
    "imagen-3.0-generate-002",
    "imagen-3.0-fast-generate-001",
    "imagen-4.0-generate-preview-05-20",
    "imagen-4.0-ultra-generate-preview-05-20",

    # Imagen 图像编辑模型
    "imagen-3.0-capability-001",
    "imagen-4.0-ingredients-preview",

    # Imagen Upscale 模型
    "imagen-4.0-upscale-preview",

    # 图像分割模型
    "image-segmentation-001",

    # 虚拟试衣模型
    "virtual-try-on-001",
    "virtual-try-on-preview-08-04",

    # 产品重构模型
    "imagen-product-recontext-preview-06-30",

    # Veo 视频生成模型
    "veo-2.0-generate-001",
    "veo-3.0-generate-preview",
    "veo-3.0-fast-generate-preview",
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
]


# ==================== Request/Response Models ====================

class VertexAIConfigResponse(BaseModel):
    """Response model for Vertex AI configuration"""
    api_mode: Literal['gemini_api', 'vertex_ai']
    capabilities: Dict[str, Any]
    gemini_api_configured: bool
    vertex_ai_configured: bool
    vertex_ai_project_id: Optional[str] = None
    vertex_ai_location: Optional[str] = 'us-central1'
    vertex_ai_credentials_json: Optional[str] = None
    hidden_models: List[str] = Field(default_factory=list)
    saved_models: List[Dict[str, Any]] = Field(default_factory=list)


class VertexAIConfigUpdateRequest(BaseModel):
    """Request model for updating Vertex AI configuration"""
    api_mode: Literal['gemini_api', 'vertex_ai'] = Field(
        description="API mode to use for image generation"
    )

    # Gemini API config (optional, uses LLM API key if not provided)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Gemini API key (optional, uses LLM config if not provided)"
    )

    # Vertex AI config
    vertex_ai_project_id: Optional[str] = Field(
        default=None,
        description="Google Cloud project ID (required for vertex_ai mode)"
    )
    vertex_ai_location: Optional[str] = Field(
        default='us-central1',
        description="Vertex AI location/region"
    )
    vertex_ai_credentials_json: Optional[str] = Field(
        default=None,
        description="Service account credentials JSON content (required for vertex_ai mode)"
    )
    hidden_models: Optional[List[str]] = Field(
        default=None,
        description="List of hidden model IDs"
    )
    saved_models: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of saved model configurations (ModelConfig[])"
    )


class TestConnectionRequest(BaseModel):
    """Request model for testing API connection"""
    api_mode: Literal['gemini_api', 'vertex_ai']

    # Gemini API credentials
    gemini_api_key: Optional[str] = None

    # Vertex AI credentials
    vertex_ai_project_id: Optional[str] = None
    vertex_ai_location: Optional[str] = 'us-central1'
    vertex_ai_credentials_json: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """Response model for connection test"""
    success: bool
    api_mode: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ModelCapabilities(BaseModel):
    """Model capabilities for display"""
    vision: bool = False
    search: bool = False
    reasoning: bool = False
    coding: bool = False
    
    class Config:
        populate_by_name = True


class VertexAIModel(BaseModel):
    """Model information from Vertex AI"""
    id: str
    name: str
    display_name: Optional[str] = Field(default=None, alias='displayName')
    description: Optional[str] = Field(default=None, description="Model description")
    capabilities: Optional[ModelCapabilities] = Field(default=None, description="Model capabilities (vision, search, reasoning, coding)")
    
    class Config:
        populate_by_name = True


class VerifyVertexAIRequest(BaseModel):
    """Request model for verifying Vertex AI connection and listing models"""
    project_id: str
    location: str = 'us-central1'
    credentials_json: str


class VerifyVertexAIResponse(BaseModel):
    """Response model for Vertex AI verification"""
    success: bool
    message: str
    models: List[VertexAIModel] = []


# ==================== Helper Functions ====================

async def _get_google_api_key(db: Session, user_id: str) -> Optional[str]:
    """
    Get Google API Key from database for the user (自动解密).

    Priority:
    1. Active profile's API key
    2. Any Google profile's API key

    Returns:
        Decrypted API key string or None if not found
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
                # 自动解密 API key（用于业务逻辑使用）
                try:
                    if is_encrypted(api_key):
                        return decrypt_data(api_key, silent=True)
                    else:
                        return api_key
                except Exception as e:
                    logger.warning(f"[VertexAIConfig] Failed to decrypt API key: {e}")
                    # 解密失败时返回原值（可能是旧数据）
                    return api_key

    # Fallback: first matching profile
    for profile in matching_profiles:
        if profile.api_key:
            api_key = profile.api_key
            # 自动解密 API key（用于业务逻辑使用）
            try:
                if is_encrypted(api_key):
                    return decrypt_data(api_key, silent=True)
                else:
                    return api_key
            except Exception as e:
                logger.warning(f"[VertexAIConfig] Failed to decrypt API key: {e}")
                # 解密失败时返回原值（可能是旧数据）
                return api_key

    return None


# ==================== API Endpoints ====================

@router.get("/config", response_model=VertexAIConfigResponse, response_model_by_alias=True)
async def get_vertex_ai_config(
    edit_mode: bool = False,  # 编辑模式：True 时解密返回，False 时返回加密值
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current Vertex AI configuration and capabilities for the authenticated user.

    通过 ProviderFactory.create("google") 获取 GoogleService，调用 get_imagen_capabilities()

    Returns:
        Current API mode, capabilities, and configuration status
    """
    try:
        # user_id 已通过依赖注入自动获取

        logger.info(f"[VertexAIConfig] Getting configuration for user={user_id}")

        # ✅ 2. 查询用户的 Vertex AI 配置
        user_config = db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()

        # Default capabilities (used when no config or no API key)
        default_capabilities = {
            "supported_models": ["imagen-3.0-generate-001"],
            "max_images": 8,
            "supported_aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "person_generation_modes": ["dont_allow", "allow_adult"]
        }

        if not user_config:
            # Return default configuration if user hasn't set up yet
            logger.info(f"[VertexAIConfig] No configuration found for user={user_id}, returning defaults")
            return VertexAIConfigResponse(
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

        # ✅ 3. 获取 Google API Key（自动解密）
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
                logger.info(f"[VertexAIConfig] Got capabilities via GoogleService for user={user_id}")
            except Exception as e:
                logger.warning(
                    f"[VertexAIConfig] Failed to get capabilities via GoogleService, using defaults: {e}"
                )

        # ✅ 5. 处理 Vertex AI 配置
        vertex_ai_project_id = user_config.vertex_ai_project_id
        vertex_ai_location = user_config.vertex_ai_location or 'us-central1'
        
        # 根据 edit_mode 决定是否解密
        if edit_mode and user_config.vertex_ai_credentials_json:
            # 编辑模式：解密返回给前端
            try:
                if is_encrypted(user_config.vertex_ai_credentials_json):
                    vertex_ai_credentials_json = decrypt_data(user_config.vertex_ai_credentials_json)
                    logger.debug(f"[VertexAIConfig] Decrypted credentials for edit mode (user={user_id})")
                else:
                    # 如果未加密（旧数据），直接返回
                    vertex_ai_credentials_json = user_config.vertex_ai_credentials_json
            except Exception as e:
                logger.warning(f"[VertexAIConfig] Failed to decrypt credentials in edit mode: {e}")
                # 解密失败时返回加密值（前端可以显示错误）
                vertex_ai_credentials_json = user_config.vertex_ai_credentials_json
        else:
            # 非编辑模式：返回加密值（或 None）
            vertex_ai_credentials_json = user_config.vertex_ai_credentials_json

        # ✅ 6. 检查 API 配置状态
        gemini_api_configured = user_config.api_mode == 'gemini_api'
        vertex_ai_configured = (
            user_config.api_mode == 'vertex_ai' and
            bool(vertex_ai_project_id) and
            bool(vertex_ai_credentials_json)
        )

        logger.info(
            f"[VertexAIConfig] Configuration retrieved: api_mode={user_config.api_mode}, "
            f"gemini_configured={gemini_api_configured}, "
            f"vertex_configured={vertex_ai_configured}"
        )

        # ✅ 读取时也检查并补充描述（处理旧数据）
        saved_models = user_config.saved_models or []
        if saved_models:
            from ...services.common.model_capabilities import get_model_description
            enriched_saved_models = []
            for model_data in saved_models:
                if isinstance(model_data, dict):
                    model_id = model_data.get('id', '')
                    name = model_data.get('name', model_id)
                    description = model_data.get('description', '')
                    
                    # ✅ 如果 description 缺失或和 name 一样，补充描述
                    if not description or description == name or description == f'Model: {model_id}':
                        try:
                            model_data = model_data.copy()  # 避免修改原数据
                            model_data['description'] = get_model_description('google', model_id)
                            logger.debug(f"[VertexAIConfig] Enriched description for {model_id} during read")
                        except Exception as e:
                            logger.warning(f"[VertexAIConfig] Failed to enrich description for {model_id} during read: {e}")
                    
                    enriched_saved_models.append(model_data)
                else:
                    enriched_saved_models.append(model_data)
            
            saved_models = enriched_saved_models

        return VertexAIConfigResponse(
            api_mode=user_config.api_mode,
            capabilities=capabilities,
            gemini_api_configured=gemini_api_configured,
            vertex_ai_configured=vertex_ai_configured,
            vertex_ai_project_id=vertex_ai_project_id,
            vertex_ai_location=vertex_ai_location,
            vertex_ai_credentials_json=vertex_ai_credentials_json,
            hidden_models=user_config.hidden_models or [],
            saved_models=saved_models  # ✅ 使用补充后的 saved_models
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[VertexAIConfig] Failed to get configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Vertex AI configuration: {str(e)}"
        )


@router.post("/config")
async def update_vertex_ai_config(
    request_body: VertexAIConfigUpdateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Update Vertex AI configuration for the authenticated user.
    
    Args:
        request_body: New configuration settings
    
    Returns:
        Success message and updated configuration
    """
    try:
        
        logger.info(
            f"[VertexAIConfig] Updating configuration for user={user_id}, "
            f"api_mode={request_body.api_mode}"
        )

        # ✅ 调试日志：检查接收到的数据
        logger.info(
            f"[VertexAIConfig] Request data: "
            f"hidden_models={len(request_body.hidden_models) if request_body.hidden_models else 0}, "
            f"saved_models={len(request_body.saved_models) if request_body.saved_models else 0}"
        )
        
        # Validate configuration based on API mode
        if request_body.api_mode == 'gemini_api':
            # Gemini API mode uses the API key from ConfigProfile (LLM configuration)
            # No additional validation needed here
            pass
        elif request_body.api_mode == 'vertex_ai':
            if not request_body.vertex_ai_project_id:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiProjectId is required for Vertex AI mode"
                )
            if not request_body.vertex_ai_credentials_json:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiCredentialsJson is required for Vertex AI mode"
                )
        
        # Query or create user configuration
        user_config = db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()
        
        if not user_config:
            # Create new configuration
            user_config = VertexAIConfig(user_id=user_id)
            db.add(user_config)
        
        # Update configuration
        user_config.api_mode = request_body.api_mode
        
        if request_body.api_mode == 'vertex_ai':
            user_config.vertex_ai_project_id = request_body.vertex_ai_project_id
            user_config.vertex_ai_location = request_body.vertex_ai_location or 'us-central1'
            
            # 保存 credentials JSON（加密存储）
            if request_body.vertex_ai_credentials_json:
                # 判断是否已经是加密的
                if is_encrypted(request_body.vertex_ai_credentials_json):
                    # 如果已经是加密的，可能是前端传递回来的加密值（用户没有修改）
                    # 检查是否与数据库中的值相同
                    existing_encrypted = user_config.vertex_ai_credentials_json
                    if existing_encrypted == request_body.vertex_ai_credentials_json:
                        # 用户没有修改凭证，保持加密状态
                        logger.debug(f"[VertexAIConfig] Credentials unchanged, keeping encrypted value (user={user_id})")
                        # 不需要更新，保持原值
                    else:
                        # 不同的加密值，直接保存（可能是从其他地方传递的加密值）
                        user_config.vertex_ai_credentials_json = request_body.vertex_ai_credentials_json
                        logger.debug(f"[VertexAIConfig] Saved encrypted credentials (different encrypted value) (user={user_id})")
                else:
                    # 明文凭证（用户输入的新凭证或修改过的凭证），加密后保存
                    try:
                        # 先检查是否与数据库中解密后的值相同（避免不必要的加密操作）
                        existing_encrypted = user_config.vertex_ai_credentials_json
                        if existing_encrypted:
                            try:
                                if is_encrypted(existing_encrypted):
                                    existing_decrypted = decrypt_data(existing_encrypted, silent=True)
                                    if existing_decrypted == request_body.vertex_ai_credentials_json:
                                        # 用户没有修改凭证，保持加密状态
                                        logger.debug(f"[VertexAIConfig] Credentials unchanged (decrypted comparison), keeping encrypted value (user={user_id})")
                                        # 不需要更新，保持原值
                                    else:
                                        # 新的凭证，加密后保存
                                        encrypted_credentials = encrypt_data(request_body.vertex_ai_credentials_json)
                                        user_config.vertex_ai_credentials_json = encrypted_credentials
                                        logger.info(f"[VertexAIConfig] Encrypted and saved new credentials (user={user_id})")
                                else:
                                    # 数据库中是明文（旧数据），加密后保存
                                    encrypted_credentials = encrypt_data(request_body.vertex_ai_credentials_json)
                                    user_config.vertex_ai_credentials_json = encrypted_credentials
                                    logger.info(f"[VertexAIConfig] Encrypted and saved credentials (migrated from plaintext) (user={user_id})")
                            except Exception as e:
                                # 解密失败，可能是密钥不匹配，当作新凭证处理
                                logger.warning(f"[VertexAIConfig] Failed to decrypt existing credentials for comparison: {e}")
                                encrypted_credentials = encrypt_data(request_body.vertex_ai_credentials_json)
                                user_config.vertex_ai_credentials_json = encrypted_credentials
                                logger.info(f"[VertexAIConfig] Encrypted and saved new credentials (decryption failed) (user={user_id})")
                        else:
                            # 数据库中没有凭证，加密后保存
                            encrypted_credentials = encrypt_data(request_body.vertex_ai_credentials_json)
                            user_config.vertex_ai_credentials_json = encrypted_credentials
                            logger.info(f"[VertexAIConfig] Encrypted and saved new credentials (first time) (user={user_id})")
                    except Exception as e:
                        logger.error(f"[VertexAIConfig] Failed to encrypt credentials: {e}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to encrypt credentials: {str(e)}"
                        )
            
            # Save model configurations (hidden_models and saved_models)
            # Always update these fields if provided (even if empty array)
            # ✅ 修复：Pydantic 使用 snake_case，不是 camelCase
            if request_body.hidden_models is not None:
                user_config.hidden_models = request_body.hidden_models
                logger.info(
                    f"[VertexAIConfig] Updated hidden_models for user={user_id}: {len(request_body.hidden_models)} models"
                )
            elif request_body.api_mode == 'vertex_ai':
                # If not provided but in vertex_ai mode, initialize as empty array
                if user_config.hidden_models is None:
                    user_config.hidden_models = []

            if request_body.saved_models is not None:
                # ✅ 确保保存的模型包含完整的能力信息和描述
                # 如果前端传递的模型缺少 capabilities 或 description，从 model_capabilities 获取
                from ...services.common.model_capabilities import get_google_capabilities, build_model_config, get_model_description
                
                enriched_saved_models = []
                for model_data in request_body.saved_models:
                    # 如果已经是完整的 ModelConfig 格式（包含 capabilities），直接使用
                    if isinstance(model_data, dict) and 'capabilities' in model_data:
                        model_id = model_data.get('id', '')
                        
                        # 检查 capabilities 是否全部为 False（可能是前端默认值）
                        caps = model_data.get('capabilities', {})
                        if not any([caps.get('vision', False), caps.get('search', False), 
                                   caps.get('reasoning', False), caps.get('coding', False)]):
                            # 如果全部为 False，尝试从 model_capabilities 获取真实能力
                            try:
                                model_caps = get_google_capabilities(model_id)
                                model_data['capabilities'] = {
                                    'vision': model_caps.vision,
                                    'search': model_caps.search,
                                    'reasoning': model_caps.reasoning,
                                    'coding': model_caps.coding
                                }
                                logger.debug(f"[VertexAIConfig] Enriched capabilities for {model_id}")
                            except Exception as e:
                                logger.warning(f"[VertexAIConfig] Failed to enrich capabilities for {model_id}: {e}")
                        
                        # ✅ 检查 description 是否和 name 一样，如果是，生成更好的描述
                        description = model_data.get('description', '')
                        name = model_data.get('name', model_id)
                        if not description or description == name or description == f'Model: {model_id}':
                            try:
                                model_data['description'] = get_model_description('google', model_id)
                                logger.debug(f"[VertexAIConfig] Enriched description for {model_id}")
                            except Exception as e:
                                logger.warning(f"[VertexAIConfig] Failed to enrich description for {model_id}: {e}")
                        
                        enriched_saved_models.append(model_data)
                    else:
                        # 如果是简单格式，构建完整的 ModelConfig
                        model_id = model_data.get('id') if isinstance(model_data, dict) else str(model_data)
                        try:
                            model_config = build_model_config('google', model_id)
                            enriched_saved_models.append({
                                'id': model_config.id,
                                'name': model_config.name,
                                'description': model_config.description,  # ✅ 使用生成的描述
                                'capabilities': {
                                    'vision': model_config.capabilities.vision,
                                    'search': model_config.capabilities.search,
                                    'reasoning': model_config.capabilities.reasoning,
                                    'coding': model_config.capabilities.coding
                                },
                                'contextWindow': model_config.context_window
                            })
                        except Exception as e:
                            logger.warning(f"[VertexAIConfig] Failed to build model config for {model_id}: {e}")
                            # Fallback: 使用原始数据，但添加默认 capabilities 和描述
                            if isinstance(model_data, dict):
                                model_data['capabilities'] = model_data.get('capabilities', {
                                    'vision': False,
                                    'search': False,
                                    'reasoning': False,
                                    'coding': False
                                })
                                # ✅ 如果没有描述或描述和 name 一样，生成描述
                                if not model_data.get('description') or model_data.get('description') == model_data.get('name', model_id):
                                    try:
                                        model_data['description'] = get_model_description('google', model_id)
                                    except:
                                        model_data['description'] = f'Google AI model: {model_id}'
                                enriched_saved_models.append(model_data)
                            else:
                                try:
                                    desc = get_model_description('google', model_id)
                                except:
                                    desc = f'Google AI model: {model_id}'
                                enriched_saved_models.append({
                                    'id': model_id,
                                    'name': model_id,
                                    'description': desc,
                                    'capabilities': {
                                        'vision': False,
                                        'search': False,
                                        'reasoning': False,
                                        'coding': False
                                    }
                                })
                
                user_config.saved_models = enriched_saved_models
                logger.info(
                    f"[VertexAIConfig] Saved {len(enriched_saved_models)} model configurations with capabilities for user={user_id}"
                )
            elif request_body.api_mode == 'vertex_ai':
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
            f"[VertexAIConfig] Configuration updated successfully: "
            f"api_mode={request_body.api_mode}, user={user_id}"
        )
        
        # Build response with updated configuration
        # Get capabilities (reuse logic from get_vertex_ai_config)
        # ✅ 注意：数据库事务已在上面提交，这里直接获取 capabilities
        
        default_capabilities = {
            "supported_models": ["imagen-3.0-generate-001"],
            "max_images": 8,
            "supported_aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "person_generation_modes": ["dont_allow", "allow_adult"]
        }
        
        capabilities = default_capabilities
        api_key = await _get_google_api_key(db, user_id)
        if api_key:
            try:
                # ✅ 创建新的 GoogleService 实例，确保使用最新的配置
                # 注意：ImageGenerator 内部的 ImagenCoordinator 会从数据库重新加载配置
                service = ProviderFactory.create(
                    provider="google",
                    api_key=api_key,
                    user_id=user_id,
                    db=db
                )
                
                # ✅ 如果 ImageGenerator 有 reload_config 方法，调用它以确保使用最新配置
                if hasattr(service, 'image_generator') and hasattr(service.image_generator, '_coordinator'):
                    coordinator = service.image_generator._coordinator
                    if hasattr(coordinator, 'reload_config'):
                        logger.info(f"[VertexAIConfig] Reloading ImagenCoordinator config for user={user_id}")
                        coordinator.reload_config()
                
                capabilities = service.get_imagen_capabilities()
                logger.info(f"[VertexAIConfig] Got capabilities after config update: supported_models={len(capabilities.get('supported_models', []))}")
            except Exception as e:
                logger.warning(f"[VertexAIConfig] Failed to get capabilities, using defaults: {e}")
        
        # Build updated config response
        # 注意：update 后返回时，应该返回加密值（非编辑模式），因为这是保存后的响应
        # 如果前端需要编辑，应该再次调用 get_vertex_ai_config(edit_mode=True)
        updated_config = VertexAIConfigResponse(
            api_mode=user_config.api_mode,
            capabilities=capabilities,
            gemini_api_configured=user_config.api_mode == 'gemini_api',
            vertex_ai_configured=(
                user_config.api_mode == 'vertex_ai' and
                bool(user_config.vertex_ai_project_id) and
                bool(user_config.vertex_ai_credentials_json)
            ),
            vertex_ai_project_id=user_config.vertex_ai_project_id,
            vertex_ai_location=user_config.vertex_ai_location or 'us-central1',
            # 返回加密值（非编辑模式），前端如果需要编辑应该再次调用 get_vertex_ai_config(edit_mode=True)
            vertex_ai_credentials_json=user_config.vertex_ai_credentials_json,
            hidden_models=user_config.hidden_models or [],
            saved_models=user_config.saved_models or []
        )
        
        return {
            "success": True,
            "message": f"Vertex AI configuration updated to {request_body.api_mode} mode",
            "config": updated_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[VertexAIConfig] Failed to update configuration: {e}",
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update Vertex AI configuration: {str(e)}"
        )


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_vertex_ai_connection(
    request_body: TestConnectionRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Test connection to Vertex AI API with provided credentials.

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
            f"[VertexAIConfig] Testing connection for user={user_id}, "
            f"api_mode={request_body.api_mode}"
        )
        
        # Validate credentials based on API mode
        if request_body.api_mode == 'gemini_api':
            if not request_body.gemini_api_key:
                raise HTTPException(
                    status_code=400,
                    detail="geminiApiKey is required for testing Gemini API"
                )
        elif request_body.api_mode == 'vertex_ai':
            if not request_body.vertex_ai_project_id:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiProjectId is required for testing Vertex AI"
                )
            if not request_body.vertex_ai_credentials_json:
                raise HTTPException(
                    status_code=400,
                    detail="vertexAiCredentialsJson is required for testing Vertex AI"
                )
        
        # Create temporary generator to test connection
        if request_body.api_mode == 'gemini_api':
            from ...services.gemini.imagen_gemini_api import GeminiAPIImageGenerator
            
            generator = GeminiAPIImageGenerator(
                api_key=request_body.gemini_api_key
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
                project_id=request_body.vertex_ai_project_id,
                location=request_body.vertex_ai_location,
                credentials_json=request_body.vertex_ai_credentials_json
            )
            
            # Test by getting supported models
            models = generator.get_supported_models()
            
            return TestConnectionResponse(
                success=True,
                api_mode='vertex_ai',
                message="Successfully connected to Vertex AI",
                details={
                    "project_id": request_body.vertex_ai_project_id,
                    "location": request_body.vertex_ai_location,
                    "supported_models": models,
                    "capabilities": generator.get_capabilities()
                }
            )
        
    except HTTPException:
        raise
    except ConfigurationError as e:
        logger.warning(
            f"[VertexAIConfig] Configuration error during connection test: {e}"
        )
        return TestConnectionResponse(
            success=False,
            api_mode=request_body.api_mode,
            message=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"[VertexAIConfig] Connection test failed: {e}",
            exc_info=True
        )
        return TestConnectionResponse(
            success=False,
            api_mode=request_body.api_mode,
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
            f"[VertexAIConfig] Verifying Vertex AI connection: "
            f"project={request_body.project_id}, location={request_body.location}"
        )
        
        # Import Google GenAI SDK
        try:
            from google import genai
            import os
            import tempfile
            import json
        except ImportError as e:
            logger.error(f"[VertexAIConfig] Failed to import Google GenAI SDK: {e}")
            raise HTTPException(
                status_code=500,
                detail="Google GenAI SDK not available"
            )
        
        # 直接使用 credentials JSON（测试时使用明文）
        credentials_json_to_use = request_body.credentials_json
        
        # Create temporary credentials file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(credentials_json_to_use)
            temp_credentials_path = temp_file.name
        
        try:
            # Set environment variables for Vertex AI
            os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
            os.environ['GOOGLE_CLOUD_PROJECT'] = request_body.project_id
            os.environ['GOOGLE_CLOUD_LOCATION'] = request_body.location
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_credentials_path
            
            # Initialize client
            client = genai.Client()
            
            # ✅ List all models - 直接调用 API，不使用缓存，确保获取最新数据
            # 注意：genai.Client().models.list() 是实时调用 Vertex AI API，不涉及缓存
            models_list = client.models.list()
            
            # Import model capabilities and description functions
            from ...services.common.model_capabilities import get_google_capabilities, get_model_description
            
            # Convert to response format with capabilities and description
            models = []
            seen_model_ids: set = set()  # 用于去重

            for model in models_list:
                model_name = model.name if hasattr(model, 'name') else str(model)
                display_name = model.display_name if hasattr(model, 'display_name') else model_name

                # Extract short model ID for capability lookup
                # e.g., "publishers/google/models/gemini-3-pro-image-preview" -> "gemini-3-pro-image-preview"
                short_model_id = model_name.split('/')[-1] if '/' in model_name else model_name

                # 跳过已存在的模型
                if short_model_id in seen_model_ids:
                    continue
                seen_model_ids.add(short_model_id)

                # Get model capabilities
                try:
                    caps = get_google_capabilities(short_model_id)
                    capabilities = ModelCapabilities(
                        vision=caps.vision,
                        search=caps.search,
                        reasoning=caps.reasoning,
                        coding=caps.coding
                    )
                except Exception as e:
                    logger.warning(f"[VertexAIConfig] Failed to get capabilities for {short_model_id}: {e}")
                    capabilities = ModelCapabilities()  # Default: all False

                # ✅ Get model description
                try:
                    description = get_model_description('google', short_model_id)
                except Exception as e:
                    logger.warning(f"[VertexAIConfig] Failed to get description for {short_model_id}: {e}")
                    description = None  # Will use default in frontend

                models.append(VertexAIModel(
                    id=model_name,
                    name=model_name,
                    display_name=display_name,
                    description=description,  # ✅ Include description
                    capabilities=capabilities
                ))

            api_model_count = len(models)

            # ✅ 合并静态模型列表（避免重复）
            static_added = 0
            for static_model_id in STATIC_VERTEX_AI_MODELS:
                if static_model_id in seen_model_ids:
                    continue
                seen_model_ids.add(static_model_id)

                try:
                    caps = get_google_capabilities(static_model_id)
                    capabilities = ModelCapabilities(
                        vision=caps.vision,
                        search=caps.search,
                        reasoning=caps.reasoning,
                        coding=caps.coding
                    )
                except Exception as e:
                    logger.warning(f"[VertexAIConfig] Failed to get capabilities for static model {static_model_id}: {e}")
                    capabilities = ModelCapabilities()

                try:
                    description = get_model_description('google', static_model_id)
                except Exception as e:
                    logger.warning(f"[VertexAIConfig] Failed to get description for static model {static_model_id}: {e}")
                    description = None

                models.append(VertexAIModel(
                    id=static_model_id,
                    name=static_model_id,
                    display_name=static_model_id,
                    description=description,
                    capabilities=capabilities
                ))
                static_added += 1

            logger.info(
                f"[VertexAIConfig] Successfully listed {len(models)} models "
                f"({api_model_count} from API + {static_added} static)"
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
                logger.warning(f"[VertexAIConfig] Failed to delete temp credentials file: {e}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[VertexAIConfig] Vertex AI verification failed: {e}",
            exc_info=True
        )
        return VerifyVertexAIResponse(
            success=False,
            message=f"Verification failed: {str(e)}",
            models=[]
        )
