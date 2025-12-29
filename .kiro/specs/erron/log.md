llmService.ts:142 [llmService.generateImage] 配置检查: {hasApiKey: true, apiKeyLength: 35, hasBaseUrl: true, baseUrl: 'https://dashscope.aliyuncs.com', providerId: 'tongyi'}
image-gen.ts:325 [WanV2-T2I] 请求参数: {
  "model": "wan2.6-t2i",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "近景镜头，18岁的中国女孩，古代服饰，圆脸，正面看着镜头，民族优雅的服装，商业摄影，室外"
          }
        ]
      }
    ]
  },
  "parameters": {
    "size": "1536*1536",
    "n": 4,
    "prompt_extend": true,
    "watermark": false
  }
}
image-gen.ts:329 [WanV2-T2I] 使用端点: /api/dashscope/api/v1/services/aigc/multimodal-generation/generation
image-gen.ts:348 [WanV2-T2I] 使用同步模式调用 API
image-gen.ts:350  POST http://192.168.50.22:5173/api/dashscope/api/v1/services/aigc/multimodal-generation/generation 400 (Bad Request)
submitWanV2T2ISync @ image-gen.ts:350
generateWanV2Image @ image-gen.ts:332
generateDashScopeImage @ image-gen.ts:119
generateImage @ DashScopeProvider.ts:110
generateImage @ llmService.ts:153
doExecute @ ImageGenHandlerClass.ts:9
execute @ BaseHandler.ts:34
sendMessage @ useChat.ts:134
await in sendMessage
(anonymous) @ App.tsx:322
handleSend @ InputArea.tsx:203
await in handleSend
executeDispatch @ react-dom_client.js?v=458fe056:13622
runWithFiberInDEV @ react-dom_client.js?v=458fe056:997
processDispatchQueue @ react-dom_client.js?v=458fe056:13658
(anonymous) @ react-dom_client.js?v=458fe056:14071
batchedUpdates$1 @ react-dom_client.js?v=458fe056:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=458fe056:13763
dispatchEvent @ react-dom_client.js?v=458fe056:16784
dispatchDiscreteEvent @ react-dom_client.js?v=458fe056:16765
installHook.js:1 [WanV2-T2I] API 错误: {request_id: 'dba26839-b508-459b-adf0-d96ca4386f4d', code: 'InvalidParameter', message: 'Total pixels (2359296) must be between 589824 and 2073600.'}
overrideMethod @ installHook.js:1
submitWanV2T2ISync @ image-gen.ts:362
await in submitWanV2T2ISync
generateWanV2Image @ image-gen.ts:332
generateDashScopeImage @ image-gen.ts:119
generateImage @ DashScopeProvider.ts:110
generateImage @ llmService.ts:153
doExecute @ ImageGenHandlerClass.ts:9
execute @ BaseHandler.ts:34
sendMessage @ useChat.ts:134
await in sendMessage
(anonymous) @ App.tsx:322
handleSend @ InputArea.tsx:203
await in handleSend
executeDispatch @ react-dom_client.js?v=458fe056:13622
runWithFiberInDEV @ react-dom_client.js?v=458fe056:997
processDispatchQueue @ react-dom_client.js?v=458fe056:13658
(anonymous) @ react-dom_client.js?v=458fe056:14071
batchedUpdates$1 @ react-dom_client.js?v=458fe056:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=458fe056:13763
dispatchEvent @ react-dom_client.js?v=458fe056:16784
dispatchDiscreteEvent @ react-dom_client.js?v=458fe056:16765
installHook.js:1 [useChat] 执行失败: Error: WanV2-T2I API Error: Total pixels (2359296) must be between 589824 and 2073600.
    at submitWanV2T2ISync (image-gen.ts:363:15)
    at async generateWanV2Image (image-gen.ts:332:21)
    at async ImageGenHandler.doExecute (ImageGenHandlerClass.ts:9:21)
    at async ImageGenHandler.execute (BaseHandler.ts:34:12)
    at async sendMessage (useChat.ts:134:22)
overrideMethod @ installHook.js:1
sendMessage @ useChat.ts:182
await in sendMessage
(anonymous) @ App.tsx:322
handleSend @ InputArea.tsx:203
await in handleSend
executeDispatch @ react-dom_client.js?v=458fe056:13622
runWithFiberInDEV @ react-dom_client.js?v=458fe056:997
processDispatchQueue @ react-dom_client.js?v=458fe056:13658
(anonymous) @ react-dom_client.js?v=458fe056:14071
batchedUpdates$1 @ react-dom_client.js?v=458fe056:2626
dispatchEventForPluginEventSystem @ react-dom_client.js?v=458fe056:13763
dispatchEvent @ react-dom_client.js?v=458fe056:16784
dispatchDiscreteEvent @ react-dom_client.js?v=458fe056:16765
