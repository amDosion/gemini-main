react-dom_client.js?v=5d683dc1:20103 Download the React DevTools for a better development experience: https://react.dev/link/react-devtools
db.ts:248 ✅ 后端 API 已连接 - 使用数据库存储 (PostgreSQL/SQLite)
ImageExpandView.tsx:165 ========== [ImageExpandView] handleSend 开始 ==========
ImageExpandView.tsx:166 [handleSend] 用户上传的附件数量: 1
ImageExpandView.tsx:167 [handleSend] 当前 sessionId: 8f8b222d-669e-4535-b113-9865f83e9009
ImageExpandView.tsx:168 [handleSend] 当前 activeImageUrl: blob:http://192.168.50.22:5173/8e9dcf9b-2cc2-4daa-8f6c-0c487a1fea8d...
ImageExpandView.tsx:174 [handleSend] activeImageUrl 类型: Blob URL
ImageExpandView.tsx:305 [handleSend] 未触发 CONTINUITY LOGIC，原因: 用户已上传新图片
ImageExpandView.tsx:310 [handleSend] 最终附件数量: 1
ImageExpandView.tsx:312 [handleSend] 最终附件详情: [{…}]
ImageExpandView.tsx:322 ========== [ImageExpandView] handleSend 结束，调用 onSend ==========
useChat.ts:247 [useChat] image-outpainting 原图 URL: blob:http://192.168.50.22:5173/8e9dcf9b-2cc2-4daa-8f6c-0c487
useChat.ts:248 [useChat] 原图是否已是云存储 URL: false
image-utils.ts:44 [ensureRemoteUrl] 上传文件到 DashScope OSS: image-1765850514661.png
api.ts:79 [DashScope Upload] Starting upload process...
api.ts:80 [DashScope Upload] File: image-1765850514661.png Size: 695960 bytes
api.ts:86 [DashScope Upload] Using backend proxy...
api.ts:87 [DashScope Upload] Proxy URL: /api/dashscope/api/v1/files
api.ts:117 [DashScope Upload] ✅ Upload successful!
api.ts:118 [DashScope Upload] OSS URL: oss://dashscope-instant/f0bc24a7418605c14b93d14042dba644/2025-12-16/9a110038-440a-46d1-9182-8272db3edbfd/image-1765850514661.png
image-utils.ts:46 [ensureRemoteUrl] 上传完成: oss://dashscope-instant/f0bc24a7418605c14b93d14042dba644/202
image-expand.ts:59 [OutPainting] 调用后端扩图服务: oss://dashscope-instant/f0bc24a7418605c14b93d14042dba644/202
image-expand.ts:60 [OutPainting] 参数: {image_url: 'oss://dashscope-instant/f0bc24a7418605c14b93d14042…0a-46d1-9182-8272db3edbfd/image-1765850514661.png', api_key: 'sk-19e01649859646c1904ee21fa08dc3ef', mode: 'scale', x_scale: 2, y_scale: 2}api_key: "sk-19e01649859646c1904ee21fa08dc3ef"image_url: "oss://dashscope-instant/f0bc24a7418605c14b93d14042dba644/2025-12-16/9a110038-440a-46d1-9182-8272db3edbfd/image-1765850514661.png"mode: "scale"x_scale: 2y_scale: 2[[Prototype]]: Object
image-expand.ts:91 [OutPainting] 扩图成功: https://vigen-invi.oss-cn-shanghai.aliyuncs.com/service_dash
useChat.ts:269 [useChat] 结果图显示 URL: blob:http://192.168.50.22:5173/56b50c30-dd08-4e4d-
useChat.ts:276 [useChat] 上传原图到云存储...
attachmentUtils.ts:75 [uploadToCloudStorageSync] 开始同步上传: {type: 'File', filename: 'image-1765850514661.png'}filename: "image-1765850514661.png"type: "File"[[Prototype]]: Object
storageUpload.ts:52 ✅ [StorageUpload] 后端 API 可用 - 使用后端上传
attachmentUtils.ts:101 [uploadToCloudStorageSync] 上传成功: https://img.dicry.com/2025/12/16/6940bda010548.png
useChat.ts:281 [useChat] 原图云存储 URL: https://img.dicry.com/2025/12/16/6940bda010548.png
useChat.ts:286 [useChat] 上传结果图到云存储...
attachmentUtils.ts:75 [uploadToCloudStorageSync] 开始同步上传: {type: 'File', filename: 'expanded-1765892883447.png'}
attachmentUtils.ts:101 [uploadToCloudStorageSync] 上传成功: https://img.dicry.com/2025/12/16/694163274c0cd.png
useChat.ts:289 [useChat] 结果图云存储 URL: https://img.dicry.com/2025/12/16/694163274c0cd.png
