# Gemini Deep Research Agent 完整开发指南

> **版本**: v1.0  
> **更新日期**: 2025-12-20  
> **适用范围**: 前端 TypeScript + 后端 Python 全栈实现

---

## 📋 目录

- [1. 概述](#1-概述)
- [2. 核心概念](#2-核心概念)
- [3. 技术架构](#3-技术架构)
- [4. 前端实现](#4-前端实现)
- [5. 后端实现](#5-后端实现)
- [6. 流式响应](#6-流式响应)
- [7. 错误处理](#7-错误处理)
- [8. 最佳实践](#8-最佳实践)
- [9. 安全考虑](#9-安全考虑)
- [10. 性能优化](#10-性能优化)
- [11. 测试策略](#11-测试策略)
- [12. 故障排查](#12-故障排查)

---

## 1. 概述

### 1.1 什么是 Deep Research Agent

`Deep Research Agent` 是 Google Gemini 提供的专门代理，用于自主规划、执行和综合多步骤研究任务。它由 **Gemini 3 Pro** 驱动，能够：

- 🤖 **自主规划**：自动制定研究计划
- 🔍 **多步骤搜索**：迭代搜索和阅读
- 📊 **详细报告**：生成带引用的长篇分析
- ⏱️ **长时间运行**：任务可能需要几分钟到60分钟
- 🔄 **异步执行**：必须使用后台模式
- 📝 **可控输出**：支持格式化和语气调整

### 1.2 关键特点

| 特性 | 标准 Gemini 模型 | Deep Research Agent |
|------|-----------------|---------------------|
| **延迟** | 秒级 | 分钟级（异步） |
| **流程** | 生成 → 输出 | 规划 → 搜索 → 阅读 → 迭代 → 输出 |
| **输出** | 对话文本、代码、摘要 | 详细报告、长篇分析、对比表格 |
| **适用场景** | 聊天机器人、提取、创意写作 | 市场分析、尽职调查、文献综述、竞争分析 |

### 1.3 核心约束

> ⚠️ **必须通过 Interactions API 访问**  
> Deep Research Agent 只能通过 Interactions API 使用，无法通过 `generate_content` 访问。

> ⚠️ **必须异步执行**  
> 研究任务涉及迭代搜索和阅读，通常超过标准 API 调用的超时限制。必须设置 `background=true`。

> ⚠️ **预览状态**  
> Deep Research Agent 目前处于预览阶段，功能可能会发生变化。

---

## 2. 核心概念

### 2.1 工作流程

```
用户输入研究查询
    ↓
Agent 分析查询并制定研究计划
    ↓
执行 google_search（多次）
    ↓
使用 url_context 访问相关网页
    ↓
迭代搜索和阅读（可能多轮）
    ↓
综合分析所有收集的信息
    ↓
生成详细的研究报告（带引用）
```

### 2.2 Interaction 对象

`Interaction` 是 Interactions API 的核心资源，代表对话或任务中的**完整一轮交互**。

```typescript
interface Interaction {
  id: string;                    // 唯一标识符
  agent: string;                 // 使用的代理（deep-research-pro-preview-12-2025）
  input: Content[];              // 用户输入
  outputs: Content[];            // 模型输出（数组，包含所有中间步骤）
  tools?: Tool[];                // 使用的工具
  previous_interaction_id?: string;  // 上一个交互的 ID
  stream?: boolean;              // 是否流式响应
  status: string;                // 状态：completed, in_progress, requires_action, failed
  background: boolean;           // 必须为 true
  store?: boolean;               // 是否存储（默认 true）
  usage?: Usage;                 // 令牌使用情况
}
```

### 2.3 状态流转

```
in_progress → completed
in_progress → failed
in_progress → cancelled
```

### 2.4 默认工具

Deep Research Agent 默认可以访问：
- ✅ `google_search`：搜索公网信息
- ✅ `url_context`：访问和理解网页内容

**注意**：这些工具是默认启用的，无需显式指定。

### 2.5 时间范围

| 任务复杂度 | 预期时间 |
|-----------|---------|
| 简单查询 | 2-5 分钟 |
| 中等复杂度 | 5-15 分钟 |
| 复杂研究 | 15-30 分钟 |
| 最大限制 | 60 分钟 |

---

## 3. 技术架构

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         前端层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  useChat.ts  │  │ GoogleProvider│  │  UI Components│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         后端层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  FastAPI     │  │  Redis Cache │  │  Database    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Gemini Interactions API                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Deep Research│  │ Google Search│  │  URL Context │      │
│  │    Agent     │  │     Tool     │  │     Tool     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
1. 用户输入 → 前端 useChat
2. 前端 → 后端 API (/api/research/start)
3. 后端 → Gemini Interactions API (background=true)
4. 后端 ← Gemini 返回 interaction_id
5. 后端 → 前端 返回 interaction_id
6. 前端 → 后端 轮询 (/api/research/status/{id})
7. 后端 → Gemini 查询状态
8. 后端 ← Gemini 返回状态和结果
9. 后端 → 前端 返回最终报告
```

### 3.3 技术栈

**前端**：
- TypeScript
- React Hooks
- Fetch API
- EventSource (SSE)

**后端**：
- Python 3.10+
- FastAPI
- google-genai SDK (>=1.55.0)
- Redis (可选，用于缓存)

---


## 4. 前端实现

### 4.1 核心 Hook 实现

#### 4.1.1 useDeepResearch Hook

```typescript
// hooks/useDeepResearch.ts
import { useState, useCallback } from 'react';

interface ResearchStatus {
  status: 'idle' | 'starting' | 'in_progress' | 'completed' | 'failed';
  interactionId?: string;
  progress?: string;
  result?: string;
  error?: string;
}

export const useDeepResearch = (apiKey: string) => {
  const [researchStatus, setResearchStatus] = useState<ResearchStatus>({
    status: 'idle'
  });

  // 启动研究任务
  const startResearch = useCallback(async (prompt: string, options?: {
    format?: string;
    includePrivateData?: boolean;
    fileSearchStoreNames?: string[];
  }) => {
    setResearchStatus({ status: 'starting' });

    try {
      // 1. 调用后端 API 启动研究
      const response = await fetch('/api/research/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          prompt,
          agent: 'deep-research-pro-preview-12-2025',
          background: true,
          ...options
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to start research: ${response.statusText}`);
      }

      const data = await response.json();
      const interactionId = data.interaction_id;

      setResearchStatus({
        status: 'in_progress',
        interactionId
      });

      // 2. 开始轮询状态
      pollResearchStatus(interactionId);

    } catch (error: any) {
      setResearchStatus({
        status: 'failed',
        error: error.message
      });
    }
  }, [apiKey]);

  // 轮询研究状态
  const pollResearchStatus = useCallback(async (interactionId: string) => {
    const pollInterval = 10000; // 10秒
    const maxPolls = 360; // 最多轮询60分钟

    for (let i = 0; i < maxPolls; i++) {
      try {
        const response = await fetch(`/api/research/status/${interactionId}`, {
          headers: {
            'Authorization': `Bearer ${apiKey}`
          }
        });

        if (!response.ok) {
          throw new Error(`Failed to get status: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.status === 'completed') {
          setResearchStatus({
            status: 'completed',
            interactionId,
            result: data.result
          });
          return;
        }

        if (data.status === 'failed') {
          setResearchStatus({
            status: 'failed',
            interactionId,
            error: data.error
          });
          return;
        }

        // 更新进度
        setResearchStatus(prev => ({
          ...prev,
          progress: data.progress || `研究进行中... (${i * pollInterval / 1000}s)`
        }));

        await new Promise(resolve => setTimeout(resolve, pollInterval));

      } catch (error: any) {
        setResearchStatus({
          status: 'failed',
          interactionId,
          error: error.message
        });
        return;
      }
    }

    // 超时
    setResearchStatus({
      status: 'failed',
      interactionId,
      error: '研究任务超时（超过60分钟）'
    });
  }, [apiKey]);

  // 取消研究任务
  const cancelResearch = useCallback(async () => {
    if (researchStatus.interactionId) {
      try {
        await fetch(`/api/research/cancel/${researchStatus.interactionId}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${apiKey}`
          }
        });
        setResearchStatus({ status: 'idle' });
      } catch (error) {
        console.error('Failed to cancel research:', error);
      }
    }
  }, [researchStatus.interactionId, apiKey]);

  return {
    researchStatus,
    startResearch,
    cancelResearch
  };
};
```

#### 4.1.2 集成到 useChat

```typescript
// hooks/useChat.ts (新增 Deep Research 模式)

export const useChat = (
  currentSessionId: string | null,
  updateSessionMessages: (id: string, msgs: Message[]) => void,
  apiKey?: string
) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingState, setLoadingState] = useState<LoadingState>('idle');
  const { researchStatus, startResearch, cancelResearch } = useDeepResearch(apiKey || '');

  const sendMessage = async (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode,
    currentModel: ModelConfig,
    protocol: 'google' | 'openai'
  ) => {
    if (!currentSessionId) return;

    // ... 现有代码 ...

    // 新增：Deep Research 模式
    if (mode === 'deep-research') {
      // 1. 添加用户消息
      const userMessage: Message = {
        id: uuidv4(),
        role: Role.USER,
        content: text,
        attachments: [],
        timestamp: Date.now(),
        mode: 'deep-research'
      };

      const updatedMessages = [...messages, userMessage];
      setMessages(updatedMessages);
      updateSessionMessages(currentSessionId, updatedMessages);
      setLoadingState('loading');

      // 2. 添加模型占位消息
      const modelMessageId = uuidv4();
      const initialModelMessage: Message = {
        id: modelMessageId,
        role: Role.MODEL,
        content: '🔍 正在启动深度研究...',
        attachments: [],
        timestamp: Date.now(),
        mode: 'deep-research'
      };

      setMessages(prev => [...prev, initialModelMessage]);

      // 3. 启动研究任务
      try {
        await startResearch(text, {
          format: options.researchFormat,
          includePrivateData: options.includePrivateData,
          fileSearchStoreNames: options.fileSearchStoreNames
        });

        // 4. 监听研究状态变化
        const unsubscribe = watchResearchStatus((status) => {
          if (status.status === 'in_progress') {
            setMessages(prev =>
              prev.map(msg =>
                msg.id === modelMessageId
                  ? { ...msg, content: `🔍 ${status.progress || '研究进行中...'}` }
                  : msg
              )
            );
          } else if (status.status === 'completed') {
            const finalMessages = [...updatedMessages, {
              ...initialModelMessage,
              content: status.result || '研究完成'
            }];
            setMessages(finalMessages);
            updateSessionMessages(currentSessionId, finalMessages);
            setLoadingState('idle');
          } else if (status.status === 'failed') {
            setMessages(prev =>
              prev.map(msg =>
                msg.id === modelMessageId
                  ? { ...msg, content: `❌ 研究失败: ${status.error}`, isError: true }
                  : msg
              )
            );
            setLoadingState('idle');
          }
        });

        return () => unsubscribe();

      } catch (error: any) {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === modelMessageId
              ? { ...msg, content: `❌ 启动研究失败: ${error.message}`, isError: true }
              : msg
          )
        );
        setLoadingState('idle');
      }
    }

    // ... 其他模式的现有代码 ...
  };

  return {
    messages,
    setMessages,
    loadingState,
    setLoadingState,
    sendMessage,
    stopGeneration: cancelResearch
  };
};
```

### 4.2 流式响应实现

#### 4.2.1 useDeepResearchStream Hook

```typescript
// hooks/useDeepResearchStream.ts
import { useState, useCallback, useRef } from 'react';

interface StreamChunk {
  type: 'thought' | 'text' | 'complete' | 'error';
  content: string;
  eventId?: string;
}

export const useDeepResearchStream = (apiKey: string) => {
  const [chunks, setChunks] = useState<StreamChunk[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string>('');
  const interactionIdRef = useRef<string>('');

  // 启动流式研究
  const startStreamingResearch = useCallback(async (prompt: string) => {
    setIsStreaming(true);
    setChunks([]);

    try {
      // 1. 启动研究任务
      const response = await fetch('/api/research/stream/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          prompt,
          agent: 'deep-research-pro-preview-12-2025',
          background: true,
          stream: true,
          agent_config: {
            type: 'deep-research',
            thinking_summaries: 'auto'
          }
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to start streaming: ${response.statusText}`);
      }

      const data = await response.json();
      interactionIdRef.current = data.interaction_id;

      // 2. 连接 SSE 流
      connectToStream(data.interaction_id);

    } catch (error: any) {
      setChunks(prev => [...prev, {
        type: 'error',
        content: error.message
      }]);
      setIsStreaming(false);
    }
  }, [apiKey]);

  // 连接到 SSE 流
  const connectToStream = useCallback((interactionId: string) => {
    const url = `/api/research/stream/${interactionId}?last_event_id=${lastEventIdRef.current}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // 保存 event_id 用于断线重连
        if (data.event_id) {
          lastEventIdRef.current = data.event_id;
        }

        // 处理不同类型的事件
        if (data.event_type === 'content.delta') {
          if (data.delta.type === 'text') {
            setChunks(prev => [...prev, {
              type: 'text',
              content: data.delta.text,
              eventId: data.event_id
            }]);
          } else if (data.delta.type === 'thought_summary') {
            setChunks(prev => [...prev, {
              type: 'thought',
              content: data.delta.content.text,
              eventId: data.event_id
            }]);
          }
        } else if (data.event_type === 'interaction.complete') {
          setChunks(prev => [...prev, {
            type: 'complete',
            content: '研究完成',
            eventId: data.event_id
          }]);
          setIsStreaming(false);
          eventSource.close();
        }
      } catch (error) {
        console.error('Failed to parse SSE data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      eventSource.close();

      // 尝试重连
      if (isStreaming) {
        console.log('Attempting to reconnect...');
        setTimeout(() => {
          connectToStream(interactionId);
        }, 2000);
      }
    };
  }, [isStreaming]);

  // 停止流式传输
  const stopStreaming = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  return {
    chunks,
    isStreaming,
    startStreamingResearch,
    stopStreaming
  };
};
```

### 4.3 UI 组件

#### 4.3.1 ResearchProgress 组件

```typescript
// components/ResearchProgress.tsx
import React from 'react';

interface ResearchProgressProps {
  status: 'starting' | 'in_progress' | 'completed' | 'failed';
  progress?: string;
  thoughts?: string[];
}

export const ResearchProgress: React.FC<ResearchProgressProps> = ({
  status,
  progress,
  thoughts = []
}) => {
  return (
    <div className="research-progress">
      {/* 状态指示器 */}
      <div className="status-indicator">
        {status === 'starting' && (
          <div className="spinner">🔄 正在启动研究...</div>
        )}
        {status === 'in_progress' && (
          <div className="spinner">🔍 研究进行中...</div>
        )}
        {status === 'completed' && (
          <div className="success">✅ 研究完成</div>
        )}
        {status === 'failed' && (
          <div className="error">❌ 研究失败</div>
        )}
      </div>

      {/* 进度信息 */}
      {progress && (
        <div className="progress-text">
          {progress}
        </div>
      )}

      {/* 思考过程 */}
      {thoughts.length > 0 && (
        <div className="thoughts-container">
          <h4>💭 研究思路</h4>
          {thoughts.map((thought, index) => (
            <div key={index} className="thought-item">
              {thought}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

---


## 5. 后端实现

### 5.1 FastAPI 路由

#### 5.1.1 启动研究任务

```python
# backend/app/routers/research.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from google import genai
import os

router = APIRouter(prefix="/api/research", tags=["research"])

class ResearchStartRequest(BaseModel):
    prompt: str
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True
    format: str | None = None
    include_private_data: bool = False
    file_search_store_names: list[str] | None = None

class ResearchStartResponse(BaseModel):
    interaction_id: str
    status: str

@router.post("/start", response_model=ResearchStartResponse)
async def start_research(request: ResearchStartRequest):
    """启动 Deep Research 任务"""
    try:
        # 1. 初始化 Gemini 客户端
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
        
        client = genai.Client(api_key=api_key)
        
        # 2. 构建 prompt（包含格式化指令）
        full_prompt = request.prompt
        if request.format:
            full_prompt += f"\n\n{request.format}"
        
        # 3. 构建工具列表
        tools = []
        if request.include_private_data and request.file_search_store_names:
            tools.append({
                "type": "file_search",
                "file_search_store_names": request.file_search_store_names
            })
        
        # 4. 启动研究任务
        interaction = client.interactions.create(
            input=full_prompt,
            agent=request.agent,
            background=True,
            tools=tools if tools else None
        )
        
        # 5. 返回 interaction_id
        return ResearchStartResponse(
            interaction_id=interaction.id,
            status=interaction.status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 5.1.2 查询研究状态

```python
# backend/app/routers/research.py (续)

class ResearchStatusResponse(BaseModel):
    status: str
    result: str | None = None
    error: str | None = None
    progress: str | None = None

@router.get("/status/{interaction_id}", response_model=ResearchStatusResponse)
async def get_research_status(interaction_id: str):
    """查询研究任务状态"""
    try:
        # 1. 初始化客户端
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # 2. 获取 interaction 状态
        interaction = client.interactions.get(interaction_id)
        
        # 3. 根据状态返回不同响应
        if interaction.status == "completed":
            # 提取最终报告
            result_text = ""
            if interaction.outputs:
                for output in interaction.outputs:
                    if hasattr(output, 'text'):
                        result_text += output.text
            
            return ResearchStatusResponse(
                status="completed",
                result=result_text
            )
        
        elif interaction.status == "failed":
            error_message = "研究任务失败"
            if hasattr(interaction, 'error'):
                error_message = str(interaction.error)
            
            return ResearchStatusResponse(
                status="failed",
                error=error_message
            )
        
        else:  # in_progress
            return ResearchStatusResponse(
                status="in_progress",
                progress="研究进行中..."
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 5.1.3 取消研究任务

```python
# backend/app/routers/research.py (续)

@router.post("/cancel/{interaction_id}")
async def cancel_research(interaction_id: str):
    """取消研究任务"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # 注意：Gemini API 可能不支持直接取消
        # 这里只是删除 interaction 记录
        client.interactions.delete(interaction_id)
        
        return {"message": "Research task cancelled"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 5.2 流式响应实现

#### 5.2.1 启动流式研究

```python
# backend/app/routers/research_stream.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from google import genai
import json
import asyncio
import os

router = APIRouter(prefix="/api/research/stream", tags=["research-stream"])

class StreamStartRequest(BaseModel):
    prompt: str
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True
    stream: bool = True
    agent_config: dict | None = None

@router.post("/start")
async def start_streaming_research(request: StreamStartRequest):
    """启动流式研究任务"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # 启动流式研究
        stream = client.interactions.create(
            input=request.prompt,
            agent=request.agent,
            background=True,
            stream=True,
            agent_config=request.agent_config or {
                "type": "deep-research",
                "thinking_summaries": "auto"
            }
        )
        
        # 从流中提取 interaction_id
        interaction_id = None
        for chunk in stream:
            if chunk.event_type == "interaction.start":
                interaction_id = chunk.interaction.id
                break
        
        if not interaction_id:
            raise HTTPException(status_code=500, detail="Failed to get interaction_id")
        
        return {"interaction_id": interaction_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 5.2.2 SSE 流式传输

```python
# backend/app/routers/research_stream.py (续)

@router.get("/{interaction_id}")
async def stream_research_events(interaction_id: str, last_event_id: str = ""):
    """通过 SSE 流式传输研究事件"""
    
    async def event_generator():
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            
            # 获取流（支持断线重连）
            stream = client.interactions.get(
                id=interaction_id,
                stream=True,
                last_event_id=last_event_id if last_event_id else None
            )
            
            # 处理流事件
            for chunk in stream:
                event_data = {
                    "event_type": chunk.event_type,
                    "event_id": chunk.event_id if hasattr(chunk, 'event_id') else None
                }
                
                # 处理内容增量
                if chunk.event_type == "content.delta":
                    if chunk.delta.type == "text":
                        event_data["delta"] = {
                            "type": "text",
                            "text": chunk.delta.text
                        }
                    elif chunk.delta.type == "thought_summary":
                        event_data["delta"] = {
                            "type": "thought_summary",
                            "content": {
                                "text": chunk.delta.content.text
                            }
                        }
                
                # 发送 SSE 事件
                yield f"data: {json.dumps(event_data)}\n\n"
                
                # 完成事件
                if chunk.event_type == "interaction.complete":
                    break
            
        except Exception as e:
            error_data = {
                "event_type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )
```

### 5.3 错误处理

#### 5.3.1 统一错误处理器

```python
# backend/app/utils/error_handler.py
from fastapi import HTTPException
from google.api_core import exceptions as google_exceptions

def handle_gemini_error(error: Exception) -> HTTPException:
    """处理 Gemini API 错误"""
    
    # 429 - 配额超限
    if isinstance(error, google_exceptions.ResourceExhausted):
        return HTTPException(
            status_code=429,
            detail={
                "error": "RESOURCE_EXHAUSTED",
                "message": "API 配额已用尽，请稍后重试或升级您的 API 密钥。",
                "suggestions": [
                    "等待几分钟后重试",
                    "切换到更轻量的模型",
                    "检查 Google AI Studio 中的配额"
                ]
            }
        )
    
    # 400 - 无效请求
    if isinstance(error, google_exceptions.InvalidArgument):
        return HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_ARGUMENT",
                "message": "请求参数无效，可能是由于安全过滤器或不支持的文件类型。",
                "original_error": str(error)
            }
        )
    
    # 503 - 服务过载
    if isinstance(error, google_exceptions.ServiceUnavailable):
        return HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "AI 服务当前过载，请稍后重试。"
            }
        )
    
    # 其他错误
    return HTTPException(
        status_code=500,
        detail={
            "error": "INTERNAL_ERROR",
            "message": str(error)
        }
    )
```

### 5.4 缓存策略

#### 5.4.1 Redis 缓存实现

```python
# backend/app/utils/cache.py
import redis
import json
from typing import Optional

class ResearchCache:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
    
    def cache_interaction(self, interaction_id: str, data: dict, ttl: int = 3600):
        """缓存 interaction 数据"""
        key = f"research:interaction:{interaction_id}"
        self.redis_client.setex(
            key,
            ttl,
            json.dumps(data)
        )
    
    def get_cached_interaction(self, interaction_id: str) -> Optional[dict]:
        """获取缓存的 interaction 数据"""
        key = f"research:interaction:{interaction_id}"
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def cache_research_result(self, prompt_hash: str, result: str, ttl: int = 86400):
        """缓存研究结果（24小时）"""
        key = f"research:result:{prompt_hash}"
        self.redis_client.setex(key, ttl, result)
    
    def get_cached_result(self, prompt_hash: str) -> Optional[str]:
        """获取缓存的研究结果"""
        key = f"research:result:{prompt_hash}"
        return self.redis_client.get(key)
```

#### 5.4.2 使用缓存

```python
# backend/app/routers/research.py (优化版)
import hashlib
from app.utils.cache import ResearchCache

cache = ResearchCache()

@router.post("/start", response_model=ResearchStartResponse)
async def start_research(request: ResearchStartRequest):
    """启动 Deep Research 任务（带缓存）"""
    try:
        # 1. 计算 prompt 哈希
        prompt_hash = hashlib.sha256(request.prompt.encode()).hexdigest()
        
        # 2. 检查缓存
        cached_result = cache.get_cached_result(prompt_hash)
        if cached_result:
            # 返回缓存的结果（模拟 interaction）
            return ResearchStartResponse(
                interaction_id=f"cached_{prompt_hash}",
                status="completed"
            )
        
        # 3. 启动新的研究任务
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        interaction = client.interactions.create(
            input=request.prompt,
            agent=request.agent,
            background=True
        )
        
        # 4. 缓存 interaction_id
        cache.cache_interaction(interaction.id, {
            "prompt": request.prompt,
            "status": interaction.status
        })
        
        return ResearchStartResponse(
            interaction_id=interaction.id,
            status=interaction.status
        )
        
    except Exception as e:
        raise handle_gemini_error(e)
```

---


## 6. 流式响应

### 6.1 完整流式实现

#### 6.1.1 前端 SSE 客户端

```typescript
// services/researchStream.ts
export class ResearchStreamClient {
  private eventSource: EventSource | null = null;
  private interactionId: string = '';
  private lastEventId: string = '';
  
  async startStream(
    prompt: string,
    onChunk: (chunk: StreamChunk) => void,
    onComplete: () => void,
    onError: (error: string) => void
  ) {
    try {
      // 1. 启动研究任务
      const response = await fetch('/api/research/stream/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          agent: 'deep-research-pro-preview-12-2025',
          background: true,
          stream: true,
          agent_config: {
            type: 'deep-research',
            thinking_summaries: 'auto'
          }
        })
      });
      
      const data = await response.json();
      this.interactionId = data.interaction_id;
      
      // 2. 连接 SSE 流
      this.connectSSE(onChunk, onComplete, onError);
      
    } catch (error: any) {
      onError(error.message);
    }
  }
  
  private connectSSE(
    onChunk: (chunk: StreamChunk) => void,
    onComplete: () => void,
    onError: (error: string) => void
  ) {
    const url = `/api/research/stream/${this.interactionId}?last_event_id=${this.lastEventId}`;
    this.eventSource = new EventSource(url);
    
    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // 保存 event_id
        if (data.event_id) {
          this.lastEventId = data.event_id;
        }
        
        // 处理不同类型的事件
        if (data.event_type === 'content.delta') {
          if (data.delta.type === 'text') {
            onChunk({
              type: 'text',
              content: data.delta.text,
              eventId: data.event_id
            });
          } else if (data.delta.type === 'thought_summary') {
            onChunk({
              type: 'thought',
              content: data.delta.content.text,
              eventId: data.event_id
            });
          }
        } else if (data.event_type === 'interaction.complete') {
          onComplete();
          this.close();
        } else if (data.event_type === 'error') {
          onError(data.error);
          this.close();
        }
      } catch (error) {
        console.error('Failed to parse SSE data:', error);
      }
    };
    
    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      this.eventSource?.close();
      
      // 尝试重连
      setTimeout(() => {
        console.log('Attempting to reconnect...');
        this.connectSSE(onChunk, onComplete, onError);
      }, 2000);
    };
  }
  
  close() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
```

### 6.2 断线重连机制

#### 6.2.1 前端重连逻辑

```typescript
// hooks/useResearchStreamWithReconnect.ts
import { useState, useCallback, useRef } from 'react';
import { ResearchStreamClient } from '../services/researchStream';

export const useResearchStreamWithReconnect = () => {
  const [chunks, setChunks] = useState<StreamChunk[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const clientRef = useRef<ResearchStreamClient | null>(null);
  const maxReconnects = 5;
  
  const startStream = useCallback(async (prompt: string) => {
    setIsStreaming(true);
    setChunks([]);
    setReconnectCount(0);
    
    const client = new ResearchStreamClient();
    clientRef.current = client;
    
    const handleChunk = (chunk: StreamChunk) => {
      setChunks(prev => [...prev, chunk]);
    };
    
    const handleComplete = () => {
      setIsStreaming(false);
      console.log('Stream completed successfully');
    };
    
    const handleError = (error: string) => {
      console.error('Stream error:', error);
      
      // 尝试重连
      if (reconnectCount < maxReconnects) {
        setReconnectCount(prev => prev + 1);
        console.log(`Reconnecting... (${reconnectCount + 1}/${maxReconnects})`);
        
        setTimeout(() => {
          client.startStream(prompt, handleChunk, handleComplete, handleError);
        }, 2000 * (reconnectCount + 1)); // 指数退避
      } else {
        setIsStreaming(false);
        setChunks(prev => [...prev, {
          type: 'error',
          content: `连接失败，已重试 ${maxReconnects} 次`
        }]);
      }
    };
    
    await client.startStream(prompt, handleChunk, handleComplete, handleError);
  }, [reconnectCount]);
  
  const stopStream = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.close();
      clientRef.current = null;
    }
    setIsStreaming(false);
  }, []);
  
  return {
    chunks,
    isStreaming,
    reconnectCount,
    startStream,
    stopStream
  };
};
```

---

## 7. 错误处理

### 7.1 常见错误类型

#### 7.1.1 错误分类

| 错误类型 | HTTP 状态码 | 错误代码 | 说明 |
|---------|-----------|---------|------|
| 配额超限 | 429 | RESOURCE_EXHAUSTED | API 调用频率或配额超限 |
| 无效请求 | 400 | INVALID_ARGUMENT | 请求参数错误或被安全过滤器拦截 |
| 服务过载 | 503 | SERVICE_UNAVAILABLE | Gemini 服务暂时不可用 |
| 超时 | 504 | TIMEOUT | 研究任务超过60分钟 |
| 认证失败 | 401 | UNAUTHENTICATED | API Key 无效或过期 |

#### 7.1.2 前端错误处理

```typescript
// utils/errorHandler.ts
export class ResearchError extends Error {
  constructor(
    public code: string,
    public message: string,
    public suggestions: string[] = []
  ) {
    super(message);
    this.name = 'ResearchError';
  }
}

export function handleResearchError(error: any): ResearchError {
  // 429 - 配额超限
  if (error.status === 429 || error.code === 'RESOURCE_EXHAUSTED') {
    return new ResearchError(
      'RESOURCE_EXHAUSTED',
      'API 配额已用尽',
      [
        '等待几分钟后重试',
        '切换到更轻量的模型（如 gemini-2.5-flash）',
        '检查 Google AI Studio 中的配额限制'
      ]
    );
  }
  
  // 400 - 无效请求
  if (error.status === 400 || error.code === 'INVALID_ARGUMENT') {
    return new ResearchError(
      'INVALID_ARGUMENT',
      '请求被拒绝，可能触发了安全过滤器',
      [
        '检查 prompt 是否包含敏感内容',
        '确认附件文件类型是否支持',
        '简化 prompt 复杂度'
      ]
    );
  }
  
  // 503 - 服务过载
  if (error.status === 503 || error.code === 'SERVICE_UNAVAILABLE') {
    return new ResearchError(
      'SERVICE_UNAVAILABLE',
      'Gemini 服务当前过载',
      [
        '等待几分钟后重试',
        '避开高峰时段'
      ]
    );
  }
  
  // 504 - 超时
  if (error.status === 504 || error.message?.includes('timeout')) {
    return new ResearchError(
      'TIMEOUT',
      '研究任务超时（超过60分钟）',
      [
        '简化研究范围',
        '分解为多个小任务',
        '使用更具体的 prompt'
      ]
    );
  }
  
  // 默认错误
  return new ResearchError(
    'UNKNOWN_ERROR',
    error.message || '未知错误',
    ['请联系技术支持']
  );
}
```

#### 7.1.3 错误展示组件

```typescript
// components/ErrorDisplay.tsx
import React from 'react';
import { ResearchError } from '../utils/errorHandler';

interface ErrorDisplayProps {
  error: ResearchError;
  onRetry?: () => void;
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error, onRetry }) => {
  return (
    <div className="error-container">
      <div className="error-header">
        <span className="error-icon">❌</span>
        <h3>{error.message}</h3>
      </div>
      
      {error.suggestions.length > 0 && (
        <div className="error-suggestions">
          <h4>💡 建议：</h4>
          <ul>
            {error.suggestions.map((suggestion, index) => (
              <li key={index}>{suggestion}</li>
            ))}
          </ul>
        </div>
      )}
      
      {onRetry && (
        <button onClick={onRetry} className="retry-button">
          🔄 重试
        </button>
      )}
      
      <details className="error-details">
        <summary>技术详情</summary>
        <pre>{JSON.stringify(error, null, 2)}</pre>
      </details>
    </div>
  );
};
```

### 7.2 重试策略

#### 7.2.1 指数退避重试

```typescript
// utils/retry.ts
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    initialDelay?: number;
    maxDelay?: number;
    backoffFactor?: number;
    shouldRetry?: (error: any) => boolean;
  } = {}
): Promise<T> {
  const {
    maxRetries = 3,
    initialDelay = 1000,
    maxDelay = 30000,
    backoffFactor = 2,
    shouldRetry = (error) => error.status === 429 || error.status === 503
  } = options;
  
  let lastError: any;
  let delay = initialDelay;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error: any) {
      lastError = error;
      
      // 检查是否应该重试
      if (attempt === maxRetries || !shouldRetry(error)) {
        throw error;
      }
      
      // 等待后重试
      console.log(`Retry attempt ${attempt + 1}/${maxRetries} after ${delay}ms`);
      await new Promise(resolve => setTimeout(resolve, delay));
      
      // 指数退避
      delay = Math.min(delay * backoffFactor, maxDelay);
    }
  }
  
  throw lastError;
}
```

#### 7.2.2 使用重试

```typescript
// hooks/useResearchWithRetry.ts
import { retryWithBackoff } from '../utils/retry';

export const useResearchWithRetry = (apiKey: string) => {
  const startResearch = useCallback(async (prompt: string) => {
    try {
      const result = await retryWithBackoff(
        async () => {
          const response = await fetch('/api/research/start', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({ prompt })
          });
          
          if (!response.ok) {
            const error = await response.json();
            throw { status: response.status, ...error };
          }
          
          return response.json();
        },
        {
          maxRetries: 3,
          initialDelay: 2000,
          shouldRetry: (error) => {
            // 只对 429 和 503 重试
            return error.status === 429 || error.status === 503;
          }
        }
      );
      
      return result;
    } catch (error) {
      throw handleResearchError(error);
    }
  }, [apiKey]);
  
  return { startResearch };
};
```

---

## 8. 最佳实践

### 8.1 Prompt 设计

#### 8.1.1 清晰的研究查询

**✅ 好的查询**：
```typescript
const goodPrompt = `
研究 2025 年电动汽车电池的竞争格局。

重点关注：
- 按市场份额排名的前 5 大制造商
- 关键技术创新（固态电池、快充技术）
- 供应链挑战（原材料短缺、地缘政治）
- 价格趋势（2023-2025）

输出格式：
1. 执行摘要（2-3 段）
2. 详细分析（包含数据表格）
3. 关键发现（要点列表）
4. 建议（编号列表）
5. 参考文献
`;
```

**❌ 不好的查询**：
```typescript
const badPrompt = "告诉我关于电动汽车电池的信息";
```

#### 8.1.2 格式化指令

```typescript
// utils/promptTemplates.ts
export const researchPromptTemplates = {
  technicalReport: (topic: string, focus: string[]) => `
研究主题：${topic}

重点关注：
${focus.map((f, i) => `${i + 1}. ${f}`).join('\n')}

输出格式要求：
1. **执行摘要**（2-3 段落）
2. **详细分析**
   - 包含数据表格对比
   - 引用具体数据来源
3. **关键发现**（要点列表）
4. **战略建议**（编号列表）
5. **参考文献**（完整 URL）

语气：专业、客观
受众：技术决策者
`,

  marketAnalysis: (market: string, timeframe: string) => `
市场分析：${market}
时间范围：${timeframe}

分析维度：
1. 市场规模和增长率
2. 主要参与者和市场份额
3. 竞争格局和差异化策略
4. 技术趋势和创新
5. 监管环境和政策影响
6. 投资机会和风险

输出格式：
- 使用 Markdown 表格展示数据
- 包含图表描述（如适用）
- 每个结论都要引用来源
`,

  literatureReview: (topic: string, keywords: string[]) => `
文献综述：${topic}

关键词：${keywords.join(', ')}

综述要求：
1. 研究背景和意义
2. 主要研究方法和理论框架
3. 关键发现和争议点
4. 研究空白和未来方向
5. 参考文献列表（按年份排序）

引用格式：APA 第7版
`
};
```

### 8.2 性能优化

#### 8.2.1 缓存策略

```typescript
// services/researchCache.ts
export class ResearchCacheService {
  private cache: Map<string, CachedResearch> = new Map();
  private readonly TTL = 24 * 60 * 60 * 1000; // 24小时
  
  // 生成缓存键
  private getCacheKey(prompt: string, options?: any): string {
    const normalized = prompt.toLowerCase().trim();
    const optionsStr = options ? JSON.stringify(options) : '';
    return `${normalized}:${optionsStr}`;
  }
  
  // 检查缓存
  get(prompt: string, options?: any): string | null {
    const key = this.getCacheKey(prompt, options);
    const cached = this.cache.get(key);
    
    if (!cached) return null;
    
    // 检查是否过期
    if (Date.now() - cached.timestamp > this.TTL) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.result;
  }
  
  // 设置缓存
  set(prompt: string, result: string, options?: any): void {
    const key = this.getCacheKey(prompt, options);
    this.cache.set(key, {
      result,
      timestamp: Date.now()
    });
  }
  
  // 清理过期缓存
  cleanup(): void {
    const now = Date.now();
    for (const [key, cached] of this.cache.entries()) {
      if (now - cached.timestamp > this.TTL) {
        this.cache.delete(key);
      }
    }
  }
}

interface CachedResearch {
  result: string;
  timestamp: number;
}
```

#### 8.2.2 请求去重

```typescript
// services/requestDeduplication.ts
export class RequestDeduplicationService {
  private pendingRequests: Map<string, Promise<any>> = new Map();
  
  async deduplicate<T>(
    key: string,
    fn: () => Promise<T>
  ): Promise<T> {
    // 检查是否有相同的请求正在进行
    const pending = this.pendingRequests.get(key);
    if (pending) {
      console.log(`Deduplicating request: ${key}`);
      return pending as Promise<T>;
    }
    
    // 执行新请求
    const promise = fn().finally(() => {
      this.pendingRequests.delete(key);
    });
    
    this.pendingRequests.set(key, promise);
    return promise;
  }
}
```

### 8.3 用户体验优化

#### 8.3.1 进度指示器

```typescript
// components/ResearchProgressIndicator.tsx
import React, { useEffect, useState } from 'react';

interface ProgressIndicatorProps {
  status: 'starting' | 'in_progress' | 'completed' | 'failed';
  elapsedTime: number; // 秒
  estimatedTime?: number; // 秒
}

export const ResearchProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  status,
  elapsedTime,
  estimatedTime
}) => {
  const [progress, setProgress] = useState(0);
  
  useEffect(() => {
    if (status === 'in_progress' && estimatedTime) {
      setProgress(Math.min((elapsedTime / estimatedTime) * 100, 95));
    } else if (status === 'completed') {
      setProgress(100);
    }
  }, [status, elapsedTime, estimatedTime]);
  
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  return (
    <div className="progress-indicator">
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${progress}%` }}
        />
      </div>
      
      <div className="progress-info">
        <span>已用时间: {formatTime(elapsedTime)}</span>
        {estimatedTime && (
          <span>预计剩余: {formatTime(Math.max(0, estimatedTime - elapsedTime))}</span>
        )}
      </div>
      
      <div className="progress-status">
        {status === 'starting' && '🔄 正在启动研究...'}
        {status === 'in_progress' && '🔍 研究进行中...'}
        {status === 'completed' && '✅ 研究完成'}
        {status === 'failed' && '❌ 研究失败'}
      </div>
    </div>
  );
};
```

---


## 9. 安全考虑

### 9.1 输入验证

#### 9.1.1 Prompt 安全检查

```python
# backend/app/utils/security.py
import re
from typing import List, Tuple

class PromptSecurityValidator:
    """Prompt 安全验证器"""
    
    # 危险关键词列表
    DANGEROUS_KEYWORDS = [
        'ignore previous instructions',
        'disregard all',
        'forget everything',
        'new instructions',
        'system prompt',
        'jailbreak'
    ]
    
    # 敏感信息模式
    SENSITIVE_PATTERNS = [
        (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),  # 社会安全号
        (r'\b\d{16}\b', 'Credit Card'),      # 信用卡号
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'Email'),
        (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', 'Phone Number')
    ]
    
    @classmethod
    def validate_prompt(cls, prompt: str) -> Tuple[bool, List[str]]:
        """
        验证 prompt 安全性
        
        Returns:
            (is_safe, warnings)
        """
        warnings = []
        
        # 1. 检查危险关键词
        prompt_lower = prompt.lower()
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in prompt_lower:
                warnings.append(f"检测到潜在的 prompt 注入: '{keyword}'")
        
        # 2. 检查敏感信息
        for pattern, info_type in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, prompt):
                warnings.append(f"检测到可能的敏感信息: {info_type}")
        
        # 3. 检查长度
        if len(prompt) > 10000:
            warnings.append("Prompt 过长（超过10000字符）")
        
        # 4. 检查特殊字符
        if re.search(r'[<>{}]', prompt):
            warnings.append("检测到特殊字符，可能存在注入风险")
        
        is_safe = len(warnings) == 0
        return is_safe, warnings
```

#### 9.1.2 使用安全验证

```python
# backend/app/routers/research.py (安全版)
from app.utils.security import PromptSecurityValidator

@router.post("/start", response_model=ResearchStartResponse)
async def start_research(request: ResearchStartRequest):
    """启动 Deep Research 任务（带安全检查）"""
    
    # 1. 验证 prompt 安全性
    is_safe, warnings = PromptSecurityValidator.validate_prompt(request.prompt)
    
    if not is_safe:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "UNSAFE_PROMPT",
                "message": "Prompt 包含不安全内容",
                "warnings": warnings
            }
        )
    
    # 2. 记录警告（如果有）
    if warnings:
        logger.warning(f"Prompt warnings: {warnings}")
    
    # 3. 继续正常流程
    # ...
```

### 9.2 API Key 管理

#### 9.2.1 安全存储

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    gemini_api_key: str
    redis_url: str = "redis://localhost:6379"
    
    # 安全配置
    api_key_rotation_days: int = 90
    max_requests_per_minute: int = 60
    
    # 数据库
    database_url: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

#### 9.2.2 速率限制

```python
# backend/app/middleware/rate_limit.py
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import redis

class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> bool:
        """
        检查速率限制
        
        Args:
            key: 限流键（通常是 user_id 或 ip）
            max_requests: 最大请求数
            window_seconds: 时间窗口（秒）
        
        Returns:
            是否允许请求
        """
        now = datetime.now().timestamp()
        window_start = now - window_seconds
        
        # 使用 Redis Sorted Set 存储请求时间戳
        pipe = self.redis.pipeline()
        
        # 1. 移除过期的请求记录
        pipe.zremrangebyscore(key, 0, window_start)
        
        # 2. 获取当前窗口内的请求数
        pipe.zcard(key)
        
        # 3. 添加当前请求
        pipe.zadd(key, {str(now): now})
        
        # 4. 设置过期时间
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        request_count = results[1]
        
        return request_count < max_requests

# 使用中间件
from fastapi import Depends

async def rate_limit_dependency(request: Request):
    """速率限制依赖"""
    limiter = RateLimiter(redis_client)
    
    # 使用 IP 地址作为限流键
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    is_allowed = await limiter.check_rate_limit(
        key=key,
        max_requests=60,  # 每分钟60次
        window_seconds=60
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后重试"
        )
```

### 9.3 数据隐私

#### 9.3.1 敏感数据脱敏

```python
# backend/app/utils/data_masking.py
import re
from typing import Dict, Any

class DataMasker:
    """数据脱敏工具"""
    
    @staticmethod
    def mask_email(email: str) -> str:
        """脱敏邮箱地址"""
        if '@' not in email:
            return email
        
        local, domain = email.split('@')
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """脱敏电话号码"""
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 4:
            return '*' * len(digits)
        
        return digits[:3] + '*' * (len(digits) - 6) + digits[-3:]
    
    @staticmethod
    def mask_credit_card(card: str) -> str:
        """脱敏信用卡号"""
        digits = re.sub(r'\D', '', card)
        if len(digits) < 4:
            return '*' * len(digits)
        
        return '*' * (len(digits) - 4) + digits[-4:]
    
    @classmethod
    def mask_sensitive_data(cls, text: str) -> str:
        """自动脱敏文本中的敏感数据"""
        # 邮箱
        text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            lambda m: cls.mask_email(m.group()),
            text
        )
        
        # 电话
        text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            lambda m: cls.mask_phone(m.group()),
            text
        )
        
        # 信用卡
        text = re.sub(
            r'\b\d{16}\b',
            lambda m: cls.mask_credit_card(m.group()),
            text
        )
        
        return text
```

#### 9.3.2 日志脱敏

```python
# backend/app/utils/logging.py
import logging
from app.utils.data_masking import DataMasker

class MaskingFormatter(logging.Formatter):
    """自动脱敏的日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        # 脱敏消息内容
        if isinstance(record.msg, str):
            record.msg = DataMasker.mask_sensitive_data(record.msg)
        
        # 脱敏参数
        if record.args:
            masked_args = tuple(
                DataMasker.mask_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
            record.args = masked_args
        
        return super().format(record)

# 配置日志
def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(MaskingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    logger = logging.getLogger('app')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    return logger
```

### 9.4 文件上传安全

#### 9.4.1 文件类型验证

```python
# backend/app/utils/file_validation.py
from typing import List, Tuple
import magic
import os

class FileValidator:
    """文件验证器"""
    
    # 允许的 MIME 类型
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'text/plain',
        'text/csv',
        'application/json',
        'image/jpeg',
        'image/png',
        'image/webp'
    }
    
    # 最大文件大小（字节）
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    @classmethod
    def validate_file(cls, file_path: str) -> Tuple[bool, str]:
        """
        验证文件
        
        Returns:
            (is_valid, error_message)
        """
        # 1. 检查文件是否存在
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        # 2. 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > cls.MAX_FILE_SIZE:
            return False, f"文件过大（最大 {cls.MAX_FILE_SIZE / 1024 / 1024}MB）"
        
        # 3. 检查 MIME 类型
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        
        if mime_type not in cls.ALLOWED_MIME_TYPES:
            return False, f"不支持的文件类型: {mime_type}"
        
        # 4. 检查文件内容（防止伪造扩展名）
        with open(file_path, 'rb') as f:
            header = f.read(512)
            
            # PDF 文件头检查
            if mime_type == 'application/pdf':
                if not header.startswith(b'%PDF'):
                    return False, "文件内容与扩展名不匹配"
            
            # 图片文件头检查
            elif mime_type == 'image/jpeg':
                if not header.startswith(b'\xff\xd8\xff'):
                    return False, "文件内容与扩展名不匹配"
            
            elif mime_type == 'image/png':
                if not header.startswith(b'\x89PNG'):
                    return False, "文件内容与扩展名不匹配"
        
        return True, ""
```

---

## 10. 性能优化

### 10.1 并发控制

#### 10.1.1 任务队列

```python
# backend/app/services/research_queue.py
from celery import Celery
from app.config import get_settings

settings = get_settings()

# 初始化 Celery
celery_app = Celery(
    'research_tasks',
    broker=settings.redis_url,
    backend=settings.redis_url
)

@celery_app.task(bind=True, max_retries=3)
def start_research_task(self, prompt: str, options: dict):
    """异步研究任务"""
    try:
        from google import genai
        
        client = genai.Client(api_key=settings.gemini_api_key)
        
        interaction = client.interactions.create(
            input=prompt,
            agent='deep-research-pro-preview-12-2025',
            background=True,
            **options
        )
        
        # 轮询直到完成
        while True:
            result = client.interactions.get(interaction.id)
            
            if result.status == 'completed':
                return {
                    'status': 'completed',
                    'result': result.outputs[-1].text
                }
            elif result.status == 'failed':
                return {
                    'status': 'failed',
                    'error': str(result.error)
                }
            
            time.sleep(10)
            
    except Exception as e:
        # 重试
        raise self.retry(exc=e, countdown=60)
```

### 10.2 数据库优化

#### 10.2.1 索引策略

```python
# backend/app/models/research.py
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ResearchRecord(Base):
    __tablename__ = 'research_records'
    
    id = Column(String(36), primary_key=True)
    interaction_id = Column(String(100), unique=True, nullable=False)
    prompt = Column(Text, nullable=False)
    prompt_hash = Column(String(64), nullable=False)  # 用于缓存查询
    result = Column(Text)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    
    # 索引
    __table_args__ = (
        Index('idx_prompt_hash', 'prompt_hash'),
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_interaction_id', 'interaction_id'),
    )
```

### 10.3 前端优化

#### 10.3.1 虚拟滚动

```typescript
// components/ResearchResultList.tsx
import React, { useRef, useCallback } from 'react';
import { FixedSizeList as List } from 'react-window';

interface ResearchResultListProps {
  results: ResearchResult[];
  onSelectResult: (result: ResearchResult) => void;
}

export const ResearchResultList: React.FC<ResearchResultListProps> = ({
  results,
  onSelectResult
}) => {
  const Row = useCallback(({ index, style }) => {
    const result = results[index];
    
    return (
      <div style={style} className="result-item" onClick={() => onSelectResult(result)}>
        <h3>{result.title}</h3>
        <p>{result.summary}</p>
        <span className="timestamp">{new Date(result.timestamp).toLocaleString()}</span>
      </div>
    );
  }, [results, onSelectResult]);
  
  return (
    <List
      height={600}
      itemCount={results.length}
      itemSize={120}
      width="100%"
    >
      {Row}
    </List>
  );
};
```

---

## 11. 测试策略

### 11.1 单元测试

#### 11.1.1 前端测试

```typescript
// __tests__/useDeepResearch.test.ts
import { renderHook, act, waitFor } from '@testing-library/react';
import { useDeepResearch } from '../hooks/useDeepResearch';

// Mock fetch
global.fetch = jest.fn();

describe('useDeepResearch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  it('should start research successfully', async () => {
    // Mock API responses
    (fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ interaction_id: 'test-id-123' })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'in_progress' })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'completed',
          result: 'Test research result'
        })
      });
    
    const { result } = renderHook(() => useDeepResearch('test-api-key'));
    
    // Start research
    await act(async () => {
      await result.current.startResearch('Test prompt');
    });
    
    // Wait for completion
    await waitFor(() => {
      expect(result.current.researchStatus.status).toBe('completed');
    }, { timeout: 5000 });
    
    expect(result.current.researchStatus.result).toBe('Test research result');
  });
  
  it('should handle errors', async () => {
    (fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));
    
    const { result } = renderHook(() => useDeepResearch('test-api-key'));
    
    await act(async () => {
      await result.current.startResearch('Test prompt');
    });
    
    expect(result.current.researchStatus.status).toBe('failed');
    expect(result.current.researchStatus.error).toContain('Network error');
  });
});
```

#### 11.1.2 后端测试

```python
# tests/test_research_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_genai_client():
    with patch('app.routers.research.genai.Client') as mock:
        yield mock

def test_start_research_success(mock_genai_client):
    """测试成功启动研究任务"""
    # Mock Gemini API
    mock_interaction = Mock()
    mock_interaction.id = 'test-interaction-123'
    mock_interaction.status = 'in_progress'
    
    mock_genai_client.return_value.interactions.create.return_value = mock_interaction
    
    # 发送请求
    response = client.post(
        '/api/research/start',
        json={
            'prompt': 'Test research prompt',
            'agent': 'deep-research-pro-preview-12-2025',
            'background': True
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data['interaction_id'] == 'test-interaction-123'
    assert data['status'] == 'in_progress'

def test_start_research_invalid_prompt(mock_genai_client):
    """测试无效 prompt"""
    response = client.post(
        '/api/research/start',
        json={
            'prompt': 'ignore previous instructions',  # 危险关键词
            'agent': 'deep-research-pro-preview-12-2025',
            'background': True
        }
    )
    
    assert response.status_code == 400
    data = response.json()
    assert 'UNSAFE_PROMPT' in data['detail']['error']
```

### 11.2 集成测试

```python
# tests/integration/test_research_flow.py
import pytest
import time
from google import genai

@pytest.mark.integration
def test_full_research_flow():
    """测试完整的研究流程"""
    client = genai.Client()
    
    # 1. 启动研究
    interaction = client.interactions.create(
        input="Research the history of Python programming language",
        agent='deep-research-pro-preview-12-2025',
        background=True
    )
    
    assert interaction.id is not None
    assert interaction.status == 'in_progress'
    
    # 2. 轮询状态
    max_wait = 300  # 5分钟
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        result = client.interactions.get(interaction.id)
        
        if result.status == 'completed':
            assert result.outputs is not None
            assert len(result.outputs) > 0
            break
        elif result.status == 'failed':
            pytest.fail(f"Research failed: {result.error}")
        
        time.sleep(10)
    else:
        pytest.fail("Research timed out")
```

---


## 12. 故障排查

### 12.1 常见问题

#### 12.1.1 研究任务一直处于 in_progress 状态

**症状**：
- 任务启动后长时间（超过30分钟）仍显示 `in_progress`
- 轮询状态没有任何变化

**可能原因**：
1. 研究任务确实需要很长时间（复杂查询可能需要60分钟）
2. Gemini API 内部错误
3. 网络连接问题

**解决方案**：
```typescript
// 添加超时检测
const MAX_RESEARCH_TIME = 60 * 60 * 1000; // 60分钟

const checkTimeout = () => {
  const elapsed = Date.now() - startTime;
  if (elapsed > MAX_RESEARCH_TIME) {
    setResearchStatus({
      status: 'failed',
      error: '研究任务超时（超过60分钟）'
    });
    return true;
  }
  return false;
};
```

#### 12.1.2 流式响应中断

**症状**：
- SSE 连接突然断开
- 收到部分内容后停止更新

**可能原因**：
1. 网络不稳定
2. 服务器超时
3. 浏览器限制

**解决方案**：
```typescript
// 实现自动重连
const connectWithRetry = (maxRetries = 5) => {
  let retryCount = 0;
  
  const connect = () => {
    const eventSource = new EventSource(url);
    
    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      eventSource.close();
      
      if (retryCount < maxRetries) {
        retryCount++;
        console.log(`Reconnecting... (${retryCount}/${maxRetries})`);
        setTimeout(connect, 2000 * retryCount); // 指数退避
      } else {
        onError('连接失败，已达到最大重试次数');
      }
    };
    
    // ... 其他事件处理
  };
  
  connect();
};
```

#### 12.1.3 429 错误（配额超限）

**症状**：
- 返回 `RESOURCE_EXHAUSTED` 错误
- HTTP 状态码 429

**可能原因**：
1. API 调用频率过高
2. 免费配额已用尽
3. 并发请求过多

**解决方案**：
```python
# 实现速率限制和重试
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=lambda e: isinstance(e, ResourceExhausted)
)
def start_research_with_retry(prompt: str):
    client = genai.Client()
    return client.interactions.create(
        input=prompt,
        agent='deep-research-pro-preview-12-2025',
        background=True
    )
```

### 12.2 调试工具

#### 12.2.1 日志记录

```python
# backend/app/utils/debug_logger.py
import logging
import json
from datetime import datetime

class ResearchDebugLogger:
    """研究任务调试日志"""
    
    def __init__(self, interaction_id: str):
        self.interaction_id = interaction_id
        self.logger = logging.getLogger(f'research.{interaction_id}')
        self.events = []
    
    def log_event(self, event_type: str, data: dict):
        """记录事件"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        self.events.append(event)
        self.logger.info(f"{event_type}: {json.dumps(data)}")
    
    def log_start(self, prompt: str):
        self.log_event('research_start', {'prompt': prompt})
    
    def log_status_check(self, status: str):
        self.log_event('status_check', {'status': status})
    
    def log_complete(self, result_length: int):
        self.log_event('research_complete', {'result_length': result_length})
    
    def log_error(self, error: str):
        self.log_event('research_error', {'error': error})
    
    def get_timeline(self) -> list:
        """获取完整时间线"""
        return self.events
```

#### 12.2.2 性能监控

```typescript
// utils/performanceMonitor.ts
export class ResearchPerformanceMonitor {
  private metrics: Map<string, PerformanceMetric> = new Map();
  
  startTimer(name: string) {
    this.metrics.set(name, {
      startTime: performance.now(),
      endTime: null,
      duration: null
    });
  }
  
  endTimer(name: string) {
    const metric = this.metrics.get(name);
    if (metric) {
      metric.endTime = performance.now();
      metric.duration = metric.endTime - metric.startTime;
    }
  }
  
  getMetrics(): Record<string, number> {
    const result: Record<string, number> = {};
    for (const [name, metric] of this.metrics.entries()) {
      if (metric.duration !== null) {
        result[name] = metric.duration;
      }
    }
    return result;
  }
  
  logMetrics() {
    console.table(this.getMetrics());
  }
}

interface PerformanceMetric {
  startTime: number;
  endTime: number | null;
  duration: number | null;
}
```

### 12.3 诊断清单

#### 12.3.1 启动问题诊断

```markdown
## 研究任务无法启动

- [ ] 检查 API Key 是否有效
  ```bash
  curl -H "x-goog-api-key: $GEMINI_API_KEY" \
    https://generativelanguage.googleapis.com/v1beta/models
  ```

- [ ] 检查网络连接
  ```bash
  ping generativelanguage.googleapis.com
  ```

- [ ] 检查 prompt 是否包含不安全内容
  - 运行安全验证器
  - 查看警告信息

- [ ] 检查后端日志
  ```bash
  tail -f /var/log/app/research.log
  ```

- [ ] 检查 Redis 连接（如果使用缓存）
  ```bash
  redis-cli ping
  ```
```

#### 12.3.2 性能问题诊断

```markdown
## 研究任务响应缓慢

- [ ] 检查 API 配额使用情况
  - 登录 Google AI Studio
  - 查看配额仪表板

- [ ] 检查网络延迟
  ```bash
  curl -w "@curl-format.txt" -o /dev/null -s \
    https://generativelanguage.googleapis.com/v1beta/models
  ```

- [ ] 检查数据库查询性能
  ```sql
  EXPLAIN ANALYZE SELECT * FROM research_records 
  WHERE prompt_hash = 'xxx';
  ```

- [ ] 检查 Redis 性能
  ```bash
  redis-cli --latency
  ```

- [ ] 检查服务器资源
  ```bash
  top
  df -h
  free -m
  ```
```

---

## 13. 附录

### 13.1 完整代码示例

#### 13.1.1 最小可行实现（前端）

```typescript
// MinimalDeepResearch.tsx
import React, { useState } from 'react';

export const MinimalDeepResearch: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'completed' | 'error'>('idle');
  
  const startResearch = async () => {
    setStatus('loading');
    setResult('');
    
    try {
      // 1. 启动研究
      const startResponse = await fetch('/api/research/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          agent: 'deep-research-pro-preview-12-2025',
          background: true
        })
      });
      
      const { interaction_id } = await startResponse.json();
      
      // 2. 轮询状态
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`/api/research/status/${interaction_id}`);
        const data = await statusResponse.json();
        
        if (data.status === 'completed') {
          clearInterval(pollInterval);
          setResult(data.result);
          setStatus('completed');
        } else if (data.status === 'failed') {
          clearInterval(pollInterval);
          setResult(`错误: ${data.error}`);
          setStatus('error');
        }
      }, 10000);
      
    } catch (error: any) {
      setResult(`错误: ${error.message}`);
      setStatus('error');
    }
  };
  
  return (
    <div>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="输入研究主题..."
        rows={5}
        style={{ width: '100%' }}
      />
      
      <button onClick={startResearch} disabled={status === 'loading'}>
        {status === 'loading' ? '研究中...' : '开始研究'}
      </button>
      
      {result && (
        <div style={{ marginTop: '20px', whiteSpace: 'pre-wrap' }}>
          {result}
        </div>
      )}
    </div>
  );
};
```

#### 13.1.2 最小可行实现（后端）

```python
# minimal_research_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
import os

app = FastAPI()

class ResearchRequest(BaseModel):
    prompt: str
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True

@app.post("/api/research/start")
async def start_research(request: ResearchRequest):
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        interaction = client.interactions.create(
            input=request.prompt,
            agent=request.agent,
            background=True
        )
        
        return {
            "interaction_id": interaction.id,
            "status": interaction.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/research/status/{interaction_id}")
async def get_status(interaction_id: str):
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        interaction = client.interactions.get(interaction_id)
        
        if interaction.status == "completed":
            result = ""
            for output in interaction.outputs:
                if hasattr(output, 'text'):
                    result += output.text
            
            return {
                "status": "completed",
                "result": result
            }
        elif interaction.status == "failed":
            return {
                "status": "failed",
                "error": str(interaction.error)
            }
        else:
            return {
                "status": "in_progress"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 13.2 参考资源

#### 13.2.1 官方文档

- [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions)
- [Deep Research Agent](https://ai.google.dev/gemini-api/docs/deep-research)
- [Google AI Studio](https://aistudio.google.com/)

#### 13.2.2 SDK 文档

- [Python SDK](https://github.com/google/generative-ai-python)
- [JavaScript SDK](https://github.com/google/generative-ai-js)

#### 13.2.3 社区资源

- [Google AI Developer Forum](https://discuss.ai.google.dev/)
- [Stack Overflow - Gemini API](https://stackoverflow.com/questions/tagged/gemini-api)

### 13.3 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.0 | 2025-12-20 | 初始版本，包含完整的前后端实现指南 |

### 13.4 贡献指南

如果你发现文档中的错误或有改进建议，请：

1. 提交 Issue 描述问题
2. 提供具体的改进建议
3. 如果可能，提供代码示例

### 13.5 许可证

本文档采用 MIT 许可证。

---

## 总结

本开发指南涵盖了 Gemini Deep Research Agent 的完整实现，包括：

✅ **核心概念**：Interaction 对象、工作流程、状态管理  
✅ **前端实现**：React Hooks、流式响应、UI 组件  
✅ **后端实现**：FastAPI 路由、SSE 流、缓存策略  
✅ **错误处理**：分类处理、重试机制、用户友好提示  
✅ **安全考虑**：输入验证、API Key 管理、数据脱敏  
✅ **性能优化**：并发控制、数据库索引、前端优化  
✅ **测试策略**：单元测试、集成测试、性能测试  
✅ **故障排查**：常见问题、调试工具、诊断清单  

通过遵循本指南，你可以构建一个**生产级的 Deep Research Agent 应用**，为用户提供强大的 AI 研究能力。

---

**最后更新**: 2025-12-20  
**维护者**: Kiro AI Team  
**反馈**: [提交 Issue](https://github.com/your-repo/issues)
