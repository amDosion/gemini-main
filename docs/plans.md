# Delivery Plan

## Milestones

1. Discovery and planning
2. Implementation
3. Validation
4. Primary release review
5. Whole-project analysis package
6. Main-agent self research and same-run next-phase planning
7. Advanced feature delivery iteration
8. Advanced release review
9. Continuous evolution cycles (optional)

## Exit Criteria by Milestone

- Planning done:
  - requirements.md + design.md + tasks.md complete
  - queue/tasks.csv validated
- Implementation done:
  - frontend/backend/devops tasks success
- Validation done:
  - qa/security tasks success
- Primary release review done:
  - RV-001 success
- Whole-project analysis done:
  - docs/project-overview.md complete
  - docs/repo-structure-map.md complete (file-level responsibilities)
- Self research done:
  - docs/self-research.md complete (question set, answers, evidence, next-cycle direction)
- Expansion analysis done:
  - docs/advanced-features.md compares multiple feature/module candidates
  - one expansion direction is selected intentionally
- Next-phase planning done:
  - queue/tasks.csv rewritten by the main agent for advanced feature delivery
  - the next batch is ready to dispatch immediately in the current resident run
- Advanced feature delivery done:
  - docs/advanced-features.md complete
- Advanced release done:
  - RV-002 success
- Continuous cycle done (if enabled):
  - post-review innovation tasks re-run for target cycle count
  - each cycle ends with review pass and synced docs
  - the main agent does not stop between accepted cycles unless a stop condition is reached

## Shared Validation Commands

- `npm run lint`
- `npm run test`
- `npm run build`
