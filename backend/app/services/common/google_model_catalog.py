"""
Google/Vertex static model catalog.

Single source of truth for Google family static model IDs used by:
- models router (unified model response)
- vertex-ai config router (verification fallback list)
"""

from typing import List

# Imagen text-to-image models (pure generation)
IMAGEN_GENERATE_MODELS: List[str] = [
    "imagen-3.0-generate-001",
    "imagen-3.0-generate-002",
    "imagen-3.0-fast-generate-001",
    "imagen-4.0-generate-preview",
    "imagen-4.0-ultra-generate-preview",
    "imagen-4.0-generate-preview-05-20",
    "imagen-4.0-ultra-generate-preview-05-20",
    "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-001",
    "imagen-4.0-fast-generate-001",
]

# Imagen edit-capable models
IMAGEN_EDIT_MODELS: List[str] = [
    "imagen-3.0-capability-001",
    "imagen-4.0-ingredients-preview",
]

# Imagen upscale models
IMAGE_UPSCALE_MODELS: List[str] = [
    "imagen-4.0-upscale-preview",
]

# Segmentation models
IMAGE_SEGMENTATION_MODELS: List[str] = [
    "image-segmentation-001",
]

# Virtual try-on models
VIRTUAL_TRY_ON_MODELS: List[str] = [
    "virtual-try-on-001",
    "virtual-try-on-preview-08-04",
]

# Product recontext models
PRODUCT_RECONTEXT_MODELS: List[str] = [
    "imagen-product-recontext-preview-06-30",
]

# Veo video models
VEO_VIDEO_MODELS: List[str] = [
    "veo-2.0-generate-001",
    "veo-3.0-generate-preview",
    "veo-3.0-fast-generate-preview",
    "veo-3.0-generate-001",
    "veo-3.0-fast-generate-001",
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
]


def get_static_google_vertex_models() -> List[str]:
    """
    Unified static model IDs for Google + Vertex capability merge.
    """
    ordered = (
        IMAGEN_GENERATE_MODELS
        + IMAGEN_EDIT_MODELS
        + IMAGE_UPSCALE_MODELS
        + IMAGE_SEGMENTATION_MODELS
        + VIRTUAL_TRY_ON_MODELS
        + PRODUCT_RECONTEXT_MODELS
        + VEO_VIDEO_MODELS
    )
    deduped: list[str] = []
    seen: set[str] = set()
    for model_id in ordered:
        if model_id in seen:
            continue
        seen.add(model_id)
        deduped.append(model_id)
    return deduped
