# Iteration Log

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: kickoff / strategic
- Goal: 为视频模式建立 long-running 的 backend-first 收敛计划
- What changed:
  - bootstrapped `.codex`, `docs`, `queue`
  - 建立了视频域专用 `domain-profile`
  - 记录了当前视频模式的关键文件、边界和参考目录借鉴方向
- Validation and review evidence:
  - long-running bootstrap 成功
  - 当前代码路径已完成一轮定位
- Key risks or failures:
  - 参考项目能力尚未正式转化为实施任务的代码变更
  - 子任务研究结果仍在回收中
- Next-cycle hypothesis:
  - 先做 backend contract 收敛，再做 frontend 对齐，能显著降低视频模式漂移
- Queue/task changes:
  - starter queue 已被定向替换为视频域 queue
- Docs updated:
  - `docs/domain-profile.md`
  - `docs/domain-profile.json`
  - `docs/requirements.md`
  - `docs/design.md`
  - `docs/tasks.md`
  - `docs/project-overview.md`
  - `docs/repo-structure-map.md`
  - `docs/self-research.md`
  - `docs/context-compact.md`
  - `docs/advanced-features.md`
  - `docs/quality-gates.md`
  - `docs/benchmarks.md`
  - `docs/stop-conditions.md`

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: execution / backend
- Goal: 完成 BE-910，把视频模式 contract 先收回后端
- What changed:
  - 新增 `backend/app/services/common/video_mode_contract.py`
  - 将 `modes.py` 中视频附件槽位解释与 runtime schema 组装迁移到后端 helper
  - 为 controls schema 增加 backend-derived `video_contract`
  - 建立 `backend/tests/` 下的 focused video contract tests
- Validation and review evidence:
  - `python3 -m py_compile backend/app/services/common/video_mode_contract.py backend/app/routers/core/modes.py backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py`
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q`
  - 结果：`9 passed`
- Key risks or failures:
  - 前端仍然在自行派生部分视频语义，还未切到 `video_contract`
  - workflow 视频路径尚未纳入本轮 contract 收敛
- Next-cycle hypothesis:
  - 继续做 `BE-911`，把剩余视频业务规则从 router / frontend 状态层继续下沉到 backend contract
- Queue/task changes:
  - `BE-910` 标记成功
  - 下一焦点切到 `BE-911`
- Docs updated:
  - `docs/execplans/BE-910.md`
  - `docs/context-compact.md`
  - `docs/iteration-log.md`

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: execution / backend
- Goal: 完成 BE-911，把剩余视频业务语义继续收回后端
- What changed:
  - 为 `video_contract` 增加了 `field_policies`
  - 新增 `normalize_video_generation_request_params()` 做 backend-side request normalization
  - 显式 `storyboard_prompt` 现在会压制旧的 tracking companion fields
  - `generate_video` 在 router 层进入服务前会统一走后端 request normalization
- Validation and review evidence:
  - `python3 -m py_compile backend/app/services/common/video_mode_contract.py backend/app/services/gemini/base/video_storyboard.py backend/app/routers/core/modes.py backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py`
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q`
  - 结果：`13 passed`
- Key risks or failures:
  - 前端仍未真正消费 `video_contract.field_policies` 和 backend extension matrix
  - `useControlsState` 仍有视频默认值状态，尚未做 frontend 去业务化
- Next-cycle hypothesis:
  - 做 `FE-910` 后，视频参数面板和 view 层可以开始只读 backend contract
- Queue/task changes:
  - `BE-911` 标记成功
  - 下一焦点切到 `FE-910`
- Docs updated:
  - `docs/execplans/BE-911.md`
  - `docs/context-compact.md`
  - `docs/iteration-log.md`

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: execution / frontend
- Goal: 完成 FE-910，让视频参数面板开始消费后端 `video_contract`
- What changed:
  - `useModeControlsSchema` 现在会解析 backend `video_contract`
  - `videoControlSchema` 现在优先使用 backend extension matrix、subtitle policy、enhance-prompt policy
  - `VideoGenControls` 不再本地推导延长选项、字幕默认模式和 mandatory 增强提示词语义
  - 补齐了 focused frontend tests 覆盖 schema parsing、contract derivation 和 controls rendering
- Validation and review evidence:
  - `npx vitest run frontend/hooks/useModeControlsSchema.test.tsx frontend/utils/videoControlSchema.test.ts frontend/controls/modes/google/VideoGenControls.test.tsx --environment jsdom`
  - 结果：`3 passed / 4 tests passed`
  - `npx tsc --noEmit --pretty false --target ES2022 --module ESNext --moduleResolution bundler --jsx react-jsx --lib ES2022,DOM,DOM.Iterable --types node --skipLibCheck true frontend/hooks/useModeControlsSchema.ts frontend/utils/videoControlSchema.ts frontend/controls/modes/google/VideoGenControls.tsx frontend/hooks/useModeControlsSchema.test.tsx frontend/utils/videoControlSchema.test.ts frontend/controls/modes/google/VideoGenControls.test.tsx`
  - 结果：通过
- Key risks or failures:
  - `useControlsState` 仍保留视频初始默认值，前端 view 层仍有少量 reset 语义
  - 全量 `tsc` 仍会被 `参考/` 目录的第三方示例依赖拖红，本轮只做窄编译
- Next-cycle hypothesis:
  - 做完 `FE-911` 后，standalone video mode 的前端将只剩 UI 呈现职责，业务分支基本可以收敛到 backend contract
- Queue/task changes:
  - `FE-910` 标记成功
  - 下一焦点切到 `FE-911`
- Docs updated:
  - `docs/execplans/FE-910.md`
  - `docs/context-compact.md`
  - `docs/iteration-log.md`

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: execution / frontend
- Goal: 完成 FE-911，继续减少 standalone video mode 的前端业务分支
- What changed:
  - `videoControlSchema` 现在还会输出 backend-derived video defaults（storyboard/audio/person/subtitle/seed/enhance 等）
  - `VideoGenView` 的 reset 和 schema-sync 行为改成消费 contract 默认值，而不是写死前端值
  - `useControlsState` 中视频专属初始值改成中性占位，不再携带 Veo 业务默认值
  - 增加了 `VideoGenView` 的 reset-focused regression
- Validation and review evidence:
  - `npx vitest run frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.test.tsx frontend/components/chat/ChatEditInputArea.test.tsx frontend/utils/videoControlSchema.test.ts frontend/hooks/useModeControlsSchema.test.tsx --environment jsdom`
  - 结果：`5 passed / 13 tests passed`
  - `npx tsc --noEmit --pretty false --target ES2022 --module ESNext --moduleResolution bundler --jsx react-jsx --lib ES2022,DOM,DOM.Iterable --types node --skipLibCheck true frontend/hooks/useControlsState.ts frontend/components/views/VideoGenView.tsx frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.tsx frontend/controls/modes/google/VideoGenControls.test.tsx frontend/components/chat/ChatEditInputArea.tsx frontend/components/chat/ChatEditInputArea.test.tsx frontend/hooks/useModeControlsSchema.ts frontend/hooks/useModeControlsSchema.test.tsx frontend/utils/videoControlSchema.ts frontend/utils/videoControlSchema.test.ts`
  - 结果：通过
- Key risks or failures:
  - live evidence 和 session/history 持久化证据还没在本轮重新收集
  - 全量 `tsc` 仍受 `参考/` 目录第三方示例依赖影响
- Next-cycle hypothesis:
  - 进入 `QA-910` 收 regression + live evidence，能判断 standalone video mode 是否达到 review gate
- Queue/task changes:
  - `FE-911` 标记成功
  - 下一焦点切到 `QA-910`
- Docs updated:
  - `docs/execplans/FE-911.md`
  - `docs/context-compact.md`
  - `docs/iteration-log.md`

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: execution / qa
- Goal: 完成 QA-910，收 standalone video mode 的 focused regression 和 live 证据
- What changed:
  - 跑完了 video contract 相关 backend focused pytest
  - 跑完了 video view / controls focused vitest
  - 用真实 `admin@example.com` token 验证了 session 列表、session 详情、history-preferences、history-states 和视频预览链
  - 记录了 extension chain 与 subtitle metadata 的两条代表性 live 样本
- Validation and review evidence:
  - `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_google_video_common.py backend/tests/test_google_video_generation_coordinator.py backend/tests/test_modes_video_attachment_params.py -q`
  - 结果：`13 passed`
  - `npx vitest run frontend/components/views/VideoGenView.test.tsx frontend/controls/modes/google/VideoGenControls.test.tsx --environment jsdom`
  - 结果：`2 passed / 7 tests passed`
  - `GET /health -> 200`
  - `POST /api/auth/login -> 200`
  - `GET /api/sessions -> 200`
  - live session evidence 已写入 `docs/execplans/QA-910.md`
- Key risks or failures:
  - review gate 还没做 read-only 收尾
  - live 证据使用的是已有 session，而不是新生成的一轮 quota 消耗
- Next-cycle hypothesis:
  - 进入 `RV-910` 做 review gate，可以判断 standalone video batch 是否达到当前收敛标准
- Queue/task changes:
  - `QA-910` 标记成功
  - 下一焦点切到 `RV-910`
- Docs updated:
  - `docs/execplans/QA-910.md`
  - `docs/context-compact.md`
  - `docs/iteration-log.md`

## Entry

### Cycle

- Session: 2026-03-17-main
- Mode: review / read-only
- Goal: 完成 RV-910，判断 standalone video convergence batch 是否通过当前收敛门槛
- What changed:
  - 对 backend/frontend 边界、focused regressions、live persistence evidence 做了 read-only review
  - 没有发现新的 blocking defect
  - 将当前 batch 标记为 review gate success
- Validation and review evidence:
  - FE/BE/QA 产物复核通过
  - `docs/documentation.md` 已记录当前 batch 的收敛结论
- Key risks or failures:
  - 没有新的 blocking review finding
  - 仍存在上游 Veo quota/availability 的运营风险，但不属于本轮架构收敛阻塞项
- Next-cycle hypothesis:
  - standalone video mode 可以暂时收口，后续如继续扩 scope，可再开新的 domain cycle
- Queue/task changes:
  - `RV-910` 标记成功
  - review gate 标记成功
- Docs updated:
  - `docs/documentation.md`
  - `docs/context-compact.md`
  - `docs/iteration-log.md`
