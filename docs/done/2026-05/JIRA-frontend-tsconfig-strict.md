# JIRA: 前端 tsconfig 启用 `strict` 模式

## 类型
Tech Debt / Type Safety / Quality Gate

## 状态
**Done — 实施完成（分支 `refactor/frontend-hook-utility-extraction-A` HEAD `d3e8f8c`）**

按 `HANDOFF.md` §0 #5 plan 模式 + §0 #6 agent teams（build-error-resolver + typescript-reviewer + code-reviewer）完成。

### 实施 commit 索引

| Step | Commit | 内容 |
|---|---|---|
| 1+2+3 | `45a1d63` | tsconfig 添加 `"strict": true` + react-syntax-highlighter.d.ts 模块声明（消除 14 TS7016）+ build-error-resolver agent 修 50 错误（25 文件）+ 4 测试文件 4 错误 |
| 4 fix | `d3e8f8c` | code-reviewer 反馈修复 HIGH×2（App.tsx 行为回归 + useWorkflowExecutionController as cast 改用合理 explicit assertion） |

### 实施事实

- **错误规模**：dry-run 检测 68 错误（远低于 plan 估算"几十~数百"）
- **react-syntax-highlighter 类型缺失** 占 14 处 — 单 declaration file 解决
- **剩余 54 错误**：
  - TS2322 (21) 类型不匹配 — 通过类型对齐 / null guard / 类型扩宽解决
  - TS2345 (6) 参数类型 — 修签名 + 类型守卫
  - TS18048 (6) Object possibly undefined — 可选链 / 守卫
  - TS2783 (4) 重复 spread prop — ModeControlsCoordinator 顺序调整
  - TS2538 / TS2531 / TS2367 / TS2349 / TS2722 / TS2719 / TS2339 / TS18047 (其余 17)
- **0 个 `as any` / `@ts-ignore` / `@ts-expect-error` 引入**（仅 1 处合理 explicit type assertion 解决 TS strict 已知 limitation）
- **测试文件 4 错误**：用 object container pattern (`{current}`) 规避 TS strict 闭包内可变 `let` 的 narrowing 失效

### 最终量化指标

- 85 测试套件 334/334 全绿
- `tsc --noEmit` 0 错误（strict 模式开启）
- `prettier --check` 全过
- 影响 35 文件（含新增 1 declaration file）
- 8 个 strict 子项全开（strict/strictNullChecks/noImplicitAny/strictFunctionTypes/strictBindCallApply/strictPropertyInitialization/alwaysStrict/noImplicitThis/useUnknownInCatchVariables）

### Reviewer 修复 finding 累计

- HIGH×2（App.tsx 行为回归 + cast 合理性）
- MEDIUM×4 + LOW×3（type declaration index signature 宽松 / nullable widening trade-off / timestamp sentinel 等可接受）

### 历史 finding（已记录）

## 来源
- `JIRA-frontend-hook-utility-extraction.md` Step 1 中检 finding #1（HIGH）
- typescript-reviewer 原话："`tsconfig.json` (root) `"strict"` is absent. Without it `strictNullChecks`, `noImplicitAny`, and `strictFunctionTypes` are all off, meaning every type assertion and narrowing in the two utilities is un-enforced by the compiler. This undermines the entire type-safety premise of the refactor."

## 当前事实
`/mnt/user/appdata/gemini-main/tsconfig.json` 缺 `"strict": true` 顶层选项。
具体未启的 sub-flag（按 TS 默认）：
- `strictNullChecks` — 允许 `null/undefined` 隐式分配给任何类型
- `noImplicitAny` — 隐式 any 不报错
- `strictFunctionTypes` — 函数参数双变行为不严格
- `strictBindCallApply` — `bind/call/apply` 不强类型检查
- `strictPropertyInitialization` — 类属性未初始化不报错
- `alwaysStrict` — 不强制 `"use strict"`
- `noImplicitThis` — `this` 隐式 any 不报错
- `useUnknownInCatchVariables` — `catch (e)` 默认 `any` 而非 `unknown`

## 影响面
- `frontend/` 下约 200+ TS/TSX 文件，启用 strict 后预计产生几十~数百条类型错误
- 现有类型守卫与断言（如本工单刚加的 `getErrorMessage`）的类型安全保证**当前未被编译器强制**
- 改造组 A/B/C 的所有"类型驱动重构"收益建立在 strict=true 假设之上

## 问题陈述
项目对外提供 SDK 集成、AI 流式输出、多 provider 切换等复杂逻辑，**类型安全是 P0 防线**。当前 strict=false 状态下：
- `unknown` narrowing 不强制 → 类型守卫可被绕过
- `null/undefined` 漏检 → runtime `Cannot read property 'x' of undefined` 类故障
- 隐式 any 漂移 → 大重构（如改造组 A）的安全网失效

## 修复范围
1. 在 `tsconfig.json` `compilerOptions` 添加 `"strict": true`
2. 跑 `npx tsc --noEmit` 收集全部错误
3. 按文件分组修复（**不允许补丁式 `as any` / `// @ts-ignore`** — 按 HANDOFF §0 #1）
4. 修复过程中如发现 runtime bug（类型错误暴露的真实逻辑漏洞），独立 commit 记录
5. 更新 `eslint` 配置以同步严格度

## 非目标
- 不引入 `strict-boolean-expressions` / `strict-template-expressions` 等 ESLint plugin 级规则（独立工单）
- 不动 `backend/` Python 类型系统

## 验收标准
- [ ] `tsconfig.json` 含 `"strict": true`
- [ ] `npx tsc --noEmit` 0 error
- [ ] 0 处新增 `as any` / `// @ts-ignore` / `// @ts-expect-error`（必须解决根因）
- [ ] CI `Run frontend tests` step 含 `npx tsc --noEmit` 作为独立 gate
- [ ] 现有 frontend vitest 测试全部通过（无回归）

## 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 类型错误数量超预期，需分阶段开多 PR | H | M | 第一 PR 启 strict + 修头部 50 错误，剩余按目录分批；用 `// @ts-expect-error` 临时标记（必须有 ticket 链接 + 7 天 SLA） |
| strictNullChecks 暴露真实 runtime bug | M | H | 这本就是引入 strict 的核心价值；每个 runtime bug 独立 commit 记录在 `docs/strict-bugs-uncovered.md` |
| 重构期间业务功能阻塞 | M | M | 分支独立，PR 单独 review；不与改造组 A/B/C 合并到同一 PR |

## 交接备注
1. **本工单不阻塞改造组 A** — Hook/utility 抽离工单（`JIRA-frontend-hook-utility-extraction.md`）继续推进，本工单作为并行 follow-up
2. **agent teams 三时点**：实施前用 `Explore` 收集 tsc 错误清单；实施中每 50 个错误修复后用 `typescript-reviewer` spot-check；实施后 `code-reviewer` + `typescript-reviewer` 复审
3. **commit 引用**：`refactor(frontend): ... (closes JIRA-frontend-tsconfig-strict.md#StepN)`
