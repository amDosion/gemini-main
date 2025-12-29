# 通义千问前端迁移指南

## 概述

本指南描述前端如何通过后端 API 访问 DashScope 服务。迁移后，前端使用相对路径调用后端 API，由 Vite 开发服务器代理转发请求。

## 迁移目标

- **解决 CORS 问题**：浏览器直接调用 DashScope API 会遇到跨域限制
- **提高安全性**：API Key 不再暴露在前端代码中（后续优化）
- **统一管理**：后端可以统一管理日志、限流、缓存等功能

---

## 架构对比

### 迁移前（直接调用）

```
┌─────────┐     CORS 问题      ┌─────────────┐
│  前端   │ ───────────────→  │  DashScope  │
│ Browser │                    │    API      │
└─────────┘                    └─────────────┘
```

### 迁移后（后端代理）

```
┌─────────┐                ┌─────────┐                ┌─────────────┐
│  前端   │ ────────────→  │  后端   │ ────────────→  │  DashScope  │
│ Browser │   Vite 代理    │  API    │                │    API      │
└─────────┘                └─────────┘                └─────────────┘
```

---

## 实现方式

### 核心原则

1. **使用相对路径**：前端直接调用 `/api/chat/tongyi` 和 `/api/models/tongyi`
2. **Vite 代理转发**：开发环境由 Vite 代理转发到后端 `http://localhost:8000`
3. **无环境变量开关**：不使用环境变量控制两套逻辑，避免代码复杂化
4. **失败即报错**：后端 API 失败直接抛出错误，不回退到直接调用

### Vite 代理配置

`vite.config.ts` 已配置 `/api` 代理：

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    }
  },
});
```

---

## 前端实现

### `DashScopeProvider.ts` 核心代码

```typescript
export class DashScopeProvider extends OpenAIProvider implements ILLMProvider {
  public id = 'tongyi'; 
  
  // 获取模型列表 - 调用后端 API
  public async getAvailableModels(apiKey: string, _baseUrl: string): Promise<ModelConfig[]> {
    const response = await fetch(`/api/models/tongyi?apiKey=${encodeURIComponent(apiKey)}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `API error (${response.status})`);
    }
    const data = await response.json();
    return data.models;
  }

  // 发送消息 - 调用后端 API（支持文本和视觉模型）
  public async *sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    _baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
    // 统一使用后端 API（包括视觉模型）
    const response = await fetch('/api/chat/tongyi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        modelId,
        messages: history.map(msg => ({
          role: msg.role,
          content: msg.content,
          isError: msg.isError || false,
          attachments: msg.attachments?.map(att => ({
            id: att.id,
            mimeType: att.mimeType,
            name: att.name,
            url: att.url,
            tempUrl: att.tempUrl,
            fileUri: att.fileUri,
          })),
        })),
        message,
        attachments: attachments?.map(att => ({
          id: att.id,
          mimeType: att.mimeType,
          name: att.name,
          url: att.url,
          tempUrl: att.tempUrl,
          fileUri: att.fileUri,
        })),
        options: {
          enableSearch: options.enableSearch || false,
          enableThinking: options.enableThinking || false,
          temperature: 1.0,
          maxTokens: null,
        },
        apiKey,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `API error (${response.status})`);
    }

    // 解析 SSE 流式响应
    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6)) as StreamUpdate;
          } catch {}
        }
      }
    }
  }
}
```

---

## 视觉模型支持

### 后端实现

后端使用 DashScope 原生 `MultiModalConversation` API 支持视觉模型（`qwen-vl-*`）：

```python
from dashscope import MultiModalConversation

# 多模态消息格式
messages = [
    {
        "role": "user",
        "content": [
            {"image": "http://xxx.jpg"},  # 图片 URL
            {"text": "描述这张图片"}       # 文本
        ]
    }
]

# 流式调用
responses = MultiModalConversation.call(
    model="qwen-vl-max",
    messages=messages,
    stream=True,
    incremental_output=True
)
```

### 前端附件传递

前端通过 `attachments` 字段传递图片附件：

```typescript
// 请求体
{
  modelId: "qwen-vl-max",
  messages: [...],
  message: "描述这张图片",
  attachments: [
    {
      id: "xxx",
      mimeType: "image/jpeg",
      name: "photo.jpg",
      url: "http://xxx.jpg",      // 图片 URL
      tempUrl: "http://yyy.jpg",  // DashScope 上传的临时 URL
    }
  ],
  options: {...},
  apiKey: "sk-xxx"
}
```

### 支持的视觉模型

| 模型 | 说明 |
|------|------|
| `qwen-vl-max` | 最强视觉模型 |
| `qwen-vl-max-latest` | 最新版本 |
| `qwen-vl-plus` | 平衡版本 |
| `qwen2-vl-72b-instruct` | Qwen2 VL 72B |
| `qwen2-vl-7b-instruct` | Qwen2 VL 7B |
| `qwen2.5-vl-72b-instruct` | Qwen2.5 VL 72B |
| `qwen2.5-vl-32b-instruct` | Qwen2.5 VL 32B |
| `qwen2.5-vl-7b-instruct` | Qwen2.5 VL 7B |

---

## 验证迁移

### 1. 启动后端服务

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端服务

```bash
cd frontend
npm run dev
```

### 3. 测试功能

| 功能 | 测试方法 | 预期结果 |
|------|---------|---------|
| 模型列表 | 打开设置页面 | 通义千问模型列表正常加载 |
| 聊天功能 | 发送消息 | 流式响应正常显示 |
| 搜索功能 | 启用搜索发送消息 | 搜索结果正常显示 |
| 思考模式 | 使用 QwQ 模型 | 思考过程正常显示 |
| 视觉模型 | 上传图片并提问 | 图片理解正常工作 |

---

## 功能支持状态

| 功能 | 后端 API | 说明 |
|------|---------|------|
| 文本聊天 | ✅ 支持 | 所有文本模型 |
| 流式响应 | ✅ 支持 | SSE 格式 |
| 网页搜索 | ✅ 支持 | `enableSearch` 参数 |
| 思考模式 | ✅ 支持 | `enableThinking` 参数 |
| 视觉模型 | ✅ 支持 | 使用 `MultiModalConversation` API |
| 图像生成 | ❌ 不支持 | 直接调用 DashScope |
| 文件上传 | ❌ 不支持 | 直接调用 DashScope |

---

## 后续优化

1. **API Key 后端化**：将 API Key 存储在后端，前端不再传递
2. **图像生成支持**：后端添加图像生成 API
3. **生产环境部署**：配置 Nginx 反向代理
