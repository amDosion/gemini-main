# Main Agent Self Research

## Research Baseline

- Reviewed docs:
  - `docs/requirements.md`
  - `docs/design.md`
  - `docs/tasks.md`
  - `docs/project-overview.md`
  - `docs/repo-structure-map.md`
- Reviewed signals:
  - current video-mode frontend and backend files
  - reference directory projects
  - existing live video generation evidence from recent sessions

## Self Questions and Answers

| Question | Evidence | Answer | Confidence | Follow-up Gap |
| --- | --- | --- | --- | --- |
| What is the highest-value bottleneck in the current video mode? | `frontend/components/views/VideoGenView.tsx`, `frontend/controls/modes/google/VideoGenControls.tsx`, `backend/app/routers/core/modes.py`, `backend/app/services/gemini/coordinators/video_generation_coordinator.py` | 视频模式 contract 已有后端基础，但前端仍承载默认值、合法性判断、延长派生和 transport 白名单，导致功能扩展易漂移。 | high | 需要精确列出哪些判断必须后移。 |
| Which business logic should move deeper into backend or shared domain layer? | `frontend/hooks/useControlsState.ts`, `frontend/components/chat/ChatEditInputArea.tsx`, `frontend/services/providers/UnifiedProviderClient.ts`, `backend/app/config/mode_controls_catalog.json` | 生成模式语义、参考输入类型、延长可用条件、字幕策略、person_generation 降级策略、参数白名单应进一步后移到 backend schema/coordinator。 | high | 需要按字段和文件做任务切分。 |
| Which reference project is most valuable? | `参考/veo-studio/*`, `参考/fit-check/services/geminiService.ts` | `veo-studio` 最适合借模式拆分和能力映射；`fit-check` 最适合借 identity-lock prompt 结构。 | high | 需要决定先吸收哪部分。 |
| Which UI inconsistency hurts maintainability most? | `VideoGenView.tsx` | 页面、参数面板、历史元数据展示和发送链混在同一视图里，容易出现 UI state 与业务能力绑定。 | medium | 后续可能需要进一步拆 view-level hooks。 |

## Research Findings

- Strongest finding: 当前最该做的是把视频模式“是什么能力”收回到后端，而不是继续在前端加控制项。
- Strongest finding evidence:
  - `frontend/hooks/useControlsState.ts` 仍硬编码视频默认值
  - `frontend/components/views/VideoGenView.tsx` 仍在前端执行 controls 合法性 gate
  - `frontend/controls/modes/google/VideoGenControls.tsx` 本地推导延长总时长
  - `frontend/services/providers/UnifiedProviderClient.ts` 维护第二份视频字段白名单
- Contradictory or weak evidence: `person_generation` 在 controls schema 与 provider 实际支持上存在边界不一致。
- Missing observability or benchmark evidence: 需要更多针对 live styling/reference 场景的固定脚本回归。
- Risks if the next cycle chooses the wrong direction: 如果先做前端模式重构而不先收 backend contract，会再次引入双重语义源。

## Candidate Next Iterations

| Theme | Type | Why Now | Dependencies | Expected User/Engineering Value | Risk |
| --- | --- | --- | --- | --- | --- |
| Backend-first video contract extraction | module / hardening | 这是视频模式后续所有扩展的前置条件 | current router/coordinator/catalog | 高 | 中 |
| Video UI mode split by backend schema | feature | 用户体验会更清楚 | backend contract first | 中高 | 中 |
| Styling / identity-lock prompt hardening | feature | 直接改善穿搭视频结果 | stable backend contract | 高 | 中 |

## Selected Direction

- Selected iteration theme: Backend-first video contract extraction
- Direction type: module-hardening
- Why this direction wins over the other candidates: 它是 UI 收敛和穿搭质量优化的共同前提。
- What must be true before implementation starts: 队列需要明确 backend/fronted 分工与验证命令。
- Which new feature, workflow, or module boundary this iteration should create: 明确的 video capability contract boundary。

## Queue Implications

- New `project_owner` planning tasks needed: yes
- New implementation tasks needed: backend contract, frontend alignment, QA, reviewer
- New validation / benchmark tasks needed: yes
- New review / remediation tasks needed: yes
- New feature or module artifacts expected from the next batch: refined video contract and thinner video UI
- Should the main agent continue immediately with the rewritten queue in the current run?: yes
