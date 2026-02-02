# 前端代码修改清单

生成日期：2026-01-31
基于：CASE_CONVERSION_CODE_SCAN_REPORT.md
目标：统一前端使用 camelCase，配合中间件自动转换

---

## 修改原则

**前端规范：**
- ✅ JSON body：统一使用 camelCase（中间件会自动转换为 snake_case）
- ✅ Query 参数：统一使用 camelCase（中间件会自动转换为 snake_case）
- ✅ 响应处理：接收 camelCase（中间件自动从 snake_case 转换）

**不需要修改：**
- 前端已经使用 camelCase 的代码
- 中间件会自动处理转换

---

## 需要修改的文件

### 📁 frontend/services/storage/storageUpload.ts

**问题**：Query 参数使用 snake_case

**修改**：
```typescript
// ❌ 当前
const params = {
  storage_id: storageId,
  session_id: sessionId,
  message_id: messageId,
  attachment_id: attachmentId
}

// ✅ 修改为
const params = {
  storageId: storageId,  // 或简写：storageId
  sessionId: sessionId,
  messageId: messageId,
  attachmentId: attachmentId
}
```

**涉及位置**：
- `upload()` 函数的 Query 参数
- `upload-async` 端点的 Query 参数

**风险**：中（影响文件上传）

---

### 📁 frontend/services/workflowTemplateService.ts

**问题1**：Query 参数使用 snake_case
**问题2**：Query 参数使用 camelCase，但字段名不统一

**修改**：
```typescript
// ❌ 当前
const params = {
  workflow_type: type,  // snake_case
  include_public: true  // snake_case
}

// 或
const params = {
  isPublic: true  // camelCase，但后端期望 is_public（中间件会转换）
}

// ✅ 修改为
const params = {
  workflowType: type,    // 统一 camelCase
  includePublic: true    // 统一 camelCase
}
```

**涉及位置**：
- `/api/workflows` GET 请求
- `/api/workflows/adk-samples/import-all` POST 请求

**风险**：低

---

### 📁 frontend/hooks/useDeepResearchStream.ts

**问题**：Query 参数使用 snake_case

**修改**：
```typescript
// ❌ 当前
const params = { last_event_id: eventId }

// ✅ 修改为
const params = { lastEventId: eventId }
```

**涉及位置**：
- SSE 连接参数

**风险**：中（影响深度研究流式输出）

---

### 📁 frontend/hooks/handlers/DeepResearchHandler.ts

**问题**：Query 参数使用 snake_case

**修改**：
```typescript
// ❌ 当前
const params = { last_event_id: lastEventId }

// ✅ 修改为
const params = { lastEventId: lastEventId }
```

**风险**：中

---

### 📁 frontend/services/db.ts

**问题**：Query 参数使用 snake_case

**修改**：
```typescript
// ❌ 当前
const params = { edit_mode: true }

// ✅ 修改为
const params = { editMode: true }
```

**风险**：低

---

### 📁 frontend/components/modals/settings/VertexAIConfiguration.tsx

**问题**：Query 参数使用 snake_case

**修改**：
```typescript
// ❌ 当前
const params = { edit_mode: true }

// ✅ 修改为
const params = { editMode: true }
```

**风险**：低

---

### 📁 frontend/services/llmService.ts

**问题1**：Query 参数字段名不一致
**问题2**：响应处理仍兼容 snake_case

**修改1 - Query 参数**：
```typescript
// ❌ 当前
const params = { useCache: true }  // 已经是 camelCase，正确

// ✅ 保持不变（已正确）
```

**修改2 - 响应处理**：
```typescript
// ❌ 当前（兼容 snake_case）
const filteredByMode = data.filtered_by_mode

// ✅ 修改为（只处理 camelCase）
const filteredByMode = data.filteredByMode
```

**风险**：低

---

### 📁 frontend/services/providers/UnifiedProviderClient.ts

**问题**：Query 参数已使用 camelCase

**修改**：
```typescript
// ✅ 当前已正确
const params = {
  apiKey: apiKey,
  baseUrl: baseUrl,
  useCache: useCache
}

// 无需修改
```

**风险**：无

---

### 📁 frontend/services/auth.ts

**问题**：响应处理仍兼容 snake_case

**修改**：
```typescript
// ❌ 当前（兼容 snake_case）
const allowRegistration = data.allow_registration

// ✅ 修改为（只处理 camelCase）
const allowRegistration = data.allowRegistration
```

**风险**：低

---

## 修改统计

| 文件类型 | 文件数 | 预估修改点 | 风险等级 |
|----------|--------|------------|----------|
| Services | 5      | ~10        | 中-低    |
| Hooks    | 2      | ~4         | 中       |
| Components | 1    | ~2         | 低       |
| **总计** | **8** | **~16** | **中-低** |

---

## 修改顺序建议

1. **阶段1（核心服务）**：
   - services/storage/storageUpload.ts（文件上传）
   - hooks/useDeepResearchStream.ts（深度研究）
   - hooks/handlers/DeepResearchHandler.ts

2. **阶段2（辅助服务）**：
   - services/workflowTemplateService.ts
   - services/db.ts
   - components/modals/settings/VertexAIConfiguration.tsx

3. **阶段3（兼容性清理）**：
   - services/auth.ts（移除 snake_case 兼容）
   - services/llmService.ts（移除 snake_case 兼容）

---

## 验证清单

修改完成后，验证以下功能：

- [ ] 文件上传（各存储提供商）
- [ ] 深度研究流式输出
- [ ] 工作流模板加载
- [ ] VertexAI 配置编辑
- [ ] 用户登录和认证
- [ ] 模型列表加载

---

## 注意事项

1. **中间件已处理转换**：
   - 前端发送 camelCase Query 参数
   - 中间件自动转为 snake_case
   - 后端接收 snake_case
   - 响应时自动转回 camelCase

2. **不需要手动转换**：
   - 不要在前端代码中手动转换 camelCase/snake_case
   - 让中间件自动处理

3. **移除兼容代码**：
   - 删除对 snake_case 响应的兼容处理
   - 只处理 camelCase 字段

4. **测试重要**：
   - 每修改一个文件，立即测试相关功能
   - 确保中间件转换正常工作

---

**生成时间**：2026-01-31
**下一步**：按优先级开始修改前端代码
