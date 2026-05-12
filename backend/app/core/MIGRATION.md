# ARCH-A: asyncpg / Async SQLAlchemy Migration

Status: **Phase 0 complete (infrastructure in place)**. Routers remain on the
sync engine. Migrate per-router in subsequent PRs.

## Why

FastAPI handlers declared `async def` but using the sync SQLAlchemy
`Session` block the event loop on every DB round-trip. With ~440+ call
sites of `db.query/db.execute/db.commit` and 148 `Depends(get_db)`
endpoints, a single-shot rewrite is high-risk and high-noise. Instead we
introduce a **parallel async engine** so new code and hot endpoints can
opt in, while the existing sync codepath continues to work unchanged.

## Audit baseline (taken on entry to ARCH-A)

| Metric | Count |
| --- | --- |
| `from sqlalchemy ... Session/sessionmaker` imports | 68 |
| `Depends(get_db)` usages in routers | 148 |
| `db.query` / `db.execute` / `db.commit` call sites (app/) | 441 |
| Current sync driver | `psycopg2-binary` |
| Current async driver | (added) `asyncpg>=0.29.0` |
| `create_engine` (sync) used | yes — `app/core/database.py` |
| `create_async_engine` (async) used | yes — `app/core/async_database.py` (new) |

Top routers by DB call volume (migration priority order):

| Router | `db.*` call sites |
| --- | --- |
| `app/routers/ai/workflows.py` | 75 |
| `app/routers/user/sessions.py` | 38 |
| `app/routers/storage/storage.py` | 26 |
| `app/routers/auth/auth.py` | 9 |
| `app/routers/core/modes.py` | 8 |
| `app/routers/user/profiles.py` | 7 |

## What Phase 0 added

- `app/core/async_database.py` — `async_engine`, `AsyncSessionLocal`,
  `get_async_db` dependency. Reuses `DATABASE_URL`, transparently
  rewrites `postgresql://` / `postgresql+psycopg2://` to
  `postgresql+asyncpg://`. Re-exports `Base` from the sync module so
  models share one `metadata`.
- `requirements.txt` — added `asyncpg>=0.29.0` alongside
  `psycopg2-binary`. `sqlalchemy[asyncio]>=2.0.0` was already present.

**Nothing in the sync codepath changed.** Endpoints continue to use
`Depends(get_db)` and `Session`. The sync engine still owns the pool
described by `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE`.

## How to migrate a router (recipe)

1. **Switch the dependency:**
   ```python
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.core.async_database import get_async_db

   @router.get("/things")
   async def list_things(db: AsyncSession = Depends(get_async_db)):
       ...
   ```

2. **Rewrite reads** — replace `db.query(Model).filter(...)` with
   SQLAlchemy 2.0 select() + `await db.execute(...)`:
   ```python
   from sqlalchemy import select

   result = await db.execute(
       select(Model).where(Model.owner_id == user.id)
   )
   rows = result.scalars().all()
   ```

3. **Rewrite writes** — `db.add(obj)` still works; replace
   `db.commit()` / `db.refresh(obj)` with awaited variants:
   ```python
   db.add(obj)
   await db.commit()
   await db.refresh(obj)
   ```

4. **Replace `db.get(Model, pk)`** with `await db.get(Model, pk)`.

5. **Lazy-load traps** — async sessions disallow lazy attribute access
   outside an awaited context. Use `selectinload` / `joinedload` for
   relationships you need, or fetch them explicitly. `expire_on_commit`
   is already disabled on `AsyncSessionLocal`, so response serialization
   of plain columns is safe.

6. **Background tasks / `BackgroundTasks`** — if a task continues using
   the session after the request returns, pass a fresh
   `AsyncSessionLocal()` context rather than the request-scoped one.

7. **Services called by the router** — services that take a `Session`
   parameter typed-hinted as `Session` need an async sibling or a
   `Union[Session, AsyncSession]` overload. Prefer creating an async
   variant alongside the sync function during the transition.

## Phased migration plan

- **Phase 0 (this PR) — Infrastructure.** Parallel async engine,
  driver dependency, migration doc. No router changes.
- **Phase 1 — POC.** Migrate one self-contained, high-traffic endpoint
  family (recommended: `app/routers/auth/auth.py`, 9 call sites, no
  cross-router service spaghetti). Verify under load and confirm
  pool behaviour.
- **Phase 2 — Heavy routers.** Migrate `workflows.py` (75) and
  `user/sessions.py` (38). Each likely needs an async variant of the
  services they call (`app/services/...`).
- **Phase 3 — Long tail.** Migrate remaining 11 routers in any order.
- **Phase 4 — Cutover.** Once `Depends(get_db)` is gone:
  - Remove the sync engine and `psycopg2-binary`
  - Rename `async_database` -> `database`
  - Drop the URL-rewrite shim in `_to_async_url`

## Constraints and invariants (do not violate)

- The sync engine must keep working until Phase 4. Tests, alembic
  migrations, and any synchronous tooling depend on it.
- Both engines use the **same** `Base.metadata`. Do not declare a
  second `declarative_base()` — re-export from `app.core.database`.
- Both engines share the `DATABASE_URL` env var. Operators do not
  need to configure two URLs.
- Pool sizing env vars (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
  `DB_POOL_RECYCLE`) are applied to both engines. Until cutover, the
  effective concurrent connection ceiling is roughly **double** the
  single-engine value. Operators should either accept that or lower
  the values during the transition.

## Verification commands

```bash
# Sanity: app still imports and the sync path is unaffected
.venv/bin/python -c "from app.main import app; print('app loads OK')"

# Async module loads (requires asyncpg installed)
.venv/bin/python -c "from app.core.async_database import async_engine, get_async_db; print('async ok')"

# Existing suite must remain green
.venv/bin/python -m pytest tests/ -x
```
