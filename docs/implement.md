# Implementation Guide

## Coding Rules

- Write targeted changes for the assigned task only.
- Add or update tests for behavioral changes.
- Keep public interfaces stable unless explicitly planned.

## Documentation Rules

- Update `docs/documentation.md` with:
  - what changed
  - why it changed
  - validation evidence
- During post-review innovation phase, maintain:
  - `docs/project-overview.md`
  - `docs/repo-structure-map.md` (file-level responsibilities)
  - `docs/self-research.md` (main-agent self-question/self-answer evidence)
  - `docs/advanced-features.md`
- A successful implementation batch does not end the run; the main agent uses the updated docs to plan and dispatch the next batch.

## Commit/Review Readiness

- Lint/test/build pass
- Required artifacts exist
- ExecPlan updated
