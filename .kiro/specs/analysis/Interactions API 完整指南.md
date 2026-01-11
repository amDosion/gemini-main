# Gemini Interactions API 完整技术指南

## 📋 目录

- [概述](#概述)
- [核心概念](#核心概念)
- [基础使用](#基础使用)
- [对话管理](#对话管理)
- [多模态能力](#多模态能力)
- [代理能力](#代理能力)
- [工具系统](#工具系统)
- [高级特性](#高级特性)
- [最佳实践](#最佳实践)
- [限制与注意事项](#限制与注意事项)

---

## 概述

### 什么是 Interactions API

`Interactions API` 是 Google Gemini 提供的**统一接口**，用于与 Gemini 模型和代理进行交互。它简化了状态管理、工具编排和长时间运行任务的处理。

**核心特性**：
- ✅ 统一的模型和代理接口
- ✅ 自动化的工具编排
- ✅ 服务端状态管理
- ✅ 原生异步执行支持
- ✅ 事件驱动的流式响应
- ✅ 结构化输出（JSON Schema）

**重要提示**：
> Interactions API 目前处于 **Beta 阶段**，功能和架构可能会发生变化。对于生产环境，建议继续使用稳定的 `generateContent` API。

### 与 generateContent API 的区别

| 维度 | generateContent API | Interactions API |
|------|---------------------|------------------|
| **设计理念** | 生成内容 | 管理交互过程 |
| **核心资源** | Content（内容） | Interaction（交互） |
| **工具处理** | 手动管理工具调用循环 | 自动处理工具编排 |
| **状态管理** | 客户端负责 | 服务端自动管理 |
| **异步支持** | 不支持 | 原生支持（background=true） |
| **代理支持** | 不支持 | 支持专门代理（如 Deep Research） |
| **适用场景** | 快速生成、聊天 | 复杂交互、代理、长时间任务 |

---

## 核心概念

### Interaction 对象

`Interaction` 是 Interactions API 的核心资源，代表对话或任务中的**完整一轮交互**。

#### Interaction 的结构

```typescript
interface Interaction {
  id: string;                    // 唯一标识符
  model?: string;                // 使用的模型（与 agent 二选一）
  agent?: string;                // 使用的代理（与 model 二选一）
  input: Content[];              // 用户输入
  outputs: Content[];            // 模型输出（数组，包含所有中间步骤）
  tools?: Tool[];                // 使用的工具
  previous_interaction_id?: string;  // 上一个交互的 ID
  stream?: boolean;              // 是否流式响应
  status: string;                // 状态：completed, in_progress, requires_action, failed
  background?: boolean;          // 是否后台执行
  store?: boolean;               // 是否存储（默认 true）
  usage?: Usage;                 // 令牌使用情况
}
```


#### Interaction 的关键特性

1. **完整的交互记录**：
   - 包含从输入到输出的完整过程
   - 包括所有工具调用和结果
   - 包括模型的中间思考过程

2. **outputs 数组**：
   ```typescript
   outputs: [
     { type: "text", text: "让我查询天气..." },
     { type: "function_call", name: "get_weather", arguments: {...} },
     { type: "function_result", result: "晴天，25°C" },
     { type: "text", text: "今天巴黎天气晴朗，温度25°C" }
   ]
   ```

3. **状态流转**：
   ```
   in_progress → completed
   in_progress → requires_action → completed
   in_progress → failed
   ```

### SDK 支持

**Python SDK**：
```bash
pip install google-genai>=1.55.0
```

**JavaScript SDK**：
```bash
npm install @google/genai@^1.33.0
```

**REST API**：
```
POST https://generativelanguage.googleapis.com/v1beta/interactions
```

---

## 基础使用

### 安装和初始化

#### Python

```python
from google import genai

# 初始化客户端（自动使用环境变量 GEMINI_API_KEY）
client = genai.Client()

# 或显式指定 API Key
client = genai.Client(api_key="your-api-key")
```

#### JavaScript

```javascript
import { GoogleGenAI } from '@google/genai';

// 初始化客户端（自动使用环境变量 GEMINI_API_KEY）
const client = new GoogleGenAI({});

// 或显式指定 API Key
const client = new GoogleGenAI({ apiKey: 'your-api-key' });
```

### 简单文本交互

#### Python

```python
from google import genai

client = genai.Client()

# 创建交互
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Tell me a short joke about programming."
)

# 获取输出
print(interaction.outputs[-1].text)
```

#### JavaScript

```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

// 创建交互
const interaction = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: 'Tell me a short joke about programming.',
});

// 获取输出
console.log(interaction.outputs[interaction.outputs.length - 1].text);
```

#### REST

```bash
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "model": "gemini-3-flash-preview",
    "input": "Tell me a short joke about programming."
}'
```

---

## 对话管理

### 有状态对话（服务端管理）

使用 `previous_interaction_id` 实现多轮对话，服务端自动管理上下文。

#### Python

```python
from google import genai

client = genai.Client()

# 第一轮对话
interaction1 = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Hi, my name is Phil."
)
print(f"Model: {interaction1.outputs[-1].text}")

# 第二轮对话（引用上一轮）
interaction2 = client.interactions.create(
    model="gemini-3-flash-preview",
    input="What is my name?",
    previous_interaction_id=interaction1.id  # 服务端自动加载上下文
)
print(f"Model: {interaction2.outputs[-1].text}")
# 输出: "Your name is Phil."
```


#### JavaScript

```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

// 第一轮对话
const interaction1 = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: 'Hi, my name is Phil.'
});
console.log(`Model: ${interaction1.outputs[interaction1.outputs.length - 1].text}`);

// 第二轮对话（引用上一轮）
const interaction2 = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: 'What is my name?',
    previous_interaction_id: interaction1.id
});
console.log(`Model: ${interaction2.outputs[interaction2.outputs.length - 1].text}`);
```

#### 检索历史交互

```python
# 通过 ID 检索之前的交互
previous_interaction = client.interactions.get("interaction_id_123")
print(previous_interaction.outputs[-1].text)
```

### 无状态对话（客户端管理）

手动管理对话历史，适合需要完全控制上下文的场景。

#### Python

```python
from google import genai

client = genai.Client()

# 手动维护对话历史
conversation_history = [
    {
        "role": "user",
        "content": "What are the three largest cities in Spain?"
    }
]

# 第一轮
interaction1 = client.interactions.create(
    model="gemini-3-flash-preview",
    input=conversation_history
)
print(f"Model: {interaction1.outputs[-1].text}")

# 添加模型响应到历史
conversation_history.append({
    "role": "model", 
    "content": interaction1.outputs
})

# 添加新的用户输入
conversation_history.append({
    "role": "user", 
    "content": "What is the most famous landmark in the second one?"
})

# 第二轮
interaction2 = client.interactions.create(
    model="gemini-3-flash-preview",
    input=conversation_history
)
print(f"Model: {interaction2.outputs[-1].text}")
```

### 数据存储和保留

**默认行为**：
- 所有 Interaction 对象默认存储（`store=true`）
- **付费版**：保留 **55 天**
- **免费版**：保留 **1 天**

**禁用存储**：
```python
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Your prompt",
    store=False  # 不存储此交互
)
```

**注意**：
- `store=false` 与 `background=true` 不兼容
- `store=false` 时无法使用 `previous_interaction_id`

**删除交互**：
```python
# 删除指定交互
client.interactions.delete("interaction_id_123")
```

---

## 多模态能力

### 图像理解

#### 使用 Base64 内联数据

**Python**：
```python
import base64
from pathlib import Path
from google import genai

client = genai.Client()

# 读取并编码图像
with open("car.png", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode('utf-8')

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[
        {"type": "text", "text": "Describe the image."},
        {"type": "image", "data": base64_image, "mime_type": "image/png"}
    ]
)

print(interaction.outputs[-1].text)
```

**JavaScript**：
```javascript
import { GoogleGenAI } from '@google/genai';
import * as fs from 'fs';

const client = new GoogleGenAI({});

const base64Image = fs.readFileSync('car.png', { encoding: 'base64' });

const interaction = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: [
        { type: 'text', text: 'Describe the image.' },
        { type: 'image', data: base64Image, mime_type: 'image/png' }
    ]
});

console.log(interaction.outputs[interaction.outputs.length - 1].text);
```


#### 使用远程 URL

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[
        {
            "type": "image",
            "uri": "https://example.com/image.jpg",
        },
        {"type": "text", "text": "Describe what you see."}
    ],
)

print(interaction.outputs[-1].text)
```

#### 使用 Files API

**Python**：
```python
from google import genai
import time

client = genai.Client()

# 1. 上传文件到 Files API
file = client.files.upload(file="car.png")

# 2. 等待处理完成
while client.files.get(name=file.name).state != "ACTIVE":
    time.sleep(2)

# 3. 在交互中使用
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[
        {"type": "image", "uri": file.uri},
        {"type": "text", "text": "Describe what you see."}
    ],
)

print(interaction.outputs[-1].text)
```

### 音频理解

**Python**：
```python
import base64
from google import genai

client = genai.Client()

# 读取并编码音频
with open("speech.wav", "rb") as f:
    base64_audio = base64.b64encode(f.read()).decode('utf-8')

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[
        {"type": "text", "text": "What does this audio say?"},
        {"type": "audio", "data": base64_audio, "mime_type": "audio/wav"}
    ]
)

print(interaction.outputs[-1].text)
```

### 视频理解

**Python**：
```python
import base64
from google import genai

client = genai.Client()

# 读取并编码视频
with open("video.mp4", "rb") as f:
    base64_video = base64.b64encode(f.read()).decode('utf-8')

print("Analyzing video...")
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[
        {"type": "text", "text": "What is happening in this video? Provide a timestamped summary."},
        {"type": "video", "data": base64_video, "mime_type": "video/mp4"}
    ]
)

print(interaction.outputs[-1].text)
```

### PDF 文档理解

**Python**：
```python
import base64
from google import genai

client = genai.Client()

with open("sample.pdf", "rb") as f:
    base64_pdf = base64.b64encode(f.read()).decode('utf-8')

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[
        {"type": "text", "text": "What is this document about?"},
        {"type": "document", "data": base64_pdf, "mime_type": "application/pdf"}
    ]
)

print(interaction.outputs[-1].text)
```

### 图像生成

**Python**：
```python
import base64
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-pro-image-preview",
    input="Generate an image of a futuristic city.",
    response_modalities=["IMAGE"]  # 指定输出模态
)

# 保存生成的图像
for output in interaction.outputs:
    if output.type == "image":
        print(f"Generated image with mime_type: {output.mime_type}")
        with open("generated_city.png", "wb") as f:
            f.write(base64.b64decode(output.data))
```

---

## 代理能力

### 使用 Deep Research Agent

Deep Research Agent 是一个专门的代理，用于执行深度研究任务。

**重要**：
- Deep Research Agent **只能通过 Interactions API** 访问
- 必须使用 `background=true` 异步执行
- 研究任务可能需要几分钟到60分钟

#### 基础用法

**Python**：
```python
import time
from google import genai

client = genai.Client()

# 1. 启动研究任务
interaction = client.interactions.create(
    input="Research the history of Google TPUs with a focus on 2025 and 2026.",
    agent="deep-research-pro-preview-12-2025",
    background=True  # 必须异步执行
)

print(f"Research started. Interaction ID: {interaction.id}")

# 2. 轮询获取结果
while True:
    result = client.interactions.get(interaction.id)
    print(f"Status: {result.status}")
    
    if result.status == "completed":
        print("\nFinal Report:\n", result.outputs[-1].text)
        break
    elif result.status in ["failed", "cancelled"]:
        print(f"Failed with status: {result.status}")
        break
    
    time.sleep(10)  # 等待10秒后再次检查
```


**JavaScript**：
```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

// 1. 启动研究任务
const interaction = await client.interactions.create({
    input: 'Research the history of Google TPUs with a focus on 2025 and 2026.',
    agent: 'deep-research-pro-preview-12-2025',
    background: true
});

console.log(`Research started. Interaction ID: ${interaction.id}`);

// 2. 轮询获取结果
while (true) {
    const result = await client.interactions.get(interaction.id);
    console.log(`Status: ${result.status}`);
    
    if (result.status === 'completed') {
        console.log('\nFinal Report:\n', result.outputs[result.outputs.length - 1].text);
        break;
    } else if (['failed', 'cancelled'].includes(result.status)) {
        console.log(`Failed with status: ${result.status}`);
        break;
    }
    
    await new Promise(resolve => setTimeout(resolve, 10000));
}
```

### 混合使用 Agent 和 Model

可以在对话中混合使用 Agent 和 Model，通过 `previous_interaction_id` 连接。

**Python**：
```python
from google import genai
import time

client = genai.Client()

# 1. 使用 Deep Research Agent 收集数据
research = client.interactions.create(
    agent="deep-research-pro-preview-12-2025",
    input="Research the competitive landscape of EV batteries.",
    background=True
)

# 等待研究完成
while True:
    result = client.interactions.get(research.id)
    if result.status == "completed":
        break
    time.sleep(10)

# 2. 使用标准模型总结
summary = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Summarize the key findings in 3 bullet points.",
    previous_interaction_id=research.id  # 引用研究结果
)

print(summary.outputs[-1].text)

# 3. 继续深入分析
followup = client.interactions.create(
    model="gemini-3-flash-preview",
    input="What are the investment opportunities?",
    previous_interaction_id=summary.id
)

print(followup.outputs[-1].text)
```

---

## 工具系统

Interactions API 统一了三种工具类型：
1. **Function Calling**（自定义函数）
2. **Built-in Tools**（内置工具）
3. **Remote MCP**（远程 MCP 服务器）

### Function Calling（自定义函数）

#### 基础用法

**Python**：
```python
from google import genai

client = genai.Client()

# 1. 定义工具
def get_weather(location: str):
    """获取指定位置的天气"""
    return f"The weather in {location} is sunny."

weather_tool = {
    "type": "function",
    "name": "get_weather",
    "description": "Gets the weather for a given location.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string", 
                "description": "The city and state, e.g. San Francisco, CA"
            }
        },
        "required": ["location"]
    }
}

# 2. 发送请求（包含工具定义）
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="What is the weather in Paris?",
    tools=[weather_tool]
)

# 3. 处理工具调用
for output in interaction.outputs:
    if output.type == "function_call":
        print(f"Tool Call: {output.name}({output.arguments})")
        
        # 执行工具
        result = get_weather(**output.arguments)
        
        # 4. 发送工具结果
        interaction = client.interactions.create(
            model="gemini-3-flash-preview",
            previous_interaction_id=interaction.id,
            input=[{
                "type": "function_result",
                "name": output.name,
                "call_id": output.id,
                "result": result
            }]
        )
        
        print(f"Response: {interaction.outputs[-1].text}")
```

**JavaScript**：
```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

// 1. 定义工具
const weatherTool = {
    type: 'function',
    name: 'get_weather',
    description: 'Gets the weather for a given location.',
    parameters: {
        type: 'object',
        properties: {
            location: { 
                type: 'string', 
                description: 'The city and state, e.g. San Francisco, CA' 
            }
        },
        required: ['location']
    }
};

// 2. 发送请求
let interaction = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: 'What is the weather in Paris?',
    tools: [weatherTool]
});

// 3. 处理工具调用
for (const output of interaction.outputs) {
    if (output.type === 'function_call') {
        console.log(`Tool Call: ${output.name}(${JSON.stringify(output.arguments)})`);
        
        // 执行工具（模拟）
        const result = `The weather in ${output.arguments.location} is sunny.`;
        
        // 4. 发送工具结果
        interaction = await client.interactions.create({
            model: 'gemini-3-flash-preview',
            previous_interaction_id: interaction.id,
            input: [{
                type: 'function_result',
                name: output.name,
                call_id: output.id,
                result: result
            }]
        });
        
        console.log(`Response: ${interaction.outputs[interaction.outputs.length - 1].text}`);
    }
}
```


#### 客户端状态管理的 Function Calling

如果不想使用服务端状态，可以手动管理对话历史。

**Python**：
```python
from google import genai

client = genai.Client()

# 定义工具
functions = [{
    "type": "function",
    "name": "schedule_meeting",
    "description": "Schedules a meeting with specified attendees.",
    "parameters": {
        "type": "object",
        "properties": {
            "attendees": {"type": "array", "items": {"type": "string"}},
            "date": {"type": "string", "description": "Date (e.g., 2024-07-29)"},
            "time": {"type": "string", "description": "Time (e.g., 15:00)"},
            "topic": {"type": "string", "description": "Meeting subject"},
        },
        "required": ["attendees", "date", "time", "topic"],
    },
}]

# 手动维护历史
history = [{
    "role": "user",
    "content": [{
        "type": "text", 
        "text": "Schedule a meeting for 2025-11-01 at 10 am with Peter and Amir about the Next Gen API."
    }]
}]

# 1. 模型决定调用函数
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input=history,
    tools=functions
)

# 添加模型响应到历史
history.append({"role": "model", "content": interaction.outputs})

for output in interaction.outputs:
    if output.type == "function_call":
        print(f"Function call: {output.name} with arguments {output.arguments}")
        
        # 2. 执行函数（模拟）
        call_result = "Meeting scheduled successfully."
        
        # 3. 添加函数结果到历史
        history.append({
            "role": "user", 
            "content": [{
                "type": "function_result", 
                "name": output.name, 
                "call_id": output.id, 
                "result": call_result
            }]
        })
        
        # 4. 发送结果回模型
        interaction2 = client.interactions.create(
            model="gemini-3-flash-preview",
            input=history,
        )
        print(f"Final response: {interaction2.outputs[-1].text}")
```

### Built-in Tools（内置工具）

Gemini 提供了三个内置工具，API 会自动执行这些工具。

#### Google Search（网络搜索）

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Who won the last Super Bowl?",
    tools=[{"type": "google_search"}]
)

# 查找文本输出（不是 GoogleSearchResultContent）
text_output = next((o for o in interaction.outputs if o.type == "text"), None)
if text_output:
    print(text_output.text)
```

**特性**：
- ✅ 自动执行搜索
- ✅ 自动处理搜索结果
- ✅ 生成基于搜索结果的回答
- ⚠️ 2026年1月5日前免费，之后按标准定价

#### Code Execution（代码执行）

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Calculate the 50th Fibonacci number.",
    tools=[{"type": "code_execution"}]
)

print(interaction.outputs[-1].text)
```

**特性**：
- ✅ 模型可以编写和执行 Python 代码
- ✅ 返回执行结果
- ✅ 适用于数据分析、计算任务

#### URL Context（网页内容理解）

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Summarize the content of https://www.wikipedia.org/",
    tools=[{"type": "url_context"}]
)

# 查找文本输出
text_output = next((o for o in interaction.outputs if o.type == "text"), None)
if text_output:
    print(text_output.text)
```

**特性**：
- ✅ 自动访问和理解网页内容
- ✅ 提取结构化信息
- ✅ 基于网页内容生成回答

### Remote MCP（远程 MCP 服务器）

Remote MCP 允许 Gemini API 直接调用远程服务器上的工具。

**Python**：
```python
import datetime
from google import genai

client = genai.Client()

# 定义 MCP 服务器
mcp_server = {
    "type": "mcp_server",
    "name": "weather_service",
    "url": "https://gemini-api-demos.uc.r.appspot.com/mcp"
}

today = datetime.date.today().strftime("%d %B %Y")

interaction = client.interactions.create(
    model="gemini-2.5-flash",
    input="What is the weather like in New York today?",
    tools=[mcp_server],
    system_instruction=f"Today is {today}."
)

print(interaction.outputs[-1].text)
```

**JavaScript**：
```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

const mcpServer = {
    type: 'mcp_server',
    name: 'weather_service',
    url: 'https://gemini-api-demos.uc.r.appspot.com/mcp'
};

const today = new Date().toDateString();

const interaction = await client.interactions.create({
    model: 'gemini-2.5-flash',
    input: 'What is the weather like in New York today?',
    tools: [mcpServer],
    system_instruction: `Today is ${today}.`
});

console.log(interaction.outputs[interaction.outputs.length - 1].text);
```

**重要限制**：
- ⚠️ 仅支持 Streamable HTTP 服务器（不支持 SSE 服务器）
- ⚠️ Gemini 3 模型暂不支持（即将支持）
- ⚠️ MCP 服务器名称不应包含 "-" 字符（使用 snake_case）


---

## 高级特性

### 流式响应

接收实时生成的响应，提升用户体验。

#### 基础流式响应

**Python**：
```python
from google import genai

client = genai.Client()

stream = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Explain quantum entanglement in simple terms.",
    stream=True
)

for chunk in stream:
    if chunk.event_type == "content.delta":
        if chunk.delta.type == "text":
            print(chunk.delta.text, end="", flush=True)
        elif chunk.delta.type == "thought":
            print(chunk.delta.thought, end="", flush=True)
    elif chunk.event_type == "interaction.complete":
        print(f"\n\n--- Stream Finished ---")
        print(f"Total Tokens: {chunk.interaction.usage.total_tokens}")
```

**JavaScript**：
```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

const stream = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: 'Explain quantum entanglement in simple terms.',
    stream: true,
});

for await (const chunk of stream) {
    if (chunk.event_type === 'content.delta') {
        if (chunk.delta.type === 'text' && 'text' in chunk.delta) {
            process.stdout.write(chunk.delta.text);
        } else if (chunk.delta.type === 'thought' && 'thought' in chunk.delta) {
            process.stdout.write(chunk.delta.thought);
        }
    } else if (chunk.event_type === 'interaction.complete') {
        console.log('\n\n--- Stream Finished ---');
        console.log(`Total Tokens: ${chunk.interaction.usage.total_tokens}`);
    }
}
```

#### 事件类型

| 事件类型 | 说明 |
|---------|------|
| `interaction.start` | 交互开始 |
| `content.delta` | 内容增量更新 |
| `interaction.complete` | 交互完成 |
| `error` | 错误事件 |

#### content.delta 的类型

| Delta 类型 | 说明 |
|-----------|------|
| `text` | 文本内容 |
| `thought` | 思考过程 |
| `thought_summary` | 思考摘要（Deep Research） |
| `image` | 图像数据 |
| `function_call` | 函数调用 |

### 生成配置

自定义模型的生成行为。

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Tell me a story about a brave knight.",
    generation_config={
        "temperature": 0.7,           # 创造性（0-2）
        "max_output_tokens": 500,     # 最大输出长度
        "thinking_level": "low",      # 思考级别
        "top_p": 0.95,                # 核采样
        "top_k": 40                   # Top-K 采样
    }
)

print(interaction.outputs[-1].text)
```

#### thinking_level 参数

控制模型的推理深度（适用于 Gemini 2.5 及更新模型）。

| 级别 | 说明 | 适用模型 |
|------|------|---------|
| `minimal` | 几乎不思考，最小延迟和成本 | 仅 Flash 模型 |
| `low` | 轻度推理，平衡延迟和成本 | 所有思考模型 |
| `medium` | 中等思考，适合大多数任务 | 仅 Flash 模型 |
| `high` | 最大推理深度（默认） | 所有思考模型 |

### 结构化输出（JSON Schema）

强制模型输出符合指定 JSON Schema 的结构化数据。

#### 基础用法

**Python**：
```python
from google import genai
from pydantic import BaseModel, Field
from typing import Literal, Union

client = genai.Client()

# 定义数据模型
class SpamDetails(BaseModel):
    reason: str = Field(description="The reason why the content is considered spam.")
    spam_type: Literal["phishing", "scam", "unsolicited promotion", "other"]

class NotSpamDetails(BaseModel):
    summary: str = Field(description="A brief summary of the content.")
    is_safe: bool = Field(description="Whether the content is safe for all audiences.")

class ModerationResult(BaseModel):
    decision: Union[SpamDetails, NotSpamDetails]

# 使用结构化输出
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Moderate the following content: 'Congratulations! You've won a free cruise. Click here to claim your prize: www.definitely-not-a-scam.com'",
    response_format=ModerationResult.model_json_schema(),
)

# 解析输出
parsed_output = ModerationResult.model_validate_json(interaction.outputs[-1].text)
print(parsed_output)
```

**JavaScript**：
```javascript
import { GoogleGenAI } from '@google/genai';
import { z } from 'zod';

const client = new GoogleGenAI({});

// 定义 Schema
const moderationSchema = z.object({
    decision: z.union([
        z.object({
            reason: z.string().describe('The reason why the content is considered spam.'),
            spam_type: z.enum(['phishing', 'scam', 'unsolicited promotion', 'other']),
        }),
        z.object({
            summary: z.string().describe('A brief summary of the content.'),
            is_safe: z.boolean().describe('Whether the content is safe for all audiences.'),
        }),
    ]),
});

const interaction = await client.interactions.create({
    model: 'gemini-3-flash-preview',
    input: "Moderate the following content: 'Congratulations! You've won a free cruise.'",
    response_format: z.toJSONSchema(moderationSchema),
});

console.log(interaction.outputs[0].text);
```


#### 结合工具使用

可以将结构化输出与工具结合，先使用工具获取信息，再强制输出结构化数据。

**Python**：
```python
from google import genai
from pydantic import BaseModel

client = genai.Client()

class GameResult(BaseModel):
    winning_team: str
    score: str

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Who won the last euro?",
    tools=[{"type": "google_search"}],  # 先搜索
    response_format=GameResult.model_json_schema(),  # 再强制 JSON 输出
)

result = GameResult.model_validate_json(interaction.outputs[-1].text)
print(f"Winner: {result.winning_team}, Score: {result.score}")
```

### 系统指令

为模型设置全局行为指南。

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="What is 2+2?",
    system_instruction="You are a helpful math tutor. Always explain your reasoning step by step."
)

print(interaction.outputs[-1].text)
```

---

## 最佳实践

### 1. 利用服务端状态管理

使用 `previous_interaction_id` 可以提高缓存命中率，降低成本和延迟。

```python
# ✅ 推荐：使用服务端状态
interaction2 = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Continue the conversation",
    previous_interaction_id=interaction1.id
)

# ❌ 不推荐：每次发送完整历史
interaction2 = client.interactions.create(
    model="gemini-3-flash-preview",
    input=[...full_history...]
)
```

### 2. 混合使用 Agent 和 Model

利用不同实体的优势，组合使用。

```python
# 1. 使用 Agent 收集数据
research = client.interactions.create(
    agent="deep-research-pro-preview-12-2025",
    input="Research topic X",
    background=True
)

# 2. 使用 Model 总结或重新格式化
summary = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Summarize in 3 points",
    previous_interaction_id=research.id
)
```

### 3. 选择合适的工具类型

| 场景 | 推荐工具 |
|------|---------|
| 需要最新信息 | `google_search` |
| 理解特定网页 | `url_context` |
| 数据计算 | `code_execution` |
| 自定义业务逻辑 | Function Calling |
| 远程服务集成 | Remote MCP |

### 4. 合理使用 thinking_level

| 任务类型 | 推荐级别 |
|---------|---------|
| 简单聊天、指令跟随 | `minimal` 或 `low` |
| 一般任务 | `medium` |
| 复杂推理、数学问题 | `high` |

### 5. 流式响应提升体验

对于长时间生成的内容，使用流式响应提供实时反馈。

```python
stream = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Write a long essay...",
    stream=True
)

for chunk in stream:
    if chunk.event_type == "content.delta":
        print(chunk.delta.text, end="", flush=True)
```

### 6. 错误处理

```python
try:
    interaction = client.interactions.create(
        model="gemini-3-flash-preview",
        input="Your prompt"
    )
except Exception as e:
    print(f"Error: {e}")
    # 处理错误
```

### 7. 数据存储策略

**需要多轮对话**：
```python
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Your prompt",
    store=True  # 默认值，可省略
)
```

**一次性查询**：
```python
interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Your prompt",
    store=False  # 不存储，节省配额
)
```

---

## 限制与注意事项

### Beta 状态

- ⚠️ Interactions API 目前处于 **Beta 阶段**
- ⚠️ 功能和架构可能会发生**破坏性变更**
- ⚠️ 生产环境建议继续使用 `generateContent` API

### 不支持的功能

目前不支持以下功能（即将支持）：
- ❌ Grounding with Google Maps
- ❌ Computer Use
- ❌ 组合使用 MCP、Function Call 和 Built-in Tools

### 工具限制

- ⚠️ Remote MCP 不支持 Gemini 3 模型（即将支持）
- ⚠️ Remote MCP 仅支持 Streamable HTTP 服务器
- ⚠️ MCP 服务器名称不应包含 "-" 字符

### 输出顺序问题

- ⚠️ Built-in Tools（`google_search`、`url_context`）的内容顺序可能不正确
- ⚠️ 文本可能在工具执行和结果之前出现
- ✅ 修复正在进行中

### 存储限制

- **付费版**：Interaction 保留 55 天
- **免费版**：Interaction 保留 1 天
- `store=false` 与 `background=true` 不兼容
- `store=false` 时无法使用 `previous_interaction_id`

### 支持的模型和代理

| 名称 | 类型 | Model/Agent ID |
|------|------|----------------|
| Gemini 2.5 Pro | Model | `gemini-2.5-pro` |
| Gemini 2.5 Flash | Model | `gemini-2.5-flash` |
| Gemini 2.5 Flash-lite | Model | `gemini-2.5-flash-lite` |
| Gemini 3 Pro Preview | Model | `gemini-3-pro-preview` |
| Gemini 3 Flash Preview | Model | `gemini-3-flash-preview` |
| Deep Research Preview | Agent | `deep-research-pro-preview-12-2025` |

---

## 反馈与支持

### 提交反馈

你的反馈对 Interactions API 的发展至关重要。请通过以下渠道分享你的想法、报告 Bug 或请求新功能：

- [Google AI Developer Community Forum](https://discuss.ai.google.dev/c/gemini-api/4)

### 相关资源

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [Deep Research Agent 指南](https://ai.google.dev/gemini-api/docs/deep-research)
- [API 参考](https://ai.google.dev/api/interactions-api)
- [定价信息](https://ai.google.dev/gemini-api/docs/pricing)

---

**文档版本**：v1.0  
**最后更新**：2025-12-20  
**适用 SDK 版本**：
- Python: `google-genai >= 1.55.0`
- JavaScript: `@google/genai >= 1.33.0`
