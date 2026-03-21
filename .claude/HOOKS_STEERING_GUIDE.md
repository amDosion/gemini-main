# Steering 架构 Hooks 使用指南

## 📚 概述

本文档介绍已集成到 `.claude/hooks.json` 主配置文件中的 Steering 架构 Hooks，用于：

1. **强制执行模块化原则** - 自动检查文件大小和结构
2. **管理 Steering 文档** - 验证文档同步和完整性
3. **优化上下文使用** - 建议使用 context-gatherer
4. **自动化工作流** - 提供架构验证和重构工具

**重要提示**：所有 Steering 相关的 Hooks 已经集成到主配置文件 `.claude/hooks.json` 中，无需单独配置。

---

## 🎯 核心 Hooks

### 1. 文件大小检查

**Hook**: `check_file_size_limit`

**触发时机**: 写入文件前

**作用**: 检查文件是否超过模块化原则限制
- 后端 Python: < 300 行（理想）
- 前端 TypeScript: < 200 行（理想）

**示例输出**:
```
✅ 后端 Python 文件大小合适: 250 行 (理想 < 300 行)
⚠️  前端 TypeScript 文件偏大: 280 行 (理想 < 200 行)
   建议：考虑拆分为多个模块
❌ 后端 Python 文件过大: 550 行 (最大 < 500 行)
   必须：拆分为多个模块
   参考：.kiro/steering/structure.md 的模块化原则
```

---

### 2. 模块化结构验证

**Hook**: `validate_modular_structure`

**触发时机**: 写入文件前

**作用**: 验证文件是否遵循模块化目录结构

**检查项**:
- 后端主协调器是否导入子模块
- 前端协调组件是否导入子组件
- 目录结构是否符合规范

**示例输出**:
```
✅ 后端服务结构正确: 主协调器正确导入子模块
⚠️  主协调器 google_service.py 应该导入并组装子模块
   参考：.kiro/steering/structure.md 的模块化组织原则
```

---

### 3. 协调器模式检查

**Hook**: `check_coordinator_pattern`

**触发时机**: 写入主协调器文件前

**作用**: 检查主协调器是否正确组装子模块

**检查项**:
- 是否导入了功能模块
- 是否在 `__init__` 中实例化模块
- 是否提供协调方法

---

### 4. 模块拆分建议

**Hook**: `suggest_module_split`

**触发时机**: 写入文件后

**作用**: 分析文件复杂度，建议拆分方案

**示例输出**:
```
💡 文件复杂度分析:
   - 文件大小: 450 行
   - 函数数量: 15 个
   - 类数量: 3 个
   
   建议拆分方案:
   1. 提取 ChatHandler 类 → chat_handler.py
   2. 提取 ImageGenerator 类 → image_generator.py
   3. 提取 ModelManager 类 → model_manager.py
   4. 保留主协调器 → google_service.py
```

---

### 5. Steering 文档同步验证

**Hook**: `validate_steering_docs_sync`

**触发时机**: 提交前

**作用**: 验证场景文档和参考文档是否同步

**检查项**:
- 场景文档引用的参考文档是否存在
- 参考文档版本号是否一致
- 交叉引用是否正确

**示例输出**:
```
✅ Steering 文档同步检查通过
   - 6 个场景文档
   - 4 个参考文档
   - 所有交叉引用正确
```

---

### 6. 路由指南完整性检查

**Hook**: `check_routing_guide_completeness`

**触发时机**: 提交 KIRO-RULES.md 前

**作用**: 检查场景路由表是否包含所有场景

**检查项**:
- 场景路由表是否包含所有场景文档
- 场景识别规则是否完整
- 文档路径是否正确

---

### 7. Context-Gatherer 使用建议

**Hook**: `suggest_context_gatherer`

**触发时机**: 读取大型 Steering 文档时

**作用**: 建议使用 context-gatherer 避免上下文超载

**示例输出**:
```
💡 提示：此文档较大 (500 行)
   建议通过 context-gatherer 子 Agent 获取摘要，避免上下文超载

   使用方法：
   invokeSubAgent(
       name="context-gatherer",
       prompt="Read and summarize frontend-development.md",
       explanation="Getting document summary"
   )
```

---

### 8. Gemini 集成合规性检查

**Hook**: `check_gemini_integration_compliance`

**触发时机**: 提交 Gemini 相关代码前

**作用**: 检查是否遵循 Gemini 集成规范

**检查项**:
- 是否继承 BaseProviderService
- 是否实现必需方法
- 是否有完整的错误处理
- 是否参考了官方文档

---

## 🚀 自定义工作流

### 1. 验证 Steering 架构

**命令**: `/workflow validate_steering_architecture`

**执行步骤**:
1. 检查路由文件
2. 检查场景文档完整性
3. 检查参考文档完整性
4. 验证文档交叉引用
5. 生成验证报告

**使用场景**:
- 更新 Steering 文档后
- 添加新场景文档后
- 定期架构审查

---

### 2. 检查模块化合规性

**命令**: `/workflow check_modular_compliance`

**执行步骤**:
1. 扫描后端服务
2. 扫描前端组件
3. 分析文件大小
4. 检查协调器模式
5. 生成合规性报告

**使用场景**:
- 代码审查前
- 重构前评估
- 定期质量检查

**示例报告**:
```
📊 模块化架构合规性报告

后端服务:
  ✅ gemini/google_service.py (主协调器, 180 行)
  ✅ gemini/chat_handler.py (功能模块, 250 行)
  ✅ gemini/image_generator.py (功能模块, 280 行)
  ⚠️  openai/openai_service.py (单一文件, 450 行) - 建议拆分

前端组件:
  ✅ chat/ChatView.tsx (协调组件, 150 行)
  ✅ chat/MessageList.tsx (子组件, 120 行)
  ⚠️  views/ImageGenView.tsx (单一组件, 350 行) - 建议拆分

总体合规率: 85%
```

---

### 3. 重构为模块化结构

**命令**: `/workflow refactor_to_modular FILE_PATH=<path>`

**执行步骤**:
1. 分析文件结构
2. 生成拆分建议
3. 创建模块目录
4. 提取功能模块
5. 创建协调器
6. 更新导入引用
7. 运行测试验证

**使用场景**:
- 重构大文件
- 优化代码结构
- 提高可维护性

**示例**:
```bash
/workflow refactor_to_modular FILE_PATH=backend/app/services/google_service.py
```

**输出**:
```
🔧 重构分析: google_service.py (650 行)

建议拆分方案:
  1. chat_handler.py (200 行) - 聊天功能
  2. image_generator.py (180 行) - 图像生成
  3. model_manager.py (150 行) - 模型管理
  4. google_service.py (120 行) - 主协调器

创建目录结构:
  backend/app/services/gemini/
    ├── __init__.py
    ├── google_service.py (主协调器)
    ├── chat_handler.py
    ├── image_generator.py
    └── model_manager.py

✅ 重构完成！测试通过。
```

---

### 4. 添加场景文档

**命令**: `/workflow add_scenario_doc SCENARIO_NAME=<name>`

**执行步骤**:
1. 创建场景文档模板
2. 更新 KIRO-RULES.md 场景路由表
3. 更新 POWER.md
4. 验证文档结构

**使用场景**:
- 添加新的开发场景
- 扩展 Steering 规则

**示例**:
```bash
/workflow add_scenario_doc SCENARIO_NAME=testing
```

**输出**:
```
📝 创建场景文档: testing

生成文件:
  ✅ .kiro/powers/gemini-fullstack/steering/testing.md (模板)
  ✅ 更新 .kiro/steering/KIRO-RULES.md (添加路由)
  ✅ 更新 .kiro/powers/gemini-fullstack/POWER.md (添加索引)

下一步:
  1. 编辑 testing.md 填写场景规则
  2. 添加代码示例和检查清单
  3. 提交变更
```

---

### 5. 同步 Steering 文档

**命令**: `/workflow sync_steering_docs`

**执行步骤**:
1. 检查文档一致性
2. 更新交叉引用
3. 同步版本号
4. 更新 CHANGELOG
5. 生成同步报告

**使用场景**:
- 更新多个文档后
- 发布新版本前
- 定期维护

---

### 6. 分析上下文使用

**命令**: `/workflow analyze_context_usage`

**执行步骤**:
1. 统计 Steering 文档大小
2. 分析文档访问频率
3. 计算上下文使用量
4. 生成优化建议

**使用场景**:
- 优化 Steering 架构
- 评估上下文效率
- 规划文档拆分

**示例报告**:
```
📊 上下文使用分析报告

Steering 文档统计:
  - 总文档数: 19 个
  - 总行数: 5,560 行
  - 平均行数: 292 行/文档

自动加载文档:
  - KIRO-RULES.md: 300 行 (~3K tokens)

按需加载文档:
  - 场景文档: 3,000 行 (~30K tokens)
  - 参考文档: 2,000 行 (~20K tokens)

访问频率 (最近 30 天):
  1. frontend-development.md: 45 次
  2. backend-development.md: 38 次
  3. gemini-integration.md: 25 次

优化建议:
  ✅ 当前架构高效，上下文使用合理
  💡 考虑缓存高频访问的场景文档摘要
```

---

## 📋 使用场景

### 场景 1: 开发新功能

```
1. 开始开发
   └─ Hook: display_steering_version (显示架构版本)
   └─ Hook: remind_steering_principles (提醒核心原则)

2. 创建新文件
   └─ Hook: check_file_size_limit (检查文件大小)
   └─ Hook: validate_modular_structure (验证结构)

3. 写入代码
   └─ Hook: format_python_code / format_typescript_code (格式化)
   └─ Hook: suggest_module_split (建议拆分)

4. 提交代码
   └─ Hook: validate_modular_architecture (验证架构)
   └─ Hook: run_backend_tests / run_frontend_tests (运行测试)
```

---

### 场景 2: 更新 Steering 文档

```
1. 编辑文档
   └─ Hook: backup_steering_docs (自动备份)
   └─ Hook: validate_steering_format (验证格式)

2. 提交文档
   └─ Hook: validate_steering_docs_sync (验证同步)
   └─ Hook: check_routing_guide_completeness (检查完整性)

3. 提交后
   └─ Hook: update_steering_changelog (更新日志)
   └─ Hook: notify_steering_update (通知团队)
```

---

### 场景 3: 重构大文件

```
1. 分析文件
   └─ /workflow check_modular_compliance

2. 执行重构
   └─ /workflow refactor_to_modular FILE_PATH=<path>

3. 验证结果
   └─ Hook: validate_modular_architecture
   └─ Hook: run_tests
```

---

### 场景 4: 添加新场景

```
1. 创建场景文档
   └─ /workflow add_scenario_doc SCENARIO_NAME=<name>

2. 编写规则
   └─ 填写场景文档内容

3. 验证架构
   └─ /workflow validate_steering_architecture

4. 同步文档
   └─ /workflow sync_steering_docs
```

---

## 🔧 配置和启用

### 1. 安装依赖

```bash
# Python 依赖
cd backend
pip install -r requirements-dev.txt

# 确保脚本可执行（Linux/Mac）
chmod +x .claude/scripts/*.py
```

### 2. Hooks 已自动启用

**所有 Steering 相关的 Hooks 已经集成到 `.claude/hooks.json` 中**，无需额外配置。

当你使用 Kiro 时，这些 Hooks 会自动运行：
- ✅ 文件大小检查
- ✅ 模块化结构验证
- ✅ Steering 文档管理
- ✅ 上下文优化建议

### 3. 验证配置

```bash
# 检查配置文件
python -m json.tool .claude/hooks.json

# 查看 Steering 版本
grep "STEERING_VERSION" .claude/hooks.json
# 应该显示: "STEERING_VERSION": "2.0.0"

# 查看集成的 Steering Hooks
grep -A 2 "check_file_size_limit\|validate_modular_structure\|suggest_context_gatherer" .claude/hooks.json
```

### 4. 测试 Hooks

```bash
# 测试文件大小检查
python .claude/scripts/check_file_size.py backend/app/services/gemini/google_service.py

# 测试模块化结构验证
python .claude/scripts/validate_modular_structure.py backend/app/services/gemini/google_service.py

# 测试 context-gatherer 建议
python .claude/scripts/suggest_context_gatherer.py .kiro/docs/scenarios/frontend-development.md
```

---

## 📊 监控和报告

### 1. 查看日志

```bash
# Hooks 执行日志
cat .claude/logs/hooks.log

# Steering 文档访问日志
cat .claude/steering_access_log.txt

# 错误日志
cat .claude/error_log.txt
```

### 2. 生成报告

```bash
# 模块化合规性报告
/workflow check_modular_compliance

# Steering 架构验证报告
/workflow validate_steering_architecture

# 上下文使用分析报告
/workflow analyze_context_usage
```

---

## 🎯 最佳实践

### 1. 渐进式启用

**第 1 周**: 启用基础 Hooks
```json
{
  "check_file_size_limit": { "enabled": true },
  "suggest_context_gatherer": { "enabled": true },
  "display_steering_version": { "enabled": true }
}
```

**第 2 周**: 启用验证 Hooks
```json
{
  "validate_modular_structure": { "enabled": true },
  "validate_steering_docs_sync": { "enabled": true }
}
```

**第 3 周**: 启用完整保护
```json
{
  "validate_modular_architecture": { "enabled": true },
  "check_gemini_integration_compliance": { "enabled": true }
}
```

### 2. 定期维护

**每周**:
- 运行 `/workflow check_modular_compliance`
- 查看合规性报告
- 重构不合规的文件

**每月**:
- 运行 `/workflow validate_steering_architecture`
- 运行 `/workflow analyze_context_usage`
- 更新 Steering 文档

**每季度**:
- 审查所有 Steering 规则
- 优化文档结构
- 更新最佳实践

### 3. 团队协作

**配置已集成**:

所有 Steering Hooks 已经集成到 `.claude/hooks.json` 主配置文件中，团队成员只需：

```bash
# 拉取最新代码
git pull

# 确保 Python 依赖已安装
cd backend && pip install -r requirements-dev.txt

# Hooks 会自动生效
```

**文档化**:
- 在团队 Wiki 中说明 Hooks 用途
- 提供使用示例和故障排除指南
- 定期培训新成员

---

## 🆘 故障排除

### 问题 1: 脚本执行失败

**现象**:
```
Error: python: command not found
```

**解决方案**:
```bash
# 检查 Python 安装
python --version
python3 --version

# 更新脚本 shebang
# 将 #!/usr/bin/env python3 改为 #!/usr/bin/env python
```

---

### 问题 2: 文件路径问题

**现象**:
```
Error: cannot find file: D:\gemini-main\...
```

**解决方案**:
```python
# 在脚本中使用 os.path.normpath
import os
file_path = os.path.normpath(sys.argv[1])
```

---

### 问题 3: Hook 未触发

**检查清单**:
1. ✅ `enabled: true` 已设置
2. ✅ 文件匹配 `pattern` 规则
3. ✅ 脚本有执行权限
4. ✅ Python 依赖已安装

---

## 📚 相关资源

- [Steering 架构说明](.kiro/steering/KIRO-RULES.md)
- [Power 配置](.kiro/powers/gemini-fullstack/POWER.md)
- [场景文档目录](.kiro/powers/gemini-fullstack/steering/)
- [完整 Hooks 指南](.claude/HOOKS_GUIDE.md)

---

## 📝 更新日志

### v2.0.0 (2026-01-09)
- ✨ 初始发布
- 🎯 支持 Steering v2.0 架构
- 🔧 8 个核心 Hooks（已集成到主配置）
- 🚀 6 个自定义工作流
- 📊 完整的监控和报告功能
- ✅ 所有 Hooks 已集成到 `.claude/hooks.json`

---

**版本**: 2.0.0  
**更新日期**: 2026-01-09  
**维护者**: Development Team

