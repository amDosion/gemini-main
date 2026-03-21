# Gemini Service Module

Google Gemini Provider 服务模块 - 提供完整的 Google AI 服务集成。

## 架构概述

本模块采用 **协调者模式（Coordinator Pattern）** 架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                         Router Layer                            │
│         (google_modes.py, imagen.py, tryon.py, etc.)           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ ProviderFactory.create("google")
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GoogleService                              │
│                   (Main Coordinator)                            │
│  - 统一的对外接口                                                 │
│  - 负责请求分发到具体子服务                                         │
│  - 管理客户端缓存和配置                                            │
└────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│  Chat  │ │ Image  │ │ Image  │ │ TryOn  │ │ Other  │
│Handler │ │Generate│ │  Edit  │ │Service │ │Services│
└────────┘ └───┬────┘ └───┬────┘ └────────┘ └────────┘
               │          │
               ▼          ▼
         ┌────────────────────────┐
         │    Coordinators        │
         │ (Gemini API/Vertex AI) │
         └────────────────────────┘
```

## 目录结构

### API 实现分类标注

| 标注 | 说明 |
|------|------|
| `[Gemini API]` | 使用 API Key 认证的 Gemini API 实现 |
| `[Vertex AI]` | 使用服务账号认证的 Vertex AI 实现 |
| `[Hybrid]` | 支持两种 API 的协调器/适配器 |
| `[Common]` | API 无关的通用组件 |

```
gemini/                                         # 共 91 个 Python 文件
├── __init__.py                                 # [Hybrid] 模块导出（含 provider-neutral/legacy Multi-Agent 说明）
├── google_service.py                           # [Hybrid] 主协调器 (Main Coordinator)
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 核心组件 (Core Components)
├── # ═══════════════════════════════════════════════════════════════════════
├── sdk_initializer.py                          # [Hybrid] SDK 初始化 - 支持 Gemini API 和 Vertex AI
├── client_pool.py                              # [Hybrid] 统一客户端池管理
├── model_manager.py                            # [Common] 模型列表管理
├── message_converter.py                        # [Common] 消息格式转换
├── response_parser.py                          # [Common] 响应解析
├── parameter_validation.py                     # [Common] 参数验证
├── platform_routing.py                         # [Common] 平台路由
├── config_builder.py                           # [Common] 配置构建
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 聊天服务 (Chat Services)
├── # ═══════════════════════════════════════════════════════════════════════
├── chat_handler.py                             # [Common] 聊天处理
├── chat_session_manager.py                     # [Common] 会话管理
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 图像生成 (Image Generation - Imagen)
├── # ═══════════════════════════════════════════════════════════════════════
├── image_generator.py                          # [Hybrid] 图像生成入口 - 使用 ImagenCoordinator
├── imagen_coordinator.py                       # [Hybrid] Imagen 协调器 - Factory 模式选择 API 实现
├── video_generation_coordinator.py             # [Hybrid] Veo 视频协调器 - 选择 Gemini API / Vertex AI
├── imagen_base.py                              # [Common] BaseImageGenerator 抽象基类
├── imagen_common.py                            # [Common] 共享工具和异常类 (ConfigurationError 等)
├── imagen_config.py                            # [Common] Pydantic 配置模型
├── video_common.py                             # [Common] Veo 视频参数归一化与引用图加载
├── imagen_gemini_api.py                        # [Gemini API] ⭐ GeminiAPIImageGenerator - 使用 api_key 认证
├── video_generation_service.py                 # [Gemini API] ⭐ GeminiAPIVideoGenerationService - `generate_videos` + `files.download`
├── imagen_vertex_ai.py                         # [Vertex AI] ⭐ VertexAIImageGenerator - 使用服务账号认证
├── video_generation_service.py                 # [Vertex AI] ⭐ VertexAIVideoGenerationService - `generate_videos` + Vertex operation polling
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 图像编辑 (Image Editing)
├── # ═══════════════════════════════════════════════════════════════════════
├── image_edit_coordinator.py                   # [Hybrid] 图像编辑协调器 - 智能路由编辑请求
├── image_edit_base.py                          # [Common] BaseImageEditor 抽象基类
├── image_edit_common.py                        # [Common] 共享工具类 (NotSupportedError 等)
├── image_edit_gemini_api.py                    # [Gemini API] ⭐ GeminiAPIImageEditor - STUB (图片编辑不支持!)
├── image_edit_vertex_ai.py                     # [Vertex AI] ⭐ VertexAIImageEditor - 完整图片编辑实现
├── simple_image_edit_service.py                # [Common] 简单编辑服务 - 使用 generateContent
├── conversational_image_edit_service.py        # [Common] 对话式编辑服务 - 使用 Chat SDK
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 专业服务 (Specialized Services)
├── # ═══════════════════════════════════════════════════════════════════════
├── expand_service.py                           # [Common] 图像扩展/外扩/放大 (Outpainting + Upscale)
├── segmentation_service.py                     # [Common] 图像分割
├── tryon_service.py                            # [Hybrid] 虚拟试穿 - Vertex AI 优先，Gemini API 降级
├── pdf_extractor.py                            # [Common] PDF 结构化提取
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # Handler 服务 (Handler Services)
├── # ═══════════════════════════════════════════════════════════════════════
├── file_handler.py                             # [Common] 文件上传/下载
├── function_handler.py                         # [Common] 函数调用和工具集成
├── schema_handler.py                           # [Common] JSON Schema 响应处理
├── token_handler.py                            # [Common] Token 计数和成本估算
├── browser.py                                  # [Common] 浏览器工具
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 模式系统 (Mode System)
├── # ═══════════════════════════════════════════════════════════════════════
├── mode_registry.py                            # [Common] Google 模式注册表
├── mode_initialization.py                      # [Common] 模式初始化
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # 官方 SDK 适配器 (Official SDK Adapter)
├── # ═══════════════════════════════════════════════════════════════════════
├── official_sdk_adapter.py                     # [Hybrid] 官方 SDK 适配器 - 支持 use_vertex 标志
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # agent/ - Agent Engine 高级功能（35 个文件）
├── # ═══════════════════════════════════════════════════════════════════════
├── agent/
│   ├── __init__.py                             # [Google runtime] 模块导出（含 legacy orchestration symbols）
│   │
│   ├── # --- Official SDK Compatibility Layer ---
│   ├── client.py                               # [Hybrid] ⭐ Official GenAI SDK 兼容客户端
│   ├── models.py                               # [Hybrid] Models API 包装器
│   ├── interactions.py                         # [Hybrid] Interactions API 包装器 (Deep Research)
│   ├── interactions_service.py                 # [Vertex AI] Vertex AI Interactions Service
│   ├── types.py                                # [Common] SDK 类型定义
│   ├── common.py                               # [Common] 公共基类和工具
│   ├── version.py                              # [Common] 版本信息
│   │
│   ├── # --- Agent Engine Core ---
│   ├── agent_executor.py                       # [Common] Agent 执行器
│   ├── agent_registry.py                       # [Common] Agent 注册表
│   ├── agent_card.py                           # [Common] Agent Card 管理
│   ├── agent_matcher.py                        # [Common] Agent 匹配器（能力匹配、负载均衡）
│   ├── agent_with_tools.py                     # [Common] 带工具的 Agent
│   │
│   ├── # --- Multi-Agent Patterns ---
│   ├── orchestrator.py                         # [Google runtime] 智能体编排器（兼容能力）
│   ├── task_decomposer.py                      # [Common] 智能任务分解器
│   ├── execution_graph.py                      # [Common] 执行图 (DAG) 管理
│   ├── coordinator_agent.py                    # [Google runtime] 协调代理 (Dispatcher Pattern)
│   ├── sequential_agent.py                     # [Google runtime] 顺序代理 (Pipeline Pattern)
│   ├── parallel_agent.py                       # [Google runtime] 并行代理 (Fan-Out/Gather Pattern)
│   │
│   ├── # --- Memory & Code Execution ---
│   ├── memory_manager.py                       # [Common] 记忆管理
│   ├── memory_bank_service.py                  # [Vertex AI] ⭐ Vertex AI Memory Bank Service
│   ├── code_executor.py                        # [Common] 代码执行器
│   ├── sandbox_manager.py                      # [Vertex AI] ⭐ Vertex AI Sandbox 管理
│   │
│   ├── # --- Tools & Protocols ---
│   ├── tool_registry.py                        # [Common] 工具注册表
│   ├── a2a_protocol.py                         # [Common] Agent-to-Agent 协议
│   ├── live_api.py                             # [Common] 实时 API 处理
│   │
│   ├── # --- ADK Integration ---
│   ├── adk_runner.py                           # [Common] ADK 运行器
│   ├── adk_agent.py                            # [Common] ADK Agent 封装
│   ├── adk_integration.py                      # [Common] ADK 集成
│   ├── adk_samples_importer.py                 # [Common] ADK 示例导入器
│   ├── workflow_template_service.py            # [Common] 工作流模板服务
│   │
│   ├── # --- tools/ 子目录 ---
│   ├── tools/
│   │   ├── __init__.py                         # [Common] 工具模块导出
│   │   ├── excel_tools.py                      # [Common] Excel 处理工具
│   │   └── image_tools.py                      # [Common] 图像处理工具
│   │
│   └── # --- workflows/ 子目录 ---
│       workflows/
│       ├── __init__.py                         # [Common] 工作流模块导出
│       ├── image_edit_workflow.py              # [Common] 图像编辑工作流
│       └── excel_analysis_workflow.py          # [Common] Excel 分析工作流
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # handlers/ - 模式处理器（4 个文件）
├── # ═══════════════════════════════════════════════════════════════════════
├── handlers/
│   ├── __init__.py                             # [Common] 模块导出
│   ├── outpainting_handler.py                  # [Common] 图像外扩处理器 - 委托给 image_edit_coordinator
│   ├── inpainting_handler.py                   # [Common] 图像修复处理器 - 委托给 image_edit_coordinator
│   └── virtual_tryon_handler.py                # [Common] 虚拟试穿处理器 - 委托给 image_edit_coordinator
│
├── # ═══════════════════════════════════════════════════════════════════════
├── # shared/ - 共享组件（4 个文件）
├── # ═══════════════════════════════════════════════════════════════════════
├── shared/
│   ├── __init__.py                             # [Common] 模块导出
│   ├── adapters.py                             # [Common] LegacyToOfficialAdapter, OfficialToLegacyAdapter
│   ├── config.py                               # [Common] GeminiConfig 配置管理
│   └── utils.py                                # [Common] detect_mime_type, validate_api_key, retry_with_backoff
│
└── # ═══════════════════════════════════════════════════════════════════════
    # genai_agent/ - GenAI Agent 服务（7 个文件）
    # ═══════════════════════════════════════════════════════════════════════
    genai_agent/
    ├── __init__.py                             # [Common] 模块导出
    ├── client.py                               # [Gemini API] ⭐ GenAI Client 池管理 - 使用 api_key 认证
    ├── service.py                              # [Common] GenAIAgentService 主服务类
    ├── research_agent.py                       # [Common] ResearchAgent 研究智能体
    ├── advanced_features.py                    # [Common] AdvancedResearchAgent 高级研究智能体
    ├── stream_handler.py                       # [Common] StreamHandler 流式事件处理
    ├── tools.py                                # [Common] ToolManager 工具集成管理
    └── types.py                                # [Common] 类型定义
```

### 文件统计

| 分类 | 文件数 | 说明 |
|------|--------|------|
| **[Gemini API]** | 3 | 使用 API Key 认证的专用实现 |
| **[Vertex AI]** | 4 | 使用服务账号认证的专用实现 |
| **[Hybrid]** | 10 | 支持两种 API 的协调器/适配器 |
| **[Common]** | 74 | API 无关的通用组件 |
| **总计** | **91** | |

### 关键实现差异

| 特性 | Gemini API | Vertex AI |
|------|------------|-----------|
| **认证方式** | API Key | 服务账号 (credentials JSON) |
| **客户端创建** | `Client(api_key=...)` | `Client(vertexai=True, project=..., location=..., credentials=...)` |
| **图像生成** | ✅ 支持 | ✅ 支持 |
| **图像编辑** | ❌ 不支持 (STUB) | ✅ 完整支持 |
| **虚拟试穿** | ⚠️ 备用方案 | ✅ 优先使用 |
| **Memory Bank** | ❌ 不支持 | ✅ 支持 |
| **Sandbox** | ❌ 不支持 | ✅ 支持 |
| **Interactions API** | ⚠️ 有限支持 | ✅ 完整支持 |

### 关键文件详解

#### Gemini API 专用文件（4 个）
| 文件 | 类名 | 说明 |
|------|------|------|
| `imagen_gemini_api.py` | `GeminiAPIImageGenerator` | 使用 `Client(api_key=...)` 进行图像生成 |
| `video_generation_service.py` | `GeminiAPIVideoGenerationService` | 使用 `client.models.generate_videos()` + `client.files.download()` 生成并下载视频 |
| `image_edit_gemini_api.py` | `GeminiAPIImageEditor` | **STUB** - 始终抛出 `NotSupportedError` |
| `genai_agent/client.py` | `get_genai_client()` | GenAI 客户端池管理，使用 api_key |

#### Vertex AI 专用文件（5 个）
| 文件 | 类名 | 说明 |
|------|------|------|
| `imagen_vertex_ai.py` | `VertexAIImageGenerator` | 使用 `Client(vertexai=True, ...)` 进行图像生成 |
| `video_generation_service.py` | `VertexAIVideoGenerationService` | 使用 `client.models.generate_videos()` 生成视频，优先消费 inline bytes，必要时回退 `gs://` 下载 |
| `image_edit_vertex_ai.py` | `VertexAIImageEditor` | 完整的图像编辑实现（inpainting, outpainting, product-image） |
| `agent/memory_bank_service.py` | `VertexAiMemoryBankService` | Vertex AI Memory Bank 服务 |
| `agent/sandbox_manager.py` | `SandboxManager` | Vertex AI Sandbox 管理 |

#### Hybrid 混合文件（11 个）
| 文件 | 类名 | 说明 |
|------|------|------|
| `google_service.py` | `GoogleService` | 主协调器，统一入口；`multi_agent()` 仅保留为 Google runtime 兼容适配器 |
| `sdk_initializer.py` | `SDKInitializer` | 支持两种 API 的 SDK 初始化 |
| `client_pool.py` | `GeminiClientPool` | 统一客户端池管理 |
| `imagen_coordinator.py` | `ImagenCoordinator` | Factory 模式选择 API 实现 |
| `video_generation_coordinator.py` | `VideoGenerationCoordinator` | 复用 GEN 模式配置加载，选择 Gemini API 或 Vertex AI 的 Veo 服务 |
| `image_edit_coordinator.py` | `ImageEditCoordinator` | 智能路由编辑请求 |
| `image_generator.py` | `ImageGenerator` | 使用 ImagenCoordinator 的包装器 |
| `tryon_service.py` | `TryOnService` | Vertex AI 优先，Gemini API 降级 |
| `official_sdk_adapter.py` | `OfficialSDKAdapter` | 支持 `use_vertex` 标志 |
| `agent/client.py` | `Client` | Official SDK 兼容客户端 |
| `agent/models.py` | `Models` | Models API 包装器 |

## 核心组件

### GoogleService (Main Coordinator)

所有 Google 服务的统一入口点，负责：

- 请求分发到具体子服务
- 客户端缓存管理
- Vertex AI / Gemini API 切换
- 统一的错误处理

说明：
- provider-neutral 的 Multi-Agent 主入口统一是 `POST /api/modes/{provider}/multi-agent`。
- `GoogleService.multi_agent()` 仅保留为 legacy Google runtime 兼容 helper。
- `GoogleService.generate_video()` 现在复用 GEN 模式风格的 `VideoGenerationCoordinator`，按用户 `VertexAIConfig.api_mode` 在 Gemini API 与 Vertex AI Veo 之间切换。

```python
from ..services.provider_factory import ProviderFactory

# 通过工厂创建服务
service = ProviderFactory.create(
    provider="google",
    api_key=api_key,
    user_id=user_id,
    db=db
)

# 使用服务方法
result = await service.generate_image(prompt, model)
result = await service.edit_image(prompt, model, reference_images, mode)
result = service.virtual_tryon(image_base64, mask_base64, prompt)
```

### 委托的子服务

| 子服务 | 描述 | GoogleService 方法 |
|--------|------|-------------------|
| ChatHandler | 聊天对话 | `chat()`, `chat_stream()` |
| ImageGenerator | 图像生成 | `generate_image()` |
| ImageEditCoordinator | 图像编辑 | `edit_image()` |
| ExpandService | 图像外扩 | `expand_image()` |
| UpscaleService | 图像放大 | `upscale_image()` |
| SegmentationService | 图像分割 | `segment_image()` |
| TryOnService | 虚拟试穿 | `virtual_tryon()` |
| PDFExtractor | PDF 提取 | `extract_pdf()` |

## 图像生成系统 (Imagen)

采用 **策略模式** 支持 Gemini API 和 Vertex AI：

```
ImageGenerator
    └── ImagenCoordinator (策略选择)
            ├── GeminiAPIImageGenerator
            └── VertexAIImageGenerator
```

### 选择逻辑

1. **Vertex AI 优先**：如果配置了 Vertex AI 凭据
2. **Gemini API 降级**：Vertex AI 不可用时使用
3. **自动降级**：运行时错误时自动切换

```python
# ImagenCoordinator 自动选择实现
coordinator = ImagenCoordinator(api_key=api_key, user_id=user_id, db=db)
result = await coordinator.generate_images(prompt, model, num_images)
```

## 图像编辑系统

支持多种编辑模式：

| 模式 | 描述 | 支持平台 |
|------|------|----------|
| `image-outpainting` | 图像外扩 | Gemini API, Vertex AI |
| `image-inpainting` | 图像修复 | Gemini API, Vertex AI |
| `virtual-try-on` | 虚拟试穿 | Vertex AI (优先) |

```python
# 通过 GoogleService.edit_image() 统一调用
result = await service.edit_image(
    prompt="extend the landscape",
    model="imagen-3.0-generate-001",
    reference_images={"raw": image_base64},
    mode="image-outpainting",
    aspect_ratio="16:9"
)
```

## Agent 子模块

位于 `agent/` 目录，提供高级 Agent 功能：

### 核心组件

| 组件 | 描述 |
|------|------|
| `AgentExecutor` | Agent 执行器 |
| `MemoryManager` | 记忆管理 |
| `CodeExecutor` | 代码执行 |
| `SandboxManager` | 沙箱管理 |
| `A2AProtocolHandler` | Agent-to-Agent 协议 |
| `LiveAPIHandler` | 实时 API 处理 |

### Multi-Agent 系统（Google runtime 专属兼容能力）

| 组件 | 描述 |
|------|------|
| `Orchestrator` | Google runtime 智能体编排器（兼容能力） |
| `SmartTaskDecomposer` | 智能任务分解器 |
| `AgentMatcher` | 代理匹配器 |
| `CoordinatorAgent` | Google runtime 协调代理 (Dispatcher Pattern) |
| `SequentialAgent` | Google runtime 顺序代理 (Pipeline Pattern) |
| `ParallelAgent` | Google runtime 并行代理 (Fan-Out/Gather Pattern) |

说明：
- 新的多 provider 编排入口统一使用 `POST /api/modes/{provider}/multi-agent`。
- `GoogleService.multi_agent()` 仅保留默认编排的兼容适配，不应视为 provider-neutral 主能力。
- `app.services.gemini.agent` 暴露的 `Orchestrator` / `CoordinatorAgent` / `SequentialAgent` / `ParallelAgent`
  仅适用于维护既有 Google runtime orchestration 代码，不是跨 provider SDK 入口。

### 工作流

| 工作流 | 描述 |
|--------|------|
| `ImageEditWorkflow` | 图像编辑工作流 |
| `ExcelAnalysisWorkflow` | Excel 分析工作流 |

### ADK 集成

| 组件 | 描述 |
|------|------|
| `ADKRunner` | ADK 运行器 |
| `ADKAgent` | ADK 代理封装 |

### Official SDK Compatibility

| 组件 | 描述 |
|------|------|
| `Client` / `AsyncClient` | 官方 SDK 兼容客户端 |
| `Models` / `AsyncModels` | 模型操作 |
| `InteractionsResource` | Interactions API 资源 |

## Handlers 子模块

位于 `handlers/` 目录，提供模式处理器：

| Handler | 描述 |
|---------|------|
| `OutpaintingHandler` | 图像外扩处理 |
| `InpaintingHandler` | 图像修复处理 |
| `VirtualTryonHandler` | 虚拟试穿处理 |

## Shared 子模块

位于 `shared/` 目录，提供共享组件：

| 组件 | 描述 |
|------|------|
| `LegacyToOfficialAdapter` | 旧版到官方 SDK 适配器 |
| `OfficialToLegacyAdapter` | 官方到旧版 SDK 适配器 |
| `GeminiConfig` | 配置管理 |
| `detect_mime_type` | MIME 类型检测 |
| `validate_api_key` | API Key 验证 |
| `retry_with_backoff` | 重试机制 |

## 使用示例

### 1. 聊天

```python
service = ProviderFactory.create("google", api_key=api_key)

# 同步聊天
response = await service.chat(messages=[{"role": "user", "content": "Hello"}])

# 流式聊天
async for chunk in service.chat_stream(messages):
    print(chunk)
```

### 2. 图像生成

```python
service = ProviderFactory.create("google", api_key=api_key, user_id=user_id, db=db)

result = await service.generate_image(
    prompt="A beautiful sunset over mountains",
    model="imagen-3.0-generate-001",
    num_images=1,
    aspect_ratio="16:9"
)
```

### 3. 图像编辑

```python
service = ProviderFactory.create("google", api_key=api_key, user_id=user_id, db=db)

# 外扩
result = await service.edit_image(
    prompt="extend with forest",
    model="imagen-3.0-generate-001",
    reference_images={"raw": image_base64},
    mode="image-outpainting",
    aspect_ratio="16:9"
)

# 修复
result = await service.edit_image(
    prompt="remove the person",
    model="imagen-3.0-generate-001",
    reference_images={"raw": image_base64, "mask": mask_base64},
    mode="image-inpainting"
)
```

### 4. 虚拟试穿

```python
service = ProviderFactory.create("google", api_key=api_key, user_id=user_id, db=db)

result = service.virtual_tryon(
    image_base64=person_image,
    mask_base64=None,  # 自动检测
    prompt="red summer dress",
    target_clothing="upper body clothing"
)
```

## 配置

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `GOOGLE_API_KEY` | Gemini API Key | - |
| `VERTEX_AI_PROJECT` | Vertex AI 项目 ID | - |
| `VERTEX_AI_LOCATION` | Vertex AI 区域 | `us-central1` |
| `USE_VERTEX_AI` | 是否使用 Vertex AI | `false` |

### 数据库配置

Vertex AI 凭据可以通过数据库 `ConfigProfile` 表配置：

```python
# 从数据库获取用户的 Vertex AI 配置
from .agent import get_vertex_ai_credentials_from_db

credentials = get_vertex_ai_credentials_from_db(db, user_id)
# Returns: {"project": "...", "location": "...", "credentials_json": "..."}
```

## 错误处理

所有服务使用统一的错误处理：

```python
from ..errors import ProviderError, OperationError, ClientCreationError

try:
    result = await service.generate_image(prompt)
except ClientCreationError as e:
    # 客户端创建失败
    pass
except OperationError as e:
    # 操作执行失败
    pass
except ProviderError as e:
    # 提供商通用错误
    pass
```

## 相关文档

- [路由与逻辑分离架构设计文档](../../../docs/路由与逻辑分离架构设计文档.md)
- [官方 Google GenAI SDK](https://googleapis.github.io/python-genai/)
