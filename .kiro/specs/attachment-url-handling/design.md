# Design Document

## Overview

本设计文档描述了附件 URL 处理系统的架构和实现细节。系统的核心目标是正确区分显示 URL 和数据 URL，处理不同来源的附件（手动上传 vs 跨模式传递），并支持三种 URL 类型（Base64、Blob、云 URL）的检测和转换。

## Architecture

系统采用分层架构，主要包含以下层次：

```
┌─────────────────────────────────────────────────────────────┐
│                    UI Layer (Views)                         │
│  ImageEditView, ImageExpandView, ImageGenView               │
│  - 使用 attachment.url 进行渲染                              │
│  - 调用 processUserAttachments 处理用户输入                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Processing Layer (Hooks)                    │
│  useChat, processUserAttachments, prepareAttachmentForApi   │
│  - 处理附件来源识别                                          │
│  - 执行 CONTINUITY LOGIC                                    │
│  - 准备 API 调用数据                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Utility Layer (attachmentUtils)             │
│  URL 类型检测、转换、查找、上传                               │
│  - isBase64Url, isBlobUrl, isHttpUrl                        │
│  - urlToBase64, urlToFile, sourceToFile                     │
│  - findAttachmentByUrl, fetchAttachmentStatus               │
│  - uploadToCloudStorageSync                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Storage Layer (Backend API)                 │
│  /api/sessions/{sessionId}/attachments/{attachmentId}       │
│  /api/storage/download?url=xxx                              │
│  - 查询附件状态和云 URL                                      │
│  - 代理下载远程图片（解决 CORS）                             │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. URL 类型检测函数

```typescript
// 检测 Base64 URL
function isBase64Url(url: string | undefined): boolean

// 检测 Blob URL
function isBlobUrl(url: string | undefined): boolean

// 检测 HTTP URL
function isHttpUrl(url: string | undefined): boolean

// 检测是否已上传到云存储
function isUploadedToCloud(att: Attachment): boolean
```

### 2. URL 转换函数

```typescript
// 将任意来源转换为 File 对象
function sourceToFile(
  source: string | File,
  filename: string,
  mimeType?: string
): Promise<File>

// 将任意 URL 转换为 Base64 Data URL
function urlToBase64(url: string): Promise<string>

// 将任意 URL 转换为 File 对象
function urlToFile(
  url: string,
  filename: string,
  mimeType?: string
): Promise<File>
```

### 3. 附件查找和状态查询

```typescript
// 从消息历史中查找匹配 URL 的附件
function findAttachmentByUrl(
  targetUrl: string,
  messages: Message[]
): { attachment: Attachment; messageId: string } | null

// 从后端查询附件的最新状态
function fetchAttachmentStatus(
  sessionId: string,
  attachmentId: string
): Promise<{ url: string; uploadStatus: string } | null>

// 尝试从后端获取云存储 URL
function tryFetchCloudUrl(
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string | undefined,
  currentStatus: string | undefined
): Promise<{ url: string; uploadStatus: string } | null>
```

### 4. 附件处理核心函数

```typescript
// 准备附件供 API 调用（CONTINUITY LOGIC 核心函数）
function prepareAttachmentForApi(
  imageUrl: string,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string
): Promise<Attachment | null>

// 处理用户上传的附件（统一函数）
function processUserAttachments(
  attachments: Attachment[],
  activeImageUrl: string | null,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string
): Promise<Attachment[]>

// 清理附件用于数据库存储
function cleanAttachmentsForDb(
  atts: Attachment[],
  verbose?: boolean
): Attachment[]
```


## Data Models

### Attachment 接口

```typescript
interface Attachment {
  id: string;                    // 唯一标识符
  mimeType: string;              // MIME 类型，如 'image/png'
  name: string;                  // 文件名
  url?: string;                  // 显示 URL（用于 UI 渲染）
                                 // - 初始：Blob URL 或 Base64 URL（用户上传后立即显示）
                                 // - 上传完成后：云 URL（从后端 target_url 获取）
  tempUrl?: string;              // 临时/匹配 URL
                                 // - AI 返回的临时图片链接（会过期）
                                 // - 跨模式传递时保存的原始 URL（用于 findAttachmentByUrl 匹配）
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'failed';
  uploadTaskId?: string;         // 上传任务 ID
  file?: File;                   // 原始 File 对象（仅内存中使用，不可序列化）
  fileUri?: string;              // Google File API URI
  base64Data?: string;           // Base64 数据（仅 API 调用时临时使用）
}
```

### URL 字段职责对照表

| 字段 | 用途 | 来源 | 生命周期 |
|------|------|------|----------|
| `url` | UI 显示 | Blob URL → 云 URL（上传完成后） | 持久化时保留 HTTP URL |
| `tempUrl` | 临时/匹配 | AI 临时链接、跨模式原始 URL | 持久化时保留 HTTP URL |
| `target_url` (后端) | 永久存储 | 云存储 URL | 永久 |

### URL 类型枚举

```typescript
type UrlType = 'Base64' | 'Blob' | 'HTTP' | 'Other' | 'None';
```

### 附件来源枚举

```typescript
type AttachmentSource = 'manual-upload' | 'cross-mode-transfer' | 'continuity-logic';
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: URL 类型检测正确性

*For any* URL string, the URL type detection functions (isBase64Url, isBlobUrl, isHttpUrl) SHALL correctly identify the URL type based on its prefix.

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 2: URL 转换往返一致性

*For any* valid image data, converting to File and back to Base64 SHALL produce equivalent data (round-trip property).

**Validates: Requirements 3.4, 3.5**

### Property 3: 数据库持久化 URL 清理

*For any* attachment with Blob URL or Base64 URL in the url field, after calling cleanAttachmentsForDb, the url field SHALL be cleared or empty.

**Validates: Requirements 1.6, 6.1, 6.2**

### Property 4: 上传完成后 URL 更新

*For any* attachment with uploadStatus === 'completed', the url field SHALL contain cloud URL (HTTP URL) obtained from backend target_url.

**Validates: Requirements 1.4, 4.3**

### Property 5: 跨模式传递 tempUrl 保留

*For any* attachment transferred from another mode, the original url SHALL be copied to tempUrl for findAttachmentByUrl matching, and the original id and uploadStatus SHALL be preserved.

**Validates: Requirements 1.5, 2.2, 4.1**

### Property 6: CONTINUITY LOGIC 附件匹配

*For any* activeImageUrl, when searching for matching attachment in message history, the system SHALL match by url field first, then tempUrl field, then fall back to most recent image attachment.

**Validates: Requirements 8.2, 8.3**

### Property 7: 后端查询触发条件

*For any* attachment with uploadStatus pending, when processing for API call, the system SHALL query backend for cloud URL (target_url) and update url field upon success.

**Validates: Requirements 2.4, 4.2, 4.4, 5.4**

### Property 8: 附件字段清理完整性

*For any* attachment saved to database, the file property and base64Data property SHALL be removed.

**Validates: Requirements 6.3**

### Property 9: API 调用 URL 选择优先级

*For any* attachment when preparing for API call:
1. IF uploadStatus === 'completed' AND url is HTTP URL THEN use url field
2. ELSE IF uploadStatus === 'pending' THEN query backend for target_url first
3. ELSE convert local Blob/Base64 to base64Data

**Validates: Requirements 5.2, 5.3, 5.4, 5.5**


## Error Handling

### 错误类型

| 错误类型 | 触发条件 | 处理策略 |
|---------|---------|---------|
| URL 转换失败 | fetch 失败或 CORS 错误 | 使用后端代理重试 |
| 后端查询失败 | API 返回非 200 状态 | 回退到使用本地 URL 转换 |
| 云 URL 获取失败 | 后端未返回有效 target_url | 使用本地 URL 转换 |
| 所有方法失败 | 无法获取有效数据 | 抛出描述性错误 |

### 错误处理流程

```
1. 检查 uploadStatus
   ├─ completed → 使用 url 字段（已是云 URL）
   └─ pending → 继续步骤 2

2. 查询后端获取 target_url
   ├─ 成功 → 更新 url 字段为云 URL，返回结果
   └─ 失败 → 继续步骤 3

3. 尝试使用本地 URL 转换
   ├─ url 是 Blob URL → 直接 fetch 转 base64Data
   ├─ url 是 Base64 URL → 直接使用
   ├─ tempUrl 是 HTTP URL → 通过后端代理获取
   └─ 失败 → 抛出错误
```

### URL 字段更新时机

| 事件 | url 字段变化 | tempUrl 字段变化 |
|------|-------------|-----------------|
| 用户上传文件 | 设置为 Blob URL | 不设置 |
| AI 返回临时图片 | 设置为 Blob URL（从临时 URL 创建） | 设置为 AI 临时 URL |
| 跨模式传递 | 保持原值 | 设置为原始 url（用于匹配） |
| 上传完成 | 更新为云 URL（target_url） | 保持不变 |
| 持久化到数据库 | 清除 Blob/Base64，保留 HTTP | 清除 Blob/Base64，保留 HTTP |

## Testing Strategy

### 单元测试

使用 Vitest 进行单元测试，覆盖以下场景：

1. **URL 类型检测**
   - 测试各种 URL 格式的正确识别
   - 测试边界情况（空字符串、undefined、null）

2. **URL 转换**
   - 测试 Base64 到 File 的转换
   - 测试 Blob URL 到 File 的转换
   - 测试 HTTP URL 到 File 的转换（需要 mock 后端代理）

3. **数据库持久化**
   - 测试 cleanAttachmentsForDb 函数
   - 验证 Blob/Base64 URL 被清理
   - 验证 HTTP URL 被保留

### 属性测试

使用 fast-check 进行属性测试，验证以下属性：

1. **Property 1: URL 类型检测正确性**
   - 生成各种 URL 字符串
   - 验证检测函数返回正确的类型

2. **Property 2: URL 转换往返一致性**
   - 生成随机图片数据
   - 验证转换后数据等价

3. **Property 3: 数据库持久化 URL 清理**
   - 生成带有各种 URL 类型的附件
   - 验证清理后的结果符合预期

4. **Property 4: 云 URL 优先级**
   - 生成带有 url 和 tempUrl 的附件
   - 验证 API 调用时使用正确的 URL

### 测试配置

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
});
```

### 属性测试示例

```typescript
import * as fc from 'fast-check';
import { isBase64Url, isBlobUrl, isHttpUrl } from './attachmentUtils';

// Property 1: URL 类型检测正确性
describe('URL Type Detection', () => {
  it('should correctly identify Base64 URLs', () => {
    fc.assert(
      fc.property(
        fc.string().map(s => `data:image/png;base64,${s}`),
        (url) => isBase64Url(url) === true
      )
    );
  });

  it('should correctly identify Blob URLs', () => {
    fc.assert(
      fc.property(
        fc.uuid().map(id => `blob:http://localhost/${id}`),
        (url) => isBlobUrl(url) === true
      )
    );
  });

  it('should correctly identify HTTP URLs', () => {
    fc.assert(
      fc.property(
        fc.webUrl(),
        (url) => isHttpUrl(url) === true
      )
    );
  });
});
```
