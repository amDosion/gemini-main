# Kiro Hooks 集成指南

**版本**：v1.0.0  
**更新日期**：2026-01-09  
**参考**：[Kiro 官方 Hooks 文档](https://kiro.dev/docs/hooks/)

---

## 概述

Kiro Hooks 是强大的自动化工具，通过在 IDE 中特定事件发生时自动执行预定义的 Agent 操作来简化开发工作流程。本指南说明如何在我们的项目中有效利用 Hooks。

**核心优势**：
- 消除手动请求常规任务的需要
- 确保代码库的一致性
- 实时响应编码活动
- 自动化测试、文档和代码标准

---

## Hook 类型

根据 [Kiro 官方文档](https://kiro.dev/docs/hooks/types/)，Hooks 支持以下触发类型：

### 1. On Prompt Submit（提示提交时）

**触发时机**：用户提交提示时

**使用场景**：
- 为 Agent 提供与提示相关的额外上下文
- 基于内容阻止某些提示
- 将所有用户提示记录到中心位置

**环境变量**：
- `USER_PROMPT`：可访问用户提示内容（Shell 命令操作）

**项目应用示例**：
```json
{
  "name": "Context Injection",
  "description": "在提示提交前注入项目上下文",
  "trigger": "onPromptSubmit",
  "action": "agentPrompt",
  "instructions": "Before processing the user's request, review the current Steering rules and MCP collaboration guidelines to ensure the response follows our architecture."
}
```

### 2. On Agent Stop（Agent 停止时）

**触发时机**：Agent 完成其回合并完成对用户的响应时

**使用场景**：
- 编译代码并向 Agent 报告任何失败
- 格式化 Agent 生成的代码
- 审查 Agent 所做的更改并提供额外指示

**项目应用示例**：
```json
{
  "name": "Code Quality Check",
  "description": "Agent 完成后自动检查代码质量",
  "trigger": "onAgentStop",
  "action": "agentPrompt",
  "instructions": "Review the changes made in this session. Run getDiagnostics on modified files and report any issues."
}
```

### 3. On File Create（文件创建时）

**触发时机**：工作区中创建匹配特定模式的新文件时

**使用场景**：
- 为新组件生成样板代码
- 向新文件添加许可证头
- 创建实现文件时设置测试文件

**项目应用示例**：
```json
{
  "name": "Auto Test File",
  "description": "创建新组件时自动生成测试文件",
  "trigger": "onFileCreate",
  "filePattern": "frontend/components/**/*.tsx",
  "action": "agentPrompt",
  "instructions": "A new component was created. Generate a corresponding test file with basic test cases."
}
```

### 4. On File Save（文件保存时）

**触发时机**：保存匹配特定模式的文件时

**使用场景**：
- 运行测试并报告失败
- 更新相关文档
- 验证代码符合项目标准
- 同步翻译文件

**项目应用示例**：
```json
{
  "name": "Update Tests",
  "description": "保存代码文件时更新并运行测试",
  "trigger": "onFileSave",
  "filePattern": "backend/app/**/*.py",
  "action": "agentPrompt",
  "instructions": "The file was modified. Update the corresponding test file and run the tests. Report any failures."
}
```

### 5. Manual Trigger（手动触发）

**触发时机**：用户通过斜杠命令手动调用

**使用场景**：
- 按需运行复杂的工作流程
- 执行一次性任务
- 提供自定义命令

**项目应用示例**：
```json
{
  "name": "Validate Architecture",
  "description": "验证项目架构合规性",
  "trigger": "manual",
  "action": "agentPrompt",
  "instructions": "Validate the project architecture against our modular design principles. Check file sizes, module organization, and separation of concerns."
}
```

---

## Hook 操作

根据 [Kiro 官方文档](https://kiro.dev/docs/hooks/actions/)，Hooks 支持两种操作类型：

### 1. Agent Prompt（Agent 提示）

**说明**：向 Agent 发送指令，Agent 在当前上下文中执行

**何时使用**：
- 需要 Agent 理解和推理
- 需要访问代码库上下文
- 需要生成或修改代码
- 需要复杂的决策逻辑

**示例**：
```json
{
  "action": "agentPrompt",
  "instructions": "Review the modified file for potential security issues. Check for SQL injection, XSS vulnerabilities, and exposed secrets."
}
```

### 2. Shell Command（Shell 命令）

**说明**：执行 Shell 命令，输出可选地发送给 Agent

**何时使用**：
- 运行测试或构建命令
- 执行代码格式化工具
- 运行 linters 或静态分析
- 执行文件系统操作

**环境变量**：
- `USER_PROMPT`：用户提示内容（On Prompt Submit）
- `FILE_PATH`：触发文件的路径（On File Save/Create）

**示例**：
```json
{
  "action": "shellCommand",
  "command": "pytest tests/test_${FILE_PATH}",
  "sendOutputToAgent": true
}
```

---

## 项目中的 Hooks 应用

### 1. Steering 架构验证

**场景**：确保代码符合模块化架构原则

**Hook 配置**：
```json
{
  "name": "Validate Modular Architecture",
  "description": "验证文件是否符合模块化原则",
  "trigger": "onFileSave",
  "filePattern": "{backend/app/**/*.py,frontend/components/**/*.tsx}",
  "action": "shellCommand",
  "command": "python .claude/scripts/validate_modular_structure.py ${FILE_PATH}",
  "sendOutputToAgent": true
}
```

**何时触发**：保存 Python 或 TypeScript 组件文件时

**作用**：
- 检查文件大小（后端 < 300 行，前端 < 200 行）
- 验证模块化目录结构
- 报告违规并建议拆分

### 2. MCP 协作规则检查

**场景**：确保遵循 MCP 协作架构

**Hook 配置**：
```json
{
  "name": "MCP Collaboration Check",
  "description": "检查是否正确使用 Context7 和 Subagents",
  "trigger": "onPromptSubmit",
  "action": "agentPrompt",
  "instructions": "Before processing this request, verify:\n1. Are we using Context7 MCP for document reading?\n2. Are we using context-gatherer for code exploration?\n3. Are we using general-purpose subagent for code generation?\n4. Are we avoiding direct Codex/Gemini calls from main agent?"
}
```

**何时触发**：用户提交任何提示时

**作用**：
- 提醒 Agent 遵循 v2.0.6 架构
- 防止上下文污染
- 确保并行执行策略

### 3. 文档同步

**场景**：代码更改时自动更新文档

**Hook 配置**：
```json
{
  "name": "Sync Documentation",
  "description": "代码更改时更新相关文档",
  "trigger": "onFileSave",
  "filePattern": "backend/app/routers/**/*.py",
  "action": "agentPrompt",
  "instructions": "The API router was modified. Check if the API documentation needs to be updated. Update the OpenAPI spec and README if necessary."
}
```

**何时触发**：保存 API 路由文件时

**作用**：
- 保持 API 文档最新
- 更新 OpenAPI 规范
- 同步 README 示例

### 4. 测试自动化

**场景**：代码更改时自动运行测试

**Hook 配置**：
```json
{
  "name": "Auto Run Tests",
  "description": "保存文件时自动运行相关测试",
  "trigger": "onFileSave",
  "filePattern": "backend/app/**/*.py",
  "action": "shellCommand",
  "command": "pytest tests/unit/test_$(basename ${FILE_PATH}) -v",
  "sendOutputToAgent": true
}
```

**何时触发**：保存 Python 文件时

**作用**：
- 立即发现回归问题
- 提供测试结果反馈
- 建议修复失败的测试

### 5. 代码审查

**场景**：Agent 完成后自动审查代码

**Hook 配置**：
```json
{
  "name": "Post-Agent Code Review",
  "description": "Agent 完成后审查生成的代码",
  "trigger": "onAgentStop",
  "action": "agentPrompt",
  "instructions": "Review all code changes made in this session:\n1. Check for security vulnerabilities\n2. Verify error handling\n3. Ensure proper logging\n4. Validate against design patterns\n5. Run getDiagnostics on modified files"
}
```

**何时触发**：Agent 完成响应时

**作用**：
- 自动质量检查
- 发现潜在问题
- 确保代码标准

### 6. Spec 文档验证

**场景**：创建或修改 Spec 文档时验证格式

**Hook 配置**：
```json
{
  "name": "Validate Spec Format",
  "description": "验证 Spec 文档格式",
  "trigger": "onFileSave",
  "filePattern": ".kiro/specs/**/requirements.md",
  "action": "agentPrompt",
  "instructions": "Validate the requirements document:\n1. Check EARS pattern compliance\n2. Verify INCOSE quality rules\n3. Ensure all terms are defined in Glossary\n4. Check for vague terms or escape clauses"
}
```

**何时触发**：保存 requirements.md 时

**作用**：
- 确保需求质量
- 验证 EARS 模式
- 检查 INCOSE 规则

---

## Hook 管理

根据 [Kiro 官方文档](https://kiro.dev/docs/hooks/management/)：

### 访问 Hooks

通过 Kiro 面板中的 **Agent Hooks** 部分访问所有 Hooks。

### 启用/禁用 Hooks

**快速切换**：
- 点击 Agent Hooks 面板中任何 Hook 旁边的眼睛图标

**从 Hook 视图**：
- 选择 Hook 并使用右上角的 "Hook Enabled" 开关

### 编辑现有 Hooks

Hooks 随工作流程演变。随时更新：
- 触发器
- 文件模式
- 指令
- 描述

更新立即生效。

### 删除 Hooks

选择 Hook 并使用删除选项。

---

## 最佳实践

根据 [Kiro 官方文档](https://kiro.dev/docs/hooks/best-practices/)：

### 1. 明确的指令

**好的示例**：
```json
{
  "instructions": "Review the modified file for:\n1. SQL injection vulnerabilities\n2. XSS attack vectors\n3. Exposed API keys or secrets\n4. Insecure authentication\nReport any findings with severity level."
}
```

**不好的示例**：
```json
{
  "instructions": "Check for security issues."
}
```

### 2. 精确的文件模式

**好的示例**：
```json
{
  "filePattern": "backend/app/routers/**/*.py"
}
```

**不好的示例**：
```json
{
  "filePattern": "**/*.py"  // 太宽泛
}
```

### 3. 适当的触发器选择

| 场景 | 推荐触发器 |
|------|-----------|
| 代码质量检查 | On File Save |
| 测试运行 | On File Save |
| 文档更新 | On File Save |
| 上下文注入 | On Prompt Submit |
| 代码审查 | On Agent Stop |
| 样板生成 | On File Create |
| 复杂工作流 | Manual |

### 4. 性能考虑

**避免**：
- 在每次文件保存时运行昂贵的操作
- 过于宽泛的文件模式
- 阻塞操作

**推荐**：
- 使用特定的文件模式
- 异步操作
- 快速验证检查

### 5. 错误处理

**Shell 命令**：
```bash
# 好的示例：处理错误
pytest tests/ || echo "Tests failed, but continuing..."

# 不好的示例：忽略错误
pytest tests/
```

**Agent 提示**：
```json
{
  "instructions": "Try to run the tests. If they fail, report the failures but don't stop the workflow."
}
```

---

## 故障排除

根据 [Kiro 官方文档](https://kiro.dev/docs/hooks/troubleshooting/)：

### 问题 1：Hook 未触发

**可能原因**：
- Hook 已禁用
- 文件模式不匹配
- 触发器配置错误

**解决方案**：
1. 检查 Hook 是否启用（眼睛图标）
2. 验证文件模式是否匹配触发文件
3. 检查触发器类型是否正确

### 问题 2：Shell 命令失败

**可能原因**：
- 命令不存在
- 权限问题
- 环境变量未设置

**解决方案**：
1. 在终端中手动测试命令
2. 检查文件权限
3. 验证环境变量

### 问题 3：Agent 提示无响应

**可能原因**：
- 指令不清晰
- 上下文不足
- Agent 超时

**解决方案**：
1. 使指令更具体
2. 提供更多上下文
3. 简化任务

### 问题 4：性能问题

**可能原因**：
- Hook 运行时间过长
- 文件模式过于宽泛
- 阻塞操作

**解决方案**：
1. 优化 Hook 逻辑
2. 缩小文件模式范围
3. 使用异步操作

---

## 项目 Hooks 清单

### 当前已实现的 Hooks

根据 `.claude/hooks.json`，我们已实现以下 Hooks：

#### 1. Steering 架构相关（14 个）

| Hook 名称 | 触发器 | 用途 |
|----------|--------|------|
| Check File Size | On File Save | 检查文件大小合规性 |
| Validate Modular Structure | On File Save | 验证模块化结构 |
| Suggest Context-Gatherer | On Prompt Submit | 建议使用 context-gatherer |
| Module Split Suggestion | Manual | 分析并建议模块拆分 |
| Validate Steering Architecture | Manual | 验证完整 Steering 架构 |
| Check Modular Compliance | Manual | 检查模块化合规性 |
| Refactor to Modular | Manual | 重构为模块化结构 |
| Add Scenario Doc | Manual | 添加场景文档 |
| Sync Steering Docs | Manual | 同步 Steering 文档 |
| Analyze Context Usage | Manual | 分析上下文使用 |
| Track Steering Access | On File Save | 跟踪文档访问 |
| Validate Scenario Doc | On File Save | 验证场景文档 |
| Check Reference Sync | Manual | 检查参考文档同步 |
| Generate Steering Report | Manual | 生成 Steering 报告 |

#### 2. 建议新增的 Hooks

基于 MCP 协作 v2.0.6 架构：

| Hook 名称 | 触发器 | 用途 | 优先级 |
|----------|--------|------|--------|
| MCP Architecture Check | On Prompt Submit | 检查是否遵循 v2.0.6 架构 | 高 |
| Context7 Usage Reminder | On Prompt Submit | 提醒使用 Context7 读取文档 | 高 |
| Subagent Usage Validation | On Agent Stop | 验证是否正确使用 subagents | 高 |
| Parallel Execution Check | On Agent Stop | 检查是否利用并行执行 | 中 |
| Context Usage Monitor | On Agent Stop | 监控上下文使用情况 | 中 |
| Spec Format Validator | On File Save | 验证 Spec 文档格式 | 中 |
| API Doc Sync | On File Save | 同步 API 文档 | 中 |
| Test Auto Run | On File Save | 自动运行测试 | 低 |

---

## 实施建议

### 阶段 1：核心 Hooks（立即实施）

1. **MCP Architecture Check**
   - 确保所有开发遵循 v2.0.6 架构
   - 防止上下文污染

2. **Context7 Usage Reminder**
   - 提醒使用 Context7 读取文档
   - 避免直接读取大文件

3. **Subagent Usage Validation**
   - 验证正确使用 subagents
   - 确保并行执行

### 阶段 2：质量 Hooks（1-2 周内）

4. **Spec Format Validator**
   - 确保 Spec 文档质量
   - 验证 EARS 和 INCOSE 规则

5. **API Doc Sync**
   - 保持文档最新
   - 减少手动维护

### 阶段 3：自动化 Hooks（1 个月内）

6. **Test Auto Run**
   - 自动化测试流程
   - 快速发现问题

7. **Context Usage Monitor**
   - 持续优化性能
   - 跟踪上下文使用

---

## 参考资源

### Kiro 官方文档

- **Hooks 概述**：https://kiro.dev/docs/hooks/
- **Hook 类型**：https://kiro.dev/docs/hooks/types/
- **Hook 操作**：https://kiro.dev/docs/hooks/actions/
- **Hook 示例**：https://kiro.dev/docs/hooks/examples/
- **Hook 管理**：https://kiro.dev/docs/hooks/management/
- **最佳实践**：https://kiro.dev/docs/hooks/best-practices/
- **故障排除**：https://kiro.dev/docs/hooks/troubleshooting/

### 项目文档

- **Hooks 配置**：`.claude/hooks.json`
- **Hooks 指南**：`.claude/HOOKS_GUIDE.md`
- **Hooks 速查表**：`.claude/HOOKS_CHEATSHEET.md`
- **Steering Hooks 指南**：`.claude/HOOKS_STEERING_GUIDE.md`

### 博客文章

- **自动化开发工作流**：https://kiro.dev/blog/automate-your-development-workflow-with-agent-hooks/
- **README 文件管理**：https://kiro.dev/blog/how-i-stopped-worrying-about-readme-files/

---

## 总结

Kiro Hooks 是强大的自动化工具，可以显著提升开发效率。通过正确使用 Hooks：

1. **自动化常规任务**：测试、文档、代码审查
2. **确保架构合规**：验证模块化、MCP 协作规则
3. **提高代码质量**：自动检查、格式化、验证
4. **加速开发流程**：减少手动操作，专注于编码

**关键要点**：
- 选择合适的触发器类型
- 编写清晰的指令
- 使用精确的文件模式
- 考虑性能影响
- 持续优化和改进

---

**版本**：v1.0.0  
**更新日期**：2026-01-09  
**维护者**：Development Team  
**下次审查**：2026-02-09

