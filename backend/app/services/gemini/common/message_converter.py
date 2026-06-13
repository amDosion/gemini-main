"""
Message Converter Module

Handles conversion between standard message format and Google API format.
Supports multimodal messages (text + images/files).
"""

import re
import logging
import base64
import binascii
import os
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from ....utils.attachment_handler import is_base64_url
from ....utils.log_sanitization import summarize_url_for_log

logger = logging.getLogger(__name__)


_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_GOOGLE_FILE_URI_PATH_RE = re.compile(r"^/v\d+(?:beta\d*)?/files/[^/]+$")
MAX_INLINE_ATTACHMENT_BYTES = int(os.getenv("GEMINI_MAX_INLINE_ATTACHMENT_BYTES", str(20 * 1024 * 1024)))


def is_allowed_provider_file_uri(file_uri: Any) -> bool:
    normalized = str(file_uri or "").strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if (
        lowered.startswith("file:")
        or normalized.startswith(("/", "\\", "~"))
        or _WINDOWS_ABSOLUTE_PATH_RE.match(normalized) is not None
    ):
        return False

    if normalized.startswith("files/"):
        return len(normalized) > len("files/")

    if lowered.startswith("gs://"):
        parsed = urlparse(normalized)
        return bool(parsed.netloc and parsed.path.strip("/"))

    if lowered.startswith("https://"):
        parsed = urlparse(normalized)
        host = str(parsed.hostname or "").lower()
        path = str(parsed.path or "")
        return (
            host == "generativelanguage.googleapis.com"
            and _GOOGLE_FILE_URI_PATH_RE.match(path) is not None
        )

    return False


def _raise_inline_payload_too_large(source: str) -> None:
    raise ValueError(f"{source} too large (> {MAX_INLINE_ATTACHMENT_BYTES} bytes)")


def _max_inline_base64_chars() -> int:
    return ((MAX_INLINE_ATTACHMENT_BYTES + 2) // 3) * 4 + 16


def _compact_base64_payload(payload: Any) -> str:
    return re.sub(r"\s+", "", str(payload or ""))


def _estimated_base64_decoded_size(payload: str) -> int:
    normalized = _compact_base64_payload(payload)
    if not normalized:
        return 0
    padding = len(normalized) - len(normalized.rstrip("="))
    return max(0, (len(normalized) * 3 // 4) - padding)


def normalize_inline_base64_payload(payload: Any, *, source: str) -> str:
    normalized = _compact_base64_payload(payload)
    if not normalized:
        raise ValueError(f"{source} payload is empty")
    if len(normalized) > _max_inline_base64_chars():
        _raise_inline_payload_too_large(source)
    if _estimated_base64_decoded_size(normalized) > MAX_INLINE_ATTACHMENT_BYTES:
        _raise_inline_payload_too_large(source)
    return normalized


def validate_inline_base64_payload(payload: Any, *, source: str) -> str:
    normalized = normalize_inline_base64_payload(payload, source=source)
    try:
        base64.b64decode(normalized, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"invalid {source} base64 payload") from exc
    return normalized


def decode_inline_attachment_bytes(payload: Any, *, source: str) -> bytes:
    normalized = normalize_inline_base64_payload(payload, source=source)
    try:
        decoded = base64.b64decode(normalized, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"invalid {source} base64 payload") from exc
    if len(decoded) > MAX_INLINE_ATTACHMENT_BYTES:
        _raise_inline_payload_too_large(source)
    return decoded


def extract_inline_data_url_payload(
    value: Any,
    *,
    fallback_mime_type: str,
    source: str,
) -> Optional[tuple[str, str]]:
    raw_value = str(value or "")
    if not is_base64_url(raw_value):
        return None

    match = re.match(r'^data:(.*?);base64,(.*)$', raw_value, re.DOTALL)
    if not match:
        return None

    actual_mime = match.group(1) or fallback_mime_type
    base64_payload = validate_inline_base64_payload(match.group(2), source=source)
    return actual_mime, base64_payload


class MessageConverter:
    """
    Converts messages between standard format and Google API format.

    Responsibilities:
    - Convert data structure (content → parts)
    - Handle system messages (merge into first user message)
    - Handle attachments (images/files → inline_data/file_data parts)
    - Maintain role names (already correct from router)
    """

    @staticmethod
    def build_contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将标准消息格式转换为 Google API 格式（一次性转换）

        职责：
        - 转换数据结构（content → parts）
        - 处理 system 消息（合并到第一条用户消息）
        - 处理附件（images/files → inline_data/file_data parts）
        - 不转换角色名称（已经是正确的）

        输入格式（来自 Router Layer，已过滤）:
            [{"role": "user"|"model"|"system", "content": str, "attachments": [...]}]

        输出格式（Google API）:
            [{"role": "user"|"model", "parts": [{"text": str}, {"inline_data": ...}]}]

        Args:
            messages: 标准消息列表（Router Layer 已过滤）

        Returns:
            Google API 格式的消息列表

        Raises:
            ValueError: 如果消息列表为空或不包含有效消息

        注意：
        - Router Layer 已经过滤了错误消息和空消息
        - Router Layer 保持了原始角色名称（"model"）
        - 此方法只转换结构，不转换角色名称
        - 移除了防御性验证（Router Layer 已保证数据有效）
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        contents = []
        system_message = None

        for msg in messages:
            role = msg['role']
            content = msg['content']
            attachments = msg.get('attachments', [])

            # ✅ 处理 system 消息（合并到第一条用户消息）
            if role == 'system':
                system_message = content
                continue

            # ✅ 直接使用 role，不转换（已经是 "model"）

            # ✅ 构建 SDK 格式的 parts（支持多模态）
            parts = []

            # 附件 parts（图片/文件，放在文本之前）
            for att in attachments:
                att_part = MessageConverter._build_attachment_part(att)
                if att_part:
                    parts.append(att_part)

            # 文本 part
            text_content = content
            # ✅ 如果是第一条用户消息且有 system 消息，将 system 消息前置
            if role == 'user' and system_message and not contents:
                text_content = f"{system_message}\n\n{content}"
                system_message = None

            parts.append({"text": text_content})

            contents.append({
                "role": role,
                "parts": parts
            })

        if not contents:
            raise ValueError("No valid messages to convert")

        return contents

    @staticmethod
    def _build_attachment_part(attachment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从附件字典构建 Google API 格式的 part（dict 格式）

        支持的附件数据源（按优先级）：
        1. fileUri → file_data part（Google Files API）
        2. url/tempUrl (data: URL) → inline_data part（Base64）
        3. base64Data → inline_data part（纯 Base64 字符串）

        Args:
            attachment: 附件字典

        Returns:
            Google API part dict 或 None
        """
        mime_type = attachment.get('mimeType', 'image/png')

        # Priority 1: fileUri (Google Files API)
        file_uri = attachment.get('fileUri')
        if file_uri:
            if not is_allowed_provider_file_uri(file_uri):
                logger.warning("[MessageConverter] Attachment: rejected unsupported fileUri")
                return None
            logger.info(
                "[MessageConverter] Attachment: file_data uri=%s",
                summarize_url_for_log(str(file_uri)),
            )
            return {
                'file_data': {
                    'file_uri': file_uri,
                    'mime_type': mime_type
                }
            }

        # Priority 2: url or tempUrl with Base64 Data URL
        url = attachment.get('url') or attachment.get('tempUrl')
        if url:
            try:
                data_url_payload = extract_inline_data_url_payload(
                    url,
                    fallback_mime_type=mime_type,
                    source="attachment data URL",
                )
            except ValueError as exc:
                logger.warning("[MessageConverter] Attachment: rejected data URL: %s", exc)
                return None
            if data_url_payload:
                actual_mime, base64_str = data_url_payload
                logger.info(f"[MessageConverter] Attachment: inline_data from data URL "
                          f"(mime={actual_mime}, base64_len={len(base64_str)})")
                return {
                    'inline_data': {
                        'data': base64_str,
                        'mime_type': actual_mime
                    }
                }

        # Priority 3: base64Data field
        base64_data = attachment.get('base64Data')
        if base64_data:
            try:
                data_url_payload = extract_inline_data_url_payload(
                    base64_data,
                    fallback_mime_type=mime_type,
                    source="attachment base64Data",
                )
                if data_url_payload:
                    actual_mime, base64_str = data_url_payload
                    logger.info(f"[MessageConverter] Attachment: inline_data from base64Data "
                              f"(mime={actual_mime})")
                    return {
                        'inline_data': {
                            'data': base64_str,
                            'mime_type': actual_mime
                        }
                    }
                base64_str = validate_inline_base64_payload(
                    base64_data,
                    source="attachment base64Data",
                )
                logger.info(f"[MessageConverter] Attachment: inline_data from raw base64 "
                          f"(mime={mime_type})")
                return {
                    'inline_data': {
                        'data': base64_data,
                        'mime_type': mime_type
                    }
                }
            except ValueError as exc:
                logger.warning("[MessageConverter] Attachment: rejected base64Data: %s", exc)
                return None

        logger.warning(f"[MessageConverter] Attachment: no usable data found "
                      f"(mimeType={mime_type}, hasUrl={bool(url)}, hasBase64={bool(base64_data)})")
        return None
