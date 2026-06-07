"""
Compatibility shim for WorkflowEngine media helpers.
"""

# svc-agent-8: replaced wildcard import with explicit named imports
# to satisfy the public-API contract without namespace pollution.
from .workflow_engine.media import (  # noqa: F401
    build_video_generate_kwargs,
    build_audio_generate_kwargs,
    normalize_video_service_result,
    normalize_audio_service_result,
    run_video_generate_task,
    run_video_understand_task,
    run_video_delete_task,
    run_audio_generate_task,
    normalize_image_edit_mode,
    normalize_mode_token_for_routing,
    is_outpaint_mode_token,
    resolve_image_tool_route,
    normalize_image_service_results,
    trim_normalized_images,
)
