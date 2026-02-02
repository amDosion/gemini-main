# 前端大小写命名分析报告

## 分析范围

检查前端代码中与后端 API 交互的所有字段命名，确认是否符合 camelCase 规范。

## 总体结论

前端**大部分**使用 camelCase，但存在**部分不一致**的情况。

---

## ✅ 符合规范的部分

### 1. TypeScript 接口定义
大部分接口使用 camelCase：

```typescript
// frontend/types/types.ts
interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: number;
  isError?: boolean;        // ✅ camelCase
  attachments?: Attachment[];
}

// frontend/services/auth.ts
interface LoginResponse {
  user: User;
  accessToken: string;      // ✅ camelCase
  refreshToken: string;
}
```

### 2. API 请求体
大部分请求体使用 camelCase：

```typescript
// frontend/services/db.ts
body: JSON.stringify({ id })  // ✅ camelCase

// frontend/services/auth.ts
body: JSON.stringify({
  email: data.email,          // ✅ camelCase
  password: data.password,
})
```

---

## ❌ 不符合规范的部分

### 1. InteractionsClient.ts - 接口定义使用 snake_case

**文件**: `frontend/services/InteractionsClient.ts`

```typescript
// ❌ 错误：接口字段使用 snake_case
export interface CreateInteractionParams {
  previous_interaction_id?: string;  // ❌ 应为 previousInteractionId
  generation_config?: GenerationConfig;  // ❌ 应为 generationConfig
  system_instruction?: string;  // ❌ 应为 systemInstruction
  response_format?: Record<string, any>;  // ❌ 应为 responseFormat
}

export interface Content {
  mime_type?: string;  // ❌ 应为 mimeType
}

export interface GenerationConfig {
  max_outputTokens?: number;  // ❌ 应为 maxOutputTokens
  thinking_level?: string;  // ❌ 应为 thinkingLevel
  top_p?: number;  // ❌ 应为 topP
  top_k?: number;  // ❌ 应为 topK
}
```

### 2. MultiAgentHandler.ts - 请求体使用 snake_case

**文件**: `frontend/hooks/handlers/MultiAgentHandler.ts`

```typescript
// ❌ 错误：请求体字段使用 snake_case
body: JSON.stringify({
  task: taskDescription,
  agent_ids: agentIds.length > 0 ? agentIds : undefined  // ❌ 应为 agentIds
}),
```

### 3. MultiAgentView.tsx - 请求体使用 snake_case

**文件**: `frontend/components/views/MultiAgentView.tsx`

```typescript
// ❌ 错误：请求体字段使用 snake_case
body: JSON.stringify({
  task: taskDescription || '执行多智能体工作流',
  agent_ids: agentIds.length > 0 ? agentIds : undefined  // ❌ 应为 agentIds
}),
```

### 4. storageUpload.ts - URL 参数使用 snake_case ✅ 正确

**文件**: `frontend/services/storage/storageUpload.ts`

```typescript
// ✅ 正确：URL Query 参数使用 snake_case（中间件不转换 URL 参数）
const params = new URLSearchParams();
params.append('session_id', options.sessionId);      // ✅ 后端期望 snake_case
params.append('message_id', options.messageId);      // ✅ 后端期望 snake_case
params.append('attachment_id', options.attachmentId); // ✅ 后端期望 snake_case
params.append('storage_id', options.storageId);      // ✅ 后端期望 snake_case
```

### 5. workflowTemplateService.ts - URL 参数使用 snake_case ✅ 正确

**文件**: `frontend/services/workflowTemplateService.ts`

```typescript
// ✅ 正确：URL Query 参数使用 snake_case（中间件不转换 URL 参数）
params.append('workflow_type', options.workflowType);  // ✅ 后端期望 snake_case
params.append('include_public', String(options.includePublic));  // ✅ 后端期望 snake_case
```

---

## 问题分析

### 为什么会出现 snake_case？

1. **直接对接后端 API**：部分代码直接使用后端期望的 snake_case 字段名，绕过了中间件转换
2. **URL Query 参数**：中间件只转换 JSON body，不转换 URL 参数
3. **历史遗留**：部分代码在中间件引入前编写

### 中间件的转换范围

`CaseConversionMiddleware` 只转换：
- ✅ JSON 请求体 (POST/PUT/PATCH body)
- ✅ JSON 响应体

不转换：
- ❌ URL Query 参数 (`?session_id=xxx`)
- ❌ URL Path 参数 (`/api/sessions/{session_id}`)
- ❌ FormData

---

## 修复建议

### 方案 A：前端统一使用 camelCase + 后端处理 Query 参数

1. 前端所有字段统一使用 camelCase
2. 后端 Query 参数接受 camelCase（FastAPI 支持 alias）
3. 或扩展中间件支持 Query 参数转换

### 方案 B：保持现状，明确约定

1. JSON body：使用 camelCase（中间件转换）
2. URL Query 参数：使用 snake_case（直接传递）
3. 在文档中明确这个约定

---

## 需要修复的文件清单

| 文件 | 问题类型 | 状态 |
|------|----------|------|
| `frontend/services/InteractionsClient.ts` | 接口定义 snake_case | ✅ 已修复 |
| `frontend/hooks/handlers/MultiAgentHandler.ts` | 请求体 snake_case | ✅ 已修复 |
| `frontend/components/views/MultiAgentView.tsx` | 请求体 snake_case | ✅ 已修复 |
| `frontend/services/storage/storageUpload.ts` | URL 参数 snake_case | ✅ 正确（URL 参数不经过中间件） |
| `frontend/services/workflowTemplateService.ts` | URL 参数 snake_case | ✅ 正确（URL 参数不经过中间件） |

---

## 建议的统一规范

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (TypeScript)                       │
│  - 所有接口字段：camelCase                                    │
│  - JSON 请求体：camelCase（中间件自动转换）                    │
│  - URL Query 参数：snake_case（直接传给后端，不经过中间件）    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  CaseConversionMiddleware                    │
│  - 请求 JSON body：camelCase → snake_case ✅                 │
│  - 响应 JSON body：snake_case → camelCase ✅                 │
│  - URL Query 参数：不转换 ❌                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      后端 (Python)                           │
│  - Pydantic 模型：snake_case                                 │
│  - SQLAlchemy 列：snake_case                                 │
│  - Query 参数：snake_case                                    │
└─────────────────────────────────────────────────────────────┘
```

---

创建日期：2026-01-31
