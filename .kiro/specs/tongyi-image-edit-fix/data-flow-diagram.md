# 通义图像编辑（Edit 模式）数据流程图

## 1. 当前实现流程（有问题）

```mermaid
flowchart TD
    Start[用户提交图像编辑请求] --> ReceiveInput[接收输入参数]
    
    ReceiveInput --> InputParams[输入参数:<br/>- modelId<br/>- prompt<br/>- referenceImage<br/>- options<br/>- apiKey<br/>- baseUrl]
    
    InputParams --> EnsureUrl[调用 ensureRemoteUrl 处理图片]
    
    EnsureUrl --> CheckUrlType{检查图片 URL 类型}
    
    CheckUrlType -->|https:// URL| TryDownload[尝试通过后端代理下载图片]
    CheckUrlType -->|oss:// URL| UseOssUrl[直接使用 oss:// URL]
    CheckUrlType -->|blob: URI| ConvertBlob[转换 blob 为 File]
    CheckUrlType -->|data: URI| ConvertData[转换 data URI 为 File]
    CheckUrlType -->|有 file 对象| UseFile[直接使用 File 对象]
    
    TryDownload --> DownloadProxy[fetch /api/storage/download]
    DownloadProxy --> DownloadSuccess{下载成功?}
    
    DownloadSuccess -->|成功| ConvertToFile[转换为 File 对象]
    DownloadSuccess -->|失败| FallbackUrl[回退到原始 https:// URL]
    
    ConvertToFile --> UploadToOss[调用 uploadDashScopeFile]
    ConvertBlob --> UploadToOss
    ConvertData --> UploadToOss
    UseFile --> UploadToOss
    
    UploadToOss --> UploadProcess[上传到 DashScope OSS]
    UploadProcess --> GetOssUrl[获取 oss:// URL]
    
    GetOssUrl --> BuildPayload[构建请求 payload]
    FallbackUrl --> BuildPayload
    UseOssUrl --> BuildPayload
    
    BuildPayload --> PayloadStructure[Payload 结构:<br/>model: modelId<br/>input.messages[0].content:<br/>  - image: imageUrl<br/>  - text: prompt<br/>parameters: {...}]
    
    PayloadStructure --> CallSubmitSync[调用 submitSync 函数]
    
    CallSubmitSync --> BuildHeaders[构建请求头]
    
    BuildHeaders --> HeaderStructure[请求头:<br/>Authorization: Bearer apiKey<br/>Content-Type: application/json<br/>X-DashScope-OssResourceResolve: enable]
    
    HeaderStructure --> HighlightProblem[❌ 问题所在:<br/>总是添加 OssResourceResolve<br/>无论 URL 是什么类型]
    
    HighlightProblem --> FetchAPI[发送 POST 请求到 DashScope API]
    
    FetchAPI --> APIEndpoint[API 端点:<br/>/api/v1/services/aigc/<br/>multimodal-generation/generation]
    
    APIEndpoint --> WaitResponse[等待 API 响应]
    
    WaitResponse --> CheckResponse{检查响应状态}
    
    CheckResponse -->|200 OK| ParseResponse[解析响应 JSON]
    CheckResponse -->|非 200| ParseError[解析错误信息]
    
    ParseError --> CheckErrorType{错误类型}
    
    CheckErrorType -->|403 权限错误| Return403[返回权限错误提示:<br/>- API Key 未开通权限<br/>- 账户余额不足<br/>- 模型未开通]
    CheckErrorType -->|下载超时| ReturnTimeout[❌ 返回下载超时错误:<br/>Download the media resource<br/>timed out]
    CheckErrorType -->|其他错误| ReturnOtherError[返回其他错误信息]
    
    ParseResponse --> FindUrl[查找图片 URL]
    
    FindUrl --> TryPaths[尝试多个可能的字段路径:<br/>1. output.results[0].url<br/>2. output.url<br/>3. output.output_image_url<br/>4. output.data.image_url]
    
    TryPaths --> UrlFound{找到 URL?}
    
    UrlFound -->|是| ReturnSuccess[返回成功结果:<br/>url: resultUrl<br/>mimeType: image/png]
    UrlFound -->|否| CheckTaskId{有 task_id?}
    
    CheckTaskId -->|是| ReturnAsyncError[返回错误:<br/>API 返回了异步任务 ID<br/>但当前使用同步模式]
    CheckTaskId -->|否| ReturnNoUrl[返回错误:<br/>API 返回成功但<br/>未找到图片 URL]
    
    ReturnSuccess --> End[结束]
    Return403 --> End
    ReturnTimeout --> End
    ReturnOtherError --> End
    ReturnAsyncError --> End
    ReturnNoUrl --> End
    
    style HighlightProblem fill:#FFB6C6
    style ReturnTimeout fill:#FFB6C6
    style FallbackUrl fill:#FFD700
    style ReturnSuccess fill:#90EE90
```

## 2. 关键代码位置

### 2.1 入口函数：`editWanxImage`

**文件**: `frontend/services/providers/tongyi/image-edit.ts`

```typescript
export async function editWanxImage(
    modelId: string,
    prompt: string,
    referenceImage: Attachment,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult> {
    
    // 步骤 1: 确保参考图片是远程 URL
    const imageUrl = await ensureRemoteUrl(referenceImage, apiKey, baseUrl);

    // 步骤 2: 构建 messages 格式的请求体
    const content: any[] = [];
    content.push({ image: imageUrl });
    if (prompt) {
        content.push({ text: prompt });
    }

    // 步骤 3: 构建完整的请求 payload
    const payload: any = {
        model: modelId,
        input: {
            messages: [
                {
                    role: "user",
                    content: content
                }
            ]
        },
        parameters: {
            n: Math.min(Math.max(options.numberOfImages || 1, 1), 4),
            negative_prompt: options.negativePrompt || undefined,
            prompt_extend: true,
            watermark: false
        }
    };

    // 步骤 4: 调用 API
    const url = resolveDashUrl(baseUrl || '', 'image-edit', modelId);
    
    try {
        return await submitSync(url, payload, apiKey);
    } catch (error: any) {
        // 错误处理
        if (error.message?.includes('403') || 
            error.message?.includes('not support')) {
            throw new Error('当前 API Key 无法使用图片编辑功能...');
        }
        throw error;
    }
}
```

### 2.2 图片 URL 处理：`ensureRemoteUrl`

**文件**: `frontend/services/providers/tongyi/image-utils.ts`

```typescript
export async function ensureRemoteUrl(
    attachment: Attachment, 
    apiKey: string, 
    baseUrl?: string
): Promise<string> {
    let imageUrl = attachment.url;
    const base64Data = (attachment as any).base64Data;
    
    // 情况 1: 已经是 HTTP/HTTPS URL
    if (imageUrl?.startsWith('http://') || imageUrl?.startsWith('https://')) {
        console.log('[ensureRemoteUrl] 检测到远程 URL，需要下载并上传到 DashScope OSS');
        
        try {
            // 通过后端代理下载图片
            const proxyUrl = `/api/storage/download?url=${encodeURIComponent(imageUrl)}`;
            const response = await fetch(proxyUrl);
            
            if (!response.ok) {
                throw new Error(`下载图片失败: ${response.status}`);
            }
            
            const blob = await response.blob();
            const fileName = attachment.name || 'image.png';
            const fileToUpload = new File([blob], fileName, { type: blob.type });
            
            // 上传到 DashScope OSS
            const ossUrl = await uploadDashScopeFile(fileToUpload, apiKey, baseUrl);
            return ossUrl;
        } catch (error: any) {
            console.error('[ensureRemoteUrl] 下载或上传失败:', error);
            // 回退到原始 URL
            console.warn('[ensureRemoteUrl] 回退到直接使用原始 URL');
            return imageUrl;
        }
    }

    // 情况 2: blob: 或 data: URI
    let fileToUpload = attachment.file;
    
    if (!fileToUpload && base64Data?.startsWith('data:')) {
        const res = await fetch(base64Data);
        const blob = await res.blob();
        fileToUpload = new File([blob], attachment.name || "temp_image.png", { type: blob.type });
    }
    
    if (!fileToUpload && imageUrl && (imageUrl.startsWith('blob:') || imageUrl.startsWith('data:'))) {
        const res = await fetch(imageUrl);
        const blob = await res.blob();
        fileToUpload = new File([blob], attachment.name || "temp_image.png", { type: blob.type });
    }
    
    if (fileToUpload) {
        imageUrl = await uploadDashScopeFile(fileToUpload, apiKey, baseUrl);
    }
    
    if (!imageUrl) throw new Error("Failed to upload image to DashScope OSS.");
    return imageUrl;
}
```

### 2.3 API 调用：`submitSync`

**文件**: `frontend/services/providers/tongyi/api.ts`

```typescript
export async function submitSync(
    endpoint: string, 
    payload: any, 
    apiKey: string
): Promise<ImageGenerationResult> {
    const safeKey = apiKey.trim();
    if (!safeKey) throw new Error("DashScope API Key is empty.");

    console.log('[DashScope] 使用同步模式调用 API');

    // ❌ 问题所在：总是添加 X-DashScope-OssResourceResolve
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${safeKey}`,
            'Content-Type': 'application/json',
            'X-DashScope-OssResourceResolve': 'enable' // ❌ 无条件添加
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ message: response.statusText }));
        const msg = err.message || err.code || response.status;
        throw new Error(`DashScope API Error: ${msg}`);
    }

    const data = await response.json();
    
    // 解析响应，查找图片 URL
    let resultUrl = null;
    
    if (data.output) {
        if (data.output.results && Array.isArray(data.output.results)) {
            resultUrl = data.output.results[0].url;
        }
        if (!resultUrl && data.output.url) {
            resultUrl = data.output.url;
        }
        if (!resultUrl && data.output.output_image_url) {
            resultUrl = data.output.output_image_url;
        }
        if (!resultUrl && data.output.data) {
            if (Array.isArray(data.output.data.image_url)) {
                resultUrl = data.output.data.image_url[0];
            } else if (data.output.data.image_url) {
                resultUrl = data.output.data.image_url;
            }
        }
    }
    
    if (!resultUrl) {
        throw new Error("API 返回成功但未找到图片 URL");
    }
    
    return {
        url: resultUrl,
        mimeType: 'image/png'
    };
}
```

## 3. 问题分析

### 3.1 核心问题

在 `submitSync` 函数中，**无条件地添加了 `X-DashScope-OssResourceResolve: enable` 请求头**。

### 3.2 问题影响

当用户使用普通 `https://` URL 进行图像编辑时：

1. `ensureRemoteUrl` 尝试下载并上传到 OSS
2. 如果下载失败，回退到原始 `https://` URL
3. `submitSync` 添加 `X-DashScope-OssResourceResolve: enable`
4. DashScope 尝试用 OSS 协议解析普通 HTTPS URL
5. **解析失败，返回 "Download the media resource timed out" 错误**

### 3.3 X-DashScope-OssResourceResolve 的作用

- 这个请求头用于访问 **DashScope 内部 OSS** 资源（`oss://` 格式）
- 对于普通 HTTPS URL，**不应该添加**这个请求头
- 如果错误地添加了，DashScope 会尝试用 OSS 协议解析，导致超时

## 4. 数据流详细说明

### 4.1 输入数据

```typescript
{
    modelId: "qwen-image-edit-plus-2025-10-30",
    prompt: "黑色头发",
    referenceImage: {
        id: "f5738452-9688-4654-965c-f70d086f7c68",
        url: "https://img.dicry.com/uploads/1766899793857_generated-1766899792116.png",
        uploadStatus: "completed"
    },
    options: {
        numberOfImages: 1,
        imageResolution: "1024*1024"
    },
    apiKey: "sk-xxx...",
    baseUrl: "https://dashscope.aliyuncs.com"
}
```

### 4.2 处理后的 Payload

```json
{
    "model": "qwen-image-edit-plus-2025-10-30",
    "input": {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "image": "https://img.dicry.com/uploads/1766899793857_generated-1766899792116.png"
                    },
                    {
                        "text": "黑色头发"
                    }
                ]
            }
        ]
    },
    "parameters": {
        "n": 1,
        "negative_prompt": undefined,
        "prompt_extend": true,
        "watermark": false
    }
}
```

### 4.3 实际发送的请求

```http
POST /api/v1/services/aigc/multimodal-generation/generation HTTP/1.1
Host: dashscope.aliyuncs.com
Authorization: Bearer sk-xxx...
Content-Type: application/json
X-DashScope-OssResourceResolve: enable

{请求 payload}
```

### 4.4 错误响应

```json
{
    "code": "InvalidParameter.FileDownload",
    "message": "Download the media resource timed out during the data inspection process. For details, see: https://help.aliyun.com/zh/model-studio/error-code#download-error"
}
```

## 5. 涉及的文件清单

| 文件路径 | 作用 | 是否需要修改 |
|---------|------|------------|
| `frontend/services/providers/tongyi/image-edit.ts` | 图像编辑入口函数 | ✅ 是 |
| `frontend/services/providers/tongyi/api.ts` | API 调用封装（submitSync） | ✅ 是 |
| `frontend/services/providers/tongyi/image-utils.ts` | 图片 URL 处理工具 | ✅ 是 |
| `frontend/services/providers/interfaces.ts` | 类型定义 | ❌ 否 |
| `frontend/types/types.ts` | 类型定义 | ❌ 否 |

## 6. 日志追踪

根据提供的日志，完整的调用链路：

```
1. [ModeSelector] 当前模型: qwen-image-edit-plus-2025-10-30
2. [ImageEditView] handleSend 开始
3. [handleSend] 用户输入: 黑色头发
4. [prepareAttachmentForApi] 开始准备附件, imageUrl 类型: HTTP
5. [findAttachmentByUrl] ✅ 精确匹配成功
6. [prepareAttachmentForApi] ✅ 复用历史附件完成
7. [llmService.generateImage] 配置检查通过
8. [ensureRemoteUrl] 已有远程 URL，直接使用
9. [DashScope] 使用同步模式调用 API
10. ❌ POST http://192.168.50.22:5173/api/dashscope/... 400 (Bad Request)
11. ❌ Error: Download the media resource timed out
```

## 7. 总结

当前 Edit 模式的问题在于 `api.ts` 的 `submitSync` 函数无条件添加了 `X-DashScope-OssResourceResolve` 请求头，导致 DashScope 无法正确处理普通 HTTPS URL，从而返回下载超时错误。
