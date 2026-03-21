# Services 模块架构文档

## 概述

`services` 模块是后端 AI 服务的核心，采用**协调者模式（Coordinator Pattern）**和**路由与逻辑分离**的架构设计，统一管理所有 AI 提供商的集成。

## 目录结构

```
services/
├── __init__.py                    # 模块导出
│
├── llm/                           # 共享 LLM 运行层（与 Agent 解耦）
│   ├── runtime.py                 # 统一 LLM Runtime（凭证/Provider/Adapter）
│   ├── adapter_factory.py         # provider -> adapter 映射
│   ├── credentials_resolver.py    # 凭证解析（含 provider 前缀回退）
│   └── adapters/                  # 各 provider LLM adapter
│
├── # === 通用服务模块 ===
├── common/                        # 通用服务和基础组件
│   ├── __init__.py               # 模块导出
│   ├── base_provider.py          # 基础提供商接口
│   ├── provider_config.py        # 提供商配置管理
│   ├── provider_factory.py      # 提供商工厂（自动注册）
│   ├── errors.py                 # 错误处理
│   ├── model_capabilities.py     # 模型能力定义
│   ├── client_selector.py        # 客户端选择器（双客户端支持）
│   ├── api_key_service.py        # API 密钥管理
│   ├── embedding_service.py      # 嵌入服务
│   ├── interactions_manager.py   # 交互管理器（Deep Research）
│   ├── progress_tracker.py       # 进度跟踪
│   ├── state_manager.py          # 状态管理
│   ├── tool_orchestrator.py      # 工具编排器
│   ├── upload_worker_pool.py     # 上传工作池
│   ├── init_service.py           # 初始化服务
│   ├── auth_service.py           # 认证服务
│   └── redis_queue_service.py    # Redis 队列服务
│
├── # === 提供商实现 ===
├── gemini/                        # Google Gemini 提供商
│   ├── README.md                 # Gemini 架构文档
│   ├── google_service.py         # 主协调器
│   └── ...                       # 子服务和处理器
│
├── openai/                        # OpenAI 提供商
│   ├── README.md                 # OpenAI 架构文档
│   ├── openai_service.py         # 主协调器
│   ├── chat_handler.py           # 聊天服务
│   ├── image_generator.py       # 图像生成（DALL-E）
│   ├── speech_generator.py      # 语音合成（TTS）
│   └── model_manager.py         # 模型管理
│
├── tongyi/                        # 阿里通义千问提供商
│   ├── README.md                 # Tongyi 架构文档
│   ├── tongyi_service.py         # 主协调器
│   └── ...                       # 子服务
│
├── ollama/                        # Ollama 本地部署提供商
│   ├── ollama.py                 # 主服务
│   └── ...                       # 处理器和类型定义
│
├── # === 功能模块 ===
├── mcp/                           # Model Context Protocol
│   ├── README.md                 # MCP 文档
│   ├── mcp_manager.py            # MCP 管理器
│   └── ...                       # MCP 客户端和适配器
│
└── storage/                       # 存储服务
    ├── storage_manager.py        # 存储管理器
    ├── base.py                   # 基础存储接口
    ├── factory.py                # 存储工厂
    └── ...                       # 各种存储提供商实现
```

## 核心架构原则

### 1. 协调者模式（Coordinator Pattern）

每个提供商都有一个**主协调器（Main Coordinator）**，负责：
- 统一入口：所有请求通过协调器进入
- 请求分发：将请求委托给对应的子服务
- **不包含业务逻辑**：协调器只负责路由，不实现具体功能

示例：
```python
# GoogleService 作为协调器
class GoogleService(BaseProviderService):
    async def edit_image(...):
        # 只负责委托，不包含业务逻辑
        return await self.image_edit_coordinator.edit_image(...)
```

### 2. 路由与逻辑分离

- **路由层**：`provider_factory.py` 和 `provider_config.py` 负责提供商选择和配置
- **逻辑层**：各子服务负责具体业务逻辑实现
- **统一接口**：所有提供商实现 `BaseProviderService` 接口

### 2.1 Agent 层位置（重要）

- **共享 Agent 层**：`services/agent/` 是跨提供商的统一工作流与 Agent 执行层（含 `llm_adapters/`）。
- **提供商实现层**：`services/{provider}/` 只放该提供商能力实现与协调器（例如 `tongyi/tongyi_service.py`）。
- **结论**：不是每个 provider 都必须有 `services/{provider}/agent/`。  
  当前架构中 Tongyi 通过 `ProviderFactory -> TongyiService` + `services/llm/adapters/tongyi_adapter.py` 完成接入。

补充：
- provider-neutral 的 Multi-Agent 主入口统一是 `POST /api/modes/{provider}/multi-agent`。
- `services/gemini/agent/` 中保留的 `Orchestrator` / `CoordinatorAgent` / `SequentialAgent` / `ParallelAgent`
  属于 legacy Google runtime 兼容能力，不应再被视为跨 provider 主入口。

### 2.2 LLM 与 Agent 解耦（新增）

- **LLM Runtime 层**：`services/llm/` 负责 Provider 凭证解析、ProviderService 创建、LLM Adapter 选择。
- **Agent 层职责**：`services/agent/agent_llm_service.py` 仅作为门面，不再内嵌凭证与 Adapter 工厂逻辑。
- **收益**：与 Qwen-Agent 的 `LLM/Agent` 分层思路一致，便于复用、测试和后续多 Agent 并发扩展。

### 3. 配置驱动

- **ProviderConfig**：集中管理所有提供商的配置（API URL、默认模型、能力等）
- **ProviderFactory**：根据配置自动注册提供商，支持动态扩展
- **新增提供商**：只需在 `ProviderConfig.CONFIGS` 中添加配置即可

## 支持的提供商

### 已实现
- ✅ **Google Gemini** - 完整功能（聊天、图像生成/编辑、Deep Research、Google runtime 兼容 helper）
- ✅ **OpenAI** - 完整功能（聊天、图像生成、语音合成、视频、provider-mode Multi-Agent）
- ✅ **Tongyi (通义千问)** - 完整功能（聊天、图像生成/编辑/扩展）
- ✅ **Ollama** - 本地部署模型

说明：
- 多 provider 的 Multi-Agent 能力按统一 mode 提供，不按单个 provider 服务包暴露主入口。

### OpenAI 兼容提供商
以下提供商使用 OpenAI 兼容 API，通过 `OpenAIService` 自动支持：
- ✅ **DeepSeek** - DeepSeek V3 & R1
- ✅ **Moonshot** - 月之暗面 (Kimi)
- ✅ **SiliconFlow** - 硅基流动
- ✅ **ZhiPu AI** - 智谱AI (GLM)
- ✅ **豆包 (Doubao)** - 字节跳动
- ✅ **混元 (Hunyuan)** - 腾讯
- ✅ **NVIDIA NIM** - NVIDIA 模型接口
- ✅ **OpenRouter** - 统一 API 聚合平台

## 使用方式

### 1. 通过工厂创建服务

```python
from app.services.common.provider_factory import ProviderFactory

# 创建服务实例（自动缓存）
service = ProviderFactory.create(
    provider="google",  # 或 "openai", "tongyi", "deepseek", 等
    api_key="your-api-key",
    user_id="user123",  # 可选，用于 Vertex AI 等需要用户配置的场景
    db=db_session      # 可选，用于数据库配置查询
)
```

### 2. 使用统一接口

```python
# 聊天
response = await service.chat(messages, model="gpt-4o")

# 流式聊天
async for chunk in service.stream_chat(messages, model):
    print(chunk)

# 图像生成
images = await service.generate_image(prompt="A beautiful sunset", model="dall-e-3")

# 图像编辑（Google/Tongyi）
edited = await service.edit_image(
    prompt="Add a rainbow",
    model="gemini-2.0-flash-exp",
    reference_images={"raw": image_base64},
    mode="image-chat-edit"
)
```

### 2.1 Multi-Agent 入口约定

- 推荐：`POST /api/modes/{provider}/multi-agent`
- 兼容：`/api/multi-agent/orchestrate` 与 `services.gemini.agent.*` 仅保留为 legacy Google runtime 路径

### 3. 获取可用模型

```python
models = await service.get_available_models()
for model in models:
    print(f"{model.id}: {model.name}")
```

## 配置管理

### ProviderConfig

所有提供商配置集中在 `common/provider_config.py`：

```python
from app.services.common.provider_config import ProviderConfig

# 获取配置
config = ProviderConfig.get_config("google")
base_url = ProviderConfig.get_base_url("openai")
default_model = ProviderConfig.get_default_model("tongyi")

# 检查能力
if ProviderConfig.supports_vision("google"):
    # 支持视觉输入
    pass

# 列出所有提供商
providers = ProviderConfig.list_all_providers()
```

### 新增提供商

只需在 `ProviderConfig.CONFIGS` 中添加配置：

```python
"new_provider": {
    "base_url": "https://api.example.com/v1",
    "default_model": "model-name",
    "client_type": "openai",  # 或 "google", "ollama", "dashscope"
    "supports_streaming": True,
    "supports_function_call": True,
    "name": "New Provider",
    "description": "Provider description",
    "icon": "provider-icon",
    "is_custom": False,
}
```

## 错误处理

统一的错误处理体系（`common/errors.py`）：

```python
from app.services.common.errors import (
    ProviderError,
    OperationError,
    ClientCreationError,
    ConfigurationError
)

try:
    service = ProviderFactory.create("invalid_provider", api_key="...")
except ConfigurationError as e:
    print(f"配置错误: {e}")
except ClientCreationError as e:
    print(f"客户端创建失败: {e}")
```

## 双客户端支持

部分提供商支持双客户端模式（如 Tongyi、Ollama）：

```python
# Tongyi 支持 DashScope SDK 和 OpenAI 兼容 API
# 通过 ClientSelector 自动选择最佳客户端
service = ProviderFactory.create("tongyi", api_key="...")
# 内部会根据配置自动选择客户端
```

## 扩展指南

### 添加新功能到现有提供商

1. 在对应的子目录中创建新的服务类
2. 在主协调器中添加委托方法
3. 遵循协调者模式：协调器只负责委托，业务逻辑在子服务中

### 添加新提供商

1. 在 `ProviderConfig.CONFIGS` 中添加配置
2. 如果使用 OpenAI 兼容 API，无需额外代码（自动使用 `OpenAIService`）
3. 如果需要自定义实现，创建新的提供商目录和协调器类
4. 在 `ProviderFactory._auto_register()` 中添加注册逻辑（如需要）

## 相关文档

- [Gemini 服务架构](./gemini/README.md)
- [OpenAI 服务架构](./openai/README.md)
- [Tongyi 服务架构](./tongyi/README.md)
- [路由与逻辑分离架构设计](../../docs/路由与逻辑分离架构设计文档.md)

## 更新日志

### 2026-01-14
- ✅ 重构目录结构，创建 `common/` 目录统一管理通用服务
- ✅ 移动所有核心基础文件到 `common/` 目录
- ✅ 更新所有导入路径
- ✅ 添加主流提供商：豆包、混元、NVIDIA、OpenRouter
- ✅ 创建服务模块 README 文档
