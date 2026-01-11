from fastapi import APIRouter, HTTPException
from app.schemas.jobs import JobRequest, JobResponse
from app.core.mode_registry import get_handler
from app.core.capability_registry import get_capabilities_response
from app.core.routing import resolve_platform_and_routing
from app.core.genai_client import get_vertex_client, get_developer_client

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/capabilities")
def capabilities():
    return get_capabilities_response()


@router.post("/jobs", response_model=JobResponse)
def run_job(req: JobRequest):
    handler = get_handler(req.mode_id)
    if handler is None:
        raise HTTPException(status_code=400, detail=f"Unknown mode_id: {req.mode_id}")

    try:
        platform, routing_info = resolve_platform_and_routing(
            mode_id=req.mode_id,
            ui_selected=req.platform
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    client = get_vertex_client() if platform == "vertex" else get_developer_client()

    try:
        resp = handler.execute(req, client=client, platform=platform)
        # optional: attach debug
        resp.debug = resp.debug or {}
        resp.debug["platform"] = platform
        resp.debug["routing"] = routing_info
        return resp
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
