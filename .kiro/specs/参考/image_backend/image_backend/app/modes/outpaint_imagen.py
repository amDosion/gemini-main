from typing import List
from google.genai import types
from google.genai.types import RawReferenceImage, MaskReferenceImage, MaskReferenceConfig
from app.schemas.jobs import JobRequest, JobResponse
from app.schemas.images import ImageB64
from app.modes._img_utils import b64_to_bytes, bytes_to_b64
from app.core.ssot_loader import load_ssot

def _img(data_b64: str, mime: str) -> types.Image:
    return types.Image.from_bytes(data=b64_to_bytes(data_b64), mime_type=mime)

class OutpaintImagenHandler:
    mode_id = "OUTPAINT_IMAGEN"

    def execute(self, req: JobRequest, client, platform: str) -> JobResponse:
        if platform != "vertex":
            raise ValueError("OUTPAINT_IMAGEN is Vertex-only")

        ssot = load_ssot()["modes"][self.mode_id]
        model = req.model or ssot["default_model"]

        if not req.image:
            raise ValueError("image is required for OUTPAINT_IMAGEN")
        if not req.mask:
            raise ValueError("mask is required for OUTPAINT_IMAGEN")

        p = req.params or {}
        mask_dilation = float(p.get("mask_dilation", 0.03))
        n = int(p.get("number_of_images", 1))
        out_mime = p.get("output_mime_type", "image/png")

        base = _img(req.image.data_b64, req.image.mime_type)
        mask = _img(req.mask.data_b64, req.mask.mime_type)

        resp = client.models.edit_image(
            model=model,
            prompt=req.prompt or "",
            reference_images=[
                RawReferenceImage(reference_id=1, reference_image=base),
                MaskReferenceImage(
                    reference_id=2,
                    reference_image=mask,
                    config=MaskReferenceConfig(mask_mode="MASK_MODE_USER_PROVIDED", mask_dilation=mask_dilation),
                ),
            ],
            config=types.EditImageConfig(
                edit_mode="EDIT_MODE_OUTPAINT",
                number_of_images=n,
                output_mime_type=out_mime,
            ),
        )

        imgs: List[ImageB64] = []
        for gi in resp.generated_images[:n]:
            imgs.append(ImageB64(data_b64=bytes_to_b64(gi.image.image_bytes), mime_type=out_mime))

        return JobResponse(mode_id=self.mode_id, model=model, images=imgs)
