"""
OpenAI 图片编辑器

处理 GPT Image 的图片编辑 / reference image 生成操作。
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx

from ...services.storage.local_provider import (
    DEFAULT_LOCAL_URL_PREFIX,
    resolve_local_public_file_path,
)
from ...utils.attachment_handler import is_base64_url
from ...utils.url_security import get_with_redirect_guard, validate_outbound_http_url
from ._shared import (
    IMAGE_EDIT_ALLOWED_OPTION_KEYS,
    build_async_client,
    call_image_api_with_fanout,
    coerce_openai_image_max_retries,
    coerce_openai_image_timeout,
    elapsed_ms,
    enhance_openai_image_prompt,
    image_response_to_results,
    normalize_image_api_kwargs,
    prepare_kwargs_for_openai_method,
    with_openai_image_client_options,
)

logger = logging.getLogger(__name__)

FileTuple = Tuple[str, bytes, str]


class ImageEditor:
    """
    OpenAI 图片编辑器

    使用 OpenAI Image API 的 /images/edits 语义：
    - image-chat-edit / 图生图：client.images.edit(...)
    - reference_images.raw 可为 data URL、受控存储 URL、HTTP URL、bytes 或附件 dict
    """

    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = kwargs.get("timeout", 120.0)
        self.image_timeout = coerce_openai_image_timeout(kwargs.get("image_timeout"))
        self.image_max_retries = coerce_openai_image_max_retries(kwargs.get("image_max_retries"))
        self.client = build_async_client(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=kwargs.get("max_retries", 3),
            client=kwargs.get("client"),
        )

        logger.info(f"[OpenAI ImageEditor] Initialized with base_url={self.base_url}")

    async def edit_image(
        self,
        prompt: str,
        model: str = "gpt-image-2",
        **kwargs
    ) -> List[Dict[str, Any]]:
        operation_start = time.perf_counter()
        try:
            logger.info(f"[OpenAI ImageEditor] Image edit: model={model}, prompt={prompt[:50]}...")
            references = self._extract_reference_sources(kwargs)
            enhanced_prompt = None
            effective_prompt = prompt
            if kwargs.get("enhance_prompt") or kwargs.get("enhancePrompt"):
                enhance_start = time.perf_counter()
                enhanced_prompt = await enhance_openai_image_prompt(
                    self.client,
                    prompt,
                    model_hint=kwargs.get("enhance_prompt_model") or kwargs.get("enhancePromptModel"),
                    thinking_level=(
                        kwargs.get("enhance_prompt_thinking_level")
                        or kwargs.get("enhancePromptThinkingLevel")
                    ),
                    edit_mode=True,
                    has_reference_images=bool(references),
                )
                if enhanced_prompt:
                    effective_prompt = enhanced_prompt
                logger.info(
                    "[OpenAI ImageEditor] Prompt enhancement phase completed "
                    "(elapsed_ms=%.2f, requested=true, enhanced=%s, enhanced_len=%s)",
                    elapsed_ms(enhance_start),
                    bool(enhanced_prompt),
                    len(enhanced_prompt or ""),
                )

            request_kwargs = self._normalize_edit_kwargs(model, kwargs)
            requested_count = self._requested_image_count(request_kwargs)
            reference_load_start = time.perf_counter()
            image_files = await self._extract_image_files(kwargs, references=references)
            mask_file = await self._extract_mask_file(kwargs)
            reference_bytes = sum(len(item[1]) for item in image_files)
            mask_bytes = len(mask_file[1]) if mask_file is not None else 0
            logger.info(
                "[OpenAI ImageEditor] Reference load completed "
                "(elapsed_ms=%.2f, references=%s, reference_bytes=%s, has_mask=%s, mask_bytes=%s)",
                elapsed_ms(reference_load_start),
                len(image_files),
                reference_bytes,
                mask_file is not None,
                mask_bytes,
            )
            self._log_edit_request_options(
                model=model,
                request_kwargs=request_kwargs,
                prompt=effective_prompt,
                reference_count=len(image_files),
                has_mask=mask_file is not None,
                enhanced_prompt_used=bool(enhanced_prompt),
            )

            api_start = time.perf_counter()
            response = await self._call_edit_image_api(
                prompt=effective_prompt,
                model=model,
                image_files=image_files,
                mask_file=mask_file,
                request_kwargs=request_kwargs,
            )
            logger.info(
                "[OpenAI ImageEditor] Images Edit API completed "
                "(elapsed_ms=%.2f, model=%s, n=%s, size=%s, quality=%s, output_format=%s)",
                elapsed_ms(api_start),
                model,
                request_kwargs.get("n", 1),
                request_kwargs.get("size"),
                request_kwargs.get("quality"),
                request_kwargs.get("output_format"),
            )

            parse_start = time.perf_counter()
            results = self._response_to_results(response, request_kwargs)
            logger.info(
                "[OpenAI ImageEditor] Response conversion completed (elapsed_ms=%.2f, images=%s)",
                elapsed_ms(parse_start),
                len(results),
            )

            if not results:
                # 无任何可用图片(全部腿失败或响应无图像负载)才算硬失败。
                raise RuntimeError("OpenAI image edit response did not contain a usable image payload.")

            if len(results) < requested_count:
                # 部分成功: 扇出为 n=1 的并发腿后, 个别腿可能因上游 502/429 失败。
                # 不丢弃已完成且已计费的编辑图片——返回部分结果并记录警告。
                logger.warning(
                    "[OpenAI ImageEditor] Partial image result: %s/%s images returned "
                    "(model=%s). Some fan-out legs failed upstream; surfacing completed images.",
                    len(results),
                    requested_count,
                    model,
                )

            if enhanced_prompt:
                for result in results:
                    result["enhanced_prompt"] = enhanced_prompt

            logger.info(
                "[OpenAI ImageEditor] Image edited: %s image(s) (total_elapsed_ms=%.2f)",
                len(results),
                elapsed_ms(operation_start),
            )
            return results
        except Exception as exc:
            logger.error(f"[OpenAI ImageEditor] Image edit error: {exc}", exc_info=True)
            raise

    async def _call_edit_image_api(
        self,
        *,
        prompt: str,
        model: str,
        image_files: List[FileTuple],
        mask_file: Optional[FileTuple],
        request_kwargs: Dict[str, Any],
    ) -> Any:
        call_kwargs = dict(request_kwargs)
        if mask_file is not None:
            call_kwargs["mask"] = mask_file
        image_client = self._image_request_client()
        call_kwargs = prepare_kwargs_for_openai_method(image_client.images.edit, call_kwargs)
        count = self._requested_image_count(call_kwargs)

        async def _single(n: int) -> Any:
            # 扇出时每次只请求 1 张; image_files 为不可变 bytes, 可安全跨并发复用。
            single_kwargs = {**call_kwargs, "n": n}
            return await image_client.images.edit(
                model=model,
                prompt=prompt,
                image=image_files,
                **single_kwargs,
            )

        # 详见 call_image_api_with_fanout: 订阅/OAuth 网关不支持原生 n>1, 故扇出为并发 n=1。
        return await call_image_api_with_fanout(_single, count)

    def _normalize_edit_kwargs(self, model: str, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
        return normalize_image_api_kwargs(
            model,
            kwargs,
            allowed_keys=IMAGE_EDIT_ALLOWED_OPTION_KEYS,
        )

    def _response_to_results(self, response: Any, request_kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        return image_response_to_results(response, request_kwargs)

    def _requested_image_count(self, request_kwargs: Mapping[str, Any]) -> int:
        try:
            return max(1, int(request_kwargs.get("n") or 1))
        except (TypeError, ValueError):
            return 1

    def _image_request_client(self):
        return with_openai_image_client_options(
            self.client,
            timeout=self.image_timeout,
            max_retries=self.image_max_retries,
        )

    def _log_edit_request_options(
        self,
        *,
        model: str,
        request_kwargs: Mapping[str, Any],
        prompt: str,
        reference_count: int,
        has_mask: bool,
        enhanced_prompt_used: bool,
    ) -> None:
        logger.info(
            "[OpenAI ImageEditor] Request options: model=%s size=%s n=%s quality=%s "
            "output_format=%s base_url=%s image_timeout=%ss image_max_retries=%s "
            "prompt_len=%s references=%s has_mask=%s enhanced_prompt_used=%s",
            model,
            request_kwargs.get("size"),
            request_kwargs.get("n", 1),
            request_kwargs.get("quality"),
            request_kwargs.get("output_format"),
            self.base_url,
            self.image_timeout,
            self.image_max_retries,
            len(prompt or ""),
            reference_count,
            has_mask,
            enhanced_prompt_used,
        )

    async def _extract_image_files(
        self,
        kwargs: Mapping[str, Any],
        *,
        references: Optional[List[Any]] = None,
    ) -> List[FileTuple]:
        references = references if references is not None else self._extract_reference_sources(kwargs)
        files = []
        for index, source in enumerate(references[:16]):
            content, mime_type = await self._load_image_bytes(source)
            extension = mimetypes.guess_extension(mime_type) or ".png"
            files.append((f"image_{index}{extension}", content, mime_type))

        if not files:
            raise ValueError("At least one reference image is required for OpenAI image editing.")
        return files

    async def _extract_mask_file(self, kwargs: Mapping[str, Any]) -> Optional[FileTuple]:
        reference_images = kwargs.get("reference_images")
        mask_source = None
        if isinstance(reference_images, Mapping):
            mask_source = reference_images.get("mask")
        if mask_source is None:
            mask_source = kwargs.get("mask")
        if not mask_source:
            return None

        content, mime_type = await self._load_image_bytes(mask_source)
        extension = mimetypes.guess_extension(mime_type) or ".png"
        return (f"mask{extension}", content, mime_type)

    def _extract_reference_sources(self, kwargs: Mapping[str, Any]) -> List[Any]:
        reference_images = kwargs.get("reference_images")
        if not reference_images:
            return []
        if isinstance(reference_images, Mapping):
            raw = reference_images.get("raw")
            if isinstance(raw, list):
                return raw
            return [raw] if raw else []
        if isinstance(reference_images, list):
            return reference_images
        return [reference_images]

    async def _load_image_bytes(self, source: Any) -> Tuple[bytes, str]:
        if isinstance(source, Mapping):
            mime_type = self._extract_mime_type(source)
            nested_source = (
                source.get("url")
                or source.get("temp_url")
                or source.get("tempUrl")
                or source.get("raw_url")
                or source.get("rawUrl")
                or source.get("base64_data")
                or source.get("base64Data")
            )
            if not nested_source:
                raise ValueError("Attachment reference did not include image data for OpenAI image editing.")
            content, nested_mime_type = await self._load_image_bytes(nested_source)
            return content, mime_type or nested_mime_type

        if isinstance(source, bytes):
            return source, "image/png"

        if isinstance(source, str):
            value = source.strip()
            if not value:
                raise ValueError("Empty image source is not supported for OpenAI image editing.")
            if is_base64_url(value):
                header, encoded = value.split(",", 1)
                mime_type = self._extract_data_url_mime_type(header) or "image/png"
                return base64.b64decode(encoded), mime_type
            local_path = self._resolve_local_storage_image_path(value)
            if local_path:
                if local_path.exists() and local_path.is_file():
                    mime_type = mimetypes.guess_type(local_path.name)[0] or "image/png"
                    return local_path.read_bytes(), mime_type
                raise ValueError(f"Local storage image file not found for OpenAI image editing: {value[:80]}")
            if value.startswith(("http://", "https://")):
                safe_url = validate_outbound_http_url(value)
                async with httpx.AsyncClient(timeout=min(float(self.timeout), 120.0)) as client:
                    response, _final_url = await get_with_redirect_guard(client, safe_url, max_redirects=5)
                    response.raise_for_status()
                    mime_type = response.headers.get("content-type", "").split(";", 1)[0] or ""
                    if not mime_type.startswith("image/"):
                        guessed_type = mimetypes.guess_type(urlparse(_final_url).path)[0] or ""
                        mime_type = guessed_type if guessed_type.startswith("image/") else ""
                    if not mime_type:
                        raise ValueError("OpenAI image editing reference URL did not return an image content type.")
                    return response.content, mime_type
            try:
                return base64.b64decode(value, validate=True), "image/png"
            except Exception as exc:
                raise ValueError(f"Unsupported image source string for OpenAI image editing: {value[:40]}") from exc

        raise ValueError(f"Unsupported image source type for OpenAI image editing: {type(source).__name__}")

    def _resolve_local_storage_image_path(self, value: str):
        candidates = [value, unquote(value)]
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.path:
            candidates.extend([parsed.path, unquote(parsed.path)])

        for candidate in candidates:
            if not candidate.startswith(f"{DEFAULT_LOCAL_URL_PREFIX}/"):
                continue
            local_path = (
                resolve_local_public_file_path(candidate)
                or resolve_local_public_file_path(unquote(candidate))
            )
            if local_path:
                return local_path
        return None

    def _extract_mime_type(self, source: Mapping[str, Any]) -> Optional[str]:
        value = (
            source.get("mime_type")
            or source.get("mimeType")
            or source.get("content_type")
            or source.get("contentType")
        )
        if isinstance(value, str) and value.startswith("image/"):
            return value
        return None

    def _extract_data_url_mime_type(self, header: str) -> Optional[str]:
        if not header.startswith("data:"):
            return None
        mime_type = header[5:].split(";", 1)[0]
        return mime_type if mime_type.startswith("image/") else None
