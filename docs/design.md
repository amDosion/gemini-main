# Design Document

## System Overview

- Architecture summary: 当前项目采用 `provider + mode + backend coordinator` 的统一模式架构。视频模式不应例外，业务能力建模应在后端完成，前端只负责输入、展示和历史交互。
- Key modules:
  - frontend video view and controls
  - backend mode router and controls catalog
  - Gemini video coordinator and storyboard helpers
  - attachment persistence and preview delivery

## Frontend Design

- Pages and routes:
  - `frontend/components/views/VideoGenView.tsx`
- Component boundaries:
  - `VideoGenView`：页面级状态、历史列表、结果播放
  - `VideoGenControls`：纯 schema-driven 控件渲染
  - `ChatEditInputArea`：把当前已选控件值打包成 request payload
- State and data flow:
  - `useModeControlsSchema` 拉取 controls schema
  - `useControlsState` 持有纯 UI 选择状态
  - `UnifiedProviderClient` 负责把 request 送到统一 mode API

## Backend Design

- Domain model:
  - `mode_controls_catalog.json` 定义视频模式能力、参数、约束和模型变体
  - `modes.py` 负责 request 入口、参数校验、附件注入和 persistence bridge，但当前仍混有部分业务归一化，需要进一步下沉
  - `VideoGenerationCoordinator` 负责 storyboard、增强、延长与 provider fallback
- API contracts:
  - `GET /api/modes/{provider}/{mode}/controls`
  - `POST /api/modes/{provider}/{mode}`
- Persistence model:
  - 通过现有 session/message/attachment 表完成消息与视频结果持久化

## Integration Design

- Frontend/backend interface:
  - 前端只从 backend schema 获取能力与默认值
  - 前端只提交后端认可的 request fields
  - 需要进一步减少前端 transport 白名单和前端派生业务值，避免重复 contract
- Error handling:
  - 后端负责把上游 quota / invalid argument / internal errors 分类映射给前端
- Versioning strategy:
  - 继续沿用 `mode_controls_catalog` 单一源，不单独引入前端版本化能力表

## DevOps and Runtime

- Environments:
  - 本地开发通过现有 `/api` 代理访问后端
- CI/CD pipeline:
  - 当前 domain 仅要求现有 pytest / vitest / tsc 验证通过
- Deployment and rollback:
  - 以当前后端路由和前端视图文件为主，小步收敛，不做横向大迁移

## QA Strategy

- Unit/integration/e2e strategy:
  - 后端重点验证 controls contract、router 参数注入、coordinator 行为
  - 前端重点验证 VideoGenView 历史/结果区和 controls schema 消费
- Regression strategy:
  - 对现有成功的 video session/history 渲染保持回归覆盖

## Security Design

- Trust boundaries:
  - provider 资产不作为长期前端公开地址
  - 继续走后端代理预览与附件持久化
- Secret management:
  - 维持现有 DB/env 中的 provider 凭据管理
- Threat controls:
  - 避免把前端参考图/视频逻辑变成绕过后端 contract 的旁路

## Observability

- Logs:
  - `modes.py` 与 video coordinator 继续作为关键日志点
- Metrics:
  - 先以请求成功率和错误分类为主
- Alerts:
  - 本轮不新增告警系统，重点是错误分类清晰化

## Research-Driven Boundary Decisions

- `_extract_video_mode_attachment_params()` 当前在 router 内承担了视频附件语义解释，这属于业务归一化，应在后续实现中下沉到后端服务层。
- `video_extension_count` 的可选项和“延长后总时长”不应由前端本地推导，后端 contract 应直接给出合法组合。
- `person_generation`、`subtitle_mode`、`storyboard_prompt`、tracking 语义等字段应继续收敛在 coordinator + storyboard helper，不应由前端页面层定义策略。
