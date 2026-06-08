# JIRA: PropertiesPanel.tsx 深度拆分（< 800 行合规 + 业务下沉准备）

## 类型
Refactor / Code Quality / Maintainability

## 状态
**Plan Backlog — Pending Execution**

## 背景

按 `JIRA-frontend-view-decomposition.md` P0 #1 计划完成首轮抽取后，PropertiesPanel.tsx
仍在 3911 行（4.9x 超 `coding-style.md` 800 max）。本工单针对剩余 3 大 render
function 进行深度抽取，目标主组件 < 800 行。

用户明确指示（2026-05-11）："应该还可以抽，单文件少于800行才对，业务能下沉到后端的就给后端"。

## 前置工作（已完成）

PropertiesPanel.tsx 当前状态（commit `066e11b`）：

| 已抽出文件 | 行数 | 来源 commit |
|---|---|---|
| `components/multiagent/workflowResolution.ts` | 145 | `09f2b6b` Step 1 |
| `hooks/useProviderModels.ts` | 70 | `d384fe1` Step 2 |
| `components/multiagent/uploadHandlers.ts` | 47 | `3dde9f1` Step 3 |
| `components/multiagent/panels/ResultSection.tsx` | 135 | `fe5fa3f` Step 4 |
| `components/multiagent/panels/SheetStagePanel.tsx` | 195 | `a19656b` Step 5 |
| `components/multiagent/toolClassification.ts` | 122 | `af63dc4` |
| `components/multiagent/panels/SimpleNodeTypePanels.tsx` | 179 | `fab9d61` |
| `components/multiagent/panels/EndNodeResultPanel.tsx` | 128 | `95afc32` |

累计抽出 `1021` 行至 8 个独立模块；PropertiesPanel 减少 `732` 行（4643 → 3911）。

## 剩余 3 大 render function（需深度拆分）

| Function | 行号 | 行数 | 闭包依赖数 |
|---|---|---|---|
| `renderStartInputNodeConfig` | L318-819 | 501 | ~6 |
| `renderAgentNodeConfig` | L821-2400 | 1579 | ~10 |
| `renderToolNodeConfig` | L2402-3618 | 1217 | ~8 |

**预期目标**：3 个 render function 全部抽出后，主组件 ~600 行（< 800 ✅）。

## 拆分方案

### Step 1: 抽离 `ToolNodeConfigPanel`（最易，先做）

**Closure deps（8 个）**：
```ts
interface ToolNodeConfigPanelProps {
  nodeData: CustomNodeData;
  nodeType: NodeType;
  selectedNode: Node<CustomNodeData>;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
  providers: ProviderModels[];
  providersLoading: boolean;
  workflowVideoSchema: ReturnType<typeof useModeControlsSchema>['schema'];
  workflowVideoControlContract: ReturnType<typeof buildVideoControlContract>;
}
```

**目标文件**：`components/multiagent/panels/ToolNodeConfigPanel.tsx`（~1240 行）

⚠️ 该文件本身仍 > 800，需进一步按 tool 类别拆为子段：
- `ToolImageGenSection.tsx` (~155)
- `ToolImageEditSection.tsx` (~200)
- `ToolVideoGenSection.tsx` (~400 → 进一步拆 audio/subtitle)
- `ToolVideoUnderstandSection.tsx` (~80)
- `ToolVideoDeleteSection.tsx` (~60)
- `ToolPromptOptimizeSection.tsx` (~150)
- `ToolTableAnalyzeSection.tsx` (~70)
- `ToolAmazonAdsSection.tsx` (~120)
- `ToolNodeConfigPanel.tsx` 主分发（~100）

### Step 2: 抽离 `AgentNodeConfigPanel`

**Closure deps（~10 个）**：nodeData + updateNodeData + providers + providersLoading +
selectedNode + workflowVideoSchema + workflowVideoControlContract + resolvedAgent +
agentDefaultAnalysis + selectedAgentTypeRef

**目标文件**：`components/multiagent/panels/AgentNodeConfigPanel.tsx`（~1580 行）

子段拆分（按 agentTaskType）：
- `AgentChatSection.tsx`
- `AgentImageGenSection.tsx`
- `AgentImageEditSection.tsx`
- `AgentVideoGenSection.tsx` ← 最大块，含 audio/subtitle/storyboard
- `AgentAudioGenSection.tsx`
- `AgentVisionUnderstandSection.tsx`
- `AgentDataAnalysisSection.tsx`

### Step 3: 抽离 `StartInputNodeConfigPanel`

**Closure deps**：nodeData + updateNodeData + nodeType + selectedNode + inline 上传 helpers
（已抽出 `uploadHandlers`，只需 fileToBase64 + reportInlineUploadError + readInlineFilesAsDataUrls）

**目标文件**：`components/multiagent/panels/StartInputNodeConfigPanel.tsx`（~500 行）

子段（可选）：按 input_text / input_image / input_video / input_audio / input_file / start 拆分。

## 业务下沉到后端（独立后续 ticket）

用户指示"业务能下沉到后端的就给后端"，识别如下候选：

| 业务逻辑 | 当前位置 | 应下沉到 |
|---|---|---|
| Tool alias 数组（IMAGE_GEN/EDIT/VIDEO_*/...） | `toolClassification.ts` | `/api/agents/tool-registry` API |
| `WORKFLOW_RESOLUTION_MAP`（图片尺寸映射） | `workflowResolution.ts` | `/api/modes/*/controls` 已部分提供，可统一 |
| `WORKFLOW_LEGACY_VIDEO_RESOLUTION_ALIASES` | `workflowResolution.ts` | 后端接收时做兼容映射，前端不再持有 |
| Agent task type 列表（'chat'/'image-gen'/...） | PropertiesPanel L818-827 | `/api/agents/task-types` API |
| Sheet stage 标签（ingest/profile/query/export） | `panels/SheetStagePanel.tsx` | 后端协议 envelope 提供 i18n label |
| 字幕模式校验（'both'/'vtt'/'srt'） | `videoHistoryHelpers.ts` | 后端 controls schema 已有 validSubtitleModes |

后端 API 设计建议（参考 `useModeControlsSchema` 模式）：
```
GET /api/agents/tool-registry
  → { tools: [{ canonicalName, aliases, taskType, capabilities }] }
GET /api/agents/task-types
  → { taskTypes: [{ value, label, category, ... }] }
```

前端缓存策略：与 `useModeControlsSchema` 一致（module-level cache + in-flight Promise dedupe）。

## 实施步骤

### 第一轮（本工单）

按 Step 1 → Step 2 → Step 3 顺序，每步独立 commit，每步：

1. 写出 sub-component 的完整 props 接口
2. 一次性 Copy & Paste 完整 JSX 到新文件，替换闭包引用为 props
3. 主组件 import + 替换调用为 `<NewComponent {...} />`
4. `npx tsc --noEmit` + `npx vitest run` 全绿
5. Reviewer agent（typescript-reviewer + code-reviewer）审核
6. Commit

### 第二轮（独立工单）

进一步细分子段（按 task type），目标每个文件 200-400 行。

### 第三轮（独立工单）

业务下沉到后端：
- 设计 `/api/agents/tool-registry` API
- 后端补全 tool taxonomy 单一来源
- 前端切换 `classifyToolNode` 为 `useToolRegistry()` hook 消费

## 验收标准

第一轮完成后：
- [ ] `PropertiesPanel.tsx` < 800 行
- [ ] 所有新增 sub-component 文件 < 800 行（或文档说明下轮再拆）
- [ ] `tsc --noEmit` 0 错误
- [ ] `vitest run` 84/329 全绿
- [ ] reviewer agent teams 验证行为等价

## 风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 1234 行 ToolNodeConfigPanel 闭包变量遗漏 → 运行时崩溃 | M | H | Explore agent 严格 grep 验证；分阶段提交便于回滚 |
| R2 | useMemo / useCallback hook 序列改变导致 React 警告 | L | M | 不在抽离过程改 hook 顺序；只搬 JSX |
| R3 | TypeScript 严格模式下 closure 类型不传递 | M | M | 显式声明 props 接口；不依赖推导 |
| R4 | reviewer agent 报噪音误判 | M | L | 在 commit message 说明"1:1 行为等价" |

## 数据来源

- Explore agent × 1 闭包扫描结果（详见会话记录）
- `~/.claude/rules/common/coding-style.md` 800 max 规则
- 用户 2026-05-11 指示

## 交接备注

- 本工单与 `JIRA-frontend-view-decomposition.md` 共享分支策略
- 每实施 1 个 Step 后立即合并避免 rebase 冲突
- 子段拆分（第二轮）建议在第一轮合并后启动
