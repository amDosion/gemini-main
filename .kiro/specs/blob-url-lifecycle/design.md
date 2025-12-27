# Design Document

## Overview

本设计文档描述了如何修复聊天附件上传功能中的 Blob URL 生命周期管理问题。

### 问题分析

通过对比 `ImageExpandView` 和 `AttachmentGrid` 的实现，发现核心问题：

1. **AttachmentGrid 未使用 tempUrl 降级**: 
   - 当前代码：`const url = att.url || att.fileUri;`
   - 缺少 `att.tempUrl` 作为降级选项
   
2. **InputArea 过早释放 Blob URL**:
   - 发送消息后立即清空 `attachments`
   - 触发 `useEffect` 清理函数释放 Blob URL

### 成功案例参考

`ImageExpandView.tsx` (第 365-368 行) 的正确实现：

```typescript
// ✅ 优先使用 url（永久 URL），如果没有则使用 tempUrl（临时 URL）
const displayUrl = att.url || att.tempUrl || '';
// ✅ 如果没有有效的 URL，不渲染图片
if (!displayUrl) return null;
```

### 解决方案

采用**简单的 URL 优先级降级**策略，无需复杂的 BlobUrlManager：

1. **修改 AttachmentGrid**: 添加 `tempUrl` 降级
2. **修改 InputArea**: 延迟释放 Blob URL
3. **添加上传完成回调**: 更新消息中的附件 URL

## Architecture

### 简化架构

```
┌─────────────────────────────────────────────────────────────┐
│  InputArea (附件输入)                                        │
│  ├─ 创建 Blob URL 并存储在 tempUrl                          │
│  ├─ 发送消息时保留 Blob URL (不立即清理)                    │
│  └─ 组件卸载时才释放 Blob URL                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  useChat (消息管理)                                          │
│  ├─ 复制附件到用户消息 (包含 tempUrl)                       │
│  ├─ 触发文件上传                                            │
│  └─ 监听上传完成，更新消息中的 url                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  AttachmentGrid (附件显示)                                   │
│  ├─ 优先使用 url (永久 URL)                                 │
│  ├─ 降级使用 tempUrl (Blob URL)                             │
│  └─ 最后使用 fileUri (兼容)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Attachment 类型 (无需修改)

当前类型已经包含所需字段：

```typescript
interface Attachment {
  id: string;
  file?: File;
  mimeType: string;
  name: string;
  url?: string;              // 永久 URL (上传后)
  tempUrl?: string;          // Blob URL (上传前)
  uploadStatus?: 'pending' | 'uploading' | 'uploaded' | 'failed';
  fileUri?: string;          // 兼容字段
}
```

### 2. AttachmentGrid 修改

**变更点**: 添加 `tempUrl` 降级

```typescript
// 修改前
const url = att.url || att.fileUri;

// 修改后 (参考 ImageExpandView)
const url = att.url || att.tempUrl || att.fileUri;
```

### 3. InputArea 修改

**变更点**: 延迟释放 Blob URL

```typescript
// 修改前：发送消息后立即清空
const handleSend = () => {
  onSend(input, options, attachments, mode);
  setInput('');
  updateAttachments([]); // ❌ 立即清空，触发 URL 释放
};

// 修改后：发送消息后保留附件
const handleSend = () => {
  onSend(input, options, attachments, mode);
  setInput('');
  // ✅ 不清空 attachments，让组件卸载时自然释放
  // 或者延迟清空，给上传足够时间
};
```

### 4. useChat 修改 (可选优化)

**变更点**: 添加上传完成回调

```typescript
// 上传完成后更新消息中的附件 URL
const onUploadComplete = (attachmentId: string, permanentUrl: string) => {
  setMessages(prev => prev.map(msg => ({
    ...msg,
    attachments: msg.attachments?.map(att =>
      att.id === attachmentId
        ? { ...att, url: permanentUrl, uploadStatus: 'uploaded' }
        : att
    )
  })));
};
```

## Data Models

### URL 优先级

```
1. url (永久 URL) - 最高优先级，上传完成后设置
2. tempUrl (Blob URL) - 中等优先级，上传前使用
3. fileUri (兼容 URL) - 最低优先级，兼容旧数据
```

### Blob URL 生命周期

```
[创建] → 存储在 tempUrl
   │
   ├─ [发送消息] → 保留 tempUrl (不释放)
   │      │
   │      ├─ [上传成功] → 设置 url，tempUrl 仍保留
   │      │
   │      └─ [上传失败] → 保留 tempUrl
   │
   └─ [组件卸载] → 释放 tempUrl
```

## Correctness Properties

*属性是一种特征或行为，应该在系统的所有有效执行中保持为真。*

### Property 1: URL 降级正确性

*For any* 附件，显示的 URL 应该按照 `url → tempUrl → fileUri` 的优先级选择

**Validates: Requirements 3.3**

### Property 2: Blob URL 可用性

*For any* 消息中的附件，如果 `url` 未设置，则 `tempUrl` 应该是有效的 Blob URL

**Validates: Requirements 1.2, 4.2**

### Property 3: 上传完成后的 URL 更新

*For any* 上传成功的附件，消息中的 `url` 应该被更新为永久 URL

**Validates: Requirements 3.1**

## Error Handling

### 1. Blob URL 失效

**场景**: Blob URL 被过早释放

**处理**:
- 使用 `tempUrl` 降级
- 如果 `tempUrl` 也失效，显示占位符

### 2. 上传失败

**场景**: 文件上传失败

**处理**:
- 保留 `tempUrl`，用户仍可查看原图
- 显示错误提示和重试按钮

## Testing Strategy

### Unit Tests

1. **AttachmentGrid URL 选择测试**
   - 测试 `url` 存在时优先使用
   - 测试 `url` 不存在时降级到 `tempUrl`
   - 测试所有 URL 都不存在时的处理

2. **InputArea Blob URL 管理测试**
   - 测试发送消息后 Blob URL 不被释放
   - 测试组件卸载时 Blob URL 被释放

### Integration Tests

1. **完整上传流程测试**
   - 创建附件 → 发送消息 → 显示 tempUrl → 上传完成 → 显示 url
   - 验证整个流程中图片始终可见

2. **错误恢复测试**
   - 模拟上传失败
   - 验证 tempUrl 仍然可用

## Implementation Notes

### 最小改动原则

本方案遵循最小改动原则，只需修改：

1. **AttachmentGrid.tsx**: 1 行代码修改
2. **InputArea.tsx**: 移除或延迟 `updateAttachments([])` 调用
3. **useChat.ts**: 可选添加上传完成回调

### 参考实现

参考 `ImageExpandView.tsx` 和 `ImageEditView.tsx` 的成功实践：
- 使用 `att.url || att.tempUrl` 降级
- 使用独立的 `canvasObjectUrlRef` 管理 Blob URL
- 组件卸载时统一释放
