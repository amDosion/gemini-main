# JIRA: 前端 React StrictMode / 重复请求 / 缓存模式全面 audit

## 类型
Perf / Bug Fix / Code Quality

## 状态
**Done — 实施完成（分支 `refactor/frontend-hook-utility-extraction-A` HEAD `92bb92f`）**

按 `HANDOFF.md` §0 #5 plan 模式 + §0 #6 agent teams（Explore × 3 + silent-failure-hunter + type-design-analyzer + architect）。

## 触发

用户多次报告 Network tab 出现 (canceled) 重复请求：
- `/api/modes/google/image-gen/controls?model_id=...` × 2
- `/api/modes/google/video-gen/controls`（一次带 model_id 一次不带）
- `/api/agents (canceled)` + `/api/workflows/history?limit=100 (canceled)`

用户原话："多次遇到这个问题，你应该进行一次全面的分析，还有没有一样的情况"

## 当前事实

### 三类 root cause pattern 识别

1. **"自动 fetch + cleanup abort"**：mount 时 useEffect 创建 AbortController + fetch，
   cleanup 调 abort。React StrictMode dev 双 mount 触发 abort → re-mount 重 fetch，
   在 Network tab 看到 (canceled) + 重 fetch 各一次

2. **"useEffect deps 含 useCallback"**：useCallback deps 包含父 prop / state，
   父 re-render 触发 callback rebuild，useEffect deps 含此 callback 引用 → useEffect 重 fire

3. **"多实例并发 fetch"**：同一 hook 在多个组件实例（如循环渲染中的 N+1 个 selector）
   同时 mount，每个独立 fire fetch（无模块级 cache + in-flight dedupe）

### audit 范围

3 个 Explore agent 并行扫描 `frontend/` 所有 `.ts/.tsx`：
- Pattern 1 命中（AbortController + cleanup）：6 处
- Pattern 2 命中（useEffect deps 含 useCallback）：4 处
- Pattern 3 命中（多实例并发）：2 处

去重后实际修复 **13 处**。

## 实施 commit 索引

| Round | Commit | 修复项 | 处数 |
|---|---|---|---|
| 1 | `b591b82` | `useModeControlsSchema` in-flight dedupe + enabled gate；VideoGenView/ImageGenView/VirtualTryOnView 传 enabled | 1 hook + 3 调用方 |
| 2 | `cabf37b` | `useAgentRegistry` 模块级 cache + in-flight + sequence guard；`useWorkflowHistoryController` ref-mirror + 移除 unmount abort all | 2 处 |
| 3 | `3fa2e25` | `useEnhancePromptModels` 模块级 cache（3 controls 实例并发） / `useSessions:381` ref-mirror refreshSessions / `useInitData:165` 移除 unmount abort / `useSessionSync:67` 移除 unmount cancelInFlightFetch / `AgentManagerPanel:127` 移除 unmount abort / `OllamaModelManager:81` ref-mirror loadModels | 6 处 |
| 4 | `92bb92f` | `useCacheSubscription:19` fallbackRef ref-mirror / `useChat:245` 冗余 deps 改 [] / `useHistoryListActions:46/75` 补 .catch / `usePerformanceOptimization:90` rAF 递归 stopped flag + currentRafId | 4 处 |

## 修复原则（统一指导）

### 原则 1：mount useEffect 不在 cleanup 中 abort 自动 fetch
- StrictMode 双 mount 会触发 cleanup → abort 当前 fetch → re-mount 重新 fire
- fetch 内部已有 isMountedRef + sequence guard 防 setState-after-unmount，无需在 cleanup 强行 abort
- **保留**：user-initiated controllers（如 download cancel、user 主动切换 search/status）
- **保留**：组件真 unmount 时的清理 timer / interval / event listener

### 原则 2：useEffect deps 不包含 useCallback 引用
- 使用 ref-mirror 模式：`const cbRef = useRef(cb); cbRef.current = cb;`
- useEffect 内调 `cbRef.current()`，deps 仅含真实业务 trigger（如 search / sessionId / mode）

### 原则 3：多实例 hook 用模块级 cache + in-flight Promise dedupe
```ts
const dataCache = new Map<key, T>();
const inFlight = new Map<key, Promise<T>>();
```
- mount 自动 fetch 路径：cache hit → 用 cache；cache miss + in-flight hit → 复用 Promise
- user refresh 路径：force re-fetch（不查 in-flight），sequence guard 防 stale 覆盖
- 测试隔离：export `__resetCacheForTesting` 让 vitest beforeEach 调用

## 实际 user 可见收益

- 修复前：image-gen mode 进入后 Network tab 看到 image-gen/controls × 2 (其一 canceled)
- 修复后：1 个有效请求，无 canceled
- 类似收益遍及 8 处 hook / N 个 view

## 验收标准

- [x] 13 处同类 pattern 全部修复
- [x] 85 测试套件 **334/334** 全绿
- [x] `tsc --noEmit` **0 错误**
- [x] `prettier --check` 全过
- [x] 0 处 `as any` / `@ts-ignore` / `@ts-expect-error` 引入
- [x] reviewer agent teams 验证（Explore × 3 + 二次深度 audit）

## 非目标

- 不改 backend（仅前端）
- 不引入新 hook 抽象（每处用最小修复）
- 不动 React StrictMode 配置（StrictMode 是 dev only，反而帮助发现 bug）

## 风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 移除 unmount abort 后真 unmount 时 fetch 仍 in-flight | L | L | isMountedRef + sequence guard 防 setState 副作用；浏览器最终也会自然完成或超时 |
| R2 | 模块级 cache 跨用户 session 污染 | L | M | 通过 subscribeAgentRegistryUpdated 类事件清空；测试导出 reset 函数 |
| R3 | ref-mirror callback 让原 lint exhaustive-deps 警告失活 | L | L | 注释明确说明 ref-mirror 设计目的 |

## 交接备注

- 本工单与 A / A-2 / A-3 / tsconfig-strict 工单共享分支
- 后续新增 fetch hook 时遵循上述 3 原则避免重新引入同类问题
- 推荐 follow-up：写 ESLint 自定义规则检测 "useEffect cleanup 内 abort + useEffect deps 含 callback" pattern

## 数据来源

- 用户 Network tab 实际报告
- Explore agent × 3 并行扫描 `.ts/.tsx`
- 二次深度 audit（确认无遗漏）
- 项目硬规则：`HANDOFF.md` §0 #1-#6
