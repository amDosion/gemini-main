# 图片服务目录重组设计文档

> **文档版本**: v1.2
> **创建日期**: 2025-01-16
> **最后更新**: 2025-01-16
> **作者**: Claude Code
> **状态**: 待审核

---

## 1. 背景与目标

### 1.1 当前问题

`backend/app/services/gemini/` 根目录下有 12 个图片相关文件，命名采用 `imagen_xxx.py` 和 `image_edit_xxx.py` 前缀：

| 当前文件名 | API 类型 | 职责 |
|-----------|----------|------|
| `imagen_base.py` | Common | 抽象基类 |
| `imagen_common.py` | Common | 共享工具/异常 |
| `imagen_config.py` | Common | 配置模型 |
| `imagen_gemini_api.py` | Gemini API | API Key 实现 |
| `imagen_vertex_ai.py` | Vertex AI | 服务账号实现 |
| `imagen_coordinator.py` | Hybrid | Factory 选择器 |
| `image_edit_base.py` | Common | 抽象基类 |
| `image_edit_common.py` | Common | 共享工具/异常 |
| `image_edit_gemini_api.py` | Gemini API | STUB（不支持） |
| `image_edit_vertex_ai.py` | Vertex AI | 完整实现 |
| `image_edit_coordinator.py` | Hybrid | Factory 选择器 |
| `image_generator.py` | Hybrid | 入口包装器 |

**问题**：
1. 根目录文件过多（41个 Python 文件）
2. API 实现类型不易识别
3. 功能模块之间边界不清晰

### 1.2 设计目标

1. **清晰的模块边界**：按功能分组到子目录
2. **API 实现可识别**：Gemini API 和 Vertex AI 文件一目了然
3. **符合行业最佳实践**：参考 LangChain、FastAPI 等项目
4. **最小化破坏性变更**：保持向后兼容

---

## 2. 行业最佳实践参考

### 2.1 LangChain 模式

[LangChain](https://github.com/langchain-ai/langchain) 采用三层分离架构：

```
langchain/
├── libs/
│   ├── core/              # 基础抽象和接口
│   ├── community/         # 社区维护的集成
│   └── partners/          # 特定提供商包
│       ├── anthropic/
│       ├── openai/
│       └── google/
```

**关键设计原则**：
- **接口与实现分离**：`langchain-core` 定义接口，partner packages 提供实现
- **可替换性**：所有实现遵循相同接口，可无缝切换
- **最小依赖**：用户只安装需要的 provider

### 2.2 FastAPI 生产模式 (2025)

[FastAPI Best Practices 2025](https://orchestrator.dev/blog/2025-1-30-fastapi-production-patterns/) 推荐：

```
app/
├── factories/           # Factory 模式
├── strategies/          # Strategy 模式
├── services/            # 业务逻辑
└── repositories/        # 数据访问
```

**关键设计模式**：
- **Factory Pattern**：集中创建逻辑，支持多种实现
- **Strategy Pattern**：行为可替换
- **Dependency Injection**：测试友好

### 2.3 外部 API 集成设计模式

[Design Patterns for External API Integration](https://mshaeri.com/blog/design-patterns-i-use-in-external-service-integration-in-python/) 推荐：

> 使用 Strategy（行为）+ Factory（创建）+ Singleton（复用）的组合，使项目更易维护、开发友好、测试友好。

---

## 3. 推荐方案：按功能分离 + Factory 模式

### 3.1 目录结构

```
backend/app/services/gemini/
├── __init__.py
├── google_service.py                    # [Hybrid] 主协调器
│
├── imagen/                              # 图片生成模块
│   ├── __init__.py                      # 模块导出
│   ├── base.py                          # [Common] BaseImageGenerator 抽象基类
│   ├── common.py                        # [Common] 共享工具、异常类
│   ├── config.py                        # [Common] Pydantic 配置模型
│   ├── coordinator.py                   # [Hybrid] Factory - 选择 API 实现
│   ├── gemini_api.py                    # [Gemini API] API Key 实现
│   └── vertex_ai.py                     # [Vertex AI] 服务账号实现
│
├── image_edit/                          # 图片编辑模块
│   ├── __init__.py                      # 模块导出
│   ├── base.py                          # [Common] BaseImageEditor 抽象基类
│   ├── common.py                        # [Common] 共享工具、异常类
│   ├── coordinator.py                   # [Hybrid] Factory - 选择 API 实现
│   ├── gemini_api.py                    # [Gemini API] STUB（不支持）
│   └── vertex_ai.py                     # [Vertex AI] 完整实现
│
├── image_generator.py                   # [Hybrid] 向后兼容入口
└── ... (其他现有文件保持不变)
```

### 3.2 模块 `__init__.py` 设计

#### imagen/__init__.py

```python
"""
图片生成模块 (Imagen)

支持两种 API 实现：
- Gemini API: 使用 API Key 认证
- Vertex AI: 使用服务账号认证

使用方式：
    from services.gemini.imagen import ImagenCoordinator

    coordinator = ImagenCoordinator(api_key=key, user_id=uid, db=db)
    result = await coordinator.generate_images(prompt, model)
"""

# 抽象基类
from .base import BaseImageGenerator

# 共享组件
from .common import (
    ConfigurationError,
    ContentPolicyError,
    validate_prompt,
    validate_model,
)

# 具体实现
from .gemini_api import GeminiAPIImageGenerator  # [Gemini API]
from .vertex_ai import VertexAIImageGenerator    # [Vertex AI]

# 协调器 (Factory)
from .coordinator import ImagenCoordinator, get_usage_stats

__all__ = [
    # 抽象
    'BaseImageGenerator',
    # Gemini API
    'GeminiAPIImageGenerator',
    # Vertex AI
    'VertexAIImageGenerator',
    # Factory
    'ImagenCoordinator',
    'get_usage_stats',
    # 共享
    'ConfigurationError',
    'ContentPolicyError',
]
```

#### image_edit/__init__.py

```python
"""
图片编辑模块 (Image Edit)

支持两种 API 实现：
- Gemini API: STUB（图片编辑不支持）
- Vertex AI: 完整支持（inpainting, outpainting, product-image）

使用方式：
    from services.gemini.image_edit import ImageEditCoordinator

    coordinator = ImageEditCoordinator(user_id=uid, db=db)
    result = await coordinator.edit_image(prompt, model, reference_images, mode)
"""

# 抽象基类
from .base import BaseImageEditor

# 共享组件
from .common import (
    NotSupportedError,
    validate_reference_images,
    validate_edit_mode,
)

# 具体实现
from .gemini_api import GeminiAPIImageEditor    # [Gemini API] STUB
from .vertex_ai import VertexAIImageEditor      # [Vertex AI]

# 协调器 (Factory)
from .coordinator import ImageEditCoordinator

__all__ = [
    # 抽象
    'BaseImageEditor',
    # Gemini API
    'GeminiAPIImageEditor',
    # Vertex AI
    'VertexAIImageEditor',
    # Factory
    'ImageEditCoordinator',
    # 共享
    'NotSupportedError',
]
```

### 3.3 文件重命名映射

| 原文件名 | 新路径 |
|---------|--------|
| `imagen_base.py` | `imagen/base.py` |
| `imagen_common.py` | `imagen/common.py` |
| `imagen_config.py` | `imagen/config.py` |
| `imagen_gemini_api.py` | `imagen/gemini_api.py` |
| `imagen_vertex_ai.py` | `imagen/vertex_ai.py` |
| `imagen_coordinator.py` | `imagen/coordinator.py` |
| `image_edit_base.py` | `image_edit/base.py` |
| `image_edit_common.py` | `image_edit/common.py` |
| `image_edit_gemini_api.py` | `image_edit/gemini_api.py` |
| `image_edit_vertex_ai.py` | `image_edit/vertex_ai.py` |
| `image_edit_coordinator.py` | `image_edit/coordinator.py` |
| `image_generator.py` | `image_generator.py` (保持不变) |

---

## 4. 实施计划

### 4.1 第一阶段：创建子目录结构

1. 创建 `imagen/` 目录
2. 创建 `image_edit/` 目录
3. 创建各自的 `__init__.py`

### 4.2 第二阶段：移动文件并更新内部导入

1. 移动 imagen 相关文件到 `imagen/`
2. 移动 image_edit 相关文件到 `image_edit/`
3. 更新内部相对导入：
   - `from .imagen_base` → `from .base`
   - `from .imagen_common` → `from .common`

### 4.3 第三阶段：更新外部导入

需要更新的文件：

| 文件 | 当前导入 | 新导入 |
|------|----------|--------|
| `google_service.py` | `from .image_edit_coordinator` | `from .image_edit import ImageEditCoordinator` |
| `image_generator.py` | `from .imagen_coordinator` | `from .imagen import ImagenCoordinator` |
| `handlers/outpainting_handler.py` | `from ..image_edit_coordinator` | `from ..image_edit import ImageEditCoordinator` |
| `handlers/inpainting_handler.py` | `from ..image_edit_coordinator` | `from ..image_edit import ImageEditCoordinator` |
| `routers/models/vertex_ai_config.py` | `from ...imagen_common` | `from ...imagen import ConfigurationError` |
| `routers/deprecated/generate.py` | 多处导入 | 使用模块级导入 |
| `services/openai/openai_service.py` | `from ..gemini.image_generator` | 保持不变 |

### 4.4 第四阶段：验证

1. 运行所有测试
2. 检查导入是否正确
3. 验证 API 功能正常

---

## 5. 向后兼容性

### 5.1 保留入口文件

`image_generator.py` 保持在根目录，作为向后兼容入口：

```python
# image_generator.py - 向后兼容
"""
向后兼容入口

推荐使用：
    from services.gemini.imagen import ImagenCoordinator

已弃用（但仍可用）：
    from services.gemini.image_generator import ImageGenerator
"""
from .imagen import ImagenCoordinator, ContentPolicyError

# 向后兼容别名
ImageGenerator = ImagenCoordinator

__all__ = ['ImageGenerator', 'ContentPolicyError']
```

### 5.2 根目录 `__init__.py` 兼容导出

```python
# services/gemini/__init__.py
# ... 现有导出 ...

# 新增：模块级导入
from . import imagen
from . import image_edit

# 向后兼容导出（可选）
from .imagen import ImagenCoordinator, GeminiAPIImageGenerator, VertexAIImageGenerator
from .image_edit import ImageEditCoordinator
```

---

## 6. 设计理由

### 6.1 为什么按功能分离（而非按 API 类型）？

| 维度 | 按功能分离 | 按 API 类型分离 |
|------|-----------|-----------------|
| **内聚性** | 高（相关代码在一起） | 低（功能分散） |
| **发现性** | 找 imagen 功能去 `imagen/` | 需要知道 API 类型 |
| **扩展性** | 新功能 = 新目录 | 新 API = 所有目录都要加 |
| **行业惯例** | LangChain, FastAPI 采用 | 较少见 |

### 6.2 Factory 模式的价值

```python
# coordinator.py 作为 Factory
class ImagenCoordinator:
    """Factory 模式选择 API 实现"""

    def get_generator(self) -> BaseImageGenerator:
        if self._config.get('api_mode') == 'vertex_ai':
            return VertexAIImageGenerator(...)  # [Vertex AI]
        else:
            return GeminiAPIImageGenerator(...) # [Gemini API]
```

**优势**：
1. 调用方无需知道具体实现
2. 运行时动态选择
3. 失败自动降级

---

## 7. API 类型详细说明（基于源码分析）

### 7.1 Gemini API (API Key 认证)

**源码位置**: `imagen_gemini_api.py:71`, `genai_agent/client.py:43`

**客户端初始化代码**:
```python
# imagen_gemini_api.py - GeminiAPIImageGenerator._ensure_initialized()
from google import genai as google_genai

self._client = google_genai.Client(api_key=self.api_key)
```

```python
# genai_agent/client.py - get_genai_client()
import google.genai as genai

client = genai.Client(api_key=api_key)
```

**特点**：
- 使用 `GEMINI_API_KEY` 环境变量或传入的 api_key
- 适合个人开发者和小型项目
- 只需一个参数：`api_key`

**文件标识**：`gemini_api.py`

### 7.2 Vertex AI (服务账号认证)

**源码位置**: `imagen_vertex_ai.py:112-127`, `agent/client.py:286-328`

**客户端初始化代码**:
```python
# imagen_vertex_ai.py - VertexAIImageGenerator._ensure_initialized()
from google import genai as google_genai
from google.oauth2 import service_account

# 创建 credentials 对象
credentials = service_account.Credentials.from_service_account_info(
    self.credentials_info,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)

# 初始化客户端
self._client = google_genai.Client(
    vertexai=True,
    project=self.project_id,
    location=self.location,
    credentials=credentials
)
```

```python
# agent/client.py - Client.__init__() Vertex AI 模式
import vertexai as vertexai_module
from google import genai

# 初始化 Vertex AI SDK
vertexai_module.init(project=self._project, location=self._location)

# 创建客户端
client_kwargs = {
    'vertexai': True,
    'project': self._project,
    'location': self._location,
}
if self._credentials:
    client_kwargs['credentials'] = self._credentials

self._genai_client = genai.Client(**client_kwargs)
```

**特点**：
- 使用 Google Cloud 服务账号 JSON
- 需要 `project_id`, `location`, `credentials` 三个参数
- 适合企业级部署

**文件标识**：`vertex_ai.py`

### 7.3 Hybrid (协调器)

**源码位置**: `agent/client.py:222-401`

**核心逻辑**:
```python
# agent/client.py - Client.__init__()
class Client:
    def __init__(
        self,
        *,
        vertexai: Optional[bool] = None,      # 是否使用 Vertex AI
        api_key: Optional[str] = None,         # API Key (Gemini API)
        credentials = None,                    # Service Account (Vertex AI)
        project: Optional[str] = None,         # GCP Project ID
        location: Optional[str] = None,        # GCP Location
        ...
    ):
        if self._vertexai:
            # Vertex AI 模式
            client_kwargs['vertexai'] = True
            client_kwargs['project'] = self._project
            client_kwargs['location'] = self._location
            if self._credentials:
                client_kwargs['credentials'] = self._credentials
        else:
            # Gemini API 模式
            client_kwargs['api_key'] = self._api_key

        self._genai_client = genai.Client(**client_kwargs)
```

**特点**：
- 运行时根据 `vertexai` 参数选择 API 实现
- 提供统一接口
- 支持两种认证方式的无缝切换

**文件标识**：`coordinator.py`, `client.py`

### 7.4 客户端初始化参数对比

| 参数 | Gemini API | Vertex AI |
|------|------------|-----------|
| `api_key` | **必需** | 不使用 |
| `vertexai` | `False` (默认) | `True` |
| `project` | 不使用 | **必需** |
| `location` | 不使用 | **必需** (默认: `us-central1`) |
| `credentials` | 不使用 | **必需** (service_account.Credentials) |

### 7.5 SDK 依赖

```python
# 两种模式都需要
from google import genai

# Vertex AI 额外需要
from google.oauth2 import service_account
import vertexai  # 可选，用于 vertexai.init()
```

---

## 8. Coordinator 详细工作流程（基于源码分析）

### 8.1 ImagenCoordinator 工作流程

**源码位置**: `imagen_coordinator.py:52-335`

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ImagenCoordinator 初始化流程                      │
├─────────────────────────────────────────────────────────────────────┤
│  __init__(user_id, db)                                              │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────────┐                   │
│  │ _load_config()                               │                   │
│  │   1. 尝试从数据库加载用户配置                  │                   │
│  │      - VertexAIConfig 表                     │                   │
│  │      - ConfigProfile 表（获取 API Key）       │                   │
│  │   2. 如果失败，从环境变量加载                  │                   │
│  │      - GOOGLE_GENAI_USE_VERTEXAI            │                   │
│  │      - GEMINI_API_KEY                       │                   │
│  │      - GOOGLE_CLOUD_PROJECT                 │                   │
│  │      - GOOGLE_CLOUD_LOCATION                │                   │
│  │      - GOOGLE_APPLICATION_CREDENTIALS_JSON  │                   │
│  └─────────────────────────────────────────────┘                   │
│       │                                                             │
│       ▼                                                             │
│  初始化 _generator_cache: Dict[str, BaseImageGenerator]            │
└─────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────┐
│                    get_generator() 选择流程                          │
├─────────────────────────────────────────────────────────────────────┤
│  get_generator()                                                    │
│       │                                                             │
│       ▼                                                             │
│  api_mode = config['api_mode']  # 'gemini_api' 或 'vertex_ai'      │
│       │                                                             │
│       ├──────────── 检查缓存 ────────────┐                         │
│       │                                  │                         │
│       ▼                                  ▼                         │
│  [缓存命中]                          [缓存未命中]                   │
│       │                                  │                         │
│       │                                  ▼                         │
│       │                         ┌─────────────────┐                │
│       │                         │ api_mode 判断    │                │
│       │                         └────────┬────────┘                │
│       │                     ┌────────────┴────────────┐            │
│       │                     ▼                         ▼            │
│       │              [vertex_ai]               [gemini_api]        │
│       │                     │                         │            │
│       │                     ▼                         ▼            │
│       │         ┌───────────────────┐    ┌───────────────────┐    │
│       │         │ _create_vertex_ai │    │ _create_gemini_api │    │
│       │         │ _generator()      │    │ _generator()       │    │
│       │         │                   │    │                    │    │
│       │         │ VertexAIImage     │    │ GeminiAPIImage     │    │
│       │         │ Generator(        │    │ Generator(         │    │
│       │         │   project_id,     │    │   api_key          │    │
│       │         │   location,       │    │ )                  │    │
│       │         │   credentials_json│    │                    │    │
│       │         │ )                 │    │                    │    │
│       │         └────────┬──────────┘    └─────────┬──────────┘    │
│       │                  │                         │               │
│       │                  │    ┌────────────────────┘               │
│       │                  │    │                                    │
│       │                  ▼    ▼                                    │
│       │         [失败?] ──────────────────────────┐               │
│       │              │                            │               │
│       │              ▼                            ▼               │
│       │         [Vertex AI 失败]            [成功: 缓存并返回]     │
│       │              │                                            │
│       │              ▼                                            │
│       │         降级到 Gemini API                                  │
│       │         _fallback_count++                                  │
│       │              │                                            │
│       └──────────────┴────────────────────────────────────────────┤
│                                                                     │
│  返回 BaseImageGenerator 实例                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 ImageEditCoordinator 智能路由

**源码位置**: `image_edit_coordinator.py:351-479`

```
┌─────────────────────────────────────────────────────────────────────┐
│                    edit_image() 智能路由逻辑                         │
├─────────────────────────────────────────────────────────────────────┤
│  edit_image(prompt, model, reference_images, mode, ...)            │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      路由优先级                                  ││
│  └─────────────────────────────────────────────────────────────────┘│
│       │                                                             │
│       ├─── mode='image-chat-edit' ─────────────────────────────────┤
│       │         │                                                   │
│       │         ▼                                                   │
│       │    ConversationalImageEditService                          │
│       │    (需要: chat_session_manager, sdk_initializer)           │
│       │                                                             │
│       ├─── mode='image-mask-edit' ─────────────────────────────────┤
│       │         │                                                   │
│       │         ▼                                                   │
│       │    Vertex AI Imagen (edit_mode='mask_edit')                │
│       │    ⚠️ 必须有 mask                                           │
│       │                                                             │
│       ├─── mode='image-inpainting' ────────────────────────────────┤
│       │         │                                                   │
│       │         ▼                                                   │
│       │    Vertex AI Imagen (edit_mode='inpainting')               │
│       │    ⚠️ 通常需要 mask                                         │
│       │                                                             │
│       ├─── mode='image-background-edit' ───────────────────────────┤
│       │         │                                                   │
│       │         ▼                                                   │
│       │    Vertex AI Imagen (edit_mode='background_edit')          │
│       │                                                             │
│       ├─── mode='image-recontext' ─────────────────────────────────┤
│       │         │                                                   │
│       │         ▼                                                   │
│       │    Vertex AI Imagen (edit_mode='recontext')                │
│       │                                                             │
│       ├─── 未指定 mode + 有 mask ───────────────────────────────────┤
│       │         │                                                   │
│       │         ▼                                                   │
│       │    Vertex AI Imagen (自动检测)                              │
│       │                                                             │
│       └─── 未指定 mode + 无 mask ───────────────────────────────────┤
│                 │                                                   │
│                 ▼                                                   │
│            SimpleImageEditService                                   │
│            (使用 generateContent API)                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 配置加载机制

**配置加载优先级**:

```python
# imagen_coordinator.py:129-247

def _load_config(self) -> Dict[str, Any]:
    """
    配置加载优先级:
    1. 数据库用户配置 (VertexAIConfig + ConfigProfile)
    2. 环境变量
    """
```

| 优先级 | 配置源 | 适用场景 |
|--------|--------|----------|
| 1 | 数据库 `VertexAIConfig` 表 | 生产环境，多用户 |
| 2 | 数据库 `ConfigProfile` 表 | Gemini API Key |
| 3 | 环境变量 | 开发/测试环境 |

**数据库配置字段**:

| 表名 | 字段 | 用途 |
|------|------|------|
| `VertexAIConfig` | `api_mode` | 'gemini_api' 或 'vertex_ai' |
| `VertexAIConfig` | `vertex_ai_project_id` | GCP 项目 ID |
| `VertexAIConfig` | `vertex_ai_location` | GCP 区域 (默认: us-central1) |
| `VertexAIConfig` | `vertex_ai_credentials_json` | 加密的服务账号 JSON |
| `ConfigProfile` | `api_key` | Gemini API Key |

**环境变量配置**:

| 环境变量 | 用途 | 默认值 |
|----------|------|--------|
| `GOOGLE_GENAI_USE_VERTEXAI` | 是否使用 Vertex AI | `false` |
| `GEMINI_API_KEY` | Gemini API Key | - |
| `GOOGLE_CLOUD_PROJECT` | GCP 项目 ID | - |
| `GOOGLE_CLOUD_LOCATION` | GCP 区域 | `us-central1` |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | 服务账号 JSON | - |

### 8.4 缓存与性能优化

**生成器缓存机制**:

```python
# imagen_coordinator.py:72, 90-100

class ImagenCoordinator:
    def __init__(self, ...):
        self._generator_cache: Dict[str, BaseImageGenerator] = {}

    def get_generator(self) -> BaseImageGenerator:
        api_mode = self._config.get('api_mode', 'gemini_api')

        # 缓存命中
        if api_mode in self._generator_cache:
            return self._generator_cache[api_mode]

        # 创建并缓存
        generator = self._create_xxx_generator()
        self._generator_cache[api_mode] = generator
        return generator
```

**性能优势**:
- 避免重复创建客户端实例
- 减少认证开销
- 支持热切换 (`reload_config()`)

### 8.5 降级策略

**自动降级流程**:

```python
# imagen_coordinator.py:117-127

# 如果 Vertex AI 创建失败，自动降级到 Gemini API
try:
    if api_mode == 'vertex_ai':
        generator = self._create_vertex_ai_generator()
except Exception as e:
    if api_mode == 'vertex_ai':
        logger.warning("Falling back to Gemini API")
        _fallback_count += 1
        return self._create_gemini_api_generator()
```

**降级触发条件**:
1. Vertex AI credentials 无效
2. GCP 项目配置错误
3. 网络连接问题
4. 权限不足

### 8.6 监控指标

**使用统计 API**:

```python
# imagen_coordinator.py:27-41

def get_usage_stats() -> Dict[str, int]:
    return {
        "vertex_ai_usage": _vertex_ai_usage_count,
        "gemini_api_usage": _gemini_api_usage_count,
        "fallback_count": _fallback_count
    }
```

| 指标 | 说明 |
|------|------|
| `vertex_ai_usage` | Vertex AI 调用次数 |
| `gemini_api_usage` | Gemini API 调用次数 |
| `fallback_count` | 降级次数（Vertex AI → Gemini API） |

---

## 9. 重构后的目录树预览

```
backend/app/services/gemini/
├── __init__.py
├── google_service.py                    # [Hybrid] 主协调器
│
├── imagen/                              # 图片生成子模块
│   ├── __init__.py                      # 模块导出
│   ├── base.py                          # [Common] BaseImageGenerator
│   ├── common.py                        # [Common] 异常类、验证函数
│   ├── config.py                        # [Common] Pydantic 配置
│   ├── coordinator.py                   # [Hybrid] Factory
│   ├── gemini_api.py                    # [Gemini API] GeminiAPIImageGenerator
│   └── vertex_ai.py                     # [Vertex AI] VertexAIImageGenerator
│
├── image_edit/                          # 图片编辑子模块
│   ├── __init__.py                      # 模块导出
│   ├── base.py                          # [Common] BaseImageEditor
│   ├── common.py                        # [Common] 异常类、验证函数
│   ├── coordinator.py                   # [Hybrid] Factory
│   ├── gemini_api.py                    # [Gemini API] STUB
│   └── vertex_ai.py                     # [Vertex AI] VertexAIImageEditor
│
├── image_generator.py                   # [Hybrid] 向后兼容入口
│
├── agent/                               # Agent Engine 子模块（保持不变）
├── handlers/                            # Mode handlers 子模块（保持不变）
├── shared/                              # 共享组件子模块（保持不变）
├── genai_agent/                         # GenAI Agent 子模块（保持不变）
│
└── ... (其他 41 个文件保持不变)
```

---

## 10. 参考资源

- [LangChain Architecture](https://docs.langchain.com/oss/python/langchain/overview)
- [FastAPI Best Practices 2025](https://orchestrator.dev/blog/2025-1-30-fastapi-production-patterns/)
- [Design Patterns for External API Integration](https://mshaeri.com/blog/design-patterns-i-use-in-external-service-integration-in-python/)
- [The Factory Method Pattern in Python](https://realpython.com/factory-method-python/)
- [Python Application Layouts](https://realpython.com/python-application-layouts/)

---

## 11. 变更历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2025-01-16 | Claude Code | 初始版本 |
| v1.1 | 2025-01-16 | Claude Code | 第7节加入基于源码分析的客户端初始化代码详情，新增7.4参数对比表和7.5 SDK依赖说明 |
| v1.2 | 2025-01-16 | Claude Code | 新增第8节 Coordinator 详细工作流程，包含流程图、智能路由逻辑、配置加载机制、缓存策略、降级策略和监控指标 |
