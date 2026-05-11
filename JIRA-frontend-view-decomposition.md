# JIRA: 前端大文件拆分（>800 行违反 coding-style）

## 类型
Refactor / Code Quality / Maintainability

## 状态
**Plan Backlog — Pending Approval**

按 `HANDOFF.md` §0 #5 plan 模式。本工单仅记录 plan，**不实施**；批准后按 P0 → P3 顺序逐文件单独开 sub-ticket 执行。

## 前置工作

- A / A-2 / A-3 / tsconfig strict / perf audit 5 个 plan ticket 已 Done（归档在 `docs/done/2026-05/`）
- Explore agent 扫描 `frontend/` 找出 11 个 >800 行文件
- architect agent 评估：**推荐合并当前分支后**作为独立工单分批执行（避免本分支 reviewer 疲劳）

## 背景

项目 `~/.claude/rules/common/coding-style.md` 规则：
- 200-400 行典型，**800 max**
- 多个小文件 > 少量大文件
- 高内聚低耦合，按 feature/domain 组织

当前 frontend/ 11 个文件违反 800 max。最大 PropertiesPanel.tsx 4643 行（违反 5.8x）。

## 当前事实

### 11 个 >800 行候选文件（Explore 扫描）

| # | 文件 | 行数 | 违反倍数 | 优先级 |
|---|---|---|---|---|
| 1 | `frontend/components/multiagent/PropertiesPanel.tsx` | 4643 | 5.8x | **P0** |
| 2 | `frontend/components/views/ImageMaskEditView.tsx` | 2161 | 2.7x | **P0** |
| 3 | `frontend/components/multiagent/MultiAgentWorkflowEditorReactFlow.tsx` | 2190 | 2.7x | P1 |
| 4 | `frontend/components/views/VideoGenView.tsx` | 1668 | 2.1x | P1 |
| 5 | `frontend/components/multiagent/WorkflowTemplateSelector.tsx` | 1612 | 2.0x | P1 |
| 6 | `frontend/components/modals/settings/McpTab.tsx` | 1167 | 1.5x | P2 |
| 7 | `frontend/components/views/ImageExpandView.tsx` | 1102 | 1.4x | P2 |
| 8 | `frontend/hooks/handlers/DeepResearchHandler.ts` | 1101 | 1.4x | P2 |
| 9 | `frontend/components/layout/Header.tsx` | 1054 | 1.3x | P2 |
| 10 | `frontend/components/common/ImageHistorySidebar.tsx` | 1038 | 1.3x | P3 |
| 11 | `frontend/services/UnifiedProviderClient.ts` | 974 | 1.2x | P3 |

总超额：约 8000+ 行需被拆分到 30+ 个新文件。

## 修复范围（按优先级）

### P0 #1: PropertiesPanel.tsx (4643 行)

**职责**：multiagent 节点属性编辑面板，处理 5+ 节点类型 + 5+ 表单

**拆分建议**（5 个新文件）：
- `components/multiagent/panels/ResultSection.tsx` (~150 行) — 结果展示
- `components/multiagent/panels/SheetStagePanel.tsx` (~200 行) — sheet stage 状态 UI
- `hooks/useProviderModels.ts` (~100 行) — provider model 选择逻辑
- `components/multiagent/workflowResolution.ts` (~150 行) — resolution 规范化
- `components/multiagent/uploadHandlers.ts` (~120 行) — inline upload handlers
- 主组件保留 ~3000 行（仍偏大但聚焦于状态编排，可下一轮再拆）

### P0 #2: ImageMaskEditView.tsx (2161 行)

**职责**：mask 编辑器（canvas + AI preview）

**拆分建议**：
- `components/views/mask/MaskCanvasPainter.tsx` (~600 行) — canvas 绘制
- `components/views/mask/MaskToolbar.tsx` (~200 行) — 工具栏
- `hooks/useMaskSegmentation.ts` (~150 行) — 语义分割
- `components/views/mask/useMaskIO.ts` (~100 行) — mask 导入/导出
- 主组件保留 ~1100 行

### P1 #3: MultiAgentWorkflowEditorReactFlow.tsx (2190 行)

**拆分**：
- `components/multiagent/workflowExport.ts` (~250 行) — PNG/SVG 导出
- `components/multiagent/workflowGraphUtils.ts` (~200 行) — node/edge 工具
- 主组件保留 ~1300 行

### P1 #4-#5: VideoGenView (1668) + WorkflowTemplateSelector (1612)

详细拆分见 Explore agent 报告（按 audit fact 块组织 player / actionMenu / preview / categoryMgr 等子组件）

### P2 / P3: 剩余 6 文件

详见 audit 报告；统一应用相同模式（按内聚域抽离子组件 / hook / util）。

## 实施步骤

每个文件**独立工单**（避免一次 PR 千行 diff）：
1. 写 plan ticket（含 file:line 拆分边界）
2. agent teams 审核 plan
3. 实施 + tsc strict + vitest 全绿
4. reviewer 验证行为等价性
5. 合并

预计总 effort：**P0 7-10 天 + P1 5-6 天 + P2 4-6 天 + P3 2-3 天 = 18-25 天**。

## 非目标

- 不修改业务行为（pure refactor）
- 不引入新依赖
- 不一次合并所有 11 个文件（每个独立 PR）
- 不强行拆分到 200-400 行（接受 P0 主组件 ~1100-3000 行作为中间态）

## 验收标准

每个 sub-ticket：
- [ ] 拆分前后**行为完全等价**（vitest 覆盖证明）
- [ ] 新文件 ≤800 行
- [ ] `tsc --noEmit` 0 错误
- [ ] reviewer agent teams 验证

## 风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 拆分破坏 props 隐式 contract | M | M | 每子组件保留原 props 形状 + JSDoc 注释 |
| R2 | 单元测试覆盖率不足以保证行为等价 | M | H | 拆分前增量补 test（架构组件级而非单元级） |
| R3 | 工单数量爆炸（11+ sub-tickets） | H | M | 按 P0/P1/P2/P3 4 轮分批，每轮合并后再启下一轮 |

## Open Questions

1. P0 #1 PropertiesPanel 主组件保留 3000 行可接受吗？还是要更激进拆分至 ~800？**推荐**：分两轮 — 本轮拆到 3000 行（功能型），下轮再拆到 ~800（状态编排型）
2. 是否同时引入 `feature/` 顶级目录重构？**推荐**：否，本工单仅拆分不改目录结构

## 数据来源

- Explore agent × 2 扫描 `wc -l` + 业务职责评估
- architect agent 评级 P0-P3 + effort 估算
- `~/.claude/rules/common/coding-style.md` 行数规则

## 交接备注

- 本工单与 A/A-2/A-3 等共享重构分支策略；新分支 `refactor/frontend-view-decomp-*` 每个 P0/P1 文件一个
- 每实施 1 个文件后立即合并避免 rebase 冲突
- coding-style 800 max 由 ESLint 自定义规则强制（可后续工单加 lint）
