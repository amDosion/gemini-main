# Models module
#
# Intentional split: this __init__.py re-exports only the subset of model
# classes that are consumed by high-level routers/services via the package
# import surface (`from app.models import ...`).  The remaining model classes
# (e.g. User, RefreshToken, MessagesChat, StorageConfig, AgentRegistry …)
# are imported directly from `.db_models` at their call sites, many of them
# deferred inside functions to break SQLAlchemy / FastAPI circular-import
# chains at module load time.  Both import paths are intentional and must be
# kept in sync with `db_models.py` — do not consolidate them without first
# auditing every deferred import in `core/`, `routers/`, and `services/`.
from .db_models import (
    ConfigProfile,
    UserSettings,
    ChatSession,
    Persona,
    UserMcpConfig,
    WorkflowTemplate,
    WorkflowTemplateCategory,
)
from .research_task import ResearchTask

__all__ = [
    'ConfigProfile',
    'UserSettings',
    'ChatSession',
    'Persona',
    'UserMcpConfig',
    'WorkflowTemplate',
    'WorkflowTemplateCategory',
    'ResearchTask',
]
