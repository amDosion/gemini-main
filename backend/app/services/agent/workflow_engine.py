"""
Compatibility shim for WorkflowEngine.

The actual implementation now lives under the workflow_engine/ package.
"""

from .workflow_engine import WorkflowEngine
from .execution_context import ExecutionContext

__all__ = ["WorkflowEngine", "ExecutionContext"]
