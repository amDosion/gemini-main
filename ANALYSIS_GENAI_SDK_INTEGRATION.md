# GenAI SDK 集成度分析与客户端管理优化方案

> 基于代码分析，评估本项目对 Google GenAI SDK / Vertex AI SDK / Google ADK 的集成深度，
> 并提出以 ProviderFactory 为中心的统一客户端池管理方案。

---

## 1. 概述

本项目深度集成了 Google 全家桶（GenAI SDK、Vertex AI、ADK），同时支持 OpenAI、Ollama、通义千问等多 Provider。当前各 Provider **独立管理各自的客户端实例**，缺乏统一的生命周期协调。其中 Google Provider 问题最突出——4 层包装链路过深、自建类型系统与官方 SDK 重复、`agent/client.py` 中直接调用私有 API。

**核心目标**：

1. 清理 Google 封装层，收敛为 `GeminiClientPool` 单入口
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
| **Ollama** | `ProviderFactory._client_cache` | dict | 进程级 | ⚠️ GIL |
| **通义千问** | `ProviderFactory._client_cache` | dict | 进程级 | ⚠️ GIL |
| **ProviderFactory** | `_client_cache` | dict（服务实例） | 进程级 | ⚠️ GIL |

**问题**：
- ProviderFactory 缓存的是 **Service 实例**，而 Google 在 Service 内部又有一个独立的 **Client 实例池**（`GeminiClientPool`）
- 缓存分散，无法统一监控、无法全局 warm-up/drain、无法协调总连接数
- 非 Google Provider 依赖 CPython GIL 保证线程安全，在异步场景下有隐患

### 3.2 Google 特有问题：4 层包装链路

一次 `generate_content` 调用的实际路径：

```
GoogleService                              # 第 1 层：协调器
  └→ ChatHandler                           # 第 2 层：功能 handler
      └→ OfficialSDKAdapter._get_client()  # 第 3 层：适配器
          └→ GeminiClientPool.get_client()  # 第 4 层：客户端池
              └→ agent/client.py Client     # 第 5 层：自建包装类
                  └→ google.genai.Client    # 最终：官方 SDK
```

**具体问题**：

#### 3.2.1 自建 `agent/client.py` 包装层

`agent/client.py` 中的 `Client` 类（约 400 行）包装了 `google.genai.Client`，主要做：
- 重新实现 `Models`、`AsyncModels`、`InteractionsResource` 等子模块
- 将官方 SDK 的参数和返回值在自建类型（`agent/types.py` 120+ 类型）与官方类型之间转换

这一层在项目早期（官方 SDK 不稳定时）有价值，但现在 `google-genai>=1.55.0` 已经稳定，这层包装：
- 增加维护成本（SDK 升级时需要同步修改）
- 引入间接性（调试困难）
- 自建类型与官方类型不完全兼容

#### 3.2.2 `OfficialSDKAdapter` 冗余

`OfficialSDKAdapter` 的职责是"从池获取 client → 调用 client.models.generate_content()"，但 `ChatHandler` 本身也可以直接通过 `SDKInitializer` 获取 client。两者功能重叠。

#### 3.2.3 `SDKInitializer` 与 `GeminiClientPool` 职责重叠

- `SDKInitializer`：懒加载获取 client，内部调用 `GeminiClientPool`
- `GeminiClientPool`：管理 client 实例池

两者都是"获取 client"的入口，调用方不确定该用哪个。

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
    _pools: Dict[str, ProviderPoolAdapter] = {}  # 新增

    @classmethod
    def register_pool(cls, provider: str, pool: ProviderPoolAdapter): ...

    @classmethod
    def get_global_stats(cls) -> dict:   # 汇总所有 Provider 的连接状态

    @classmethod
    def drain_all(cls) -> None:          # 优雅关闭所有连接池
```

### 4.2 Google 层：收敛包装链路

目标：从 5 层收敛为 3 层。

```
GoogleService                        # 协调器（不变）
  └→ ChatHandler / ImageGenerator ... # 功能 handler（不变）
      └→ GeminiClientPool.get_client() # 直接从池获取官方 client
          └→ google.genai.Client       # 官方 SDK（直接使用）
```

**消除**：
- `agent/client.py` 的 `Client` 包装类 → 直接使用 `google.genai.Client`
- `agent/types.py` 120+ 自建类型 → 直接使用 `google.genai.types`
- `OfficialSDKAdapter` → 合并到 `ChatHandler`
- `SDKInitializer` → 合并到 `GeminiClientPool`

### 4.3 预期最终架构

```
┌─────────────────────────────────────────────────────┐
│                  ProviderFactory                     │
│  ┌──────────────┐  ┌───────────┐  ┌──────────────┐  │
│  │ 服务注册表    │  │ 服务缓存   │  │ 连接池注册表  │  │
│  │ name→Class   │  │ key→inst  │  │ name→Pool    │  │
│  └──────────────┘  └───────────┘  └──────────────┘  │
│                                                      │
│  统一 API: get_global_stats(), drain_all(),          │
│           health_check_all()                         │
└──────────┬──────────┬──────────┬──────────┬──────────┘
           │          │          │          │
    ┌──────▼───┐ ┌────▼────┐ ┌──▼────┐ ┌───▼─────┐
    │GoogleSvc │ │OpenAISvc│ │Ollama │ │TongyiSvc│
    │          │ │         │ │       │ │         │
    │ Pool:    │ │ Pool:   │ │ Pool: │ │ Pool:   │
    │ Gemini   │ │ OpenAI  │ │ Ollama│ │ Tongyi  │
    │ ClientP. │ │ PoolAdp.│ │ PoolA.│ │ PoolAdp.│
    └──────────┘ └─────────┘ └───────┘ └─────────┘
```

---

## 5. 实施阶段

### 阶段 1：定义 ProviderPoolAdapter 接口 + 注册 GeminiClientPool

**范围**：最小变更，验证架构可行性

| 任务 | 文件 | 变更 |
|---|---|---|
| 定义 `ProviderPoolAdapter` Protocol | `backend/app/services/common/pool_adapter.py`（新建） | ~30 行 |
| `GeminiClientPool` 实现 adapter 接口 | `client_pool.py` | 添加 `get_stats()` / `drain()` 等（大部分已有） |
| `ProviderFactory` 新增 `_pools` + 注册/查询方法 | `provider_factory.py` | ~40 行 |
| Google 注册时自动注册 pool | `provider_factory.py::_auto_register()` | ~5 行 |

**验证**：`ProviderFactory.get_global_stats()` 能返回 Google 的连接池统计。

### 阶段 2：消除 `agent/client.py` 包装层

**范围**：最高风险，需要逐文件替换

| 任务 | 涉及文件 | 说明 |
|---|---|---|
| 将 `from ..agent.client import Client` 替换为 `from google import genai` | `client_pool.py`, `official_sdk_adapter.py` | Client 创建改为直接 `genai.Client(...)` |
| 将 `from ..agent.types import ...` 替换为 `from google.genai import types` | 45+ 文件 | 自建类型 → 官方类型 |
| 将 `from ..agent.models import Models` 调用替换为 `client.models` 直接访问 | `official_sdk_adapter.py`, `chat_handler.py` | 消除 Models 包装 |
| 保留 `agent/interactions.py` | — | Interactions API 可能仍需兼容层 |
| 标记 `agent/client.py`, `agent/types.py`, `agent/models.py` 为 deprecated | — | 保留一个版本周期 |

**风险**：
- `agent/types.py` 中可能有项目特有的扩展字段，需逐个比对官方类型
- `Models` 包装类可能有参数转换逻辑，需确认官方 SDK 已支持

### 阶段 3：合并 OfficialSDKAdapter + SDKInitializer

| 任务 | 涉及文件 | 说明 |
|---|---|---|
| `ChatHandler` 直接通过 `GeminiClientPool` 获取 client | `chat_handler.py` | 不再经过 adapter |
| `SDKInitializer` 的懒加载逻辑合并到 `GeminiClientPool` | `sdk_initializer.py` → `client_pool.py` | 池本身已支持懒创建 |
| 删除 `official_sdk_adapter.py` | — | 功能已被 ChatHandler 吸收 |
| 删除 `sdk_initializer.py` | — | 功能已被 ClientPool 吸收 |
| 更新 `GoogleService.__init__` 中的初始化链路 | `google_service.py` | 减少初始化参数传递 |

### 阶段 4：其他 Provider 接入连接池注册

| 任务 | 涉及文件 | 说明 |
|---|---|---|
| `OpenAIPoolAdapter`：包装 `AsyncOpenAI` 实例管理 | `openai_service.py` + 新建 adapter | 当前 OpenAI 每个 service 实例持有一个 client |
| `OllamaPoolAdapter`：包装 Ollama client | `ollama.py` + 新建 adapter | |
| `TongyiPoolAdapter`：包装通义千问 client | `tongyi_service.py` + 新建 adapter | |
| 注册到 `ProviderFactory._pools` | `provider_factory.py::_auto_register()` | |

### 阶段 5：全局监控与运维

| 任务 | 说明 |
|---|---|
| `/api/admin/pool-stats` 端点 | 暴露所有 Provider 的连接池状态 |
| 启动时 warm-up | 根据配置预建连接 |
| 优雅关闭 | app shutdown 时 `ProviderFactory.drain_all()` |
| 日志增强 | 统一的 `[ProviderFactory.Pool]` 日志前缀 |

---

## 6. 验证计划

| 验证项 | 方法 | 通过标准 |
|---|---|---|
| Google 文本生成（流式/非流式） | 集成测试 | 响应正常，无类型错误 |
| Vertex AI 图像操作 | 端到端测试 | 图像编辑/分割/试穿正常 |
| OpenAI / Ollama / 通义千问正常工作 | 冒烟测试 | 聊天、模型列表正常 |
| 连接池统计准确 | `get_global_stats()` | 各 Provider 统计数据一致 |
| 并发安全 | 50 并发请求 | 无竞态条件 |
| 优雅关闭 | SIGTERM 测试 | 所有连接正常释放 |

---

## 7. 回滚策略

- **阶段 1-2**：`agent/client.py` 标记 deprecated 但不删除，一个版本周期内保留
- **阶段 3**：`OfficialSDKAdapter` 和 `SDKInitializer` 同理
- **Feature Flag**：`USE_UNIFIED_POOL=true/false` 控制是否走新链路
- **全量回滚**：git revert 到 ProviderFactory 变更前的 commit
