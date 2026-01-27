# Tongyi Service Module

通义服务模块 - 基于阿里云 DashScope SDK 的服务实现。

## 架构概述

本模块采用 **协调者模式（Coordinator Pattern）** 架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                         Router Layer                            │
│          (tongyi.py, image_edit.py, image_expand.py)           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ ProviderFactory.create("tongyi")
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TongyiService                              │
│                   (Main Coordinator)                            │
│  - 统一的对外接口，仅负责请求分发                                    │
│  - 不包含业务逻辑，委托给具体子服务                                   │
│  - 延迟加载子服务实例                                              │
└────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│  Chat  │ │ Image  │ │ Image  │ │ Image  │ │ Model  │
│Provider│ │Generate│ │  Edit  │ │ Expand │ │Manager │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

## 目录结构

```
tongyi/
├── __init__.py                 # 模块导出
├── tongyi_service.py           # 主协调器 (Main Coordinator)
│
├── # === Base Configuration ===
├── base.py                     # 基础配置（端点、分辨率映射）
│
├── # === Chat Service ===
├── chat.py                     # 通义千问聊天服务 (QwenNativeProvider)
│
├── # === Image Services ===
├── image_generation.py         # 文生图服务 (ImageGenerationService)
├── image_edit.py               # 图像编辑服务 (ImageEditService)
├── image_expand.py             # 图像扩展服务 (ImageExpandService)
├── file_upload.py              # 文件上传服务
│
├── # === Prompt Optimizer (新增) ===
├── prompt_optimizer/           # Prompt 智能优化模块
│   ├── __init__.py
│   ├── language_detector.py    # 语言检测（中文/英文）
│   ├── generation_optimizer.py # 文生图 Prompt 优化
│   └── edit_optimizer.py       # 图像编辑 Prompt 优化
│
├── # === Model Management ===
├── model_manager.py            # 模型管理器
├── fetch_bailian_models_live.py # 百炼模型实时获取
└── aliyun_bailian_models.json  # 百炼模型缓存数据
```

## 核心组件

### TongyiService (Main Coordinator)

所有通义服务的统一入口点，使用委托模式分发请求：

```python
from ..services.provider_factory import ProviderFactory

# 通过工厂创建服务
service = ProviderFactory.create(
    provider="tongyi",
    api_key=api_key,
    user_id=user_id,
    db=db
)

# 使用服务方法
response = await service.chat(messages, model)
images = await service.generate_image(prompt, model)
edited = await service.edit_image(prompt, model, reference_images)
expanded = await service.expand_image(prompt, model, reference_images)
```

### 委托的子服务

| 子服务 | 描述 | TongyiService 方法 |
|--------|------|-------------------|
| QwenNativeProvider | 聊天对话 | `chat()`, `stream_chat()` |
| ImageGenerationService | 图像生成 | `generate_image()` |
| ImageEditService | 图像编辑 | `edit_image()` |
| ImageExpandService | 图像扩展 | `expand_image()` |
| ModelManager | 模型管理 | `get_available_models()` |

## 聊天服务 (QwenNativeProvider)

使用 DashScope 原生 SDK，支持高级功能：

### 功能特性

| 功能 | 描述 |
|------|------|
| 基础聊天 | 文本对话 |
| 流式输出 | 实时响应 |
| 网页搜索 | `enable_search` 参数 |
| 代码解释器 | `code_interpreter` 插件 |
| PDF 解析 | `pdf_extracter` 插件 |
| 图片理解 | Qwen-VL 视觉模型 |

### 支持的模型

**文本模型：**
- qwen-turbo, qwen-plus, qwen-max
- qwen2.5-72b-instruct, qwen2.5-32b-instruct
- qwen-long（长文本）
- qwen-coder-turbo（代码）

**视觉模型：**
- qwen-vl-max, qwen-vl-plus
- qwen2-vl-72b-instruct, qwen2.5-vl-72b-instruct

```python
# 文本聊天
response = await service.chat(
    messages=[{"role": "user", "content": "Hello"}],
    model="qwen-turbo"
)

# 流式聊天
async for chunk in service.stream_chat(messages, model):
    print(chunk)
```

## 图像服务

### 图像生成 (ImageGenerationService)

文生图服务，支持多种模型：

**万相系列 (WanX)：**
- wan2.6-t2i - 万相2.6（推荐）
- wan2.5-t2i-preview - 万相2.5
- wan2.2-t2i-plus/flash - 万相2.2
- wanx2.1-t2i-plus/turbo - 万相2.1
- wanx2.0-t2i-turbo - 万相2.0

**Z-Image 系列：**
- z-image-plus - Z-Image专业版
- z-image-standard - Z-Image标准版

**其他：**
- qwen-image-plus - 通义图像

```python
images = await service.generate_image(
    prompt="美丽的日落风景",
    model="wan2.6-t2i",
    aspect_ratio="16:9",
    resolution="1.25K",
    num_images=1,
    negative_prompt="模糊，低质量"
)
```

### 图像编辑 (ImageEditService)

基于参考图片的编辑服务：

```python
result = await service.edit_image(
    prompt="将背景改为海滩",
    model="wanx-t2i-edit",
    reference_images={"raw": image_url},
    number_of_images=1
)
```

### 图像扩展 (ImageExpandService)

图像外扩（Outpainting）服务，支持三种模式：

| 模式 | 描述 | 参数 |
|------|------|------|
| `scale` | 缩放模式 | `x_scale`, `y_scale` |
| `offset` | 偏移模式 | `left/right/top/bottom_offset` |
| `ratio` | 比例模式 | `angle`, `output_ratio` |

```python
result = await service.expand_image(
    prompt="扩展风景",
    model="wanx-outpainting",
    reference_images={"raw": image_url},
    mode="scale",
    x_scale=2.0,
    y_scale=1.5
)
```

## Prompt 智能优化 (新增)

基于 Qwen-Image 官方参考实现的 Prompt 智能优化功能。

### 功能特性

| 功能 | 描述 |
|------|------|
| 语言检测 | 自动检测中文/英文 |
| 场景分类 | 人像/含文字图/通用图三分类 |
| LLM 改写 | 使用 Qwen-Plus 智能改写 Prompt |
| 魔法词组 | 自动追加 "4K, 电影级构图" |
| 编辑优化 | 使用 Qwen-VL-Max 理解图像优化编辑指令 |

### 文生图 Prompt 优化

```python
from .prompt_optimizer import GenerationPromptOptimizer

optimizer = GenerationPromptOptimizer(api_key)
result = await optimizer.optimize(
    prompt="一只可爱的猫咪",
    enable_rewrite=True,
    add_magic_suffix=True
)

print(result.optimized_prompt)
# 输出: "一只毛色雪白的英短猫咪，圆润的脸庞...超清，4K，电影级构图"
print(result.language)  # "zh"
```

### 编辑 Prompt 优化

```python
from .prompt_optimizer import EditPromptOptimizer

optimizer = EditPromptOptimizer(api_key)
result = await optimizer.optimize(
    prompt="将背景改为海滩",
    image=image_url,
    enable_rewrite=True
)

print(result.optimized_prompt)
# 输出: "Replace the current background with a sunny beach scene..."
```

### 在图像生成中使用

```python
from .image_generation import ImageGenerationRequest, ImageGenerationService

service = ImageGenerationService(api_key)
request = ImageGenerationRequest(
    model_id="wan2.6-t2i",
    prompt="一只可爱的猫咪",
    enable_prompt_optimize=True,  # 启用 Prompt 优化
    add_magic_suffix=True
)

results = await service.generate(request)
# results[0].optimized_prompt 包含优化后的 Prompt
```

### 在图像编辑中使用

```python
from .image_edit import ImageEditService, ImageEditOptions

service = ImageEditService(api_key)
options = ImageEditOptions(
    enable_prompt_optimize=True  # 启用编辑 Prompt 优化
)

result = await service.edit(
    model="qwen-image-edit-plus",
    prompt="将背景改为海滩",
    image_url=image_url,
    options=options
)
# result.optimized_prompt 包含优化后的 Prompt
```

## 基础配置 (base.py)

### API 端点

```python
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"

ENDPOINTS = {
    "image-generation": "/api/v1/services/aigc/multimodal-generation/generation",
    "out-painting": "/api/v1/services/aigc/image2image/out-painting",
    "file": "/api/v1/files",
    "task": "/api/v1/tasks",
}
```

### 分辨率映射

支持多种模型的分辨率配置：

**Z-Image 分辨率：**
| 档位 | 1:1 | 16:9 | 9:16 | 特有比例 |
|------|-----|------|------|----------|
| 1K | 1024×1024 | 1280×720 | 720×1280 | 7:9, 9:21 |
| 1.25K | 1280×1280 | 1536×864 | 864×1536 | 7:9, 9:21 |
| 1.5K | 1536×1536 | 2048×1152 | 1152×2048 | 7:9, 9:21 |
| 2K | 2048×2048 | 2730×1536 | 1536×2730 | 7:9, 9:21 |

**WanV2 分辨率：**
| 档位 | 1:1 | 16:9 | 9:16 |
|------|-----|------|------|
| 1K | 1280×1280 | 1280×720 | 720×1280 |
| 1.25K | 1440×1440 | 1440×810 | 810×1440 |
| 1.5K | 1536×1536 | 1536×864 | 864×1536 |

**Qwen 分辨率（固定）：**
- 1:1 → 1328×1328
- 16:9 → 1664×928
- 9:16 → 928×1664
- 4:3 → 1472×1140
- 3:4 → 1140×1472

## 模型管理 (ModelManager)

### 模型来源

1. **静态维护的万相模型** - 在 `chat.py` 中硬编码
2. **百炼模型** - 从 `aliyun_bailian_models.json` 加载
3. **实时获取** - 通过 `fetch_bailian_models_live.py` 从 API 获取

### 模型分类

| 类别 | 模型示例 |
|------|----------|
| 文本聊天 | qwen-turbo, qwen-max |
| 视觉理解 | qwen-vl-max, qwen2.5-vl-72b |
| 代码生成 | qwen-coder-turbo |
| 长文本 | qwen-long |
| 文生图 | wan2.6-t2i, z-image-plus |
| 图像编辑 | wanx-t2i-edit |

## 文件上传 (file_upload.py)

DashScope 文件上传服务：

```python
from .file_upload import upload_to_dashscope, upload_bytes_to_dashscope

# 从文件路径上传
result = await upload_to_dashscope(file_path, api_key)

# 从字节数据上传
result = await upload_bytes_to_dashscope(file_bytes, filename, api_key)

# 结果
print(result.file_id)    # 文件 ID
print(result.file_url)   # 文件 URL
```

## 使用示例

### 1. 聊天对话

```python
service = ProviderFactory.create("tongyi", api_key=api_key)

# 普通聊天
response = await service.chat(
    messages=[
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"}
    ],
    model="qwen-turbo"
)

# 启用网页搜索
response = await service.chat(
    messages=[{"role": "user", "content": "今天的新闻"}],
    model="qwen-turbo",
    enable_search=True
)
```

### 2. 图像生成

```python
service = ProviderFactory.create("tongyi", api_key=api_key)

images = await service.generate_image(
    prompt="赛博朋克风格的城市夜景",
    model="wan2.6-t2i",
    aspect_ratio="16:9",
    resolution="1.5K",
    num_images=2,
    negative_prompt="模糊，噪点",
    style="cyberpunk"
)

for img in images:
    print(f"URL: {img['url']}")
```

### 3. 图像编辑

```python
service = ProviderFactory.create("tongyi", api_key=api_key)

result = await service.edit_image(
    prompt="将天空改为星空",
    model="wanx-t2i-edit",
    reference_images={"raw": "https://example.com/image.jpg"},
    number_of_images=1
)
```

### 4. 图像扩展

```python
service = ProviderFactory.create("tongyi", api_key=api_key)

# 缩放模式
result = await service.expand_image(
    prompt="扩展自然风景",
    model="wanx-outpainting",
    reference_images={"raw": image_url},
    mode="scale",
    x_scale=2.0,
    y_scale=1.0
)

# 比例模式
result = await service.expand_image(
    prompt="扩展为宽屏",
    model="wanx-outpainting",
    reference_images={"raw": image_url},
    mode="ratio",
    output_ratio="21:9"
)
```

## 配置

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | DashScope API Key | - |
| `DASHSCOPE_BASE_URL` | API 基础 URL | `https://dashscope.aliyuncs.com` |

### 数据库配置

API Key 通过数据库 `ConfigProfile` 表配置：

```python
# 从数据库获取用户的 Tongyi 配置
profiles = db.query(ConfigProfile).filter(
    ConfigProfile.provider_id == 'tongyi',
    ConfigProfile.user_id == user_id
).all()
```

## 错误处理

```python
from ..errors import (
    ProviderError,
    OperationError,
    APIKeyError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError
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
except InvalidRequestError as e:
    # 请求参数无效
    pass
except OperationError as e:
    # 操作执行失败
    pass
```

## 与 OpenAI 兼容 API 的对比

| 特性 | DashScope 原生 SDK | OpenAI 兼容 API |
|------|-------------------|-----------------|
| 功能覆盖率 | 100% | ~50% |
| 网页搜索 | 支持 | 不支持 |
| 代码解释器 | 支持 | 不支持 |
| PDF 解析 | 支持 | 不支持 |
| 图像服务 | 完整支持 | 部分支持 |
| 万相模型 | 完整支持 | 不支持 |

## 相关文档

- [路由与逻辑分离架构设计文档](../../../docs/路由与逻辑分离架构设计文档.md)
- [DashScope 官方文档](https://help.aliyun.com/zh/dashscope/)
- [通义千问模型](https://help.aliyun.com/zh/model-studio/developer-reference/qwen-models)
- [万相文生图](https://help.aliyun.com/zh/model-studio/text-to-image-v2)
