import json
from pathlib import Path
from typing import Any, Dict

_ROUTING_PATH = Path(__file__).resolve().parents[2] / "routing" / "routing.json"

def load_routing() -> Dict[str, Any]:
    return json.loads(_ROUTING_PATH.read_text(encoding="utf-8"))
