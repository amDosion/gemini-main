# Quality Gates

## Domain Gates

- reviewer gate passes for the active video-mode queue
- no failed tasks remain
- no blocked tasks remain
- no unresolved pending tasks remain
- backend and frontend validator groups pass
- active-domain accepted-session streak is satisfied

## Video-Mode Convergence Gates

- `backend/app/config/mode_controls_catalog.json` and `backend/app/services/common/mode_controls_catalog.py` remain the canonical source for exposed video controls and constraints
- `backend/app/routers/core/modes.py` and `backend/app/services/gemini/coordinators/video_generation_coordinator.py` own capability semantics such as extension, reference-image constraints, subtitle behavior, and storyboard metadata
- `frontend/components/views/VideoGenView.tsx` does not invent new video capabilities or mode semantics outside backend schema
- `frontend/controls/modes/google/VideoGenControls.tsx` renders backend-provided capabilities rather than re-deriving policy
- successful video generations persist sessions, attachments, and history metadata in a way that the left history list can render without custom one-off branches

## Promotion Rule

- Do not move from standalone video-mode convergence to workflow/video template expansion until all video-mode gates pass.
- If a gate fails, the next queue must remain in video contract repair, backend hardening, or video UI alignment.
