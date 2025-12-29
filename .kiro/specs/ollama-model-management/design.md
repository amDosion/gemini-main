# Design Document

## Overview

本设计文档描述了 Ollama 模型管理功能的技术实现方案。该功能允许用户在设置界面中管理 Ollama 模型，包括查看本地模型列表、下载新模型、删除模型和查看模型详情。

系统采用前后端分离架构：
- **前端**：React 组件集成到 `EditorTab.tsx`，提供模型管理 UI
- **后端**：FastAPI 路由封装 Ollama 原生 API，提供 RESTful 接口

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
├─────────────────────────────────────────────────────────────────┤
│  EditorTab.tsx                                                   │
│  ├── OllamaModelManager.tsx (新组件)                             │
│  │   ├── ModelList (模型列表)                                    │
│  │   ├── ModelPullForm (下载表单)                                │
│  │   ├── ModelDetails (模型详情)                                 │
│  │   └── PullProgress (下载进度)                                 │
│  └── 现有配置表单                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│  /api/ollama/models          GET    - 获取模型列表               │
│  /api/ollama/models/{name}   GET    - 获取模型详情               │
│  /api/ollama/models/{name}   DELETE - 删除模型                   │
│  /api/ollama/pull            POST   - 下载模型 (SSE 流式)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Ollama Service                               │
├─────────────────────────────────────────────────────────────────┤
│  /api/tags    - 列出本地模型                                     │
│  /api/show    - 模型详情                                         │
│  /api/delete  - 删除模型                                         │
│  /api/pull    - 下载模型 (流式)                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### Frontend Components

#### 1. OllamaModelManager

主容器组件，管理模型管理功能的状态和子组件。

```typescript
interface OllamaModelManagerProps {
    baseUrl: string;      // Ollama API 地址
    apiKey?: string;      // API Key (可选)
    onModelSelect?: (modelId: string) => void;  // 模型选择回调
}

interface OllamaModelManagerState {
    models: OllamaModel[];           // 本地模型列表
    isLoading: boolean;              // 加载状态
    error: string | null;            // 错误信息
    pullProgress: PullProgress | null;  // 下载进度
    selectedModel: OllamaModel | null;  // 选中的模型
}
```

#### 2. ModelList

显示本地模型列表的组件。

```typescript
interface ModelListProps {
    models: OllamaModel[];
    onSelect: (model: OllamaModel) => void;
    onDelete: (modelName: string) => void;
    isLoading: boolean;
}
```

#### 3. ModelPullForm

模型下载表单组件。

```typescript
interface ModelPullFormProps {
    onPull: (modelName: string) => void;
    isPulling: boolean;
    disabled?: boolean;
}
```

#### 4. PullProgress

下载进度显示组件。

```typescript
interface PullProgressProps {
    progress: PullProgress;
    onCancel?: () => void;
}

interface PullProgress {
    status: string;           // 状态描述
    digest?: string;          // 当前下载的文件摘要
    total?: number;           // 总大小 (bytes)
    completed?: number;       // 已完成大小 (bytes)
    percent?: number;         // 百分比
}
```

### Backend API Endpoints

#### 1. GET /api/ollama/models

获取本地模型列表。

**Request:**
```
GET /api/ollama/models?base_url={ollama_url}&api_key={key}
```

**Response:**
```json
{
    "models": [
        {
            "name": "llama3:latest",
            "model": "llama3:latest",
            "size": 4661224676,
            "digest": "sha256:...",
            "modified_at": "2024-01-15T10:30:00Z",
            "details": {
                "format": "gguf",
                "family": "llama",
                "parameter_size": "8B",
                "quantization_level": "Q4_K_M"
            }
        }
    ]
}
```

#### 2. GET /api/ollama/models/{name}

获取模型详情。

**Request:**
```
GET /api/ollama/models/llama3:latest?base_url={ollama_url}&api_key={key}
```

**Response:**
```json
{
    "modelfile": "...",
    "parameters": "...",
    "template": "...",
    "details": {
        "format": "gguf",
        "family": "llama",
        "parameter_size": "8B",
        "quantization_level": "Q4_K_M"
    },
    "model_info": {
        "general.architecture": "llama",
        "llama.context_length": 8192
    },
    "capabilities": ["completion", "vision"]
}
```

#### 3. DELETE /api/ollama/models/{name}

删除模型。

**Request:**
```
DELETE /api/ollama/models/llama3:latest?base_url={ollama_url}&api_key={key}
```

**Response:**
```json
{
    "success": true,
    "message": "Model deleted successfully"
}
```

#### 4. POST /api/ollama/pull

下载模型（SSE 流式响应）。

**Request:**
```
POST /api/ollama/pull
Content-Type: application/json

{
    "model": "llama3:latest",
    "base_url": "http://localhost:11434",
    "api_key": "optional_key"
}
```

**Response (SSE):**
```
data: {"status": "pulling manifest"}
data: {"status": "pulling sha256:abc...", "digest": "sha256:abc...", "total": 1000000, "completed": 500000}
data: {"status": "verifying sha256:abc..."}
data: {"status": "writing manifest"}
data: {"status": "success"}
```

## Data Models

### OllamaModel

```typescript
interface OllamaModel {
    name: string;              // 模型名称 (如 "llama3:latest")
    model: string;             // 模型标识符
    size: number;              // 模型大小 (bytes)
    digest: string;            // SHA256 摘要
    modified_at: string;       // 修改时间 (ISO 8601)
    details: OllamaModelDetails;
}

interface OllamaModelDetails {
    format: string;            // 格式 (如 "gguf")
    family: string;            // 模型家族 (如 "llama")
    parameter_size: string;    // 参数量 (如 "8B")
    quantization_level: string; // 量化级别 (如 "Q4_K_M")
}
```

### OllamaModelInfo

```typescript
interface OllamaModelInfo {
    modelfile: string;         // Modelfile 内容
    parameters: string;        // 参数字符串
    template: string;          // 提示词模板
    details: OllamaModelDetails;
    model_info: Record<string, any>;  // 模型架构信息
    capabilities: string[];    // 能力列表 (如 ["completion", "vision"])
}
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Provider-based Component Rendering

*For any* provider selection in EditorTab, the OllamaModelManager component SHALL be rendered if and only if the providerId is 'ollama'.

**Validates: Requirements 1.1, 5.1, 5.2**

### Property 2: Model List Display Completeness

*For any* model returned from the Ollama API, the ModelList component SHALL display the model's name, size (formatted), and modification time.

**Validates: Requirements 1.4**

### Property 3: Pull Request Initiation

*For any* valid model name entered by the user, clicking the download button SHALL trigger a POST request to `/api/ollama/pull` with the correct model name and base URL.

**Validates: Requirements 2.1**

### Property 4: Progress Display During Download

*For any* SSE progress event received during model download, the PullProgress component SHALL display the current status, and if available, the percentage, completed size, and total size.

**Validates: Requirements 2.2**

### Property 5: Delete API Call After Confirmation

*For any* model deletion confirmed by the user, the system SHALL send a DELETE request to `/api/ollama/models/{name}` with the correct model name.

**Validates: Requirements 3.2**

### Property 6: Model Details Display

*For any* model selected by the user, the ModelDetails component SHALL display the model's family, parameter size, quantization level, and capabilities array.

**Validates: Requirements 4.1, 4.2**

### Property 7: Backend Model List Endpoint

*For any* GET request to `/api/ollama/models`, the backend SHALL return a JSON response containing a `models` array where each model has `name`, `size`, `digest`, `modified_at`, and `details` fields.

**Validates: Requirements 6.1**

### Property 8: Backend Pull Endpoint Streaming

*For any* POST request to `/api/ollama/pull` with a valid model name, the backend SHALL return an SSE stream with progress events containing `status` field.

**Validates: Requirements 6.2**

### Property 9: Backend Delete Endpoint

*For any* DELETE request to `/api/ollama/models/{name}`, the backend SHALL return a JSON response with `success` boolean and `message` string.

**Validates: Requirements 6.3**

### Property 10: Backend Model Details Endpoint

*For any* GET request to `/api/ollama/models/{name}`, the backend SHALL return a JSON response containing `details`, `model_info`, and `capabilities` fields.

**Validates: Requirements 6.4**

## Error Handling

### Frontend Error Handling

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| Ollama service unavailable | Display connection error message with retry button |
| Model list fetch failed | Show error state with "Retry" option |
| Model download failed | Display error message from API, allow retry |
| Model deletion failed | Show error notification, keep model in list |
| Network timeout | Display timeout message with retry option |
| Invalid model name | Show validation error before API call |

### Backend Error Handling

| Error Scenario | HTTP Status | Response |
|----------------|-------------|----------|
| Ollama service unavailable | 503 | `{"error": "Ollama service unavailable", "detail": "..."}` |
| Model not found | 404 | `{"error": "Model not found", "model": "..."}` |
| Invalid request | 400 | `{"error": "Invalid request", "detail": "..."}` |
| Pull failed | 500 | SSE event: `{"status": "error", "error": "..."}` |
| Delete failed | 500 | `{"success": false, "error": "..."}` |

### Error Recovery

1. **Connection Errors**: Implement exponential backoff retry (max 3 attempts)
2. **Partial Downloads**: Ollama API supports resume, frontend should retry automatically
3. **State Inconsistency**: Refresh model list after any mutation operation

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

1. **Component Rendering Tests**
   - OllamaModelManager renders when providerId is 'ollama'
   - OllamaModelManager does not render for other providers
   - Loading state displays spinner
   - Empty state displays guidance message

2. **API Integration Tests**
   - Model list endpoint returns correct format
   - Model details endpoint returns capabilities
   - Delete endpoint removes model
   - Pull endpoint streams progress

3. **Error Handling Tests**
   - Connection error displays error message
   - Download failure shows error notification
   - Delete failure keeps model in list

### Property-Based Tests

Property-based tests verify universal properties across all inputs:

1. **Property Test: Provider Rendering**
   - Generate random provider IDs
   - Verify OllamaModelManager visibility matches (providerId === 'ollama')

2. **Property Test: Model Display Completeness**
   - Generate random OllamaModel objects
   - Verify rendered output contains name, size, modified_at

3. **Property Test: Progress Event Handling**
   - Generate random progress events with varying fields
   - Verify PullProgress displays available information correctly

4. **Property Test: API Response Format**
   - Generate random model data
   - Verify backend response matches expected schema

### Test Configuration

- **Testing Framework**: Vitest (frontend), pytest (backend)
- **Property Testing Library**: fast-check (frontend), hypothesis (backend)
- **Minimum Iterations**: 100 per property test
- **Mocking**: MSW for frontend API mocking, pytest-httpx for backend

### Test File Structure

```
frontend/
├── components/modals/settings/
│   ├── OllamaModelManager.tsx
│   └── OllamaModelManager.test.tsx
└── services/providers/ollama/
    ├── ollamaApi.ts
    └── ollamaApi.test.ts

backend/
├── app/routers/
│   ├── ollama_models.py
│   └── test_ollama_models.py
└── app/services/ollama/
    └── test_ollama_service.py
```
