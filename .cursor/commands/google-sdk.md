# 查阅 Google 官方 SDK

在开发 Google Gemini 或 ADK 相关功能前，查阅官方 SDK 的相关示例和文档。

## SDK 位置

### 1. Google Generative AI SDK
```
官方SDK/specs/参考/generative-ai-main/generative-ai-main/
```
**用途**: Gemini 聊天、图像生成/编辑、视频、音频、工具调用等

### 2. ADK Python SDK
```
官方SDK/specs/参考/adk-python-main/
```
**用途**: 智能体开发、多智能体、Memory Bank

### 3. ADK Samples
```
官方SDK/specs/参考/adk-samples-main/adk-samples-main/
```
**用途**: 智能体示例、A2A 协议、最佳实践

## 执行步骤

1. **确定功能类型**
   - 基础 Gemini 功能 → 查看 `generative-ai-main`
   - 智能体/多智能体 → 查看 `adk-python-main` + `adk-samples-main`

2. **查找相关示例**
   根据功能在 SDK 中查找对应的示例代码

3. **分析 API 格式**
   - 请求参数
   - 响应结构
   - 错误处理

4. **提供实现建议**
   基于 SDK 示例给出项目中的实现方案

## 功能对照表

| 功能 | SDK | 示例文件 |
|------|-----|---------|
| 聊天 | generative-ai-main | `samples/chat.py` |
| 流式响应 | generative-ai-main | `samples/streaming.py` |
| 图像生成 | generative-ai-main | `samples/image_generation.py` |
| 图像编辑 | generative-ai-main | `samples/image_editing.py` |
| 视频生成 | generative-ai-main | `samples/video_generation.py` |
| 工具调用 | generative-ai-main | `samples/tool_calling.py` |
| 代码执行 | generative-ai-main | `samples/code_execution.py` |
| 搜索/Grounding | generative-ai-main | `samples/grounding.py` |
| 智能体 | adk-python-main | `src/google/adk/agents/` |
| 多智能体 | adk-samples-main | `python/multi_agent/` |
| A2A 协议 | adk-samples-main | `python/a2a/` |
| Memory Bank | adk-python-main | `src/google/adk/memory/` |
| Live API | generative-ai-main | `samples/live_api.py` |

## 使用示例

```
/google-sdk 我要实现图像编辑功能，帮我查看官方 SDK 的实现方式
```

```
/google-sdk 查看多智能体工作流的官方示例
```

```
/google-sdk 如何使用 Gemini 的工具调用功能
```

```
/google-sdk A2A 协议的实现参考
```

```
/google-sdk Live API 实时交互的实现方式
```
