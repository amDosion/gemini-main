# 统一附件处理架构设计方案

> **版本**: v1.0
> **创建日期**: 2026-01-18
> **状态**: 设计阶段
> **负责人**: 架构组

---

## 📋 目录

1. [背景与问题](#背景与问题)
2. [当前架构分析](#当前架构分析)
3. [设计目标](#设计目标)
4. [统一架构设计](#统一架构设计)
5. [API 设计规范](#api-设计规范)
6. [数据模型设计](#数据模型设计)
7. [实施计划](#实施计划)
8. [风险评估与缓解](#风险评估与缓解)
9. [监控与回滚方案](#监控与回滚方案)

---

## 背景与问题

### 1.1 问题概述

通过对 Edit 模式附件处理流程的多轮验证分析，发现当前架构存在**严重的前后端功能重复**和**效率问题**：

| 问题类型 | 具体表现 | 影响 |
|---------|---------|------|
| **功能重复** | URL 类型检测、格式转换、文件下载在前后端都有实现 | 开发成本增加 2 倍 |
| **网络浪费** | 同一图片被下载 2-3 次（前端下载 → Base64 → 后端下载） | 带宽浪费 50%+ |
| **性能损耗** | Base64 编码导致数据膨胀 33%，且需要编码/解码 | 延迟增加 2-3 秒 |
| **状态不一致** | 前端 `uploadStatus` 与后端 `upload_tasks.status` 可能不同步 | 容易出现显示错误 |
| **代码复杂** | 前端需要处理 6 种附件场景，包含大量转换逻辑 | 可维护性差 |

### 1.2 典型问题案例

#### 案例 1：HTTP URL 的无意义循环

```
原始 HTTP URL (AI 返回)
    ↓ 前端 fetch() 下载
Blob 对象
    ↓ fileToBase64() 编码
Base64 Data URL (+33% 数据量)
    ↓ POST /api/modes/google/image-chat-edit
后端接收 Base64
    ↓ base64.b64decode() 解码
二进制数据
    ↓ fetch() 下载原始 HTTP URL (再次！)
图片字节
```

**问题**：原始 HTTP URL 完全可以直接传给后端，前端的下载 → Base64 转换毫无必要。

#### 案例 2：用户上传图片的多次转换

```
用户选择文件
    ↓ File 对象
URL.createObjectURL()
    ↓ Blob URL (blob:http://localhost:3000/xxx)
fileToBase64()
    ↓ Base64 Data URL (data:image/png;base64,...)
传给后端
    ↓ base64.b64decode()
二进制数据
    ↓ 写入临时文件
Temp 文件路径
    ↓ 读取文件
二进制数据
    ↓ 上传云存储
云存储 URL
```

**问题**：File 对象可以直接通过 `multipart/form-data` 上传，无需 Blob URL → Base64 → Temp 文件的多次转换。

### 1.3 量化影响

**性能影响**（以 2MB 图片为例）：

| 指标 | 当前架构 | 统一架构 | 改善 |
|-----|---------|---------|------|
| **网络传输** | 4.67MB (下载 2MB + 上传 2.67MB Base64) | 2MB (直接上传) | **-57%** |
| **前端内存** | 4.67MB (Blob + Base64 字符串) | 0MB (不持有图片数据) | **-100%** |
| **处理延迟** | 3-5 秒 (下载 + 编码 + 上传 + 解码 + 云存储) | 1-2 秒 (直接上传云存储) | **-60%** |
| **HTTP 请求** | 3-5 个 (上传 + 轮询 + 查询状态) | 1 个 (统一上传) | **-70%** |

**代码复杂度影响**：

| 文件 | 当前行数 | 优化后行数 | 减少 |
|-----|---------|-----------|------|
| `attachmentUtils.ts` | ~1,200 行 | ~700 行 | **-42%** |
| `InputArea.tsx` | ~400 行 | ~300 行 | **-25%** |
| `ImageEditView.tsx` | ~600 行 | ~500 行 | **-17%** |

---

## 当前架构分析

### 2.1 前端附件处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Frontend)                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  InputArea.tsx                                                │
│  ├─ handleFileSelect()                                        │
│  │   └─ URL.createObjectURL(file) → Blob URL                 │
│  └─ handleSend()                                              │
│      └─ fileToBase64(file) → Base64 Data URL                 │
│                                                               │
│  attachmentUtils.ts                                           │
│  ├─ processUserAttachments()          (6 种场景处理)          │
│  │   ├─ isBlobUrl() → urlToBase64()                          │
│  │   ├─ isBase64Url() → base64ToFile()                       │
│  │   ├─ isHttpUrl() → 直接传递或下载                          │
│  │   └─ tryFetchCloudUrl() → 查询后端                         │
│  │                                                            │
│  ├─ prepareAttachmentForApi()        (CONTINUITY LOGIC)      │
│  │   ├─ findAttachmentByUrl()                                │
│  │   └─ tryFetchCloudUrl()                                   │
│  │                                                            │
│  ├─ processMediaResult()             (AI 结果处理)            │
│  │   ├─ isHttpUrl(res.url) → fetch() → Blob URL              │
│  │   └─ sourceToFile() → 上传云存储                           │
│  │                                                            │
│  ├─ sourceToFile()                   (3 层降级策略)           │
│  │   ├─ 后端代理下载                                          │
│  │   ├─ 直接下载                                              │
│  │   └─ urlToFile()                                          │
│  │                                                            │
│  └─ cleanAttachmentsForDb()          (数据库序列化)           │
│      └─ 清空 Blob/Base64 URL，保留 HTTP URL                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                           ↓ (Base64/HTTP URL)
┌─────────────────────────────────────────────────────────────┐
│                      后端 (Backend)                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  modes.py                                                     │
│  ├─ convert_attachments_to_reference_images()                │
│  │   └─ 提取 attachments 中的图片数据                          │
│  └─ provider.edit_image()                                    │
│                                                               │
│  Google Provider (simple_image_edit_service.py)               │
│  └─ _process_reference_image()                               │
│      ├─ Google File URI → 检查过期                            │
│      ├─ Base64 Data URL → 解码 → 上传 Google Files API        │
│      └─ HTTP URL → 下载 → 上传 Google Files API               │
│                                                               │
│  Tongyi Provider (image_edit.py, file_upload.py)             │
│  └─ process_reference_image()                                │
│      ├─ oss:// URL → 直接使用                                 │
│      ├─ Base64 Data URL → 解码 → 上传 DashScope OSS           │
│      └─ HTTP URL → 下载 → 上传 DashScope OSS                  │
│                                                               │
│  upload_worker_pool.py                                        │
│  └─ _process_task()                                          │
│      ├─ 读取临时文件或 URL                                     │
│      ├─ 上传云存储                                            │
│      └─ 更新数据库 (message_attachments)                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 重复处理识别

| 功能 | 前端实现 | 后端实现 | 重复性 |
|-----|---------|---------|--------|
| **URL 类型检测** | `isHttpUrl()`, `isBlobUrl()`, `isBase64Url()` | `url.startswith('http')`, `url.startswith('data:')` | ✅ 完全重复 |
| **HTTP URL 下载** | `sourceToFile()` → `fetch(url)` | `aiohttp.get(url)` / `requests.get(url)` | ✅ 完全重复 |
| **Base64 编码/解码** | `fileToBase64()`, `urlToBase64()` | `base64.b64decode()` | ✅ 循环转换 |
| **文件格式验证** | `blob.type.startsWith('image/')` | `mime_type` 检测 | ✅ 部分重复 |
| **云存储上传** | `storageUpload.uploadFileAsync()` | `StorageService.upload_file()` | ⚠️ 职责重复 |
| **附件状态管理** | `uploadStatus`, `tempUrl` | `upload_tasks.status`, `message_attachments.url` | ✅ 状态冗余 |

### 2.3 架构缺陷总结

#### ❌ 缺陷 1：前端承担了不应有的职责

**问题**：前端需要处理图片下载、格式转换、云存储上传调度，这些应该是后端的职责。

**影响**：
- 前端代码复杂度增加（`attachmentUtils.ts` 超过 1,200 行）
- 前端内存占用增加（持有 Base64 字符串）
- 网络带宽浪费（Base64 编码 +33% 数据量）

#### ❌ 缺陷 2：Base64 编码是不必要的性能杀手

**问题**：为了解决 Blob URL 生命周期问题，前端将所有图片转为 Base64，导致数据膨胀 33%。

**更好的方案**：
- 用户上传 → 直接通过 FormData 上传 File 对象（无编码）
- HTTP URL → 直接传递字符串给后端（无下载）
- Blob URL → 仅用于 UI 显示，不传给后端

#### ❌ 缺陷 3：同一图片被下载多次

**问题**：
1. 前端下载 HTTP URL → 转为 Blob/Base64
2. 后端接收 Base64 → 解码 → 再次下载 HTTP URL（Google/Tongyi 上传）

**影响**：
- 网络带宽浪费 2-3 倍
- 延迟增加 2-3 秒

#### ❌ 缺陷 4：状态管理分散且容易不一致

**问题**：
- 前端维护 `uploadStatus`（'pending' | 'uploading' | 'completed' | 'failed'）
- 后端维护 `upload_tasks.status`（'pending' | 'completed' | 'failed'）
- 数据库维护 `message_attachments.url`

**影响**：
- 前端显示 "上传完成"，但后端任务可能失败
- 跨模式传递时，状态可能不同步

---

## 设计目标

### 3.1 核心原则

#### ✅ 前端职责清晰化

**前端应该做的**：
- 用户交互（文件选择、拖拽上传）
- UI 显示（图片预览、加载状态）
- 表单提交（通过 FormData 上传 File）
- **即时显示**（AI 返回的原始 URL，无延迟）

**前端不应该做的**：
- 图片下载和格式转换（用于上传到云存储的目的）
- Base64 编码/解码（用于传输的目的）
- 云存储上传调度
- 附件状态同步

#### ✅ 后端统一处理图片

**后端应该做的**：
- 接收所有类型的图片来源（File / HTTP URL / Base64）
- 统一下载、验证、转换
- 统一上传到云存储
- 统一管理附件状态

#### ✅ 双 URL 显示机制（保留当前优秀设计）

**重要发现**：当前系统的双 URL 机制是一个**优秀的用户体验设计**，应该保留：

```typescript
// 场景 1：页面未重载 - 立即显示（无延迟）
// AI 返回 Base64 或临时 HTTP URL → 前端立即显示
displayAttachment = {
  url: "data:image/png;base64,..."  // Google: Base64（立即可见）
  // 或
  url: "blob:http://localhost:3000/xxx"  // 通义: Blob URL（立即可见）
};

// 后台异步上传到云存储（不阻塞 UI）
const cloudUrl = await uploadToCloudStorage(displayUrl);

// 场景 2：页面重载后 - 显示持久化 URL
// 从数据库读取云存储 URL
displayAttachment = {
  url: "https://storage.example.com/xxx.png"  // 云存储 URL（永久有效）
};
```

**设计原则**：
- ✅ **即时显示优先**：AI 返回结果立即显示（Base64 / Blob URL），无需等待云存储上传
- ✅ **后台异步上传**：上传到云存储在后台进行，不阻塞用户操作
- ✅ **持久化存储**：数据库只存储云存储 URL（`url` 字段），不存储临时 URL
- ✅ **智能降级**：页面重载后，显示云存储 URL；如果云存储上传失败，显示占位符

### 3.2 性能目标

| 指标 | 当前值 | 目标值 | 改善幅度 |
|-----|-------|-------|---------|
| **网络传输** | 4.67MB | 2MB | -57% |
| **处理延迟** | 3-5 秒 | 1-2 秒 | -60% |
| **HTTP 请求** | 3-5 个 | 1 个 | -70% |
| **前端代码** | 1,200 行 | 700 行 | -42% |
| **前端内存** | 4.67MB | 0MB | -100% |

### 3.3 架构目标

1. **简化前端**：移除所有 URL 转换函数，前端只负责 UI
2. **统一后端**：所有图片处理逻辑集中在后端
3. **提升性能**：减少网络传输和延迟
4. **降低复杂度**：减少前后端状态同步问题

---

## 统一架构设计

### 4.1 新架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Frontend)                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  InputArea.tsx                                                │
│  ├─ handleFileSelect()                                        │
│  │   └─ 显示 Blob URL 预览 (不上传)                           │
│  └─ handleSend()                                              │
│      └─ FormData.append('file', file)  → 直接上传              │
│                                                               │
│  attachmentUtils.ts (简化版)                                  │
│  ├─ uploadAttachment(source)          (统一上传函数)           │
│  │   └─ POST /api/attachments/prepare                        │
│  │                                                            │
│  ├─ getAttachmentUrl(attachmentId)    (查询云 URL)            │
│  │   └─ GET /api/attachments/{id}                            │
│  │                                                            │
│  └─ cleanAttachmentsForDb()           (简化为只保留 ID)        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                           ↓ (File/URL/attachmentId)
┌─────────────────────────────────────────────────────────────┐
│                      后端 (Backend)                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  storage.py (新增统一接口)                                     │
│  └─ POST /api/attachments/prepare                            │
│      ├─ 接收 File (multipart/form-data)                       │
│      ├─ 接收 URL (JSON: {"url": "http://..."})                │
│      ├─ 接收 attachmentId (JSON: {"attachmentId": "..."})     │
│      └─ 返回: {"attachmentId": "...", "url": "...", "status"}│
│                                                               │
│  attachment_processor.py (新增核心处理器)                      │
│  └─ class UnifiedAttachmentProcessor                          │
│      ├─ process_file(file) → upload_to_cloud()               │
│      ├─ process_url(url)                                     │
│      │   ├─ HTTP URL → download() → upload_to_cloud()        │
│      │   └─ Base64 URL → decode() → upload_to_cloud()        │
│      ├─ process_attachment_id(id) → query_db()               │
│      └─ upload_to_cloud(bytes, metadata)                     │
│          ├─ 选择存储后端 (S3 / GCS / OSS)                     │
│          ├─ 上传文件                                          │
│          └─ 返回永久 URL                                       │
│                                                               │
│  modes.py (简化)                                              │
│  └─ handle_mode()                                            │
│      └─ 直接使用 attachment.url (已经是云 URL)                 │
│                                                               │
│  Google/Tongyi Provider (简化)                                │
│  └─ edit_image()                                             │
│      └─ 直接使用云 URL，无需下载 (Google Files API 可选)       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 核心变更点

#### 变更 1：新增统一附件处理接口

**接口**：`POST /api/attachments/prepare`

**功能**：
- 接收任意类型的图片来源（File / HTTP URL / Base64 / attachmentId）
- 统一下载、验证、上传到云存储
- 返回云存储 URL 和附件 ID

**优势**：
- 前端只需调用一个接口，无需关心图片处理细节
- 后端统一处理，避免重复逻辑
- 支持缓存，避免重复下载

#### 变更 2：移除前端 Base64 转换

**移除函数**：
- `urlToBase64()` - ❌ 删除
- `fileToBase64()` - ❌ 删除
- `sourceToFile()` - ❌ 删除（部分保留，仅用于 Blob URL 预览）

**保留函数**：
- `isHttpUrl()` - ✅ 保留（基本验证）
- `uploadAttachment()` - ✅ 新增（调用后端 API）

#### 变更 3：废弃临时 URL 字段

**废弃字段**：
- `tempUrl` - ❌ 删除
- `base64Data` - ❌ 删除

**权威字段**：
- `url` - ✅ 云存储 URL（永久有效）
- `uploadStatus` - ✅ 上传状态
- `attachmentId` - ✅ 附件唯一标识

#### 变更 4：后端统一图片下载

**实现**：
- 新增 `UnifiedAttachmentProcessor` 类
- 统一处理 HTTP URL 下载（避免前后端重复下载）
- 支持重试和缓存（Redis）

### 4.3 双 URL 显示机制完整流程

**重要说明**：当前系统的双 URL 机制是一个优秀的用户体验设计，统一架构需要**保留**这个机制。

#### 流程 1：AI 生成图片后的即时显示（无延迟）

```
用户发送编辑请求
    ↓
后端调用 AI API (Google/通义)
    ↓
AI 返回结果
    ├─ Google: Base64 Data URL (data:image/png;base64,...)
    └─ 通义: HTTP 临时 URL (https://dashscope.oss-cn-xxx...)
    ↓
前端接收响应
    ↓
创建 displayAttachment (立即显示，无需等待上传)
{
  id: "att-12345678",
  url: "data:image/png;base64,..."  // 或 Blob URL (通义)
  uploadStatus: "pending",
  _displayUrl: "data:image/png;base64,..."  // 保存原始 URL
}
    ↓
UI 立即显示图片 <img src={attachment.url} />
    ↓
后台异步上传到云存储（不阻塞 UI）
{
  // processMediaResult() 内部
  const dbAttachmentPromise = (async () => {
    const file = await sourceToFile(res.url);  // Base64/HTTP → File
    const result = await storageUpload.uploadFileAsync(file);
    return { ...attachment, url: cloudUrl, uploadStatus: 'completed' };
  })();
}
    ↓
上传完成后，更新 attachment.url
{
  id: "att-12345678",
  url: "https://storage.example.com/xxx.png",  // 替换为云 URL
  uploadStatus: "completed",
  _displayUrl: undefined  // 清空临时字段
}
    ↓
UI 自动切换到云存储 URL（图片无闪烁）
```

**关键点**：
- ✅ **立即显示**：AI 返回后，前端立即显示 Base64/Blob URL，用户无需等待
- ✅ **后台上传**：上传到云存储在后台异步进行，不阻塞用户操作
- ✅ **无缝切换**：上传完成后，`url` 字段从临时 URL 切换到云 URL，UI 自动更新

#### 流程 2：用户上传图片的即时预览

```
用户选择文件
    ↓
InputArea.handleFileSelect()
{
  const file = files[0];
  const blobUrl = URL.createObjectURL(file);  // 创建 Blob URL

  const attachment = {
    id: uuidv4(),
    url: blobUrl,  // 立即显示
    file: file,
    uploadStatus: 'pending',
    _displayUrl: blobUrl
  };

  setAttachments([...attachments, attachment]);
}
    ↓
UI 立即显示预览 <img src={blobUrl} />
    ↓
用户点击发送
    ↓
后端上传（优化：直接 FormData，无需 Base64）
{
  const formData = new FormData();
  formData.append('file', attachment.file);

  const response = await fetch('/api/attachments/prepare', {
    method: 'POST',
    body: formData
  });

  const { attachmentId, url } = await response.json();
}
    ↓
更新 attachment.url 为云 URL
{
  id: attachmentId,
  url: "https://storage.example.com/xxx.png",  // 云 URL
  uploadStatus: 'completed',
  _displayUrl: undefined  // 清空
}
    ↓
清理 Blob URL（释放内存）
URL.revokeObjectURL(blobUrl);
```

**关键点**：
- ✅ **即时预览**：用户选择文件后，立即显示 Blob URL 预览
- ✅ **直接上传**：使用 FormData 直接上传 File，无需 Base64 转换
- ✅ **内存清理**：上传完成后，释放 Blob URL 内存

#### 流程 3：页面重载后的显示（从数据库读取）

```
用户刷新页面
    ↓
前端加载历史消息
    ↓
从后端获取消息列表
GET /api/sessions/{sessionId}/messages
    ↓
后端查询数据库
SELECT * FROM messages WHERE session_id = ...
JOIN message_attachments ON messages.id = message_attachments.message_id
    ↓
返回消息 + 附件
{
  "messages": [{
    "id": "msg-xxx",
    "attachments": [{
      "id": "att-12345678",
      "url": "https://storage.example.com/xxx.png",  // 云 URL（永久有效）
      "uploadStatus": "completed",
      "mimeType": "image/png",
      "size": 2048576
    }]
  }]
}
    ↓
前端渲染消息
{
  // attachment.url 已经是云存储 URL
  // 无需任何转换，直接显示
  <img src={attachment.url} />
}
```

**关键点**：
- ✅ **持久化存储**：数据库只存储云存储 URL，不存储临时 URL
- ✅ **无需转换**：页面重载后，直接显示云 URL，无需额外处理
- ✅ **长期有效**：云存储 URL 永久有效（或长期有效，如 1 年）

#### 数据库存储策略

```typescript
/**
 * cleanAttachmentsForDb() - 数据库序列化前的清理
 */
export const cleanAttachmentsForDb = (atts: Attachment[]): Attachment[] => {
  return atts.map(att => {
    const cleaned = { ...att };

    // 1. 只保留云存储 URL
    if (att.uploadStatus === 'completed' && isHttpUrl(att.url)) {
      cleaned.url = att.url;  // 云存储 URL
    } else {
      cleaned.url = '';  // 上传未完成，清空
    }

    // 2. 删除临时字段
    delete cleaned.file;
    delete cleaned._displayUrl;

    // 3. 删除废弃字段（兼容期）
    delete cleaned.tempUrl;
    delete cleaned.base64Data;

    return cleaned;
  });
};
```

**存储规则**：

| URL 类型 | uploadStatus | 存储到数据库 | 理由 |
|---------|-------------|------------|------|
| 云存储 URL | completed | ✅ 保留 | 永久有效 |
| Base64 URL | pending | ❌ 清空 | 数据过大（>1MB） |
| Blob URL | pending | ❌ 清空 | 页面关闭后失效 |
| HTTP 临时 URL | pending | ❌ 清空 | 可能过期（48 小时） |

#### 智能降级策略

```typescript
/**
 * 显示附件时的降级策略
 */
function getDisplayUrl(attachment: Attachment): string {
  // 优先级 1: 云存储 URL（永久有效）
  if (attachment.uploadStatus === 'completed' && isHttpUrl(attachment.url)) {
    return attachment.url;
  }

  // 优先级 2: 临时显示 URL（Base64/Blob）
  if (attachment._displayUrl) {
    return attachment._displayUrl;
  }

  // 优先级 3: url 字段（可能是 Base64/Blob）
  if (attachment.url) {
    return attachment.url;
  }

  // 优先级 4: 占位符（上传失败或 URL 过期）
  return '/placeholder.png';
}
```

### 4.4 优化后的性能对比

#### 当前架构 vs 统一架构（保留双 URL）

| 场景 | 当前架构 | 统一架构（优化） | 改善 |
|-----|---------|----------------|------|
| **AI 返回显示延迟** | 0 秒（立即显示 Base64） | 0 秒（立即显示 Base64） | 相同 |
| **用户上传预览延迟** | 0 秒（立即显示 Blob URL） | 0 秒（立即显示 Blob URL） | 相同 |
| **云存储上传时间** | 2-3 秒（Base64 → 云存储） | 1-2 秒（直接上传，无 Base64） | **-50%** |
| **网络传输** | 4.67MB（Base64 +33%） | 2MB（直接上传 File） | **-57%** |
| **页面重载显示** | 正常（云 URL） | 正常（云 URL） | 相同 |

**结论**：
- ✅ **保留用户体验**：即时显示能力不变（0 秒延迟）
- ✅ **优化后台上传**：减少 50% 上传时间和 57% 网络传输
- ✅ **保持功能完整**：页面重载后仍正常显示

---

## API 设计规范

### 5.1 统一附件上传接口

#### 接口定义

```
POST /api/attachments/prepare
Content-Type: multipart/form-data 或 application/json
```

#### 请求格式（3 种模式）

**模式 1：上传 File 对象**

```http
POST /api/attachments/prepare
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="file"; filename="image.png"
Content-Type: image/png

<binary data>
--boundary--
```

**模式 2：传递 HTTP URL 或 Base64**

```http
POST /api/attachments/prepare
Content-Type: application/json

{
  "url": "https://example.com/image.png"
}
```

或

```http
POST /api/attachments/prepare
Content-Type: application/json

{
  "url": "data:image/png;base64,iVBORw0KGgo..."
}
```

**模式 3：复用已有附件**

```http
POST /api/attachments/prepare
Content-Type: application/json

{
  "attachmentId": "att-12345678"
}
```

#### 响应格式

**成功响应**：

```json
{
  "success": true,
  "data": {
    "attachmentId": "att-12345678",
    "url": "https://storage.example.com/images/xxx.png",
    "uploadStatus": "completed",
    "mimeType": "image/png",
    "size": 2048576,
    "uploadedAt": "2026-01-18T10:30:00Z"
  }
}
```

**异步上传响应**（文件过大时）：

```json
{
  "success": true,
  "data": {
    "attachmentId": "att-12345678",
    "url": "",
    "uploadStatus": "pending",
    "taskId": "task-87654321"
  }
}
```

**错误响应**：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_FILE_TYPE",
    "message": "不支持的文件格式，仅支持 JPEG, PNG, WebP",
    "details": {
      "mimeType": "image/gif"
    }
  }
}
```

#### 错误码定义

| 错误码 | HTTP 状态码 | 说明 |
|-------|-----------|------|
| `INVALID_FILE_TYPE` | 400 | 不支持的文件格式 |
| `FILE_TOO_LARGE` | 413 | 文件大小超过限制 (5MB) |
| `DOWNLOAD_FAILED` | 502 | 下载 HTTP URL 失败 |
| `UPLOAD_FAILED` | 500 | 上传到云存储失败 |
| `ATTACHMENT_NOT_FOUND` | 404 | 附件 ID 不存在 |

### 5.2 附件状态查询接口

#### 接口定义

```
GET /api/attachments/{attachmentId}
```

#### 响应格式

```json
{
  "success": true,
  "data": {
    "attachmentId": "att-12345678",
    "url": "https://storage.example.com/images/xxx.png",
    "uploadStatus": "completed",
    "mimeType": "image/png",
    "size": 2048576,
    "uploadedAt": "2026-01-18T10:30:00Z"
  }
}
```

### 5.3 批量查询接口

#### 接口定义

```
GET /api/attachments?ids=att-111,att-222,att-333
```

#### 响应格式

```json
{
  "success": true,
  "data": [
    {
      "attachmentId": "att-111",
      "url": "https://storage.example.com/images/111.png",
      "uploadStatus": "completed"
    },
    {
      "attachmentId": "att-222",
      "url": "",
      "uploadStatus": "pending",
      "taskId": "task-222"
    },
    {
      "attachmentId": "att-333",
      "url": "",
      "uploadStatus": "failed",
      "error": "上传超时"
    }
  ]
}
```

---

## 数据模型设计

### 6.1 前端 Attachment 模型（优化版）

**TypeScript 定义**：

```typescript
interface Attachment {
  // ===== 必需字段 =====
  id: string;                          // 附件唯一标识 (att-xxx)
  mimeType: string;                    // MIME 类型 (image/png)
  name: string;                        // 文件名

  // ===== 核心字段：智能 URL 切换 =====
  url: string;                         // 显示 URL（智能切换）
                                       // - AI 返回后：Base64 / Blob URL（立即显示）
                                       // - 上传完成后：云存储 URL（持久化）
                                       // - 页面重载后：云存储 URL（从数据库读取）

  uploadStatus: 'pending' | 'completed' | 'failed';

  // ===== 可选字段 =====
  size?: number;                       // 文件大小 (字节)
  uploadTaskId?: string;               // 异步上传任务 ID
  uploadedAt?: string;                 // 上传完成时间 (ISO 8601)
  error?: string;                      // 错误信息

  // ===== 前端临时字段（不存储到数据库）=====
  file?: File;                         // 原始 File 对象 (仅用于上传)
  _displayUrl?: string;                // 内部字段：原始显示 URL（Base64/Blob）
                                       // 用于在云存储上传完成前显示
}
```

**字段说明**：

| 字段 | 用途 | 生命周期 | 持久化 |
|-----|------|---------|-------|
| `id` | 附件唯一标识 | 永久 | ✅ 数据库 |
| `url` | **智能显示 URL** | 动态切换 | ✅ 数据库（仅云 URL） |
| `uploadStatus` | 上传状态 | 永久 | ✅ 数据库 |
| `file` | 原始 File 对象 | 临时（上传前） | ❌ 不存储 |
| `_displayUrl` | 原始显示 URL（Base64/Blob） | 临时（UI 显示） | ❌ 不存储 |

**url 字段的智能切换逻辑**：

```typescript
/**
 * url 字段在不同阶段的值
 */

// 阶段 1：AI 返回结果（立即显示）
attachment.url = "data:image/png;base64,..."  // Google: Base64
// 或
attachment.url = "blob:http://localhost:3000/xxx"  // 通义: Blob URL
attachment.uploadStatus = 'pending';

// 阶段 2：后台上传完成（替换为云 URL）
attachment.url = "https://storage.example.com/xxx.png"  // 云存储 URL
attachment.uploadStatus = 'completed';

// 阶段 3：页面重载（从数据库读取）
// 数据库中只存储云 URL
attachment.url = "https://storage.example.com/xxx.png"
attachment.uploadStatus = 'completed';
```

**废弃字段**（向后兼容 3 个月）：

```typescript
interface DeprecatedAttachment {
  tempUrl?: string;        // ❌ 废弃，合并到 url 字段
  base64Data?: string;     // ❌ 废弃，合并到 url 字段
  googleFileUri?: string;  // ❌ 废弃，后端自动管理
  googleFileExpiry?: number; // ❌ 废弃
}
```

**兼容层（保留 3 个月）**：

```typescript
/**
 * 读取附件时的兼容逻辑
 */
function getDisplayUrl(att: Attachment): string {
  // 优先使用新字段
  if (att.url) {
    return att.url;
  }

  // 兼容旧字段（显示警告）
  if (att.tempUrl) {
    console.warn(`[Deprecated] 使用了废弃字段 tempUrl: ${att.id}`);
    return att.tempUrl;
  }

  if (att.base64Data) {
    console.warn(`[Deprecated] 使用了废弃字段 base64Data: ${att.id}`);
    return att.base64Data;
  }

  // 占位符
  return '/placeholder.png';
}
```

### 6.2 后端数据库模型

#### message_attachments 表（简化版）

```sql
CREATE TABLE message_attachments (
    id VARCHAR(36) PRIMARY KEY,              -- 附件 ID (att-xxx)
    message_id VARCHAR(36) NOT NULL,          -- 关联消息 ID
    session_id VARCHAR(36) NOT NULL,          -- 关联会话 ID

    -- 文件信息
    url TEXT NOT NULL,                        -- 云存储 URL (权威)
    mime_type VARCHAR(100) NOT NULL,          -- MIME 类型
    name VARCHAR(255) NOT NULL,               -- 文件名
    size BIGINT,                              -- 文件大小 (字节)

    -- 上传状态
    upload_status VARCHAR(20) DEFAULT 'pending', -- pending/completed/failed
    upload_task_id VARCHAR(36),               -- 异步任务 ID
    uploaded_at TIMESTAMP,                    -- 上传完成时间
    error TEXT,                               -- 错误信息

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- 索引
    INDEX idx_message_id (message_id),
    INDEX idx_session_id (session_id),
    INDEX idx_upload_status (upload_status),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);
```

**字段变更**：

| 字段 | 状态 | 说明 |
|-----|------|------|
| `url` | ✅ 保留 | 改为存储云存储 URL（永久有效） |
| `temp_url` | ❌ 删除 | 不再需要临时 URL |
| `base64_data` | ❌ 删除 | 不再存储 Base64 |
| `google_file_uri` | ❌ 删除 | 后端内部管理，不存储 |
| `google_file_expiry` | ❌ 删除 | 后端内部管理 |

#### upload_tasks 表（保留，用于异步上传）

```sql
CREATE TABLE upload_tasks (
    id VARCHAR(36) PRIMARY KEY,
    attachment_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,

    -- 任务状态
    status VARCHAR(20) DEFAULT 'pending',
    progress INT DEFAULT 0,              -- 进度 (0-100)

    -- 文件来源
    source_file_path TEXT,               -- 临时文件路径
    source_url TEXT,                     -- 源 URL

    -- 结果
    result_url TEXT,                     -- 云存储 URL
    error_message TEXT,

    -- 重试
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_attachment_id (attachment_id)
);
```

### 6.3 后端核心类设计

#### UnifiedAttachmentProcessor 类

```python
from typing import Union, Optional, Dict, Any
from fastapi import UploadFile
import aiohttp
import base64
from io import BytesIO

class UnifiedAttachmentProcessor:
    """统一附件处理器"""

    def __init__(
        self,
        storage_service: StorageService,
        cache_service: Optional[CacheService] = None,
        max_file_size: int = 5 * 1024 * 1024  # 5MB
    ):
        self.storage = storage_service
        self.cache = cache_service
        self.max_file_size = max_file_size
        self.supported_mime_types = {'image/jpeg', 'image/png', 'image/webp'}

    async def process(
        self,
        source: Union[UploadFile, str, dict],
        session_id: str,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        统一处理附件

        Args:
            source: File 对象 / URL 字符串 / {"attachmentId": "..."} 字典
            session_id: 会话 ID
            message_id: 消息 ID (可选)

        Returns:
            {
                "attachmentId": "att-xxx",
                "url": "https://...",
                "uploadStatus": "completed",
                "mimeType": "image/png",
                "size": 2048576
            }
        """

        # 场景 1: File 对象
        if isinstance(source, UploadFile):
            return await self._process_file(source, session_id, message_id)

        # 场景 2: URL 字符串
        if isinstance(source, str):
            return await self._process_url(source, session_id, message_id)

        # 场景 3: 附件 ID 字典
        if isinstance(source, dict) and 'attachmentId' in source:
            return await self._process_attachment_id(
                source['attachmentId'], session_id
            )

        raise ValueError(f"不支持的 source 类型: {type(source)}")

    async def _process_file(
        self,
        file: UploadFile,
        session_id: str,
        message_id: Optional[str]
    ) -> Dict[str, Any]:
        """处理 File 对象"""

        # 1. 验证 MIME 类型
        if file.content_type not in self.supported_mime_types:
            raise ValueError(
                f"不支持的文件格式: {file.content_type}。"
                f"仅支持: {', '.join(self.supported_mime_types)}"
            )

        # 2. 读取文件内容
        file_bytes = await file.read()
        file_size = len(file_bytes)

        # 3. 验证文件大小
        if file_size > self.max_file_size:
            raise ValueError(
                f"文件大小超过限制: {file_size / 1024 / 1024:.2f}MB "
                f"(最大 {self.max_file_size / 1024 / 1024}MB)"
            )

        # 4. 上传到云存储
        attachment_id = f"att-{uuid.uuid4().hex[:12]}"
        cloud_url = await self.storage.upload_file(
            file_data=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            metadata={
                'session_id': session_id,
                'message_id': message_id,
                'attachment_id': attachment_id
            }
        )

        # 5. 保存到数据库
        attachment = await self._save_to_db(
            attachment_id=attachment_id,
            session_id=session_id,
            message_id=message_id,
            url=cloud_url,
            mime_type=file.content_type,
            name=file.filename,
            size=file_size,
            upload_status='completed'
        )

        return {
            'attachmentId': attachment_id,
            'url': cloud_url,
            'uploadStatus': 'completed',
            'mimeType': file.content_type,
            'size': file_size,
            'uploadedAt': attachment.uploaded_at.isoformat()
        }

    async def _process_url(
        self,
        url: str,
        session_id: str,
        message_id: Optional[str]
    ) -> Dict[str, Any]:
        """处理 URL 字符串（HTTP 或 Base64）"""

        # 场景 1: Base64 Data URL
        if url.startswith('data:'):
            return await self._process_base64_url(url, session_id, message_id)

        # 场景 2: HTTP/HTTPS URL
        if url.startswith('http'):
            return await self._process_http_url(url, session_id, message_id)

        raise ValueError(f"不支持的 URL 格式: {url[:50]}...")

    async def _process_base64_url(
        self,
        data_url: str,
        session_id: str,
        message_id: Optional[str]
    ) -> Dict[str, Any]:
        """处理 Base64 Data URL"""

        # 1. 解析 Data URL
        match = re.match(r'^data:([^;]+);base64,(.+)$', data_url)
        if not match:
            raise ValueError("无效的 Base64 Data URL 格式")

        mime_type, base64_str = match.groups()

        # 2. 验证 MIME 类型
        if mime_type not in self.supported_mime_types:
            raise ValueError(f"不支持的文件格式: {mime_type}")

        # 3. 解码 Base64
        try:
            image_bytes = base64.b64decode(base64_str)
        except Exception as e:
            raise ValueError(f"Base64 解码失败: {e}")

        # 4. 验证文件大小
        file_size = len(image_bytes)
        if file_size > self.max_file_size:
            raise ValueError(f"文件大小超过限制: {file_size / 1024 / 1024:.2f}MB")

        # 5. 上传到云存储
        attachment_id = f"att-{uuid.uuid4().hex[:12]}"
        filename = f"image-{int(time.time())}.{mime_type.split('/')[-1]}"
        cloud_url = await self.storage.upload_file(
            file_data=image_bytes,
            filename=filename,
            mime_type=mime_type,
            metadata={
                'session_id': session_id,
                'message_id': message_id,
                'attachment_id': attachment_id
            }
        )

        # 6. 保存到数据库
        await self._save_to_db(
            attachment_id=attachment_id,
            session_id=session_id,
            message_id=message_id,
            url=cloud_url,
            mime_type=mime_type,
            name=filename,
            size=file_size,
            upload_status='completed'
        )

        return {
            'attachmentId': attachment_id,
            'url': cloud_url,
            'uploadStatus': 'completed',
            'mimeType': mime_type,
            'size': file_size
        }

    async def _process_http_url(
        self,
        http_url: str,
        session_id: str,
        message_id: Optional[str]
    ) -> Dict[str, Any]:
        """处理 HTTP/HTTPS URL（带缓存）"""

        # 1. 检查缓存
        if self.cache:
            cached = await self.cache.get(f"attachment:url:{http_url}")
            if cached:
                return cached

        # 2. 下载图片
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(http_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        raise ValueError(f"HTTP 下载失败: {response.status}")

                    image_bytes = await response.read()
                    mime_type = response.headers.get('Content-Type', 'image/png')
        except Exception as e:
            raise ValueError(f"下载 HTTP URL 失败: {e}")

        # 3. 验证 MIME 类型和大小
        if mime_type not in self.supported_mime_types:
            raise ValueError(f"不支持的文件格式: {mime_type}")

        file_size = len(image_bytes)
        if file_size > self.max_file_size:
            raise ValueError(f"文件大小超过限制: {file_size / 1024 / 1024:.2f}MB")

        # 4. 上传到云存储
        attachment_id = f"att-{uuid.uuid4().hex[:12]}"
        filename = http_url.split('/')[-1].split('?')[0] or f"image-{int(time.time())}.png"
        cloud_url = await self.storage.upload_file(
            file_data=image_bytes,
            filename=filename,
            mime_type=mime_type,
            metadata={
                'session_id': session_id,
                'message_id': message_id,
                'attachment_id': attachment_id,
                'source_url': http_url
            }
        )

        # 5. 保存到数据库
        await self._save_to_db(
            attachment_id=attachment_id,
            session_id=session_id,
            message_id=message_id,
            url=cloud_url,
            mime_type=mime_type,
            name=filename,
            size=file_size,
            upload_status='completed'
        )

        # 6. 缓存结果（1 小时）
        result = {
            'attachmentId': attachment_id,
            'url': cloud_url,
            'uploadStatus': 'completed',
            'mimeType': mime_type,
            'size': file_size
        }

        if self.cache:
            await self.cache.set(f"attachment:url:{http_url}", result, ttl=3600)

        return result

    async def _process_attachment_id(
        self,
        attachment_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """处理已有附件 ID（从数据库查询）"""

        # 1. 从数据库查询
        attachment = await db.query(MessageAttachment).filter(
            MessageAttachment.id == attachment_id,
            MessageAttachment.session_id == session_id
        ).first()

        if not attachment:
            raise ValueError(f"附件不存在: {attachment_id}")

        # 2. 返回附件信息
        return {
            'attachmentId': attachment.id,
            'url': attachment.url,
            'uploadStatus': attachment.upload_status,
            'mimeType': attachment.mime_type,
            'size': attachment.size,
            'uploadedAt': attachment.uploaded_at.isoformat() if attachment.uploaded_at else None
        }

    async def _save_to_db(
        self,
        attachment_id: str,
        session_id: str,
        message_id: Optional[str],
        url: str,
        mime_type: str,
        name: str,
        size: int,
        upload_status: str
    ) -> MessageAttachment:
        """保存附件到数据库"""

        attachment = MessageAttachment(
            id=attachment_id,
            session_id=session_id,
            message_id=message_id,
            url=url,
            mime_type=mime_type,
            name=name,
            size=size,
            upload_status=upload_status,
            uploaded_at=datetime.utcnow() if upload_status == 'completed' else None
        )

        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)

        return attachment
```

---

## 实施计划

### 7.1 分阶段实施

#### 阶段 1：后端统一接口开发（Week 1）

**任务**：
- [ ] 创建 `UnifiedAttachmentProcessor` 类
- [ ] 新增 `POST /api/attachments/prepare` 接口
- [ ] 新增 `GET /api/attachments/{id}` 接口
- [ ] 新增 `GET /api/attachments?ids=...` 批量查询接口
- [ ] 添加单元测试（File / HTTP URL / Base64 / attachmentId）
- [ ] 添加集成测试（端到端上传流程）

**交付物**：
- `backend/app/services/attachment_processor.py`
- `backend/app/routers/storage/storage.py` (更新)
- 测试覆盖率 ≥ 90%

**风险**：
- 文件上传并发测试（模拟 100 个用户同时上传）
- HTTP URL 下载超时处理

#### 阶段 2：前端调用后端接口（Week 2）

**任务**：
- [ ] 创建 `uploadAttachment()` 函数（调用后端 API）
- [ ] 更新 `InputArea.tsx` - 使用 FormData 上传 File
- [ ] 更新 `ImageEditView.tsx` - 传递 attachmentId 或 HTTP URL
- [ ] 更新 `processUserAttachments()` - 移除 Base64 转换
- [ ] 添加前端单元测试

**交付物**：
- `frontend/hooks/handlers/attachmentUtils.ts` (简化版)
- `frontend/components/chat/InputArea.tsx` (更新)
- 测试覆盖率 ≥ 80%

**风险**：
- Blob URL 预览显示可能延迟（等待后端上传）
- 缓解：使用 Blob URL 临时显示，后端返回后替换

#### 阶段 3：废弃旧字段和逻辑（Week 3）

**任务**：
- [ ] 标记 `tempUrl`, `base64Data` 为 `@deprecated`
- [ ] 添加兼容层（读取旧字段但显示警告）
- [ ] 更新 `cleanAttachmentsForDb()` - 只保留 `id` 和 `url`
- [ ] 数据库迁移脚本（清理旧数据）

**交付物**：
- 数据库迁移脚本 `migrations/remove_deprecated_fields.sql`
- 兼容层代码（3 个月后删除）

**风险**：
- 旧数据无法显示
- 缓解：兼容层保留 3 个月，逐步迁移

#### 阶段 4：性能优化（Week 4）

**任务**：
- [ ] 添加 Redis 缓存（HTTP URL → 云 URL 映射）
- [ ] 实现批量上传接口（减少 HTTP 请求）
- [ ] 优化云存储上传（支持分片上传）
- [ ] 添加性能监控（延迟、成功率、缓存命中率）

**交付物**：
- Redis 缓存配置
- 性能监控看板（Grafana）

**风险**：
- 缓存过期导致重复下载
- 缓解：设置合理的 TTL（1 小时）

### 7.2 时间表

```
Week 1: 后端统一接口开发
├─ Day 1-2: UnifiedAttachmentProcessor 类开发
├─ Day 3-4: API 接口实现
└─ Day 5:   单元测试 + 集成测试

Week 2: 前端调用后端接口
├─ Day 1-2: uploadAttachment() 函数开发
├─ Day 3-4: 更新前端组件（InputArea, ImageEditView）
└─ Day 5:   前端单元测试

Week 3: 废弃旧字段和逻辑
├─ Day 1-2: 标记废弃字段 + 兼容层
├─ Day 3-4: 数据库迁移脚本
└─ Day 5:   回归测试

Week 4: 性能优化
├─ Day 1-2: Redis 缓存实现
├─ Day 3-4: 批量上传接口
└─ Day 5:   性能测试 + 监控部署
```

### 7.3 成功标准

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|-------|-------|---------|
| **网络传输** | 4.67MB | ≤ 2.5MB | 减少 50%+ |
| **处理延迟** | 3-5 秒 | ≤ 2 秒 | 减少 60%+ |
| **HTTP 请求** | 3-5 个 | ≤ 2 个 | 减少 60%+ |
| **前端代码** | 1,200 行 | ≤ 800 行 | 减少 30%+ |
| **错误率** | 5% | ≤ 2% | 提升可靠性 |

---

## 风险评估与缓解

### 8.1 技术风险

#### 风险 1：后端负载增加

**描述**：所有图片下载和处理都在后端执行，可能导致 CPU、内存、带宽占用增加。

**影响**：
- 后端服务器资源不足
- 响应延迟增加
- 并发能力下降

**缓解方案**：
1. **Redis 缓存**：缓存 HTTP URL → 云 URL 映射（1 小时 TTL）
2. **限流**：单用户每分钟最多上传 10 个附件
3. **异步处理**：文件 > 1MB 使用异步上传（upload_tasks）
4. **水平扩展**：增加后端服务器数量

**优先级**：🔴 高

#### 风险 2：用户体验变差（等待上传）

**描述**：用户上传图片后，需要等待后端处理才能看到预览。

**影响**：
- 用户感觉系统变慢
- 可能误认为上传失败

**缓解方案**：
1. **前端 Blob URL 临时预览**：
   ```typescript
   // 用户上传后立即显示 Blob URL
   const previewUrl = URL.createObjectURL(file);
   setPreviewImage(previewUrl);

   // 后端上传完成后替换为云 URL
   const { url } = await uploadAttachment(file);
   setPreviewImage(url);
   URL.revokeObjectURL(previewUrl);  // 释放内存
   ```

2. **进度条显示**：显示上传进度（0-100%）

3. **乐观更新**：假设上传成功，失败时回滚

**优先级**：🟡 中

#### 风险 3：HTTP URL 下载失败

**描述**：后端下载 HTTP URL 可能因为网络超时、404 错误等失败。

**影响**：
- 附件处理失败
- 用户无法继续编辑

**缓解方案**：
1. **重试机制**：指数退避重试（3 次）
2. **超时控制**：30 秒超时
3. **降级方案**：如果下载失败，提示用户重新上传
4. **错误日志**：记录详细的错误信息（URL、HTTP 状态码）

**优先级**：🟡 中

### 8.2 兼容性风险

#### 风险 1：旧数据无法显示

**描述**：现有数据库中的附件使用 `tempUrl` 和 `base64Data`，新架构无法识别。

**影响**：
- 历史消息中的图片无法显示
- 用户投诉

**缓解方案**：
1. **数据库迁移脚本**：
   ```sql
   -- 查找所有使用 tempUrl 的附件
   SELECT id, temp_url FROM message_attachments
   WHERE temp_url IS NOT NULL AND (url IS NULL OR url = '');

   -- 批量上传到云存储（后台任务）
   -- 更新 url 字段
   UPDATE message_attachments SET
       url = '云存储URL',
       upload_status = 'completed'
   WHERE id = ...;
   ```

2. **兼容层**（前端）：
   ```typescript
   // 读取旧字段，但显示警告
   const displayUrl = att.url || att.tempUrl || '/placeholder.png';

   if (att.tempUrl && !att.url) {
     console.warn('[Deprecated] 使用了废弃字段 tempUrl:', att.id);
   }
   ```

3. **渐进式迁移**：保留兼容层 3 个月，逐步迁移旧数据

**优先级**：🔴 高

#### 风险 2：前端组件依赖旧字段

**描述**：现有代码可能在多处使用 `tempUrl`、`base64Data` 字段。

**影响**：
- 前端报错或显示空白
- 功能异常

**缓解方案**：
1. **代码搜索**：
   ```bash
   # 全局搜索 tempUrl 的使用
   grep -r "tempUrl" frontend/ --include="*.tsx" --include="*.ts"

   # 全局搜索 base64Data 的使用
   grep -r "base64Data" frontend/ --include="*.tsx" --include="*.ts"
   ```

2. **单元测试覆盖**：确保所有使用附件的组件都有测试

3. **TypeScript 编译检查**：标记废弃字段为 `@deprecated`

**优先级**：🟡 中

### 8.3 运维风险

#### 风险 1：数据库迁移失败

**描述**：迁移脚本可能因为数据量大、锁表等问题失败。

**影响**：
- 数据库不可用
- 服务中断

**缓解方案**：
1. **分批迁移**：每次迁移 1,000 条记录，避免锁表
2. **备份**：迁移前完整备份数据库
3. **在线迁移**：使用 `pt-online-schema-change` 工具
4. **回滚方案**：准备回滚脚本

**优先级**：🔴 高

#### 风险 2：云存储费用增加

**描述**：所有图片都上传到云存储，可能导致存储费用增加。

**影响**：
- 运营成本增加

**缓解方案**：
1. **重复文件检测**：计算文件 MD5，避免重复上传
2. **定期清理**：删除 30 天前的临时附件
3. **压缩**：上传前压缩图片（保持质量 90%）

**优先级**：🟢 低

---

## 监控与回滚方案

### 9.1 监控指标

#### 关键指标

| 指标 | 说明 | 告警阈值 |
|-----|------|---------|
| **上传成功率** | 成功上传 / 总上传次数 | < 95% |
| **上传延迟 (P95)** | 95% 的上传请求耗时 | > 3 秒 |
| **HTTP 下载失败率** | 下载失败 / 总下载次数 | > 10% |
| **缓存命中率** | Redis 缓存命中 / 总查询 | < 50% |
| **云存储错误率** | 云存储上传失败 / 总上传 | > 5% |

#### 监控实现

```python
# 使用 Prometheus 监控
from prometheus_client import Counter, Histogram

# 上传计数器
upload_counter = Counter(
    'attachment_upload_total',
    'Total attachment uploads',
    ['status', 'source_type']  # status: success/failed, source_type: file/url/base64
)

# 上传延迟直方图
upload_duration = Histogram(
    'attachment_upload_duration_seconds',
    'Attachment upload duration',
    ['source_type']
)

# 使用
with upload_duration.labels(source_type='file').time():
    result = await processor.process(file, session_id)
    upload_counter.labels(status='success', source_type='file').inc()
```

### 9.2 回滚方案

#### 回滚触发条件

如果出现以下情况，立即回滚：

1. **上传成功率 < 90%**（持续 10 分钟）
2. **上传延迟 P95 > 5 秒**（持续 10 分钟）
3. **数据库迁移失败**（无法恢复）
4. **用户投诉增加 > 50%**

#### 回滚步骤

**Step 1：停止部署**
```bash
# 停止新版本部署
kubectl rollout pause deployment/backend
```

**Step 2：回滚代码**
```bash
# 回滚到上一个版本
kubectl rollout undo deployment/backend

# 验证回滚状态
kubectl rollout status deployment/backend
```

**Step 3：回滚数据库**
```sql
-- 恢复废弃字段
ALTER TABLE message_attachments ADD COLUMN temp_url TEXT;
ALTER TABLE message_attachments ADD COLUMN base64_data TEXT;

-- 从备份恢复数据
-- (如果有修改)
```

**Step 4：验证**
- 检查前端是否正常显示图片
- 检查上传功能是否恢复
- 检查监控指标是否恢复正常

#### 回滚时间

- 代码回滚：5 分钟
- 数据库回滚：15 分钟
- 总计：< 20 分钟

---

## 附录

### A. 参考文档

- [EDIT_MODE_ATTACHMENT_COMPLETE_ANALYSIS.md](./EDIT_MODE_ATTACHMENT_COMPLETE_ANALYSIS.md) - 当前架构完整分析
- [GIT_PR_SETUP.md](./GIT_PR_SETUP.md) - Git 工作流程
- [IMAGE_GEN_COMPLETE_FLOW_ANALYSIS.md](./IMAGE_GEN_COMPLETE_FLOW_ANALYSIS.md) - 图片生成流程分析

### B. 决策日志

| 日期 | 决策 | 理由 |
|-----|------|------|
| 2026-01-18 | 废弃 `tempUrl` 字段 | 云 URL 是唯一权威来源，不需要临时 URL |
| 2026-01-18 | 废弃 `base64Data` 字段 | Base64 导致数据膨胀 33%，浪费存储和传输 |
| 2026-01-18 | 新增统一附件处理接口 | 减少前后端重复逻辑，提升可维护性 |
| 2026-01-18 | 保留 `upload_tasks` 表 | 异步上传仍需要任务管理 |

### C. FAQ

**Q1: 为什么不直接在前端上传到云存储？**

A: 前端直接上传需要暴露云存储凭证（如 S3 Access Key），存在安全风险。后端统一上传可以：
- 隐藏云存储凭证
- 统一验证文件类型和大小
- 支持多种云存储后端（S3 / GCS / OSS）

**Q2: HTTP URL 下载失败怎么办？**

A: 后端会重试 3 次（指数退避），如果仍失败：
- 返回错误信息给前端
- 前端提示用户重新上传
- 记录错误日志（URL、HTTP 状态码）

**Q3: 旧数据（使用 tempUrl）如何处理？**

A: 渐进式迁移：
1. 兼容层保留 3 个月，前端可以读取 `tempUrl`
2. 数据库迁移脚本批量上传到云存储
3. 3 个月后删除兼容层和废弃字段

**Q4: 性能是否会变差？**

A: 不会，反而会提升：
- 减少 50%+ 网络传输（不再 Base64 编码）
- 减少 60% 延迟（后端直接处理，无需前端中转）
- Redis 缓存进一步提升性能

---

**文档状态**: ✅ 设计完成，待评审

**下一步**: 开始阶段 1 开发（后端统一接口）
