"""
Generate API Router

This module provides generation API endpoints for all AI providers.
It handles image generation, video generation, and speech generation.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ...core.database import get_db
from ...services.gemini.image_generator import ContentPolicyError
from ...services.gemini.image_edit_common import NotSupportedError
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
        logger.warning(f"[Generate] API key decryption failed: {e}")
        return api_key

router = APIRouter(prefix="/api/generate", tags=["generate"])


# ==================== Request Models ====================

class Attachment(BaseModel):
    """Attachment model (reference images, etc.)"""
    id: str
    mimeType: str
    name: str
    url: Optional[str] = None
    tempUrl: Optional[str] = None
    fileUri: Optional[str] = None


class GenerateOptions(BaseModel):
    """Generation options"""
    # Image size and quality options
    size: Optional[str] = None  # Image size (e.g., '1024x1024')
    quality: Optional[str] = None  # Image quality ('standard', 'hd')
    style: Optional[str] = None  # Image style ('vivid', 'natural')

    # Number of images to generate
    n: Optional[int] = 1  # Legacy: Number of images (OpenAI style)
    numberOfImages: Optional[int] = None  # Frontend style: Number of images

    # Aspect ratio options
    aspectRatio: Optional[str] = None  # Legacy: Aspect ratio ('1:1', '16:9', etc.)
    imageAspectRatio: Optional[str] = None  # Frontend style: Aspect ratio

    # API configuration
    baseUrl: Optional[str] = None  # Custom API URL

    # Other chat options that might be passed through
    enableSearch: Optional[bool] = None
    enableThinking: Optional[bool] = None
    enableCodeExecution: Optional[bool] = None
    enableUrlContext: Optional[bool] = None
    googleCacheMode: Optional[str] = None
    imageResolution: Optional[str] = None
    imageStyle: Optional[str] = None
    voiceName: Optional[str] = None

    # ✅ NEW: Imagen-specific advanced parameters
    negativePrompt: Optional[str] = None  # What to avoid in the image
    guidanceScale: Optional[float] = None  # Guidance strength (1.0-20.0)
    seed: Optional[int] = None  # Random seed for reproducible generation
    personGeneration: Optional[str] = None  # Person generation setting
    outputMimeType: Optional[str] = None  # Output format ('image/jpeg', 'image/png')
    outputCompressionQuality: Optional[int] = None  # JPEG compression quality (1-100)
    enhancePrompt: Optional[bool] = None  # Let AI improve the prompt



class ImageGenerateRequest(BaseModel):
    """Image generation request"""
    modelId: str
    prompt: str
    referenceImages: Optional[List[Attachment]] = None
    options: Optional[GenerateOptions] = None
    apiKey: Optional[str] = None  # Optional, will try to get from database/env


class ImageEditRequest(BaseModel):
    """Image editing request"""
    modelId: str
    prompt: str
    referenceImages: Dict[str, Any]  # {'raw': 'base64...', 'mask': 'base64...', ...}
    mode: Optional[str] = None  # 编辑模式：'image-chat-edit', 'image-mask-edit', 'image-inpainting', etc.
    options: Optional[Dict[str, Any]] = None  # edit_mode, number_of_images, aspect_ratio, etc.


class VideoGenerateRequest(BaseModel):
    """Video generation request"""
    modelId: Optional[str] = None
    prompt: str
    referenceImages: Optional[List[Attachment]] = None
    options: Optional[GenerateOptions] = None
    apiKey: Optional[str] = None


class SpeechGenerateRequest(BaseModel):
    """Speech generation request"""
    text: str
    voiceName: str
    apiKey: Optional[str] = None
    baseUrl: Optional[str] = None


# ==================== Helper Functions ====================

async def get_api_key(provider: str, request_api_key: Optional[str], user_id: str, db: Session) -> str:
    """
    Get API key for the provider.

    Priority:
    1. API key from request body
    2. API key from database (ConfigProfile table) - filtered by user_id
    3. API key from environment variables

    Args:
        provider: Provider name (e.g., "google", "openai")
        request_api_key: API key from request body (optional)
        user_id: User ID for user-scoped credential retrieval
        db: Database session

    Returns:
        API key string

    Raises:
        HTTPException: If no API key is found
    """
    # 1. Try request body
    if request_api_key:
        logger.info(f"[Generate] Using API key from request body for provider={provider}, user={user_id}")
        return request_api_key

    # 2. Try database (ConfigProfile table) - filter by BOTH provider_id AND user_id
    try:
        from ...models.db_models import ConfigProfile

        profile = db.query(ConfigProfile).filter(
            ConfigProfile.provider_id == provider,
            ConfigProfile.user_id == user_id
        ).first()

        if profile and profile.api_key:
            logger.info(f"[Generate] Using API key from database for provider={provider}, user={user_id}")
            return _decrypt_api_key(profile.api_key)
    except Exception as e:
        logger.warning(f"[Generate] Failed to get API key from database for provider={provider}, user={user_id}: {e}")

    # 3. Try environment variables
    import os
    env_key_map = {
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "tongyi": "DASHSCOPE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
        "zhipu": "ZHIPU_API_KEY",
    }

    env_key = env_key_map.get(provider)
    if env_key:
        api_key = os.getenv(env_key)
        if api_key:
            logger.info(f"[Generate] Using API key from environment variable {env_key} for provider={provider}, user={user_id}")
            return api_key

    raise HTTPException(
        status_code=401,
        detail=f"API Key not found for provider: {provider}. User: {user_id}. "
               f"Please configure it in provider settings or environment variables."
    )


# ==================== API Endpoints ====================

@router.post("/{provider}/image")
async def generate_image(
    provider: str,
    request_body: ImageGenerateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Image generation API endpoint for all providers.

    Supports providers: openai (DALL-E), google (Imagen), tongyi (Wanx), etc.
    """
    try:
        # ✅ Authenticate user
        from ...core.user_context import require_user_id
        user_id = require_user_id(request)

        logger.info(
            f"[Generate] ==================== Image Generation Request ===================="
        )
        logger.info(
            f"[Generate] Provider: {provider}"
        )
        logger.info(
            f"[Generate] User ID: {user_id}"
        )
        logger.info(
            f"[Generate] Model: {request_body.modelId}"
        )
        logger.info(
            f"[Generate] Prompt: {request_body.prompt[:100]}{'...' if len(request_body.prompt) > 100 else ''}"
        )
        logger.info(
            f"[Generate] Reference Images Count: {len(request_body.referenceImages) if request_body.referenceImages else 0}"
        )

        # 记录原始请求选项
        if request_body.options:
            logger.info(
                f"[Generate] Raw Request Options: {{"
                f"numberOfImages={request_body.options.numberOfImages}, "
                f"n={request_body.options.n}, "
                f"aspectRatio={request_body.options.aspectRatio}, "
                f"imageAspectRatio={request_body.options.imageAspectRatio}, "
                f"imageResolution={request_body.options.imageResolution}, "
                f"imageStyle={request_body.options.imageStyle}, "
                f"size={request_body.options.size}, "
                f"quality={request_body.options.quality}, "
                f"style={request_body.options.style}, "
                f"personGeneration={request_body.options.personGeneration}, "
                f"negativePrompt={'<set>' if request_body.options.negativePrompt else None}, "
                f"guidanceScale={request_body.options.guidanceScale}, "
                f"seed={request_body.options.seed}, "
                f"outputMimeType={request_body.options.outputMimeType}, "
                f"outputCompressionQuality={request_body.options.outputCompressionQuality}, "
                f"enhancePrompt={request_body.options.enhancePrompt}"
                f"}}"
            )
        else:
            logger.info(f"[Generate] Raw Request Options: None")

        # Get API key with user-based credential retrieval
        api_key = await get_api_key(provider, request_body.apiKey, user_id, db)
        
        # Get base URL from options
        base_url = None
        if request_body.options and request_body.options.baseUrl:
            base_url = request_body.options.baseUrl
        
        # Build generation options first (needed for tongyi special handling)
        gen_kwargs = {}
        if request_body.options:
            # Size, quality, style (OpenAI style)
            if request_body.options.size:
                gen_kwargs["size"] = request_body.options.size
            if request_body.options.quality:
                gen_kwargs["quality"] = request_body.options.quality
            if request_body.options.style:
                gen_kwargs["style"] = request_body.options.style

            # Number of images (support both frontend and legacy formats)
            number_of_images = request_body.options.numberOfImages or request_body.options.n or 1
            gen_kwargs["number_of_images"] = number_of_images

            # Aspect ratio (support both frontend and legacy formats)
            aspect_ratio = request_body.options.imageAspectRatio or request_body.options.aspectRatio
            if aspect_ratio:
                gen_kwargs["aspect_ratio"] = aspect_ratio

            # Image style (frontend format: imageStyle)
            if request_body.options.imageStyle:
                gen_kwargs["image_style"] = request_body.options.imageStyle

            # Image resolution tier (frontend format: imageResolution, e.g. "1K"/"2K"/"4K")
            if request_body.options.imageResolution:
                gen_kwargs["image_size"] = request_body.options.imageResolution

            # ✅ NEW: Imagen-specific advanced parameters
            # Negative prompt (what to avoid in the image)
            if request_body.options.negativePrompt:
                gen_kwargs["negative_prompt"] = request_body.options.negativePrompt

            # Guidance scale (guidance strength 1.0-20.0)
            if request_body.options.guidanceScale is not None:
                gen_kwargs["guidance_scale"] = request_body.options.guidanceScale

            # Seed (random seed for reproducible generation)
            if request_body.options.seed is not None:
                gen_kwargs["seed"] = request_body.options.seed

            # Person generation setting
            if request_body.options.personGeneration:
                gen_kwargs["person_generation"] = request_body.options.personGeneration

            # Output MIME type ('image/jpeg', 'image/png')

            if request_body.options.outputMimeType:
                gen_kwargs["output_mime_type"] = request_body.options.outputMimeType

            # Output compression quality (1-100, for JPEG)
            if request_body.options.outputCompressionQuality is not None:
                gen_kwargs["output_compression_quality"] = request_body.options.outputCompressionQuality

            # Enhance prompt (let AI improve the prompt)
            if request_body.options.enhancePrompt is not None:
                gen_kwargs["enhance_prompt"] = request_body.options.enhancePrompt

            # 记录所有提取的参数
            logger.info(
                f"[Generate] ==================== Extracted Parameters ===================="
            )
            logger.info(
                f"[Generate] Extracted gen_kwargs: {gen_kwargs}"
            )
            logger.info(
                f"[Generate] ====================================================================="
            )

            # Log all extracted parameters
            logger.info(
                f"[Generate] Extracted parameters: "
                f"number_of_images={gen_kwargs.get('number_of_images')}, "
                f"aspect_ratio={gen_kwargs.get('aspect_ratio')}, "
                f"image_size={gen_kwargs.get('image_size')}, "
                f"image_style={gen_kwargs.get('image_style')}, "
                f"negative_prompt={'<set>' if gen_kwargs.get('negative_prompt') else None}, "
                f"guidance_scale={gen_kwargs.get('guidance_scale')}, "
                f"seed={gen_kwargs.get('seed')}, "
                f"person_generation={gen_kwargs.get('person_generation')}, "
                f"output_mime_type={gen_kwargs.get('output_mime_type')}, "
                f"output_compression_quality={gen_kwargs.get('output_compression_quality')}, "
                f"enhance_prompt={gen_kwargs.get('enhance_prompt')}"
            )

        # Create provider service - special handling for tongyi
        if provider == 'tongyi':
            # Tongyi uses dedicated TongyiImageService for image generation
            from ...services.tongyi.image_service import TongyiImageService, GenerateImageParams

            logger.info(f"[Generate] Using TongyiImageService for tongyi provider")

            tongyi_service = TongyiImageService.get_instance(api_key)

            # Build parameters for TongyiImageService
            params = GenerateImageParams(
                model_id=request_body.modelId,
                prompt=request_body.prompt,
                aspect_ratio=gen_kwargs.get('aspect_ratio', '1:1'),
                resolution=gen_kwargs.get('image_size', '1.25K'),
                num_images=gen_kwargs.get('number_of_images', 1),
                negative_prompt=gen_kwargs.get('negative_prompt'),
                seed=gen_kwargs.get('seed'),
                style=gen_kwargs.get('style') or gen_kwargs.get('image_style')
            )

            results = await tongyi_service.generate_image(params)
            images = [{"url": r.url, "revised_prompt": None} for r in results]

            logger.info(
                f"[Generate] Image generation successful: provider={provider}, user={user_id}, "
                f"count={len(images)}, model={request_body.modelId}"
            )

            return {"images": images}

        # Other providers use ProviderFactory
        from ...services.common.provider_factory import ProviderFactory

        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                api_url=base_url,
                timeout=120.0,
                user_id=user_id,
                db=db
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Call provider's generate_image method
        result = await service.generate_image(
            prompt=request_body.prompt,
            model=request_body.modelId,
            **gen_kwargs
        )
        
        # Convert to frontend format
        # Frontend expects: { images: [{ url: string, revised_prompt?: string }] }
        images = []
        if isinstance(result, dict):
            if "url" in result:
                images.append({
                    "url": result["url"],
                    "revised_prompt": result.get("revised_prompt")
                })
            elif "images" in result:
                images = result["images"]
        elif isinstance(result, list):
            images = result
        
        logger.info(
            f"[Generate] Image generation successful: provider={provider}, user={user_id}, "
            f"count={len(images)}, model={request_body.modelId}"
        )

        return {"images": images}

    except HTTPException:
        raise
    except ContentPolicyError as e:
        logger.warning(
            f"[Generate] Content policy blocked image generation: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, error={e}"
        )
        raise HTTPException(
            status_code=422,
            detail={"code": "content_policy", "message": str(e)}
        )
    except NotImplementedError as e:
        logger.warning(
            f"[Generate] Feature not implemented: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, error={e}"
        )
        raise HTTPException(
            status_code=501,
            detail=f"Feature not implemented for {provider}: {str(e)}"
        )
    except ValueError as e:
        logger.warning(
            f"[Generate] Validation error: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, error={e}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"[Generate] Image generation failed: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, prompt={request_body.prompt[:50]}..., error={e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(e)}"
        )


@router.post("/{provider}/image/edit")
async def edit_image(
    provider: str,
    request_body: ImageEditRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Image editing API endpoint for Google Imagen.
    
    Currently only supports Google provider with Vertex AI configuration.
    Gemini API does not support image editing.
    
    Args:
        provider: Provider name (must be 'google')
        request_body: Image edit request with model, prompt, reference images, and options
        request: FastAPI request object for user authentication
        db: Database session for loading user configuration
    
    Returns:
        Dictionary with edited images and metadata
    
    Raises:
        HTTPException: If provider is not supported, editing fails, or content policy is violated
    """
    try:
        # Validate provider
        if provider != 'google':
            raise HTTPException(
                status_code=400,
                detail=f"Image editing is not supported for provider: {provider}. Only Google (Vertex AI) supports image editing."
            )
        
        # Authenticate user
        from ...core.user_context import require_user_id
        user_id = require_user_id(request)
        
        logger.info(
            f"[Generate] ==================== Image Editing Request ===================="
        )
        logger.info(
            f"[Generate] Provider: {provider}"
        )
        logger.info(
            f"[Generate] User ID: {user_id}"
        )
        logger.info(
            f"[Generate] Model: {request_body.modelId}"
        )
        logger.info(
            f"[Generate] Prompt: {request_body.prompt[:100]}{'...' if len(request_body.prompt) > 100 else ''}"
        )
        logger.info(
            f"[Generate] Reference Images: {list(request_body.referenceImages.keys())}"
        )
        if request_body.options:
            logger.info(
                f"[Generate] Options: {request_body.options}"
            )
        
        # Get API key with user-based credential retrieval
        api_key = await get_api_key(provider, None, user_id, db)
        
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="No API key configured. Please configure your API key in settings."
            )
        
        # Create provider service with user context
        from ...services.common.provider_factory import ProviderFactory
        
        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                timeout=120.0,
                user_id=user_id,
                db=db
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Call edit_image method
        result = await service.edit_image(
            prompt=request_body.prompt,
            model=request_body.modelId,
            reference_images=request_body.referenceImages,
            mode=request_body.mode,
            **(request_body.options or {})
        )
        
        # Get current API mode for metadata
        api_mode = service.image_edit_coordinator.get_current_api_mode()
        
        logger.info(
            f"[Generate] Image editing successful: provider={provider}, user={user_id}, "
            f"count={len(result)}, model={request_body.modelId}, api_mode={api_mode}"
        )
        
        return {
            "images": result,
            "metadata": {
                "model": request_body.modelId,
                "prompt": request_body.prompt,
                "timestamp": datetime.utcnow().isoformat(),
                "api_mode": api_mode,
                "reference_image_types": list(request_body.referenceImages.keys())
            }
        }
    
    except HTTPException:
        raise
    except NotSupportedError as e:
        logger.warning(
            f"[Generate] Image editing not supported: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, error={e}"
        )
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except ContentPolicyError as e:
        logger.warning(
            f"[Generate] Content policy blocked image editing: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, error={e}"
        )
        raise HTTPException(
            status_code=422,
            detail={"code": "content_policy", "message": str(e)}
        )
    except ValueError as e:
        logger.warning(
            f"[Generate] Validation error: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, error={e}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameter: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"[Generate] Image editing failed: provider={provider}, user={user_id}, "
            f"model={request_body.modelId}, prompt={request_body.prompt[:50]}..., error={e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Image editing failed: {str(e)}"
        )


@router.post("/{provider}/video")
async def generate_video(
    provider: str,
    request_body: VideoGenerateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Video generation API endpoint for all providers.
    """
    try:
        # ✅ Authenticate user
        from ...core.user_context import require_user_id
        user_id = require_user_id(request)

        logger.info(
            f"[Generate] Video generation: provider={provider}, user={user_id}, "
            f"prompt={request_body.prompt[:50]}..."
        )

        # Get API key with user-based credential retrieval
        api_key = await get_api_key(provider, request_body.apiKey, user_id, db)
        
        # Get base URL from options
        base_url = None
        if request_body.options and request_body.options.baseUrl:
            base_url = request_body.options.baseUrl

        # Create provider service
        from ...services.common.provider_factory import ProviderFactory

        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                api_url=base_url,
                timeout=300.0,  # Video generation may take longer
                user_id=user_id,
                db=db
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Call provider's generate_video method
        model = request_body.modelId or "default"
        result = await service.generate_video(
            prompt=request_body.prompt,
            model=model
        )
        
        logger.info(f"[Generate] Video generated")
        
        return result
    
    except HTTPException:
        raise
    except NotImplementedError as e:
        logger.warning(f"[Generate] Not implemented: {e}")
        raise HTTPException(
            status_code=501,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[Generate] Video generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider}/speech")
async def generate_speech(
    provider: str,
    request_body: SpeechGenerateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Speech generation API endpoint for all providers.
    """
    try:
        # ✅ Authenticate user
        from ...core.user_context import require_user_id
        user_id = require_user_id(request)

        logger.info(
            f"[Generate] Speech generation: provider={provider}, user={user_id}, "
            f"voice={request_body.voiceName}, text={request_body.text[:50]}..."
        )

        # Get API key with user-based credential retrieval
        api_key = await get_api_key(provider, request_body.apiKey, user_id, db)

        # Create provider service
        from ...services.common.provider_factory import ProviderFactory

        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                api_url=request_body.baseUrl,
                timeout=120.0,
                user_id=user_id,
                db=db
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Call provider's generate_speech method
        result = await service.generate_speech(
            text=request_body.text,
            voice=request_body.voiceName
        )
        
        logger.info(f"[Generate] Speech generated")
        
        return result
    
    except HTTPException:
        raise
    except NotImplementedError as e:
        logger.warning(f"[Generate] Not implemented: {e}")
        raise HTTPException(
            status_code=501,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[Generate] Speech generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/stats")
async def get_monitoring_stats(request: Request):
    """
    Get monitoring statistics for image generation.
    
    Returns usage statistics including:
    - Vertex AI usage count
    - Gemini API usage count
    - Fallback count (Vertex AI → Gemini API)
    
    Requires authentication.
    """
    try:
        # ✅ Authenticate user (admin only would be better, but for now just require auth)
        from ...core.user_context import require_user_id
        user_id = require_user_id(request)
        
        # Get usage stats from ImagenCoordinator
        from ...services.gemini.imagen_coordinator import get_usage_stats
        
        stats = get_usage_stats()
        
        logger.info(f"[Generate] Monitoring stats requested by user={user_id}")
        
        return {
            "status": "success",
            "stats": stats,
            "description": {
                "vertex_ai_usage": "Number of times Vertex AI was used for image generation",
                "gemini_api_usage": "Number of times Gemini API was used for image generation",
                "fallback_count": "Number of times fallback from Vertex AI to Gemini API occurred"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Generate] Failed to get monitoring stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
