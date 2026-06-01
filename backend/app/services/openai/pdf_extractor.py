"""
OpenAI PDF extraction through Responses API file inputs.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Mapping, Optional

import httpx

from ._shared import build_async_client, read_field

logger = logging.getLogger(__name__)


PDF_TEMPLATE_LABELS: Dict[str, Dict[str, str]] = {
    "invoice": {
        "name": "Invoice",
        "description": "Extract structured data from invoices",
        "icon": "file-text",
    },
    "form": {
        "name": "Generic Form",
        "description": "Extract data from application forms and contact forms",
        "icon": "file-text",
    },
    "receipt": {
        "name": "Receipt",
        "description": "Extract data from purchase receipts",
        "icon": "receipt",
    },
    "contract": {
        "name": "Contract",
        "description": "Extract key information from contracts and agreements",
        "icon": "file-signature",
    },
    "full-text": {
        "name": "Full Text",
        "description": "Extract full PDF text as Markdown",
        "icon": "file-text",
    },
}


class OpenAIPDFExtractor:
    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs: Any) -> None:
        self.client = build_async_client(
            api_key=api_key,
            base_url=base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3),
            client=kwargs.get("client"),
        )

    async def extract_pdf_data(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        pdf_bytes = await self._resolve_pdf_bytes(reference_images or {}, kwargs)
        template_type = str(kwargs.get("template_type") or "full-text").strip() or "full-text"
        template = PDF_TEMPLATE_LABELS.get(template_type, PDF_TEMPLATE_LABELS["full-text"])
        instructions = self._build_extraction_prompt(
            template_type=template_type,
            prompt=prompt,
            additional_instructions=str(kwargs.get("additional_instructions") or "").strip(),
        )
        response = await self.client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": f"{template_type}.pdf",
                            "file_data": self._pdf_bytes_to_data_url(pdf_bytes),
                        },
                        {
                            "type": "input_text",
                            "text": instructions,
                        },
                    ],
                }
            ],
        )

        output_text = self._extract_output_text(response)
        parsed = self._parse_json_object(output_text)
        if parsed is None:
            return {
                "success": template_type == "full-text",
                "template_type": template_type,
                "template_name": template["name"],
                "data": {"text": output_text} if template_type == "full-text" else {},
                "raw_text": output_text,
                "model_response": output_text,
                **({} if template_type == "full-text" else {"error": "Model did not return JSON object"}),
            }

        return {
            "success": True,
            "template_type": template_type,
            "template_name": template["name"],
            "data": parsed,
            "raw_text": output_text,
        }

    def get_available_templates(self) -> List[Dict[str, str]]:
        return [
            {
                "id": template_id,
                "name": template["name"],
                "description": template["description"],
                "icon": template["icon"],
            }
            for template_id, template in PDF_TEMPLATE_LABELS.items()
        ]

    async def _resolve_pdf_bytes(
        self,
        reference_images: Mapping[str, Any],
        kwargs: Mapping[str, Any],
    ) -> bytes:
        pdf_bytes = reference_images.get("pdf_bytes") or kwargs.get("pdf_bytes")
        if isinstance(pdf_bytes, bytes):
            return pdf_bytes
        if isinstance(pdf_bytes, bytearray):
            return bytes(pdf_bytes)

        pdf_url = str(reference_images.get("pdf_url") or kwargs.get("pdf_url") or "").strip()
        if pdf_url:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()
                return response.content

        raise ValueError("extract_pdf_data requires pdf_bytes or pdf_url for OpenAI PDF extraction.")

    def _build_extraction_prompt(
        self,
        *,
        template_type: str,
        prompt: str,
        additional_instructions: str,
    ) -> str:
        base_prompt = (prompt or "").strip() or "Extract data from this PDF."
        if template_type == "full-text":
            return (
                f"{base_prompt}\n\nReturn the extracted document content as clean Markdown. "
                "Preserve tables as Markdown tables where possible."
            )
        return (
            f"{base_prompt}\n\nTemplate: {template_type}. "
            "Return only one valid JSON object with the extracted fields. "
            "Do not wrap the JSON in markdown."
            + (f"\n\nAdditional instructions: {additional_instructions}" if additional_instructions else "")
        )

    def _extract_output_text(self, response: Any) -> str:
        direct = read_field(response, "output_text", "outputText")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        parts: List[str] = []
        for output in read_field(response, "output") or []:
            for content in read_field(output, "content") or []:
                text = read_field(content, "text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()

    def _parse_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        value = str(text or "").strip()
        if not value:
            return None
        if value.startswith("```"):
            value = value.strip("`").strip()
            if value.lower().startswith("json"):
                value = value[4:].strip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _pdf_bytes_to_data_url(self, pdf_bytes: bytes) -> str:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        return f"data:application/pdf;base64,{encoded}"
