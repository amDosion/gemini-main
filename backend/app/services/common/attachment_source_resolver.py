"""本地直写源数据解析

从 ``attachment_service.py`` 拆出的"把源 payload(本地临时文件 / base64 data URL /
Google provider 资产 / 外链 HTTP)解析为字节流"逻辑,以及直写完成后删除本地临时
文件的逻辑。

这两个函数不依赖被测试 monkeypatch 的模块级名字(``StorageService`` /
``decrypt_config`` 仍由 ``attachment_service.py`` 直接调用),因此可安全迁出。
``download_google_video_asset_for_user`` 需要一个 SQLAlchemy ``Session`` 以解析
用户级 provider 凭据,故以参数显式传入。
"""

import base64
import os
import logging
from typing import Any, Optional

import httpx

from ...utils.attachment_handler import is_base64_url
from ...utils.url_security import (
    get_with_redirect_guard,
)
from .attachment_records import is_google_provider_http_file_url, parse_data_url

logger = logging.getLogger(__name__)


async def load_local_storage_source_bytes(
    *,
    db: Any,
    user_id: str,
    source_file_path: Optional[str] = None,
    source_ai_url: Optional[str] = None,
) -> bytes:
    if source_file_path:
        from ...core.path_utils import resolve_relative_path

        file_path = resolve_relative_path(source_file_path)
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except (FileNotFoundError, PermissionError) as exc:
            logger.error(
                "[AttachmentService] Cannot read local source file '%s': %s",
                source_file_path,
                exc,
            )
            raise

    normalized_ai_url = str(source_ai_url or "").strip()
    if not normalized_ai_url:
        raise ValueError("Local storage persistence requires a source payload.")

    if is_base64_url(normalized_ai_url):
        _mime_type, base64_str = parse_data_url(normalized_ai_url)
        return base64.b64decode(base64_str)

    if (
        normalized_ai_url.startswith('files/')
        or normalized_ai_url.startswith('gs://')
        or is_google_provider_http_file_url(normalized_ai_url)
    ):
        from ..gemini.base.video_asset_download import download_google_video_asset_for_user
        from ..gemini.base.video_common import normalize_gemini_file_name

        provider_file_name = normalize_gemini_file_name(normalized_ai_url)
        provider_file_uri = (
            normalized_ai_url
            if normalized_ai_url.startswith('files/') or provider_file_name
            else None
        )
        gcs_uri = normalized_ai_url if normalized_ai_url.startswith('gs://') else None
        payload, _mime_type = await download_google_video_asset_for_user(
            db,
            user_id,
            provider_file_name=provider_file_name,
            provider_file_uri=provider_file_uri,
            gcs_uri=gcs_uri,
        )
        return payload

    async with httpx.AsyncClient(timeout=30.0) as client:
        response, _final_url = await get_with_redirect_guard(
            client,
            normalized_ai_url,
            max_redirects=5,
        )
        response.raise_for_status()
        return response.content


def delete_local_source_file(source_file_path: str) -> None:
    from ...core.path_utils import resolve_relative_path

    try:
        file_path = resolve_relative_path(source_file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        logger.warning(f"[AttachmentService] 本地存储直写后删除临时文件失败: {source_file_path}")
