# 上传数据流分析文档

## 1. 概述

本文档描述了从用户选择附件到最终上传至云存储的完整数据流。系统采用**前后端分离架构**，前端负责文件预处理和 `UI` 交互，后端负责实际的云存储上传。

## 2. 架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   前端 (Frontend)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────────┐  │
│  │  InputArea   │───▶│   useChat    │───▶│         Handler 层               │  │
│  │  (用户交互)   │    │  (消息处理)   │    │  imageGenHandler / imageEdit... │  │
│  └──────────────┘    └──────────────┘    └──────────────────────────────────┘  │
│         │                   │                          │                        │
│         │                   │                          ▼                        │
│         │                   │            ┌──────────────────────────────────┐  │
│         │                   │            │       attachmentUtils.ts         │  │
│         │                   │            │   uploadToCloudStorageSync()     │  │
│         │                   │            └──────────────────────────────────┘  │
│         │                   │                          │                        │
│         ▼                   ▼                          ▼                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                      storageUpload.ts                                     │  │
│  │                   StorageUploadService                                    │  │
│  │  - checkBackendAvailable()  检测后端可用性                                 │  │
│  │  - uploadFile()             上传文件入口                                   │  │
│  │  - uploadViaBackend()       调用后端 API                                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
└──────────────────────────────────────│──────────────────────────────────────────┘
                                       │ HTTP POST /api/storage/upload
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   后端 (Backend)                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        storage.py (Router)                                │  │
│  │  - POST /api/storage/upload          同步上传                             │  │
│  │  - POST /api/storage/upload-async    异步上传                             │  │
│  │  - POST /api/storage/upload-from-url 从 URL 下载后上传                    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│                                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                    storage_service.py (Service)                           │  │
│  │  - upload_to_lsky()        上传到兰空图床                                  │  │
│  │  - upload_to_aliyun_oss()  上传到阿里云 OSS                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
└──────────────────────────────────────│──────────────────────────────────────────┘
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │      云存储服务         │
                          │  - 兰空图床 (Lsky Pro) │
                          │  - 阿里云 OSS          │
                          └────────────────────────┘
```

## 3. 详细数据流

### 3.1 用户选择附件流程

```
用户点击上传按钮
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  InputArea.tsx: handleFileSelect()                              │
│  位置: frontend/components/chat/InputArea.tsx:130               │
├─────────────────────────────────────────────────────────────────┤
│  1. 获取用户选择的文件 (File 对象)                               │
│  2. 创建 Blob URL 用于 UI 预览: URL.createObjectURL(file)       │
│  3. 生成唯一 attachmentId: uuidv4()                             │
│  4. 构建 Attachment 对象:                                        │
│     {                                                            │
│       id: attachmentId,                                          │
│       file: file,           // 保留 File 对象                    │
│       mimeType: file.type,                                       │
│       name: file.name,                                           │
│       url: blobUrl,         // Blob URL 用于预览                 │
│       tempUrl: blobUrl,                                          │
│       uploadStatus: 'pending'  // 等待发送时上传                 │
│     }                                                            │
│  5. 更新 attachments 状态                                        │
│                                                                  │
│  ⚠️ 注意：此时不触发任何上传，只做本地预览                        │
└─────────────────────────────────────────────────────────────────┘
       │
       │ 用户点击发送
       ▼
```

### 3.2 发送消息触发上传流程

```
用户点击发送按钮
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  InputArea.tsx: handleSend()                                    │
│  位置: frontend/components/chat/InputArea.tsx:220               │
├─────────────────────────────────────────────────────────────────┤
│  调用 onSend(input, options, attachments, mode)                 │
│  将 attachments 传递给 useChat                                   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  useChat.ts: sendMessage()                                      │
│  位置: frontend/hooks/useChat.ts:30                             │
├─────────────────────────────────────────────────────────────────┤
│  根据 mode 分发到不同的 Handler:                                 │
│  - chat         → handleChat()                                  │
│  - image-gen    → handleImageGen()                              │
│  - image-edit   → handleImageEdit()                             │
│  - image-outpainting → handleImageExpand()                      │
│  - video-gen    → handleVideoGen()                              │
│  - audio-gen    → handleAudioGen()                              │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
```

### 3.3 图片生成模式上传流程 (以 `image-gen` 为例)

```
┌─────────────────────────────────────────────────────────────────┐
│  imageGenHandler.ts: handleImageGen()                           │
│  位置: frontend/hooks/handlers/imageGenHandler.ts:30            │
├─────────────────────────────────────────────────────────────────┤
│  1. 调用 llmService.generateImage() 生成图片                    │
│  2. 处理 API 返回的结果（可能是临时 URL 或 Base64）              │
│  3. 下载远程图片，创建本地 Blob URL 用于立即显示                 │
│  4. 构建 displayAttachments（本地 URL，用于 UI）                │
│  5. 创建 uploadTask（异步上传任务）                              │
│  6. 立即返回 displayAttachments，不阻塞 UI                      │
└─────────────────────────────────────────────────────────────────┘
       │
       │ uploadTask 异步执行
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  attachmentUtils.ts: uploadToCloudStorageSync()                 │
│  位置: frontend/hooks/handlers/attachmentUtils.ts:142           │
├─────────────────────────────────────────────────────────────────┤
│  输入类型判断与转换:                                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  File 对象      → 直接使用                               │    │
│  │  Base64 URL     → fetch() → blob → File                 │    │
│  │  Blob URL       → fetch() → blob → File                 │    │
│  │  HTTP URL       → fetch() → blob → File (下载远程图片)  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  调用 storageUpload.uploadFile(file)                            │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  storageUpload.ts: uploadFile()                                 │
│  位置: frontend/services/storage/storageUpload.ts:225           │
├─────────────────────────────────────────────────────────────────┤
│  1. checkBackendAvailable()                                     │
│     - 检测后端 API 是否可用                                      │
│     - 请求: GET /api/storage/configs                            │
│     - 超时: 5 秒                                                 │
│     - 缓存: 30 秒内不重复检测                                    │
│                                                                  │
│  2. 如果后端可用:                                                │
│     uploadViaBackend(file, storageId)                           │
│     - 构建 FormData                                              │
│     - 请求: POST /api/storage/upload                            │
│                                                                  │
│  3. 如果后端不可用:                                              │
│     返回错误: "后端服务不可用，请确保后端服务正在运行"            │
└─────────────────────────────────────────────────────────────────┘
       │
       │ HTTP POST /api/storage/upload
       ▼
```

### 3.4 后端上传处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│  storage.py: upload_file()                                      │
│  位置: backend/app/routers/storage.py:170                       │
├─────────────────────────────────────────────────────────────────┤
│  1. 获取存储配置                                                 │
│     - 如果指定 storage_id，使用指定配置                          │
│     - 否则使用当前激活的配置 (ActiveStorage)                     │
│                                                                  │
│  2. 验证配置                                                     │
│     - 配置是否存在                                               │
│     - 配置是否启用                                               │
│                                                                  │
│  3. 读取文件内容: await file.read()                             │
│                                                                  │
│  4. 调用 StorageService.upload_file()                           │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  storage_service.py: upload_file()                              │
│  位置: backend/app/services/storage_service.py:200              │
├─────────────────────────────────────────────────────────────────┤
│  根据 provider 类型分发:                                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  provider == "lsky"                                      │    │
│  │  → upload_to_lsky()                                      │    │
│  │    - 构建 FormData                                       │    │
│  │    - 请求: POST {domain}/api/v1/upload                   │    │
│  │    - Headers: Authorization: Bearer {token}              │    │
│  │    - 超时: 60 秒                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  provider == "aliyun-oss"                                │    │
│  │  → upload_to_aliyun_oss()                                │    │
│  │    - 使用 oss2 SDK                                       │    │
│  │    - 生成对象名: uploads/{timestamp}_{filename}          │    │
│  │    - 调用 bucket.put_object()                            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  返回结果                                                        │
├─────────────────────────────────────────────────────────────────┤
│  成功:                                                           │
│  {                                                               │
│    "success": true,                                              │
│    "url": "https://img.dicry.com/2025/12/17/xxx.png",           │
│    "provider": "lsky"                                            │
│  }                                                               │
│                                                                  │
│  失败:                                                           │
│  {                                                               │
│    "success": false,                                             │
│    "error": "错误信息"                                           │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## 4. 关键文件清单

| 层级 | 文件路径 | 职责 |
|------|----------|------|
| UI 层 | `frontend/components/chat/InputArea.tsx` | 用户文件选择、预览、发送 |
| Hook 层 | `frontend/hooks/useChat.ts` | 消息处理、模式分发 |
| Handler 层 | `frontend/hooks/handlers/imageGenHandler.ts` | 图片生成处理 |
| Handler 层 | `frontend/hooks/handlers/imageEditHandler.ts` | 图片编辑处理 |
| Handler 层 | `frontend/hooks/handlers/imageExpandHandler.ts` | 图片扩展处理 |
| Handler 层 | `frontend/hooks/handlers/mediaGenHandler.ts` | 视频/音频生成处理 |
| 工具层 | `frontend/hooks/handlers/attachmentUtils.ts` | 附件处理工具函数 |
| 服务层 | `frontend/services/storage/storageUpload.ts` | 前端上传服务 |
| 服务层 | `frontend/services/storage/BlobStorageService.ts` | 本地 IndexedDB 缓存 |
| 路由层 | `backend/app/routers/storage.py` | 后端上传接口 |
| 服务层 | `backend/app/services/storage_service.py` | 云存储上传实现 |

## 5. 数据状态流转

```
┌─────────────────────────────────────────────────────────────────┐
│                      Attachment 状态流转                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  用户选择文件                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  uploadStatus: 'pending'                                 │    │
│  │  url: blob:xxx (本地预览 URL)                            │    │
│  │  file: File 对象                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       │ 发送消息，触发上传                                       │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  uploadStatus: 'uploading' (可选中间状态)                │    │
│  │  url: blob:xxx                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       │ 上传完成                                                 │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  uploadStatus: 'completed'                               │    │
│  │  url: https://img.dicry.com/xxx.png (云存储 URL)         │    │
│  │  file: undefined (已清除)                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       │ 上传失败                                                 │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  uploadStatus: 'failed'                                  │    │
│  │  url: '' (清空)                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 6. 并发上传问题分析

根据日志 `.kiro/specs/erron/log.md`，当前存在并发上传问题：

### 6.1 问题现象

```
storageUpload.ts:52 ✅ [StorageUpload] 后端 API 可用 - 使用后端上传
storageUpload.ts:66 ⚠️ [StorageUpload] 后端 API 检测失败，将重试
storageUpload.ts:67 错误详情: TimeoutError: signal timed out
```

### 6.2 根本原因

```
┌─────────────────────────────────────────────────────────────────┐
│  并发竞态条件 (Race Condition)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  3 张图片同时上传:                                               │
│                                                                  │
│  图片 1 ──▶ checkBackendAvailable() ──▶ 成功 ✅                 │
│  图片 2 ──▶ checkBackendAvailable() ──▶ 超时 ❌ (并发请求)      │
│  图片 3 ──▶ checkBackendAvailable() ──▶ 成功 ✅ (重试后)        │
│                                                                  │
│  问题：                                                          │
│  1. 缓存机制在并发场景下失效                                     │
│  2. 多个请求同时发起后端检测                                     │
│  3. 超时设置 (5秒) 在高负载时不够                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 建议优化方案

```typescript
// storageUpload.ts 优化建议

class StorageUploadService {
  private checkPromise: Promise<boolean> | null = null;  // 并发锁

  private async checkBackendAvailable(): Promise<boolean> {
    // 如果已有检测在进行中，等待其完成
    if (this.checkPromise) {
      return this.checkPromise;
    }

    // 缓存命中
    if (this.useBackend === true && Date.now() - this.lastCheckTime < this.CHECK_INTERVAL) {
      return true;
    }

    // 创建新的检测 Promise
    this.checkPromise = this.doCheck();
    
    try {
      return await this.checkPromise;
    } finally {
      this.checkPromise = null;
    }
  }

  private async doCheck(): Promise<boolean> {
    // 实际检测逻辑...
  }
}
```

## 7. 总结

### 7.1 数据流总结

1. **用户选择文件** → 创建 `Blob URL` 预览，不触发上传
2. **用户点击发送** → 根据模式分发到对应 `Handler`
3. **Handler 处理** → 调用 `uploadToCloudStorageSync()` 上传
4. **前端服务层** → `storageUpload.ts` 检测后端并调用 `API`
5. **后端路由层** → `storage.py` 接收请求并分发
6. **后端服务层** → `storage_service.py` 执行实际上传
7. **云存储** → 返回永久 `URL`

### 7.2 设计特点

- **前后端分离**：前端只负责预处理和调用，后端负责实际上传
- **异步非阻塞**：`UI` 先显示本地预览，上传在后台进行
- **多提供商支持**：兰空图床、阿里云 `OSS`
- **状态追踪**：通过 `uploadStatus` 追踪上传状态
