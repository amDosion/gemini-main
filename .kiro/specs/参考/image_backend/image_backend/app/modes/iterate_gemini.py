from typing import Any, Dict, List
from google.genai import types
from app.schemas.jobs import JobRequest, JobResponse
from app.schemas.images import ImageB64
from app.modes._img_utils import b64_to_bytes, bytes_to_b64
from app.core.ssot_loader import load_ssot

class IterateGeminiHandler:
    mode_id = "ITERATE_GEMINI"

    def execute(self, req: JobRequest, client, platform: str) -> JobResponse:
        ssot = load_ssot()["modes"][self.mode_id]
        model = req.model or ssot["default_model"]

        if not req.prompt:
            raise ValueError("prompt is required for ITERATE_GEMINI")

        contents: List[Any] = [req.prompt]
        if req.image:
            contents.append(
                types.Part.from_bytes(
                    data=b64_to_bytes(req.image.data_b64),
                    mime_type=req.image.mime_type
                )
            )

        p = req.params or {}
        cfg_kwargs: Dict[str, Any] = {}

        image_cfg_in = p.get("image_config") or {}
        image_cfg = {}

        if "aspect_ratio" in image_cfg_in:
            image_cfg["aspect_ratio"] = image_cfg_in["aspect_ratio"]
        if "image_size" in image_cfg_in:
            image_cfg["image_size"] = image_cfg_in["image_size"]

        if image_cfg:
            cfg_kwargs["image_config"] = types.ImageConfig(**image_cfg)

        for k in ("temperature", "seed", "top_p", "top_k", "max_output_tokens", "candidate_count"):
            if k in p:
                cfg_kwargs[k] = p[k]

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            **cfg_kwargs
        )

        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        out_images: List[ImageB64] = []
        out_text = getattr(resp, "text", None)

        candidates = getattr(resp, "candidates", []) or []
        if candidates:
            parts = candidates[0].content.parts
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    mime = getattr(inline, "mime_type", None) or "image/png"
                    out_images.append(
                        ImageB64(data_b64=bytes_to_b64(inline.data), mime_type=mime)
                    )

        return JobResponse(mode_id=self.mode_id, model=model, text=out_text, images=out_images)
