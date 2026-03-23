# Google AI SDK 集成度分析报告

> 基于纯代码分析（不参考现有文档），分析本项目对 Google GenAI SDK、Google ADK、Vertex AI SDK 及 Google AI Cookbook 的集成情况。

---

## 一、总体评估

| SDK / 框架 | 集成度评分 | 文件数 | 说明 |
|---|---|---|---|
| **Google GenAI SDK** (`google-genai`) | ⭐⭐⭐⭐⭐ 极深 | 45+ | 全面封装，覆盖几乎所有 API |
| **Vertex AI SDK** (`google-cloud-aiplatform`) | ⭐⭐⭐⭐⭐ 极深 | 13+ 专属服务 | 图像/视频/Agent Engine 全覆盖 |
| **Google ADK** (`google-adk`) | ⭐⭐⭐⭐☆ 深度 | 8 后端 + 4 前端 | 完整 Agent 生命周期支持 |
| **Google AI Cookbook** | ⭐☆☆☆☆ 极低 | 0 | 无直接引用 cookbook 代码/模式 |

---

## 二、Google GenAI SDK (`google-genai>=1.55.0`) 集成详情

### 2.1 核心架构

项目构建了**完整的 SDK 封装层**，位于 `backend/app/services/gemini/`：

```
services/gemini/
├── agent/              # SDK 客户端封装 + ADK 集成
│   ├── client.py       # Client/AsyncClient 封装（支持双模式）
│   ├── models.py       # Models/AsyncModels API 封装
│   ├── types.py        # 120+ 类型定义（Part/Blob/Content/Tool 等）
│   ├── interactions.py # Deep Research Interactions API
│   └── live_api.py     # Live API（双向流式）
├── common/             # 通用功能层
│   ├── chat_handler.py         # 聊天（流式/非流式/异步）
│   ├── config_builder.py       # 生成配置构建器
│   ├── function_handler.py     # Function Calling 处理
│   ├── schema_handler.py       # 结构化输出（JSON Schema/Pydantic）
│   ├── file_handler.py         # Files API（上传/查询/删除）
│   ├── token_handler.py        # Token 计数
│   ├── pdf_extractor.py        # PDF 结构化提取
│   ├── official_sdk_adapter.py # 官方 SDK 适配器
│   └── sdk_initializer.py      # 懒加载初始化
├── client_pool.py      # 单例客户端池（线程安全，缓存命中统计）
├── genai_agent/        # 研究代理
│   ├── research_agent.py       # 多轮研究 Agent
│   ├── advanced_features.py    # 思维链/工具协调/事件流
│   ├── tools.py                # 工具管理器
│   └── stream_handler.py       # 流式响应处理
├── geminiapi/          # Gemini API 模式专属
│   ├── imagen_gemini_api.py
│   ├── video_generation_service.py
│   ├── video_understanding_service.py
│   └── conversational_image_edit_service.py
└── vertexai/           # Vertex AI 模式专属（见第三节）
```

### 2.2 已集成的 GenAI SDK 功能

| 功能分类 | 具体能力 | 实现文件 | SDK API |
|---|---|---|---|
| **文本生成** | 流式/非流式/异步 | `chat_handler.py` | `models.generate_content()` |
| **Function Calling** | 注册/声明/AUTO/ANY/NONE | `function_handler.py` | `FunctionDeclaration`, `Tool` |
| **结构化输出** | JSON Schema / Pydantic / Enum | `schema_handler.py` | `response_json_schema` |
| **多模态** | 图像/视频/音频/文档 | `file_handler.py` | Files API |
| **图像生成** | Imagen 3.0/4.0, Gemini Image | `imagen_gemini_api.py` | `models.generate_images()` |
| **视频生成** | Veo 3.1 | `video_generation_service.py` | `models.generate_videos()` |
| **视频理解** | 视频分析 | `video_understanding_service.py` | `models.generate_content()` |
| **Embedding** | 文档嵌入/相似搜索 | `embedding_service.py` | Embedding API |
| **Token 计数** | 令牌统计/成本估算 | `token_handler.py` | Token Counting API |
| **Live API** | 双向流式通信 | `live_api.py` | Bidirectional Streaming |
| **Deep Research** | Interactions API | `interactions.py`, `interactions_service.py` | `interactions.execute()` |
| **安全设置** | 4 类危害 × 4 级阈值 | `types.py` | `SafetySetting` |
| **HTTP 配置** | 超时/重试/指数退避 | `client_pool.py`, `types.py` | `HttpOptions`, `HttpRetryOptions` |
| **PDF 提取** | 结构化数据抽取 | `pdf_extractor.py` | `models.generate_content()` |
| **模型管理** | 模型列表 | `model_manager.py` | `models.list_models()` |

### 2.3 支持的模型

- **文本**: `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash-exp`, `gemini-1.5-pro`, `gemini-1.5-flash`
- **图像生成**: `imagen-3.0-generate-002`, `imagen-4.0-generate-001`, `gemini-2.5-flash-image`, `gemini-2.5-pro-image`, `gemini-3-pro-image`
- **视频**: `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`
- **研究**: `deep-research-pro-preview-12-2025`

### 2.4 客户端管理

```python
# 单例客户端池 —— 支持 Gemini API 和 Vertex AI 双模式
from google import genai as google_genai

pool = get_client_pool()
client = pool.get_client(
    api_key="xxx",           # Gemini API 模式
    vertexai=True/False,     # 切换模式
    project="project-id",    # Vertex AI
    location="us-central1",  # Vertex AI
    credentials=creds,       # Service Account
    http_options=HttpOptions(timeout=120, retry_options=...)
)
```

---

## 三、Vertex AI SDK (`google-cloud-aiplatform[agent_engines,adk]>=1.38.0`) 集成详情

### 3.1 专属服务层

位于 `backend/app/services/gemini/vertexai/`：

| 服务 | 文件 | Vertex AI API | 功能 |
|---|---|---|---|
| **图像生成** | `imagen_vertex_ai.py` | `models.generate_images()`, `models.generate_content()` | Imagen/Gemini/Veo 图像 |
| **图像编辑基类** | `vertex_edit_base.py` | `models.edit_image()` | 统一编辑接口 |
| **修复/抠图** | `inpainting_service.py` | `edit_image(INPAINT_INSERTION)` | 图像修复 |
| **背景替换** | `background_edit_service.py` | `edit_image(BGSWAP)` | 背景编辑 |
| **重构上下文** | `recontext_service.py` | `edit_image(INPAINT_INSERTION)` | 场景重构 |
| **蒙版编辑** | `mask_edit_service.py` | `edit_image()` | 蒙版编辑 |
| **图像分割** | `segmentation_service.py` | `models.segment_image()` | 前景/背景/语义分割 |
| **图像扩展** | `expand_service.py` | `edit_image(OUTPAINT)` | 画布扩展 |
| **图像超分** | `expand_service.py` | `models.upscale_image()` | imagen-4.0-upscale-preview |
| **虚拟试穿** | `tryon_service.py` | `models.recontext_image()` | virtual-try-on-001 |
| **视频生成** | `video_generation_service.py` | `models.generate_videos()` + `operations.get()` | Veo + 长轮询 |
| **视频理解** | `video_understanding_service.py` | `models.generate_content()` | 视频分析 |

### 3.2 认证与配置

- **数据库持久化**: `VertexAIConfig` 表存储 `project_id`、`location`、加密的 `credentials_json`
- **Service Account**: `google.oauth2.service_account.Credentials.from_service_account_info()`
- **ADC 降级**: 支持 Application Default Credentials
- **API 端点**: `/api/vertex-ai-config` 提供配置 CRUD + 连接测试

### 3.3 协调器模式

通过 `coordinators/` 目录实现 Gemini API ↔ Vertex AI 的**自动路由**：

```
coordinators/
├── imagen_coordinator.py           # 图像生成路由
├── image_edit_coordinator.py       # 图像编辑路由
├── video_generation_coordinator.py # 视频生成路由
└── video_understanding_coordinator.py # 视频理解路由
```

每个协调器根据数据库中的 `api_mode` 配置（`gemini_api` 或 `vertex_ai`）自动选择后端。

---

## 四、Google ADK (`google-adk>=0.1.0`) 集成详情

### 4.1 直接 SDK 使用

项目**直接导入并使用** Google ADK 官方 SDK：

```python
# 来自实际代码的 import
from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.apps import App
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService, VertexAiMemoryBankService
from google.adk.agents.live_request_queue import LiveRequestQueue, LiveRequest
from google.adk.agents.run_config import RunConfig
from google.adk.code_executors import AgentEngineSandbox
```

### 4.2 ADK 功能覆盖

| ADK 能力 | 实现文件 | 描述 |
|---|---|---|
| **LlmAgent** | `adk_agent.py` | 封装 ADK LlmAgent，工具转换，查询方法 |
| **Runner** | `adk_runner.py` | Session/Memory 管理，流式/Live 执行 |
| **SequentialAgent** | `sequential_agent.py` | 顺序流水线，output_key/input_key 链式传递 |
| **ParallelAgent** | `parallel_agent.py` | 并行扇出/聚合，超时管理 |
| **Coordinator** | `coordinator_agent.py` | 意图分析 → 代理选择 → 执行 |
| **Orchestrator** | `orchestrator.py` | 智能任务分解 + DAG 执行图 |
| **Code Execution** | `code_executor.py` | Agent Engine 沙箱代码执行 |
| **Memory Bank** | `memory_bank_service.py` | Vertex AI Memory Bank 集成 |
| **Built-in Tools** | `adk_builtin_tools.py` | 内置工具（sheet_analyze 等） |
| **Runtime Contract** | `adk_runtime_contract.py` | 运行时策略（OFFICIAL_ONLY/FALLBACK） |

### 4.3 ADK 示例模板

从 `google/adk-samples` 仓库导入了 **4 个官方 ADK 模板**，转换为可执行工作流：

| 模板 | 文件 | ADK 模式 |
|---|---|---|
| **客服** | `adk_sample_customer_service_v1.json` | Parallel → Merge → Final |
| **数据工程** | `adk_sample_data_engineering_v1.json` | Parse → Parallel Review → Decision |
| **营销** | `adk_sample_marketing_agency_v1.json` | Plan → Parallel Gen → QA |
| **CAMEL** | `adk_sample_camel_v1.json` | Decompose → Parallel Exec → Unify |

### 4.4 前端 ADK 支持

- `AdkSessionPanel.tsx` — Session 管理 UI（会话列表/工具确认/回退）
- `adkSessionService.ts` — TypeScript 服务层（API 调用封装）
- `AdkExportPanel.tsx` — 导出面板
- `AdkRuntimePolicyPanel.tsx` — 运行时策略控制

### 4.5 API 端点

```
POST /api/multi-agent/agents/{id}/runtime/run        # ADK 执行
POST /api/multi-agent/agents/{id}/runtime/run-live    # Live 流式执行
GET  /api/multi-agent/agents/{id}/runtime/sessions    # Session 列表
POST .../sessions/{sid}/confirm-tool                   # 工具确认
POST .../sessions/{sid}/rewind                         # Session 回退
POST /api/workflows/adk-samples/import                 # 导入单个模板
POST /api/workflows/adk-samples/import-all             # 批量导入
```

---

## 五、Google AI Cookbook 集成

### 评估：几乎为零

经全面代码搜索：
- **无** `cookbook` 关键字引用
- **无** 从 `google-gemini/cookbook` 仓库复制的代码
- **无** cookbook 示例的显式引用或注释

虽然项目实现了许多与 cookbook 示例相似的功能（如 Function Calling、结构化输出、多模态等），但这些都是**独立实现**，未直接参考或移植 cookbook 代码。

---

## 六、集成度评估总结

### 6.1 Google GenAI SDK — 极深集成 ⭐⭐⭐⭐⭐

- **122+ 处 import 引用**，45+ 文件涉及
- **覆盖 SDK 几乎所有公开 API**：生成、流式、Function Calling、结构化输出、多模态、Embedding、Token 计数、Files API、Live API、Interactions API
- 构建了**完整的抽象层**：客户端池、配置构建器、适配器、类型系统
- 支持 **15+ 模型家族**

### 6.2 Vertex AI SDK — 极深集成 ⭐⭐⭐⭐⭐

- **13 个专属 Vertex AI 服务文件**
- 覆盖 Vertex AI **独有能力**：图像分割、虚拟试穿、图像超分、画布扩展、Agent Engine
- **数据库级配置管理**（加密凭证、项目/区域）
- **自动路由协调器**在 Gemini API 和 Vertex AI 之间无缝切换

### 6.3 Google ADK — 深度集成 ⭐⭐⭐⭐☆

- **直接使用官方 SDK**（LlmAgent、Runner、Session、Memory）
- **完整实现** Sequential/Parallel/Coordinator 编排模式
- **前后端全栈支持**（Python 后端 + React/TS 前端）
- **4 个官方 ADK 模板**转换为可执行工作流
- 扣分项：未见 LoopAgent 实现；ADK 的一些高级特性（如 Evaluation、Deployment to Agent Engine）未完整覆盖

### 6.4 Google AI Cookbook — 几乎无集成 ⭐☆☆☆☆

- 代码中无任何 cookbook 引用
- 功能实现与 cookbook 示例有重叠，但属独立开发
