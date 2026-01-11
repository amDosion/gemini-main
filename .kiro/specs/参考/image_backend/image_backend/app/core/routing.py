from typing import Literal, Optional, Tuple, Dict, Any
from app.core.routing_loader import load_routing

Platform = Literal["developer", "vertex"]
Support = Literal["either", "vertex_only", "developer_only"]


def resolve_platform_and_routing(mode_id: str, ui_selected: Optional[Platform]) -> Tuple[Platform, Dict[str, Any]]:
    r = load_routing()
    defaults = r.get("defaults", {})
    mode_cfg = (r.get("modes") or {}).get(mode_id, {})

    support: Support = mode_cfg.get("support", "either")

    # Vertex-only
    if support == "vertex_only":
        routing_info = {
            "support": "vertex_only",
            "ui_can_choose_platform": False,
            "ui_allowed_platforms": ["vertex"],
            "default_platform": "vertex",
            "resolved_platform": "vertex",
        }
        return "vertex", routing_info

    # Developer-only
    if support == "developer_only":
        routing_info = {
            "support": "developer_only",
            "ui_can_choose_platform": False,
            "ui_allowed_platforms": ["developer"],
            "default_platform": "developer",
            "resolved_platform": "developer",
        }
        return "developer", routing_info

    # Either
    ui_can_choose = mode_cfg.get("ui_can_choose_platform", defaults.get("ui_can_choose_platform", True))
    allowed = mode_cfg.get("ui_allowed_platforms", defaults.get("ui_allowed_platforms", ["developer", "vertex"]))
    default_platform: Platform = mode_cfg.get("default_platform") or defaults.get("either_platform", "developer")

    if ui_selected is not None:
        if not ui_can_choose:
            raise ValueError(f"Platform selection disabled for mode_id={mode_id}")
        if ui_selected not in allowed:
            raise ValueError(f"Selected platform '{ui_selected}' not allowed for mode_id={mode_id}")
        routing_info = {
            "support": "either",
            "ui_can_choose_platform": True,
            "ui_allowed_platforms": allowed,
            "default_platform": default_platform,
            "resolved_platform": ui_selected,
        }
        return ui_selected, routing_info

    routing_info = {
        "support": "either",
        "ui_can_choose_platform": ui_can_choose,
        "ui_allowed_platforms": allowed,
        "default_platform": default_platform,
        "resolved_platform": default_platform,
    }
    return default_platform, routing_info
