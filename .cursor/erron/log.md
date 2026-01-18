content.js:8 🚀 AI Chat Sidebar content script loaded
ImageEditView.tsx:440 ========== [ImageEditView] handleSend 开始 ==========
ImageEditView.tsx:441 [handleSend] 用户输入: 黑色头发
ImageEditView.tsx:442 [handleSend] 选择的编辑模式: image-chat-edit
ImageEditView.tsx:443 [handleSend] 用户上传的附件数量: 0
attachmentUtils.ts:799 [processUserAttachments] ✅ 触发 CONTINUITY LOGIC（无新上传）
attachmentUtils.ts:660 [prepareAttachmentForApi] 开始准备附件, imageUrl 类型: HTTP
attachmentUtils.ts:537 [findAttachmentByUrl] 开始查找, targetUrl 类型: HTTP
attachmentUtils.ts:545 [findAttachmentByUrl] ✅ 精确匹配成功: {id: '203fb389-93c8-4f4f-beeb-a4f2fc9b0083', messageId: 'a9715f4b-a8a8-4031-91b9-9f4ca5c3a432', matchedField: 'url', uploadStatus: 'completed'}id: "203fb389-93c8-4f4f-beeb-a4f2fc9b0083"matchedField: "url"messageId: "a9715f4b-a8a8-4031-91b9-9f4ca5c3a432"uploadStatus: "completed"[[Prototype]]: Object
attachmentUtils.ts:667 [prepareAttachmentForApi] ✅ 找到历史附件
attachmentUtils.ts:707 [prepareAttachmentForApi] ✅ HTTP URL，直接传递（后端会自己下载）
attachmentUtils.ts:710 [prepareAttachmentForApi] ✅ 复用历史附件完成, Cloud URL: https://img.dicry.com/uploads/1768542604886_generated-1768542602652.png
ImageEditView.tsx:469 [handleSend] 最终附件数量: 1
ImageEditView.tsx:470 ========== [ImageEditView] handleSend 结束 ==========
llmService.ts:149 ========== [llmService.startNewChat] 设置图片生成参数 ==========
llmService.ts:150 [startNewChat] Model: nano-banana-pro-preview
llmService.ts:151 [startNewChat] 传入的 Options: {numberOfImages: 1, imageAspectRatio: '1:1', imageResolution: '1K', imageStyle: 'None', negativePrompt: '', …}enhancePrompt: falseimageAspectRatio: "1:1"imageResolution: "1K"imageStyle: "None"negativePrompt: ""numberOfImages: 1outputCompressionQuality: 80outputMimeType: "image/png"seed: undefined[[Prototype]]: Object
llmService.ts:163 [startNewChat] 完整 Options 对象: {
  "enableSearch": false,
  "enableThinking": false,
  "enableCodeExecution": false,
  "enableUrlContext": false,
  "enableBrowser": false,
  "enableResearch": false,
  "googleCacheMode": "none",
  "imageAspectRatio": "1:1",
  "imageResolution": "1K",
  "numberOfImages": 1,
  "imageStyle": "None",
  "voiceName": "Puck",
  "outPainting": {
    "mode": "scale",
    "xScale": 2,
    "yScale": 2,
    "leftOffset": 0,
    "rightOffset": 0,
    "topOffset": 0,
    "bottomOffset": 0,
    "bestQuality": true,
    "limitImageSize": false
  },
  "negativePrompt": "",
  "outputMimeType": "image/png",
  "outputCompressionQuality": 80,
  "enhancePrompt": false,
  "persona": {
    "id": "general",
    "userId": "gemini2026_ru1o6o91",
    "name": "General Assistant",
    "description": "Helpful and versatile assistant for daily tasks.",
    "systemPrompt": "You are a helpful, harmless, and honest AI assistant. You answer questions clearly and concisely using Markdown formatting.",
    "icon": "MessageSquare",
    "category": "General"
  }
}
llmService.ts:164 ========== [llmService.startNewChat] 参数设置结束 ==========
ImageEditHandlerClass.ts:41 [ImageEditHandler] ✅ 使用 HTTP URL，后端将自行下载: https://img.dicry.com/uploads/1768542604886_generated-176854
llmService.ts:311 [llmService.editImage] 配置检查: {hasBaseUrl: true, baseUrl: 'https://generativelanguage.goo', providerId: 'google', modelId: 'nano-banana-pro-preview', mode: 'image-chat-edit', …}
UnifiedProviderClient.ts:443  POST http://localhost:21573/api/modes/google/image-chat-edit 400 (Bad Request)
executeMode @ UnifiedProviderClient.ts:443
editImage @ UnifiedProviderClient.ts:578
editImage @ llmService.ts:352
doExecute @ ImageEditHandlerClass.ts:63
execute @ BaseHandler.ts:34
sendMessage @ useChat.ts:172
await in sendMessage
(anonymous) @ App.tsx:281
(anonymous) @ ImageEditView.tsx:472
await in (anonymous)
handleSend @ InputArea.tsx:270
await in handleSend
handleKeyDown @ PromptInput.tsx:83
executeDispatch @ react-dom_client.js?v=d4a005e9:13622
runWithFiberInDEV @ react-dom_client.js?v=d4a005e9:997
processDispatchQueue @ react-dom_client.js?v=d4a005e9:13658
(anonymous) @ react-dom_client.js?v=d4a005e9:14071
batchedUpdates$1 @ react-dom_client.js?v=d4a005e9:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=d4a005e9:13763
dispatchEvent @ react-dom_client.js?v=d4a005e9:16784
dispatchDiscreteEvent @ react-dom_client.js?v=d4a005e9:16765
installHook.js:1 [UnifiedProviderClient] Mode execution error for google/image-chat-edit: Error: Invalid base64-encoded string: number of data characters (65) cannot be 1 more than a multiple of 4
    at UnifiedProviderClient.executeMode (UnifiedProviderClient.ts:465:15)
    at async UnifiedProviderClient.editImage (UnifiedProviderClient.ts:578:18)
    at async ImageEditHandler.doExecute (ImageEditHandlerClass.ts:63:21)
    at async ImageEditHandler.execute (BaseHandler.ts:34:12)
    at async sendMessage (useChat.ts:172:22)
overrideMethod @ installHook.js:1
executeMode @ UnifiedProviderClient.ts:476
await in executeMode
editImage @ UnifiedProviderClient.ts:578
editImage @ llmService.ts:352
doExecute @ ImageEditHandlerClass.ts:63
execute @ BaseHandler.ts:34
sendMessage @ useChat.ts:172
await in sendMessage
(anonymous) @ App.tsx:281
(anonymous) @ ImageEditView.tsx:472
await in (anonymous)
handleSend @ InputArea.tsx:270
await in handleSend
handleKeyDown @ PromptInput.tsx:83
executeDispatch @ react-dom_client.js?v=d4a005e9:13622
runWithFiberInDEV @ react-dom_client.js?v=d4a005e9:997
processDispatchQueue @ react-dom_client.js?v=d4a005e9:13658
(anonymous) @ react-dom_client.js?v=d4a005e9:14071
batchedUpdates$1 @ react-dom_client.js?v=d4a005e9:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=d4a005e9:13763
dispatchEvent @ react-dom_client.js?v=d4a005e9:16784
dispatchDiscreteEvent @ react-dom_client.js?v=d4a005e9:16765
installHook.js:1 [useChat] 执行失败: Error: Invalid base64-encoded string: number of data characters (65) cannot be 1 more than a multiple of 4
    at UnifiedProviderClient.executeMode (UnifiedProviderClient.ts:465:15)
    at async UnifiedProviderClient.editImage (UnifiedProviderClient.ts:578:18)
    at async ImageEditHandler.doExecute (ImageEditHandlerClass.ts:63:21)
    at async ImageEditHandler.execute (BaseHandler.ts:34:12)
    at async sendMessage (useChat.ts:172:22)
overrideMethod @ installHook.js:1
sendMessage @ useChat.ts:223
await in sendMessage
(anonymous) @ App.tsx:281
(anonymous) @ ImageEditView.tsx:472
await in (anonymous)
handleSend @ InputArea.tsx:270
await in handleSend
handleKeyDown @ PromptInput.tsx:83
executeDispatch @ react-dom_client.js?v=d4a005e9:13622
runWithFiberInDEV @ react-dom_client.js?v=d4a005e9:997
processDispatchQueue @ react-dom_client.js?v=d4a005e9:13658
(anonymous) @ react-dom_client.js?v=d4a005e9:14071
batchedUpdates$1 @ react-dom_client.js?v=d4a005e9:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=d4a005e9:13763
dispatchEvent @ react-dom_client.js?v=d4a005e9:16784
dispatchDiscreteEvent @ react-dom_client.js?v=d4a005e9:16765
