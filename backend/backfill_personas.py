"""
为已有用户补齐默认 AI Personas（仅补齐缺失项，不覆盖自定义角色）。

用法：
  python3 backend/backfill_personas.py
  python3 backend/backfill_personas.py --user-id <USER_ID>
  python3 backend/backfill_personas.py --email admin@example.com
  python3 backend/backfill_personas.py --email admin@example.com --dry-run
  python3 backend/backfill_personas.py --persona-ids amazon-selection-strategist,amazon-ads-keyword-operator,amazon-listing-cvr-optimizer
"""

import argparse
import ast
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.models.db_models import Persona, User


def _load_default_personas() -> List[Dict[str, Any]]:
    source_path = Path(__file__).parent / "app/services/common/persona_init_service.py"
    source = source_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(source_path))

    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "DEFAULT_PERSONAS":
            value = ast.literal_eval(node.value)
            if isinstance(value, list):
                return value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_PERSONAS":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, list):
                        return value

    raise ValueError("未找到 DEFAULT_PERSONAS 定义")


def _filter_personas(
    default_personas: List[Dict[str, Any]],
    persona_ids: Optional[str],
) -> List[Dict[str, Any]]:
    if not persona_ids:
        return default_personas

    selected_ids = [item.strip() for item in persona_ids.split(",") if item.strip()]
    if not selected_ids:
        raise ValueError("--persona-ids 为空，请至少提供一个 persona id")

    # preserve input order while deduplicating
    ordered_unique_ids = list(dict.fromkeys(selected_ids))
    by_id = {str(p.get("id")): p for p in default_personas if p.get("id")}
    unknown = sorted(pid for pid in ordered_unique_ids if pid not in by_id)
    if unknown:
        raise ValueError(f"--persona-ids 包含未知 id: {', '.join(unknown)}")

    return [by_id[pid] for pid in ordered_unique_ids]


def _collect_targets(db, user_id: Optional[str], email: Optional[str]) -> List[Tuple[str, str]]:
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"用户不存在: {user_id}")
        return [(str(user.id), str(user.email))]

    if email:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError(f"邮箱对应用户不存在: {email}")
        return [(str(user.id), str(user.email))]

    users = db.query(User.id, User.email).all()
    return [(str(uid), str(uemail)) for uid, uemail in users if uid and uemail]


def _count_missing_default_personas(db, user_id: str, default_personas: List[Dict[str, Any]]) -> int:
    existing_ids = {
        row[0]
        for row in db.query(Persona.id).filter(Persona.user_id == user_id).all()
        if row and row[0]
    }
    missing = 0
    for persona in default_personas:
        pid = f"{user_id}:{persona['id']}"
        if pid not in existing_ids:
            missing += 1
    return missing


def _create_missing_personas(db, user_id: str, default_personas: List[Dict[str, Any]]) -> int:
    existing_ids = {
        row[0]
        for row in db.query(Persona.id).filter(Persona.user_id == user_id).all()
        if row and row[0]
    }
    now_ms = int(time.time() * 1000)
    to_add = []

    for persona_data in default_personas:
        persona_key = str(persona_data["id"])
        persona_id = f"{user_id}:{persona_key}"
        if persona_id in existing_ids:
            continue
        to_add.append(
            Persona(
                id=persona_id,
                user_id=user_id,
                name=str(persona_data.get("name", persona_key)),
                description=str(persona_data.get("description", "")),
                system_prompt=str(persona_data.get("systemPrompt", "")),
                icon=str(persona_data.get("icon", "MessageSquare")),
                category=str(persona_data.get("category", "General")),
                created_at=now_ms,
                updated_at=now_ms,
            )
        )

    if not to_add:
        return 0

    for persona in to_add:
        db.add(persona)
    db.commit()
    return len(to_add)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill default AI personas for existing users")
    parser.add_argument("--user-id", dest="user_id", help="Only backfill one user id")
    parser.add_argument("--email", dest="email", help="Only backfill user by email")
    parser.add_argument(
        "--persona-ids",
        dest="persona_ids",
        help="Comma-separated default persona ids to backfill only (e.g. general,writer)",
    )
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="Only report missing count")
    args = parser.parse_args()

    if args.user_id and args.email:
        raise ValueError("--user-id 与 --email 不能同时指定")

    db = SessionLocal()
    try:
        default_personas = _filter_personas(
            default_personas=_load_default_personas(),
            persona_ids=args.persona_ids,
        )
        targets = _collect_targets(db=db, user_id=args.user_id, email=args.email)
        if not targets:
            print("⚠️ 未找到任何用户")
            return

        print(f"开始补齐默认 Personas，目标用户数: {len(targets)}")
        print(f"待补齐 Persona 模板数: {len(default_personas)}")
        total_created = 0
        total_missing = 0

        for uid, uemail in targets:
            missing = _count_missing_default_personas(
                db=db,
                user_id=uid,
                default_personas=default_personas,
            )
            total_missing += missing
            if args.dry_run:
                print(f"  🧪 user={uid} email={uemail} | missing={missing}")
                continue

            created = _create_missing_personas(
                db=db,
                user_id=uid,
                default_personas=default_personas,
            )
            total_created += created
            print(f"  ✅ user={uid} email={uemail} | missing={missing} | created={created}")

        print("\n🎉 Personas 补齐完成")
        print(f"  - 用户总数: {len(targets)}")
        print(f"  - 缺失总数: {total_missing}")
        if not args.dry_run:
            print(f"  - 新建总数: {total_created}")
    except Exception as exc:
        db.rollback()
        print(f"❌ Personas 补齐失败: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
