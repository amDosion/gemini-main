# File Search 上传和 Deep Research 测试指南

## 测试目标

验证文档上传到 Google File Search Store 并使用 Deep Research Agent 分析的完整流程。

---

## 前置条件

1. ✅ 后端已启动 (http://localhost:8000)
2. ✅ 前端已启动 (http://localhost:5173)
3. ✅ 已设置环境变量 `GEMINI_API_KEY`
4. ✅ Google API Key 有 File Search 和 Deep Research 权限

---

## 测试步骤

### 方法 1: 使用前端 UI 测试 (推荐)

#### 步骤 1: 准备测试文档

创建一个包含有意义内容的测试文档,例如 `project-overview.md`:

```markdown
# Gemini Chat Application - Project Overview

## Project Description
This is a multi-modal AI chat application built with React and FastAPI, powered by Google Gemini AI.

## Key Features
1. Text chat with Gemini models
2. Image generation using Imagen
3. Image editing and expansion
4. Deep Research analysis
5. Virtual Try-On

## Technology Stack
- **Frontend**: React 18, TypeScript, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, Redis
- **AI Services**: Google Gemini API, Imagen API
- **Storage**: Lsky Image Hosting, Aliyun OSS

## Architecture Highlights
- Async upload with Redis queue
- Real-time SSE streaming
- IndexedDB caching
- Multi-provider storage support
```

#### 步骤 2: 前端上传测试

1. 打开浏览器访问 `http://localhost:5173`
2. 选择 **Deep Research** 模式
3. 点击 **附件上传按钮** (📎)
4. 选择你创建的 `project-overview.md` 文件
5. 观察控制台日志:
   - 应该看到 `[DeepResearchHandler] 📤 正在上传文档...`
   - 应该看到上传成功的日志

#### 步骤 3: 发起 Deep Research

在附件上传成功后:

1. 在输入框输入提示词:
   ```
   请基于上传的文档,深度研究这个项目的技术架构和特点
   ```
2. 点击发送
3. 观察:
   - SSE 连接建立
   - 思考过程显示
   - 最终研究报告生成

---

### 方法 2: 使用 API 直接测试

#### 步骤 1: 上传文件到 File Search Store

使用提供的测试脚本:

```bash
python test_file_search.py
```

**预期输出**:
```
[OK] Test file created: test_document.md
[UPLOAD] Uploading to Google File Search Store...
[SUCCESS] Upload completed!
  Store Name: fileSearchStores/deep-research-documents
  File Name: test_document.md
  Status: active
[INFO] Use this store_name for Deep Research:
  fileSearchStores/deep-research-documents
[CLEAN] Test file deleted: test_document.md
```

#### 步骤 2: 使用 store_name 创建 Deep Research 任务

使用 curl 或 Postman 发送请求:

```bash
curl -X POST http://localhost:8000/api/research/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "prompt": "Analyze the project architecture described in the uploaded document",
    "agent": "deep-research-pro-preview-12-2025",
    "file_search_store_names": ["fileSearchStores/deep-research-documents"],
    "agent_config": {
      "type": "deep-research",
      "thinking_summaries": "auto"
    }
  }'
```

#### 步骤 3: 验证 SSE 流式响应

**预期响应**:
- SSE 连接建立成功
- 收到 `interaction.start` 事件
- 收到多个 `content.delta` 事件
- 最终收到 `interaction.completed` 事件

---

## 常见问题排查

### 问题 1: 上传失败 500 错误

**症状**: `/api/file-search/upload` 返回 500

**可能原因**:
- API Key 无效或权限不足
- 网络连接问题
- 文件格式不支持

**解决方案**:
1. 检查后端日志查看具体错误
2. 验证 API Key 权限
3. 尝试上传纯文本文件 (.txt, .md)

### 问题 2: Deep Research 显示 "Missing Document Context"

**症状**: Agent 返回找不到文档内容

**可能原因**:
- `file_search_store_names` 参数未正确传递
- Store name 格式错误
- 文件还在处理中

**解决方案**:
1. 确认前端 DeepResearchHandler 正确传递了 `file_search_store_names`
2. 检查后端 research_stream.py 是否构建了正确的 tools 参数
3. 等待 30 秒后重试(文件可能还在索引中)

### 问题 3: SSE 连接中断

**症状**: 研究进行到一半断开连接

**解决方案**:
- 检查自动重连机制是否工作
- 查看后端日志确认是否是 Google API 主动断开
- 验证 `agent_config.thinking_summaries: "auto"` 是否已设置

---

## 验证清单

- [ ] 文件成功上传到 File Search Store
- [ ] 获得有效的 `file_search_store_name`
- [ ] Deep Research 能访问文档内容
- [ ] 思考过程正确显示在前端
- [ ] 最终研究报告完整生成
- [ ] SSE 自动重连机制正常工作
- [ ] 临时文件被正确清理

---

## 成功标准

### 文件上传成功标准

```json
{
  "file_search_store_name": "fileSearchStores/deep-research-documents",
  "file_name": "your-file.md",
  "status": "active",
  "operation": "operations/xxx"
}
```

### Deep Research 成功标准

1. **思考过程**: 在 `<thinking>` 标签中显示研究步骤
2. **引用文档**: 研究报告明确引用了上传的文档内容
3. **完整报告**: 生成详细的分析和结论
4. **无错误**: 整个过程没有抛出异常

---

## 下一步行动

测试成功后,可以进行以下优化:

1. **批量上传**: 支持一次上传多个文档
2. **文件管理**: 添加已上传文件的列表和管理功能
3. **Store 复用**: 同一 Store 可以包含多个文档
4. **格式支持**: 测试 PDF、DOCX、XLSX 等格式
5. **错误处理**: 完善上传失败的重试机制

---

**最后更新**: 2025-12-27
**测试负责人**: Claude Code
