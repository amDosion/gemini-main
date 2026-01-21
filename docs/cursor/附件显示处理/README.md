# GEN模式跳转Edit/Expand模式附件显示处理文档

## 📋 文档概述

本目录包含关于 GEN 模式跳转到 Edit/Expand 模式时附件显示问题的完整文档，包括需求、设计和任务文档。

---

## 📚 文档结构

### 1. requirements.md - 需求文档

**内容**：
- 问题背景和用户期望
- 功能需求和非功能需求
- 用户故事
- 验收标准

**用途**：明确问题定义和需求，为设计和实施提供依据

---

### 2. design.md - 设计文档

**内容**：
- 当前实现分析
- 设计方案和优化策略
- 详细设计说明
- 实施计划

**用途**：提供技术设计方案，指导代码实现

---

### 3. tasks.md - 任务文档

**内容**：
- 任务列表和优先级
- 任务依赖关系
- 实施步骤
- 测试计划
- 验收标准

**用途**：提供具体的实施计划和任务分解

---

### 4. IMAGE_GEN_TO_EDIT_EXPAND_FLOW.md - 流程文档

**内容**：
- 完整流程图（ASCII 和 Mermaid）
- 详细步骤说明
- 代码验证结果
- 已知问题和优化建议

**用途**：提供完整的流程说明和代码验证结果

---

## 🔗 文档关系

```
requirements.md (需求)
    ↓
design.md (设计)
    ↓
tasks.md (任务)
    ↓
IMAGE_GEN_TO_EDIT_EXPAND_FLOW.md (流程参考)
```

---

## 🎯 核心问题

**问题描述**：
GEN 模式生成图片后，用户立即点击 Edit/Expand 按钮时，附件的显示可能存在以下问题：

1. **异步查询延迟**：如果图片刚生成，`uploadStatus === 'pending'`，会触发异步查询后端获取云 URL，导致显示延迟
2. **Base64 URL 被不必要查询**：Base64 URL 已经完整可用，但仍会触发 `tryFetchCloudUrl` 查询后端
3. **HTTP 临时 URL 过期风险**：如果上传未完成，可能使用已过期的 HTTP 临时 URL，导致图片无法显示

**解决方案**：
- 优化 `tryFetchCloudUrl`：Base64 URL 和 Blob URL 直接使用，不查询后端
- 优化 `useImageHandlers`：优先使用传入的 URL，查询在后台进行，不阻塞初始显示
- 添加降级策略：如果 HTTP URL 不可用，尝试使用 Base64 URL

---

## 📝 使用指南

### 对于开发者

1. **开始实施前**：
   - 阅读 `requirements.md` 了解需求
   - 阅读 `design.md` 了解设计方案
   - 阅读 `tasks.md` 了解具体任务

2. **实施过程中**：
   - 参考 `tasks.md` 中的任务列表
   - 参考 `design.md` 中的详细设计
   - 参考 `IMAGE_GEN_TO_EDIT_EXPAND_FLOW.md` 了解完整流程

3. **测试验证**：
   - 参考 `tasks.md` 中的测试计划
   - 参考 `requirements.md` 中的验收标准

### 对于产品/测试

1. **了解需求**：阅读 `requirements.md`
2. **了解设计**：阅读 `design.md`
3. **测试验证**：参考 `tasks.md` 中的测试计划

---

## 🔄 更新日志

- **2024-01-18**：创建文档目录和所有文档

---

## 📖 相关文档

- `../附件文档/` - 其他附件相关文档
- `../../IMAGE_MODE_SWITCH_FLOW_ANALYSIS.md` - 模式切换流程分析
- `../../TEMP_IMAGES_AUTHENTICATION_FIX_PLAN.md` - 临时图片认证方案
