react-dom_client.js?v=5d683dc1:20103 Download the React DevTools for a better development experience: https://react.dev/link/react-devtools
content.js:8 🚀 AI Chat Sidebar content script loaded
db.ts:213 ✅ 后端 API 已连接 - 使用数据库存储 (PostgreSQL/SQLite)
ImageEditView.tsx:170 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:171 [handleSend] 用户输入: 姿势很性感妖娆
ImageEditView.tsx:172 [handleSend] 用户上传的附件数量: 0
ImageEditView.tsx:173 [handleSend] 当前 sessionId: 92770ad2-befc-434c-9a3d-7faa2d14606c
ImageEditView.tsx:174 [handleSend] 当前 activeImageUrl: https://img.dicry.com/2025/12/16/6940db7b6be20.png...
ImageEditView.tsx:180 [handleSend] activeImageUrl 类型: 云存储 URL
ImageEditView.tsx:187 [handleSend] ✅ 触发 CONTINUITY LOGIC（用户未上传新图，使用画布图片）
ImageEditView.tsx:126 [findAttachmentFromHistory] ✅ 找到匹配的附件: {id: '15899201-c674-4178-9198-a22a05f244d1', messageId: 'a8f24658-f1ab-4e47-be03-218b2a2f3678', url: 'https://img.dicry.com/2025/12/16/6940db7b6be20.png', uploadStatus: 'completed'}
ImageEditView.tsx:195 [handleSend] 复用历史附件模式, messageId: a8f24658-f1ab-4e47-be03-218b2a2f3678
ImageEditView.tsx:201 [handleSend] 检查是否需要查询后端: {finalUploadStatus: 'completed', currentSessionId: '92770ad2-befc-434c-9a3d-7faa2d14606c', attachmentId: '15899201-c674-4178-9198-a22a05f244d1'}
ImageEditView.tsx:228 [handleSend] 附件已上传到云存储，下载转 Base64
ImageEditView.tsx:244 [handleSend] ✅ 复用历史附件完成，uploadStatus: completed url 类型: 云存储
ImageEditView.tsx:312 [handleSend] 最终附件数量: 1
ImageEditView.tsx:314 [handleSend] 最终附件详情: [{…}]
ImageEditView.tsx:324 ========== [ImageEditView] handleSend 结束，调用 onSend ==========
image-edit.ts:99 [GoogleMedia] Editing image with model: gemini-3-pro-image-preview
image-edit.ts:100 [GoogleMedia] Parts count: 2 (images: 1)
useChat.ts:277 [useChat] 上传结果图到云存储: edited-1765858265629-1.png
useChat.ts:52 [useChat] 提交异步上传任务: Base64 Data URL
useChat.ts:65 [useChat] Base64 已转换为 File: edited-1765858265629-1.png image/jpeg 8587837
storageUpload.ts:424 [StorageUpload] 异步上传任务已创建: dcd71d6c-516c-45c9-9bd7-89a53926d48d
useChat.ts:77 [useChat] 异步上传任务已提交: dcd71d6c-516c-45c9-9bd7-89a53926d48d
ImageEditView.tsx:170 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:171 [handleSend] 用户输入: V领，细微可见的乳沟
ImageEditView.tsx:172 [handleSend] 用户上传的附件数量: 0
ImageEditView.tsx:173 [handleSend] 当前 sessionId: 92770ad2-befc-434c-9a3d-7faa2d14606c
ImageEditView.tsx:174 [handleSend] 当前 activeImageUrl: data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/6/36SlAAAQAAAAEABHtLanVtYgAAAB5qdW1kYzJwYQARABCAA...
ImageEditView.tsx:180 [handleSend] activeImageUrl 类型: Base64
ImageEditView.tsx:187 [handleSend] ✅ 触发 CONTINUITY LOGIC（用户未上传新图，使用画布图片）
ImageEditView.tsx:126 [findAttachmentFromHistory] ✅ 找到匹配的附件: {id: '0412499d-dff6-41e8-a37a-0cf8006c7faa', messageId: '933c2258-a513-4227-a482-fc1fb855c23e', url: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/6/36SlAAA', uploadStatus: 'pending'}
ImageEditView.tsx:195 [handleSend] 复用历史附件模式, messageId: 933c2258-a513-4227-a482-fc1fb855c23e
ImageEditView.tsx:201 [handleSend] 检查是否需要查询后端: {finalUploadStatus: 'pending', currentSessionId: '92770ad2-befc-434c-9a3d-7faa2d14606c', attachmentId: '0412499d-dff6-41e8-a37a-0cf8006c7faa'}
ImageEditView.tsx:207 [handleSend] 附件状态为 pending，查询后端获取最新 URL
ImageEditView.tsx:150 [fetchAttachmentFromBackend] 查询附件: 0412499d-dff6-41e8-a37a-0cf8006c7faa
ImageEditView.tsx:157 [fetchAttachmentFromBackend] 查询结果: {url: 'https://img.dicry.com/2025/12/16/6940dbeb0d206.png', uploadStatus: 'completed', taskId: 'dcd71d6c-516c-45c9-9bd7-89a53926d48d'}
ImageEditView.tsx:210 [handleSend] ✅ 从后端获取到云存储 URL: https://img.dicry.com/2025/12/16/6940dbeb0d206.png
ImageEditView.tsx:228 [handleSend] 附件已上传到云存储，下载转 Base64
ImageEditView.tsx:244 [handleSend] ✅ 复用历史附件完成，uploadStatus: completed url 类型: 云存储
ImageEditView.tsx:312 [handleSend] 最终附件数量: 1
ImageEditView.tsx:314 [handleSend] 最终附件详情: [{…}]
ImageEditView.tsx:324 ========== [ImageEditView] handleSend 结束，调用 onSend ==========
image-edit.ts:99 [GoogleMedia] Editing image with model: gemini-3-pro-image-preview
image-edit.ts:100 [GoogleMedia] Parts count: 2 (images: 1)
useChat.ts:277 [useChat] 上传结果图到云存储: edited-1765858356327-1.png
useChat.ts:52 [useChat] 提交异步上传任务: Base64 Data URL
useChat.ts:65 [useChat] Base64 已转换为 File: edited-1765858356327-1.png image/jpeg 8015252
storageUpload.ts:424 [StorageUpload] 异步上传任务已创建: dda86d4e-4419-4f3e-84ce-9146a6ddf35e
useChat.ts:77 [useChat] 异步上传任务已提交: dda86d4e-4419-4f3e-84ce-9146a6ddf35e
