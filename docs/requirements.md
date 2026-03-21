# Requirements Document

## Product Goal

- Problem statement: 当前视频模式可以工作，但模式语义、能力边界和一部分业务判断分散在前后端，导致穿搭/参考图/延长/字幕等能力扩展时容易漂移，且参考目录中的能力无法有序吸收。
- Target users: 在本项目内使用 Gemini/Google 视频模式进行文生视频、图生视频、视频延长和穿搭素材生成的业务用户与内部运营人员。
- Success criteria: 视频模式形成后端优先的单一源 contract，前端只消费 schema 与结果；当前视频历史、播放、参数面板和实际生成链保持可用。

## In Scope

- Must-have features:
  - 统一视频模式能力建模
  - 明确参考图、首末帧、延长、穿搭/场景锁定等能力边界
  - 视频历史与结果显示保持稳定
  - 吸收参考目录中有价值的交互模型与 prompt 结构
- Frontend scope:
  - `VideoGenView` 与 `VideoGenControls` 改为后端 contract 驱动
  - 保持结果区、历史列表、参数面板的用户体验
- Backend scope:
  - `mode_controls_catalog`、`modes.py`、video coordinator、storyboard helpers 的 contract 统一
  - 补齐视频模式元数据与持久化语义

## Out of Scope

- Workflow 视频模板与多智能体工作流域
- 重新设计整套通用聊天历史系统
- 引入前端直连 Google SDK 的调用模式

## Functional Requirements

1. 后端必须定义视频模式支持的能力集合与约束，至少覆盖：text-to-video、reference-driven video、video extension、storyboard prompting。
2. 前端必须通过 `/api/modes/{provider}/{mode}/controls` 读取视频能力与参数，而不是在页面内定义独立业务规则。
3. 视频生成成功后，会话、消息、附件、历史元数据和预览链接必须保持可回放、可持久化、可在历史列表显示。
4. 参考目录中可借鉴的功能只可作为 backend-first 架构下的能力模型或 UI 结构参考，不能绕开现有 provider/mode/coordinator 体系。

## Non-Functional Requirements

- Performance: 视频模式 controls 获取与页面初始化不得引入明显额外阻塞；预览播放保持流畅。
- Reliability: 后端必须对上游 429/500/503 等错误保持明确分类，避免前端拿到模糊失败。
- Security: 继续沿用后端代理预览与附件持久化，不暴露未受控的 provider 下载链接给前端作为长期地址。
- Observability: 视频模式失败需要在路由或协调器层具备明确 requestId / 错误分类。

## Acceptance Criteria

1. 当前视频模式的主要业务判断边界被文档化，并写入实施队列。
2. 至少有一轮实施任务专门把视频模式 business logic 向 backend contract 收敛。
3. 参考目录的借鉴项与拒绝项都有明确去向，不再是“看过但未落地”的状态。

## Risks and Open Questions

- Risk: Gemini / Veo 上游配额和可用性波动会影响 live 验证节奏。
- Risk: 现有前端视频视图承载了较多交互细节，收 contract 时容易引入 UI 回归。
- Question: `person_generation` 在 controls schema 与上游 extension 能力之间仍存在不完全一致，需要在 backend-first 方案里明确降级策略。
