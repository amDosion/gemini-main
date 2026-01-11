from typing import List
from google.genai import types
from app.schemas.jobs import JobRequest, JobResponse
from app.schemas.images import ImageB64
from app.modes._img_utils import b64_to_bytes, bytes_to_b64
from app.core.ssot_loader import load_ssot

def _img(data_b64: str, mime: str) -> types.Image:
    return types.Image.from_bytes(data=b64_to_bytes(data_b64), mime_type=mime)

class UpscaleImagenHandler:
    mode_id = "UPSCALE_IMAGEN"

    def execute(self, req: JobRequest, client, platform: str) -> JobResponse:
        if platform != "vertex":
            raise ValueError("UPSCALE_IMAGEN is Vertex-only")

        ssot = load_ssot()["modes"][self.mode_id]
        model = req.model or ssot["default_model"]

        if not req.image:
            raise ValueError("image is required for UPSCALE_IMAGEN")

        p = req.params or {}
        upscale_factor = p.get("upscale_factor", "x2")
        out_mime = p.get("output_mime_type", "image/png")

        img = _img(req.image.data_b64, req.image.mime_type)

        resp = client.models.upscale_image(
            model=model,
            image=img,
            upscale_factor=upscale_factor,
            config=types.UpscaleImageConfig(output_mime_type=out_mime),
        )

        imgs: List[ImageB64] = []
        if getattr(resp, "generated_images", None):
            gi = resp.generated_images[0]
            imgs.append(ImageB64(data_b64=bytes_to_b64(gi.image.image_bytes), mime_type=out_mime))

        return JobResponse(mode_id=self.mode_id, model=model, images=imgs)
