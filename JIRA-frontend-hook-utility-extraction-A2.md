# JIRA: 改造组 A-2 — Frontend Hook / Utility 抽离 Follow-up

## 类型
Refactor / Code Quality / Maintainability

## 状态
**Plan Ready — Approved for Implementation**

按 `HANDOFF.md` §0 #5 plan 模式 + §0 #6 agent teams 验证。

## 前置工作
- 改造组 A 工单（`JIRA-frontend-hook-utility-extraction.md`）实施完成 — 分支 `refactor/frontend-hook-utility-extraction-A` HEAD `4b00ad7`，17 commit
- 本工单实施分支与改造组 A 共享（不另起分支，作为 A 的延续）
- planner agent + code-explorer agent 并行 fact 验证完成

## 背景

改造组 A 完成后，plan ticket §Defer 列出 6 项 follow-up。本工单逐项做 **GO / DEFER / DISCARD / REFERENCE** 决策，避免过度抽象（违反硬规则 §0 #1 / §0 #3）。

## 当前事实

### 6 项 follow-up 精准 fact（code-explorer 在 `4b00ad7` 验证）

| § | 项目 | 实际命中 | 关键观察 |
|---|---|---|---|
| 1 | useMobileHistory | **14 处** view（plan §1 估算 8 处过低） | 3 种模式（直接 useState / 仅 prop 传递 / 含 `window.innerWidth<768` guard） |
| 2 | useAsyncState 剩余候选 | **0 个**真正"纯 async wrapper" | 全部候选含 AbortController / 多源 setError / 多路 setData 至少一项 |
| 3 | useEscapeClose 未迁 | **8 处** | 4 处纯单键 Escape / 4 处含 Enter 共享 handler |
| 4 | safeJsonParse 散落 | **4 处** wrapper（第 4 处 = `useWorkflowExecutionStream.ts:34 parseSseEventData`） | 3 处含额外 schema 守卫（{}/[ 边界 / isRecord / MessageEvent 类型） |
| 5 | `instanceof Error` B 类残留 | **68 处** | 抽样 10 处中 err 实际都是 Error 实例（fetch/async throw） |
| 6 | tsconfig strict | **未开** | 所有 strict 子项（strict/noImplicitAny/strictNullChecks/strictFunctionTypes/noImplicitReturns）均未设置 |

## 修复范围（逐项决策）

### §1 useMobileHistory drawer state 14 处 — **DEFER**

**决策**：DEFER 至 `GenViewLayout` 重构工单
**理由**：架构层级问题。`isMobileHistoryOpen` 本属于 `GenViewLayout` 内部状态（共享布局壳的 drawer 关注点），不应外抛到每个 view 再抽离 hook。先抽 hook 会形成"hook → 后续被 layout 内化"的二次重构。

### §2 useAsyncState 剩余适配 — **DISCARD**

**决策**：DISCARD，关闭 plan §A.1.3 "4+ 处候选"命题
**理由**：code-explorer 验证 0 个真正合格 callsite。`useCacheStatus` / `useAuth.{register,login,logout}` / `useAgentRegistry` / `useWorkflowHistoryController` / `useCloudStorageActions` 全部含 hook 设计假设不支持的副作用（abort / 多源 error / 局部 setData / 外部 props 驱动 data）。`useAsyncState` 保留为 hook 库的工具 — 未来真正需要"纯 async 包装"时使用。

### §3 useEscapeClose 未迁移 — **DISCARD（修正自原 GO 决策）**

**决策**：DISCARD，**全部 8 处 inline Escape 不适合精准迁移**。
**实施修正**：planner agent + code-explorer 初判"4 处纯单键可迁"基于行级 grep，未看 useEffect 复合结构。实际 read 后发现：
- `WorkflowResultPanel.tsx:182` — 含 ArrowLeft/ArrowRight 同 handler（不是纯单键）
- `ChatControls.tsx:327/356/385` — 3 处嵌在含 mousedown/resize/scroll 的复合 useEffect 内（拆出会增加全局 keydown listener 数）
- `WorkflowTemplateCategoryCreateDialog.tsx:41` / `SearchInput.tsx:24` / `SessionSwitcher.tsx:175` / `SessionList.tsx:183` — 4 处含 Enter 共享 handler

按 §0 #3 精准修复原则，**全部保留 inline**。

**事实修正**：plan agent 报告 `useEscapeClose` "0 调用" 错误。实际 hook 已被 6 个文件使用：
`ActionDialog.tsx`、`PersonaModal.tsx`、`ImageModal.tsx`、`SettingsModal.tsx`、`McpTab.tsx`、`Header.tsx` — hook 本身有真实生产消费，只是 8 处 inline Escape 不适合迁移到它。

### §4 safeJsonParse 散落 4 处 — **GO（部分）**

**决策**：GO，扩展 `safeJsonParse` 添加 `guard?: (v: unknown) => v is T` 重载；迁移 3 处含 schema 守卫的；保留 1 处 throw 语义的 inline。

**实施**：
- `adkSessionService.ts:391 parseJsonObject`（{} 守卫 + isRecord）→ 迁移：`safeJsonParse(value, null, isRecord)`
- `sheetStageService.ts:122 parseJsonValue`（{ 或 [ 守卫）→ 迁移：`safeJsonParse(value, null, /* objectOrArrayGuard */)`
- `useWorkflowExecutionStream.ts:34 parseSseEventData`（MessageEvent 守卫）→ 评估迁移可行性
- `AdkSessionPanel.tsx:35 parseOptionalJson`（throw 不接 + 空串返 undefined）→ **保留 inline**，注释说明 throw 语义不属于 "safe" 范畴

### §5 68 处 `instanceof Error` B 类 — **DISCARD**

**决策**：DISCARD 批量改造
**理由**：B 类语义为"err 非 Error 时使用 business-specific fallback"，`getErrorMessage(e, fallback)` 现有语义为"err == null 时使用 fallback"。两者语义边界不同。虽然 code-explorer 抽样 10 处 err 实际都是 Error 实例（机械替换在运行时等价），但**类型语义**不一致；扩展 `getErrorMessage` 第二参数为"全路径兜底"违反硬规则 §0 #1 禁止补丁式修改。68 处分散在不同错误分支，inline `instanceof Error` 三元式表达力直接，强行抽象反而降低可读性。

### §6 tsconfig strict — **REFERENCE**

**决策**：不在本工单实施，已有独立工单 `JIRA-frontend-tsconfig-strict.md` 跟踪。

## 实施步骤

| Step | 内容 | 预估 commit |
|---|---|---|
| 1 | §3 useEscapeClose 4 处迁移 + 4 处 inline 加 SKIP 注释 | 1 commit |
| 2 | §4 safeJsonParse `guard?` 重载 + 测试 + 3 处迁移 | 1-2 commit |
| 3 | reviewer 验证（typescript-reviewer + code-reviewer 并行） | 反馈修复按 §0 #4 全级别修 |
| 4 | 更新 plan ticket 状态 = Done + 回填 commit hashes | 1 commit |

## 验收标准

- [ ] `useEscapeClose` 调用数从 0 升至 4，签名向后兼容（保留 `enabled`）
- [ ] `safeJsonParse` 调用数从 0 升至 3，新增 `guard?` 可选参数且旧签名 0 调用者无破坏
- [ ] §1 / §2 / §5 / §6 在本工单显式标记决策不留歧义
- [ ] 未迁移 callsite 加注释说明原因
- [ ] `tsc --noEmit` 0 错误，`vitest run` 327/327 全绿
- [ ] reviewer agent teams 全级别 finding 修复（HANDOFF §0 #6）

## 非目标

- 不重构 `GenViewLayout`
- 不批量推广 `useAsyncState`
- 不批量改写 `instanceof Error`
- 不动 `tsconfig.strict`
- 不引入新依赖

## 风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | safeJsonParse `guard?` 重载在 strict=false 下类型推断宽松 | L | L | 显式标注 `T` 泛型 + 测试覆盖 |
| R2 | §3 含 Enter 共享 handler 实际可拆分但未迁 | L | L | 加 inline 注释指向 §4 follow-up（"含 Enter 需先拆分"） |
| R3 | §4 useWorkflowExecutionStream parseSseEventData 实际不能迁（MessageEvent 守卫复杂） | M | L | 实施时复核，无法迁则保留 inline + 注释 |

## Open Questions

1. `safeJsonParse` 的 `guard?` 重载是否要独立函数名（如 `safeJsonParseAs<T>`）以保持单一职责？**推荐答案**：直接扩展（可选参数，向后兼容；hook 接受可选 guard 比独立函数更符合"参数化抽象"原则）。

## 交接备注

- 与改造组 A 共享分支 `refactor/frontend-hook-utility-extraction-A`，HEAD `4b00ad7` 起步
- agent teams 三时点强制（plan 完成已做 / 每 Step commit 后 reviewer / 最终一致性 audit）

## 数据来源

- plan agent 输出：完整 6 项决策（来自上轮）
- code-explorer agent 输出：6 项精准 fact（含 file:line 验证）
- 项目硬规则：`HANDOFF.md` §0 #1-#6
