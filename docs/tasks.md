# Task Breakdown

## Domain Intent

本轮只收敛“视频模式后端优先架构”，不扩展到 workflow。

## Team Assignment Matrix

| Role | Responsibility | Typical Deliverables |
| --- | --- | --- |
| project_owner | 研究归纳、实施队列、domain gate 收敛 | requirements.md, design.md, queue/tasks.csv |
| backend | 视频 contract、router/coordinator、storyboard/domain logic | backend code, pytest, docs |
| frontend | schema-driven UI 收敛、历史/结果展示、去业务化 | frontend code, vitest, docs |
| qa | 回归验证与 live evidence 归纳 | test evidence, regression notes |
| reviewer | 正确性与边界审查 | findings / pass decision |

## Task List

| id | title | owner_role | depends_on | required_files | validate_cmds |
| --- | --- | --- | --- | --- | --- |
| P-910 | Video domain research baseline | project_owner |  | docs/requirements.md;docs/design.md;docs/tasks.md;docs/domain-profile.md;docs/domain-profile.json |  |
| P-911 | Backend-first implementation queue | project_owner | P-910 | docs/context-compact.md;docs/self-research.md |  |
| BE-910 | Unify backend video capability contract | backend | P-911 | docs/execplans/BE-910.md | _(test files planned, not yet created)_ PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q |
| BE-911 | Move remaining video business rules behind backend contract | backend | BE-910 | docs/execplans/BE-911.md | _(test files planned, not yet created)_ PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_attachment_service_provider_assets.py backend/tests/test_workflow_result_media_persistence.py -q |
| FE-910 | Align VideoGenView and controls to backend-defined semantics | frontend | BE-910 | docs/execplans/FE-910.md | _(test files planned, not yet created)_ npx vitest run frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.test.tsx frontend/components/chat/ChatEditInputArea.test.tsx --environment jsdom |
| FE-911 | Remove frontend-only video business branching | frontend | BE-911;FE-910 | docs/execplans/FE-911.md | npx tsc --noEmit --pretty false |
| QA-910 | Video mode regression and live evidence pass | qa | FE-911 | docs/execplans/QA-910.md | _(test files planned, not yet created)_ PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q ;; npx vitest run frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.test.tsx --environment jsdom |
| RV-910 | Video mode convergence review gate | reviewer | QA-910 | docs/documentation.md |  |

## Current Hypothesis

- 最优先的实现方向不是继续堆前端按钮，而是把视频模式语义抽成后端 contract，再让前端自适配。
- 参考目录中 `veo-studio` 的“模式拆分”和值得借鉴的 prompt/input 模型应首先落到后端 schema/coordinator，而不是先搬到前端 UI。
