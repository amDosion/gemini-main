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

```
gemini/
├── __init__.py                 # 模块导出
├── google_service.py           # 主协调器 (Main Coordinator)
│
├── # === Core Components ===
├── sdk_initializer.py          # SDK 初始化
├── model_manager.py            # 模型列表管理
├── message_converter.py        # 消息格式转换
├── response_parser.py          # 响应解析
├── parameter_validation.py     # 参数验证
├── platform_routing.py         # 平台路由
│
├── # === Chat Services ===
├── chat_handler.py             # 聊天处理
├── chat_session_manager.py     # 会话管理
│
├── # === Image Generation (Imagen) ===
├── image_generator.py          # 图像生成入口
├── imagen_coordinator.py       # Imagen 协调器
├── imagen_base.py              # 基础类定义
├── imagen_common.py            # 共享工具和异常
├── imagen_config.py            # 配置管理
├── imagen_gemini_api.py        # Gemini API 实现
├── imagen_vertex_ai.py         # Vertex AI 实现
│
├── # === Image Editing ===
├── image_edit_coordinator.py   # 图像编辑协调器
├── image_edit_base.py          # 基础类定义
├── image_edit_common.py        # 共享工具
├── image_edit_gemini_api.py    # Gemini API 实现
├── image_edit_vertex_ai.py     # Vertex AI 实现
├── simple_image_edit_service.py         # 简单编辑服务
├── conversational_image_edit_service.py # 对话式编辑服务
│
├── # === Specialized Services ===
├── expand_service.py           # 图像扩展/外扩 (Outpainting)
├── upscale_service.py          # 图像放大
├── segmentation_service.py     # 图像分割
├── tryon_service.py            # 虚拟试穿
├── pdf_extractor.py            # PDF 结构化提取
│
├── # === Handler Services ===
├── file_handler.py             # 文件上传/下载
├── function_handler.py         # 函数调用和工具集成
├── schema_handler.py           # JSON Schema 响应处理
├── token_handler.py            # Token 计数和成本估算
│
├── # === Mode System ===
├── mode_registry.py            # Google 模式注册表
├── mode_initialization.py      # 模式初始化
│
├── # === Official SDK Adapter ===
├── official_sdk_adapter.py     # 官方 SDK 适配器
│
├── # === Subdirectories ===
├── agent/                      # Agent Engine 高级功能
├── handlers/                   # 模式处理器
└── shared/                     # 共享组件
```

## 核心组件

### GoogleService (Main Coordinator)

所有 Google 服务的统一入口点，负责：

- 请求分发到具体子服务
- 客户端缓存管理
- Vertex AI / Gemini API 切换
- 统一的错误处理

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

### Multi-Agent 系统

| 组件 | 描述 |
|------|------|
| `Orchestrator` | 智能体编排器 |
| `SmartTaskDecomposer` | 智能任务分解器 |
| `AgentMatcher` | 代理匹配器 |
| `CoordinatorAgent` | 协调代理 (Dispatcher Pattern) |
| `SequentialAgent` | 顺序代理 (Pipeline Pattern) |
| `ParallelAgent` | 并行代理 (Fan-Out/Gather Pattern) |

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
