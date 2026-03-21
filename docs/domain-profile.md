# Domain Profile

## Active Domain

- Profile: backend-first-video-mode-convergence
- Goal: 将视频模式收敛为“后端定义能力与业务规则，前端只消费 contract 与展示结果”的单一源架构。
- Objective: 统一 `google/video-gen` 的模式语义、参数 contract、参考输入、延长逻辑、storyboard 逻辑与结果持久化边界，避免前端继续承载业务判断。

## Active Scope

- 视频模式页面：`frontend/components/views/VideoGenView.tsx`
- 视频参数面板：`frontend/controls/modes/google/VideoGenControls.tsx`
- 视频参数状态与 schema 消费：`frontend/hooks/useControlsState.ts`, `frontend/hooks/useModeControlsSchema.ts`
- 视频发送链：`frontend/components/chat/ChatEditInputArea.tsx`, `frontend/services/providers/UnifiedProviderClient.ts`
- 统一模式路由：`backend/app/routers/core/modes.py`
- controls 单一源：`backend/app/config/mode_controls_catalog.json`, `backend/app/services/common/mode_controls_catalog.py`
- 视频业务协调：`backend/app/services/gemini/coordinators/video_generation_coordinator.py`
- 视频 prompt / storyboard / 字幕辅助：`backend/app/services/gemini/base/video_storyboard.py`, `backend/app/services/gemini/base/video_common.py`

## Role Priorities

### Primary

- `backend`
- `reviewer`

### Secondary

- `frontend`
- `qa`

### Support

- `project_owner`

## Phase Model

- Session model: main-agent-phased
- Same-run continuation required: yes
- Analysis boundary required: yes
- Main agent owns self research: yes
- Preplanned downstream innovation allowed: no

## Domain Rule

- 前端不定义视频模式业务能力集合；前端只消费后端 controls schema 和后端返回的结果 contract。
- 视频模式的“生成类型语义”应由后端统一表达，例如：text-to-video、reference-to-video、extend-video，而不是由前端零散状态隐式拼装。
- `storyboardPrompt`、字幕策略、人物生成策略、延长规则、参考图限制、分辨率/时长耦合规则必须以后端为单一源。
- 参考目录中的能力只能作为“能力模型与交互结构”借鉴，不能把前端直调 SDK 的模式直接迁入当前项目。
- 在 reviewer gate 通过前，不允许把 scope 扩展到 workflow 域；当前只处理视频模式本身。
