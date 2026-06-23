"""Gemini native image recontext service.

Product recontext used to have a dedicated preview endpoint. The supported
migration path now uses Gemini native image editing through chat mode with the
source image plus a scene prompt.
"""

import asyncio
import base64
import hashlib
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.genai import types as genai_types

from ..client_pool import get_client_pool
from ....core.sdk_executor import run_in_sdk_thread
from ....utils.attachment_handler import is_base64_url

logger = logging.getLogger(__name__)


class GeminiRecontextImageService:
    """Recontext images with Gemini image models using official chat-mode editing."""

    _RECONTEXT_INSTRUCTIONS = (
        "Recontext the provided subject or product into the requested scene. "
        "This is not a mask-based background swap; create a new scene context "
        "around the source subject instead of describing a background-only edit. "
        "Preserve the subject identity, shape, color, material, logos, text, "
        "and fine details as much as the model allows. The surrounding context, "
        "surface, lighting, atmosphere, camera framing, and composition may change "
        "to match the requested recontextualization. "
        "Do not invent extra products or alter the product design unless the "
        "user explicitly asks for that. If the request only says to replace or "
        "change the background without naming a scene, choose a clean, bright, "
        "commercial lifestyle background that naturally fits the subject. "
        "Generate image output directly; do not answer with text only or ask "
        "clarifying questions."
    )

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        use_vertex: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None,
        credentials: Optional[Any] = None,
        http_options: Optional[Any] = None,
        client: Optional[Any] = None,
        **_: Any,
    ) -> None:
        self._api_key = api_key
        self._use_vertex = use_vertex
        self._project = project
        self._location = location
        self._credentials = credentials
        self._http_options = http_options
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        return get_client_pool().get_client(
            api_key=self._api_key,
            vertexai=self._use_vertex,
            project=self._project,
            location=self._location,
            credentials=self._credentials,
            http_options=self._http_options,
        )

    @classmethod
    def build_recontext_prompt(cls, prompt: str, number_of_images: int = 1) -> str:
        user_prompt = str(prompt or "").strip()
        parts = [cls._RECONTEXT_INSTRUCTIONS]
        if number_of_images > 1:
            parts.append(
                f"Return exactly {number_of_images} separate image parts in this one response. "
                f"For each numbered variation 1 through {number_of_images}, write a very short title, "
                "then generate one separate image immediately after that title. "
                f"Do not stop before producing {number_of_images} image parts. "
                "Keep text concise and do not add text inside the generated images."
            )
        if user_prompt:
            parts.append(f"User request:\n{user_prompt}")
        return "\n\n".join(parts)

    def _normalize_reference_items(self, reference_images: Dict[str, Any]) -> List[Any]:
        raw = reference_images.get("raw") if isinstance(reference_images, dict) else None
        if raw is None:
            return []
        return raw if isinstance(raw, list) else [raw]

    def _part_from_bytes(self, data: bytes, mime_type: str) -> Any:
        try:
            return genai_types.Part.from_bytes(data=data, mime_type=mime_type)
        except AttributeError:
            return genai_types.Part(inline_data=genai_types.Blob(data=data, mime_type=mime_type))

    def _part_from_reference_item(self, item: Any, user_id: Optional[str] = None) -> Optional[Any]:
        if isinstance(item, dict):
            if item.get("google_file_uri"):
                return genai_types.Part(file_data=genai_types.FileData(
                    file_uri=item["google_file_uri"],
                    mime_type=item.get("mime_type", "image/png"),
                ))
            item = item.get("url") or item.get("base64_data") or item.get("temp_url")

        if not isinstance(item, str):
            return None

        text = item.strip()
        if not text:
            return None

        if text.startswith("/api/storage/local-files/"):
            from ...storage.local_provider import resolve_local_public_file_path_for_user
            local_path = resolve_local_public_file_path_for_user(text, user_id)
            if not local_path or not local_path.exists():
                raise ValueError(f"Local file not found: {text}")
            mime_type = mimetypes.guess_type(str(local_path))[0] or "image/png"
            return self._part_from_bytes(local_path.read_bytes(), mime_type)

        if text.startswith("/") or text.startswith("file://") or Path(text).expanduser().exists():
            # CANON-027/028: legit local references arrive as allow-rooted
            # /api/storage/local-files/ URLs (handled above via
            # resolve_local_public_file_path). A raw absolute / file:// path is a
            # local-file-read vector and is denied rather than read off disk.
            raise ValueError(
                "Local reference must be an /api/storage/local-files/ URL, not a raw filesystem path"
            )

        if is_base64_url(text):
            match = re.match(r"^data:(.*?);base64,(.*)$", text)
            if not match:
                return None
            mime_type = match.group(1) or "image/png"
            return self._part_from_bytes(base64.b64decode(match.group(2)), mime_type)

        compact = text.replace("\n", "").replace("\r", "")
        if len(compact) >= 64 and len(compact) % 4 == 0 and re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
            return self._part_from_bytes(base64.b64decode(compact), "image/png")

        return None

    def _build_message(
        self,
        prompt: str,
        reference_images: Dict[str, Any],
        number_of_images: int = 1,
        user_id: Optional[str] = None,
    ) -> List[Any]:
        image_parts = []
        for item in self._normalize_reference_items(reference_images):
            part = self._part_from_reference_item(item, user_id)
            if part is not None:
                image_parts.append(part)

        if not image_parts:
            raise ValueError("image-recontext requires at least one source image")

        # Official Gemini image editing examples send the prompt and image to a
        # chat session. Keep the prompt first so the model has concrete edit
        # instructions before reading the source image.
        return [
            genai_types.Part.from_text(text=self.build_recontext_prompt(prompt, number_of_images)),
            *image_parts,
        ]

    def _build_config(self, kwargs: Dict[str, Any]) -> Any:
        if not self._use_vertex:
            unsupported_output_keys = [
                key for key in ("output_mime_type", "output_compression_quality")
                if kwargs.get(key) is not None
            ]
            if unsupported_output_keys:
                raise ValueError(
                    f"{', '.join(unsupported_output_keys)} parameter is not supported in Gemini API"
                )

        # The official Gemini native image editing path supports modality
        # settings only. Do not pass image_config, temperature, max tokens, or
        # safety overrides here; Vertex can return text-only responses when
        # editing is sent through the generation-shaped config.
        return genai_types.GenerateContentConfig(
            response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
        )

    def _coerce_image_bytes(self, image_bytes: Any) -> Optional[bytes]:
        if image_bytes is None:
            return None
        if isinstance(image_bytes, str):
            data_str = image_bytes
            if is_base64_url(data_str):
                _, data_str = data_str.split(",", 1)
            return base64.b64decode(data_str)
        if isinstance(image_bytes, bytes):
            return image_bytes
        if isinstance(image_bytes, bytearray):
            return bytes(image_bytes)
        if isinstance(image_bytes, memoryview):
            return image_bytes.tobytes()
        if isinstance(image_bytes, list):
            return bytes(image_bytes)
        return None

    def _extract_images(self, response: Any, output_mime_type: str = "image/png") -> List[Dict[str, Any]]:
        images: List[Dict[str, Any]] = []
        seen_payloads = set()

        def append_from_parts(parts: Any) -> None:
            for part in parts or []:
                inline_data = getattr(part, "inline_data", None)
                image_bytes = getattr(inline_data, "data", None) if inline_data is not None else None
                try:
                    image_bytes = self._coerce_image_bytes(image_bytes)
                except Exception as exc:
                    logger.warning("[GeminiRecontextImageService] Failed to decode image part: %s", exc)
                    continue
                if not image_bytes:
                    continue
                mime_type = getattr(inline_data, "mime_type", None) or output_mime_type
                payload_key = (
                    mime_type,
                    hashlib.sha256(image_bytes).hexdigest(),
                )
                if payload_key in seen_payloads:
                    continue
                seen_payloads.add(payload_key)
                images.append({
                    "url": f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}",
                    "mime_type": mime_type,
                    "index": len(images),
                    "size": len(image_bytes),
                })

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            append_from_parts(getattr(content, "parts", None))
        append_from_parts(getattr(response, "parts", None))
        return images

    def _describe_response_without_images(self, response: Any) -> str:
        texts: List[str] = []
        finish_reasons: List[str] = []

        def collect_parts(parts: Any) -> None:
            for part in parts or []:
                text = getattr(part, "text", None)
                if text:
                    compact = " ".join(str(text).split())
                    if compact:
                        texts.append(compact[:240])

        for candidate in getattr(response, "candidates", None) or []:
            reason = getattr(candidate, "finish_reason", None)
            if reason is not None:
                finish_reasons.append(str(reason))
            content = getattr(candidate, "content", None)
            collect_parts(getattr(content, "parts", None))
        collect_parts(getattr(response, "parts", None))

        parts = []
        if finish_reasons:
            parts.append(f"finish_reason={','.join(finish_reasons)}")
        if texts:
            parts.append(f"text={texts[0]}")
        return "; ".join(parts) if parts else "response had no candidate parts"

    async def edit_image(
        self,
        *,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        client = self._get_client()
        output_mime_type = kwargs.get("output_mime_type") or "image/png"
        number_of_images = max(1, min(10, int(kwargs.get("number_of_images") or kwargs.get("numberOfImages") or 1)))

        message = self._build_message(prompt, reference_images, number_of_images, user_id=user_id)
        config = self._build_config(kwargs)
        chat = client.chats.create(model=model, config=config)
        response = await run_in_sdk_thread(
            chat.send_message,
            message=message,
        )
        images = self._extract_images(response, output_mime_type)

        if not images:
            response_summary = self._describe_response_without_images(response)
            logger.error(
                "[GeminiRecontextImageService] Gemini recontext returned no image parts: %s",
                response_summary,
            )
            raise ValueError(f"Gemini recontext did not return an image. {response_summary}")
        images = images[:number_of_images]
        if len(images) < number_of_images:
            warning_text = f"模型返回 {len(images)}/{number_of_images} 张图片，已显示实际返回结果。"
            logger.warning(
                "[GeminiRecontextImageService] %s",
                warning_text,
            )
            images[0]["text"] = warning_text
        for index, image in enumerate(images):
            image["index"] = index
        logger.info("[GeminiRecontextImageService] Generated %d image(s) with model=%s", len(images), model)
        return images
