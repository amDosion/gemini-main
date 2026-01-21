# 附件处理完整场景文档

## 一、文档概述

本文档完整描述了系统中所有附件处理场景，包括：
1. 不同提供商的附件 URL 类型
2. 不同来源的附件处理方式
3. 重载网页后的 URL 处理
4. 后端上传后前端会话更新策略

---

## 二、不同提供商的 URL 类型

### 2.1 Gemini 提供商

**返回类型**：Base64 Data URL

**代码位置**：`backend/app/services/gemini/imagen_gemini_api.py:270`

```python
result = {
    "url": f"data:{output_mime_type};base64,{b64_data}",
    "mimeType": output_mime_type,
    "index": idx,
    "size": len(image_bytes)
}
```

**特点**：
- ✅ 立即可用，无需下载
- ✅ 前端可以直接显示
- ⚠️ 体积较大（Base64 编码增加 33% 大小）
- ⚠️ 重载后失效（Base64 URL 被 `cleanAttachmentsForDb` 清空）

**处理流程**：
```
1. Gemini API 返回 GeneratedImage 对象
   ↓
2. 读取 image_bytes
   ↓
3. 编码为 Base64 Data URL
   ↓
4. 返回给前端：data:image/png;base64,xxx
   ↓
5. 前端立即显示
   ↓
6. 后端异步上传到云存储
   ↓
7. 上传完成后更新数据库（url 字段更新为云存储 URL）
```

---

### 2.2 Tongyi 提供商

**返回类型**：HTTP URL（临时 URL）

**代码位置**：`backend/app/services/tongyi/image_generation.py:354`

```python
if "image" in item:
    image_url = item["image"]
    url_type = "HTTP" if image_url.startswith('http') else "其他"
    results.append(ImageGenerationResult(url=image_url))
```

**特点**：
- ✅ 可以立即显示（浏览器可以直接加载）
- ⚠️ 可能有时效性（临时 URL 可能过期）
- ⚠️ 重载后可能失效（如果临时 URL 过期，会被 `cleanAttachmentsForDb` 清空）

**处理流程**：
```
1. Tongyi API 返回 HTTP 临时 URL
   ↓
2. 后端直接返回给前端：https://dashscope.aliyuncs.com/...
   ↓
3. 前端立即显示（浏览器直接加载）
   ↓
4. 后端异步上传到云存储
   ↓
5. 上传完成后更新数据库（url 字段更新为云存储 URL）
```

---

### 2.3 其他提供商

**可能返回的类型**：
- Base64 Data URL
- HTTP 临时 URL
- 其他格式

**处理方式**：统一由 `attachment_service.py` 处理

---

## 三、不同来源的附件处理

### 3.1 场景 1：用户上传附件

**触发时机**：
- 用户在 Edit/Expand 模式中点击上传按钮
- 选择本地图片文件

**处理函数**：`processUserAttachments`（`attachmentUtils.ts:871`）

**处理流程**：
```typescript
// 1. 用户选择文件
const file = event.target.files[0];

// 2. 创建预览（Blob URL）
const blobUrl = URL.createObjectURL(file);

// 3. 创建附件对象
const attachment: Attachment = {
  id: uuidv4(),
  file: file,  // ✅ 保留 File 对象
  url: blobUrl,  // ✅ 用于预览
  mimeType: file.type,
  name: file.name,
  uploadStatus: 'pending'
};

// 4. 提交到后端
// 后端 modes.py 调用 AttachmentService.process_user_upload()
// 后端统一处理上传到云存储
```

**后端处理**（`attachment_service.py:process_user_upload`）：
- 接收 File 对象
- 上传到云存储
- 创建附件记录
- 返回 `attachmentId` 和 `taskId`

**特点**：
- ✅ 前端只负责文件选择和预览
- ✅ 后端统一处理上传
- ✅ 上传完成后更新数据库

---

### 3.2 场景 2：跨模式时发送的附件

**触发时机**：
- 从 GEN 模式跳转到 Edit/Expand 模式
- 点击 Edit/Expand 按钮

**处理函数**：`prepareAttachmentForApi`（`attachmentUtils.ts:660`）

**处理流程**：
```typescript
// 1. 查找历史附件
const found = findAttachmentByUrl(imageUrl, messages);

// 2. 如果找到，复用附件信息
if (found) {
  // 查询后端获取永久云存储 URL（如果上传已完成）
  const cloudResult = await tryFetchCloudUrl(...);
  
  // 返回附件对象
  return {
    id: found.attachment.id,
    url: cloudResult?.url || found.attachment.url,
    uploadStatus: cloudResult?.uploadStatus || found.attachment.uploadStatus
  };
}

// 3. 如果未找到，创建新附件
return {
  id: uuidv4(),
  url: imageUrl,
  uploadStatus: 'pending'
};
```

**特点**：
- ✅ 复用历史附件的 ID 和信息
- ✅ 查询后端获取永久云存储 URL（如果上传已完成）
- ✅ 避免重复上传

---

### 3.3 场景 3：没有上传附件，获取活跃画布当作附件（CONTINUITY LOGIC）

**触发时机**：
- 用户在 Edit/Expand 模式中，没有上传新附件
- 直接点击发送按钮
- 使用画布上的图片作为附件

**处理函数**：`prepareAttachmentForApi`（`attachmentUtils.ts:660`）

**处理流程**：
```typescript
// 1. 获取画布上的图片 URL
const activeImageUrl = getStableCanvasUrlFromAttachment(activeAttachments[0]);

// 2. 调用 prepareAttachmentForApi
const prepared = await prepareAttachmentForApi(
  activeImageUrl,  // 画布上的图片 URL
  messages,
  sessionId,
  'canvas'
);

// 3. 后端处理 CONTINUITY LOGIC
// 后端 modes.py 调用 AttachmentService.resolve_continuity_attachment()
// 后端查找或创建附件记录
```

**后端处理**（`attachment_service.py:resolve_continuity_attachment`）：
- 查找历史附件（通过 URL 匹配）
- 如果找到，复用附件 ID
- 如果未找到，创建新附件记录
- 返回附件信息

**特点**：
- ✅ 无需用户上传，自动使用画布图片
- ✅ 复用历史附件，避免重复上传
- ✅ 后端统一处理

---

### 3.4 场景 4：AI 生成的附件

**触发时机**：
- GEN 模式生成图片
- Edit 模式编辑图片
- Expand 模式扩展图片

**处理函数**：
- **ImageGenHandler**：直接使用后端返回的 URL（`ImageGenHandlerClass.ts:27-34`）
- **ImageEditHandler**：直接使用后端返回的 URL（`ImageEditHandlerClass.ts:67-74`）

**处理流程**：
```typescript
// 1. 调用 AI API
const results = await llmService.generateImage(...);

// 2. 后端处理（attachment_service.py）
// - 创建附件记录
// - 提交异步上传任务
// - 返回 display_url（Base64 或 HTTP URL）

// 3. 前端直接使用
const displayAttachments: Attachment[] = results.map((res) => ({
  id: res.attachmentId,
  url: res.url,  // ✅ Base64 或 HTTP URL
  uploadStatus: res.uploadStatus || 'pending',
  uploadTaskId: res.taskId
}));
```

**特点**：
- ✅ 后端统一处理附件创建和上传任务
- ✅ 前端直接使用后端返回的 URL
- ✅ 无需前端转换

---

## 四、重载网页后的 URL 处理

### 4.1 保存到数据库时的清理

**函数**：`cleanAttachmentsForDb`（`attachmentUtils.ts:98`）

**清理规则**：
```typescript
// 1. Blob URL：清空（页面刷新后失效）
if (isBlobUrl(url)) {
  cleaned.url = '';
  cleaned.uploadStatus = 'pending';
}

// 2. Base64 URL：清空（体积太大，不适合数据库）
else if (isBase64Url(url)) {
  cleaned.url = '';
  cleaned.uploadStatus = 'pending';
}

// 3. HTTP URL：根据状态处理
else if (isHttpUrl(url)) {
  // 3.1 如果 uploadStatus === 'completed'，保留（永久云存储 URL）
  if (cleaned.uploadStatus === 'completed') {
    // ✅ 保留永久云存储 URL
  }
  // 3.2 如果有 uploadTaskId，保留（上传进行中）
  else if (uploadTaskId) {
    cleaned.uploadStatus = 'pending';
  }
  // 3.3 如果是临时 URL（包含 /temp/ 或 expires=），清空
  else if (url.includes('/temp/') || url.includes('expires=')) {
    cleaned.url = '';
    cleaned.uploadStatus = 'pending';
  }
  // 3.4 其他 HTTP URL，标记为 pending
  else {
    cleaned.uploadStatus = 'pending';
  }
}
```

**结果**：
- ✅ 只有永久云存储 URL（`uploadStatus === 'completed'`）会被保留
- ✅ Base64 URL 和 Blob URL 会被清空
- ✅ 临时 HTTP URL 会被清空

---

### 4.2 重载后从数据库加载

**函数**：`prepareSessions`（`useSessions.ts:34`）

**恢复逻辑**：
```typescript
const recoveredAttachments = message.attachments.map(att => {
  // 检查 url 是否是 Blob URL（页面刷新后已失效）
  if (att.url && att.url.startsWith('blob:')) {
    // 如果有 tempUrl（云存储 URL），使用它替代失效的 Blob URL
    if (att.tempUrl && att.tempUrl.startsWith('http')) {
      return {
        ...att,
        url: att.tempUrl, // ✅ 替换为云存储 URL
        uploadStatus: 'completed' as const
      };
    }
  }
  
  // 其他类型的 URL（Base64, HTTP）不需要恢复
  return att;
});
```

**结果**：
- ✅ 重载后，只有永久云存储 URL 会被保留
- ✅ 如果 Blob URL 失效，使用 `tempUrl` 中的云存储 URL 替换
- ✅ Base64 URL 已被清空，无法恢复（需要重新生成或查询后端）

---

### 4.3 重载后的显示逻辑

**流程**：
```
1. 重载网页
   ↓
2. 从数据库加载会话和消息
   ↓
3. cleanAttachmentsForDb 已清空 Base64 和 Blob URL
   ↓
4. 只有永久云存储 URL（uploadStatus === 'completed'）被保留
   ↓
5. prepareSessions 恢复 Blob URL（如果有 tempUrl）
   ↓
6. 前端显示：使用永久云存储 URL
```

**验证**：
- ✅ `cleanAttachmentsForDb` 会清空 Base64 和 Blob URL
- ✅ 只有 `uploadStatus === 'completed'` 的 HTTP URL 会被保留
- ✅ `prepareSessions` 会恢复失效的 Blob URL（使用 tempUrl）
- ✅ 重载后，前端使用永久云存储 URL 显示

---

## 五、后端上传后前端会话更新策略

### 5.1 当前实现

**代码位置**：`BaseHandler.ts:196-241`

**实现逻辑**：
```typescript
onSuccess: async (taskId, result) => {
  // ============================================================
  // 长期方案：上传完成后更新数据库中的 tempUrl
  // 只更新数据库，不调用 context.onProgressUpdate()，避免前端重新渲染
  // ============================================================
  if (result && result.url) {
    try {
      // 更新数据库
      await db.updateAttachmentUrl(
        context.sessionId,
        messageId,
        attachment.id,
        result.url  // 永久云存储 URL
      );
      console.log('[BaseHandler] ✅ 数据库 tempUrl 更新成功');
    } catch (dbError) {
      console.error('[BaseHandler] ⚠️ 更新数据库 tempUrl 失败:', dbError);
    }
  }
  
  // 原有逻辑：通知前端上传完成（可选，根据需求决定是否保留）
  // 注释掉以避免前端重新渲染
  // context.onProgressUpdate?.({
  //   attachmentId: attachment.id,
  //   status: 'completed',
  //   progress: 100
  // });
}
```

**特点**：
- ✅ 只更新数据库，不更新前端会话
- ✅ 避免前端重新渲染
- ✅ 保持原始 URL（Base64 或 HTTP 临时 URL）用于显示

---

### 5.2 为什么这样设计？

**原因 1：避免不必要的查询**
- 如果前端更新会话，用户点击 Edit/Expand 按钮时，会使用更新后的云存储 URL
- 但原始 URL（Base64 或 HTTP 临时 URL）仍然可以显示
- 保持原始 URL 可以避免查询后端

**原因 2：避免前端重新渲染**
- 如果调用 `context.onProgressUpdate()`，会触发前端重新渲染
- 可能导致图片闪烁或重新加载
- 影响用户体验

**原因 3：重载后自动使用云存储 URL**
- 重载后，`cleanAttachmentsForDb` 会清空 Base64 和 Blob URL
- 只有永久云存储 URL 会被保留
- 前端自动使用云存储 URL 显示

---

### 5.3 验证当前实现

**代码验证**：
- ✅ `BaseHandler.ts:199`：注释明确说明"只更新数据库，不调用 context.onProgressUpdate()，避免前端重新渲染"
- ✅ `BaseHandler.ts:241-247`：`context.onProgressUpdate` 被注释掉
- ✅ `useChat.ts:236`：只在初始保存时调用 `updateSessionMessages`，上传完成后不更新

**结论**：
- ✅ 当前实现符合要求：后端上传完成后，只更新数据库，不更新前端会话
- ✅ 前端保持原始 URL（Base64 或 HTTP 临时 URL）用于显示
- ✅ 重载后，自动使用永久云存储 URL

---

## 六、完整场景矩阵

| 场景 | 提供商 | URL 类型 | 处理函数 | 重载后 | 后端上传后 |
|------|--------|---------|---------|--------|-----------|
| **用户上传附件** | - | File → Blob URL | `processUserAttachments` | 使用云存储 URL | 只更新数据库 |
| **跨模式附件** | - | Base64/HTTP/Blob | `prepareAttachmentForApi` | 使用云存储 URL | 只更新数据库 |
| **画布附件（CONTINUITY）** | - | Base64/HTTP/Blob | `prepareAttachmentForApi` | 使用云存储 URL | 只更新数据库 |
| **AI 生成（Gemini）** | Gemini | Base64 Data URL | `ImageGenHandler` | 使用云存储 URL | 只更新数据库 |
| **AI 生成（Tongyi）** | Tongyi | HTTP 临时 URL | `ImageGenHandler` | 使用云存储 URL | 只更新数据库 |
| **AI 编辑（Gemini）** | Gemini | Base64 Data URL | `ImageEditHandler` | 使用云存储 URL | 只更新数据库 |
| **AI 编辑（Tongyi）** | Tongyi | HTTP 临时 URL | `ImageEditHandler` | 使用云存储 URL | 只更新数据库 |

---

## 七、关键设计原则

### 7.1 URL 生命周期管理

**原则 1：立即显示优先**
- 无论 URL 类型，都应该立即显示
- 不等待查询后端或上传完成

**原则 2：永久 URL 用于持久化**
- 重载后，只有永久云存储 URL 会被保留
- Base64 和 Blob URL 会被清空

**原则 3：后端上传不更新前端会话**
- 后端上传完成后，只更新数据库
- 前端保持原始 URL 用于显示
- 重载后自动使用云存储 URL

---

### 7.2 不同场景的处理策略

| 场景 | 策略 |
|------|------|
| **用户上传** | File 对象 → 后端统一处理上传 |
| **跨模式传递** | 查找历史附件 → 复用 ID → 查询云存储 URL（如果需要） |
| **画布附件** | CONTINUITY LOGIC → 后端查找或创建附件 |
| **AI 生成** | 直接使用后端返回的 URL → 后端异步上传 |

---

## 八、相关文档

- `IMAGE_GEN_TO_EDIT_EXPAND_FLOW.md` - 完整流程文档
- `CODE_ANALYSIS_AND_OPTIMIZATION.md` - 代码分析与优化建议
- `requirements.md` - 需求文档
- `design.md` - 设计文档
- `tasks.md` - 任务文档

---

## 九、更新日志

- **2024-01-21**：创建完整的附件处理场景文档，涵盖所有提供商、所有场景、重载处理和会话更新策略
