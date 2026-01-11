from typing import Optional, Protocol
from app.schemas.jobs import JobRequest, JobResponse

class ModeHandler(Protocol):
    def execute(self, req: JobRequest, client, platform: str) -> JobResponse: ...

from app.modes.iterate_gemini import IterateGeminiHandler
from app.modes.inpaint_add_imagen import InpaintAddImagenHandler
from app.modes.product_background_editing import ProductBackgroundEditingHandler
from app.modes.outpaint_imagen import OutpaintImagenHandler
from app.modes.mask_edit_imagen import MaskEditImagenHandler
from app.modes.upscale_imagen import UpscaleImagenHandler
from app.modes.try_on import TryOnHandler
from app.modes.product_recontext import ProductRecontextHandler

_HANDLERS = {
    "ITERATE_GEMINI": IterateGeminiHandler(),
    "INPAINT_ADD": InpaintAddImagenHandler(),
    "PRODUCT_BACKGROUND_EDITING": ProductBackgroundEditingHandler(),
    "OUTPAINT_IMAGEN": OutpaintImagenHandler(),
    "MASK_EDIT_IMAGEN": MaskEditImagenHandler(),
    "UPSCALE_IMAGEN": UpscaleImagenHandler(),
    "TRY_ON": TryOnHandler(),
    "PRODUCT_RECONTEXT": ProductRecontextHandler(),
}

def get_handler(mode_id: str) -> Optional[ModeHandler]:
    return _HANDLERS.get(mode_id)
