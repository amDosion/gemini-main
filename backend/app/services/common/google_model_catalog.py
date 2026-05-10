"""Google/Vertex static model catalog loaded from JSON."""

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Dict, List


_CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "google_vertex_models.json"


@lru_cache(maxsize=1)
def _load_catalog() -> Dict[str, Any]:
    with _CATALOG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    models = data.get("models")
    if not isinstance(models, list):
        raise ValueError(f"Invalid Google/Vertex model catalog: {_CATALOG_PATH}")

    return data


def get_google_vertex_static_model_entries() -> List[Dict[str, Any]]:
    """Return the JSON-backed static Google/Vertex model entries."""
    return list(_load_catalog()["models"])


def _model_ids_for_family(family: str) -> List[str]:
    return [
        str(entry["id"])
        for entry in get_google_vertex_static_model_entries()
        if family in (entry.get("families") or [])
    ]


def get_static_google_vertex_model_ids_for_family(family: str) -> List[str]:
    """Return static model IDs explicitly marked with a model family."""
    return _model_ids_for_family(family)


def get_static_google_vertex_model_ids_for_mode(mode: str) -> List[str]:
    """Return static model IDs explicitly marked as available for an app mode."""
    return [
        str(entry["id"])
        for entry in get_google_vertex_static_model_entries()
        if mode in (entry.get("modes") or [])
    ]


DEPRECATED_GOOGLE_VERTEX_IMAGE_MODEL_MIGRATIONS: Dict[str, str] = {
    "gemini-2.0-flash-image-generation-preview": "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-generation-preview": "gemini-2.5-flash-image",
    "imagen-4.0-generate-preview": "imagen-4.0-generate-001",
    "imagen-4.0-generate-preview-05-20": "imagen-4.0-generate-001",
    "imagen-4.0-generate-preview-06-06": "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-preview": "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-preview-05-20": "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-preview-06-06": "imagen-4.0-generate-001",
    "imagen-4.0-fast-generate-preview-05-20": "imagen-4.0-generate-001",
    "imagen-product-recontext-preview-06-30": "gemini-2.5-flash-image",
    "imagen-2.0-edit-preview-0627": "gemini-2.5-flash-image",
    "virtual-try-on-preview-08-04": "virtual-try-on-001",
    "imagen-4.0-ingredients-preview": "gemini-2.5-flash-image",
}


def is_deprecated_google_vertex_image_model(model_id: str) -> bool:
    """Return whether a Google/Vertex image endpoint is deprecated."""
    short_id = str(model_id or "").split("/")[-1].lower()
    return short_id in DEPRECATED_GOOGLE_VERTEX_IMAGE_MODEL_MIGRATIONS


# Compatibility exports. Values come from backend/app/config/google_vertex_models.json.
IMAGEN_GENERATE_MODELS: List[str] = _model_ids_for_family("imagen_generate")
IMAGEN_EDIT_MODELS: List[str] = _model_ids_for_family("imagen_edit")
IMAGE_UPSCALE_MODELS: List[str] = _model_ids_for_family("image_upscale")
IMAGE_SEGMENTATION_MODELS: List[str] = _model_ids_for_family("image_segmentation")
VIRTUAL_TRY_ON_MODELS: List[str] = _model_ids_for_family("virtual_try_on")
PRODUCT_RECONTEXT_MODELS: List[str] = _model_ids_for_family("product_recontext")
VEO_VIDEO_MODELS: List[str] = _model_ids_for_family("veo_video")


def get_static_google_vertex_models() -> List[str]:
    """
    Unified static model IDs for Google + Vertex capability merge.
    """
    deduped: list[str] = []
    seen: set[str] = set()
    for model_id in [str(entry["id"]) for entry in get_google_vertex_static_model_entries()]:
        if model_id in seen:
            continue
        seen.add(model_id)
        deduped.append(model_id)
    return deduped
