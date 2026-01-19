# 前端适配计划

> **日期**: 2026-01-18
> **目标**: 适配新的后端统一附件处理API

---

## 📋 需要适配的功能

### 1. 图片生成和编辑结果处理

**后端返回格式**（新）:
```json
{
  "images": [
    {
      "url": "/api/temp-images/{attachment_id}" 或 HTTP URL,
      "attachmentId": "att-123",
      "uploadStatus": "pending",
      "taskId": "task-123"
    }
  ]
}
```

**前端需要**:
- ✅ 更新 `ImageGenerationResult` 接口，添加 `attachmentId`, `uploadStatus`, `taskId` 字段
- ✅ 更新 `UnifiedProviderClient.executeMode()` 处理新的响应格式
- ✅ 更新图片显示逻辑，使用 `url` 字段（可能是临时代理URL）

---

### 2. CONTINUITY LOGIC 后端化

**旧方式**: 前端 `findAttachmentByUrl()` 遍历消息查找附件

**新方式**: 使用后端API `/api/attachments/resolve-continuity`

**需要更新**:
- ✅ 更新 `prepareAttachmentForApi()` 使用新的API端点
- ✅ 移除前端 `findAttachmentByUrl()` 逻辑（可选，保留作为fallback）

---

### 3. 云URL查询

**旧方式**: `fetchAttachmentStatus()` 使用 `/api/sessions/{sessionId}/attachments/{attachmentId}`

**新方式**: 使用 `/api/attachments/{attachment_id}/cloud-url`

**需要更新**:
- ✅ 更新 `tryFetchCloudUrl()` 使用新的API端点
- ✅ 更新 `fetchAttachmentStatus()` 使用新的API端点

---

## 🔧 具体修改

### 修改1: 更新 ImageGenerationResult 接口

**文件**: `frontend/services/providers/interfaces.ts`

```typescript
export interface ImageGenerationResult {
  url: string;  // 显示URL（可能是 /api/temp-images/{attachment_id} 或 HTTP URL）
  mimeType: string;
  filename?: string;
  // ✅ 新增字段
  attachmentId?: string;  // 附件ID
  uploadStatus?: 'pending' | 'completed' | 'failed';  // 上传状态
  taskId?: string;  // 上传任务ID
  thoughts?: Array<{ type: 'text' | 'image'; content: string }>;
  text?: string;
}
```

---

### 修改2: 更新 UnifiedProviderClient.executeMode()

**文件**: `frontend/services/providers/UnifiedProviderClient.ts`

**需要处理**:
- 后端返回的 `images` 数组格式
- 将后端响应转换为 `ImageGenerationResult[]`

---

### 修改3: 更新 tryFetchCloudUrl()

**文件**: `frontend/hooks/handlers/attachmentUtils.ts`

**旧代码**:
```typescript
const response = await fetch(`/api/sessions/${sessionId}/attachments/${attachmentId}`, {
  headers,
  credentials: 'include',
});
```

**新代码**:
```typescript
const response = await fetch(`/api/attachments/${attachmentId}/cloud-url`, {
  headers,
  credentials: 'include',
});
```

---

### 修改4: 更新 prepareAttachmentForApi() - CONTINUITY LOGIC

**文件**: `frontend/hooks/handlers/attachmentUtils.ts`

**需要添加**:
- 调用 `/api/attachments/resolve-continuity` API
- 处理返回的 `{attachmentId, url, status, taskId}`

---

## 📝 实施步骤

1. ✅ 更新类型定义
2. ✅ 更新 API 调用
3. ✅ 更新 CONTINUITY LOGIC
4. ✅ 测试验证

---

**状态**: 待实施
