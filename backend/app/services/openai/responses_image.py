"""
OpenAI Responses API image generation/editing coordinator.

This is the provider-level advanced path for GPT Image workflows that need
conversation state (`previous_response_id`) or mixed text/image inputs.
Single-turn generation/editing remains handled by the Image API by default.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Mapping, Optional

from ._shared import (
    build_async_client,
    enhance_openai_image_prompt,
    is_gpt_image_2_model,
    normalize_image_api_kwargs,
    responses_image_response_to_results,
    to_data_url,
)
from .image_editor import ImageEditor


RESPONSES_IMAGE_SIZE_ALLOWLIST = {"1024x1024", "1024x1536", "1536x1024", "auto"}


class ResponsesImageService:
    """Generate or edit images through `responses.create(..., tools=[image_generation])`."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        *,
        image_editor: ImageEditor,
        **kwargs: Any,
    ) -> None:
        self.client = build_async_client(
            api_key=api_key,
            base_url=base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3),
            client=kwargs.get("client"),
        )
        self.image_editor = image_editor

    async def generate_image(
        self,
        prompt: str,
        *,
        image_model: str,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        request_kwargs = normalize_image_api_kwargs(image_model, kwargs)
        enhanced_prompt = await self._maybe_enhance_prompt(
            prompt,
            kwargs,
            edit_mode=False,
            has_reference_images=False,
        )
        return await self._create_image_generation_response(
            prompt=enhanced_prompt or prompt,
            image_model=image_model,
            action="generate",
            request_kwargs=request_kwargs,
            kwargs=kwargs,
            enhanced_prompt=enhanced_prompt,
        )

    async def edit_image(
        self,
        prompt: str,
        *,
        image_model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        request_kwargs = normalize_image_api_kwargs(image_model, kwargs)
        references = self.image_editor._extract_reference_sources(  # noqa: SLF001 - shared provider loader
            {"reference_images": reference_images or {}}
        )
        mask_url = await self._extract_mask_data_url(reference_images or {}, kwargs)
        if not references and not mask_url:
            raise ValueError("At least one reference image is required for OpenAI image editing.")
        enhanced_prompt = await self._maybe_enhance_prompt(
            prompt,
            kwargs,
            edit_mode=True,
            has_reference_images=bool(references or mask_url),
        )
        return await self._create_image_generation_response(
            prompt=enhanced_prompt or prompt,
            image_model=image_model,
            action="edit",
            request_kwargs=request_kwargs,
            kwargs=kwargs,
            references=references,
            mask_url=mask_url,
            enhanced_prompt=enhanced_prompt,
        )

    async def _create_image_generation_response(
        self,
        *,
        prompt: str,
        image_model: str,
        action: str,
        request_kwargs: Dict[str, Any],
        kwargs: Mapping[str, Any],
        references: Optional[List[Any]] = None,
        mask_url: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        count = self._requested_image_count(request_kwargs)
        single_request_kwargs = dict(request_kwargs)
        single_request_kwargs.pop("n", None)

        concurrency = min(count, 4)
        semaphore = asyncio.Semaphore(concurrency)

        async def generate_one() -> List[Dict[str, Any]]:
            async with semaphore:
                response = await self._call_responses_api(
                    prompt=prompt,
                    image_model=image_model,
                    action=action,
                    request_kwargs=single_request_kwargs,
                    kwargs=kwargs,
                    references=references or [],
                    mask_url=mask_url,
                )
            return responses_image_response_to_results(
                response,
                output_format=single_request_kwargs.get("output_format"),
            )

        batches = await asyncio.gather(*(generate_one() for _ in range(count)))
        results = [item for batch in batches for item in batch]
        if not results:
            raise RuntimeError("OpenAI Responses image response did not contain a usable image payload.")
        if enhanced_prompt:
            for result in results:
                result["enhanced_prompt"] = enhanced_prompt
        return results

    async def _maybe_enhance_prompt(
        self,
        prompt: str,
        kwargs: Mapping[str, Any],
        *,
        edit_mode: bool,
        has_reference_images: bool,
    ) -> Optional[str]:
        if not (kwargs.get("enhance_prompt") or kwargs.get("enhancePrompt")):
            return None
        return await enhance_openai_image_prompt(
            self.client,
            prompt,
            model_hint=kwargs.get("enhance_prompt_model") or kwargs.get("enhancePromptModel"),
            thinking_level=(
                kwargs.get("enhance_prompt_thinking_level")
                or kwargs.get("enhancePromptThinkingLevel")
            ),
            edit_mode=edit_mode,
            has_reference_images=has_reference_images,
        )

    async def _call_responses_api(
        self,
        *,
        prompt: str,
        image_model: str,
        action: str,
        request_kwargs: Mapping[str, Any],
        kwargs: Mapping[str, Any],
        references: List[Any],
        mask_url: Optional[str],
    ) -> Any:
        responses_model = self._resolve_responses_model(kwargs)
        tool = self._build_image_generation_tool(
            image_model=image_model,
            action=action,
            request_kwargs=request_kwargs,
            mask_url=mask_url,
        )
        request: Dict[str, Any] = {
            "model": responses_model,
            "input": await self._build_input(prompt, references),
            "tools": [tool],
        }
        previous_response_id = self._resolve_previous_response_id(kwargs)
        if previous_response_id:
            request["previous_response_id"] = previous_response_id
        return await self.client.responses.create(**request)

    async def _build_input(self, prompt: str, references: List[Any]) -> Any:
        if not references:
            return prompt

        content: List[Dict[str, Any]] = [
            {
                "type": "input_text",
                "text": prompt,
            }
        ]
        for source in references[:16]:
            content.append(
                {
                    "type": "input_image",
                    "image_url": await self._image_source_to_data_url(source),
                    "detail": "high",
                }
            )
        return [
            {
                "role": "user",
                "content": content,
            }
        ]

    def _build_image_generation_tool(
        self,
        *,
        image_model: str,
        action: str,
        request_kwargs: Mapping[str, Any],
        mask_url: Optional[str],
    ) -> Dict[str, Any]:
        tool: Dict[str, Any] = {
            "type": "image_generation",
            "action": action,
            "model": image_model,
        }
        for key in (
            "quality",
            "background",
            "moderation",
            "output_format",
            "output_compression",
            "partial_images",
            "input_fidelity",
        ):
            value = request_kwargs.get(key)
            if value is not None:
                tool[key] = value

        size = str(request_kwargs.get("size") or "").strip().lower()
        if size in RESPONSES_IMAGE_SIZE_ALLOWLIST:
            tool["size"] = size
        elif is_gpt_image_2_model(image_model):
            tool["size"] = "auto"

        if mask_url:
            tool["input_image_mask"] = {"image_url": mask_url}
        return tool

    async def _extract_mask_data_url(
        self,
        reference_images: Mapping[str, Any],
        kwargs: Mapping[str, Any],
    ) -> Optional[str]:
        mask_source = reference_images.get("mask") or kwargs.get("mask")
        if not mask_source:
            return None
        return await self._image_source_to_data_url(mask_source)

    async def _image_source_to_data_url(self, source: Any) -> str:
        if isinstance(source, str) and source.strip().startswith("data:image/"):
            return source.strip()
        content, mime_type = await self.image_editor._load_image_bytes(source)  # noqa: SLF001
        return to_data_url(content, mime_type)

    def _requested_image_count(self, request_kwargs: Mapping[str, Any]) -> int:
        try:
            return max(1, min(int(request_kwargs.get("n") or 1), 10))
        except (TypeError, ValueError):
            return 1

    def _resolve_responses_model(self, kwargs: Mapping[str, Any]) -> str:
        value = str(
            kwargs.get("openai_responses_model")
            or kwargs.get("openaiResponsesModel")
            or ""
        ).strip()
        return value or "gpt-5.4-mini"

    def _resolve_previous_response_id(self, kwargs: Mapping[str, Any]) -> Optional[str]:
        value = str(
            kwargs.get("openai_previous_response_id")
            or kwargs.get("openaiPreviousResponseId")
            or kwargs.get("previous_response_id")
            or ""
        ).strip()
        return value or None
