from typing import List
from google.genai import types
from app.schemas.jobs import JobRequest, JobResponse
from app.schemas.images import ImageB64
from app.modes._img_utils import b64_to_bytes, bytes_to_b64
from app.core.ssot_loader import load_ssot

def _part(img: ImageB64) -> types.Part:
    return types.Part.from_bytes(data=b64_to_bytes(img.data_b64), mime_type=img.mime_type)

class TryOnHandler:
    mode_id = "TRY_ON"

    def execute(self, req: JobRequest, client, platform: str) -> JobResponse:
        if platform != "vertex":
            raise ValueError("TRY_ON is Vertex-only")

        ssot = load_ssot()["modes"][self.mode_id]
        model = req.model or ssot["default_model"]

        if not req.person_image:
            raise ValueError("person_image is required for TRY_ON")
        if not req.product_images:
            raise ValueError("product_images is required for TRY_ON")

        p = req.params or {}
        n = int(p.get("number_of_images", 1))

        resp = client.models.recontext_image(
            model=model,
            person_image=_part(req.person_image),
            product_images=[_part(x) for x in req.product_images],
            config=types.RecontextImageConfig(number_of_images=n),
        )

        imgs: List[ImageB64] = []
        for gi in resp.generated_images[:n]:
            imgs.append(ImageB64(data_b64=bytes_to_b64(gi.image.image_bytes), mime_type="image/png"))

        return JobResponse(mode_id=self.mode_id, model=model, images=imgs)
