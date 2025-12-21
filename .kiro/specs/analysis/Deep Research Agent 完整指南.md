# Gemini Deep Research Agent 完整技术指南

## 📋 目录

- [概述](#概述)
- [核心概念](#核心概念)
- [快速开始](#快速开始)
- [执行模式](#执行模式)
- [研究能力](#研究能力)
- [可控性与格式化](#可控性与格式化)
- [流式响应](#流式响应)
- [后续对话](#后续对话)
- [最佳实践](#最佳实践)
- [安全考虑](#安全考虑)
- [限制与定价](#限制与定价)

---

## 概述

### 什么是 Deep Research Agent

`Deep Research Agent` 是 Google Gemini 提供的专门代理，用于自主规划、执行和综合多步骤研究任务。它由 **Gemini 3 Pro** 驱动，能够导航复杂的信息环境，使用网络搜索和你自己的数据生成详细的、带引用的研究报告。

**核心特性**：
- 🤖 **自主规划**：自动制定研究计划
- 🔍 **多步骤搜索**：迭代搜索和阅读
- 📊 **详细报告**：生成带引用的长篇分析
- ⏱️ **长时间运行**：任务可能需要几分钟到60分钟
- 🔄 **异步执行**：必须使用后台模式
- 📝 **可控输出**：支持格式化和语气调整

### 关键特点

| 特性 | 标准 Gemini 模型 | Deep Research Agent |
|------|-----------------|---------------------|
| **延迟** | 秒级 | 分钟级（异步） |
| **流程** | 生成 → 输出 | 规划 → 搜索 → 阅读 → 迭代 → 输出 |
| **输出** | 对话文本、代码、摘要 | 详细报告、长篇分析、对比表格 |
| **适用场景** | 聊天机器人、提取、创意写作 | 市场分析、尽职调查、文献综述、竞争分析 |

### 重要约束

> **必须通过 Interactions API 访问**  
> Deep Research Agent 只能通过 Interactions API 使用，无法通过 `generate_content` 访问。

> **必须异步执行**  
> 研究任务涉及迭代搜索和阅读，通常超过标准 API 调用的超时限制。必须设置 `background=true`。

> **预览状态**  
> Deep Research Agent 目前处于预览阶段，功能可能会发生变化。

---

## 核心概念

### 工作流程

Deep Research Agent 的研究过程包含以下步骤：

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

### 默认工具

Deep Research Agent 默认可以访问：
- ✅ `google_search`：搜索公网信息
- ✅ `url_context`：访问和理解网页内容

**注意**：这些工具是默认启用的，无需显式指定。

### 时间范围

| 任务复杂度 | 预期时间 |
|-----------|---------|
| 简单查询 | 2-5 分钟 |
| 中等复杂度 | 5-15 分钟 |
| 复杂研究 | 15-30 分钟 |
| 最大限制 | 60 分钟 |

---

## 快速开始

### 安装依赖

**Python**：
```bash
pip install google-genai>=1.55.0
```

**JavaScript**：
```bash
npm install @google/genai@^1.33.0
```

### 基础示例

#### Python

```python
import time
from google import genai

client = genai.Client()

# 1. 启动研究任务
interaction = client.interactions.create(
    input="Research the history of Google TPUs.",
    agent='deep-research-pro-preview-12-2025',
    background=True  # 必须异步执行
)

print(f"Research started: {interaction.id}")

# 2. 轮询获取结果
while True:
    interaction = client.interactions.get(interaction.id)
    
    if interaction.status == "completed":
        print(interaction.outputs[-1].text)
        break
    elif interaction.status == "failed":
        print(f"Research failed: {interaction.error}")
        break
    
    time.sleep(10)  # 等待10秒后再次检查
```


#### JavaScript

```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

// 1. 启动研究任务
const interaction = await client.interactions.create({
    input: 'Research the history of Google TPUs.',
    agent: 'deep-research-pro-preview-12-2025',
    background: true
});

console.log(`Research started: ${interaction.id}`);

// 2. 轮询获取结果
while (true) {
    const result = await client.interactions.get(interaction.id);
    
    if (result.status === 'completed') {
        console.log(result.outputs[result.outputs.length - 1].text);
        break;
    } else if (result.status === 'failed') {
        console.log(`Research failed: ${result.error}`);
        break;
    }
    
    await new Promise(resolve => setTimeout(resolve, 10000));
}
```

#### REST

```bash
# 1. 启动研究任务
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "input": "Research the history of Google TPUs.",
    "agent": "deep-research-pro-preview-12-2025",
    "background": true
}'

# 2. 轮询获取结果（替换 INTERACTION_ID）
# curl -X GET "https://generativelanguage.googleapis.com/v1beta/interactions/INTERACTION_ID" \
# -H "x-goog-api-key: $GEMINI_API_KEY"
```

---

## 执行模式

### 异步执行（必须）

Deep Research Agent 必须使用 `background=true` 异步执行。

#### 执行流程

```
1. 调用 interactions.create(background=true)
   ↓
2. 立即返回部分 Interaction 对象（包含 id 和 status）
   ↓
3. 研究任务在后台执行
   ↓
4. 定期调用 interactions.get(id) 检查状态
   ↓
5. status 从 "in_progress" 变为 "completed" 或 "failed"
   ↓
6. 获取最终报告
```

#### 状态值

| 状态 | 说明 |
|------|------|
| `in_progress` | 研究正在进行中 |
| `completed` | 研究成功完成 |
| `failed` | 研究失败 |
| `cancelled` | 研究被取消 |

### 轮询策略

**推荐轮询间隔**：
- 简单查询：5-10 秒
- 复杂研究：10-15 秒

**Python 示例**：
```python
import time
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    input="Research the competitive landscape of EV batteries.",
    agent="deep-research-pro-preview-12-2025",
    background=True
)

print(f"Research started: {interaction.id}")

# 轮询策略
poll_interval = 10  # 秒
max_polls = 360     # 最多轮询60分钟

for i in range(max_polls):
    result = client.interactions.get(interaction.id)
    print(f"[{i * poll_interval}s] Status: {result.status}")
    
    if result.status == "completed":
        print("\n=== Final Report ===")
        print(result.outputs[-1].text)
        break
    elif result.status in ["failed", "cancelled"]:
        print(f"Research {result.status}: {result.error}")
        break
    
    time.sleep(poll_interval)
else:
    print("Timeout: Research exceeded maximum time")
```

---

## 研究能力

### 使用公网数据

默认情况下，Deep Research Agent 可以访问公网信息。

**Python**：
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    input="Research the latest developments in quantum computing in 2025.",
    agent="deep-research-pro-preview-12-2025",
    background=True
)

# 等待完成...
```

**Agent 会自动**：
1. 使用 `google_search` 搜索相关信息
2. 使用 `url_context` 访问相关网页
3. 迭代搜索和阅读
4. 综合信息生成报告

### 结合私有数据

可以添加 `file_search` 工具，让 Agent 访问你的私有数据。

**Python**：
```python
import time
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    input="Compare our 2025 fiscal year report against current public web news.",
    agent="deep-research-pro-preview-12-2025",
    background=True,
    tools=[
        {
            "type": "file_search",
            "file_search_store_names": ['fileSearchStores/my-store-name']
        }
    ]
)

# 等待完成...
while True:
    result = client.interactions.get(interaction.id)
    if result.status == "completed":
        print(result.outputs[-1].text)
        break
    time.sleep(10)
```

**JavaScript**：
```javascript
const interaction = await client.interactions.create({
    input: 'Compare our 2025 fiscal year report against current public web news.',
    agent: 'deep-research-pro-preview-12-2025',
    background: true,
    tools: [
        { 
            type: 'file_search', 
            file_search_store_names: ['fileSearchStores/my-store-name'] 
        },
    ]
});
```

**注意**：
- ⚠️ 使用 Deep Research 与 `file_search` 仍处于实验阶段
- ✅ 需要先创建 File Search Store 并上传文件


---

## 可控性与格式化

### 指定输出格式

可以在 prompt 中明确指定输出格式，Agent 会遵循你的要求。

#### 技术报告格式

**Python**：
```python
from google import genai

client = genai.Client()

prompt = """
Research the competitive landscape of EV batteries.

Format the output as a technical report with the following structure:
1. Executive Summary
2. Key Players (Must include a data table comparing capacity and chemistry)
3. Supply Chain Risks
"""

interaction = client.interactions.create(
    input=prompt,
    agent="deep-research-pro-preview-12-2025",
    background=True
)

# 等待完成...
```

**JavaScript**：
```javascript
const prompt = `
Research the competitive landscape of EV batteries.

Format the output as a technical report with the following structure:
1. Executive Summary
2. Key Players (Must include a data table comparing capacity and chemistry)
3. Supply Chain Risks
`;

const interaction = await client.interactions.create({
    input: prompt,
    agent: 'deep-research-pro-preview-12-2025',
    background: true,
});
```

#### REST

```bash
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "input": "Research the competitive landscape of EV batteries.\n\nFormat the output as a technical report with the following structure: \n1. Executive Summary\n2. Key Players (Must include a data table comparing capacity and chemistry)\n3. Supply Chain Risks",
    "agent": "deep-research-pro-preview-12-2025",
    "background": true
}'
```

### 调整语气和受众

可以指定报告的语气和目标受众。

**示例**：
```python
prompt = """
Research the impact of AI on healthcare.

Target audience: Executive leadership
Tone: Professional and concise
Format: 
- Executive Summary (3 paragraphs)
- Key Findings (bullet points)
- Strategic Recommendations (numbered list)
"""

interaction = client.interactions.create(
    input=prompt,
    agent="deep-research-pro-preview-12-2025",
    background=True
)
```

### 包含数据表格

可以要求 Agent 在报告中包含数据表格。

**示例**：
```python
prompt = """
Research the top 5 cloud providers in 2025.

Include a comparison table with the following columns:
- Provider Name
- Market Share (%)
- Key Services
- Pricing Model
- Target Customers
"""

interaction = client.interactions.create(
    input=prompt,
    agent="deep-research-pro-preview-12-2025",
    background=True
)
```

---

## 流式响应

### 启用流式响应

使用流式响应可以实时查看研究进度和中间思考过程。

**必须设置**：
- `stream=True`
- `background=True`
- `agent_config.thinking_summaries="auto"`

#### Python

```python
from google import genai

client = genai.Client()

stream = client.interactions.create(
    input="Research the history of Google TPUs.",
    agent="deep-research-pro-preview-12-2025",
    background=True,
    stream=True,
    agent_config={
        "type": "deep-research",
        "thinking_summaries": "auto"  # 启用思考摘要
    }
)

interaction_id = None
last_event_id = None

for chunk in stream:
    # 1. 捕获 Interaction ID
    if chunk.event_type == "interaction.start":
        interaction_id = chunk.interaction.id
        print(f"Interaction started: {interaction_id}")
    
    # 2. 追踪事件 ID（用于断线重连）
    if chunk.event_id:
        last_event_id = chunk.event_id
    
    # 3. 处理内容
    if chunk.event_type == "content.delta":
        if chunk.delta.type == "text":
            print(chunk.delta.text, end="", flush=True)
        elif chunk.delta.type == "thought_summary":
            print(f"\n💭 {chunk.delta.content.text}", flush=True)
    
    # 4. 完成事件
    elif chunk.event_type == "interaction.complete":
        print("\n✅ Research Complete")
```

#### JavaScript

```javascript
import { GoogleGenAI } from '@google/genai';

const client = new GoogleGenAI({});

const stream = await client.interactions.create({
    input: 'Research the history of Google TPUs.',
    agent: 'deep-research-pro-preview-12-2025',
    background: true,
    stream: true,
    agent_config: {
        type: 'deep-research',
        thinking_summaries: 'auto'
    }
});

let interactionId;
let lastEventId;

for await (const chunk of stream) {
    // 1. 捕获 Interaction ID
    if (chunk.event_type === 'interaction.start') {
        interactionId = chunk.interaction.id;
        console.log(`Interaction started: ${interactionId}`);
    }
    
    // 2. 追踪事件 ID
    if (chunk.event_id) lastEventId = chunk.event_id;
    
    // 3. 处理内容
    if (chunk.event_type === 'content.delta') {
        if (chunk.delta.type === 'text') {
            process.stdout.write(chunk.delta.text);
        } else if (chunk.delta.type === 'thought_summary') {
            console.log(`\n💭 ${chunk.delta.content.text}`);
        }
    } else if (chunk.event_type === 'interaction.complete') {
        console.log('\n✅ Research Complete');
    }
}
```


#### REST

```bash
curl -X POST "https://generativelanguage.googleapis.com/v1beta/interactions?alt=sse" \
-H "Content-Type: application/json" \
-H "x-goog-api-key: $GEMINI_API_KEY" \
-d '{
    "input": "Research the history of Google TPUs.",
    "agent": "deep-research-pro-preview-12-2025",
    "background": true,
    "stream": true,
    "agent_config": {
        "type": "deep-research",
        "thinking_summaries": "auto"
    }
}'
```

**注意**：查找 `interaction.start` 事件以获取 interaction ID。

### 思考摘要示例

启用 `thinking_summaries: "auto"` 后，你会看到类似以下的实时更新：

```
Interaction started: interaction_abc123

💭 正在搜索 "Google TPU history"...
💭 找到 15 个相关结果
💭 正在访问 https://cloud.google.com/tpu/docs/intro-to-tpu
💭 正在分析 TPU 架构演进...
💭 正在搜索 "TPU v4 specifications"...
💭 正在综合多个来源的信息...

# Google TPU 发展历史

## 概述
Google Tensor Processing Unit (TPU) 是...

[完整报告内容]

✅ Research Complete
```

### 断线重连

网络中断时，可以使用 `last_event_id` 恢复流。

#### Python

```python
import time
from google import genai

client = genai.Client()

# 配置
agent_name = 'deep-research-pro-preview-12-2025'
prompt = 'Compare golang SDK test frameworks'

# 状态追踪
last_event_id = None
interaction_id = None
is_complete = False

def process_stream(event_stream):
    """处理事件流"""
    global last_event_id, interaction_id, is_complete
    
    for event in event_stream:
        # 捕获 Interaction ID
        if event.event_type == "interaction.start":
            interaction_id = event.interaction.id
            print(f"Interaction started: {interaction_id}")
        
        # 捕获事件 ID
        if event.event_id:
            last_event_id = event.event_id
        
        # 打印内容
        if event.event_type == "content.delta":
            if event.delta.type == "text":
                print(event.delta.text, end="", flush=True)
            elif event.delta.type == "thought_summary":
                print(f"\n💭 {event.delta.content.text}", flush=True)
        
        # 检查完成
        if event.event_type in ['interaction.complete', 'error']:
            is_complete = True

# 1. 尝试初始流式请求
try:
    print("Starting Research...")
    initial_stream = client.interactions.create(
        input=prompt,
        agent=agent_name,
        background=True,
        stream=True,
        agent_config={
            "type": "deep-research",
            "thinking_summaries": "auto"
        }
    )
    process_stream(initial_stream)
except Exception as e:
    print(f"\n⚠️ Initial connection dropped: {e}")

# 2. 重连循环
while not is_complete and interaction_id:
    print(f"\n🔄 Resuming from event {last_event_id}...")
    time.sleep(2)
    
    try:
        resume_stream = client.interactions.get(
            id=interaction_id,
            stream=True,
            last_event_id=last_event_id
        )
        process_stream(resume_stream)
    except Exception as e:
        print(f"⚠️ Reconnection failed, retrying... ({e})")
```

#### JavaScript

```javascript
let lastEventId;
let interactionId;
let isComplete = false;

// 处理事件流
const handleStream = async (stream) => {
    for await (const chunk of stream) {
        if (chunk.event_type === 'interaction.start') {
            interactionId = chunk.interaction.id;
        }
        if (chunk.event_id) lastEventId = chunk.event_id;
        
        if (chunk.event_type === 'content.delta') {
            if (chunk.delta.type === 'text') {
                process.stdout.write(chunk.delta.text);
            } else if (chunk.delta.type === 'thought_summary') {
                console.log(`\n💭 ${chunk.delta.content.text}`);
            }
        } else if (chunk.event_type === 'interaction.complete') {
            isComplete = true;
        }
    }
};

// 1. 启动任务
try {
    const stream = await client.interactions.create({
        input: 'Compare golang SDK test frameworks',
        agent: 'deep-research-pro-preview-12-2025',
        background: true,
        stream: true,
        agent_config: {
            type: 'deep-research',
            thinking_summaries: 'auto'
        }
    });
    await handleStream(stream);
} catch (e) {
    console.log('\n⚠️ Initial stream interrupted.');
}

// 2. 重连循环
while (!isComplete && interactionId) {
    console.log(`\n🔄 Reconnecting from event ${lastEventId}...`);
    try {
        const stream = await client.interactions.get(interactionId, {
            stream: true,
            last_event_id: lastEventId
        });
        await handleStream(stream);
    } catch (e) {
        console.log('⚠️ Reconnection failed, retrying in 2s...');
        await new Promise(resolve => setTimeout(resolve, 2000));
    }
}
```

---

## 后续对话

研究完成后，可以继续对话以获取澄清、总结或详细说明。

### 基础用法

**Python**：
```python
import time
from google import genai

client = genai.Client()

# 1. 完成初始研究
research = client.interactions.create(
    input="Research the competitive landscape of EV batteries.",
    agent="deep-research-pro-preview-12-2025",
    background=True
)

# 等待完成
while True:
    result = client.interactions.get(research.id)
    if result.status == "completed":
        break
    time.sleep(10)

print("Initial research completed.")

# 2. 后续问题
followup = client.interactions.create(
    input="Can you elaborate on the second point in the report?",
    model="gemini-3-pro-preview",  # 使用标准模型
    previous_interaction_id=research.id  # 引用研究结果
)

print(followup.outputs[-1].text)
```


**JavaScript**：
```javascript
// 1. 完成初始研究
const research = await client.interactions.create({
    input: 'Research the competitive landscape of EV batteries.',
    agent: 'deep-research-pro-preview-12-2025',
    background: true
});

// 等待完成
while (true) {
    const result = await client.interactions.get(research.id);
    if (result.status === 'completed') break;
    await new Promise(resolve => setTimeout(resolve, 10000));
}

// 2. 后续问题
const followup = await client.interactions.create({
    input: 'Can you elaborate on the second point in the report?',
    agent: 'deep-research-pro-preview-12-2025',
    previous_interaction_id: research.id
});

console.log(followup.outputs[followup.outputs.length - 1].text);
```

### 常见后续问题类型

#### 1. 请求澄清

```python
followup = client.interactions.create(
    input="Can you explain what you mean by 'supply chain risks' in more detail?",
    model="gemini-3-pro-preview",
    previous_interaction_id=research.id
)
```

#### 2. 请求总结

```python
followup = client.interactions.create(
    input="Summarize the key findings in 3 bullet points.",
    model="gemini-3-flash-preview",
    previous_interaction_id=research.id
)
```

#### 3. 深入特定部分

```python
followup = client.interactions.create(
    input="Provide more details about the top 3 players mentioned in the report.",
    model="gemini-3-pro-preview",
    previous_interaction_id=research.id
)
```

#### 4. 重新格式化

```python
followup = client.interactions.create(
    input="Convert the report into a PowerPoint-friendly format with slide titles and bullet points.",
    model="gemini-3-flash-preview",
    previous_interaction_id=research.id
)
```

---

## 最佳实践

### 1. 编写清晰的研究查询

**✅ 好的查询**：
```python
prompt = """
Research the competitive landscape of electric vehicle batteries in 2025.

Focus on:
- Top 5 manufacturers by market share
- Key technological innovations
- Supply chain challenges
- Price trends

Include data tables where applicable.
"""
```

**❌ 不好的查询**：
```python
prompt = "Tell me about EV batteries"
```

### 2. 指定输出格式

明确指定你需要的报告结构和格式。

```python
prompt = """
Research [topic].

Format as:
1. Executive Summary (2-3 paragraphs)
2. Detailed Analysis (with subsections)
3. Key Findings (bullet points)
4. Recommendations (numbered list)
5. References
"""
```

### 3. 处理未知数据

指导 Agent 如何处理缺失的信息。

```python
prompt = """
Research the market size of quantum computing in 2025.

If specific figures for 2025 are not available, explicitly state they are 
projections or unavailable rather than estimating.
"""
```

### 4. 提供上下文

为 Agent 提供背景信息或约束条件。

```python
prompt = """
Research the adoption of AI in healthcare.

Context: We are a mid-sized hospital considering AI implementation.
Focus on: Cost-benefit analysis, implementation challenges, regulatory compliance.
"""
```

### 5. 使用流式响应

对于长时间研究，使用流式响应提供实时反馈。

```python
stream = client.interactions.create(
    input="Research [complex topic]",
    agent="deep-research-pro-preview-12-2025",
    background=True,
    stream=True,
    agent_config={
        "type": "deep-research",
        "thinking_summaries": "auto"
    }
)
```

### 6. 合理设置轮询间隔

根据任务复杂度调整轮询间隔。

```python
# 简单查询
poll_interval = 5  # 秒

# 复杂研究
poll_interval = 15  # 秒
```

### 7. 实现超时机制

设置最大等待时间，避免无限等待。

```python
max_wait_time = 3600  # 60分钟
poll_interval = 10
max_polls = max_wait_time // poll_interval

for i in range(max_polls):
    result = client.interactions.get(interaction.id)
    if result.status == "completed":
        break
    time.sleep(poll_interval)
else:
    print("Timeout: Research exceeded maximum time")
```

### 8. 错误处理

```python
try:
    interaction = client.interactions.create(
        input="Research topic",
        agent="deep-research-pro-preview-12-2025",
        background=True
    )
    
    while True:
        result = client.interactions.get(interaction.id)
        if result.status == "completed":
            print(result.outputs[-1].text)
            break
        elif result.status == "failed":
            print(f"Research failed: {result.error}")
            break
        time.sleep(10)
        
except Exception as e:
    print(f"Error: {e}")
```

---

## 安全考虑

### 1. Prompt 注入风险（文件）

Agent 会读取你提供的文件内容。确保上传的文档来自可信来源。

**风险**：
- 恶意文件可能包含隐藏文本，试图操纵 Agent 的输出

**缓解措施**：
- ✅ 只上传来自可信来源的文件
- ✅ 审查上传文件的内容
- ✅ 使用文件扫描工具检测恶意内容

### 2. 网页内容风险

Agent 会搜索和访问公网。虽然有安全过滤器，但仍存在风险。

**风险**：
- Agent 可能遇到并处理恶意网页

**缓解措施**：
- ✅ 审查报告中提供的引用来源
- ✅ 验证关键信息的来源
- ✅ 对敏感主题使用额外验证

### 3. 数据泄露风险

当 Agent 同时访问内部数据和公网时，需要谨慎。

**风险**：
- Agent 可能在总结敏感内部数据时无意中泄露信息

**缓解措施**：
- ✅ 明确指示 Agent 不要泄露敏感信息
- ✅ 审查输出，确保没有敏感数据
- ✅ 考虑分离内部和外部研究任务

**示例**：
```python
prompt = """
Research public market trends in [industry].

IMPORTANT: Do not include or reference any internal company data, 
financial figures, or proprietary information in your response.
"""
```


---

## 限制与定价

### 限制

#### 1. Beta 状态

- ⚠️ Interactions API 处于公开 Beta 阶段
- ⚠️ 功能和架构可能会发生变化

#### 2. 自定义工具

- ❌ 目前无法为 Deep Research Agent 提供自定义 Function Calling 工具
- ❌ 无法提供远程 MCP 服务器

#### 3. 结构化输出

- ❌ Deep Research Agent 目前不支持结构化输出（JSON Schema）
- ❌ 不支持人工批准的规划流程

#### 4. 最大研究时间

- ⚠️ 最大研究时间：**60 分钟**
- ✅ 大多数任务应在 **20 分钟**内完成

#### 5. 存储要求

- ⚠️ 使用 `background=true` 的 Agent 执行需要 `store=true`
- ✅ 默认情况下 `store=true`

#### 6. Google Search 限制

- ⚠️ Google Search 默认启用
- ⚠️ 适用特定的[使用限制](https://ai.google.dev/gemini-api/terms#use-restrictions2)

#### 7. 音频输入

- ❌ 不支持音频输入

### 定价

#### Google Search 免费期

> **重要**：Google Search 工具调用在 **2026年1月5日前免费**。之后将按标准定价收费。

#### 标准定价

- 详细定价信息请参考：[Pricing for Agents](https://ai.google.dev/gemini-api/docs/pricing#pricing-for-agents)

#### 成本优化建议

1. **明确研究范围**：
   ```python
   # ✅ 明确范围，减少不必要的搜索
   prompt = "Research the top 3 EV battery manufacturers in 2025"
   
   # ❌ 范围过广，可能导致过多搜索
   prompt = "Research everything about EV batteries"
   ```

2. **使用缓存**：
   - 利用 `previous_interaction_id` 进行后续问题
   - 避免重复研究相同主题

3. **合理使用 file_search**：
   - 只在必要时添加私有数据
   - 预先筛选相关文件

---

## 使用场景

### 1. 市场分析

```python
prompt = """
Research the global market for renewable energy storage systems in 2025.

Include:
- Market size and growth projections
- Key players and market share
- Technological trends
- Regional analysis (North America, Europe, Asia)
- Investment opportunities

Format as a comprehensive market analysis report.
"""
```

### 2. 竞争分析

```python
prompt = """
Research the competitive landscape of cloud gaming platforms.

Analyze:
- Top 5 platforms by user base
- Pricing models comparison (include table)
- Technology stack and infrastructure
- Strengths and weaknesses
- Market positioning

Target audience: Product strategy team
"""
```

### 3. 技术尽职调查

```python
prompt = """
Research the technical feasibility of implementing blockchain for supply chain tracking.

Focus on:
- Current implementations and case studies
- Technical challenges and solutions
- Cost-benefit analysis
- Scalability considerations
- Security implications

Format as a technical due diligence report.
"""
```

### 4. 文献综述

```python
prompt = """
Research recent advances in natural language processing (2023-2025).

Cover:
- Key breakthroughs and innovations
- Leading research institutions and papers
- Practical applications
- Future directions

Format as an academic literature review with citations.
"""
```

### 5. 政策与法规研究

```python
prompt = """
Research data privacy regulations affecting AI systems in the European Union.

Include:
- Current regulations (GDPR, AI Act)
- Compliance requirements
- Recent enforcement cases
- Upcoming changes
- Best practices for compliance

Format as a compliance guide.
"""
```

---

## 故障排除

### 问题 1：研究超时

**症状**：研究任务超过60分钟仍未完成

**解决方案**：
1. 简化研究查询，缩小范围
2. 将大型研究拆分为多个小任务
3. 提供更明确的约束条件

### 问题 2：输出质量不佳

**症状**：报告缺乏深度或相关性

**解决方案**：
1. 提供更详细的研究指导
2. 明确指定输出格式和结构
3. 添加上下文和背景信息
4. 使用后续问题深入特定部分

### 问题 3：流式响应中断

**症状**：网络中断导致流式响应停止

**解决方案**：
1. 实现断线重连逻辑（使用 `last_event_id`）
2. 保存 `interaction_id` 以便恢复
3. 使用轮询作为备选方案

### 问题 4：引用不完整

**症状**：报告缺少引用或来源

**解决方案**：
1. 在 prompt 中明确要求引用
   ```python
   prompt = """
   Research [topic].
   
   IMPORTANT: Include citations and references for all key claims.
   """
   ```

### 问题 5：研究失败

**症状**：`status` 变为 `"failed"`

**解决方案**：
1. 检查 `error` 字段获取详细信息
2. 验证 API Key 和权限
3. 确认查询符合使用限制
4. 简化查询后重试

---

## 相关资源

### 官方文档

- [Interactions API 文档](https://ai.google.dev/gemini-api/docs/interactions)
- [Gemini 3 Pro 模型](https://ai.google.dev/gemini-api/docs/models/gemini-3)
- [File Search 工具](https://ai.google.dev/gemini-api/docs/file-search)
- [API 参考](https://ai.google.dev/api/interactions-api)

### 社区支持

- [Google AI Developer Community Forum](https://discuss.ai.google.dev/c/gemini-api/4)

### SDK 文档

- [Python SDK](https://github.com/google/generative-ai-python)
- [JavaScript SDK](https://github.com/google/generative-ai-js)

---

## 总结

Deep Research Agent 是一个强大的工具，适用于需要深度分析和综合多个来源信息的场景。通过合理使用其功能，你可以：

✅ 自动化复杂的研究任务  
✅ 生成详细的、带引用的报告  
✅ 结合公网和私有数据  
✅ 自定义输出格式和语气  
✅ 实时监控研究进度  

**关键要点**：
- 必须通过 Interactions API 访问
- 必须使用 `background=true` 异步执行
- 支持流式响应和断线重连
- 可以与标准模型混合使用
- 注意安全考虑和使用限制

---

**文档版本**：v1.0  
**最后更新**：2025-12-20  
**适用 SDK 版本**：
- Python: `google-genai >= 1.55.0`
- JavaScript: `@google/genai >= 1.33.0`  
**Agent ID**：`deep-research-pro-preview-12-2025`
