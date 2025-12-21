attachmentUtils.ts:395 [findAttachmentByUrl] 开始查找, targetUrl 类型: Base64
attachmentUtils.ts:402 [findAttachmentByUrl] ✅ 精确匹配成功: {id: '19e4d31f-cd86-4e64-98f5-9c60852d614d', messageId: 'c15cd510-506c-48e4-b5e2-b554eadb2ad9', matchedField: 'url', uploadStatus: 'completed'}id: "19e4d31f-cd86-4e64-98f5-9c60852d614d"matchedField: "url"messageId: "c15cd510-506c-48e4-b5e2-b554eadb2ad9"uploadStatus: "completed"[[Prototype]]: Object
App.tsx:349 [handleEditImage] 跨模式传递 - 完整附件状态: {foundOriginal: true, attachmentId: '19e4d31f...', url: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...', urlType: 'Base64', tempUrl: 'https://img.dicry.com/uploads/1766314002902_genera...', …}attachmentId: "19e4d31f..."foundOriginal: truetempUrl: "https://img.dicry.com/uploads/1766314002902_genera..."tempUrlType: "HTTP"uploadStatus: "completed"url: "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."urlType: "Base64"[[Prototype]]: Object
ImageEditView.tsx:118 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:119 [handleSend] 用户输入: 黑色头发
ImageEditView.tsx:120 [handleSend] 用户上传的附件数量: 1
ImageEditView.tsx:130 [handleSend] 附件[0]: {id: '19e4d31f...', urlType: 'Base64', tempUrlType: 'HTTP', uploadStatus: 'completed'}id: "19e4d31f..."tempUrlType: "HTTP"uploadStatus: "completed"urlType: "Base64"[[Prototype]]: Object
ImageEditView.tsx:137 [handleSend] activeImageUrl 类型: Base64
attachmentUtils.ts:683 [processUserAttachments] ✅ 处理用户上传的附件, 数量: 1
attachmentUtils.ts:694 [processUserAttachments] 附件[0] 原始状态: {id: '19e4d31f...', urlType: 'Base64', tempUrlType: 'HTTP', uploadStatus: 'completed', hasBase64Data: false}hasBase64Data: falseid: "19e4d31f..."tempUrlType: "HTTP"uploadStatus: "completed"urlType: "Base64"[[Prototype]]: Object
attachmentUtils.ts:712 [processUserAttachments] 附件[0] 处理策略: {hasCloudUrlInTemp: true, displayUrlType: 'Base64'}displayUrlType: "Base64"hasCloudUrlInTemp: true[[Prototype]]: Object
attachmentUtils.ts:721 [processUserAttachments] 附件[0] 情况1: 使用 tempUrl 中的云 URL
attachmentUtils.ts:725 [processUserAttachments] 附件[0] ✅ 从云 URL 获取 base64 成功
ImageEditView.tsx:152 [handleSend] 最终附件数量: 1
ImageEditView.tsx:153 ========== [ImageEditView] handleSend 结束 ==========
image-edit.ts:122 [GoogleMedia] Editing image with model: gemini-3-pro-image-preview
image-edit.ts:123 [GoogleMedia] Parts count: 2 (images: 1)
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 734b98e4-5921-4475-91ea-76abee7def5b
useChat.ts:169 [useChat] 上传任务已提交，已保存到数据库（pending）
