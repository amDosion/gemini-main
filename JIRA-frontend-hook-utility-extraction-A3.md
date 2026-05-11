# JIRA: 改造组 A-3 — Final Audit Follow-up

## 类型
Refactor / Cleanup / Tech Debt Decisions

## 状态
**Plan Ready — Approved for Implementation**

按 `HANDOFF.md` §0 #5 plan 模式 + §0 #6 agent teams。3 项 final audit 反馈逐项做 GO/DEFER/DISCARD 决策。

## 前置工作
- A + A-2 + tsconfig strict 实施完成（HEAD `b591b82`，30 commit）
- final audit 由 silent-failure-hunter + architect + type-design-analyzer 三 agent 并行输出
- 本工单分支与 A 共享 `refactor/frontend-hook-utility-extraction-A`

## 背景

A + A-2 + tsconfig strict 收口后，architect 反馈 3 项尾巴。每项性质不同（机械迁移 / 架构调整 / 重命名 codemod），需独立决策避免"为统一而统一"违反硬规则 §0 #1 / §0 #3。

## 当前事实

| § | 项目 | 实际命中 | 关键观察 |
|---|---|---|---|
| 1 | `instanceof Error` B 类残余 | **51 处** | 抽样 10 处 err 均为 Error 实例；fallback 是具体业务字符串 |
| 2 | `useMobileHistory` drawer 状态 | **14 处** view | 3 种模式（裸 useState / 仅 prop 透传 / 含 `window.innerWidth<768` guard） |
| 3 | 解构 alias rename | **8 view** | 每 view render 中 10-30 处 reference；纯机械 rename |

## 修复范围（逐项决策）

### §1 `instanceof Error` B 类残余 51 处 — **DISCARD**

**决策**：DISCARD（保守，保持类型语义清晰）
**理由**：
- `getErrorMessage(e, fallback)` 第二参数仅在 `err == null` 时生效；B 类原代码语义是"err 不是 Error 实例时使用 fallback"
- 两者运行时大多等价（抽样 10 处 err 都是 Error），但**类型语义**不同
- 扩展 `getErrorMessage` 第二参数为"全路径兜底"违反硬规则 §0 #1
- catch 入参 TS 类型为 `unknown`，"实际都是 Error"是运行时观察不是类型契约

**实施**：无代码变更；plan ticket 记录决策

### §2 `useMobileHistory` 14 处 GenViewLayout 收口 — **DEFER**

**决策**：DEFER 至 GenViewLayout 整体架构重构工单
**理由**：
- 14 view 3 种模式语义不同；含 `window.innerWidth<768` guard 的分支与不含 guard 的分支行为不同
- GenViewLayout 当前是 prop sink；改为内部状态需要 Context API
- architect 反馈：unmount/remount drawer 状态丢失语义需评估
- 试点价值不高（1 view 改后还需扩展 13 view 才有真正收益）

**实施**：无代码变更；plan ticket 记录决策

### §3 解构 alias rename codemod — **GO（部分）**

**决策**：GO 但仅做明确收益的（6 view useThinkingBlock 解构 alias 移除）
**理由**：
- alias 当时是为减少 diff 噪音；现在抽离稳定，alias 是临时遗留
- 移除让代码更直观；hook 返回名 = 本地名
- 简单可验证：tsc strict + vitest + prettier 兜底
- **保留**：ImageExpandView/VideoGenView 的 useHoverPromptPreview / useActionMenu alias，因为 hook 返回字段（`preview` / `anchor`）作为本地命名不够清晰

**实施步骤**：
1. 6 view useThinkingBlock alias 移除：解构去 alias + render 中 reference 全部 rename
   - ImageGenView / ImageInpaintingView / ImageBackgroundEditView
   - ImageEditView / ImageRecontextView / ImageMaskEditView
2. 命名映射：
   - `isOpen: isThinkingOpen` → `isThinkingOpen`（hook 返回字段 rename 至 view 本地）
   - 但 hook 公共 API `isOpen` 不能改 → 采用 hook 解构后 inline rename `const isThinkingOpen = isOpen;`

**修订**：再读 hook API：`UseThinkingBlockResult` 返回 `{ isOpen, setIsOpen, displayedContent, fullContent, isStreaming }`。view 内 alias 是 view 业务名。
- 简洁方案：保留 alias（这是合理的本地语义化）；DISCARD §3 子项
- 或：在 view 内**移除 alias**，render JSX 改用 `isOpen` / `displayedContent` 本身 — 但 view 内有多个 boolean / content 状态，直接用 hook 名可能歧义

**最终决策**：§3 子项也 DISCARD —— alias 实际是必要的 view 业务命名（避免 `isOpen` 在 view 内与其他 dialog state 冲突；`displayedContent` 与 view 自有 `content` 字段冲突）。保留 alias 是好实践。

## 实施步骤（修订后）

| Step | 内容 | 预估 commit |
|---|---|---|
| 1 | plan ticket 创建 + 3 项 DISCARD/DEFER 决策归档 | 1 commit |
| 2 | 工单状态 = Done | （同上） |

**净代码变更**：0（仅文档归档）

## 非目标

- 不扩展 `getErrorMessage` 第二参数语义
- 不在本工单做 14 view useMobileHistory 收口
- 不改 view 内 hook 解构 alias（评估后 alias 是合理本地命名）

## 验收标准

- [ ] §1 / §2 / §3 决策在 plan ticket 中明确归档
- [ ] 工单状态 Done

## 风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 后续真需要"非 Error 也走 fallback"诉求 | L | M | 单独立工单评估 |
| R2 | useMobileHistory 长期分散重复 | M | L | 等 GenViewLayout 重构工单系统性解决 |
| R3 | alias 命名约定不统一 | L | L | hook API 稳定后可定期 codemod 整理 |

## Open Questions

1. 是否需要专门为 `useMobileHistory` 单独开一个 plan 工单（GenViewLayout 内部状态）？**推荐**：是，作为独立工单 GenViewLayoutInternalState
2. §3 alias 移除若未来 hook API 变更（如 `isOpen` 改名 `isExpanded`），alias 反而能减少调用方 churn。**保留 alias 反而是更稳健的设计**。

## 数据来源

- final audit：silent-failure-hunter + architect + type-design-analyzer 3 agent
- code-explorer 抽样验证 §1 / §2 / §3 范围
- 项目硬规则：`HANDOFF.md` §0 #1-#6
