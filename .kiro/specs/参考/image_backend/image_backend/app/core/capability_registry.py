from typing import Any, Dict, Optional
from app.core.ssot_loader import load_ssot
from app.core.routing import resolve_platform_and_routing
from app.core.genai_client import get_vertex_client, get_developer_client

def _to_dict(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    try:
        return obj.__dict__
    except Exception:
        return None

def _try_fetch_model_metadata(platform: str, model_name: str) -> Optional[Dict[str, Any]]:
    if not model_name:
        return None

    client = get_vertex_client() if platform == "vertex" else get_developer_client()

    if hasattr(client.models, "get"):
        try:
            m = client.models.get(model_name)
            return _to_dict(m)
        except Exception:
            pass

    if hasattr(client.models, "list"):
        try:
            for m in client.models.list(config={"page_size": 200}):
                md = _to_dict(m) or {}
                blob = " ".join(str(v) for v in md.values()).lower()
                if model_name.lower() in blob:
                    return md
        except Exception:
            pass

    return None

def get_capabilities_response() -> Dict[str, Any]:
    ssot = load_ssot()
    out_modes: Dict[str, Any] = {}

    for mode_id, mode_def in (ssot.get("modes") or {}).items():
        mode_def = dict(mode_def)

        resolved_platform, routing_info = resolve_platform_and_routing(mode_id, ui_selected=None)
        mode_def["routing"] = routing_info

        default_model = mode_def.get("default_model", "")
        meta = _try_fetch_model_metadata(resolved_platform, default_model)
        mode_def["resolved"] = {
            "source": "ssot+endpoint" if meta else "ssot_only",
            "endpoint_metadata": meta,
        }

        mode_def["mode_id"] = mode_id
        out_modes[mode_id] = mode_def

    return {"version": ssot.get("version"), "modes": out_modes}
