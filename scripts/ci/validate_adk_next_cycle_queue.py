#!/usr/bin/env python3
"""Validate queue/adk_next_cycle_tasks.csv task/role/dependency contract."""

from __future__ import annotations

import csv
import sys
from collections import deque
from pathlib import Path

EXPECTED = {
    "P-701": {"owner_role": "project_owner", "depends_on": set()},
    "BE-701": {"owner_role": "backend", "depends_on": {"P-701"}},
    "FE-701": {"owner_role": "frontend", "depends_on": {"P-701", "BE-701"}},
    "SE-701": {"owner_role": "security", "depends_on": {"BE-701"}},
    "QA-701": {"owner_role": "qa", "depends_on": {"BE-701", "FE-701", "SE-701"}},
    "OP-701": {"owner_role": "devops", "depends_on": {"QA-701", "SE-701"}},
    "RV-701": {"owner_role": "reviewer", "depends_on": {"P-701", "BE-701", "FE-701", "SE-701", "QA-701", "OP-701"}},
}
EXPECTED_ROLES = {"project_owner", "backend", "frontend", "security", "qa", "devops", "reviewer"}


def _split_ids(raw: str) -> set[str]:
    return {item.strip() for item in (raw or "").split(";") if item.strip()}


def _fail(message: str) -> int:
    print(f"[queue-check] ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        return _fail("usage: python3 scripts/ci/validate_adk_next_cycle_queue.py <tasks.csv>")

    queue_path = Path(sys.argv[1])
    if not queue_path.is_file():
        return _fail(f"missing queue file: {queue_path}")

    with queue_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        return _fail("queue is empty")

    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        task_id = (row.get("id") or "").strip()
        if not task_id:
            return _fail("row with empty id")
        if task_id in by_id:
            return _fail(f"duplicate task id: {task_id}")
        by_id[task_id] = row

    actual_ids = set(by_id.keys())
    expected_ids = set(EXPECTED.keys())
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing or extra:
        return _fail(f"task set mismatch; missing={missing or '[]'} extra={extra or '[]'}")

    roles_present: set[str] = set()
    graph: dict[str, set[str]] = {}
    reverse_graph: dict[str, set[str]] = {task_id: set() for task_id in expected_ids}

    for task_id, expected in EXPECTED.items():
        row = by_id[task_id]
        owner_role = (row.get("owner_role") or "").strip()
        depends_on = _split_ids(row.get("depends_on") or "")

        if owner_role != expected["owner_role"]:
            return _fail(f"{task_id} owner_role expected {expected['owner_role']} got {owner_role or '<empty>'}")

        if depends_on != expected["depends_on"]:
            return _fail(
                f"{task_id} depends_on mismatch; expected={sorted(expected['depends_on'])} got={sorted(depends_on)}"
            )

        unknown_deps = sorted(dep for dep in depends_on if dep not in expected_ids)
        if unknown_deps:
            return _fail(f"{task_id} depends on unknown tasks: {unknown_deps}")

        roles_present.add(owner_role)
        graph[task_id] = depends_on
        for dep in depends_on:
            reverse_graph[dep].add(task_id)

        if not depends_on and owner_role != "project_owner":
            return _fail(f"{task_id} is a dependency root but owner_role is {owner_role}, expected project_owner")

    if roles_present != EXPECTED_ROLES:
        missing_roles = sorted(EXPECTED_ROLES - roles_present)
        extra_roles = sorted(roles_present - EXPECTED_ROLES)
        return _fail(f"role coverage mismatch; missing={missing_roles or '[]'} extra={extra_roles or '[]'}")

    reviewer_gate = graph["RV-701"]
    expected_reviewer_gate = expected_ids - {"RV-701"}
    if reviewer_gate != expected_reviewer_gate:
        return _fail(
            f"RV-701 gate mismatch; expected={sorted(expected_reviewer_gate)} got={sorted(reviewer_gate)}"
        )

    indegree: dict[str, int] = {task_id: len(deps) for task_id, deps in graph.items()}
    queue = deque(task_id for task_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in reverse_graph[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if visited != len(expected_ids):
        return _fail("dependency graph contains a cycle")

    edge_count = sum(len(deps) for deps in graph.values())
    print(f"[queue-check] OK: tasks={len(expected_ids)} roles={len(roles_present)} edges={edge_count} reviewer_gate=RV-701")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
