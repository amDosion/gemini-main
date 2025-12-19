chatHandler.ts:25 [chatHandler] 开始流式对话: {textLength: 65, attachmentsCount: 0, model: 'gemini-2.5-flash'}
cacheService.ts:252 [CacheService] 失效缓存: "sessions"
GoogleProvider.ts:195  POST http://192.168.50.22:5173/api/browse 503 (Service Unavailable)
sendMessageStream @ GoogleProvider.ts:195
sendMessageStream @ llmService.ts:83
handleChat @ chatHandler.ts:40
await in handleChat
sendMessage @ useChat.ts:125
onSend @ App.tsx:296
handleSend @ InputArea.tsx:220
executeDispatch @ react-dom_client.js?v=5d683dc1:13622
runWithFiberInDEV @ react-dom_client.js?v=5d683dc1:997
processDispatchQueue @ react-dom_client.js?v=5d683dc1:13658
(anonymous) @ react-dom_client.js?v=5d683dc1:14071
batchedUpdates$1 @ react-dom_client.js?v=5d683dc1:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=5d683dc1:13763
dispatchEvent @ react-dom_client.js?v=5d683dc1:16784
dispatchDiscreteEvent @ react-dom_client.js?v=5d683dc1:16765
chatHandler.ts:81 [chatHandler] 流式对话完成: {chunkCount: 3, finalTextLength: 212, attachmentsCount: 0, hasGrounding: false, hasUrlContext: false, …}attachmentsCount: 0chunkCount: 3finalTextLength: 212hasBrowserOp: truehasGrounding: falsehasUrlContext: false[[Prototype]]: Object
