"""
重置工作流数据：
1) 清理工作流执行历史（workflow_executions + node_executions）
2) 清理并重建工作流模板（workflow_templates）

用法：
  python3 backend/reset_workflow_data.py
  python3 backend/reset_workflow_data.py --user-id <USER_ID>
  python3 backend/reset_workflow_data.py --skip-seed
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.models.db_models import User, WorkflowExecution, NodeExecution, WorkflowTemplate
from app.services.gemini.agent.workflow_template_service import WorkflowTemplateService


def _collect_target_user_ids(db, user_id: Optional[str]) -> List[str]:
    if user_id:
        return [user_id]

    user_ids: Set[str] = set()
    user_ids.update([str(row[0]) for row in db.query(User.id).all() if row and row[0]])
    user_ids.update([str(row[0]) for row in db.query(WorkflowExecution.user_id).distinct().all() if row and row[0]])
    user_ids.update([str(row[0]) for row in db.query(WorkflowTemplate.user_id).distinct().all() if row and row[0]])
    return sorted(user_ids)


async def _reset_user_workflow_data(
    db,
    user_id: str,
    recreate_starters: bool,
) -> Dict[str, Any]:
    execution_ids = [
        str(row[0])
        for row in db.query(WorkflowExecution.id).filter(WorkflowExecution.user_id == user_id).all()
        if row and row[0]
    ]

    running_count = db.query(WorkflowExecution).filter(
        WorkflowExecution.user_id == user_id,
        WorkflowExecution.status == "running",
    ).count()

    node_deleted = 0
    if execution_ids:
        node_deleted = db.query(NodeExecution).filter(
            NodeExecution.execution_id.in_(execution_ids)
        ).delete(synchronize_session=False)

    execution_deleted = db.query(WorkflowExecution).filter(
        WorkflowExecution.user_id == user_id
    ).delete(synchronize_session=False)

    template_deleted = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.user_id == user_id
    ).delete(synchronize_session=False)

    db.commit()

    created_templates: List[Dict[str, Any]] = []
    if recreate_starters:
        service = WorkflowTemplateService(db=db)
        created_templates = await service.ensure_starter_templates(user_id=user_id)

    return {
        "user_id": user_id,
        "running_count": int(running_count or 0),
        "execution_deleted_count": int(execution_deleted or 0),
        "node_deleted_count": int(node_deleted or 0),
        "template_deleted_count": int(template_deleted or 0),
        "template_created_count": len(created_templates),
    }


def main():
    parser = argparse.ArgumentParser(description="Reset workflow history and templates")
    parser.add_argument("--user-id", dest="user_id", help="Only reset one user id")
    parser.add_argument("--skip-seed", action="store_true", help="Do not recreate starter templates")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        target_user_ids = _collect_target_user_ids(db=db, user_id=args.user_id)
        if not target_user_ids:
            print("⚠️ 未找到可重置的用户")
            return

        print(f"开始重置工作流数据，目标用户数: {len(target_user_ids)}")
        print(f"重建 Starter 模板: {'否' if args.skip_seed else '是'}")

        async def _run():
            summaries: List[Dict[str, Any]] = []
            for uid in target_user_ids:
                summary = await _reset_user_workflow_data(
                    db=db,
                    user_id=uid,
                    recreate_starters=not args.skip_seed,
                )
                summaries.append(summary)
                print(
                    f"  ✅ user={uid} | executions={summary['execution_deleted_count']} "
                    f"| nodes={summary['node_deleted_count']} "
                    f"| templates={summary['template_deleted_count']}→{summary['template_created_count']} "
                    f"| running={summary['running_count']}"
                )
            return summaries

        summaries = asyncio.run(_run())
        total_executions = sum(item["execution_deleted_count"] for item in summaries)
        total_nodes = sum(item["node_deleted_count"] for item in summaries)
        total_templates_deleted = sum(item["template_deleted_count"] for item in summaries)
        total_templates_created = sum(item["template_created_count"] for item in summaries)

        print("\n🎉 工作流数据重置完成")
        print(f"  - 删除执行历史: {total_executions}")
        print(f"  - 删除节点明细: {total_nodes}")
        print(f"  - 删除模板数量: {total_templates_deleted}")
        print(f"  - 新建模板数量: {total_templates_created}")

    except Exception as exc:
        db.rollback()
        print(f"❌ 重置失败: {exc}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
