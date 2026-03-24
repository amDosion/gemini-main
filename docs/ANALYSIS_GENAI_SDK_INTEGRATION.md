# GenAI SDK 集成度分析与客户端管理优化方案

> 基于代码分析，评估本项目对 Google GenAI SDK / Vertex AI SDK / Google ADK 的集成深度，
> 并提出以 ProviderFactory 为中心的统一客户端池管理方案。
> 最后更新：2026-03-24

---

## 1. 概述

本项目深度集成了 Google 全家桶（GenAI SDK、Vertex AI、ADK），同时支持 OpenAI、Ollama、通义千问、Grok 等多 Provider。当前各 Provider **独立管理各自的客户端实例**，缺乏统一的生命周期协调。其中 Google Provider 问题最突出——4 层包装链路过深、自建类型系统与官方 SDK 重复、`agent/client.py` 中直接调用私有 API。

**核心目标**：

1. 清理 Google 封装层，收敛为 `GeminiClientPool` 单入口（详见 `BE-GENAI-CLIENT-REFACTOR.md`）
2. 将 `ProviderFactory` 从"服务注册表"进化为"统一连接池管理器"，协调所有 Provider 的客户端生命周期

---

## 2. SDK 集成度评估

### 2.1 总体评分

| SDK / 框架 | 集成度 | 文件数 | 说明 |
|---|---|---|---|
| **Google GenAI SDK** (`google-genai`) | ⭐⭐⭐⭐⭐ 极深 | 45+ | 覆盖几乎所有 API |
| **Vertex AI SDK** (`google-cloud-aiplatform`) | ⭐⭐⭐⭐⭐ 极深 | 13+ 专属服务 | 图像/视频/Agent Engine 全覆盖 |
| **Google ADK** (`google-adk`) | ⭐⭐⭐⭐☆ 深度 | 8 后端 + 4 前端 | 完整 Agent 生命周期 |
| **Google AI Cookbook** | ⭐☆☆☆☆ | 0 | 无直接引用 |

### 2.2 Google GenAI SDK 已集成功能

| 功能 | 实现文件 | SDK API |
|---|---|---|
| 文本生成（流式/非流式/异步） | `chat_handler.py` | `models.generate_content()` |
| Function Calling | `function_handler.py` | `FunctionDeclaration`, `Tool` |
| 结构化输出 | `schema_handler.py` | `response_json_schema` |
| 多模态（图/视频/音频/文档） | `file_handler.py` | Files API |
| 图像生成（Imagen 3/4, Gemini Image） | `imagen_gemini_api.py` | `models.generate_images()` |
| 视频生成（Veo 3.1） | `video_generation_service.py` | `models.generate_videos()` |
| Embedding | `embedding_service.py` | Embedding API |
| Token 计数 | `token_handler.py` | Token Counting API |
| Live API（双向流式） | `live_api.py` | Bidirectional Streaming |
| Deep Research | `interactions.py` | `interactions.execute()` |
| PDF 提取 | `pdf_extractor.py` | `models.generate_content()` |

### 2.3 Vertex AI SDK 专属服务

位于 `backend/app/services/gemini/vertexai/`：

| 服务 | 文件 | Vertex AI API |
|---|---|---|
| 图像编辑（修复/背景/蒙版） | `inpainting_service.py`, `background_edit_service.py` 等 | `edit_image()` |
| 图像分割 | `segmentation_service.py` | `models.segment_image()` |
| 画布扩展 + 超分 | `expand_service.py` | `edit_image(OUTPAINT)`, `upscale_image()` |
| 虚拟试穿 | `tryon_service.py` | `models.recontext_image()` |
| 视频生成（长轮询） | `video_generation_service.py` | `models.generate_videos()` + `operations.get()` |

协调器（`coordinators/`）根据数据库 `api_mode` 自动路由 Gemini API ↔ Vertex AI。

### 2.4 Google ADK 集成

项目直接使用官方 ADK SDK：

```python
from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService, VertexAiMemoryBankService
```

覆盖：LlmAgent、Runner、Sequential/Parallel/Coordinator 编排、4 个官方 ADK 示例模板、前后端全栈支持。

---

## 3. 当前客户端管理现状与问题

### 3.1 全局视角：5 个孤立的客户端缓存

| Provider | 缓存位置 | 缓存方式 | 生命周期 | 线程安全 |
|---|---|---|---|---|
| **Google** | `GeminiClientPool._clients` | 单例 + dict | 进程级 | ✅ threading.Lock |
| **OpenAI** | `ProviderFactory._client_cache` | dict | 进程级 | ⚠️ GIL |
| **Grok** | `ProviderFactory._client_cache` | dict | 进程级 | ⚠️ GIL |
| **Ollama** | `ProviderFactory._client_cache` | dict | 进程级 | ⚠️ GIL |
| **通义千问** | `ProviderFactory._client_cache` | dict | 进程级 | ⚠️ GIL |
| **MCP** | `MCPSessionPool` | 实例级 | 会话级 | ✅ asyncio.Lock |

**问题**：
- ProviderFactory 缓存的是 **Service 实例**，而 Google 在 Service 内部又有一个独立的 **Client 实例池**（`GeminiClientPool`）
- 缓存分散，无法统一监控、无法全局 warm-up/drain、无法协调总连接数
- 非 Google Provider 依赖 CPython GIL 保证线程安全，在异步场景下有隐患
- Shutdown 时 `shutdown_tasks.py` 只关闭 Redis 和 Browser，遗漏了所有 Provider 的连接池

### 3.2 Google 特有问题：4 层包装链路

> 详细分析见 `BE-GENAI-CLIENT-REFACTOR.md`

一次 `generate_content` 调用的实际路径（5 层）：

```
GoogleService → ChatHandler → OfficialSDKAdapter → GeminiClientPool → agent/client.py → google.genai.Client
```

核心问题：
- 21 处 `getattr(x, "_genai_client", x)` 绕过包装层
- `agent/models.py`（604 行）重新实现了 `generate_content`，调用私有 `client.request()` API
- `agent/types.py`（333 行）重新定义了 SDK 类型
- 4 条语义重叠的 Client 获取路径
- 目标消除约 2315 行 SDK 包装代码

---

## 4. 目标架构

### 4.1 ProviderFactory 进化为连接池管理器

**核心思想**：ProviderFactory 已经是所有 Provider 的路由中枢和服务缓存中心。每个 Provider 的连接池应注册到 Factory，由 Factory 统一协调。

```
ProviderFactory（进化后）
├── 服务注册表（现有）：provider_name → ServiceClass
├── 服务实例缓存（现有）：cache_key → service_instance
└── 连接池注册表（新增）：provider_name → PoolAdapter
    ├── "google"  → GeminiClientPool（已有，注册进来）
    ├── "openai"  → OpenAIPoolAdapter（新建，管理 AsyncOpenAI 实例）
    ├── "grok"    → GrokPoolAdapter（新建，管理 AsyncOpenAI + httpx 实例）
    ├── "ollama"  → OllamaPoolAdapter（新建）
    └── "tongyi"  → TongyiPoolAdapter（新建）
```

新增统一接口：

```python
class ProviderPoolAdapter(Protocol):
    """每个 Provider 的连接池都实现此接口"""
    def get_stats(self) -> dict:            # 连接数、命中率
    def health_check(self) -> bool:         # 健康检查
    def drain(self) -> None:                # 优雅关闭
    def warm_up(self, count: int) -> None:  # 预热

# ProviderFactory 新增方法
class ProviderFactory:
    _pools: Dict[str, ProviderPoolAdapter] = {}

    @classmethod
    def register_pool(cls, provider: str, pool: ProviderPoolAdapter): ...

    @classmethod
    def get_global_stats(cls) -> dict:   # 汇总所有 Provider 的连接状态

    @classmethod
    def drain_all(cls) -> None:          # 优雅关闭所有连接池
```

### 4.2 Google 层：收敛包装链路

> 详细实施计划见 `BE-GENAI-CLIENT-REFACTOR.md`

目标：从 5 层收敛为 3 层。

```
GoogleService                        # 协调器（不变）
  └→ ChatHandler / ImageGenerator ... # 功能 handler（不变）
      └→ GeminiClientPool.get_client() # 直接从池获取官方 client
          └→ google.genai.Client       # 官方 SDK（直接使用）
```

### 4.3 各 Provider 的 Client 管理方式

| Provider | client_type | SDK | 创建方式 | 是否需要池 |
|----------|-------------|-----|----------|-----------|
| **Google** | `google` | `google-genai` | `GeminiClientPool`（单例） | **是**（创建成本高） |
| **OpenAI** | `openai` | `openai` (AsyncOpenAI) | Service 内直接创建 | 否（轻量配置对象） |
| **DeepSeek** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **Moonshot** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **ZhiPu** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **Doubao** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **Hunyuan** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **NVIDIA** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **OpenRouter** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **SiliconFlow** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **Grok** | `grok` | `openai` + `httpx` | GrokService 内创建 | 否（轻量配置对象） |
| **Tongyi/Qwen** | `dashscope` | DashScope + `openai` | 双客户端，Service 内创建 | 否 |
| **Ollama** | `ollama` | `openai` + httpx | 双客户端，Handler 内创建 | 否 |
| **Custom** | `openai` | `openai` (AsyncOpenAI) | 复用 OpenAIService | 否 |
| **MCP** | — | 自定义 MCPClient | `MCPSessionPool`（实例级） | 是（会话池） |

> **核心洞察**：连接池的价值在于避免重复的高成本创建。Google 是唯一需要显式池化的 AI Provider。其他 Provider 的 SDK 内部已有连接复用（`httpx.AsyncClient` 内置连接池）。统一池管理器的价值主要在**生命周期协调**（shutdown drain）和**监控统计**，而非性能。

---

## 5. 实施阶段

### 阶段 1：Google 封装层清理

> 详细计划见 `BE-GENAI-CLIENT-REFACTOR.md` 阶段 1-3

- 消除 21 处 `_genai_client` 绕过 hack
- 收敛 4 条 Client 获取路径为 1 条
- 消除 `agent/models.py`、`agent/types.py` 等 SDK 包装代码（~2315 行）
- 删除 `OfficialSDKAdapter`、`SDKInitializer`、`genai_agent/client.py`

### 阶段 2：定义 ProviderPoolAdapter 接口 + 注册 GeminiClientPool

| 任务 | 文件 | 变更 |
|---|---|---|
| 定义 `ProviderPoolAdapter` Protocol | `common/pool_adapter.py`（新建） | ~30 行 |
| `GeminiClientPool` 实现 adapter 接口 | `client_pool.py` | 添加 `get_stats()` / `drain()` |
| `ProviderFactory` 新增 `_pools` + 注册/查询方法 | `provider_factory.py` | ~40 行 |
| Google 注册时自动注册 pool | `provider_factory.py::_auto_register()` | ~5 行 |

### 阶段 3：其他 Provider 接入连接池注册

| 任务 | 涉及文件 | 说明 |
|---|---|---|
| `OpenAIPoolAdapter`：包装 `AsyncOpenAI` 实例管理 | `openai_service.py` + 新建 adapter | pass-through adapter |
| `GrokPoolAdapter`：包装 Grok client | `grok_service.py` + 新建 adapter | pass-through adapter |
| `OllamaPoolAdapter`：包装 Ollama client | `ollama.py` + 新建 adapter | pass-through adapter |
| `TongyiPoolAdapter`：包装通义千问 client | `tongyi_service.py` + 新建 adapter | pass-through adapter |
| 注册到 `ProviderFactory._pools` | `provider_factory.py::_auto_register()` | |

### 阶段 4：全局监控与运维

| 任务 | 说明 |
|---|---|
| `/api/admin/pool-stats` 端点 | 暴露所有 Provider 的连接池状态 |
| 启动时 warm-up | 根据配置预建连接 |
| 优雅关闭 | app shutdown 时 `ProviderFactory.drain_all()` |
| 日志增强 | 统一的 `[ProviderFactory.Pool]` 日志前缀 |

### 阶段 5：清理前端幽灵依赖

- 从 `package.json` 中移除 `"@google/genai": "^1.32.0"`（前端无任何 import 引用）
- 运行 `npm install` 更新 lock 文件

---

## 6. 验证计划

| 验证项 | 方法 | 通过标准 |
|---|---|---|
| Google 文本生成（流式/非流式） | 集成测试 | 响应正常，无类型错误 |
| Vertex AI 图像操作 | 端到端测试 | 图像编辑/分割/试穿正常 |
| OpenAI / Grok / Ollama / 通义千问正常工作 | 冒烟测试 | 聊天、模型列表正常 |
| 连接池统计准确 | `get_global_stats()` | 各 Provider 统计数据一致 |
| 并发安全 | 50 并发请求 | 无竞态条件 |
| 优雅关闭 | SIGTERM 测试 | 所有连接正常释放 |

---

## 7. 回滚策略

- **阶段 1**：Google 封装层清理使用独立 commit，可逐阶段 revert
- **阶段 2-3**：`ProviderPoolAdapter` 为纯新增，删除即回滚
- **Feature Flag**（可选）：`USE_UNIFIED_POOL=true/false` 控制是否走新链路
- **全量回滚**：git revert 到 ProviderFactory 变更前的 commit

---

## 8. 文档交叉引用

| 文档 | 内容 |
|------|------|
| `BE-GENAI-CLIENT-REFACTOR.md` | Google SDK 包装层的详细修复计划（4 阶段） |
| 本文档 | 全局 Provider 连接池管理方案 + SDK 集成度评估 |

两份文档互补：`BE-GENAI-CLIENT-REFACTOR.md` 聚焦 Google 内部的包装层清理（阶段 1 的前置工作），本文档聚焦跨 Provider 的统一连接池管理器方案。
