# Project Change Log

## Task Status

- Task ID: RV-910
- Owner role: reviewer
- Status: success

## What Changed

- Code paths changed:
  - `backend/app/services/common/video_mode_contract.py`
  - `backend/app/routers/core/modes.py`
  - `frontend/hooks/useModeControlsSchema.ts`
  - `frontend/utils/videoControlSchema.ts`
  - `frontend/controls/modes/google/VideoGenControls.tsx`
  - `frontend/components/views/VideoGenView.tsx`
  - `frontend/hooks/useControlsState.ts`
- Config changes:
  - standalone video mode now relies on backend `mode_controls_catalog` + backend-derived `video_contract`
- Documentation changes:
  - `docs/execplans/BE-910.md`
  - `docs/execplans/BE-911.md`
  - `docs/execplans/FE-910.md`
  - `docs/execplans/FE-911.md`
  - `docs/execplans/QA-910.md`

## Why It Changed

- Requirement or issue:
  - standalone video mode was still splitting business semantics between backend and frontend, especially around extension duration rules, subtitle policy, and default/reset behavior
- Decision summary:
  - move capability, normalization, and policy decisions behind backend `video_contract`
  - keep frontend focused on rendering schema-driven controls and view state
  - verify with focused regression plus live persistence/preview evidence
- Tradeoffs:
  - full-project TypeScript compile remains noisy because `参考/` demo directories carry unresolved third-party dependencies
  - validation therefore uses focused frontend compilation for touched video files

## Validation Evidence

- Commands run:
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q`
  - `npx vitest run frontend/hooks/useModeControlsSchema.test.tsx frontend/utils/videoControlSchema.test.ts frontend/controls/modes/google/VideoGenControls.test.tsx --environment jsdom`
  - `npx vitest run frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.test.tsx frontend/components/chat/ChatEditInputArea.test.tsx frontend/utils/videoControlSchema.test.ts frontend/hooks/useModeControlsSchema.test.tsx --environment jsdom`
  - `npx tsc --noEmit --pretty false --target ES2022 --module ESNext --moduleResolution bundler --jsx react-jsx --lib ES2022,DOM,DOM.Iterable --types node --skipLibCheck true frontend/hooks/useControlsState.ts frontend/components/views/VideoGenView.tsx frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.tsx frontend/controls/modes/google/VideoGenControls.test.tsx frontend/components/chat/ChatEditInputArea.tsx frontend/components/chat/ChatEditInputArea.test.tsx frontend/hooks/useModeControlsSchema.ts frontend/hooks/useModeControlsSchema.test.tsx frontend/utils/videoControlSchema.ts frontend/utils/videoControlSchema.test.ts`
  - live API checks:
    - `GET /health -> 200`
    - `POST /api/auth/login -> 200`
    - `GET /api/sessions -> 200`
    - `GET /api/sessions/d2e39964-e260-47a4-8e3b-d5e12b558720 -> 200`
    - `GET /api/sessions/562409f9-8904-431f-8551-1d12874f2615 -> 200`
    - `GET /api/temp-images/4b693c07-c10d-49bf-ab0c-af2639caf651 -> 200 video/mp4`
- Results:
  - backend focused regressions passed
  - frontend focused regressions passed
  - live extension metadata, subtitle metadata, session history endpoints, and preview URLs all behaved correctly for representative persisted video sessions
- Residual risks:
  - review found no blocking defects for the standalone video convergence batch
  - remaining risk is operational rather than architectural: live Veo generation still depends on upstream quota/service availability
