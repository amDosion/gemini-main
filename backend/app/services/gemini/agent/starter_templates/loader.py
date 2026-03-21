"""
Load starter template definitions from JSON files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

try:
    from ....common.prompt_enricher import enrich_starter_template_definition
except ImportError:  # pragma: no cover - direct module loading in tests
    from app.services.common.prompt_enricher import enrich_starter_template_definition

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_REQUIRED_TOP_LEVEL_KEYS = {
    "starter_key",
    "starter_version",
    "name",
    "workflow_type",
    "config",
}


def _validate_definition(definition: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    missing = [key for key in _REQUIRED_TOP_LEVEL_KEYS if key not in definition]
    if missing:
        raise ValueError(f"{source_path.name}: missing keys {missing}")

    starter_key = str(definition.get("starter_key") or "").strip()
    if not starter_key:
        raise ValueError(f"{source_path.name}: starter_key is empty")

    config = definition.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"{source_path.name}: config must be object")
    nodes = config.get("nodes")
    edges = config.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError(f"{source_path.name}: config must contain nodes[] and edges[]")

    return definition


def load_starter_template_definitions() -> List[Dict[str, Any]]:
    if not _TEMPLATES_DIR.exists():
        raise FileNotFoundError(f"starter template directory not found: {_TEMPLATES_DIR}")

    paths = sorted(_TEMPLATES_DIR.glob("*.json"))
    definitions: List[Dict[str, Any]] = []
    seen_keys = set()
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name}: top-level JSON must be object")
        definition = _validate_definition(payload, path)
        definition = enrich_starter_template_definition(definition)
        starter_key = str(definition.get("starter_key") or "").strip()
        if starter_key in seen_keys:
            raise ValueError(f"duplicate starter_key in templates dir: {starter_key}")
        seen_keys.add(starter_key)
        definitions.append(definition)

    logger.info(
        "[StarterTemplates] Loaded %s templates from %s",
        len(definitions),
        _TEMPLATES_DIR,
    )
    return definitions
