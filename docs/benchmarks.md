# Benchmarks

## Command Groups

### backend-video-contract

- Required: yes
- Notes: verifies router/coordinator/catalog contract and video persistence behavior
- Commands:
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q`
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_attachment_service_provider_assets.py backend/tests/test_workflow_result_media_persistence.py -q`

### frontend-video-ui

- Required: yes
- Notes: verifies VideoGenView history/result UI and schema-driven parameter flow
- Commands:
  - `npx vitest run frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.test.tsx frontend/components/chat/ChatEditInputArea.test.tsx --environment jsdom`
  - `npx tsc --noEmit --pretty false`

## Rule

- The main agent must read benchmark results before promoting the domain beyond standalone video mode.
- Live API runs are supporting evidence, not replacements for the required command groups.
