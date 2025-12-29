# 通义千问后端 API 文档

## 概述

本文档描述了通义千问后端 API 的使用方法。这些 API 提供了与 DashScope 服务的集成，支持聊天和模型列表功能。

## 基础信息

- **基础 URL**: `http://localhost:8000`
- **内容类型**: `application/json`
- **认证方式**: 通过请求参数传递 API Key

---

## API 端点

### 1. 聊天 API

#### `POST /api/chat/tongyi`

发起通义千问聊天请求，返回 SSE 流式响应。

**请求体**:

```json
{
  "modelId": "qwen-max",
  "messages": [
    {
      "role": "user",
      "content": "你好",
      "isError": false
    }
  ],
  "message": "请介绍一下你自己",
  "attachments": null,
  "options": {
    "enableSearch": false,
    "enableThinking": false,
    "temperature": 1.0,
    "maxTokens": null
  },
  "apiKey": "sk-xxxxxxxx"
}
```

**请求参数说明**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `modelId` | string | 是 | 模型 ID，如 `qwen-max`、`qwen-plus`、`qwen-vl-max` |
| `messages` | array | 是 | 历史消息列表 |
| `message` | string | 是 | 当前用户消息 |
| `attachments` | array | 否 | 当前消息的图片附件（视觉模型使用） |
| `options` | object | 是 | 聊天选项 |
| `apiKey` | string | 是 | DashScope API Key |

**消息对象 (`messages[]`)**:

| 字段 | 类型 | 描述 |
|------|------|------|
| `role` | string | 角色：`user`、`model`、`system` |
| `content` | string | 消息内容 |
| `isError` | boolean | 是否为错误消息（可选，默认 `false`） |
| `attachments` | array | 消息的图片附件（可选，视觉模型使用） |

**附件对象 (`attachments[]`)**:

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | string | 附件 ID |
| `mimeType` | string | MIME 类型，如 `image/jpeg` |
| `name` | string | 文件名 |
| `url` | string | 图片 URL（可选） |
| `tempUrl` | string | DashScope 上传的临时 URL（可选） |
| `fileUri` | string | 文件 URI（可选） |

**选项对象 (`options`)**:

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `enableSearch` | boolean | `false` | 是否启用网页搜索 |
| `enableThinking` | boolean | `false` | 是否启用思考模式 |
| `temperature` | number | `1.0` | 温度参数（0.0-2.0） |
| `maxTokens` | number | `null` | 最大输出 token 数 |

**响应格式**:

返回 `text/event-stream` 类型的 SSE 流式响应。

```
data: {"text": "你好", "chunk_type": "content"}

data: {"text": "！", "chunk_type": "content"}

data: {"text": "", "chunk_type": "done", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
```

**流式响应字段**:

| 字段 | 类型 | 描述 |
|------|------|------|
| `text` | string | 文本内容 |
| `chunk_type` | string | 块类型：`reasoning`、`content`、`done` |
| `usage` | object | Token 使用量（仅在 `done` 时返回） |
| `groundingMetadata` | object | 搜索结果（启用搜索时返回） |

**搜索结果格式 (`groundingMetadata`)**:

```json
{
  "groundingChunks": [
    {
      "web": {
        "uri": "https://example.com",
        "title": "示例网页"
      }
    }
  ]
}
```

**错误响应**:

```json
{
  "detail": "错误信息"
}
```

**状态码**:

| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 500 | 服务器错误 |

---

### 2. 模型列表 API

#### `GET /api/models/tongyi`

获取可用的通义千问模型列表。

**查询参数**:

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `apiKey` | string | 是 | DashScope API Key |
| `refresh` | boolean | 否 | 是否强制刷新缓存（默认 `false`） |

**请求示例**:

```
GET /api/models/tongyi?apiKey=sk-xxxxxxxx&refresh=false
```

**响应格式**:

```json
{
  "models": [
    {
      "id": "qwen-deep-research",
      "name": "Qwen Deep Research",
      "description": "Specialized model for deep web research and complex query resolution.",
      "capabilities": {
        "vision": false,
        "reasoning": true,
        "coding": true,
        "search": true
      },
      "baseModelId": "qwen-deep-research"
    },
    {
      "id": "qwen-max",
      "name": "Qwen Max",
      "description": "Alibaba's most capable large model. Excellent at complex reasoning.",
      "capabilities": {
        "vision": false,
        "reasoning": false,
        "coding": true,
        "search": true
      },
      "baseModelId": "qwen-max"
    }
  ]
}
```

**模型对象字段**:

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | string | 模型 ID |
| `name` | string | 模型显示名称 |
| `description` | string | 模型描述 |
| `capabilities` | object | 模型能力 |
| `baseModelId` | string | 基础模型 ID |

**能力对象 (`capabilities`)**:

| 字段 | 类型 | 描述 |
|------|------|------|
| `vision` | boolean | 是否支持视觉 |
| `reasoning` | boolean | 是否支持推理/思考 |
| `coding` | boolean | 是否支持编程 |
| `search` | boolean | 是否支持搜索 |

**缓存机制**:

- 模型列表默认缓存 1 小时
- 使用 `refresh=true` 参数可强制刷新缓存

**状态码**:

| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 500 | 服务器错误 |

---

## 使用示例

### JavaScript/TypeScript

```typescript
// 聊天请求
async function chat(message: string, apiKey: string) {
  const response = await fetch('/api/chat/tongyi', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      modelId: 'qwen-max',
      messages: [],
      message: message,
      options: {
        enableSearch: false,
        enableThinking: false,
        temperature: 1.0,
      },
      apiKey: apiKey,
    }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader!.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        console.log(data.text);
      }
    }
  }
}

// 获取模型列表
async function getModels(apiKey: string) {
  const response = await fetch(`/api/models/tongyi?apiKey=${apiKey}`);
  const data = await response.json();
  return data.models;
}
```

### Python

```python
import requests
import json

# 聊天请求
def chat(message: str, api_key: str):
    response = requests.post(
        'http://localhost:8000/api/chat/tongyi',
        json={
            'modelId': 'qwen-max',
            'messages': [],
            'message': message,
            'options': {
                'enableSearch': False,
                'enableThinking': False,
                'temperature': 1.0,
            },
            'apiKey': api_key,
        },
        stream=True,
    )

    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                print(data['text'], end='', flush=True)

# 获取模型列表
def get_models(api_key: str):
    response = requests.get(
        f'http://localhost:8000/api/models/tongyi?apiKey={api_key}'
    )
    return response.json()['models']
```

### cURL

```bash
# 聊天请求
curl -X POST http://localhost:8000/api/chat/tongyi \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "qwen-max",
    "messages": [],
    "message": "你好",
    "options": {
      "enableSearch": false,
      "enableThinking": false,
      "temperature": 1.0
    },
    "apiKey": "sk-xxxxxxxx"
  }'

# 获取模型列表
curl "http://localhost:8000/api/models/tongyi?apiKey=sk-xxxxxxxx"
```

---

## 支持的模型

### 文本模型

| 模型 ID | 名称 | 能力 |
|---------|------|------|
| `qwen-deep-research` | Qwen Deep Research | 推理、编程、搜索 |
| `qwq-32b` | Qwen QwQ 32B | 推理、编程 |
| `qwen-max` | Qwen Max | 编程、搜索 |
| `qwen-plus` | Qwen Plus | 编程、搜索 |
| `qwen-turbo` | Qwen Turbo | 编程、搜索 |

### 视觉模型

| 模型 ID | 名称 | 能力 |
|---------|------|------|
| `qwen-vl-max` | Qwen VL Max | 视觉、编程 |
| `qwen-vl-max-latest` | Qwen VL Max Latest | 视觉、编程 |
| `qwen-vl-plus` | Qwen VL Plus | 视觉、编程 |
| `qwen2-vl-72b-instruct` | Qwen2 VL 72B | 视觉、编程 |
| `qwen2-vl-7b-instruct` | Qwen2 VL 7B | 视觉、编程 |
| `qwen2.5-vl-72b-instruct` | Qwen2.5 VL 72B | 视觉、编程 |
| `qwen2.5-vl-32b-instruct` | Qwen2.5 VL 32B | 视觉、编程 |
| `qwen2.5-vl-7b-instruct` | Qwen2.5 VL 7B | 视觉、编程 |

---

## 视觉模型使用示例

### 请求示例

```json
{
  "modelId": "qwen-vl-max",
  "messages": [],
  "message": "描述这张图片",
  "attachments": [
    {
      "id": "img-001",
      "mimeType": "image/jpeg",
      "name": "photo.jpg",
      "url": "https://example.com/image.jpg"
    }
  ],
  "options": {
    "enableSearch": false,
    "enableThinking": false,
    "temperature": 1.0
  },
  "apiKey": "sk-xxxxxxxx"
}
```

### JavaScript 示例

```typescript
async function chatWithImage(message: string, imageUrl: string, apiKey: string) {
  const response = await fetch('/api/chat/tongyi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      modelId: 'qwen-vl-max',
      messages: [],
      message: message,
      attachments: [
        {
          id: 'img-001',
          mimeType: 'image/jpeg',
          name: 'image.jpg',
          url: imageUrl,
        },
      ],
      options: {
        enableSearch: false,
        enableThinking: false,
        temperature: 1.0,
      },
      apiKey: apiKey,
    }),
  });

  // 处理流式响应...
}
```

### cURL 示例

```bash
curl -X POST http://localhost:8000/api/chat/tongyi \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "qwen-vl-max",
    "messages": [],
    "message": "描述这张图片",
    "attachments": [
      {
        "id": "img-001",
        "mimeType": "image/jpeg",
        "name": "photo.jpg",
        "url": "https://example.com/image.jpg"
      }
    ],
    "options": {
      "enableSearch": false,
      "enableThinking": false,
      "temperature": 1.0
    },
    "apiKey": "sk-xxxxxxxx"
  }'
```

---

## 错误处理

所有 API 在发生错误时返回 HTTP 500 状态码，响应体包含错误详情：

```json
{
  "detail": "错误描述信息"
}
```

常见错误：

| 错误 | 描述 | 解决方案 |
|------|------|----------|
| Invalid API Key | API Key 无效 | 检查 API Key 是否正确 |
| Model not found | 模型不存在 | 使用有效的模型 ID |
| Rate limit exceeded | 超出速率限制 | 降低请求频率 |
| Network error | 网络错误 | 检查网络连接 |

---

## 注意事项

1. **API Key 安全**: 不要在前端代码中硬编码 API Key
2. **流式响应**: 聊天 API 返回 SSE 流，需要正确处理流式数据
3. **缓存**: 模型列表有 1 小时缓存，如需最新数据请使用 `refresh=true`
4. **CORS**: 后端已配置 CORS，支持 `localhost:5173` 和 `localhost:3000`
