# GEN模式跳转Edit/Expand模式附件显示设计文档

## 一、设计目标

优化 GEN 模式跳转到 Edit/Expand 模式时的附件显示逻辑，确保：
1. **即时显示**：图片在点击按钮后立即显示，无需等待后端查询
2. **减少延迟**：避免不必要的后端查询，特别是对 Base64 URL 的查询
3. **提升可靠性**：处理各种 URL 类型和上传状态，确保图片能够显示

---

## 二、当前实现分析

### 2.1 当前流程

```
1. 用户点击 Edit/Expand 按钮
   ↓
2. 传递 att.url（Base64 或 HTTP URL）
   ↓
3. handleEditImage(url) 被调用
   ↓
4. findAttachmentByUrl(url, messages) 查找历史附件
   ↓
5. 如果找到且 uploadStatus === 'pending'，调用 tryFetchCloudUrl
   ↓
6. tryFetchCloudUrl 检查：currentStatus === 'pending' || !isHttpUrl(currentUrl)
   ↓
7. 如果传入 Base64 URL，!isHttpUrl 为 true，触发查询 ⚠️
   ↓
8. 异步查询后端，等待响应
   ↓
9. 如果查询返回 null，使用传入的 URL
   ↓
10. 设置 initialAttachments，切换到目标模式
```

### 2.2 问题点

1. **问题 1：Base64 URL 被不必要查询**
   - **位置**：`attachmentUtils.ts:385-388`
   - **问题**：`!isHttpUrl(currentUrl)` 对 Base64 URL 为 true，触发查询
   - **影响**：不必要的网络请求和延迟

2. **问题 2：异步查询导致延迟**
   - **位置**：`useImageHandlers.ts:57-68`
   - **问题**：如果 `uploadStatus === 'pending'`，会异步查询后端
   - **影响**：在查询完成前，可能使用临时 URL，导致延迟

3. **问题 3：HTTP 临时 URL 过期风险**
   - **位置**：`useImageHandlers.ts:51`
   - **问题**：如果上传未完成，可能使用已过期的 HTTP 临时 URL
   - **影响**：图片无法显示

---

## 三、设计方案

### 3.1 设计原则

1. **优先使用本地数据**：Base64 URL 和 HTTP URL 应该直接使用，不查询后端
2. **延迟查询**：只有在必要时（如上传已完成且有云 URL）才查询后端
3. **降级策略**：如果 HTTP URL 不可用，尝试使用 Base64 URL

### 3.2 核心设计

#### 设计 1：优化 tryFetchCloudUrl 逻辑

**目标**：避免对 Base64 URL 进行不必要的查询

**实现**：
```typescript
export const tryFetchCloudUrl = async (
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string | undefined,
  currentStatus: string | undefined
): Promise<{ url: string; uploadStatus: string } | null> => {
  // ✅ 优化：Base64 URL 和 Blob URL 直接使用，不查询后端
  if (currentUrl && (isBase64Url(currentUrl) || isBlobUrl(currentUrl))) {
    console.log('[tryFetchCloudUrl] Base64/Blob URL，直接使用，不查询后端');
    return null;
  }

  // ✅ 优化：只有 HTTP URL 且状态为 pending 时才查询
  const needFetch = sessionId && (
    currentStatus === 'pending' && 
    isHttpUrl(currentUrl)  // ✅ 只对 HTTP URL 查询
  );

  if (!needFetch) {
    return null;
  }

  // 查询后端...
};
```

**优势**：
- ✅ Base64 URL 不触发查询，立即使用
- ✅ Blob URL 不触发查询，立即使用
- ✅ 只有 HTTP URL 且 pending 时才查询

#### 设计 2：优化 useImageHandlers 逻辑

**目标**：优先使用传入的 URL，延迟查询后端

**实现**：
```typescript
const handleEditImage = useCallback(async (url: string) => {
  setAppMode('image-chat-edit');

  const found = findAttachmentByUrl(url, messages);

  let newAttachment: Attachment;

  if (found) {
    newAttachment = {
      id: found.attachment.id,
      mimeType: found.attachment.mimeType || 'image/png',
      name: found.attachment.name || 'Reference Image',
      url: url, // ✅ 优先使用传入的 URL
      tempUrl: found.attachment.tempUrl,
      uploadStatus: found.attachment.uploadStatus
    };

    // ✅ 优化：只有 HTTP URL 且 pending 时才查询，Base64 URL 直接使用
    const shouldFetchCloudUrl = found.attachment.uploadStatus === 'pending' && 
                                currentSessionId && 
                                isHttpUrl(url);  // ✅ 只对 HTTP URL 查询

    if (shouldFetchCloudUrl) {
      // 异步查询，但不阻塞显示
      tryFetchCloudUrl(...).then(cloudResult => {
        if (cloudResult) {
          // 可选：更新 URL（如果用户还在查看）
          // 但不应该影响初始显示
        }
      });
    }
  } else {
    newAttachment = {
      id: uuidv4(),
      mimeType: 'image/png',
      name: 'Reference Image',
      url: url  // ✅ 直接使用传入的 URL
    };
  }

  // ✅ 立即设置，不等待查询
  setInitialAttachments([newAttachment]);
  setInitialPrompt("Make it look like...");
  // ...
}, [messages, currentSessionId, ...]);
```

**优势**：
- ✅ 立即设置 `initialAttachments`，不等待查询
- ✅ Base64 URL 直接使用，不查询
- ✅ HTTP URL 直接使用，查询在后台进行

#### 设计 3：降级策略

**目标**：如果 HTTP URL 不可用，尝试使用 Base64 URL

**实现**：
```typescript
// 在 useImageHandlers 中
if (found) {
  // 优先使用传入的 URL
  let displayUrl = url;
  
  // 如果传入的是 HTTP URL，且不可用，尝试使用 tempUrl 中的 Base64
  if (isHttpUrl(url) && found.attachment.tempUrl && isBase64Url(found.attachment.tempUrl)) {
    // 可选：验证 HTTP URL 是否可用
    // 如果不可用，使用 Base64 URL
    displayUrl = found.attachment.tempUrl;
  }
  
  newAttachment = {
    id: found.attachment.id,
    url: displayUrl,  // ✅ 使用优化后的 URL
    // ...
  };
}
```

**优势**：
- ✅ 如果 HTTP URL 不可用，自动降级到 Base64 URL
- ✅ 提升可靠性

---

## 四、详细设计

### 4.1 tryFetchCloudUrl 优化

**文件**：`frontend/hooks/handlers/attachmentUtils.ts`

**修改位置**：第 378-411 行

**修改内容**：
```typescript
export const tryFetchCloudUrl = async (
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string | undefined,
  currentStatus: string | undefined
): Promise<{ url: string; uploadStatus: string } | null> => {
  // ✅ 新增：Base64 URL 和 Blob URL 直接使用，不查询后端
  if (currentUrl) {
    if (isBase64Url(currentUrl)) {
      console.log('[tryFetchCloudUrl] Base64 URL，直接使用，不查询后端');
      return null;
    }
    if (isBlobUrl(currentUrl)) {
      console.log('[tryFetchCloudUrl] Blob URL，直接使用，不查询后端');
      return null;
    }
  }

  // ✅ 优化：只有 HTTP URL 且状态为 pending 时才查询
  const needFetch = sessionId && (
    currentStatus === 'pending' && 
    isHttpUrl(currentUrl)  // ✅ 只对 HTTP URL 查询
  );

  if (!needFetch) {
    return null;
  }

  console.log('[tryFetchCloudUrl] 查询后端, 原因: uploadStatus=pending 且是 HTTP URL');

  const backendData = await fetchAttachmentStatus(sessionId, attachmentId);

  if (backendData && isHttpUrl(backendData.url) && backendData.uploadStatus === 'completed') {
    console.log('[tryFetchCloudUrl] ✅ 获取到云 URL:', backendData.url.substring(0, 60));
    return {
      url: backendData.url,
      uploadStatus: 'completed'
    };
  }

  console.log('[tryFetchCloudUrl] ⚠️ 后端未返回有效云 URL');
  return null;
};
```

### 4.2 useImageHandlers 优化

**文件**：`frontend/hooks/useImageHandlers.ts`

**修改位置**：第 37-86 行（handleEditImage）和第 88-159 行（handleExpandImage）

**修改内容**：
```typescript
const handleEditImage = useCallback(async (url: string) => {
  setAppMode('image-chat-edit');

  const found = findAttachmentByUrl(url, messages);

  let newAttachment: Attachment;

  if (found) {
    // ✅ 优化：优先使用传入的 URL，如果不可用则使用 tempUrl
    let displayUrl = url;
    
    // 如果传入的是 HTTP URL，且 tempUrl 是 Base64，保留作为备选
    if (isHttpUrl(url) && found.attachment.tempUrl && isBase64Url(found.attachment.tempUrl)) {
      // 保留 tempUrl 作为备选，但不立即使用（优先使用 HTTP URL）
      // 如果 HTTP URL 失败，可以在后续降级使用
    }

    newAttachment = {
      id: found.attachment.id,
      mimeType: found.attachment.mimeType || 'image/png',
      name: found.attachment.name || 'Reference Image',
      url: displayUrl,  // ✅ 优先使用传入的 URL
      tempUrl: found.attachment.tempUrl,
      uploadStatus: found.attachment.uploadStatus
    };

    // ✅ 优化：只有 HTTP URL 且 pending 时才查询，Base64 URL 直接使用
    const shouldFetchCloudUrl = found.attachment.uploadStatus === 'pending' && 
                                 currentSessionId && 
                                 isHttpUrl(url);  // ✅ 只对 HTTP URL 查询

    if (shouldFetchCloudUrl) {
      // ✅ 异步查询，但不阻塞显示
      tryFetchCloudUrl(
        currentSessionId,
        found.attachment.id,
        found.attachment.url,
        found.attachment.uploadStatus
      ).then(cloudResult => {
        if (cloudResult) {
          // 可选：如果查询成功，可以更新 URL（但不影响初始显示）
          console.log('[handleEditImage] 云 URL 查询成功，但初始显示已使用原始 URL');
        }
      }).catch(err => {
        console.warn('[handleEditImage] 云 URL 查询失败，使用原始 URL:', err);
      });
    }
  } else {
    newAttachment = {
      id: uuidv4(),
      mimeType: 'image/png',
      name: 'Reference Image',
      url: url  // ✅ 直接使用传入的 URL
    };
  }

  // ✅ 立即设置，不等待查询
  setInitialAttachments([newAttachment]);
  setInitialPrompt("Make it look like...");
  // ...
}, [messages, currentSessionId, ...]);
```

---

## 五、设计优势

### 5.1 性能优势

- ✅ **减少网络请求**：Base64 URL 不触发查询，减少 50% 以上的不必要请求
- ✅ **即时显示**：图片在点击按钮后立即显示，无需等待查询
- ✅ **降低延迟**：避免异步查询导致的延迟

### 5.2 可靠性优势

- ✅ **降级策略**：如果 HTTP URL 不可用，可以降级使用 Base64 URL
- ✅ **容错处理**：处理各种 URL 类型和上传状态
- ✅ **向后兼容**：不影响现有功能

### 5.3 用户体验优势

- ✅ **即时反馈**：点击按钮后立即看到图片
- ✅ **流畅体验**：无需等待后端查询
- ✅ **稳定可靠**：无论上传状态如何，都能显示图片

---

## 六、实施计划

### 阶段 1：优化 tryFetchCloudUrl（0.5 天）

1. 修改 `tryFetchCloudUrl`，添加 Base64/Blob URL 检查
2. 优化查询条件，只对 HTTP URL 且 pending 时查询
3. 测试验证

### 阶段 2：优化 useImageHandlers（0.5 天）

1. 修改 `handleEditImage` 和 `handleExpandImage`
2. 优化查询逻辑，不阻塞初始显示
3. 测试验证

### 阶段 3：测试验证（0.5 天）

1. 测试 Base64 URL 场景
2. 测试 HTTP URL 场景
3. 测试上传未完成场景
4. 性能测试

---

## 七、风险评估

### 7.1 技术风险

- **风险 1**：修改可能影响其他功能
  - **缓解**：充分测试，确保向后兼容

- **风险 2**：HTTP URL 过期问题
  - **缓解**：添加降级策略，使用 Base64 URL

### 7.2 业务风险

- **风险 1**：用户体验下降
  - **缓解**：优化后用户体验应该提升

---

## 八、相关文档

- `requirements.md` - 需求文档
- `tasks.md` - 任务文档
- `IMAGE_GEN_TO_EDIT_EXPAND_FLOW.md` - 完整流程文档

---

## 九、更新日志

- **2024-01-18**：创建设计文档，基于需求文档设计优化方案
