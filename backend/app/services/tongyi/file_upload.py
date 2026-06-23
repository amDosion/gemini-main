"""
DashScope 临时文件上传服务

上传文件到 DashScope 的临时存储（48小时有效期）
返回 oss:// 格式的 URL，用于 DashScope API 调用

文档: https://help.aliyun.com/zh/model-studio/get-temporary-file-url

使用方式:
    from app.services.dashscope_file_upload import upload_to_dashscope, upload_bytes_to_dashscope
    
    # 方式1: 从 URL 或 base64 上传
    result = upload_to_dashscope(image_url, api_key)
    
    # 方式2: 从二进制数据上传
    result = upload_bytes_to_dashscope(image_data, "image.png", api_key)
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import requests

from ...utils.attachment_handler import is_base64_url
from ...utils.url_security import (
    UnsafeURLError,
    stream_with_redirect_guard,
    sync_stream_with_redirect_guard,
    validate_outbound_http_url,
    validate_outbound_http_url_async,
)
from ...utils.media_limits import (
    MediaTooLargeError,
    decode_base64_data_url_limited,
    read_httpx_response_limited,
    read_httpx_response_limited_sync,
)
from ...utils.log_sanitization import summarize_url_for_log

logger = logging.getLogger(__name__)

# DashScope API 配置
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"

# Module-level lazy ``httpx.AsyncClient`` for async upload paths. The sync
# functions below still use ``requests`` because they are called from sync
# code paths (e.g. ``image_expand._retry_with_oss`` which itself runs
# inside ``asyncio.to_thread``). The async variants avoid blocking the
# event loop on the typically expensive image upload.
_http_client: Optional[httpx.AsyncClient] = None
_http_client_lock = asyncio.Lock()


async def _get_async_http_client() -> httpx.AsyncClient:
    """Lazy initializer for the module-level ``httpx.AsyncClient``."""
    global _http_client
    if _http_client is None:
        async with _http_client_lock:
            if _http_client is None:
                _http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    return _http_client


@dataclass
class DashScopeUploadResult:
    """上传结果"""
    success: bool
    oss_url: Optional[str] = None  # oss:// 格式的 URL
    error: Optional[str] = None


def _get_upload_policy(api_key: str, model: str = "wanx-v1") -> tuple[bool, Optional[dict], Optional[str]]:
    """
    获取 DashScope OSS 上传凭证
    
    Args:
        api_key: DashScope API Key
        model: 模型名称
    
    Returns:
        (success, policy_data, error_msg)
    """
    try:
        policy_url = f"{DASHSCOPE_BASE_URL}/api/v1/uploads"
        
        response = requests.get(
            policy_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={
                "action": "getPolicy",
                "model": model
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return False, None, f"获取上传凭证失败: {response.text}"
        
        policy_data = response.json().get("data", {})
        if not policy_data:
            return False, None, "上传凭证数据为空"
        
        return True, policy_data, None
        
    except Exception as e:
        return False, None, f"获取上传凭证异常: {str(e)}"


def _upload_to_oss(
    image_data: bytes,
    filename: str,
    policy_data: dict
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    上传文件到 OSS
    
    Args:
        image_data: 图片二进制数据
        filename: 文件名
        policy_data: 上传凭证数据
    
    Returns:
        (success, oss_url, error_msg)
    """
    try:
        key = f"{policy_data['upload_dir']}/{filename}"
        
        # 确定 Content-Type
        if filename.lower().endswith(".png"):
            content_type = "image/png"
        elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "image/png"
        
        # 构建 multipart/form-data
        files = {
            "key": (None, key),
            "OSSAccessKeyId": (None, policy_data["oss_access_key_id"]),
            "Signature": (None, policy_data["signature"]),
            "policy": (None, policy_data["policy"]),
            "x-oss-object-acl": (None, policy_data["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (None, policy_data["x_oss_forbid_overwrite"]),
            "success_action_status": (None, "200"),
            "file": (filename, image_data, content_type)
        }
        
        response = requests.post(
            policy_data["upload_host"],
            files=files,
            timeout=60
        )
        
        if response.status_code != 200:
            return False, None, f"上传失败: {response.text}"
        
        oss_url = f"oss://{key}"
        return True, oss_url, None
        
    except Exception as e:
        return False, None, f"上传异常: {str(e)}"


def upload_bytes_to_dashscope(
    image_data: bytes,
    filename: str,
    api_key: str,
    model: str = "wanx-v1"
) -> DashScopeUploadResult:
    """
    上传二进制图片数据到 DashScope 临时存储
    
    Args:
        image_data: 图片二进制数据
        filename: 文件名（用于确定文件类型）
        api_key: DashScope API Key
        model: 模型名称（必须与后续 API 调用使用的模型匹配）
    
    Returns:
        DashScopeUploadResult: 包含 oss:// URL 的上传结果
    """
    logger.info(f"[DashScope Upload] 开始上传二进制数据: {len(image_data)} bytes")
    
    # 1. 获取上传凭证
    success, policy_data, error = _get_upload_policy(api_key, model)
    if not success:
        logger.error(f"[DashScope Upload] {error}")
        return DashScopeUploadResult(success=False, error=error)
    
    logger.info("[DashScope Upload] ✅ 获取上传凭证成功")
    
    # 2. 上传到 OSS
    success, oss_url, error = _upload_to_oss(image_data, filename, policy_data)
    if not success:
        logger.error(f"[DashScope Upload] {error}")
        return DashScopeUploadResult(success=False, error=error)
    
    logger.info("[DashScope Upload] ✅ 上传成功: %s", summarize_url_for_log(oss_url))
    logger.info("[DashScope Upload] ⏱️  有效期 48 小时")
    
    return DashScopeUploadResult(success=True, oss_url=oss_url)


def upload_to_dashscope(
    image_url: str,
    api_key: str,
    model: str = "wanx-v1"
) -> DashScopeUploadResult:
    """
    上传图片到 DashScope 临时存储
    
    Args:
        image_url: 图片 URL 或 base64 数据 URL
        api_key: DashScope API Key
        model: 模型名称（必须与后续 API 调用使用的模型匹配）
    
    Returns:
        DashScopeUploadResult: 包含 oss:// URL 的上传结果
    """
    try:
        logger.info("[DashScope Upload] 开始上传到临时存储...")
        logger.info(f"[DashScope Upload] 模型: {model}")

        # CANON-012: image_url is user-supplied and fetched server-side (step 2).
        # Enforce the outbound SSRF policy up-front (data: URLs aren't fetched, so
        # they are exempt) and fail fast before any outbound request is made.
        if not is_base64_url(image_url):
            try:
                image_url = validate_outbound_http_url(image_url)
            except UnsafeURLError as exc:
                logger.warning(f"[DashScope Upload] 图片 URL 被出站策略拒绝: {exc}")
                return DashScopeUploadResult(success=False, error=f"图片 URL 被拒绝: {exc}")

        # 步骤 1: 获取上传凭证
        logger.info("[DashScope Upload] 步骤 1: 获取上传凭证...")
        policy_url = f"{DASHSCOPE_BASE_URL}/api/v1/uploads"
        
        policy_response = requests.get(
            policy_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={
                "action": "getPolicy",
                "model": model
            },
            timeout=30
        )
        
        if policy_response.status_code != 200:
            error_text = policy_response.text
            logger.error(f"[DashScope Upload] 获取凭证失败: {error_text}")
            return DashScopeUploadResult(
                success=False,
                error=f"获取上传凭证失败: {error_text}"
            )
        
        policy_data = policy_response.json().get("data", {})
        if not policy_data:
            return DashScopeUploadResult(
                success=False,
                error="上传凭证数据为空"
            )
        
        logger.info("[DashScope Upload] ✅ 获取上传凭证成功")
        
        # 步骤 2: 转换图片为二进制数据
        logger.info("[DashScope Upload] 步骤 2: 转换图片为二进制数据...")
        
        if is_base64_url(image_url):
            # Base64 数据 URL
            # 格式: data:image/jpeg;base64,/9j/4AAQ...
            try:
                image_data, mime_type = decode_base64_data_url_limited(image_url)
                extension = mime_type.split("/")[1] if "/" in mime_type else "jpg"
                file_name = f"expansion-{int(time.time() * 1000)}.{extension}"
            except MediaTooLargeError as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"图片过大: {str(e)}"
                )
            except Exception as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"解析 base64 数据失败: {str(e)}"
                )
        else:
            # URL - 下载图片
            try:
                # CANON-012: per-hop redirect-validated fetch (requests follows
                # redirects by default; a public URL could otherwise 302 -> internal).
                with sync_stream_with_redirect_guard(image_url, timeout=30) as (image_response, _final_url):
                    if image_response.status_code != 200:
                        return DashScopeUploadResult(
                            success=False,
                            error=f"下载图片失败: HTTP {image_response.status_code}"
                        )
                    image_data = read_httpx_response_limited_sync(image_response)
                file_name = f"expansion-{int(time.time() * 1000)}.jpg"
            except MediaTooLargeError as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"图片过大: {str(e)}"
                )
            except Exception as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"下载图片失败: {str(e)}"
                )
        
        logger.info(f"[DashScope Upload] ✅ 图片转换完成: {len(image_data)} bytes")
        
        # 步骤 3: 上传到 OSS
        logger.info("[DashScope Upload] 步骤 3: 上传到 OSS...")
        key = f"{policy_data['upload_dir']}/{file_name}"
        
        # 确定 Content-Type
        if file_name.lower().endswith(".png"):
            content_type = "image/png"
        elif file_name.lower().endswith(".jpg") or file_name.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        else:
            content_type = "image/png"
        
        # 构建 multipart/form-data
        files = {
            "key": (None, key),
            "OSSAccessKeyId": (None, policy_data["oss_access_key_id"]),
            "Signature": (None, policy_data["signature"]),
            "policy": (None, policy_data["policy"]),
            "x-oss-object-acl": (None, policy_data["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (None, policy_data["x_oss_forbid_overwrite"]),
            "success_action_status": (None, "200"),
            "file": (file_name, image_data, content_type)
        }
        
        upload_response = requests.post(
            policy_data["upload_host"],
            files=files,
            timeout=60
        )
        
        if upload_response.status_code != 200:
            error_text = upload_response.text
            logger.error(f"[DashScope Upload] 上传失败: {error_text}")
            return DashScopeUploadResult(
                success=False,
                error=f"上传失败: {error_text}"
            )
        
        oss_url = f"oss://{key}"
        logger.info("[DashScope Upload] ✅ 上传成功!")
        logger.info("[DashScope Upload] OSS URL: %s", summarize_url_for_log(oss_url))
        logger.info("[DashScope Upload] ⏱️  有效期 48 小时")
        
        return DashScopeUploadResult(
            success=True,
            oss_url=oss_url
        )
        
    except Exception as e:
        logger.error(f"[DashScope Upload] 错误: {str(e)}")
        return DashScopeUploadResult(
            success=False,
            error=str(e)
        )


# ---------------------------------------------------------------------------
# Async variants (httpx-based) for use from FastAPI async paths.
# Result shapes match the sync versions exactly so call sites can be swapped
# 1:1 with ``await``.
# ---------------------------------------------------------------------------


async def _get_upload_policy_async(
    api_key: str,
    model: str = "wanx-v1",
) -> tuple[bool, Optional[dict], Optional[str]]:
    """Async variant of ``_get_upload_policy``.

    Uses the module-level ``httpx.AsyncClient`` to avoid blocking the event
    loop. Same parameters and return shape as the sync version.
    """
    try:
        policy_url = f"{DASHSCOPE_BASE_URL}/api/v1/uploads"
        client = await _get_async_http_client()
        response = await client.get(
            policy_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={
                "action": "getPolicy",
                "model": model,
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            return False, None, f"获取上传凭证失败: {response.text}"

        policy_data = response.json().get("data", {})
        if not policy_data:
            return False, None, "上传凭证数据为空"

        return True, policy_data, None

    except Exception as e:
        return False, None, f"获取上传凭证异常: {str(e)}"


async def _upload_to_oss_async(
    image_data: bytes,
    filename: str,
    policy_data: dict,
) -> tuple[bool, Optional[str], Optional[str]]:
    """Async variant of ``_upload_to_oss``."""
    try:
        key = f"{policy_data['upload_dir']}/{filename}"

        # 确定 Content-Type
        if filename.lower().endswith(".png"):
            content_type = "image/png"
        elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "image/png"

        # 构建 multipart/form-data — httpx accepts the same shape as requests.
        files = {
            "key": (None, key),
            "OSSAccessKeyId": (None, policy_data["oss_access_key_id"]),
            "Signature": (None, policy_data["signature"]),
            "policy": (None, policy_data["policy"]),
            "x-oss-object-acl": (None, policy_data["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (None, policy_data["x_oss_forbid_overwrite"]),
            "success_action_status": (None, "200"),
            "file": (filename, image_data, content_type),
        }

        client = await _get_async_http_client()
        response = await client.post(
            policy_data["upload_host"],
            files=files,
            timeout=60.0,
        )

        if response.status_code != 200:
            return False, None, f"上传失败: {response.text}"

        oss_url = f"oss://{key}"
        return True, oss_url, None

    except Exception as e:
        return False, None, f"上传异常: {str(e)}"


async def upload_bytes_to_dashscope_async(
    image_data: bytes,
    filename: str,
    api_key: str,
    model: str = "wanx-v1",
) -> DashScopeUploadResult:
    """Async variant of :func:`upload_bytes_to_dashscope`.

    Behavior identical — only the underlying HTTP transport changes from
    ``requests`` to ``httpx.AsyncClient``.
    """
    logger.info(f"[DashScope Upload] 开始上传二进制数据 (async): {len(image_data)} bytes")

    success, policy_data, error = await _get_upload_policy_async(api_key, model)
    if not success:
        logger.error(f"[DashScope Upload] {error}")
        return DashScopeUploadResult(success=False, error=error)

    logger.info("[DashScope Upload] ✅ 获取上传凭证成功")

    success, oss_url, error = await _upload_to_oss_async(image_data, filename, policy_data)
    if not success:
        logger.error(f"[DashScope Upload] {error}")
        return DashScopeUploadResult(success=False, error=error)

    logger.info("[DashScope Upload] ✅ 上传成功: %s", summarize_url_for_log(oss_url))
    logger.info("[DashScope Upload] ⏱️  有效期 48 小时")

    return DashScopeUploadResult(success=True, oss_url=oss_url)


async def upload_to_dashscope_async(
    image_url: str,
    api_key: str,
    model: str = "wanx-v1",
) -> DashScopeUploadResult:
    """Async variant of :func:`upload_to_dashscope`.

    Behavior identical — only the underlying HTTP transport changes from
    ``requests`` to ``httpx.AsyncClient``. Used by FastAPI async paths so
    the (potentially seconds-long) upload does not block the event loop.
    """
    try:
        logger.info("[DashScope Upload] 开始上传到临时存储 (async)...")
        logger.info(f"[DashScope Upload] 模型: {model}")

        # CANON-012: image_url is user-supplied and fetched server-side (step 2 via
        # httpx, follow_redirects=False). Enforce the outbound SSRF policy up-front
        # (data: URLs are exempt) and fail fast before any outbound request.
        if not is_base64_url(image_url):
            try:
                image_url = await validate_outbound_http_url_async(image_url)
            except UnsafeURLError as exc:
                logger.warning(f"[DashScope Upload] 图片 URL 被出站策略拒绝: {exc}")
                return DashScopeUploadResult(success=False, error=f"图片 URL 被拒绝: {exc}")

        # 步骤 1: 获取上传凭证
        logger.info("[DashScope Upload] 步骤 1: 获取上传凭证...")
        success, policy_data, error = await _get_upload_policy_async(api_key, model)
        if not success:
            logger.error(f"[DashScope Upload] 获取凭证失败: {error}")
            return DashScopeUploadResult(success=False, error=error)

        logger.info("[DashScope Upload] ✅ 获取上传凭证成功")

        # 步骤 2: 转换图片为二进制数据
        logger.info("[DashScope Upload] 步骤 2: 转换图片为二进制数据...")
        client = await _get_async_http_client()

        if is_base64_url(image_url):
            try:
                image_data, mime_type = decode_base64_data_url_limited(image_url)
                extension = mime_type.split("/")[1] if "/" in mime_type else "jpg"
                file_name = f"expansion-{int(time.time() * 1000)}.{extension}"
            except MediaTooLargeError as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"图片过大: {str(e)}",
                )
            except Exception as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"解析 base64 数据失败: {str(e)}",
                )
        else:
            try:
                # CANON-012: per-hop redirect-validated fetch (so a public URL cannot
                # 302 -> internal and legit redirect-serving URLs still work).
                async with stream_with_redirect_guard(client, image_url, max_redirects=5) as (image_response, _final_url):
                    if image_response.status_code != 200:
                        return DashScopeUploadResult(
                            success=False,
                            error=f"下载图片失败: HTTP {image_response.status_code}",
                        )
                    image_data = await read_httpx_response_limited(image_response)
                file_name = f"expansion-{int(time.time() * 1000)}.jpg"
            except MediaTooLargeError as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"图片过大: {str(e)}",
                )
            except Exception as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"下载图片失败: {str(e)}",
                )

        logger.info(f"[DashScope Upload] ✅ 图片转换完成: {len(image_data)} bytes")

        # 步骤 3: 上传到 OSS
        logger.info("[DashScope Upload] 步骤 3: 上传到 OSS...")
        success, oss_url, error = await _upload_to_oss_async(image_data, file_name, policy_data)
        if not success:
            logger.error(f"[DashScope Upload] {error}")
            return DashScopeUploadResult(success=False, error=error)

        logger.info("[DashScope Upload] ✅ 上传成功!")
        logger.info("[DashScope Upload] OSS URL: %s", summarize_url_for_log(oss_url))
        logger.info("[DashScope Upload] ⏱️  有效期 48 小时")

        return DashScopeUploadResult(success=True, oss_url=oss_url)

    except Exception as e:
        logger.error(f"[DashScope Upload] 错误: {str(e)}")
        return DashScopeUploadResult(
            success=False,
            error=str(e),
        )
