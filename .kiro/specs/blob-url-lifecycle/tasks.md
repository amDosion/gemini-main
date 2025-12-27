# Implementation Plan: Blob URL Lifecycle Management

## Overview

本实施计划采用**最小改动原则**，参考 `ImageExpandView` 和 `ImageEditView` 的成功实践，修复聊天附件上传的 Blob URL 问题。

## Tasks

- [x] 1. 修改 AttachmentGrid 组件
  - [x] 1.1 添加 tempUrl 降级支持
    - 修改 URL 选择逻辑：`att.url || att.tempUrl || att.fileUri`
    - 应用到所有附件类型（图片、视频、音频、文件）
    - _Requirements: 3.3, 3.4_
    - **状态**：已完成 ✅
    - **修改内容**：
      - 图片：使用 `const displayUrl = att.url || att.tempUrl || att.fileUri;`
      - 视频：使用 `const displayUrl = att.url || att.tempUrl || att.fileUri;`
      - 音频：使用 `const displayUrl = att.url || att.tempUrl || att.fileUri;`
      - 更新所有使用 `url` 的地方为 `displayUrl`

- [x] 2. 修改 InputArea 组件
  - [x] 2.1 在发送前转换 Blob URL 为 Base64
    - 导入 `fileToBase64` 和 `isBlobUrl` 工具函数
    - 在 `handleSend()` 中，发送前将 Blob URL 转换为 Base64 Data URL
    - 保持 `updateAttachments([])` 调用（清空附件），但用户消息中的图片已经是 Base64 URL，不受影响
    - _Requirements: 1.2, 1.4_
    - **状态**：已完成 ✅
    - **修改内容**：
      - 添加 `import { fileToBase64, isBlobUrl } from '../../hooks/handlers/attachmentUtils';`
      - 修改 `handleSend` 为 `async` 函数
      - 在发送前处理附件：如果有 `file` 对象且 `url` 是 Blob URL，转换为 Base64

- [ ] 3. 测试基本功能
  - [ ] 3.1 测试图片上传和显示
    - 上传图片 → 发送消息 → 验证图片在消息中可见
    - 刷新页面 → 验证图片仍然可见（如果已上传）
    - _Requirements: 1.1, 1.2, 3.3_
    - **状态**：待测试 ⏳

- [ ] 4. (可选) 添加上传完成回调
  - [ ] 4.1 在 useChat 中添加 URL 更新逻辑
    - 监听上传完成事件
    - 更新消息中的附件 URL
    - _Requirements: 3.1, 3.2_
    - **状态**：可选优化 📝

- [ ] 5. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户

## Implementation Summary

### 修改的文件

1. **`frontend/components/message/AttachmentGrid.tsx`**
   - 添加 URL 优先级降级策略：`url -> tempUrl -> fileUri`
   - 应用到所有附件类型（图片、视频、音频）

2. **`frontend/components/chat/InputArea.tsx`**
   - 导入 `fileToBase64` 和 `isBlobUrl` 工具函数
   - 在 `handleSend()` 中，发送前将 Blob URL 转换为 Base64 Data URL
   - 保持原有的 `updateAttachments([])` 调用

### 核心原理

参考 `ImageEditView` 的成功实践：
- **Blob URL 转换**：在发送消息前，将 Blob URL 转换为 Base64 Data URL（永久有效）
- **URL 降级策略**：在显示时，优先使用 `url`，降级到 `tempUrl`，最后使用 `fileUri`
- **生命周期管理**：Base64 URL 不受 `InputArea` 的 Blob URL 清理影响

### 关键代码

```typescript
// InputArea.tsx - 发送前转换
const processedAttachments = await Promise.all(
  attachments.map(async (att) => {
    if (att.file && isBlobUrl(att.url)) {
      const base64Url = await fileToBase64(att.file);
      return { ...att, url: base64Url, tempUrl: base64Url };
    }
    return att;
  })
);

// AttachmentGrid.tsx - 显示时降级
const displayUrl = att.url || att.tempUrl || att.fileUri;
```

## Notes

- 本方案修改了 2 个文件，约 20 行代码
- 参考 `ImageExpandView.tsx` 第 365-368 行和 `ImageEditView.tsx` 的实现
- 优先完成任务 1-3，任务 4 为可选优化
- 核心思路：**在发送前转换为永久 URL，避免依赖 Blob URL 生命周期**
