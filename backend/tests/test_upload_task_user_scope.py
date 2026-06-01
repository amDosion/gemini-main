import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_upload_task_model_matches_existing_table_without_direct_user_scope_column():
    from app.models.db_models import UploadTask

    assert "user_id" not in UploadTask.__table__.columns


def test_upload_task_owner_is_resolved_from_related_records():
    from app.core.database import Base
    from app.models.db_models import ChatSession, MessageAttachment, StorageConfig, UploadTask
    from app.routers.storage.storage import _is_upload_task_owned_by_user
    from app.services.common.upload_task_scope import resolve_upload_task_user_id

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ChatSession.__table__,
            MessageAttachment.__table__,
            StorageConfig.__table__,
            UploadTask.__table__,
        ],
    )
    TestingSessionLocal = sessionmaker(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add(
            ChatSession(
                id="session-1",
                user_id="user-session",
                title="Session",
                mode="image-gen",
                created_at=1000,
            )
        )
        db.add(
            MessageAttachment(
                id="attachment-1",
                message_id="message-1",
                session_id="session-1",
                user_id="user-attachment",
            )
        )
        db.add(
            StorageConfig(
                id="storage-1",
                user_id="user-storage",
                name="Storage",
                provider="local",
                enabled=True,
                config={},
                created_at=1000,
                updated_at=1000,
            )
        )
        db.add_all(
            [
                UploadTask(
                    id="task-by-attachment",
                    attachment_id="attachment-1",
                    filename="attachment.png",
                    status="pending",
                    created_at=1000,
                ),
                UploadTask(
                    id="task-by-session",
                    session_id="session-1",
                    filename="session.png",
                    status="pending",
                    created_at=1000,
                ),
                UploadTask(
                    id="task-by-storage",
                    storage_id="storage-1",
                    filename="storage.png",
                    status="pending",
                    created_at=1000,
                ),
            ]
        )
        db.commit()

        by_attachment = db.query(UploadTask).filter_by(id="task-by-attachment").first()
        by_session = db.query(UploadTask).filter_by(id="task-by-session").first()
        by_storage = db.query(UploadTask).filter_by(id="task-by-storage").first()

        assert resolve_upload_task_user_id(db, by_attachment) == "user-attachment"
        assert resolve_upload_task_user_id(db, by_session) == "user-session"
        assert resolve_upload_task_user_id(db, by_storage) == "user-storage"
        assert _is_upload_task_owned_by_user(db, by_attachment, "user-attachment") is True
        assert _is_upload_task_owned_by_user(db, by_attachment, "user-session") is False
    finally:
        db.close()
