"""
为已有用户补齐 Starter 工作流模板。

用法：
  python3 backend/backfill_starter_templates.py
  python3 backend/backfill_starter_templates.py --user-id <USER_ID>
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.models.db_models import User
from app.services.gemini.agent.workflow_template_service import WorkflowTemplateService


def _collect_target_user_ids(db, user_id: Optional[str]) -> List[str]:
    if user_id:
        return [user_id]

    user_ids: Set[str] = set()
    user_ids.update([str(row[0]) for row in db.query(User.id).all() if row and row[0]])
    return sorted(user_ids)


async def _backfill_one_user(db, user_id: str) -> Dict[str, Any]:
    service = WorkflowTemplateService(db=db)
    created = await service.ensure_starter_templates(user_id=user_id)
    return {
        "user_id": user_id,
        "created_count": len(created),
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill starter workflow templates for existing users")
    parser.add_argument("--user-id", dest="user_id", help="Only backfill one user id")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        target_user_ids = _collect_target_user_ids(db=db, user_id=args.user_id)
        if not target_user_ids:
            print("⚠️ 未找到用户，无需补齐模板")
            return

        print(f"开始补齐 Starter 模板，目标用户数: {len(target_user_ids)}")

        async def _run():
            summaries: List[Dict[str, Any]] = []
            for uid in target_user_ids:
                summary = await _backfill_one_user(db=db, user_id=uid)
                summaries.append(summary)
                print(f"  ✅ user={uid} | created={summary['created_count']}")
            return summaries

        summaries = asyncio.run(_run())
        total_created = sum(item["created_count"] for item in summaries)
        print("\n🎉 Starter 模板补齐完成")
        print(f"  - 用户总数: {len(summaries)}")
        print(f"  - 新建模板总数: {total_created}")
    except Exception as exc:
        db.rollback()
        print(f"❌ 补齐失败: {exc}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

