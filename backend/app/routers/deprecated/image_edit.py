"""
图像编辑路由
统一处理通义万相和Qwen图像编辑请求
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
import httpx
import base64
import logging

from ...core.database import SessionLocal
from ...core.user_context import require_user_id
from ...models.db_models import ConfigProfile, UserSettings
from ...core.encryption import decrypt_data, is_encrypted

# 复用现有的 DashScope 文件上传服务
try:
    from ...services.tongyi.file_upload import upload_bytes_to_dashscope, upload_to_dashscope
except ImportError:
    from services.tongyi.file_upload import upload_bytes_to_dashscope, upload_to_dashscope

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
        logger.warning(f"[Image Edit] API key decryption failed: {e}")
        return api_key


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_tongyi_api_key(
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None
) -> str:
    """
    从数据库获取 Tongyi 的 API Key

    优先级：
    1. 请求参数（用于测试/覆盖）
    2. 数据库激活配置（必须匹配 tongyi provider）
    3. 数据库任意配置（匹配 tongyi provider）
    """
    provider = "tongyi"

    if request_api_key and request_api_key.strip():
        logger.info(f"[Image Edit] Using API key from request parameter (test/override mode)")
        return request_api_key

    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    matching_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == provider,
        ConfigProfile.user_id == user_id
    ).all()

    if not matching_profiles:
        raise HTTPException(
            status_code=401,
            detail=f"API Key not found for provider: {provider}. "
                   f"Please configure it in Settings → Profiles."
        )

    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                logger.info(f"[Image Edit] Using API key from active profile '{profile.name}'")
                return _decrypt_api_key(profile.api_key)

    for profile in matching_profiles:
        if profile.api_key:
            logger.info(f"[Image Edit] Using API key from profile '{profile.name}' (fallback)")
            return _decrypt_api_key(profile.api_key)

    raise HTTPException(
        status_code=401,
        detail=f"API Key not found for provider: {provider}. "
               f"Please configure it in Settings → Profiles."
    )

router = APIRouter(prefix="/api/generate/tongyi/image", tags=["Tongyi Image Edit"])

# DashScope 官方 API 地址
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"


# === Pydantic 模型定义 ===

class ReferenceImage(BaseModel):
    """参考图片"""
    url: str = Field(..., description="图片URL (支持 https://, oss://, data:image/...)")
    file_name: str = Field(default="image.png", description="文件名")


class ImageEditOptions(BaseModel):
    """图像编辑选项"""
    n: int = Field(default=1, ge=1, le=6, description="生成图片数量")
    negative_prompt: Optional[str] = Field(default=None, description="反向提示词")
    size: Optional[str] = Field(default=None, description="输出分辨率 (宽*高)")
    watermark: bool = Field(default=False, description="是否添加水印")
    seed: Optional[int] = Field(default=None, description="随机数种子")
    prompt_extend: bool = Field(default=True, description="是否开启提示词智能改写")


class ImageEditRequest(BaseModel):
    """图像编辑请求"""
    model: str = Field(..., description="模型名称")
    prompt: str = Field(..., description="编辑提示词")
    reference_image: ReferenceImage = Field(..., description="参考图片")
    options: ImageEditOptions = Field(default_factory=ImageEditOptions)
    api_key: Optional[str] = Field(default=None, description="DashScope API Key（可选，会从数据库获取）")


class ImageEditResponse(BaseModel):
    """图像编辑响应"""
    url: str = Field(..., description="生成的图片URL")
    mime_type: str = Field(default="image/png", description="图片MIME类型")


# === 辅助函数 ===

async def process_reference_image(
    reference_image: ReferenceImage,
    api_key: str,
    model: str
) -> str:
    """
    处理参考图片,统一转换为 oss:// URL
    复用现有的 DashScope 文件上传服务
    
    Args:
        reference_image: 参考图片对象
        api_key: DashScope API Key
        model: 模型名称（用于获取上传凭证）
    
    Returns:
        oss:// 格式的URL
    """
    url = reference_image.url
    file_name = reference_image.file_name
    
    # 情况 1: 已经是 oss:// URL - 直接使用
    if url.startswith('oss://'):
        logger.info(f"[Image Edit] 使用现有 OSS URL: {url[:60]}...")
        return url
    
    # 情况 2 & 3: HTTPS URL 或 Base64 data URI
    # 使用现有的 upload_to_dashscope 服务统一处理
    logger.info(f"[Image Edit] 上传图片到 OSS: {url[:60]}...")
    logger.info(f"[Image Edit] 使用模型获取上传凭证: {model}")
    
    try:
        # upload_to_dashscope 支持两种输入:
        # - HTTPS URL: 自动下载后上传
        # - data: URI: 自动解码后上传
        result = upload_to_dashscope(
            image_url=url,
            api_key=api_key,
            model=model  # 使用实际请求的模型获取上传凭证
        )
        
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"图片上传失败: {result.error}"
            )
        
        logger.info(f"[Image Edit] ✅ 上传成功: {result.oss_url[:60]}...")
        return result.oss_url
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Image Edit] 上传失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"图片上传失败: {str(e)}"
        )


def build_qwen_payload(
    model: str,
    prompt: str,
    image_url: str,
    options: ImageEditOptions
) -> dict:
    """构建 Qwen Image Edit 请求 payload"""
    content = [{"image": image_url}]
    if prompt:
        content.append({"text": prompt})

    payload = {
        "model": model,
        "input": {
            "messages": [{
                "role": "user",
                "content": content
            }]
        },
        "parameters": {
            "n": options.n,
            "watermark": options.watermark,
            "prompt_extend": options.prompt_extend
        }
    }

    if options.negative_prompt:
        payload["parameters"]["negative_prompt"] = options.negative_prompt
    if options.seed is not None:
        payload["parameters"]["seed"] = options.seed

    # 前端已计算好 size，直接使用
    if options.size and options.n == 1:  # Qwen 只在 n=1 时支持自定义 size
        payload["parameters"]["size"] = options.size

    return payload


def build_wan26_image_payload(
    model: str,
    prompt: str,
    image_url: str,
    options: ImageEditOptions
) -> dict:
    """
    构建 wan2.6-image 模型请求 payload
    
    wan2.6-image 使用 multimodal-generation 端点，采用 messages 格式
    官方文档: https://help.aliyun.com/zh/model-studio/developer-reference/wan2.6-image
    
    enable_interleave=false: 图像编辑模式（需要输入图片，同步调用）
    """
    # 构建 content 数组：先文本后图片
    content = []
    if prompt:
        content.append({"text": prompt})
    content.append({"image": image_url})
    
    payload = {
        "model": model,
        "input": {
            "messages": [{
                "role": "user",
                "content": content
            }]
        },
        "parameters": {
            "n": options.n,
            "watermark": options.watermark,
            "prompt_extend": options.prompt_extend,
            "enable_interleave": False  # 图像编辑模式，同步调用
        }
    }

    if options.negative_prompt:
        payload["parameters"]["negative_prompt"] = options.negative_prompt
    if options.seed is not None:
        payload["parameters"]["seed"] = options.seed
    if options.size:
        payload["parameters"]["size"] = options.size

    return payload


def build_wan_legacy_payload(
    model: str,
    prompt: str,
    image_url: str,
    options: ImageEditOptions
) -> dict:
    """
    构建旧版通义万相模型请求 payload (wanx-v1, wan2.5-i2i-preview 等)
    
    使用 image-generation 端点，采用 prompt + images 格式
    """
    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "images": [image_url]
        },
        "parameters": {
            "n": options.n,
            "watermark": options.watermark
        }
    }

    if options.negative_prompt:
        payload["parameters"]["negative_prompt"] = options.negative_prompt
    if options.seed is not None:
        payload["parameters"]["seed"] = options.seed

    # 前端已计算好 size，直接使用
    if options.size:
        payload["parameters"]["size"] = options.size

    return payload


async def call_dashscope_api(
    endpoint: str,
    payload: dict,
    api_key: str,
    use_oss_resolve: bool = True
) -> dict:
    """调用 DashScope API"""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # 智能添加 OssResourceResolve 头
    if use_oss_resolve:
        headers['X-DashScope-OssResourceResolve'] = 'enable'
        logger.info("[Image Edit] 添加 X-DashScope-OssResourceResolve: enable")
    
    logger.info(f"[Image Edit] 调用 DashScope API: {endpoint}")
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[Image Edit] API 错误 ({response.status_code}): {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"DashScope API 错误: {error_text}"
                )
            
            result = response.json()
            logger.info("[Image Edit] ✅ API 调用成功")
            return result
            
    except httpx.TimeoutException:
        logger.error("[Image Edit] API 调用超时")
        raise HTTPException(status_code=504, detail="DashScope API 超时")
    except httpx.RequestError as e:
        logger.error(f"[Image Edit] API 调用失败: {str(e)}")
        raise HTTPException(status_code=502, detail=f"无法连接到 DashScope API: {str(e)}")


def extract_image_url(response_data: dict, model: str) -> str:
    """从 API 响应中提取图片 URL"""

    # 检查是否误用了视觉理解模型（只返回文本，不返回图片）
    if 'output' in response_data and 'choices' in response_data.get('output', {}):
        choices = response_data['output']['choices']
        if choices and len(choices) > 0:
            content = choices[0].get('message', {}).get('content', [])
            # 检查是否只包含文本（视觉理解模型的响应）
            has_text_only = all(isinstance(item, dict) and 'text' in item and 'image' not in item for item in content)
            if has_text_only and content:
                logger.error(f"[Image Edit] 错误: 模型 {model} 返回了文本而非图片，可能使用了视觉理解模型")
                raise HTTPException(
                    status_code=400,
                    detail=f"模型错误: '{model}' 是视觉理解模型，不支持图像编辑。\n\n"
                           f"请使用以下图像编辑模型:\n"
                           f"- qwen-image-edit-plus\n"
                           f"- qwen-image-edit-plus-2025-12-15\n"
                           f"- qwen-image-edit-plus-2025-10-30\n"
                           f"- wan2.6-image\n"
                           f"- wan2.5-i2i-preview"
                )

    # Qwen 和 wan2.6-image 模型响应格式 (multimodal-generation 端点)
    # 响应格式: output.choices[0].message.content[{image: url}]
    if model.startswith('qwen-') or model == 'wan2.6-image':
        if 'output' in response_data and 'choices' in response_data['output']:
            choices = response_data['output']['choices']
            if choices and len(choices) > 0:
                content = choices[0].get('message', {}).get('content', [])
                for item in content:
                    if isinstance(item, dict) and 'image' in item:
                        return item['image']

    # 旧版通义万相响应格式 (image-generation 端点)
    # 响应格式: output.results[0].url
    if model.startswith('wan') and model != 'wan2.6-image':
        if 'output' in response_data and 'results' in response_data['output']:
            results = response_data['output']['results']
            if results and len(results) > 0:
                return results[0]['url']

    # 通用格式尝试
    if 'output' in response_data:
        output = response_data['output']
        for field in ['url', 'output_image_url', 'image_url']:
            if field in output:
                return output[field]

    logger.error(f"[Image Edit] 无法从响应中提取图片 URL: {response_data}")
    raise HTTPException(
        status_code=500,
        detail="API 返回成功但未找到图片 URL"
    )


# === 主路由 ===

@router.post("/edit", response_model=ImageEditResponse)
async def edit_image(
    request: ImageEditRequest,
    request_obj: Request,
    db: Session = Depends(get_db)
) -> ImageEditResponse:
    """
    统一的图像编辑接口

    支持的模型:
    - qwen-image-edit-plus (及其变体)
    - wan2.6-image (推荐)
    - wan2.5-i2i-preview (向后兼容)

    图片输入支持:
    - HTTPS URL: 自动下载并上传到 OSS
    - oss:// URL: 直接使用
    - Base64 data URI: 解码并上传到 OSS
    """
    try:
        # ✅ Step 1: 验证用户认证
        user_id = require_user_id(request_obj)

        # ✅ Step 2: 从数据库获取 API Key
        api_key = await get_tongyi_api_key(
            db=db,
            user_id=user_id,
            request_api_key=request.api_key
        )

        logger.info(f"[Image Edit] 收到图像编辑请求: model={request.model}, user_id={user_id}")

        # 步骤 3: 处理参考图片,统一转换为 oss:// URL
        oss_url = await process_reference_image(
            request.reference_image,
            api_key,  # ✅ 使用从数据库获取的 API Key
            request.model
        )
        
        # 步骤 2: 根据模型类型构建 payload 和 endpoint
        if request.model.startswith('qwen-'):
            # Qwen Image Edit 系列 - 使用 multimodal-generation 端点
            endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
            payload = build_qwen_payload(
                request.model,
                request.prompt,
                oss_url,
                request.options
            )
        elif request.model == 'wan2.6-image':
            # wan2.6-image 模型 - 使用 multimodal-generation 端点 + messages 格式
            endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
            payload = build_wan26_image_payload(
                request.model,
                request.prompt,
                oss_url,
                request.options
            )
            logger.info(f"[Image Edit] wan2.6-image 使用 multimodal-generation 端点")
        elif request.model.startswith('wan'):
            # 旧版通义万相系列 (wanx-v1, wan2.5-i2i-preview 等) - 使用 image-generation 端点
            endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/image-generation/generation"
            payload = build_wan_legacy_payload(
                request.model,
                request.prompt,
                oss_url,
                request.options
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模型: {request.model}"
            )
        
        # 步骤 4: 调用 DashScope API
        # 因为我们统一转换为 oss:// URL,所以总是添加 OssResourceResolve 头
        result = await call_dashscope_api(
            endpoint,
            payload,
            api_key,  # ✅ 使用从数据库获取的 API Key
            use_oss_resolve=True
        )
        
        # 步骤 4: 提取图片 URL
        image_url = extract_image_url(result, request.model)
        
        logger.info(f"[Image Edit] ✅ 图像编辑完成: {image_url[:60]}...")
        
        return ImageEditResponse(
            url=image_url,
            mime_type='image/png'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Image Edit] ❌ 图像编辑失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"图像编辑失败: {str(e)}"
        )
