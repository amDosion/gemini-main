# OpenAI Service Module

OpenAI Provider 服务模块 - 提供 OpenAI API 服务集成。

## 架构概述

本模块采用 **协调者模式（Coordinator Pattern）** 架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                         Router Layer                            │
│                    (chat.py, imagen.py, etc.)                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ ProviderFactory.create("openai")
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OpenAIService                              │
│                   (Main Coordinator)                            │
│  - 统一的对外接口，仅负责请求分发                                    │
│  - 不包含业务逻辑，委托给具体子服务                                   │
│  - 延迟加载子服务实例                                              │
└────┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
     │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│  Chat  │ │ Image  │ │ Video  │ │ Speech │ │ Model  │
│Handler │ │Generate│ │Generate│ │Generate│ │Manager │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

## 目录结构

```
openai/
├── __init__.py             # 模块导出
├── _shared.py              # 共享客户端/参数过滤/媒体辅助函数
├── openai_service.py       # 主协调器 (Main Coordinator)
├── chat_handler.py         # 聊天服务
├── image_generator.py      # 图像生成服务 (DALL-E)
├── video_generator.py      # 视频生成服务 (Sora)
├── speech_generator.py     # 语音合成服务 (TTS)
└── model_manager.py        # 模型管理器
```

## 核心组件

### OpenAIService (Main Coordinator)

所有 OpenAI 服务的统一入口点，使用委托模式分发请求：

```python
from ..services.provider_factory import ProviderFactory

# 通过工厂创建服务
service = ProviderFactory.create(
    provider="openai",
    api_key=api_key,
    api_url=api_url  # 可选，用于 OpenAI 兼容 API
)

# 使用服务方法
response = await service.chat(messages, model)
images = await service.generate_image(prompt, model)
video = await service.generate_video(prompt, "sora-2")
audio = await service.generate_speech(text, voice)
```

补充约定：

- `OpenAIService` 会复用同一个 `AsyncOpenAI` 客户端给 chat / image / speech 子服务，避免同目录内配置漂移。
- media 子服务统一返回可序列化结果：
  - 图片/视频：`url` + `mime_type`
  - 语音：`url` + `mime_type` + `format`

### 委托的子服务

| 子服务 | 描述 | OpenAIService 方法 |
|--------|------|-------------------|
| ChatHandler | 聊天对话 | `chat()`, `stream_chat()` |
| ImageGenerator | 图像生成 (DALL-E) | `generate_image()` |
| VideoGenerator | 视频生成 (Sora) | `generate_video()` |
| SpeechGenerator | 语音合成 (TTS) | `generate_speech()` |
| ModelManager | 模型管理 | `get_available_models()` |

## 聊天服务 (ChatHandler)

支持流式和非流式聊天：

```python
# 非流式聊天
response = await service.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"}
    ],
    model="gpt-4o"
)

# 流式聊天
async for chunk in service.stream_chat(messages, model):
    print(chunk)
```

## 图像生成 (ImageGenerator)

支持 DALL-E 2 和 DALL-E 3：

```python
images = await service.generate_image(
    prompt="A beautiful sunset over mountains",
    model="dall-e-3",
    size="1024x1024",
    quality="hd",
    n=1
)

for img in images:
    print(f"URL: {img['url']}")
```

### 说明

- 前端传递的 `image_aspect_ratio` 会在服务内部映射成 OpenAI 所需的 `size`。
- 若 OpenAI 返回 `b64_json` 而不是公网 URL，服务会自动转成 `data:` URL，保持前端契约不变。
- 路由层附带的 `session_id`、`message_id` 等内部字段不会透传到 OpenAI API。

### 支持的参数

| 参数 | DALL-E 2 | DALL-E 3 |
|------|----------|----------|
| size | 256x256, 512x512, 1024x1024 | 1024x1024, 1792x1024, 1024x1792 |
| quality | - | standard, hd |
| style | - | vivid, natural |
| n | 1-10 | 1 |

## 视频生成 (VideoGenerator)

支持 OpenAI Sora 视频生成：

```python
video = await service.generate_video(
    prompt="A cinematic sunrise over the ocean",
    model="sora-2",
    aspect_ratio="16:9",
    resolution="1K",
    seconds="4"
)

print(video["url"])
print(video["mime_type"])
print(video["video_size"])
```

### 说明

- 使用 OpenAI Videos API 的异步流程：创建任务、轮询状态、下载 MP4。
- 支持 `sora-2` 和 `sora-2-pro`。
- 前端统一传递 `aspect_ratio`、`resolution`、`seconds`，服务内部映射到 Sora 的 `size` 与 `seconds`。
- 若带参考图，服务会自动读取第一个参考图片并作为 `input_reference` 发送。

## 语音合成 (SpeechGenerator)

支持 TTS 文本转语音：

```python
audio = await service.generate_speech(
    text="Hello, how are you?",
    voice="alloy",
    model="tts-1",
    response_format="mp3"
)

# audio 包含:
# - url: data:audio/... Base64 URL
# - mime_type: 音频 MIME 类型
# - format: 音频格式
```

### 可用语音

| 语音 | 描述 |
|------|------|
| alloy | 中性 |
| echo | 男性 |
| fable | 叙述风格 |
| onyx | 低沉男性 |
| nova | 女性 |
| shimmer | 柔和女性 |

### 说明

- 服务内部会过滤 `audio-gen` 路由带来的非 OpenAI 参数。
- OpenAI 返回的二进制响应会统一转换成 `data:` URL，兼容前端 `audio-gen` 流程和工作流引擎。

## 模型管理 (ModelManager)

获取可用模型列表：

```python
models = await service.get_available_models()

for model in models:
    print(f"{model.id}: {model.name}")
```

### 说明

- 返回列表会去重并按显示名称排序。
- 会过滤当前项目未接入的 OpenAI 模型类型，例如 `embedding`、`moderation`、`realtime`、`transcribe/whisper`，避免污染普通模型选择器。
- 会为 `GPT-4.1`、`GPT-5`、`GPT Image 1`、`Sora 2`、`TTS`、`Codex` 等模型补全更贴近实际用途的名称、描述和能力标签。

## 配置

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_BASE_URL` | API 基础 URL | `https://api.openai.com/v1` |

### OpenAI 兼容 API

支持使用 OpenAI 兼容的第三方 API：

```python
service = ProviderFactory.create(
    provider="openai",
    api_key="your-api-key",
    api_url="https://your-compatible-api.com/v1"
)
```

## 错误处理

```python
from ..errors import (
    ProviderError,
    OperationError,
    APIKeyError,
    RateLimitError,
    ModelNotFoundError
)

try:
    result = await service.generate_image(prompt, model)
except APIKeyError as e:
    # API Key 无效
    pass
except RateLimitError as e:
    # 请求频率限制
    pass
except ModelNotFoundError as e:
    # 模型不存在
    pass
except OperationError as e:
    # 操作执行失败
    pass
```

## 相关文档

- [路由与逻辑分离架构设计文档](../../../docs/路由与逻辑分离架构设计文档.md)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
- [DALL-E API 文档](https://platform.openai.com/docs/guides/images)
- [Sora Video API 文档](https://developers.openai.com/api/docs/guides/video-generation/)
- [TTS API 文档](https://platform.openai.com/docs/guides/text-to-speech)
