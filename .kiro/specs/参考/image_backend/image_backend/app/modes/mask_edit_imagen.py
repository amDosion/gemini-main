from typing import List
from google.genai import types
from google.genai.types import RawReferenceImage, MaskReferenceImage, MaskReferenceConfig
from app.schemas.jobs import JobRequest, JobResponse
from app.schemas.images import ImageB64
from app.modes._img_utils import b64_to_bytes, bytes_to_b64
from app.core.ssot_loader import load_ssot

def _img(data_b64: str, mime: str) -> types.Image:
    return types.Image.from_bytes(data=b64_to_bytes(data_b64), mime_type=mime)

class MaskEditImagenHandler:
    mode_id = "MASK_EDIT_IMAGEN"

    def execute(self, req: JobRequest, client, platform: str) -> JobResponse:
        if platform != "vertex":
            raise ValueError("MASK_EDIT_IMAGEN is Vertex-only")

        ssot = load_ssot()["modes"][self.mode_id]
        model = req.model or ssot["default_model"]

        if not req.prompt:
            raise ValueError("prompt is required for MASK_EDIT_IMAGEN")
        if not req.image:
            raise ValueError("image is required for MASK_EDIT_IMAGEN")

        p = req.params or {}
        mask_mode = p.get("mask_mode", "MASK_MODE_USER_PROVIDED")
        mask_dilation = float(p.get("mask_dilation", 0.03))
        n = int(p.get("number_of_images", 1))
        out_mime = p.get("output_mime_type", "image/png")
        edit_mode = p.get("edit_mode", "EDIT_MODE_INPAINT_INSERTION")

        base = _img(req.image.data_b64, req.image.mime_type)
        raw_ref = RawReferenceImage(reference_id=1, reference_image=base)

        if mask_mode == "MASK_MODE_USER_PROVIDED":
            if not req.mask:
                raise ValueError("mask required when mask_mode=MASK_MODE_USER_PROVIDED")
            mask_img = _img(req.mask.data_b64, req.mask.mime_type)
            mask_ref = MaskReferenceImage(
                reference_id=2,
                reference_image=mask_img,
                config=MaskReferenceConfig(mask_mode=mask_mode, mask_dilation=mask_dilation),
            )
        else:
            mask_ref = MaskReferenceImage(
                reference_id=2,
                config=MaskReferenceConfig(mask_mode=mask_mode, mask_dilation=mask_dilation),
            )

        resp = client.models.edit_image(
            model=model,
            prompt=req.prompt,
            reference_images=[raw_ref, mask_ref],
            config=types.EditImageConfig(
                edit_mode=edit_mode,
                number_of_images=n,
                output_mime_type=out_mime,
            ),
        )

        imgs: List[ImageB64] = []
        for gi in resp.generated_images[:n]:
            imgs.append(ImageB64(data_b64=bytes_to_b64(gi.image.image_bytes), mime_type=out_mime))

        return JobResponse(mode_id=self.mode_id, model=model, images=imgs)
