# 附件上传逻辑分析与修复方案

## 1. 问题背景

在 `image-edit` 模式中，当 `activeImageUrl` 是云存储 URL 时，出现以下错误：

```
[editImage] Failed to fetch reference image: https://img.dicry.com/xxx.png TypeError: Failed to fetch
```

原因是 `attachmentUtils.ts` 中的 `isCloudStorageUrl` 函数通过 URL 格式（`http://` 或 `https://`）判断是否是云存储 URL，这种判断方式不准确。

---

## 2. 附件来源分析

### 2.1 来源 1：用户手动上传文件

**代码位置：** `frontend/components/chat/InputArea.tsx` 第 130-165 行

```typescript
const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const attachment: Attachment = {
        id: attachmentId,
        file: file,           // ✅ 保留 File 对象
        mimeType: file.type,
        name: file.name,
        url: blobUrl,         // Blob URL 用于 UI 预览
        tempUrl: blobUrl,
        uploadStatus: 'pending'  // ✅ 等待发送时上传
    };
};
```

**特征：**
| 字段 | 值 |
|------|-----|
| `file` | File 对象 |
| `url` | `blob:xxx` 格式 |
| `uploadStatus` | `'pending'` |

---

### 2.2 来源 2：AI 返回的结果图

**代码位置：** 各个 Handler（如 `imageGenHandler.ts`、`imageEditHandler.ts`）

AI 返回的结果可能是：
- Base64 URL: `data:image/png;base64,xxx`
- 远程临时 URL: `https://dashscope.aliyuncs.com/temp/xxx`（会过期）

**特征：**
| 字段 | 值 |
|------|-----|
| `file` | 无 |
| `url` | `data:xxx` 或 `https://xxx`（临时） |
| `uploadStatus` | `'pending'`（上传前）→ `'completed'`（上传后） |

---

### 2.3 来源 3：CONTINUITY LOGIC 复用的历史附件

**代码位置：** `ImageEditView.tsx` / `ImageExpandView.tsx` 第 186-310 行

CONTINUITY LOGIC 处理三种情况：
1. 从历史消息中找到附件（可能已上传）
2. `activeImageUrl` 是云存储 URL（页面刷新后从数据库加载）
3. `activeImageUrl` 是 Base64/Blob（当前会话中的临时数据）

**关键代码：**
```typescript
// CONTINUITY LOGIC
if (finalAttachments.length === 0 && activeImageUrl) {
    // 情况 1：复用历史附件
    const found = findAttachmentFromHistory(activeImageUrl);
    if (found) {
        // 检查 uploadStatus，如果是 pending 则查询后端
        if (finalUploadStatus === 'pending' && currentSessionId) {
            const backendData = await fetchAttachmentFromBackend(...);
        }
    }
    // 情况 2：云存储 URL（需要下载转 Base64）
    else if (isCloudUrl) {
        const fetchUrl = `/api/storage/download?url=${encodeURIComponent(activeImageUrl)}`;
        // 下载并转换为 Base64
    }
    // 情况 3：Base64/Blob 兜底
    else if (isBase64 || isBlobUrl) {
        // 直接使用
    }
}
```

---

### 2.4 来源 4：从数据库加载的历史消息附件

**场景：** 页面刷新后，从数据库加载消息

**特征：**
| 字段 | 值 |
|------|-----|
| `file` | 无（不能序列化） |
| `url` | 云存储 URL（`https://img.dicry.com/xxx`） |
| `uploadStatus` | `'completed'` |

---

## 3. 附件状态流转图

```
┌─────────────────────────────────────────────────────────────────┐
│                        附件来源                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户上传文件          AI 返回结果           数据库加载          │
│       │                    │                    │               │
│       ▼                    ▼                    ▼               │
│  ┌─────────┐         ┌─────────┐         ┌─────────┐           │
│  │ file: ✓ │         │ file: ✗ │         │ file: ✗ │           │
│  │ url:    │         │ url:    │         │ url:    │           │
│  │ blob:xx │         │ data:xx │         │ https:  │           │
│  │ status: │         │ 或      │         │ //cloud │           │
│  │ pending │         │ https:  │         │ status: │           │
│  └────┬────┘         │ //temp  │         │completed│           │
│       │              │ status: │         └────┬────┘           │
│       │              │ pending │              │                │
│       │              └────┬────┘              │                │
│       │                   │                   │                │
│       ▼                   ▼                   │                │
│  ┌─────────────────────────────┐              │                │
│  │     uploadToCloudStorage    │              │                │
│  │     (需要上传到云存储)       │              │                │
│  └─────────────┬───────────────┘              │                │
│                │                              │                │
│                ▼                              │                │
│  ┌─────────────────────────────┐              │                │
│  │  url: https://cloud/xxx     │◄─────────────┘                │
│  │  uploadStatus: 'completed'  │                               │
│  └─────────────────────────────┘                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 判断逻辑依据

### 4.1 核心原则

**判断是否需要上传应该基于 `uploadStatus` 字段，而不是 URL 格式或域名。**

### 4.2 判断规则

| 判断条件 | 含义 | 是否需要上传 |
|----------|------|-------------|
| `uploadStatus === 'completed'` | 已上传到云存储 | ❌ 不需要 |
| `uploadStatus === 'pending'` + `file` 存在 | 用户上传的新文件 | ✅ 需要 |
| `uploadStatus === 'pending'` + `url` 是 Base64 | AI 返回的 Base64 | ✅ 需要 |
| `uploadStatus === 'pending'` + `url` 是 Blob | 用户上传的预览 | ✅ 需要 |
| `uploadStatus === 'pending'` + `url` 是 HTTP | 临时远程 URL | ✅ 需要 |

---

## 5. 修复方案

### 5.1 修改 `attachmentUtils.ts`

**文件路径：** `frontend/hooks/handlers/attachmentUtils.ts`

#### 5.1.1 新增 `isUploadedToCloud` 函数

```typescript
/**
 * 检查附件是否已上传到云存储
 * 
 * 判断依据：uploadStatus === 'completed'
 */
export const isUploadedToCloud = (att: Attachment): boolean => {
  return att.uploadStatus === 'completed' && !!att.url && isHttpUrl(att.url);
};
```

#### 5.1.2 新增 `needsUpload` 函数

```typescript
/**
 * 检查附件是否需要上传到云存储
 */
export const needsUpload = (att: Attachment): boolean => {
  // 已上传完成，不需要再上传
  if (att.uploadStatus === 'completed') {
    return false;
  }
  // 其他情况都需要上传
  return true;
};
```

#### 5.1.3 修改 `isCloudStorageUrl` 函数

```typescript
/**
 * 检查 URL 是否是云存储 URL（基于 uploadStatus）
 * 
 * @deprecated 建议使用 isUploadedToCloud(attachment) 代替
 * 
 * 注意：这个函数只检查 URL 格式，不检查 uploadStatus
 * 对于完整的云存储判断，应该使用 isUploadedToCloud
 */
export const isCloudStorageUrl = (url: string | undefined): boolean => {
  // 保持向后兼容：只检查是否是 HTTP URL
  return isHttpUrl(url);
};
```

#### 5.1.4 修改 `uploadToCloudStorageSync` 函数

增加对各种 URL 类型的处理：

```typescript
export const uploadToCloudStorageSync = async (
  imageSource: string | File,
  filename?: string
): Promise<string> => {
  // 1. 判断输入类型
  const isFile = imageSource instanceof File;
  const sourceUrl = typeof imageSource === 'string' ? imageSource : '';
  
  // 2. 转换为 File 对象
  let file: File;

  if (isFile) {
    file = imageSource as File;
  } 
  else if (isBase64Url(sourceUrl)) {
    file = await base64ToFile(sourceUrl, filename || `image-${Date.now()}.png`);
  } 
  else if (isBlobUrl(sourceUrl)) {
    const response = await fetch(sourceUrl);
    const blob = await response.blob();
    file = new File([blob], filename || `image-${Date.now()}.png`, { type: blob.type });
  } 
  else if (isHttpUrl(sourceUrl)) {
    // HTTP URL（包括临时 URL）- 下载后上传
    const response = await fetch(sourceUrl);
    const blob = await response.blob();
    file = new File([blob], filename || `image-${Date.now()}.png`, { type: blob.type || 'image/png' });
  } 
  else {
    throw new Error(`不支持的图片来源格式`);
  }

  // 3. 上传到云存储
  const result = await storageUpload.uploadFile(file);
  return result.success ? result.url : '';
};
```

---

### 5.2 修改 Handler 中的上传逻辑

在各个 Handler（`imageGenHandler.ts`、`imageEditHandler.ts`、`imageExpandHandler.ts`）中，上传前应该检查 `uploadStatus`：

```typescript
// 处理原图上传
if (mode === 'image-edit' && attachments.length > 0) {
  const uploadTasks = attachments.map(async (att) => {
    // ✅ 基于 uploadStatus 判断，而不是 URL 格式
    if (att.uploadStatus === 'completed') {
      console.log('[Handler] 原图已上传，直接复用');
      return att;
    }

    // 需要上传
    const uploadSource = att.file || att.url;
    if (!uploadSource) {
      return { ...att, url: '', uploadStatus: 'failed' };
    }

    const cloudUrl = await uploadToCloudStorageSync(uploadSource, att.name);
    return {
      ...att,
      url: cloudUrl || '',
      uploadStatus: cloudUrl ? 'completed' : 'failed'
    };
  });
}
```

---

## 6. URL 类型工具函数

### 6.1 完整的工具函数列表

| 函数 | 用途 | 返回值 |
|------|------|--------|
| `isUploadedToCloud(att)` | 检查附件是否已上传到云存储 | `boolean` |
| `needsUpload(att)` | 检查附件是否需要上传 | `boolean` |
| `isHttpUrl(url)` | 检查是否是 HTTP/HTTPS URL | `boolean` |
| `isBlobUrl(url)` | 检查是否是 Blob URL | `boolean` |
| `isBase64Url(url)` | 检查是否是 Base64 URL | `boolean` |
| `cleanAttachmentsForDb(atts)` | 清理附件用于数据库存储 | `Attachment[]` |

### 6.2 使用示例

```typescript
import { isUploadedToCloud, needsUpload, uploadToCloudStorageSync } from './attachmentUtils';

// 检查是否需要上传
if (needsUpload(attachment)) {
  const cloudUrl = await uploadToCloudStorageSync(attachment.file || attachment.url, attachment.name);
  attachment.url = cloudUrl;
  attachment.uploadStatus = 'completed';
}

// 检查是否已上传
if (isUploadedToCloud(attachment)) {
  console.log('附件已在云存储，URL:', attachment.url);
}
```

---

## 7. 相关文件

| 文件路径 | 说明 |
|----------|------|
| `frontend/hooks/handlers/attachmentUtils.ts` | 附件处理工具函数 |
| `frontend/hooks/handlers/imageGenHandler.ts` | 图片生成处理器 |
| `frontend/hooks/handlers/imageEditHandler.ts` | 图片编辑处理器 |
| `frontend/hooks/handlers/imageExpandHandler.ts` | 图片扩展处理器 |
| `frontend/hooks/useChat.ts` | 聊天 Hook（协调者） |
| `frontend/components/views/ImageEditView.tsx` | 图片编辑视图 |
| `frontend/components/views/ImageExpandView.tsx` | 图片扩展视图 |
| `frontend/components/chat/InputArea.tsx` | 输入区域组件 |
| `frontend/services/providers/google/media/image-edit.ts` | Google 图片编辑 API |

---

## 8. 已完成的修复

### 8.1 `attachmentUtils.ts` 修改

1. ✅ 新增 `isUploadedToCloud(att)` 函数 - 基于 `uploadStatus` 判断
2. ✅ 新增 `needsUpload(att)` 函数 - 检查是否需要上传
3. ✅ 标记 `isCloudStorageUrl` 为 `@deprecated`
4. ✅ 增强 `uploadToCloudStorageSync` 支持所有 URL 类型

### 8.2 `imageEditHandler.ts` 修改

1. ✅ 导入改为 `needsUpload` 和 `isHttpUrl`
2. ✅ 预处理原图时，基于 `uploadStatus` 判断是否复用云 URL
3. ✅ 上传原图时，使用 `needsUpload(att)` 判断

### 8.3 `imageExpandHandler.ts` 修改

1. ✅ 导入改为 `needsUpload`
2. ✅ 使用 `needsUpload(originalAttachment)` 判断原图是否需要上传

### 8.4 修改原则

- `uploadStatus === 'completed'` 表示已上传，无需重复上传
- `uploadStatus === 'pending'` 表示待上传，需要上传
- 上传完成后更新 `uploadStatus` 为 `'completed'`

---

## 9. 测试建议

### 9.1 测试场景

1. **用户上传新图片** → 应该上传到云存储
2. **使用 AI 生成的结果图继续编辑** → 结果图应该上传，原图复用
3. **页面刷新后继续编辑** → 从数据库加载的图片（`uploadStatus: 'completed'`）应该复用
4. **CONTINUITY LOGIC** → 画布上的图片应该正确处理

### 9.2 验证方法

查看控制台日志：
- `[imageEditHandler] 原图已上传，直接复用` - 表示正确复用
- `[imageEditHandler] 上传新原图` - 表示正确上传新图片
- `[imageExpandHandler] 原图已上传，复用云存储 URL` - 表示正确复用
