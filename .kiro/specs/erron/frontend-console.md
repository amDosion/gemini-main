ImageEditView.tsx:171 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:172 [handleSend] 用户输入: 蓝宝石手链


ImageEditView.tsx:173 [handleSend] 用户上传的附件数量: 0
ImageEditView.tsx:174 [handleSend] 当前 sessionId: 86878f54-b236-44d9-9e02-4850686aa515
ImageEditView.tsx:175 [handleSend] 当前 activeImageUrl: https://img.dicry.com/uploads/1766042874139_generated-1766042873902-1.png...
ImageEditView.tsx:181 [handleSend] activeImageUrl 类型: 云存储 URL
ImageEditView.tsx:188 [handleSend] ✅ 触发 CONTINUITY LOGIC（用户未上传新图，使用画布图片）
ImageEditView.tsx:127 [findAttachmentFromHistory] ✅ 找到匹配的附件: {id: 'aef3a59c-4ddd-4a12-b547-1df1db0e59f0', messageId: '473f12ab-8550-4ee6-b2e9-c5f9bc1770af', url: 'https://img.dicry.com/uploads/1766042874139_generated-176604', uploadStatus: undefined}
ImageEditView.tsx:196 [handleSend] 复用历史附件模式, messageId: 473f12ab-8550-4ee6-b2e9-c5f9bc1770af
ImageEditView.tsx:202 [handleSend] 检查是否需要查询后端: {finalUploadStatus: 'completed', currentSessionId: '86878f54-b236-44d9-9e02-4850686aa515', attachmentId: 'aef3a59c-4ddd-4a12-b547-1df1db0e59f0'}
ImageEditView.tsx:235 [handleSend] 从云存储下载图片转 Base64
ImageEditView.tsx:251 [handleSend] ✅ 复用历史附件完成，uploadStatus: completed url 类型: 云存储
ImageEditView.tsx:319 [handleSend] 最终附件数量: 1
ImageEditView.tsx:321 [handleSend] 最终附件详情: [{…}]
ImageEditView.tsx:331 ========== [ImageEditView] handleSend 结束，调用 onSend ==========
imageEditHandler.ts:45 [imageEditHandler] 预处理 1 张原图
imageEditHandler.ts:62 [imageEditHandler] 已有 Base64 数据，直接转换为 File（无需下载）
imageEditHandler.ts:69 [imageEditHandler] Base64 转 File 完成，大小: 401215 bytes
image-edit.ts:122 [GoogleMedia] Editing image with model: gemini-3-pro-image-preview
image-edit.ts:123 [GoogleMedia] Parts count: 2 (images: 1)
imageEditHandler.ts:171 [imageEditHandler] 1 张结果图已准备好显示
imageEditHandler.ts:188 [imageEditHandler] 提交 1 张结果图到 Redis 上传队列
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: e08b64ec-e4f3-4767-9a40-ef27483d40ee
imageEditHandler.ts:212 [imageEditHandler] 结果图 edited-1766044620899-1.png 已提交到队列，任务ID: e08b64ec-e4f3-4767-9a40-ef27483d40ee
imageEditHandler.ts:245 [imageEditHandler] 所有结果图已提交到 Redis 队列
imageEditHandler.ts:248 [imageEditHandler] 处理 1 张原图上传
imageEditHandler.ts:253 [imageEditHandler] 复用原始云存储 URL: https://img.dicry.com/uploads/1766042874139_generated-176604
imageEditHandler.ts:301 [imageEditHandler] 所有原图已处理，Worker 池将在后台处理上传
useChat.ts:296 [useChat] image-edit 上传任务已提交，已保存到数据库（pending）
useChat.ts:313 [upload:e08b64ec] [info] upload request received
useChat.ts:313 [upload:e08b64ec] [info] temp file saved
useChat.ts:313 [upload:e08b64ec] [info] db record created (upload_tasks)
useChat.ts:313 [upload:e08b64ec] [info] dequeued from upload:queue:normal
useChat.ts:313 [upload:e08b64ec] [info] enqueued to upload:queue:normal (priority=normal, position=0)
useChat.ts:313 [upload:e08b64ec] [info] Worker-1 received task
useChat.ts:313 [upload:e08b64ec] [info] Worker-1 acquired lock
useChat.ts:313 [upload:e08b64ec] [info] status changed: pending -> uploading
useChat.ts:313 [upload:e08b64ec] [info] upload started (provider=aliyun-oss, filename=edited-1766044620899-1.png, size_kb=7800.21)
useChat.ts:313 [upload:e08b64ec] [info] upload succeeded (duration_s=5.24, url=https://img.dicry.com/uploads/1766044621370_edited-1766044620899-1.png)
useChat.ts:313 [upload:e08b64ec] [info] db verify (after_success_commit): status=completed, target_url=yes, retry_count=0, completed_at=1766044626630
useChat.ts:313 [upload:e08b64ec] [info] status changed: uploading -> completed
useChat.ts:324 [upload:e08b64ec] ✅ 上传完成（前端保持本地URL）: https://img.dicry.com/uploads/1766044621370_edited-1766044620899-1.png
