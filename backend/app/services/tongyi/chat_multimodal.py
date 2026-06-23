"""
通义千问多模态 Mixin - 视觉模型消息归一化与响应格式化

从 chat.py 拆分而来（行为完全一致），保存多模态（qwen-vl 系列）相关的纯函数式
辅助方法：图片附件识别、MIME 推断、本地路径转 data URL、图文消息归一化，以及
多模态流式 chunk / 完整响应的格式化。被 QwenNativeProvider 通过 mixin 继承复用。

依赖说明：这些方法使用 self（保持原签名），并复用模块级 logger 与共享的本地
存储 allow-root 解析器 resolve_local_public_file_path（CANON-028 安全约束）。
"""

from typing import Dict, Any, Optional, List
import logging
import re
import base64
import mimetypes

from ..storage.local_provider import resolve_local_public_file_path_for_user

logger = logging.getLogger(__name__)


class _QwenMultimodalMixin:
    """通义千问多模态辅助 Mixin（供 QwenNativeProvider 继承）"""

    def _is_image_like_attachment(self, attachment: Dict[str, Any]) -> bool:
        mime_type = str(
            attachment.get("mimeType")
            or attachment.get("mime_type")
            or ""
        ).strip().lower()
        if mime_type.startswith("image/"):
            return True

        candidate = str(
            attachment.get("url")
            or attachment.get("tempUrl")
            or attachment.get("temp_url")
            or attachment.get("fileUri")
            or attachment.get("file_uri")
            or ""
        ).strip().lower()
        if not candidate:
            return False
        if candidate.startswith("data:image/"):
            return True
        if candidate.startswith(("http://", "https://", "oss://")):
            return True
        if candidate.startswith("/") and any(candidate.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")):
            return True
        return any(candidate.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"))

    def _guess_image_mime_type(self, source: str, explicit_mime: str = "") -> str:
        normalized_explicit = str(explicit_mime or "").strip().lower()
        if normalized_explicit.startswith("image/"):
            return normalized_explicit

        raw = str(source or "").strip()
        if raw.lower().startswith("data:image/"):
            header = raw.split(",", 1)[0]
            if ":" in header:
                mime_part = header.split(":", 1)[1]
                mime_type = mime_part.split(";", 1)[0].strip().lower()
                if mime_type.startswith("image/"):
                    return mime_type

        guessed = str(mimetypes.guess_type(raw)[0] or "").strip().lower()
        if guessed.startswith("image/"):
            return guessed
        return "image/png"

    def _local_path_to_data_url(self, path_value: str, explicit_mime: str = "") -> Optional[str]:
        raw_path = str(path_value or "").strip()
        if not raw_path:
            return None

        try:
            # CANON-028: only read files that resolve within the allowed local-storage
            # root (shared allow-root resolver). Arbitrary filesystem paths and
            # file:// URLs are denied — no raw Path(...).read_bytes() on user/model input.
            candidate = resolve_local_public_file_path_for_user(
                raw_path,
                getattr(self, "user_id", None),
            )
            if candidate is None or not candidate.exists() or not candidate.is_file():
                return None

            data = candidate.read_bytes()
            if not data:
                return None

            mime_type = self._guess_image_mime_type(str(candidate), explicit_mime=explicit_mime)
            encoded = base64.b64encode(data).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"
        except Exception:
            logger.debug("[Qwen Provider] Failed to convert local image path to data URL", exc_info=True)
            return None

    def _normalize_multimodal_image_ref(self, ref_value: Any, explicit_mime: str = "") -> Optional[str]:
        if ref_value is None:
            return None

        if isinstance(ref_value, dict):
            nested = (
                ref_value.get("url")
                or ref_value.get("image")
                or ref_value.get("tempUrl")
                or ref_value.get("temp_url")
                or ref_value.get("fileUri")
                or ref_value.get("file_uri")
            )
            return self._normalize_multimodal_image_ref(
                nested,
                explicit_mime=str(ref_value.get("mimeType") or ref_value.get("mime_type") or explicit_mime or ""),
            )

        raw = str(ref_value or "").strip()
        if not raw:
            return None

        lowered = raw.lower()
        if lowered.startswith(("http://", "https://", "oss://", "data:image/")):
            return raw

        local_data_url = self._local_path_to_data_url(raw, explicit_mime=explicit_mime)
        if local_data_url:
            return local_data_url

        compact = raw.replace("\n", "").replace("\r", "")
        if (
            len(compact) >= 128
            and re.fullmatch(r"[A-Za-z0-9+/=]+", compact)
            and " " not in compact
        ):
            mime_type = self._guess_image_mime_type(raw, explicit_mime=explicit_mime)
            return f"data:{mime_type};base64,{compact}"

        return raw

    def _coerce_multimodal_messages(self, messages: list) -> List[Dict[str, Any]]:
        normalized_messages: List[Dict[str, Any]] = []

        for message in messages or []:
            if not isinstance(message, dict):
                continue

            role = str(message.get("role") or "user").strip().lower() or "user"
            if role == "model":
                role = "assistant"

            content = message.get("content")
            attachments = message.get("attachments") if isinstance(message.get("attachments"), list) else []

            multimodal_content: List[Dict[str, Any]] = []
            seen_images = set()

            if isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        text_piece = item.strip()
                        if text_piece:
                            multimodal_content.append({"text": text_piece})
                        continue
                    if not isinstance(item, dict):
                        continue

                    text_piece = str(item.get("text") or "").strip()
                    if text_piece:
                        multimodal_content.append({"text": text_piece})

                    image_source = None
                    if "image" in item:
                        image_source = item.get("image")
                    elif "image_url" in item:
                        image_url = item.get("image_url")
                        image_source = image_url.get("url") if isinstance(image_url, dict) else image_url
                    elif "url" in item and str(item.get("type") or "").strip().lower() in {"image", "input_image"}:
                        image_source = item.get("url")

                    normalized_image = self._normalize_multimodal_image_ref(
                        image_source,
                        explicit_mime=str(item.get("mimeType") or item.get("mime_type") or ""),
                    )
                    if normalized_image and normalized_image not in seen_images:
                        seen_images.add(normalized_image)
                        multimodal_content.append({"image": normalized_image})
            else:
                text_value = str(content or "").strip()
                if text_value:
                    multimodal_content.append({"text": text_value})

            for attachment in attachments:
                if not isinstance(attachment, dict) or not self._is_image_like_attachment(attachment):
                    continue

                image_candidate = (
                    attachment.get("url")
                    or attachment.get("tempUrl")
                    or attachment.get("temp_url")
                    or attachment.get("fileUri")
                    or attachment.get("file_uri")
                )
                normalized_image = self._normalize_multimodal_image_ref(
                    image_candidate,
                    explicit_mime=str(attachment.get("mimeType") or attachment.get("mime_type") or ""),
                )
                if normalized_image and normalized_image not in seen_images:
                    seen_images.add(normalized_image)
                    multimodal_content.insert(0, {"image": normalized_image})

            if not multimodal_content:
                multimodal_content.append({"text": str(content or "")})

            normalized_messages.append({
                "role": role,
                "content": multimodal_content,
            })

        return normalized_messages

    def _format_multimodal_stream_chunk(self, chunk: Any) -> Dict[str, Any]:
        """
        格式化多模态流式 chunk

        MultiModalConversation 的响应格式与 Generation 略有不同

        Args:
            chunk: DashScope MultiModalConversationResponse 对象

        Returns:
            StreamChunk 格式
        """
        output = chunk.output

        # 多模态响应的 choices 结构
        choices = output.get("choices", []) if isinstance(output, dict) else getattr(output, "choices", [])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason")

        # 提取内容（多模态响应的 content 可能是列表）
        content = message.get("content", "")
        if isinstance(content, list):
            # 从列表中提取文本内容
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
            content = "".join(text_parts)

        result = {
            "content": content,
            "chunk_type": "content"
        }

        # 提取 usage 信息
        usage = chunk.usage if hasattr(chunk, "usage") else None
        if usage:
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)

            if finish_reason == "stop":
                result.update({
                    "chunk_type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "finish_reason": finish_reason
                })
                logger.info(f"[Qwen VL] Stream ended: prompt={prompt_tokens}, completion={completion_tokens}")
            else:
                result.update({
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                })
                if finish_reason:
                    result["finish_reason"] = finish_reason

        return result

    def _format_multimodal_response(self, response: Any) -> Dict[str, Any]:
        """
        格式化多模态响应为 ChatResponse

        Args:
            response: DashScope MultiModalConversationResponse 对象

        Returns:
            ChatResponse 格式
        """
        output = response.output

        # 多模态响应的 choices 结构
        choices = output.get("choices", []) if isinstance(output, dict) else getattr(output, "choices", [])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})

        # 提取内容（多模态响应的 content 可能是列表）
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
            content = "".join(text_parts)

        # 提取 usage 信息
        usage = response.usage if hasattr(response, "usage") else None
        usage_dict = {
            "prompt_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0
        }

        return {
            "content": content,
            "role": message.get("role", "assistant"),
            "usage": usage_dict,
            "model": "qwen-vl",
            "finish_reason": choice.get("finish_reason", "stop")
        }
