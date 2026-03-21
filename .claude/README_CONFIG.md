# Claude Code Configuration Files

This directory contains optimized configuration files for the Kiro AI Full-Stack Development Assistant using Claude Code.

## 📁 File Structure

```
.claude/
├── CLAUDE_OPTIMIZED.md          # Main steering document (optimized)
├── agent-config.json             # Agent collaboration configuration
├── cot-config.json               # Chain of Thought configuration
├── skills/
│   └── gemini-fullstack.json    # Development skills definition
└── hooks/
    └── development.json          # Development workflow hooks
```

## 📄 File Descriptions

### 1. CLAUDE_OPTIMIZED.md
**Purpose**: Main steering document for Claude Code assistant

**Key Contents**:
- Claude's role definition as Kiro AI Development Assistant
- Core principles: 指哪打哪 + 不爆 token + 完整流程
- Quick routing table for scenario identification
- Tool usage strategy with subagents
- Fixed execution flow (context → execute → validate)
- Chain of Thought patterns integration
- Troubleshooting guide

**When to Use**: This is the primary document Claude Code will reference. It provides high-level guidance and quick reference for all development tasks.

---

### 2. agent-config.json
**Purpose**: Detailed agent collaboration rules and workflows

**Key Contents**:
- Main Agent responsibilities and prohibited actions
- Subagent definitions:
  - `context-gatherer`: Read-only context gathering
  - `general-purpose`: Code generation, analysis, file operations
- Execution flow phases:
  - Phase 1: Parallel context gathering
  - Phase 2: Parallel execution
  - Phase 3: File operations
- Iteration loop (Generate-Analyze-Validate-Fix)
- Session management with SESSION_ID
- Performance metrics and token savings data

**When to Use**: Reference when needing detailed information about:
- How to call subagents
- Execution workflow patterns
- Token optimization strategies
- Error handling procedures

---

### 3. cot-config.json
**Purpose**: Chain of Thought (CoT) configuration and patterns

**Key Contents**:
- CoT patterns:
  - Sequential Analysis (5-step structured thinking)
  - Parallel Decision (simultaneous task execution)
  - Validation Pattern (generate → validate → fix loop)
  - Incremental Refinement (iterative development)
- MCP tool integration:
  - Sequential Thinking MCP usage
  - Codex MCP for backend generation
  - Gemini MCP for frontend generation
  - Claude Code MCP for reviews
- Workflow examples for common tasks
- Decision trees for when to use each pattern
- Performance guidelines

**When to Use**: Reference when:
- Designing complex analysis workflows
- Deciding between sequential vs parallel execution
- Implementing iterative refinement loops
- Integrating MCP tools

---

### 4. skills/gemini-fullstack.json
**Purpose**: Pre-defined skills for common development tasks

**Key Contents**:
- 10 development skills:
  1. `analyze-requirements`: Create spec documents
  2. `implement-backend`: Backend service implementation
  3. `implement-frontend`: Frontend component implementation
  4. `integrate-gemini`: Gemini model/feature integration
  5. `refactor-module`: Modular architecture refactoring
  6. `setup-storage`: Cloud storage integration
  7. `add-authentication`: Auth feature implementation
  8. `debug-issue`: Issue debugging and fixing
  9. `optimize-performance`: Performance optimization
  10. `write-tests`: Test suite generation
- Each skill includes:
  - Trigger keywords
  - Step-by-step workflow
  - Scenario document reference
  - Expected outputs

**When to Use**:
- Automatically triggered by keyword matching
- Reference for standard workflows
- Template for creating new skills

---

### 5. hooks/development.json
**Purpose**: Development workflow automation hooks

**Key Contents**:
- 15 development hooks across 5 categories:
  - **Validation** (5 hooks): File validators for backend, frontend, services, hooks, API contracts
  - **Testing** (2 hooks): Backend tests, frontend type check
  - **Security** (1 hook): Dependency security check
  - **Quality** (2 hooks): Code quality gate, performance check
  - **Documentation** (1 hook): Spec documentation sync
- Hook configurations:
  - Trigger events (onFileSave, beforeCommit, onAgentStop)
  - File patterns
  - Actions (agentPrompt, shellCommand)
  - Blocking/non-blocking settings
  - Timeout configurations

**When to Use**:
- Automatically triggered based on events
- Ensures code quality standards
- Prevents commits with failing tests
- Validates architecture compliance

---

## 🚀 Quick Start

### For Claude Code
1. Read `CLAUDE_OPTIMIZED.md` first - it's your primary steering document
2. Reference `agent-config.json` for detailed subagent usage
3. Use `cot-config.json` for complex analysis patterns
4. Skills in `skills/gemini-fullstack.json` are auto-triggered by keywords
5. Hooks in `hooks/development.json` run automatically based on events

### For Developers
1. Review `CLAUDE_OPTIMIZED.md` to understand Claude's capabilities
2. Check `skills/gemini-fullstack.json` to see available automated workflows
3. Review `hooks/development.json` to understand validation gates
4. Customize hooks as needed for your workflow

---

## 🔧 Configuration Usage Examples

### Example 1: Implementing a New Backend Feature

**User Request**: "Implement backend API for user authentication"

**Claude's Workflow**:
1. Keyword match → Triggers `implement-backend` skill
2. Read `backend-development.md` via context-gatherer
3. Explore existing auth code via context-gatherer
4. Generate code via general-purpose + Codex
5. Analyze security via general-purpose + Sequential Thinking
6. Review quality via general-purpose + Claude Code
7. Write files via general-purpose + Kiro native tools
8. Hooks auto-validate on save and before commit

---

### Example 2: Refactoring Large Service

**User Request**: "Refactor google_service.py into modular architecture"

**Claude's Workflow**:
1. Keyword match → Triggers `refactor-module` skill
2. Read refactoring.md via context-gatherer
3. Analyze boundaries via general-purpose + Sequential Thinking
4. Generate modules via general-purpose + Codex
5. Update tests
6. Review via general-purpose + Claude Code
7. Write files
8. Hooks validate module structure

---

### Example 3: Debugging Performance Issue

**User Request**: "Debug slow image generation performance"

**Claude's Workflow**:
1. Keyword match → Triggers `debug-issue` skill
2. Read relevant code via context-gatherer
3. Deep analysis via general-purpose + Sequential Thinking (5-step)
4. Identify bottlenecks
5. Generate optimizations via general-purpose + Codex/Gemini
6. Review via general-purpose + Claude Code
7. Apply fixes
8. Hooks validate performance improvements

---

## 📊 Performance Benefits

### Token Optimization
- **Context gathering**: 100% savings (Main Agent: 0 tokens)
- **Code generation**: 90% savings (30K → 3K summary)
- **Deep analysis**: 92% savings (25K → 2K summary)
- **File operations**: 93% savings (15K → 1K result)

### Execution Speed
- **Phase 1** (context gathering): 3x faster via parallel subagents
- **Phase 2** (execution): 4x faster via parallel subagents
- **Overall**: ~7x faster than sequential execution

### Quality Assurance
- **Dual validation**: Sequential Thinking + Claude Code in parallel
- **Iterative refinement**: Generate → Analyze → Fix loop
- **Automated gates**: 15 validation hooks ensure standards

---

## 🔄 Updating Configurations

### Adding New Skills
Edit `skills/gemini-fullstack.json`:
```json
{
  "name": "new-skill-name",
  "description": "Description",
  "trigger": "keyword1|keyword2",
  "workflow": ["step1", "step2"],
  "scenarioDoc": "scenario.md",
  "expectedOutput": ["output1", "output2"]
}
```

### Adding New Hooks
Edit `hooks/development.json`:
```json
{
  "name": "new_hook",
  "enabled": true,
  "trigger": "onFileSave",
  "filePattern": "path/**/*.ext",
  "action": "agentPrompt",
  "instructions": "Validation instructions",
  "blocking": false,
  "timeout": 60000
}
```

### Modifying CoT Patterns
Edit `cot-config.json` to add new thinking patterns or workflow examples.

---

## 🆘 Troubleshooting

### Issue: Hooks not triggering
**Solution**: Check `enabled: true` and file pattern matches target files

### Issue: Skills not auto-triggering
**Solution**: Verify trigger keywords match user request

### Issue: Subagent calls failing
**Solution**: Check `agent-config.json` for correct invocation patterns

### Issue: Token explosion
**Solution**: Verify using subagents (not direct file reads or MCP calls)

---

## 📚 Related Documentation

- **Project Rules**: `.kiro/steering/KIRO-RULES.md` (simplified routing)
- **Agent Collaboration**: `.kiro/docs/core/agents-collaboration.md` (detailed reference)
- **MCP Usage**: `.kiro/docs/collaboration/mcp-usage-guide.md` (MCP tool guide)
- **Project Structure**: `.kiro/docs/architecture/project-structure.md` (codebase layout)

---

## 🔖 Version Information

- **Version**: 1.0.0
- **Created**: 2026-01-13
- **Last Updated**: 2026-01-13
- **Maintainer**: Kiro AI Development Team

---

## ✅ Configuration Checklist

When using these configurations, Claude Code ensures:

- [ ] All file reads use context-gatherer subagent
- [ ] All MCP tool calls use general-purpose subagent
- [ ] All file writes use general-purpose + Kiro native tools
- [ ] Parallel execution maximized for independent tasks
- [ ] Code follows modular architecture (Backend <300, Frontend <200 lines)
- [ ] Security best practices applied (JWT, encryption, validation)
- [ ] Tests generated alongside code
- [ ] Documentation synchronized with implementation
- [ ] All validations pass before committing
- [ ] Quality gates satisfied before completion

---

**Note**: These configurations work together to provide a comprehensive development assistant experience. Start with `CLAUDE_OPTIMIZED.md` as the entry point and reference other files as needed.
