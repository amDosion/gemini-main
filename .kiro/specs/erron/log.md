cacheService.ts:252 [CacheService] 失效缓存: "sessions"
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 28a86912-f261-4f3e-b8b9-f1174c49f8ba
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: bb2b8d84-512f-45ce-ab93-e55d1dd4d23b
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 6e3246cc-38c6-4402-852d-3e1119919fc7
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 93440d85-3f4d-49e2-9ddd-b95685ce9a30
useChat.ts:169 [useChat] 上传任务已提交，已保存到数据库（pending）
attachmentUtils.ts:395 [findAttachmentByUrl] 开始查找, targetUrl 类型: Base64
attachmentUtils.ts:402 [findAttachmentByUrl] ✅ 精确匹配成功: {id: '37be669d-4b26-46f1-9413-7726f65dd0be', messageId: '35fdee80-3b6d-443d-8eae-a19a6da239ef', matchedField: 'url', uploadStatus: 'pending'}
App.tsx:325 [handleEditImage] uploadStatus=pending，查询后端获取云 URL
attachmentUtils.ts:305 [tryFetchCloudUrl] 查询后端, 原因: uploadStatus=pending
attachmentUtils.ts:446 [fetchAttachmentStatus] 开始查询附件: {sessionId: '899c53be...', attachmentId: '37be669d-4b26-46f1-9413-7726f65dd0be'}
attachmentUtils.ts:456 [fetchAttachmentStatus] 查询结果: {url: 'https://img.dicry.com/uploads/1766328711679_generated-1766328709410.png', urlIsHttp: true, uploadStatus: 'completed', taskId: '28a86912-f261-4f3e-b8b9-f1174c49f8ba', taskStatus: 'completed', …}
attachmentUtils.ts:312 [tryFetchCloudUrl] ✅ 获取到云 URL: https://img.dicry.com/uploads/1766328711679_generated-176632
App.tsx:333 [handleEditImage] ✅ 获取到云 URL: https://img.dicry.com/uploads/1766328711679_generated-176632
App.tsx:349 [handleEditImage] 跨模式传递 - 完整附件状态: {foundOriginal: true, attachmentId: '37be669d...', url: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...', urlType: 'Base64', tempUrl: 'https://img.dicry.com/uploads/1766328711679_genera...', …}attachmentId: "37be669d..."foundOriginal: truetempUrl: "https://img.dicry.com/uploads/1766328711679_genera..."tempUrlType: "HTTP"uploadStatus: "completed"url: "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."urlType: "Base64"[[Prototype]]: Object
ImageEditView.tsx:118 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:119 [handleSend] 用户输入: 黑色头发
ImageEditView.tsx:120 [handleSend] 用户上传的附件数量: 1
ImageEditView.tsx:130 [handleSend] 附件[0]: {id: '37be669d...', urlType: 'Base64', tempUrlType: 'HTTP', uploadStatus: 'completed'}
ImageEditView.tsx:137 [handleSend] activeImageUrl 类型: Base64
attachmentUtils.ts:683 [processUserAttachments] ✅ 处理用户上传的附件, 数量: 1
attachmentUtils.ts:694 [processUserAttachments] 附件[0] 原始状态: {id: '37be669d...', urlType: 'Base64', tempUrlType: 'HTTP', uploadStatus: 'completed', hasBase64Data: false}hasBase64Data: falseid: "37be669d..."tempUrlType: "HTTP"uploadStatus: "completed"urlType: "Base64"[[Prototype]]: Object
attachmentUtils.ts:711 [processUserAttachments] 附件[0] 处理策略: {displayUrlType: 'Base64', hasCloudUrlInTemp: true, uploadStatus: 'completed'}
attachmentUtils.ts:722 [processUserAttachments] 附件[0] ✅ url 已是 Base64，直接使用（无需网络请求）
ImageEditView.tsx:152 [handleSend] 最终附件数量: 1
ImageEditView.tsx:153 ========== [ImageEditView] handleSend 结束 ==========
image-edit.ts:122 [GoogleMedia] Editing image with model: gemini-3-pro-image-preview
image-edit.ts:123 [GoogleMedia] Parts count: 2 (images: 1)
(index):1 Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received
(index):1 Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received
(index):1 Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received
(index):1 Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received
(index):1 Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received
(index):1 Uncaught (in promise) Error: A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 436ecb82-8c05-479f-9e46-806e0f17d82a
useChat.ts:169 [useChat] 上传任务已提交，已保存到数据库（pending）
ImageEditView.tsx:118 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:119 [handleSend] 用户输入: 白色衣服
ImageEditView.tsx:120 [handleSend] 用户上传的附件数量: 0
ImageEditView.tsx:137 [handleSend] activeImageUrl 类型: Base64
attachmentUtils.ts:666 [processUserAttachments] ✅ 触发 CONTINUITY LOGIC（无新上传）
attachmentUtils.ts:505 [prepareAttachmentForApi] 开始准备附件
attachmentUtils.ts:506 [prepareAttachmentForApi] imageUrl 类型: Base64
attachmentUtils.ts:395 [findAttachmentByUrl] 开始查找, targetUrl 类型: Base64
attachmentUtils.ts:402 [findAttachmentByUrl] ✅ 精确匹配成功: {id: 'c7bf2ad5-bb83-477e-99e6-413ea2f5476c', messageId: '0bef5d69-4877-4d57-8d2c-4bec19917cea', matchedField: 'url', uploadStatus: 'pending'}
attachmentUtils.ts:520 [prepareAttachmentForApi] ✅ 找到历史附件: {id: 'c7bf2ad5-bb83-477e-99e6-413ea2f5476c', url: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/6ximSlAAA', uploadStatus: 'pending'}
attachmentUtils.ts:305 [tryFetchCloudUrl] 查询后端, 原因: uploadStatus=pending
attachmentUtils.ts:446 [fetchAttachmentStatus] 开始查询附件: {sessionId: '899c53be...', attachmentId: 'c7bf2ad5-bb83-477e-99e6-413ea2f5476c'}
attachmentUtils.ts:456 [fetchAttachmentStatus] 查询结果: {url: 'https://img.dicry.com/uploads/1766328779138_edited-1766328778836.png', urlIsHttp: true, uploadStatus: 'completed', taskId: '436ecb82-8c05-479f-9e46-806e0f17d82a', taskStatus: 'completed', …}
attachmentUtils.ts:312 [tryFetchCloudUrl] ✅ 获取到云 URL: https://img.dicry.com/uploads/1766328779138_edited-176632877
attachmentUtils.ts:566 [prepareAttachmentForApi] ✅ 复用历史附件完成: {hasCloudUrl: true, hasBase64: true}hasBase64: truehasCloudUrl: true[[Prototype]]: Object
ImageEditView.tsx:152 [handleSend] 最终附件数量: 1
ImageEditView.tsx:153 ========== [ImageEditView] handleSend 结束 ==========
image-edit.ts:122 [GoogleMedia] Editing image with model: gemini-3-pro-image-preview
image-edit.ts:123 [GoogleMedia] Parts count: 2 (images: 1)
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 5fac82a5-9f44-4d34-818c-b6ffa9f242e3
useChat.ts:169 [useChat] 上传任务已提交，已保存到数据库（pending）
