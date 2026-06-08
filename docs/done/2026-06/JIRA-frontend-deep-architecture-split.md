# JIRA: 前端剩余 10 个文件深度架构拆分

## 类型
Refactor / Architecture / Maintainability

## 状态
**Plan Backlog — Pending Execution**

## 背景

经过 37+ 次抽离 commits，前端已有 12 个文件达成 < 800 行合规。剩余 10 个文件
均为单一巨型组件（800-2078 行），仅靠 helper-extraction 无法继续瘦身。本工单为
这 10 个文件做架构性拆分规划，原则：

1. **能下沉后端的就下沉**：业务规则、数据归一化、taxonomy 等
2. **能抽 hook 的就抽 hook**：状态机、副作用、API 调用
3. **能拆 sub-component 的就拆**：每个独立 UI 段（dialog、card、panel）独立文件
4. **保证 1:1 行为等价**：每个 commit 单独通过 tsc + vitest

## 10 个文件拆分方案 + ROI 排序

详见后续 sub-tickets。执行顺序按 ROI（投入产出比）从高到低：

1. **adkSessionService.ts** (1639) — 纯 service 文件，最简单（无 React closure），最大体积
2. **WorkflowTemplateSelector.tsx** (1480) — 一组明确 sub-component
3. **VideoGenView.tsx** (1584) — useVideoPlayerControls 是清晰 hook
4. **McpTab.tsx** (1042) — Dialog + Card 清晰拆分
5. **Header.tsx** (1009) — SystemConfigDialog + UserInfoDialog 清晰
6. **MultiAgentWorkflowEditorReactFlow.tsx** (2078) — 最大但耦合最深
7. **ImageHistorySidebar.tsx** (904) — 内部 hook 抽离
8. **ImageMaskEditView.tsx** (1175) — 已抽 50%，剩余主体
9. **ImageExpandView.tsx** (1102) — 单体一体化
10. **App.tsx** (821) — 边缘超限

每个文件分多个 commits，每 commit 单独 tsc + vitest 验证。

## 后端下沉 sub-ticket

识别出的 6 类需后端 API 提供：

1. `GET /api/agents/tool-registry` — tool taxonomy（aliases + capabilities）
2. `GET /api/agents/task-types` — agent task type 枚举
3. `GET /api/admin/config-schema` — 系统配置字段元数据
4. `POST /api/multi-agent/workflows/validate` — workflow 合法性验证
5. `GET /api/templates`（已存在）— 返回已规范化数据，前端不再 migrateTemplate
6. ADK runtime envelope schema — 错误消息 i18n + structured payload

## 验收

- [ ] 10 个目标文件全部 < 800 行
- [ ] 所有新增 sub-component / hook 文件 < 800 行
- [ ] 每个 commit `tsc --noEmit` 0 错误
- [ ] 每个 commit `vitest run` 全绿
- [ ] 行为完全 1:1 等价
