# JIRA: 改造组 A — Frontend Hook / Utility 抽离

## 类型
Refactor / Code Quality / Maintainability

## 状态
**Plan Review — Pending User Approval**

按 `HANDOFF.md` §0 #5 项目硬规则，本工单为 plan 阶段产物。批准后才进入实施；实施期按 §0 #6 启动 agent teams 并行 spot-check。

## 前置工作（已完成）
- `docs/REPETITION-AND-PERF-ANALYSIS.md` §1 — 由 4 个并行 reviewer agent 输出的重复代码分析（commit `9bcc8db`）
- 实施前交叉验证：
  - `Explore` agent 在 commit `9bcc8db` 时点验证 §1 全部 11 条 file:line 引用（结论：全部 PASS，0 失效）+ 4 条漏网 finding
  - `everything-claude-code:architect` agent 五维评审（接口契约 / 放置位置 / 测试策略 / 迁移策略 / 范围边界）

## 背景
按 `docs/REPETITION-AND-PERF-ANALYSIS.md` §5 "综合改造路线图"中"改造组 A"的内容：前端代码存在 7 类典型重复模式（44+ 处复制），可通过抽离 5 个 React hook + 2 个 utility 收口。本工单是改造组 A 的实施前 plan。

不属于本工单（按 architect 建议拆出）：
- §1 #2 `useMobileHistory` 8 处 → 拆 A-2（建议改 `GenViewLayout` 内部状态，而非新增 hook）
- §1 #7 API 调用三轨统一 → 独立 ticket（services/ 层架构决策，跨域）
- §1 #8 `useAsyncState` 剩余 3 处批量替换 → 拆 A-2（本工单仅做 1 处试点）
- §1.2 `PROVIDER_IDS` 枚举 → 归改造组 D-Tier1（跨层枚举单源）
- §1.2 `WorkflowHistoryItem` 移位 → 独立小 ticket

## 当前事实

### 项目结构 / 测试约定（来自实施前调查）

- `frontend/hooks/` 已有 28+ hooks；新 hook 命名风格 `use<Verb><Noun>`
- `frontend/hooks/handlers/` 是 chat/agent message strategy 子树，已有 `attachmentUtils.ts:218:fileToBase64`
- `frontend/utils/` 已有 13 utilities 含 `safeOps.ts:safeJsonParse`、`globalErrorHandler.ts`
- `frontend/hooks/useEscapeClose.ts` 已存在但 4-5 处未迁移
- 测试约定：**与源同目录**（如 `useSessionSync.test.tsx` ↔ `useSessionSync.ts`），**不用 `__tests__/` 子目录**
- 测试库：`@testing-library/react@^16.3.2`（含内置 `renderHook`，**不需** deprecated `react-hooks` 包）+ `@testing-library/jest-dom@^6.9.1` + `vitest@^3.2.4`
- `package.json` 无 `lodash` / `lodash-es` → `debounce` 手写不引依赖
- 所有 `ImageMaskEditView` FileReader 调用经 grep 确认均为 `readAsDataURL` → 不需 `fileToText`

### Explore 验证结果摘要

| § Ref | 验证状态 | 实际行数 / 量化 |
|---|---|---|
| §1 #1 useThinkingBlock | PASS 6 处 | 每处 18-21 行；逐字相同，仅 `ImageRecontextView:480` 依赖数组多 1 项 |
| §1 #3 fileToBase64 | PASS 6 处 | `readAsDataURL` 包装，签名一致 |
| §1 #4 getErrorMessage | PASS **23 处**（实际比 §1 报告的 20 处多 3） | 完全逐字相同 |
| §1 #5 debounce | PARTIAL | useSettings(11 行完整) vs usePerformanceOptimization(8 行精简) vs App.tsx(1 行 inline) — 行为有细微差异 |
| §1 #6 useHoverPromptPreview | PARTIAL | ImageExpandView 5 字段 vs VideoGenView 9-10 字段（含 `extensionCount/totalDurationSeconds/strategyLabel/subtitleLabel/subtitleCount`）—— 需泛型 |
| §1 #9 useEscapeClose | PASS 4-5 处 | hook 存在但 0 处调用方 |
| §1 #11 useActionMenu | PARTIAL | ActionMenuAnchor 类型完全相同；定位 effect 待 plan 阶段 read 验证差异 |

### Explore 漏网发现（4 项，并入 A）

1. **JSON 解析散落 4 处**：`AdkSessionPanel.tsx:35`、`adkSessionService.ts:391`、`sheetStageService.ts:123`、`workflowUtils.ts:381` —— 各自定义 `parseOptionalJson / parseJsonObject / parseJsonValue`；`safeOps.ts:safeJsonParse` 已存在但 **0 处调用**
2. **`HoverPromptPreview` 字段差异化**：通过泛型 P 在 hook 接受（不是简单合并）
3. **`ActionMenuAnchor` 完全相同**（2 处可直接共享类型）
4. **`useEscapeClose` 5 处未迁中 ≥2 处实际不能用现有签名**（多键 / 级联 state），需保留 inline 或扩展 hook

## 修复范围（改造组 A 最终清单）

### A.1 新增 5 个 React Hook

#### A.1.1 `useThinkingBlock` — `frontend/hooks/useThinkingBlock.ts`

接口签名：

```ts
export interface UseThinkingBlockOptions {
  chunkSize?: number;   // default 5
  delayMs?: number;     // default 30
  autoOpen?: boolean;   // default true
}

export interface UseThinkingBlockResult {
  isOpen: boolean;
  setIsOpen: React.Dispatch<React.SetStateAction<boolean>>;
  displayedContent: string;
  fullContent: string;
  isStreaming: boolean;
}

export function useThinkingBlock(
  messages: readonly Message[],
  loadingState: string,
  options?: UseThinkingBlockOptions,
): UseThinkingBlockResult;
```

**边界条件**：空 messages → 空 displayedContent；`loadingState === 'idle'` → 一次性 snap 到 fullContent；卸载时 `clearTimeout`；非 text thought parts → 保留 `[图片思考过程]` placeholder。

**调用方迁移**：6 个 view（`ImageGenView` / `ImageInpaintingView` / `ImageEditView` / `ImageMaskEditView` / `ImageRecontextView` / `ImageBackgroundEditView`），平均每处 18-21 行 → 单行 hook 调用。

#### A.1.2 `useHoverPromptPreview<P>` — `frontend/hooks/useHoverPromptPreview.ts`

泛型 P 支持 ImageExpandView (5 字段) 与 VideoGenView (10 字段) 两种 payload。

```ts
export interface HoverPromptPreviewBase {
  messageId: string;
  anchorX: number;
  anchorY: number;
  originalPrompt: string;
  optimizedPrompt: string;
}

export interface UseHoverPromptPreviewResult<P extends HoverPromptPreviewBase> {
  preview: P | null;
  position: { top: number; left: number; arrowOffsetY: number } | null;
  size: { width: number; height: number } | null;
  panelRef: React.RefObject<HTMLDivElement>;
  openPreview: (payload: P) => void;
  closePreview: () => void;
  scheduleClose: (delayMs?: number) => void;
  cancelScheduledClose: () => void;
  startResize: (e: React.MouseEvent) => void;
  isResizing: boolean;
}

export function useHoverPromptPreview<
  P extends HoverPromptPreviewBase = HoverPromptPreviewBase
>(): UseHoverPromptPreviewResult<P>;
```

#### A.1.3 `useAsyncState<T, Args>` — `frontend/hooks/useAsyncState.ts`

```ts
export interface UseAsyncStateOptions<T> {
  initialData?: T | null;
  onSuccess?: (data: T) => void;
  onError?: (err: unknown) => void;
}

export interface UseAsyncStateResult<T, Args extends unknown[]> {
  data: T | null;
  loading: boolean;
  error: string | null;
  execute: (...args: Args) => Promise<T | null>;
  reset: () => void;
}

export function useAsyncState<T, Args extends unknown[] = []>(
  asyncFn: (...args: Args) => Promise<T>,
  options?: UseAsyncStateOptions<T>,
): UseAsyncStateResult<T, Args>;
```

**边界**：`isMountedRef` 防卸载 setState；连续 `execute` 用 sequence id 丢弃 stale 结果；error 走 `getErrorMessage` 归一化。

**本工单只迁 1 处试点**（推荐 `OllamaModelManager.tsx:45` 最简单），剩余 3 处拆 A-2。

#### A.1.4 `useActionMenu` — `frontend/hooks/useActionMenu.ts`

```ts
export interface ActionMenuAnchor {
  messageId: string;
  anchorX: number;
  anchorY: number;
}

export interface UseActionMenuResult {
  anchor: ActionMenuAnchor | null;
  position: { top: number; left: number } | null;
  panelRef: React.RefObject<HTMLDivElement>;
  open: (anchor: ActionMenuAnchor) => void;
  close: () => void;
  isOpen: boolean;
}

export function useActionMenu(): UseActionMenuResult;
```

调用方：`ImageExpandView` + `VideoGenView`。

#### A.1.5 `useEscapeClose` 调用方迁移（已有 hook）

不新建 hook；只迁移 4-5 处未调用方中**签名匹配**的子集（plan 阶段逐一 read 验证）：
- `WorkflowResultPanel.tsx:182` — **保留 inline**（多键 Escape + ArrowLeft + ArrowRight，lightbox 导航）
- `WorkflowTemplateSelector.tsx:235` — **保留 inline**（3 级 state machine 级联）
- `WorkflowTemplateSaveDialog.tsx:269` — plan 阶段确认后迁移
- `WorkflowTemplateCategoryCreateDialog.tsx:41` — plan 阶段确认后迁移
- `useCloudStorageViewer.ts:148` — plan 阶段确认后迁移

不扩展 `useEscapeClose` 增加 `additionalKeys` 参数（保持单一职责）。多键场景的统一收口属于 follow-up。

### A.2 新增 2 个 Utility

#### A.2.1 `getErrorMessage` — `frontend/utils/errorMessage.ts`

```ts
export function getErrorMessage(err: unknown, fallback?: string): string;
```

行为：
- `err instanceof Error` → `err.message`
- `typeof err === 'string'` → 原样返回
- `err == null` → `fallback ?? 'Unknown error'`
- `err` 形如 `{ message: string }`（axios-like 鸭子类型） → `err.message`（**推荐采纳**，常见场景）
- 其他 → `String(err)`（**不**用 `JSON.stringify`，规避循环引用）

**调用方迁移**：23 处机械替换。

#### A.2.2 `debounce` — `frontend/utils/debounce.ts`

```ts
export interface DebouncedFn<Args extends unknown[]> {
  (...args: Args): void;
  cancel: () => void;
  flush: () => void;
}

export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number,
): DebouncedFn<Args>;
```

**调用方迁移**：3 处（`useSettings.ts:78` 私有 debounce / `usePerformanceOptimization.ts:62` / `App.tsx:354` inline）。

### A.3 现有 Utility / Hook 迁移

| 项 | 已有位置 | 迁移目标 | 调用方数 |
|---|---|---|---|
| `fileToBase64` | `hooks/handlers/attachmentUtils.ts:218` | 6 处 inline FileReader 改用 `fileToBase64` | 6 |
| `safeJsonParse` | `utils/safeOps.ts:6` | 至少 `AdkSessionPanel.tsx:35` 替换（其余 3 处 JSON 工具函数评估是否同 batch） | 1-4 |
| `useEscapeClose` | `hooks/useEscapeClose.ts:9` | 2-3 处签名匹配的（见 A.1.5） | 2-3 |

### A.4 共享 Type 抽离

- `ActionMenuAnchor` / `ActionMenuPosition` 移到 `frontend/hooks/useActionMenu.ts` 内 export
- `HoverPromptPreviewBase` / `HoverPromptPreviewSize` / `HoverPromptPreviewPosition` 移到 `useHoverPromptPreview.ts` 内 export

## 非目标 / 拆出

- **拆 A-2**：`useMobileHistory`（8 处）— architect 推荐改 `GenViewLayout` 内部状态
- **拆 A-2**：`useAsyncState` 剩余 3 处批量替换（试点验证后再做）
- **独立 ticket**：API 调用三轨统一（`apiClient` / `requestJson` / 裸 fetch）— 跨 services/ 架构决策
- **独立 ticket（归 D-Tier1）**：`PROVIDER_IDS` 枚举跨层单源
- **独立小 ticket**：`WorkflowHistoryItem` 类型文件移位
- **独立 follow-up**：扩展 `useEscapeClose` 支持多键（仅当确认 ≥3 处需要时再做）

## 验收标准

### 强约束

- [ ] 5 个新 hook + 2 个新 utility 全部带测试，**与源同目录** `*.test.ts` / `*.test.tsx`
- [ ] 每个新 hook / utility 至少 3 个测试 case（含边界 / 卸载安全 / 错误路径）
- [ ] §1 #1 useThinkingBlock 6 处复制**全部**替换（不允许部分迁移）
- [ ] §1 #4 getErrorMessage 23 处机械替换**全部**完成
- [ ] §1 #3 fileToBase64 6 处 inline FileReader **全部**改用现有 helper
- [ ] §1 #5 debounce 3 处统一为新 utility，`useSettings.ts:78` 私有实现删除
- [ ] §1 #6 useHoverPromptPreview 2 处替换
- [ ] §1 #11 useActionMenu 2 处替换
- [ ] §1 #10 `AdkSessionPanel.tsx:35` parseOptionalJson 改用 `safeJsonParse`
- [ ] `frontend/` 现有所有 `vitest` 测试**全部通过**（无回归）
- [ ] `tsc --noEmit` 0 error
- [ ] 改动覆盖 PR description 含**前后对比量化**：消除 N 行复制代码 / 多少文件减少

### 软约束

- [ ] `useAsyncState` 1 处试点迁移含 mock-based 测试
- [ ] `useEscapeClose` 至少 2 处迁移；其余明确 verdict（migrate/keep）写在 PR description

## 建议实现步骤（按 §0 #5 + #6）

按依赖顺序，**单 PR 内分 Step commit**（避免接续 PR 排队但保留可 revert 粒度）：

### Step 0 — Plan 批准
本工单获得 user 批准（5 个 Open Questions 已决策）

### Step 1 — Utility 落地（独立 commit）
- 写 `frontend/utils/errorMessage.ts` + 测试
- 写 `frontend/utils/debounce.ts` + 测试
- 跑测试绿
- **agent team 中检**：`typescript-reviewer` × 1

### Step 2 — Hook 落地（独立 commit）
- 写 `useThinkingBlock` / `useHoverPromptPreview` / `useAsyncState` / `useActionMenu` 4 个 hook + 测试
- 跑测试绿
- **agent team 中检**：`typescript-reviewer` × 1 + `code-reviewer` × 1

### Step 3 — 调用方批量迁移（独立 commit per 主题）

按主题拆 4 个 commit：

- 3.1 `useThinkingBlock` 6 处替换 + `fileToBase64` 6 处替换（image view 主题）
- 3.2 `getErrorMessage` 23 处机械替换
- 3.3 `debounce` 3 处替换 + 删 `useSettings.ts:78` 私有实现
- 3.4 `useHoverPromptPreview` + `useActionMenu` + `useEscapeClose` 调用方替换 + `safeJsonParse` 替换

### Step 4 — 实施后复审（按 §0 #6 后置）
- 跑 split-role agent teams（≥3 个）做 ship-readiness 复审：
  - `typescript-reviewer`（hook 实现正确性 + 类型完整性）
  - `code-reviewer`（commit 一致性 + 命名一致性）
  - `performance-optimizer`（是否引入 re-render 或 effect 性能退化）
- 任一 NO-GO 必须修复后再 push

## 推荐测试命令

```bash
cd /mnt/user/appdata/gemini-main

# 新 hook / utility 单元测试
npm run test -- frontend/hooks/useThinkingBlock.test.ts
npm run test -- frontend/hooks/useHoverPromptPreview.test.ts
npm run test -- frontend/hooks/useAsyncState.test.ts
npm run test -- frontend/hooks/useActionMenu.test.ts
npm run test -- frontend/utils/errorMessage.test.ts
npm run test -- frontend/utils/debounce.test.ts

# 全前端测试回归
npm run test

# 类型检查（无回归）
npx tsc --noEmit
```

## 建议新增测试点

按 architect 评审：

| 测试名 | case 数 | 覆盖目标 |
|---|---|---|
| `useThinkingBlock.test.ts` | 5 | 空 messages / idle 一次性 snap / 流式 chunk 推进 / 卸载 clearTimeout / 图片 thought placeholder |
| `useHoverPromptPreview.test.ts` | 4 | 泛型 P 接受两种 payload / scheduleClose 与 cancelScheduledClose 抵消 / startResize listener 清理 / 卸载安全 |
| `useAsyncState.test.ts` | 4 | success 路径 / failure 路径（error 来自 getErrorMessage） / 卸载中途 resolve 不 setState / 连续 execute 旧请求丢弃 |
| `useActionMenu.test.ts` | 3 | open/close 切换 / scroll 重定位 / 卸载 listener 注销 |
| `errorMessage.test.ts` | 5 | Error 实例 / string / null/undefined+fallback / 鸭子类型 {message} / 普通对象 |
| `debounce.test.ts` | 4 | 延迟触发 / 重复调用只触发末次 / cancel() / flush() |

## 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| `useThinkingBlock` 6 处迁移中漏掉某 view 特有边界（如 `ImageRecontextView` 依赖数组多 1 项） | M | M | plan 阶段逐处 read diff，迁移时保留特殊行为为 hook option；测试覆盖每个 view 的具体行为 |
| `getErrorMessage` 鸭子类型 `{message}` 在某些 axios 错误路径上多读了内部字段 | L | L | 测试 case 覆盖；如发现回归则 fallback 改 `String(err)` |
| `useHoverPromptPreview` 泛型 P 在 `VideoGenView` 10 字段被某处用错（运行时少字段） | M | M | TypeScript 严格类型 + run-time 不读 P 自身字段（仅传递） |
| 单 PR 内 ~46 处替换 diff 巨大，review 困难 | H | M | 按主题切 4 个 commit + PR description 含主题表格 |
| 测试覆盖某些 hook 时 `vi.useFakeTimers` 在 React 18 strict mode 行为差异 | M | L | 参考已有 `useSessionSync.test.tsx` 写法 |

## Open Questions（plan 批准前需决策）

| # | 问题 | 我的推荐答案 | 影响 |
|---|---|---|---|
| 1 | `useMobileHistory` 是改 `GenViewLayout` 内部状态还是新增 hook？ | **改 `GenViewLayout`**（拆 A-2，本工单不含） | 本工单规模 |
| 2 | `useAsyncState` 是 1 处试点 + A-2 还是一 PR 全替换 4 处？ | **1 处试点 + A-2**（本工单只迁 `OllamaModelManager`） | 本工单规模 |
| 3 | `getErrorMessage` 是否兼容 `{message: string}` 鸭子类型？ | **是**（覆盖 axios-like 错误） | 行为统一 |
| 4 | `useEscapeClose` 是否扩展 `additionalKeys` 参数？ | **不扩展**（保持单职责；多键场景保留 inline） | follow-up 是否独立 |
| 5 | 同 PR 还是分多 PR？ | **单 PR 4 step commit** | review 负担 vs 风险粒度 |

测试库 / FileReader 方法 / lodash 三项已通过实际 grep 解决（见"当前事实"章节），不再列入 Open Questions。

## 交接备注

1. **本工单已经按 plan 模式产出，不动一行代码** — 实施需经 user 批准 5 个 Open Questions 后进行
2. **改造组 A 与 hardening JIRA 是平行工作**，不互相阻塞 — hardening 已落地 16 commit 在分支 `refactor/gemini-pool-unification`；本工单实施时新开分支 `refactor/frontend-hook-utility-extraction-A`
3. **agent teams 三时点强制**：plan 完成（前置已做）/ 每个 Step commit 后（实施中）/ ship-readiness 复审（实施后），任一 NO-GO 不允许 push
4. **commit message 必引用本工单**：`refactor(frontend): ... (closes JIRA-frontend-hook-utility-extraction.md#StepN)`
5. **量化交付指标**（PR description 必须列）：消除复制代码总行数 / 改动文件数 / 测试新增数 / `tsc --noEmit` 0 error 截图 / `vitest` 通过数前后对比

## 数据来源 / 复审依据

- 重复识别原始报告：`docs/REPETITION-AND-PERF-ANALYSIS.md` §1（commit `9bcc8db`）
- 实施前 Explore 验证：14 条 file:line PASS / 0 失效 / 4 条漏网 finding
- 实施前 architect 五维评审：完整 TS 签名 / 测试约定 / 迁移策略 / 范围边界 / 7 个 Open Questions（其中 3 个已通过实际 grep 解决）
- 项目硬规则依据：`HANDOFF.md` §0 #1-#6（commit `4726750` + `a58e4bc`）
