from typing import Any, Dict, List
import requests

from app.core.config import settings
from app.core.vertex_auth import get_adc_token
from app.core.ssot_loader import load_ssot
from app.schemas.jobs import JobRequest, JobResponse
from app.schemas.images import ImageB64

class ProductRecontextHandler:
    mode_id = "PRODUCT_RECONTEXT"

    def execute(self, req: JobRequest, client, platform: str) -> JobResponse:
        if platform != "vertex":
            raise ValueError("PRODUCT_RECONTEXT is Vertex-only")

        ssot = load_ssot()["modes"][self.mode_id]
        model_id = req.model or ssot["default_model"]

        if not req.product_images or len(req.product_images) == 0:
            raise ValueError("product_images is required for PRODUCT_RECONTEXT (1~3 images)")
        if len(req.product_images) > 3:
            raise ValueError("PRODUCT_RECONTEXT supports up to 3 product images")

        prompt = req.prompt
        p = req.params or {}

        parameters: Dict[str, Any] = {}
        for key in (
            "addWatermark",
            "enhancePrompt",
            "personGeneration",
            "safetySetting",
            "sampleCount",
            "seed",
            "storageUri",
        ):
            if key in p and p[key] is not None:
                parameters[key] = p[key]

        if "outputOptions" in p and isinstance(p["outputOptions"], dict):
            parameters["outputOptions"] = p["outputOptions"]

        product_images_payload = []
        for img in req.product_images:
            product_images_payload.append({"image": {"bytesBase64Encoded": img.data_b64}})

        instance: Dict[str, Any] = {"productImages": product_images_payload}
        if prompt:
            instance["prompt"] = prompt

        body: Dict[str, Any] = {"instances": [instance]}
        if parameters:
            body["parameters"] = parameters

        if not settings.project:
            raise ValueError("Missing GOOGLE_CLOUD_PROJECT")
        if not settings.location:
            raise ValueError("Missing GOOGLE_CLOUD_LOCATION")

        url = (
            f"https://{settings.location}-aiplatform.googleapis.com/v1/"
            f"projects/{settings.project}/locations/{settings.location}/publishers/google/models/{model_id}:predict"
        )

        token, _ = get_adc_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        r = requests.post(url, headers=headers, json=body, timeout=120)
        if r.status_code >= 400:
            raise ValueError(f"Vertex predict failed: {r.status_code} {r.text}")

        data = r.json()
        preds = data.get("predictions", []) or []
        if not preds:
            raise ValueError("No predictions returned. (If storageUri set, read outputs from GCS.)")

        out_images: List[ImageB64] = []
        for pred in preds:
            b64 = pred.get("bytesBase64Encoded")
            mime = pred.get("mimeType", "image/png")
            if b64:
                out_images.append(ImageB64(data_b64=b64, mime_type=mime))

        return JobResponse(mode_id=self.mode_id, model=model_id, images=out_images)
