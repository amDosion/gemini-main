"""Upload task ownership helpers.

`upload_tasks` is an existing table without a direct `user_id` column in some
deployments. Resolve ownership from related records so the service remains
compatible with those databases.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from ...models.db_models import (
    ChatSession,
    MessageAttachment,
    StorageConfig,
    WorkflowExecution,
)


def _task_value(task: Any, field: str) -> str:
    return str(getattr(task, field, "") or "").strip()


def _scalar_user_id(query_result: Any) -> Optional[str]:
    if query_result is None:
        return None
    try:
        value = query_result[0]
    except (KeyError, IndexError, TypeError):
        value = query_result
    normalized = str(value or "").strip()
    return normalized or None


def resolve_upload_task_user_id(db: Session, task: Any) -> Optional[str]:
    direct_user_id = _task_value(task, "user_id")
    if direct_user_id:
        return direct_user_id

    for attachment_field in ("attachment_id", "source_attachment_id"):
        attachment_id = _task_value(task, attachment_field)
        if attachment_id:
            owner = db.query(MessageAttachment.user_id).filter(
                MessageAttachment.id == attachment_id,
            ).first()
            resolved = _scalar_user_id(owner)
            if resolved:
                return resolved

    session_id = _task_value(task, "session_id")
    if session_id:
        session_owner = db.query(ChatSession.user_id).filter(
            ChatSession.id == session_id,
        ).first()
        resolved = _scalar_user_id(session_owner)
        if resolved:
            return resolved

        workflow_owner = db.query(WorkflowExecution.user_id).filter(
            WorkflowExecution.id == session_id,
        ).first()
        resolved = _scalar_user_id(workflow_owner)
        if resolved:
            return resolved

    message_id = _task_value(task, "message_id")
    if message_id:
        message_owner = db.query(MessageAttachment.user_id).filter(
            MessageAttachment.message_id == message_id,
        ).first()
        resolved = _scalar_user_id(message_owner)
        if resolved:
            return resolved

    storage_id = _task_value(task, "storage_id")
    if storage_id:
        storage_owner = db.query(StorageConfig.user_id).filter(
            StorageConfig.id == storage_id,
        ).first()
        resolved = _scalar_user_id(storage_owner)
        if resolved:
            return resolved

    return None


def is_upload_task_owned_by_user(db: Session, task: Any, user_id: str) -> bool:
    resolved_user_id = resolve_upload_task_user_id(db, task)
    return bool(resolved_user_id and resolved_user_id == str(user_id or "").strip())
