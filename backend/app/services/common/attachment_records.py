"""附件元数据 / URL 分类纯函数

从 ``attachment_service.py`` 拆出的无副作用辅助逻辑:
- 生成文件名 (``build_generated_filename``)
- 解析 provider 资产元数据 (``resolve_provider_asset_metadata``)
- URL 分类 (``is_persistent_storage_url`` / ``is_google_provider_http_file_url``)
- data URL 解析 (``parse_data_url``)
- 在历史消息中按 URL 反查附件 ID (``find_attachment_by_url``)

这些函数不触碰数据库、网络或被测试 monkeypatch 的模块级名字,因此可以安全
迁出为模块级纯函数。``AttachmentService`` 的同名私有方法保留为薄 delegation,
以维持既有公共 API 与测试 (``svc._build_generated_filename`` 等) 不变。
"""

from typing import Optional, Dict, Any, List
import mimetypes
import uuid

from ...utils.attachment_handler import is_base64_url, is_blob_url


def build_generated_filename(prefix: str, mime_type: Optional[str]) -> str:
    guessed_ext = mimetypes.guess_extension((mime_type or "").split(";")[0].strip()) or ""
    if guessed_ext == ".jpe":
        guessed_ext = ".jpg"
    if not guessed_ext:
        guessed_ext = ".bin"
    return f"{prefix}-{uuid.uuid4()}{guessed_ext}"


def resolve_provider_asset_metadata(
    *,
    ai_url: Optional[str],
    file_uri: Optional[str] = None,
    provider_file_name: Optional[str] = None,
    provider_file_uri: Optional[str] = None,
    gcs_uri: Optional[str] = None,
) -> tuple[str, str]:
    from ..gemini.base.video_common import normalize_gemini_file_name

    normalized_ai_url = str(ai_url or "").strip()
    normalized_file_uri = str(file_uri or "").strip()
    normalized_provider_file_name = str(provider_file_name or "").strip()
    normalized_provider_file_uri = str(provider_file_uri or "").strip()
    normalized_gcs_uri = str(gcs_uri or "").strip()

    resolved_file_uri = (
        normalized_file_uri
        or normalized_gcs_uri
        or normalized_provider_file_uri
        or normalized_provider_file_name
    )
    if not resolved_file_uri:
        if normalized_ai_url.startswith("gs://") or normalize_gemini_file_name(normalized_ai_url):
            resolved_file_uri = normalized_ai_url

    resolved_google_file_uri = normalize_gemini_file_name(
        normalized_provider_file_name
        or normalized_provider_file_uri
        or resolved_file_uri
    ) or ""

    return resolved_file_uri, resolved_google_file_uri


def is_persistent_storage_url(url: Optional[str]) -> bool:
    from ..gemini.base.video_common import normalize_gemini_file_name

    normalized = str(url or "").strip()
    if not normalized:
        return False
    if is_base64_url(normalized) or is_blob_url(normalized):
        return False
    if normalized.startswith('gs://') or normalized.startswith('files/'):
        return False
    if normalize_gemini_file_name(normalized):
        return False
    return True


def is_google_provider_http_file_url(url: str) -> bool:
    normalized = str(url or "").strip()
    return normalized.startswith("https://") and "/files/" in normalized


def parse_data_url(data_url: str) -> tuple[str, str]:
    if not is_base64_url(data_url):
        raise ValueError("Invalid data URL")

    parts = data_url.split(',', 1)
    if len(parts) != 2:
        raise ValueError("Invalid data URL format")

    header = parts[0]
    base64_str = parts[1]
    mime_type = header.split(':', 1)[1].split(';', 1)[0] if ':' in header else ''
    return (mime_type or 'application/octet-stream', base64_str)


def find_attachment_by_url(
    target_url: str,
    messages: List[Dict[str, Any]],
) -> Optional[str]:
    """在消息列表中查找附件ID

    策略:
    1. 精确匹配url
    2. 精确匹配tempUrl
    """
    for msg in reversed(messages):  # 从新到旧
        for att in msg.get('attachments', []):
            # 策略1: 精确匹配url
            if att.get('url') == target_url:
                return att.get('id')

            # 策略2: 精确匹配tempUrl
            if att.get('tempUrl') == target_url:
                return att.get('id')

    return None
