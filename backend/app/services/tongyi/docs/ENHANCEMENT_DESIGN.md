# Tongyi 图像服务增强设计文档

基于 Qwen-Image 官方参考项目的分析，提出以下增强方案。

## 1. 功能对比分析

### 1.1 当前实现 vs Qwen-Image 参考

| 功能 | 当前实现 | Qwen-Image 参考 | 差距 |
|------|----------|-----------------|------|
| **Prompt 优化** | `prompt_extend=True` (API内置) | LLM 智能改写系统 | 缺少专业化改写 |
| **语言检测** | 无 | 自动中英文检测 | 需新增 |
| **场景分类** | 无 | 人像/文字图/通用图三分类 | 需新增 |
| **编辑 Prompt 优化** | 无 | Qwen-VL-Max 图像理解 | 需新增 |
| **多图编辑** | 单图 | 支持 1-3 图 | 需扩展 |
| **魔法词组** | 无 | 自动追加增强词 | 需新增 |

### 1.2 增强价值评估

| 增强项 | 实现复杂度 | 用户价值 | 优先级 |
|--------|-----------|----------|--------|
| Prompt 优化服务 | 中 | 高 | P0 |
| 编辑 Prompt 优化 | 中 | 高 | P0 |
| 语言检测 | 低 | 中 | P1 |
| 多图编辑支持 | 高 | 中 | P2 |

---

## 2. 架构设计

### 2.1 新增模块结构

```
tongyi/
├── prompt_optimizer/              # 新增: Prompt 优化模块
│   ├── __init__.py
│   ├── language_detector.py       # 语言检测
│   ├── generation_optimizer.py    # 文生图 Prompt 优化
│   └── edit_optimizer.py          # 图像编辑 Prompt 优化
├── image_generation.py            # 增强: 集成 Prompt 优化
├── image_edit.py                  # 增强: 集成编辑优化 + 多图支持
└── ...
```

### 2.2 调用流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户请求                                      │
│              prompt + (images) + options                             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PromptOptimizer                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ 语言检测     │→│ 场景分类     │→│ Prompt 改写  │                 │
│  │ zh/en       │  │ 人像/文字/通用│  │ LLM API     │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                              │                                       │
│                              ▼                                       │
│                    优化后的 Prompt + 魔法词组                         │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              ImageGenerationService / ImageEditService              │
│                    调用 DashScope API                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 详细设计

### 3.1 Prompt 优化服务

#### 3.1.1 语言检测器 (`language_detector.py`)

```python
def detect_language(text: str) -> str:
    """
    检测文本语言

    Args:
        text: 输入文本

    Returns:
        'zh' 或 'en'
    """
    # CJK 字符范围检测
    cjk_ranges = [
        ('\u4e00', '\u9fff'),  # CJK Unified Ideographs
    ]
    for char in text:
        if any(start <= char <= end for start, end in cjk_ranges):
            return 'zh'
    return 'en'
```

#### 3.1.2 文生图 Prompt 优化器 (`generation_optimizer.py`)

**核心功能：**
- 自动分类场景（人像/含文字/通用）
- 调用 Qwen-Plus 进行智能改写
- 添加魔法词组

**接口设计：**

```python
@dataclass
class PromptOptimizeResult:
    """Prompt 优化结果"""
    original_prompt: str          # 原始提示词
    optimized_prompt: str         # 优化后提示词
    language: str                 # 检测到的语言
    scene_type: str              # 场景类型: portrait/text/general
    magic_suffix: str            # 添加的魔法词组

class GenerationPromptOptimizer:
    """文生图 Prompt 优化器"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def optimize(
        self,
        prompt: str,
        enable_rewrite: bool = True,
        add_magic_suffix: bool = True
    ) -> PromptOptimizeResult:
        """
        优化文生图 Prompt

        Args:
            prompt: 原始提示词
            enable_rewrite: 是否启用 LLM 改写
            add_magic_suffix: 是否添加魔法词组

        Returns:
            PromptOptimizeResult
        """
        pass
```

**Prompt 模板（中文版核心）：**

```
# 图像 Prompt 改写专家

你是一位世界顶级的图像 Prompt 构建专家。你的任务是将用户提供的原始图像描述，
根据其内容自动归类为**人像**、**含文字图**或**通用图像**三类之一，
并进行自然、精准、富有美感的改写。

## 基础要求
1. 使用流畅、自然的描述性语言
2. 合理丰富画面细节
3. 严禁修改任何专有名词
4. 完整呈现所有文字信息（用双引号包含）
5. 明确指定整体艺术风格

## 子任务一：人像图像改写
- 指出人物基本信息：种族、性别、年龄、脸型、五官、表情
- 指出服装、发型与配饰
- 指出姿态与动作
- 指出背景与环境

## 子任务二：含文字图改写
- 忠实还原所有文字内容
- 说明文字与载体的关系
- 补充环境与氛围

## 子任务三：通用图像改写
- 核心视觉元素
- 场景与氛围
- 多对象视觉关系
```

**魔法词组：**
- 中文: `"超清，4K，电影级构图"`
- 英文: `"Ultra HD, 4K, cinematic composition"`

#### 3.1.3 编辑 Prompt 优化器 (`edit_optimizer.py`)

**核心功能：**
- 使用 Qwen-VL-Max 理解输入图像
- 根据编辑任务类型优化 Prompt
- 支持多种编辑场景

**接口设计：**

```python
@dataclass
class EditPromptOptimizeResult:
    """编辑 Prompt 优化结果"""
    original_prompt: str
    optimized_prompt: str
    task_type: str  # add/delete/replace/text/style/inpaint/outpaint

class EditPromptOptimizer:
    """图像编辑 Prompt 优化器"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def optimize(
        self,
        prompt: str,
        image: Union[str, bytes, PIL.Image.Image],
        enable_rewrite: bool = True
    ) -> EditPromptOptimizeResult:
        """
        优化编辑 Prompt

        Args:
            prompt: 原始编辑指令
            image: 输入图像 (URL/bytes/PIL Image)
            enable_rewrite: 是否启用 LLM 改写

        Returns:
            EditPromptOptimizeResult
        """
        pass
```

**编辑任务类型处理规则：**

| 任务类型 | 规则 |
|----------|------|
| 添加/删除/替换 | 补充位置、数量、属性等细节 |
| 文字编辑 | 所有文字用双引号包含，保持原语言 |
| 人物编辑 | 强调核心视觉一致性（种族、性别、年龄等） |
| 风格转换 | 描述关键视觉特征 |
| 内容填充 | 使用固定模板 |
| 多图任务 | 明确指出操作哪张图的元素 |

---

### 3.2 ImageGenerationService 增强

#### 3.2.1 新增参数

```python
@dataclass
class ImageGenerationRequest:
    """图像生成请求 - 增强版"""
    model_id: str
    prompt: str
    aspect_ratio: str = "1:1"
    resolution: str = "1.25K"
    num_images: int = 1
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    style: Optional[str] = None

    # 新增参数
    enable_prompt_optimize: bool = True    # 是否启用 Prompt 优化
    add_magic_suffix: bool = True          # 是否添加魔法词组
    return_optimized_prompt: bool = False  # 是否返回优化后的 Prompt
```

#### 3.2.2 集成优化器

```python
class ImageGenerationService:
    def __init__(self, api_key: str, timeout: float = 300.0):
        self.api_key = api_key
        self.timeout = timeout
        self._prompt_optimizer = None  # 延迟加载

    @property
    def prompt_optimizer(self) -> GenerationPromptOptimizer:
        if self._prompt_optimizer is None:
            from .prompt_optimizer import GenerationPromptOptimizer
            self._prompt_optimizer = GenerationPromptOptimizer(self.api_key)
        return self._prompt_optimizer

    async def generate(self, request: ImageGenerationRequest) -> List[ImageGenerationResult]:
        # 步骤 1: Prompt 优化（如果启用）
        prompt = request.prompt
        optimized_info = None

        if request.enable_prompt_optimize:
            optimized_info = await self.prompt_optimizer.optimize(
                prompt=request.prompt,
                add_magic_suffix=request.add_magic_suffix
            )
            prompt = optimized_info.optimized_prompt
            logger.info(f"[ImageGeneration] Prompt 优化完成: {prompt[:100]}...")

        # 步骤 2: 调用 API（现有逻辑）
        ...
```

---

### 3.3 ImageEditService 增强

#### 3.3.1 新增参数

```python
@dataclass
class ImageEditOptions:
    """图像编辑选项 - 增强版"""
    n: int = 1
    negative_prompt: Optional[str] = None
    size: Optional[str] = None
    watermark: bool = False
    seed: Optional[int] = None
    prompt_extend: bool = True

    # 新增参数
    enable_prompt_optimize: bool = True      # 是否启用编辑 Prompt 优化
    reference_images: List[str] = None       # 多图编辑支持 (最多3张)
    preserve_identity: bool = True           # 人物编辑时保持身份一致
    true_guidance_scale: float = 4.0         # True CFG 引导强度
```

#### 3.3.2 多图编辑支持

```python
async def edit(
    self,
    model: str,
    prompt: str,
    image_url: str,
    options: Optional[ImageEditOptions] = None,
    additional_images: Optional[List[str]] = None  # 额外参考图
) -> ImageEditResult:
    """
    执行图像编辑 - 支持多图

    Args:
        model: 模型名称
        prompt: 编辑提示词
        image_url: 主图片 URL
        options: 编辑选项
        additional_images: 额外参考图片 (最多2张)
    """
    # 步骤 1: 编辑 Prompt 优化
    if options.enable_prompt_optimize:
        optimized = await self.edit_optimizer.optimize(
            prompt=prompt,
            image=image_url
        )
        prompt = optimized.optimized_prompt

    # 步骤 2: 构建多图 payload
    if additional_images:
        payload = self.build_multi_image_payload(
            model, prompt, image_url, additional_images, options
        )
    else:
        payload = self.build_single_image_payload(model, prompt, image_url, options)

    # 步骤 3: 调用 API
    ...
```

---

## 4. API 接口变更

### 4.1 ImageGenerationRequest 扩展

```python
# 前端请求示例
{
    "prompt": "一只可爱的猫咪",
    "model": "wan2.6-t2i",
    "aspect_ratio": "1:1",
    "resolution": "1.25K",
    "num_images": 1,

    # 新增字段
    "enable_prompt_optimize": true,
    "add_magic_suffix": true
}
```

### 4.2 ImageEditRequest 扩展

```python
# 前端请求示例
{
    "prompt": "将背景改为海滩",
    "model": "qwen-image-edit-plus",
    "image_url": "https://...",

    # 新增字段
    "enable_prompt_optimize": true,
    "additional_images": [          # 多图编辑
        "https://reference1.jpg",
        "https://reference2.jpg"
    ],
    "true_guidance_scale": 4.0
}
```

### 4.3 响应扩展

```python
# 响应示例
{
    "success": true,
    "images": [
        {"url": "https://..."}
    ],

    # 新增字段
    "prompt_info": {
        "original": "一只可爱的猫咪",
        "optimized": "一只毛色雪白的英短猫咪...",
        "language": "zh",
        "scene_type": "general"
    }
}
```

---

## 5. 实现计划

### Phase 1: Prompt 优化基础设施 (P0)

**任务列表：**

1. **创建 `prompt_optimizer/` 模块结构**
   - `__init__.py`
   - `language_detector.py`
   - `base.py` (基类和数据结构)

2. **实现语言检测器**
   - CJK 字符范围检测
   - 单元测试

3. **实现文生图 Prompt 优化器**
   - 中英文 Prompt 模板
   - Qwen-Plus API 调用封装
   - 魔法词组追加
   - 错误处理和重试

4. **集成到 ImageGenerationService**
   - 新增配置参数
   - 可选启用/禁用优化
   - 日志记录

### Phase 2: 编辑 Prompt 优化 (P0)

**任务列表：**

1. **实现编辑 Prompt 优化器**
   - Qwen-VL-Max API 调用
   - 编辑任务类型分类
   - JSON 响应解析

2. **集成到 ImageEditService**
   - 新增配置参数
   - 图像编码处理

3. **添加编辑模板**
   - 任务类型处理规则
   - 示例输出

### Phase 3: 多图编辑支持 (P2)

**任务列表：**

1. **扩展 ImageEditService**
   - 多图 payload 构建
   - 身份一致性参数

2. **更新 API 接口**
   - 接受多图输入
   - 响应格式调整

3. **前端适配**
   - 多图上传 UI
   - 参考图选择

---

## 6. 配置项

### 6.1 环境变量

```bash
# Prompt 优化配置
TONGYI_PROMPT_OPTIMIZE_ENABLED=true
TONGYI_PROMPT_OPTIMIZE_MODEL=qwen-plus
TONGYI_EDIT_OPTIMIZE_MODEL=qwen-vl-max-latest
TONGYI_MAGIC_SUFFIX_ENABLED=true
TONGYI_PROMPT_OPTIMIZE_TIMEOUT=30
TONGYI_PROMPT_OPTIMIZE_MAX_RETRIES=3
```

### 6.2 功能开关

```python
class PromptOptimizerConfig:
    """Prompt 优化器配置"""
    enabled: bool = True
    generation_model: str = "qwen-plus"
    edit_model: str = "qwen-vl-max-latest"
    add_magic_suffix: bool = True
    timeout: float = 30.0
    max_retries: int = 3

    # 魔法词组
    magic_suffix_zh: str = "超清，4K，电影级构图"
    magic_suffix_en: str = "Ultra HD, 4K, cinematic composition"
```

---

## 7. 风险与注意事项

### 7.1 性能影响

| 操作 | 预估延迟 | 缓解措施 |
|------|----------|----------|
| Prompt 优化 (Qwen-Plus) | 1-3s | 可选启用，并行处理 |
| 编辑优化 (Qwen-VL-Max) | 2-5s | 可选启用，图像压缩 |

### 7.2 成本影响

- Prompt 优化调用 Qwen-Plus API，会产生额外费用
- 建议添加配置开关，允许用户控制是否启用

### 7.3 兼容性

- 所有新增参数均为可选，默认值保持向后兼容
- API 响应扩展为追加字段，不影响现有客户端

---

## 8. 参考资料

- [Qwen-Image 官方仓库](https://github.com/QwenLM/Qwen-Image)
- [DashScope 官方文档](https://help.aliyun.com/zh/dashscope/)
- [通义千问模型 API](https://help.aliyun.com/zh/model-studio/developer-reference/qwen-models)
