# Kiro 完整配置方案分析与改进建议

## 总体评估

### ✅ 优点
1. **职责清晰** - router/DocLens/subagent contracts 分离明确
2. **上下文保护** - 硬性限制输出长度，强制写入文件
3. **DocLens 理念正确** - Locate→Slice→Compress→Spill 是好模式
4. **分层合理** - always/manual/powers/hooks 各司其职

### ❌ 核心问题

#### 问题 1：00-router-always.md 仍然过重
````yaml
---
inclusion: always  # 每次对话都加载
---
# 当前约 400-500 words
````

**影响：**
- 占用 10-15% 的 always-included 预算
- 包含大量"如何做"而非"是什么"
- 大部分内容应该在 manual 或 agent config

#### 问题 2：Powers 设计有误解
````markdown
# 4) .kiro/powers/docread/POWER.md
Purpose: On-demand document/code reading...
````

**问题：**
- Powers 不是用来"定义流程"的
- Powers 是用来"注入工具+知识"的
- 你的 DocLens 逻辑应该在 steering/agent，不是 Power

#### 问题 3：混淆了 Powers 和 Steering
- `docread` Power 里写的是"流程规则"
- 应该是 MCP 工具 + 使用指南，而非执行流程

#### 问题 4：Hooks 配置不完整
- 只有配置，没有告诉 Kiro 如何触发
- 缺少与 router 的联动

---

## 改进方案（完整架构）

### 架构层次
````
Layer 1: Always Included (极简核心) - <150 words
Layer 2: Conditional (按文件类型) - 按需
Layer 3: Manual (详细手册) - 显式调用
Layer 4: Powers (工具注入) - 关键词触发
Layer 5: Hooks (自动化) - 事件驱动
Layer 6: Custom Agent (可选) - 专用路由器
````

---

## 完整文件结构（推荐）
````
.kiro/
├── steering/
│   ├── 00-core.md                    # Always: <150 words
│   ├── 01-context-limits.md          # Always: <100 words  
│   ├── workflows/
│   │   ├── subagent-playbook.md      # Manual: 详细指南
│   │   ├── doclens-guide.md          # Manual: DocLens 完整流程
│   │   └── evidence-format.md        # Manual: 输出规范
│   └── domain/
│       ├── frontend.md               # Conditional: **/*.tsx
│       └── backend.md                # Conditional: **/api/**/*.ts
│
├── powers/
│   ├── github-power/
│   │   ├── POWER.md                  # 工具说明 + 最佳实践
│   │   └── mcp.json                  # MCP 配置
│   └── codebase-search/
│       ├── POWER.md
│       └── mcp.json
│
├── hooks/
│   ├── file-hooks.json
│   ├── contextual-hooks.json
│   └── manual-hooks.json
│
└── agents/
    └── orchestrator.yaml             # 可选：专用路由 agent
````

---

## 文件内容（完整版）

### 1. .kiro/steering/00-core.md (Always, 极简)
````yaml
---
inclusion: always
---

# Core Directives (<150 words)

## Output Limits (Hard)
- Main chat: ≤10 bullets
- Large data: write to `.kiro/notes/` or `.kiro/reports/`
- Evidence: `path:Lx-Ly` or object ID

## Routing (Default)
- Heavy work → subagents
  - Discovery: context-gathering
  - Parallel: general-purpose
- External systems → Powers (inside subagents)
- Automation → Hooks (main agent only)

## Playbooks (Manual)
- Subagent details: `#subagent-playbook`
- DocLens reading: `#doclens-guide`
- Output format: `#evidence-format`

## Tech Stack
- Frontend: React 18 + TS + Tailwind
- Backend: Node + Express + PostgreSQL
- State: Zustand | Query: TanStack

Total: 120 words
````

---

### 2. .kiro/steering/01-context-limits.md (Always, 规则)
````yaml
---
inclusion: always
---

# Context Protection Rules (<100 words)

## Input Limits
- Never request full files (use ranges)
- MCP returns: ≤5 snippets, each ≤80 lines
- Codebase search: max 10 results

## Output Limits
- Chat response: ≤10 bullets
- Code snippets: ≤40 lines/each, max 2
- Logs/lists: ≤20 lines or spill to file

## Spill Locations
- Research notes: `.kiro/notes/<topic>-YYYYMMDD.md`
- Analysis reports: `.kiro/reports/<type>-YYYYMMDD.md`
- Session logs: `.kiro/logs/session-YYYYMMDD.log`

Total: 90 words
````

---

### 3. .kiro/steering/workflows/subagent-playbook.md (Manual)
````yaml
---
inclusion: manual
---

# Subagent Playbook (Complete Guide)
Trigger: `#subagent-playbook`

## When to Use Subagents

### Mandatory Cases
- Task requires ≥3 files
- Output expected >300 lines
- Codebase-wide analysis
- Long document reading (>500 lines)
- ≥3 external tool calls
- Parallel processing needed

### context-gathering Subagent

**Purpose:** Discover facts, never decide

**Use For:**
- "Find where X is used"
- "What modules depend on Y?"
- "Read and extract from long spec"
- "Scan codebase for pattern Z"
- "Fetch external data for understanding"

**Output Contract:**
```markdown
## Findings (≤10 bullets)
- Fact 1
- Fact 2

## Evidence (≤5 refs)
- src/api/auth.ts:45-67
- docs/design.md:L120-L145

## Artifacts
- `.kiro/notes/discovery-YYYYMMDD.md` (detailed findings)
```

**Prohibited:**
- ❌ Solution proposals
- ❌ Implementation code
- ❌ Value judgments
- ❌ "I think/suggest/recommend"

---

### general-purpose Subagent

**Purpose:** Execute parallel work on known scope

**Use For:**
- "Process these 10 tickets"
- "Compare 3 implementation approaches"
- "Generate variants of X"
- "Implement feature Y (bounded scope)"
- "Batch transform files"

**Output Contract:**
```markdown
## Results (≤10 bullets, grouped)
### Item 1
- Result A
- Result B

### Item 2
- Result C

## Tradeoffs (if applicable, ≤5)
- Option A: pros/cons
- Option B: pros/cons

## Artifacts
- `.kiro/reports/analysis-YYYYMMDD.md`
```

**Prohibited:**
- ❌ Raw data dumps
- ❌ Full file contents in response
- ❌ Long unstructured output

---

## Execution Patterns

### Pattern 1: Sequential Discovery → Execution
````
User: "Implement feature X"
  ↓
Main: context-gathering("find related code")
  ↓
context-gathering returns: files A, B, C with evidence
  ↓
Main: Analyze scope, create plan
  ↓
Main: general-purpose("implement subtask 1")
Main: general-purpose("implement subtask 2")
  ↓
Main: Synthesize results
````

### Pattern 2: Parallel Processing
````
User: "Analyze these 8 PRs for security issues"
  ↓
Main: Spawn 8 general-purpose subagents (parallel)
  ↓
Each subagent: Analyze 1 PR → return summary
  ↓
Main: Aggregate findings
````

### Pattern 3: Deep Dive with DocLens
````
User: "Understand the auth flow from our ADR"
  ↓
Main: context-gathering + DocLens Power
  ↓
Subagent:
  - Locate: list_headings(docs/adr/auth.md)
  - Slice: read_section("Authentication Flow")
  - Compress: extract key decisions
  - Spill: write full notes to `.kiro/notes/`
  ↓
Subagent returns: summary + evidence refs
  ↓
Main: Answer user with synthesized info
````

### Pattern 4: MCP-Heavy Task
````
User: "Get all open P0 bugs from Jira"
  ↓
Main: general-purpose + GitHub Power (inside subagent)
  ↓
Subagent:
  - MCP: search_issues(priority=P0, status=open)
  - MCP returns: 50 results
  - Filter: extract key fields (ID, title, assignee)
  - Spill: write full list to `.kiro/reports/p0-bugs.json`
  ↓
Subagent returns: "Found 50 P0 bugs, see report + top 5 summary"
  ↓
Main: Present summary + file path
````

---

## Cost Considerations

**Subagent Overhead:**
- Each subagent = separate context window
- Parallel subagents = multiple API calls
- Trade-off: Speed & isolation vs. cost

**When NOT to Use Subagents:**
- Simple queries (answerable in <50 words)
- Single file edits
- Quick clarifications
- Tasks with <3 tool calls

**Optimization Tips:**
1. Batch similar tasks into one subagent
2. Reuse context-gathering results
3. Limit parallel subagents to 5-10 max
4. For >10 items, consider batching

---

## Debugging Subagents

**If subagent returns too much:**
- Check output contract enforcement
- Verify spill-to-file logic
- Review subagent's steering access

**If subagent context overflows:**
- Reduce input scope
- Split into smaller subtasks
- Use more aggressive filtering

**If results are poor:**
- Provide clearer task boundaries
- Add domain-specific steering (conditional)
- Consider custom agent configuration
````

---

### 4. .kiro/steering/workflows/doclens-guide.md (Manual)
````yaml
---
inclusion: manual
---

# DocLens Reading Protocol
Trigger: `#doclens-guide`

## Philosophy
Never load entire documents into context. Always: locate → slice → compress → spill.

## 4-Step Pipeline (Mandatory)

### Step 1: Locate (No Full Read)
**Goal:** Find relevant sections without reading content

**Tools:**
- `list_headings(path)` - get table of contents
- `search_in_file(path, query)` - find keywords
- `list_files(glob, max=20)` - locate candidates

**Output:** List of target locations (≤10)

---

### Step 2: Slice (Precise Extraction)
**Goal:** Read only necessary parts

**Tools:**
- `read_section(path, heading)` - one section
- `read_range(path, start, end)` - line range
- `get_surrounding(path, line, context=20)` - around key line

**Rules:**
- Max 5 slices per operation
- Each slice ≤80 lines
- If need more, split into multiple subagent tasks

---

### Step 3: Compress (Extract Essence)
**Goal:** Distill to actionable information

**Process:**
1. Identify key facts/decisions/patterns
2. Create evidence references (`path:Lx-Ly`)
3. Summarize in ≤10 bullets
4. Discard boilerplate/examples/verbose explanations

**Example:**
```markdown
## Key Findings
- Auth uses JWT (exp: 15min)
- Refresh token: 7 days
- MFA required for admin

## Evidence
- docs/auth.md:L45-L67
- src/auth/jwt.ts:L12-L30
```

---

### Step 4: Spill (Archive Details)
**Goal:** Preserve full context without polluting main chat

**Process:**
```python
# Write detailed notes
notes_path = f".kiro/notes/{topic}-{YYYYMMDD}.md"
content = f"""
# {topic} - Full Research Notes

## Source Documents
- {doc1}
- {doc2}

## Detailed Findings
{full_extracted_content}

## Raw Excerpts
{relevant_snippets}
"""
write_file(notes_path, content)
```

**In Chat:** Only mention path + summary

---

## Common Patterns

### Pattern: Read ADR/RFC
````
1. list_headings(docs/adr/003-auth.md)
   → ["Context", "Decision", "Consequences"]
2. read_section(docs/adr/003-auth.md, "Decision")
   → Extract decision rationale (≤60 lines)
3. Compress to 5 bullets
4. Spill full section to .kiro/notes/adr-003-analysis.md
5. Return: summary + evidence ref
````

### Pattern: Understand Complex Module
````
1. search_in_repo("class PaymentProcessor")
   → src/payments/processor.ts:L45
2. read_range(src/payments/processor.ts, 45, 120)
   → Get class definition + key methods
3. Find dependencies:
   search_in_repo("import.*PaymentProcessor")
   → 5 files found
4. Compress architecture
5. Spill full analysis to .kiro/notes/payments-arch.md
````

### Pattern: Read Long Spec
````
1. list_headings(specs/api-v2.md)
   → 20 sections found
2. User needs: authentication + rate limiting
3. read_section "Authentication" + "Rate Limiting"
4. Extract requirements (≤80 lines total)
5. Compress to checklist
6. Spill full spec analysis to .kiro/notes/api-v2-review.md
````

---

## Anti-Patterns (Prohibited)

❌ **Full File Dump**
````
# BAD
read_file(docs/manual.md)  # 5000 lines
# paste entire content in chat
````

✅ **Correct**
````
# GOOD
list_headings(docs/manual.md)
read_section(docs/manual.md, "Chapter 3")
# compress to ≤10 bullets + spill to file
````

---

❌ **Iterative Full Read**
````
# BAD
read_range(file, 1, 100)
read_range(file, 101, 200)
read_range(file, 201, 300)
# continue until EOF
````

✅ **Correct**
````
# GOOD
search_in_file(file, "authentication")
read_range(file, 145, 190)  # targeted slice
# done
````

---

❌ **No Compression**
````
# BAD
read_section → paste 200 lines in chat
````

✅ **Correct**
````
# GOOD
read_section → extract 5 key points
→ spill 200 lines to .kiro/notes/
→ return summary + path