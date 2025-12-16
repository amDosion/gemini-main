# Edit模式 vs Expand模式数据流分析

## 概述

本文档详细分析图片编辑（Edit）模式和图片扩展（Expand）模式的数据流差异，特别关注**云地址**和**非云地址**两种场景的处理流程。

---

## 一、数据流概览

### Edit模式（图片编辑）
- **前端组件**: `ImageEditView.tsx`
- **处理器**: `imageGenHandler.ts` (处理 `image-edit` 模式)
- **Provider实现**: 
  - Google: `google/media/image-edit.ts`
  - Tongyi: `tongyi/image-edit.ts`

### Expand模式（图片扩展/Out-Painting）
- **前端组件**: `ImageExpandView.tsx`
- **处理器**: `imageExpandHandler.ts` (处理 `image-outpainting` 模式)
- **Provider实现**: 
  - Tongyi: `tongyi/image-expand.ts`
  - 后端服务: `backend/app/services/image_expand_service.py`

---

## 二、CONTINUITY LOGIC（连续性逻辑）

两种模式都实现了**CONTINUITY LOGIC**，当用户没有上传新图片时，自动使用当前画布上的图片作为输入。

### 2.1 共同的处理流程

```typescript
// 1. 判断 activeImageUrl 的类型
const isBase64 = activeImageUrl?.startsWith('data:');
const isBlobUrl = activeImageUrl?.startsWith('blob:');
const isCloudUrl = activeImageUrl?.startsWith('http://') || activeImageUrl?.startsWith('https://');

// 2. 优先从历史消息中查找已有附件
const found = findAttachmentFromHistory(activeImageUrl);

// 3. 根据找到的附件状态处理
if (found) {
    // 复用历史附件
    // 如果 uploadStatus 是 pending，查询后端获取最新 URL
    // 设置 base64Data 字段供 API 使用
}
```

### 2.2 关键差异

#### Edit模式（ImageEditView.tsx）
- **base64Data 用途**: 供 Google API 使用（需要 Base64 格式）
- **处理逻辑**: 
  - 如果原图是 Base64，直接使用
  - 如果原图是云存储 URL，通过 `/api/storage/download` 下载后转 Base64

#### Expand模式（ImageExpandView.tsx）
- **base64Data 用途**: 供 DashScope API 使用（通过 `ensureRemoteUrl` 处理）
- **处理逻辑**: 
  - 如果原图是 Base64，直接使用
  - 如果原图是云存储 URL，通过 `/api/storage/download` 下载后转 Base64

---

## 三、原图处理流程（按URL类型分类）

### 3.1 场景A：原图是云存储URL（http/https）

#### Edit模式流程：
```
1. ImageEditView.handleSend()
   └─> 检测到 isCloudUrl = true
   └─> 调用 /api/storage/download?url=xxx 下载图片
   └─> 转换为 Base64 Data URL
   └─> 设置 attachment.base64Data = base64Url
   └─> attachment.url = 云存储URL（保持不变）

2. imageGenHandler.handleImageGen()
   └─> 调用 llmService.generateImage()
       └─> Google Provider: editImage()
           └─> processReferenceImage(attachment)
               └─> 优先使用 base64Data 字段
               └─> 提取 imageBytes（Base64字符串）
           └─> parts.push({ inlineData: { mimeType, data: imageBytes } })
       └─> Tongyi Provider: editWanxImage()
           └─> ensureRemoteUrl(attachment)
               └─> 检测到 url 是 http/https
               └─> 直接返回云存储URL（不转换）
               └─> 调用 DashScope API 时添加 X-DashScope-OssResourceResolve: enable 头

3. 结果处理
   └─> 返回 Base64 Data URL（Google）或 远程URL（Tongyi）
   └─> 创建 resultAttachment，url = 结果URL
   └─> 异步上传结果图到云存储
```

#### Expand模式流程：
```
1. ImageExpandView.handleSend()
   └─> 检测到 isCloudUrl = true
   └─> 调用 /api/storage/download?url=xxx 下载图片
   └─> 转换为 Base64 Data URL
   └─> 设置 attachment.base64Data = base64Url
   └─> attachment.url = 云存储URL（保持不变）

2. imageExpandHandler.handleImageExpand()
   └─> 调用 llmService.outPaintImage()
       └─> Tongyi Provider: outPaintWanxImage()
           └─> ensureRemoteUrl(attachment)
               └─> 检测到 url 是 http/https
               └─> 直接返回云存储URL（不转换）
               └─> 调用后端 /api/image/out-painting
                   └─> 后端 image_expand_service.py
                       └─> 检测到 image_url 是 http/https
                       └─> 直接使用（不添加 OssResourceResolve 头）
                       └─> 如果下载失败，自动回退到上传 DashScope OSS

3. 结果处理
   └─> 后端返回 output_url（远程URL）
   └─> 前端下载结果图创建 Blob URL
   └─> 创建 resultAttachment，url = blobUrl
   └─> 异步上传结果图到云存储（传 File 对象）
```

### 3.2 场景B：原图是Base64 Data URL

#### Edit模式流程：
```
1. ImageEditView.handleSend()
   └─> 检测到 isBase64 = true
   └─> 直接使用 activeImageUrl（无需下载）
   └─> 设置 attachment.base64Data = activeImageUrl
   └─> attachment.url = Base64 URL

2. imageGenHandler.handleImageGen()
   └─> 调用 llmService.generateImage()
       └─> Google Provider: editImage()
           └─> processReferenceImage(attachment)
               └─> 优先使用 base64Data 字段
               └─> 提取 imageBytes
           └─> parts.push({ inlineData: { mimeType, data: imageBytes } })
       └─> Tongyi Provider: editWanxImage()
           └─> ensureRemoteUrl(attachment)
               └─> 检测到 base64Data 存在
               └─> 转换为 File 对象
               └─> 上传到 DashScope OSS
               └─> 返回 DashScope OSS URL

3. 结果处理
   └─> 返回 Base64 Data URL（Google）或 远程URL（Tongyi）
   └─> 创建 resultAttachment
   └─> 异步上传原图到云存储（如果有 File 对象）
   └─> 异步上传结果图到云存储
```

#### Expand模式流程：
```
1. ImageExpandView.handleSend()
   └─> 检测到 isBase64 = true
   └─> 直接使用 activeImageUrl（无需下载）
   └─> 设置 attachment.base64Data = activeImageUrl
   └─> attachment.url = Base64 URL

2. imageExpandHandler.handleImageExpand()
   └─> 调用 llmService.outPaintImage()
       └─> Tongyi Provider: outPaintWanxImage()
           └─> ensureRemoteUrl(attachment)
               └─> 检测到 base64Data 存在
               └─> 转换为 File 对象
               └─> 上传到 DashScope OSS
               └─> 返回 DashScope OSS URL
           └─> 调用后端 /api/image/out-painting
               └─> 后端使用 DashScope OSS URL

3. 结果处理
   └─> 后端返回 output_url（远程URL）
   └─> 前端下载结果图创建 Blob URL
   └─> 创建 resultAttachment
   └─> 异步上传原图到云存储（如果有 File 对象）
   └─> 异步上传结果图到云存储（传 File 对象）
```

### 3.3 场景C：原图是Blob URL

#### Edit模式流程：
```
1. ImageEditView.handleSend()
   └─> 检测到 isBlobUrl = true
   └─> 通过 fetch(activeImageUrl) 下载
   └─> 转换为 Base64 Data URL
   └─> 设置 attachment.base64Data = base64Url
   └─> attachment.url = Base64 URL（或保持 Blob URL）

2. 后续流程同场景B（Base64处理）
```

#### Expand模式流程：
```
1. ImageExpandView.handleSend()
   └─> 检测到 isBlobUrl = true
   └─> 通过 fetch(activeImageUrl) 下载
   └─> 转换为 Base64 Data URL
   └─> 设置 attachment.base64Data = base64Url
   └─> attachment.url = Base64 URL（或保持 Blob URL）

2. 后续流程同场景B（Base64处理）
```

---

## 四、关键差异总结

### 4.1 API调用方式

| 模式 | Provider | API调用方式 | 图片格式要求 |
|------|----------|------------|-------------|
| **Edit** | Google | 前端直接调用，使用 Base64 inlineData | Base64 字符串 |
| **Edit** | Tongyi | 前端调用，需要远程URL | HTTP URL 或 DashScope OSS URL |
| **Expand** | Tongyi | 前端调用后端代理，后端调用 DashScope API | HTTP URL 或 DashScope OSS URL |

### 4.2 云存储URL处理

#### Edit模式（Tongyi Provider）：
```typescript
// image-utils.ts: ensureRemoteUrl()
if (imageUrl?.startsWith('http://') || imageUrl?.startsWith('https://')) {
    // ✅ 直接使用云存储URL
    // 调用 DashScope API 时添加 X-DashScope-OssResourceResolve: enable 头
    return imageUrl;
}
```

#### Expand模式（后端服务）：
```python
# image_expand_service.py: execute_with_fallback()
# 检测是否是 oss:// URL
is_oss_url = image_url.startswith("oss://")
if is_oss_url:
    # 添加 OssResourceResolve 头
    headers["X-DashScope-OssResourceResolve"] = "enable"

# 如果是 http/https URL，直接使用（不添加头）
# 如果下载失败，自动回退到上传 DashScope OSS
```

### 4.3 结果图处理

#### Edit模式：
```typescript
// imageGenHandler.ts
const resultArray: Attachment[] = results.map((res) => ({
    url: res.url,           // Base64 Data URL 或 远程URL
    tempUrl: res.url,
    uploadStatus: 'pending'
}));

// 异步上传结果图（传 URL）
uploadToCloudStorage(
    att.url,  // Base64 Data URL 或 远程URL
    context.modelMessageId,
    att.id,
    context.sessionId,
    att.name
);
```

#### Expand模式：
```typescript
// imageExpandHandler.ts
// 下载结果图创建 Blob
const imageBlob = await fetch(result.url).then(r => r.blob());
const blobUrl = URL.createObjectURL(imageBlob);
const resultFile = new File([imageBlob], resultFilename, { type: 'image/png' });

const resultArray: Attachment[] = [{
    url: blobUrl,      // Blob URL（用于显示）
    tempUrl: blobUrl,
    uploadStatus: 'pending'
}];

// 异步上传结果图（传 File 对象）
uploadToCloudStorage(
    resultFile,  // File 对象
    context.modelMessageId,
    resultAttachmentId,
    context.sessionId,
    resultFilename
);
```

### 4.4 原图上传策略

#### Edit模式：
```typescript
// imageGenHandler.ts
// 异步上传原图到云存储（如果有 File 对象）
for (const att of attachments) {
    if (att.file) {
        uploadToCloudStorage(att.file, ...);
    }
}
// ⚠️ 注意：如果原图是云存储URL，不会触发上传（因为 att.file 不存在）
```

#### Expand模式：
```typescript
// imageExpandHandler.ts
const isOriginalCloudUrl = isCloudStorageUrl(originalUrl);

// 异步上传原图到云存储（仅当原图不是云存储 URL 时）
if (!isOriginalCloudUrl && originalAttachment.file) {
    uploadToCloudStorage(originalAttachment.file, ...);
} else if (isOriginalCloudUrl) {
    console.log('原图已是云存储 URL，跳过上传');
}
```

---

## 五、数据流对比图

### Edit模式（Google Provider + 云存储URL）
```
用户发送
  ↓
ImageEditView.handleSend()
  ├─> 检测到云存储URL
  ├─> 下载转Base64 → attachment.base64Data
  └─> attachment.url = 云存储URL
  ↓
imageGenHandler.handleImageGen()
  ↓
Google Provider: editImage()
  ├─> processReferenceImage()
  │   └─> 使用 base64Data → imageBytes
  └─> parts.push({ inlineData: { mimeType, data: imageBytes } })
  ↓
Google API 返回 Base64 Data URL
  ↓
创建 resultAttachment
  ├─> url = Base64 Data URL
  └─> 异步上传结果图到云存储
```

### Expand模式（Tongyi Provider + 云存储URL）
```
用户发送
  ↓
ImageExpandView.handleSend()
  ├─> 检测到云存储URL
  ├─> 下载转Base64 → attachment.base64Data
  └─> attachment.url = 云存储URL
  ↓
imageExpandHandler.handleImageExpand()
  ↓
Tongyi Provider: outPaintWanxImage()
  ├─> ensureRemoteUrl()
  │   └─> 检测到 http/https URL
  │   └─> 直接返回云存储URL（不转换）
  └─> 调用后端 /api/image/out-painting
      └─> 后端直接使用云存储URL
      └─> 如果下载失败，回退到上传 DashScope OSS
  ↓
后端返回 output_url（远程URL）
  ↓
前端下载结果图 → Blob URL
  ↓
创建 resultAttachment
  ├─> url = Blob URL
  └─> 异步上传结果图到云存储（File对象）
```

---

## 六、关键代码位置

### Edit模式
1. **前端视图**: `frontend/components/views/ImageEditView.tsx` (169-332行)
2. **处理器**: `frontend/hooks/handlers/imageGenHandler.ts` (13-71行)
3. **Google Provider**: `frontend/services/providers/google/media/image-edit.ts` (15-124行)
4. **Tongyi Provider**: `frontend/services/providers/tongyi/image-edit.ts` (8-102行)
5. **工具函数**: `frontend/services/media/utils.ts` (16-55行)

### Expand模式
1. **前端视图**: `frontend/components/views/ImageExpandView.tsx` (164-324行)
2. **处理器**: `frontend/hooks/handlers/imageExpandHandler.ts` (14-76行)
3. **Tongyi Provider**: `frontend/services/providers/tongyi/image-expand.ts` (14-97行)
4. **后端服务**: `backend/app/services/image_expand_service.py` (32-327行)
5. **工具函数**: `frontend/services/providers/tongyi/image-utils.ts` (6-51行)

---

## 七、注意事项

### 7.1 云存储URL的处理
- **Edit模式（Tongyi）**: 云存储URL直接使用，需要添加 `X-DashScope-OssResourceResolve: enable` 头
- **Expand模式**: 云存储URL直接使用，如果下载失败会自动回退到上传 DashScope OSS

### 7.2 Base64数据的传递
- 两种模式都使用 `attachment.base64Data` 字段传递 Base64 数据
- 这个字段不会持久化到数据库，仅用于 API 调用

### 7.3 结果图的上传
- **Edit模式**: 上传时传 URL（Base64 Data URL 或远程URL）
- **Expand模式**: 上传时传 File 对象（需要先下载结果图）

### 7.4 原图上传策略
- **Edit模式**: 只要有 `att.file` 就上传（不检查是否已是云存储URL）
- **Expand模式**: 明确检查 `isOriginalCloudUrl`，如果是云存储URL则跳过上传

---

## 八、Expand模式结果图无法保存到数据库的问题分析

### 8.1 问题描述

在Expand模式中，上传附件后附件地址为 Blob URL，最后的结果图片不能保存在数据库。

### 8.2 问题原因

#### 根本原因
**保存消息到数据库时，没有调用 `cleanAttachmentsForDb` 函数来清理 Blob URL**。

#### 详细流程分析

```
1. imageExpandHandler.handleImageExpand()
   └─> 后端返回 output_url（远程URL）
   └─> 前端下载结果图创建 Blob URL
   └─> 创建 resultAttachment: { url: blobUrl, uploadStatus: 'pending' }
   └─> 异步上传结果图到云存储（传 File 对象）

2. 返回结果给 useChat.ts
   └─> 创建 finalModelMessage，包含 resultAttachment（url = blobUrl）
   └─> 调用 updateSessionMessages(currentSessionId, [...updatedMessages, finalModelMessage])

3. updateSessionMessages (useSessions.ts)
   └─> 调用 saveSessionToDb(updatedSession)
   └─> ❌ 问题：没有调用 cleanAttachmentsForDb 清理 Blob URL

4. saveSessionToDb → db.saveSession(session)
   └─> 直接保存消息，包含 Blob URL
   └─> Blob URL 被保存到数据库（但这是临时URL，页面刷新后失效）

5. 后端异步上传任务
   └─> 上传完成后调用 update_session_attachment_url()
   └─> 更新数据库中的 URL 为云存储 URL
   └─> ⚠️ 但如果上传任务失败或还没完成，URL 就会是空的或无效的
```

#### 代码位置

1. **问题位置**: `frontend/hooks/useSessions.ts` 的 `updateSessionMessages` 函数
   ```typescript
   // 第79-108行
   const updateSessionMessages = useCallback((sessionId: string, newMessages: Message[]) => {
     // ...
     saveSessionToDb(updatedSession);  // ❌ 直接保存，没有清理 Blob URL
   }, [saveSessionToDb]);
   ```

2. **清理函数存在但未使用**: `frontend/hooks/handlers/attachmentUtils.ts`
   ```typescript
   // 第25-55行
   export const cleanAttachmentsForDb = (atts: Attachment[], verbose: boolean = false): Attachment[] => {
     // 如果 url 是 Blob URL，设置为空字符串（等待上传完成后更新）
     if (cleaned.url && cleaned.url.startsWith('blob:')) {
       cleaned.url = '';
       cleaned.uploadStatus = 'pending';
     }
     // ...
   };
   ```

3. **后端合并逻辑**: `backend/app/routers/sessions.py`
   ```python
   # 第115行：如果新 URL 是 Blob URL，使用旧的永久 URL
   if not new_url or new_url.startswith('blob:') or new_url.startswith('data:'):
       att['url'] = old_data['url']
   ```
   ⚠️ 但这只适用于**更新现有消息**，不适用于**新消息**。

### 8.3 解决方案

#### 方案1：在保存前清理附件（推荐）

在 `updateSessionMessages` 中调用 `cleanAttachmentsForDb`：

```typescript
// frontend/hooks/useSessions.ts
import { cleanAttachmentsForDb } from '../handlers/attachmentUtils';

const updateSessionMessages = useCallback((sessionId: string, newMessages: Message[]) => {
  setSessions(prev => {
    const updated = prev.map(s => {
      if (s.id === sessionId) {
        // ✅ 清理附件中的 Blob URL 和 Base64 URL
        const cleanedMessages = newMessages.map(msg => ({
          ...msg,
          attachments: msg.attachments 
            ? cleanAttachmentsForDb(msg.attachments, true)  // verbose = true 输出日志
            : undefined
        }));
        
        const updatedSession = { ...s, title, messages: cleanedMessages, mode: currentMode };
        saveSessionToDb(updatedSession);
        return updatedSession;
      }
      return s;
    });
    return updated;
  });
}, [saveSessionToDb]);
```

#### 方案2：在保存时使用原始URL（临时方案）

在 `imageExpandHandler` 中，保存原始远程URL：

```typescript
// frontend/hooks/handlers/imageExpandHandler.ts
const resultArray: Attachment[] = [{ 
  id: resultAttachmentId,
  mimeType: result.mimeType,
  name: resultFilename,
  url: blobUrl,      // Blob URL（用于显示）
  tempUrl: blobUrl,
  originalUrl: result.url,  // ✅ 保存原始远程URL
  uploadStatus: 'pending'
}];
```

然后在保存时优先使用 `originalUrl`。

#### 方案3：等待上传完成后再保存（不推荐）

等待上传任务完成后再保存消息，但这会阻塞UI，影响用户体验。

### 8.4 为什么Edit模式没有这个问题？

Edit模式的结果图通常是：
- **Google Provider**: 返回 Base64 Data URL，虽然也会被清理，但通常上传更快
- **Tongyi Provider**: 返回远程URL（DashScope OSS URL），直接是永久URL

而Expand模式的结果图：
- 后端返回远程URL
- 前端下载后创建 Blob URL 用于显示
- 但保存时使用的是 Blob URL，而不是原始远程URL

### 8.5 修复建议

**立即修复**：采用方案1，在 `updateSessionMessages` 中调用 `cleanAttachmentsForDb`。

这样可以：
1. ✅ 清空 Blob URL，避免保存临时URL
2. ✅ 设置 `uploadStatus: 'pending'`，等待上传完成
3. ✅ 后端上传完成后自动更新 URL
4. ✅ 如果上传失败，URL 为空但不会保存无效的 Blob URL

---

## 九、优化建议

1. **统一原图上传策略**: Edit模式也应该检查是否已是云存储URL，避免重复上传
2. **统一结果图处理**: 考虑统一使用 File 对象上传，避免 Base64 Data URL 的转换开销
3. **错误处理**: Expand模式的后端回退机制可以应用到 Edit模式（Tongyi Provider）
4. **修复保存逻辑**: 在 `updateSessionMessages` 中调用 `cleanAttachmentsForDb` 清理临时URL（见第8节）

