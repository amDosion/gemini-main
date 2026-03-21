"""
为用户模板生成真实样例结果并写回模板。

用法:
  python3 backend/materialize_template_samples.py --user-id <USER_ID>
  python3 backend/materialize_template_samples.py --user-id <USER_ID> --force
  python3 backend/materialize_template_samples.py --user-id <USER_ID> --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.services.gemini.agent.test_template_fixture_service import (
    ensure_data_analysis_sample_spreadsheet,
    ensure_listing_sample_spreadsheet,
)
from app.services.gemini.agent.workflow_template_sample_service import WorkflowTemplateSampleService


async def _run(
    *,
    user_id: str,
    template_ids: List[str],
    force: bool,
    limit: int | None,
    timeout_seconds: int,
) -> dict:
    db = SessionLocal()
    try:
        service = WorkflowTemplateSampleService(db=db)
        return await service.materialize_for_user(
            user_id=user_id,
            template_ids=template_ids or None,
            force=force,
            limit=limit,
            timeout_seconds=timeout_seconds,
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize real template sample results")
    parser.add_argument("--user-id", required=True, help="Target user id")
    parser.add_argument("--template-id", action="append", default=[], help="Specific template id (repeatable)")
    parser.add_argument("--force", action="store_true", help="Re-generate even if sample already exists")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N templates")
    parser.add_argument("--timeout-seconds", type=int, default=240, help="Per-template timeout")
    args = parser.parse_args()

    listing_fixture_path = ensure_listing_sample_spreadsheet()
    data_analysis_fixture_path = ensure_data_analysis_sample_spreadsheet()
    print(f"[fixture] listing sample spreadsheet ready: {listing_fixture_path}")
    print(f"[fixture] data-analysis sample spreadsheet ready: {data_analysis_fixture_path}")

    summary = asyncio.run(
        _run(
            user_id=str(args.user_id).strip(),
            template_ids=[str(item).strip() for item in args.template_id if str(item).strip()],
            force=bool(args.force),
            limit=args.limit,
            timeout_seconds=max(30, int(args.timeout_seconds or 240)),
        )
    )

    print("=== Template Sample Materialization Summary ===")
    print(f"user_id: {summary.get('user_id')}")
    print(f"requested: {summary.get('requested_count')}")
    print(f"success:   {summary.get('success_count')}")
    print(f"failed:    {summary.get('failed_count')}")
    if summary.get("failures"):
        print("\n--- failures ---")
        for item in summary.get("failures", []):
            print(f"- {item.get('template_id')} | {item.get('template_name')} | {item.get('error')}")

    print("\n--- json ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
