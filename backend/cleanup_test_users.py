"""
清理测试用户及其关联数据（保留真实用户）。

默认保留:
  - admin@example.com

默认识别为测试用户的邮箱前缀:
  - agent-e2e-
  - workflow-e2e-
  - prompt-opt-e2e-
  - url-check-
  - split-check-
  - register-auto-template-
  - e2e_
  - cachefix_
  - dbmodels_
  - dbonly_
  - initmode_

用法:
  python3 backend/cleanup_test_users.py              # 仅预览
  python3 backend/cleanup_test_users.py --apply      # 执行删除
  python3 backend/cleanup_test_users.py --apply --keep-email admin@example.com --keep-email xxx@domain.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Set

from sqlalchemy import and_

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal, Base  # noqa: E402
from app.models.db_models import User, A2ATask, A2AEvent, ChatSession, UploadTask  # noqa: E402


TEST_EMAIL_PREFIXES = (
    "agent-e2e-",
    "workflow-e2e-",
    "prompt-opt-e2e-",
    "url-check-",
    "split-check-",
    "register-auto-template-",
    "e2e_",
    "cachefix_",
    "dbmodels_",
    "dbonly_",
    "initmode_",
)


def is_test_email(email: str) -> bool:
    normalized = str(email or "").strip().lower()
    if not normalized:
        return False
    local = normalized.split("@", 1)[0]
    return any(local.startswith(prefix) for prefix in TEST_EMAIL_PREFIXES)


def collect_test_users(db, keep_emails: Set[str]) -> List[User]:
    users = db.query(User).all()
    targets: List[User] = []
    for user in users:
        email = str(user.email or "").strip().lower()
        if not email or email in keep_emails:
            continue
        if is_test_email(email):
            targets.append(user)
    return targets


def delete_user_related_rows(db, user_ids: List[str]) -> None:
    if not user_ids:
        return

    # 1) 删除 A2AEvent（无 user_id，通过任务关联）
    task_ids = [
        str(row[0]) for row in db.query(A2ATask.id).filter(A2ATask.user_id.in_(user_ids)).all()
        if row and row[0]
    ]
    if task_ids:
        db.query(A2AEvent).filter(A2AEvent.task_id.in_(task_ids)).delete(synchronize_session=False)

    # 2) 删除 UploadTask（无 user_id，通过会话关联）
    session_ids = [
        str(row[0]) for row in db.query(ChatSession.id).filter(ChatSession.user_id.in_(user_ids)).all()
        if row and row[0]
    ]
    if session_ids:
        db.query(UploadTask).filter(UploadTask.session_id.in_(session_ids)).delete(synchronize_session=False)

    # 3) 删除所有带 user_id 字段的表（除 users）
    for table in reversed(Base.metadata.sorted_tables):
        if table.name == "users":
            continue
        if "user_id" not in table.c:
            continue
        db.execute(table.delete().where(table.c.user_id.in_(user_ids)))

    # 4) 删除用户
    db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup test users and related data")
    parser.add_argument("--apply", action="store_true", help="Apply deletion (default is dry-run)")
    parser.add_argument(
        "--keep-email",
        action="append",
        default=[],
        help="Email to preserve (can be repeated)",
    )
    args = parser.parse_args()

    keep_emails = {str(email).strip().lower() for email in args.keep_email if str(email).strip()}
    keep_emails.add("admin@example.com")

    db = SessionLocal()
    try:
        targets = collect_test_users(db, keep_emails=keep_emails)
        all_users = db.query(User).count()
        print(f"当前用户总数: {all_users}")
        print(f"保留邮箱: {sorted(keep_emails)}")
        print(f"识别到测试用户: {len(targets)}")
        for user in targets:
            print(f"  - {user.id}\t{user.email}")

        if not args.apply:
            print("\nDry-run 完成。使用 --apply 执行删除。")
            return

        target_ids = [str(user.id) for user in targets if user.id]
        delete_user_related_rows(db, target_ids)
        db.commit()

        remaining = db.query(User).count()
        print("\n✅ 删除完成")
        print(f"  - 删除用户数: {len(target_ids)}")
        print(f"  - 剩余用户数: {remaining}")
    except Exception as exc:
        db.rollback()
        print(f"❌ 清理失败: {exc}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

