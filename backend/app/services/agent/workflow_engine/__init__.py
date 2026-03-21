"""
WorkflowEngine package entrypoint.

This package is intentionally split by responsibility:
- `engine.py` only defines the `WorkflowEngine` shell and binds helpers.
- heavy execution logic lives in sibling modules such as
  `orchestration.py`, `agent_execution.py`, `image_pipeline.py`,
  `analysis_tools.py`, `builtin_tools.py`, and `agent_resolution.py`.

If you are adding new execution behavior, prefer extending a focused helper
module and binding it back in `engine.py` instead of growing `engine.py`.
See `README.md` in this directory for the module boundary guide.
"""

__all__ = ["WorkflowEngine", "ExecutionContext"]


def __getattr__(name):
    if name == "WorkflowEngine":
        from .engine import WorkflowEngine

        return WorkflowEngine
    if name == "ExecutionContext":
        from ..execution_context import ExecutionContext

        return ExecutionContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
