# Claude Code Configuration Index

> **Quick Start**: Read `CLAUDE_OPTIMIZED.md` first, then reference other files as needed.

## 📑 Configuration Files Overview

| File | Purpose | Size | Priority |
|------|---------|------|----------|
| **CLAUDE_OPTIMIZED.md** | Main steering document | 12.9 KB | 🔴 Critical |
| **agent-config.json** | Agent collaboration rules | 15.6 KB | 🟠 High |
| **cot-config.json** | Chain of Thought patterns | 12.8 KB | 🟡 Medium |
| **skills/gemini-fullstack.json** | Development skills | 10.9 KB | 🟢 Auto-triggered |
| **hooks/development.json** | Workflow automation | 9.2 KB | 🟢 Auto-triggered |
| **README_CONFIG.md** | Configuration guide | This doc | 📖 Reference |

---

## 🎯 When to Use Each File

### CLAUDE_OPTIMIZED.md (Always Start Here)
**Read this when**:
- Starting any new development task
- Need to identify which scenario to follow
- Unsure about tool usage rules
- Need execution flow overview
- Looking for troubleshooting guidance

**Key Sections**:
- Quick Routing Table (keyword → scenario mapping)
- Tool Usage Strategy (Main Agent vs Subagents)
- Fixed Execution Flow (3-phase workflow)
- Core Principles (指哪打哪 + 不爆 token + 完整流程)

---

### agent-config.json (Detailed Reference)
**Read this when**:
- Need detailed subagent invocation patterns
- Implementing complex workflows
- Debugging subagent issues
- Understanding parallel execution strategy
- Need performance metrics/token savings data

**Key Sections**:
- Main Agent roles and prohibited actions
- Subagent definitions (context-gatherer, general-purpose)
- Execution flow phases with examples
- Session management (SESSION_ID usage)
- Error handling strategies

---

### cot-config.json (Complex Analysis)
**Read this when**:
- Designing multi-step analysis workflows
- Need to use Sequential Thinking MCP
- Implementing iterative refinement loops
- Deciding between parallel vs sequential execution
- Creating new workflow patterns

**Key Sections**:
- 4 CoT patterns (Sequential, Parallel, Validation, Incremental)
- MCP tool integration (Codex, Gemini, Sequential Thinking, Claude Code)
- Workflow examples (New Feature, Bug Fix, Refactoring, Optimization)
- Decision trees for pattern selection

---

### skills/gemini-fullstack.json (Auto-Triggered)
**Automatically activated when**:
- User request contains trigger keywords
- Need standard workflow templates
- Implementing common development tasks

**Available Skills** (10 total):
1. analyze-requirements
2. implement-backend
3. implement-frontend
4. integrate-gemini
5. refactor-module
6. setup-storage
7. add-authentication
8. debug-issue
9. optimize-performance
10. write-tests

---

### hooks/development.json (Auto-Triggered)
**Automatically activated on**:
- File save events (validation hooks)
- Before commit events (test/check hooks)
- Agent stop events (quality gate hooks)

**Hook Categories** (15 hooks total):
- Validation: 5 hooks
- Testing: 2 hooks
- Security: 1 hook
- Quality: 2 hooks
- Documentation: 1 hook
- Other: 4 hooks

---

## 🔄 Typical Usage Flow

### Scenario 1: New Backend Feature
```
1. User: "Implement authentication API"
   ↓
2. Claude reads: CLAUDE_OPTIMIZED.md (keyword: "backend", "api")
   ↓
3. Auto-trigger: skills/gemini-fullstack.json → "implement-backend"
   ↓
4. Reference: agent-config.json (for subagent patterns)
   ↓
5. Execute: Use context-gatherer + general-purpose subagents
   ↓
6. Reference: cot-config.json (for validation pattern)
   ↓
7. Auto-trigger: hooks/development.json (validation + tests)
   ↓
8. Complete: Files written, tests pass, quality validated
```

### Scenario 2: Complex Refactoring
```
1. User: "Refactor google_service.py to modular architecture"
   ↓
2. Claude reads: CLAUDE_OPTIMIZED.md (keyword: "refactor")
   ↓
3. Auto-trigger: skills/gemini-fullstack.json → "refactor-module"
   ↓
4. Reference: cot-config.json (sequential analysis + incremental refinement)
   ↓
5. Reference: agent-config.json (parallel execution strategy)
   ↓
6. Execute: Deep analysis → Module generation → Integration
   ↓
7. Auto-trigger: hooks/development.json (structure validation)
   ↓
8. Complete: Modular structure, all validations pass
```

### Scenario 3: Debugging Issue
```
1. User: "Debug slow performance in image generation"
   ↓
2. Claude reads: CLAUDE_OPTIMIZED.md (keyword: "debug", "performance")
   ↓
3. Auto-trigger: skills/gemini-fullstack.json → "debug-issue"
   ↓
4. Reference: cot-config.json (sequential analysis pattern)
   ↓
5. Reference: agent-config.json (Sequential Thinking MCP usage)
   ↓
6. Execute: 5-step analysis → Identify bottleneck → Generate fix
   ↓
7. Auto-trigger: hooks/development.json (performance validation)
   ↓
8. Complete: Performance improved, documented
```

---

## 🎓 Learning Path

### For First-Time Users
1. Read `CLAUDE_OPTIMIZED.md` sections:
   - Claude's Role
   - Core Principles
   - Quick Routing Table
   - Tool Usage Strategy

2. Skim `skills/gemini-fullstack.json`:
   - See what skills are available
   - Note trigger keywords

3. Review `hooks/development.json`:
   - Understand automatic validations
   - Know what gates exist

### For Advanced Users
1. Study `agent-config.json`:
   - Master subagent patterns
   - Understand parallel execution
   - Learn SESSION_ID usage

2. Deep dive `cot-config.json`:
   - Implement custom workflows
   - Design complex analysis patterns
   - Optimize for your use cases

---

## 🔍 Quick Reference Tables

### File Read Operations
| What to Read | Use Which Subagent | Config Reference |
|--------------|-------------------|------------------|
| Project docs (Spec) | context-gatherer | agent-config.json |
| Existing code | context-gatherer | agent-config.json |
| External docs (FastAPI) | Main Agent + Context7 MCP | CLAUDE_OPTIMIZED.md |

### Code Generation Operations
| What to Generate | Use Which Tool | Config Reference |
|-----------------|----------------|------------------|
| Backend code | general-purpose + Codex | agent-config.json |
| Frontend code | general-purpose + Gemini | agent-config.json |
| Tests | general-purpose + Codex/Gemini | skills/*.json |

### Analysis Operations
| What to Analyze | Use Which Tool | Config Reference |
|-----------------|----------------|------------------|
| Security | general-purpose + Sequential Thinking | cot-config.json |
| Performance | general-purpose + Sequential Thinking | cot-config.json |
| Code quality | general-purpose + Claude Code | agent-config.json |
| Architecture | general-purpose + Sequential Thinking | cot-config.json |

### File Write Operations
| What to Write | Use Which Tool | Config Reference |
|--------------|----------------|------------------|
| New files | general-purpose + fsWrite | agent-config.json |
| Edit files | general-purpose + strReplace | agent-config.json |
| Append files | general-purpose + fsAppend | agent-config.json |

---

## 🛠️ Customization Guide

### Adding New Scenario
1. Create scenario doc in `.kiro/powers/gemini-fullstack/steering/`
2. Add entry to `CLAUDE_OPTIMIZED.md` Quick Routing Table
3. Update keyword triggers if needed

### Adding New Skill
1. Edit `skills/gemini-fullstack.json`
2. Add skill definition with trigger keywords
3. Define workflow steps
4. Specify expected outputs

### Adding New Hook
1. Edit `hooks/development.json`
2. Add hook with trigger event
3. Define file pattern and validation logic
4. Set blocking/timeout parameters

### Modifying CoT Pattern
1. Edit `cot-config.json`
2. Add new pattern to `patterns` section
3. Define use cases and steps
4. Add workflow examples

---

## 📈 Performance Optimization

### Token Savings
| Operation | Without Config | With Config | Savings |
|-----------|---------------|-------------|---------|
| Read docs | 20K tokens | 0 tokens | 100% |
| Generate code | 30K tokens | 3K tokens | 90% |
| Analyze code | 25K tokens | 2K tokens | 92% |
| Write files | 15K tokens | 1K tokens | 93% |

### Execution Speed
| Phase | Sequential | Parallel | Speedup |
|-------|-----------|----------|---------|
| Context gathering | 3 tasks | 3x parallel | 3x |
| Execution | 4 tasks | 4x parallel | 4x |
| Overall | 100% | ~14% | 7x |

---

## ✅ Configuration Health Check

Run this checklist periodically:

### Main Steering Document
- [ ] CLAUDE_OPTIMIZED.md is up-to-date
- [ ] Quick Routing Table covers all scenarios
- [ ] Tool Usage Strategy is clear
- [ ] Execution Flow is documented

### Agent Configuration
- [ ] agent-config.json has all subagent patterns
- [ ] Execution flows are optimized for parallel
- [ ] Error handling is comprehensive
- [ ] Performance metrics are accurate

### CoT Configuration
- [ ] cot-config.json has relevant patterns
- [ ] MCP integration is documented
- [ ] Workflow examples are up-to-date
- [ ] Decision trees are clear

### Skills Configuration
- [ ] skills/gemini-fullstack.json covers common tasks
- [ ] Trigger keywords are comprehensive
- [ ] Workflows are detailed
- [ ] Expected outputs are clear

### Hooks Configuration
- [ ] hooks/development.json validates key files
- [ ] Test hooks prevent bad commits
- [ ] Quality gates are enforced
- [ ] Hook performance is acceptable

---

## 🔗 Related Resources

### Project Documentation
- `.kiro/steering/KIRO-RULES.md` - Simplified routing rules
- `.kiro/docs/core/agents-collaboration.md` - Detailed agent collaboration
- `.kiro/docs/collaboration/mcp-usage-guide.md` - MCP tool usage
- `.kiro/docs/architecture/project-structure.md` - Codebase structure

### External Documentation
- FastAPI docs (via Context7 MCP)
- React docs (via Context7 MCP)
- Gemini SDK docs (via Context7 MCP)

---

## 🆘 Support

### Common Issues
1. **Skills not triggering**: Check trigger keywords match user request
2. **Hooks not running**: Verify file patterns and enabled flags
3. **Token explosion**: Ensure using subagents (not direct reads)
4. **Slow execution**: Check for sequential operations that could be parallel

### Getting Help
1. Check `CLAUDE_OPTIMIZED.md` Troubleshooting section
2. Review `agent-config.json` error handling
3. Examine hook logs in `hooks/development.json`
4. Consult detailed docs in `.kiro/docs/`

---

## 📊 Metrics Dashboard

Track these metrics to ensure configurations are working:

### Token Efficiency
- Main Agent context size: Target < 10K tokens
- Subagent usage rate: Target 100% for reads/MCP calls
- Cache hit rate: Target > 50%

### Execution Performance
- Average task completion time
- Parallel execution rate: Target > 70%
- Iteration count per task: Target < 3

### Quality Metrics
- Validation pass rate: Target > 90%
- Test pass rate: Target 100%
- Hook compliance rate: Target 100%

---

**Version**: 1.0.0
**Created**: 2026-01-13
**Last Updated**: 2026-01-13
**Maintained By**: Kiro AI Development Team

---

**Next Steps**: Start with `CLAUDE_OPTIMIZED.md` and work through a simple task to familiarize yourself with the configuration system.
