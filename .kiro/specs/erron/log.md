###  前端日志

react-dom_client.js?v=5d683dc1:20103 Download the React DevTools for a better development experience: https://react.dev/link/react-devtools
idbCacheAdapter.ts:86 [IDBCacheAdapter] IndexedDB 缓存初始化成功
db.ts:248 ✅ 后端 API 已连接 - 使用数据库存储 (PostgreSQL/SQLite)
idbCacheAdapter.ts:86 [IDBCacheAdapter] IndexedDB 缓存初始化成功
cacheService.ts:113 [CacheService] 从 IndexedDB 加载了 1 个缓存条目
cacheService.ts:124 [CacheService] 缓存服务初始化完成
cachedDb.ts:54 [CachedDB] 缓存数据库初始化完成
cacheService.ts:157 [CacheService] 缓存命中: "sessions"
cacheService.ts:113 [CacheService] 从 IndexedDB 加载了 1 个缓存条目
cacheService.ts:124 [CacheService] 缓存服务初始化完成
cachedDb.ts:54 [CachedDB] 缓存数据库初始化完成
cacheService.ts:157 [CacheService] 缓存命中: "sessions"
imageGenHandler.ts:35 [imageGenHandler] 调用 API 生成图片，提示词: 欧洲女孩
cacheService.ts:252 [CacheService] 失效缓存: "sessions"
imageGenHandler.ts:64 [imageGenHandler] 4 张结果图已准备好显示
imageGenHandler.ts:80 [imageGenHandler] 提交 4 张图片到 Redis 上传队列
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
imageGenHandler.ts:105 [imageGenHandler] 图片 generated-1766035199660-2.png 已提交到队列，任务ID: 26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
imageGenHandler.ts:105 [imageGenHandler] 图片 generated-1766035199660-1.png 已提交到队列，任务ID: 4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 47b1071d-9838-4f58-bada-e9fb745a8bd2
imageGenHandler.ts:105 [imageGenHandler] 图片 generated-1766035199660-3.png 已提交到队列，任务ID: 47b1071d-9838-4f58-bada-e9fb745a8bd2
storageUpload.ts:428 [StorageUpload] 异步上传任务已创建: 1f86fdce-02e7-4c77-ad3b-b3dc4a878779
imageGenHandler.ts:105 [imageGenHandler] 图片 generated-1766035199661-4.png 已提交到队列，任务ID: 1f86fdce-02e7-4c77-ad3b-b3dc4a878779
imageGenHandler.ts:138 [imageGenHandler] 所有图片已提交到 Redis 队列，Worker 池将在后台处理上传
useChat.ts:176 [useChat] image-gen 上传任务已提交，已保存到数据库（pending）
storageUpload.ts:556  GET http://192.168.50.22:5173/api/storage/upload-logs/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96?tail=200 404 (Not Found)
getUploadTaskLogs @ storageUpload.ts:556
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
await in sendMessage
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
storageUpload.ts:560 [StorageUpload] /storage/upload-logs 返回 404：后端可能仍是旧版本，已停止拉取任务日志
getUploadTaskLogs @ storageUpload.ts:560
await in getUploadTaskLogs
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
storageUpload.ts:556  GET http://192.168.50.22:5173/api/storage/upload-logs/1f86fdce-02e7-4c77-ad3b-b3dc4a878779?tail=200 404 (Not Found)
getUploadTaskLogs @ storageUpload.ts:556
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
await in sendMessage
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
storageUpload.ts:560 [StorageUpload] /storage/upload-logs 返回 404：后端可能仍是旧版本，已停止拉取任务日志
getUploadTaskLogs @ storageUpload.ts:560
await in getUploadTaskLogs
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
storageUpload.ts:556  GET http://192.168.50.22:5173/api/storage/upload-logs/47b1071d-9838-4f58-bada-e9fb745a8bd2?tail=200 404 (Not Found)
getUploadTaskLogs @ storageUpload.ts:556
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
await in sendMessage
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
storageUpload.ts:560 [StorageUpload] /storage/upload-logs 返回 404：后端可能仍是旧版本，已停止拉取任务日志
getUploadTaskLogs @ storageUpload.ts:560
await in getUploadTaskLogs
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
storageUpload.ts:556  GET http://192.168.50.22:5173/api/storage/upload-logs/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d?tail=200 404 (Not Found)
getUploadTaskLogs @ storageUpload.ts:556
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167
await in sendMessage
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
storageUpload.ts:560 [StorageUpload] /storage/upload-logs 返回 404：后端可能仍是旧版本，已停止拉取任务日志
getUploadTaskLogs @ storageUpload.ts:560
await in getUploadTaskLogs
monitorOne @ useChat.ts:199
(anonymous) @ useChat.ts:243
Promise.then
sendMessage @ useChat.ts:167



###  后端日志


[1] → 发送请求: POST /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=4634da77-4b6a-44dc-95e3-16d7e531e15c
[1] → 发送请求: POST /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=1a26f86a-88a9-47d1-967f-3be6ddbf1cd5
[1] → 发送请求: POST /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=58ac8b24-362c-4d9e-a2cb-1c30cf31d142
[1] → 发送请求: POST /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=90165418-0c78-48ad-942d-4afc1cd98c66
[1] ← 收到响应: 200 /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=4634da77-4b6a-44dc-95e3-16d7e531e15c
[1] ← 收到响应: 200 /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=58ac8b24-362c-4d9e-a2cb-1c30cf31d142
[1] ← 收到响应: 200 /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=90165418-0c78-48ad-942d-4afc1cd98c66
[1] ← 收到响应: 200 /api/storage/upload-async?session_id=86878f54-b236-44d9-9e02-4850686aa515&message_id=9b66c631-4984-470a-b6b0-dfae5c547706&attachment_id=1a26f86a-88a9-47d1-967f-3be6ddbf1cd5
[1] → 发送请求: GET /api/storage/upload-logs/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96?tail=200
[1] → 发送请求: GET /api/storage/upload-logs/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d?tail=200
[1] → 发送请求: GET /api/storage/upload-logs/47b1071d-9838-4f58-bada-e9fb745a8bd2?tail=200
[1] → 发送请求: GET /api/storage/upload-logs/1f86fdce-02e7-4c77-ad3b-b3dc4a878779?tail=200
[1] ← 收到响应: 404 /api/storage/upload-logs/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96?tail=200
[1] ← 收到响应: 404 /api/storage/upload-logs/1f86fdce-02e7-4c77-ad3b-b3dc4a878779?tail=200
[1] ← 收到响应: 404 /api/storage/upload-logs/47b1071d-9838-4f58-bada-e9fb745a8bd2?tail=200
[1] ← 收到响应: 404 /api/storage/upload-logs/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d?tail=200
[1] → 发送请求: POST /api/sessions
[1] → 发送请求: POST /api/sessions
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/sessions
[1] ← 收到响应: 200 /api/sessions
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] → 发送请求: GET /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] → 发送请求: GET /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779
[1] → 发送请求: GET /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] → 发送请求: GET /api/storage/upload-status/26c3dce2-b2a3-4a9a-9b34-38ce84c2571d
[1] ← 收到响应: 200 /api/storage/upload-status/4fa03c83-f7f4-4ad6-a8ed-fe17952dbb96
[1] ← 收到响应: 200 /api/storage/upload-status/47b1071d-9838-4f58-bada-e9fb745a8bd2
[1] ← 收到响应: 200 /api/storage/upload-status/1f86fdce-02e7-4c77-ad3b-b3dc4a878779