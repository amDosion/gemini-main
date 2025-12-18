"""
Backfill / normalize upload_tasks data.

用途：
- 回填缺失字段：priority、retry_count（避免为 NULL）
- 归一化 source_file_path：
  - 将 backend/temp 下的“绝对路径”转换为相对路径（backend/temp/...）
  - 将相对路径中的反斜杠统一为正斜杠（跨平台更稳）

默认只做 dry-run；加 --apply 才会真正写入数据库。
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402
from backend.app.core.database import engine  # noqa: E402


def _is_abs_path(path: str) -> bool:
    if not path:
        return False
    # Windows drive: C:\ or C:/
    if re.match(r"^[A-Za-z]:[\\/]", path):
        return True
    # UNC path: \\server\share
    if path.startswith("\\\\"):
        return True
    # POSIX absolute: /...
    return path.startswith("/")


def _normalize_source_path(path: str) -> str | None:
    if not path:
        return None

    p = path.replace("\\", "/")

    # 1) 绝对路径：只在包含 backend/temp/ 时才转换为相对路径（避免误伤系统 temp）
    if _is_abs_path(path):
        idx = p.lower().rfind("backend/temp/")
        if idx >= 0:
            return p[idx:]
        return None

    # 2) 相对路径：仅做分隔符归一化
    if p != path:
        return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正执行写入（默认 dry-run）")
    parser.add_argument("--limit", type=int, default=500, help="最多处理多少条记录（默认 500）")
    args = parser.parse_args()

    with engine.begin() as conn:
        # 统计
        counts = conn.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM upload_tasks WHERE priority IS NULL) AS null_priority,
                  (SELECT COUNT(*) FROM upload_tasks WHERE retry_count IS NULL) AS null_retry,
                  (SELECT COUNT(*) FROM upload_tasks WHERE source_file_path IS NOT NULL AND source_file_path != '') AS has_source_path
                """
            )
        ).mappings().first()

        print("=" * 80)
        print("upload_tasks backfill/normalize")
        print("=" * 80)
        print(f"DB: {engine.url.render_as_string(hide_password=True)}")
        print(f"null priority: {counts['null_priority']}")
        print(f"null retry_count: {counts['null_retry']}")
        print(f"rows with source_file_path: {counts['has_source_path']}")
        print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print("-" * 80)

        # 批量回填 priority / retry_count（这两项不依赖逐行）
        if args.apply:
            conn.execute(text("UPDATE upload_tasks SET priority = 'normal' WHERE priority IS NULL"))
            conn.execute(text("UPDATE upload_tasks SET retry_count = 0 WHERE retry_count IS NULL"))

        # 逐行归一化 source_file_path（绝对->相对、\\->/）
        rows = conn.execute(
            text(
                """
                SELECT id, source_file_path
                FROM upload_tasks
                WHERE source_file_path IS NOT NULL AND source_file_path != ''
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": args.limit},
        ).fetchall()

        changed = 0
        skipped_abs = 0

        for task_id, source_file_path in rows:
            new_path = _normalize_source_path(source_file_path)
            if not new_path or new_path == source_file_path:
                continue

            if _is_abs_path(source_file_path) and "backend/temp/" not in new_path.lower():
                skipped_abs += 1
                continue

            changed += 1
            print(f"- {task_id[:8]}... source_file_path:")
            print(f"    from: {source_file_path}")
            print(f"    to:   {new_path}")

            if args.apply:
                conn.execute(
                    text("UPDATE upload_tasks SET source_file_path = :p WHERE id = :id"),
                    {"p": new_path, "id": task_id},
                )

        print("-" * 80)
        print(f"normalized source_file_path rows: {changed}")
        if skipped_abs:
            print(f"skipped absolute paths (not under backend/temp): {skipped_abs}")

        if not args.apply:
            print()
            print("Dry-run only. Re-run with --apply to persist changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

