import json
from pathlib import Path
from typing import Any, Dict

_SSOT_PATH = Path(__file__).resolve().parents[2] / "capabilities" / "ssot.json"

def load_ssot() -> Dict[str, Any]:
    return json.loads(_SSOT_PATH.read_text(encoding="utf-8"))
