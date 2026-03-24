# 通义图像服务 - 前后端参数映射文档

## 概述

本文档详细记录通义（Tongyi）图像服务的前端控件参数与后端服务参数的对应关系，基于新的模块化控件架构。

---

## 一、前端架构概览

### 1.1 目录结构

```
frontend/
├── controls/                          # 控件模块
│   ├── modes/                         # 按提供商分组的控件
│   │   ├── google/                    # Google 主实现
│   │   ├── tongyi/                    # TongYi 专有实现
│   │   │   ├── ImageGenControls.tsx   # 文生图控件
│   │   │   ├── ImageEditControls.tsx  # 图像编辑控件
│   │   │   └── index.ts              # 模块导出
│   │   ├── google/                    # Google 主实现
│   │   │   ├── ImageOutpaintControls.tsx  # 图像外扩控件
│   │   │   ├── VideoGenControls.tsx       # 视频生成控件
│   │   │   └── ...
│   │   └── openai/                    # OpenAI 实现
│
├── coordinators/                      # 协调者模块
│   └── ModeControlsCoordinator.tsx    # 模式控件协调者
```

### 1.2 控件分发机制

`ModeControlsCoordinator` 根据 `providerId` 和 `mode` 分发渲染对应的控件：

```typescript
const getProviderControls = (providerId: string) => {
  switch (providerId) {
    case 'tongyi': return TongYiControls;
    case 'openai': return OpenAIControls;
    default: return GoogleControls;
  }
};
```

### 1.3 ControlsState 状态管理

所有控件参数通过 `ControlsState` 接口统一管理：

```typescript
interface ControlsState {
  // 图像生成参数
  aspectRatio: string;
  resolution: string;
  numberOfImages: number;
  style: string;

  // 高级参数
  showAdvanced: boolean;
  negativePrompt: string;
  seed: number;

  // TongYi 专用参数
  promptExtend: boolean;    // AI 增强提示词
  addMagicSuffix: boolean;  // 魔法词组（默认开启）

  // ... 其他参数
}
```

---

## 二、图像生成参数映射

### 2.1 前端控件: `tongyi/ImageGenControls.tsx`

| UI 参数 | 变量名 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| 风格 | `style` | string | "None" | 图像风格选择 |
| 图片数量 | `numberOfImages` | number | 1 | 1-4 张（z-image-turbo 仅 1 张） |
| 图片比例 | `aspectRatio` | string | "1:1" | 如 "1:1", "16:9", "9:16" |
| 分辨率档位 | `resolution` | string | "1K" | 如 "1K", "1.25K", "1.5K", "2K" |
| Seed | `seed` | number | -1 | 随机种子（-1 表示随机） |
| 负向提示词 | `negativePrompt` | string | "" | 不想出现的内容 |
| AI 增强提示词 | `promptExtend` | boolean | false | 启用 LLM 智能改写 |
| 魔法词组 | `addMagicSuffix` | boolean | true | 自动添加质量增强词 |

### 2.2 后端服务: `ImageGenerationRequest`

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `model_id` | str | - | 模型 ID |
| `prompt` | str | - | 提示词 |
| `aspect_ratio` | str | "1:1" | 宽高比 |
| `resolution` | str | "1.25K" | 分辨率档位 |
| `num_images` | int | 1 | 生成数量 |
| `negative_prompt` | Optional[str] | None | 负向提示词 |
| `seed` | Optional[int] | None | 随机种子 |
| `style` | Optional[str] | None | 风格 |
| `enable_prompt_optimize` | bool | False | 启用 Prompt 智能优化 |
| `add_magic_suffix` | bool | True | 添加魔法词组 |

### 2.3 参数传递: `TongyiService.generate_image()`

```python
request = ImageGenerationRequest(
    model_id=model,
    prompt=prompt,
    aspect_ratio=kwargs.get("aspectRatio") or kwargs.get("aspect_ratio", "1:1"),
    resolution=kwargs.get("imageResolution") or kwargs.get("resolution", "1.25K"),
    num_images=kwargs.get("numberOfImages") or kwargs.get("num_images", 1),
    negative_prompt=kwargs.get("negativePrompt") or kwargs.get("negative_prompt"),
    seed=kwargs.get("seed"),
    style=kwargs.get("imageStyle") or kwargs.get("style"),
    # ⚠️ 需要添加以下参数传递
    # enable_prompt_optimize=kwargs.get("promptExtend", False),
    # add_magic_suffix=kwargs.get("add_magic_suffix", True),
)
```

### 2.4 完整对照表

| 前端参数 | kwargs 键名 | 后端字段 | 状态 |
|---------|------------|---------|------|
| `style` | `imageStyle` / `style` | `style` | ✅ 已对接 |
| `numberOfImages` | `numberOfImages` / `num_images` | `num_images` | ✅ 已对接 |
| `aspectRatio` | `aspectRatio` / `aspect_ratio` | `aspect_ratio` | ✅ 已对接 |
| `resolution` | `imageResolution` / `resolution` | `resolution` | ✅ 已对接 |
| `seed` | `seed` | `seed` | ✅ 已对接 |
| `negativePrompt` | `negativePrompt` / `negative_prompt` | `negative_prompt` | ✅ 已对接 |
| `promptExtend` | `promptExtend` | `enable_prompt_optimize` | ✅ 已对接 |
| `addMagicSuffix` | `addMagicSuffix` | `add_magic_suffix` | ✅ 已对接 |

---

## 三、图像编辑参数映射

### 3.1 前端控件: `tongyi/ImageEditControls.tsx`

| UI 参数 | 变量名 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| 图片比例 | `aspectRatio` | string | "1:1" | 输出比例 |
| 分辨率档位 | `resolution` | string | "1K" | 分辨率档位 |
| 负面提示词 | `negativePrompt` | string | "" | 不想出现的元素 |
| Seed | `seed` | number | -1 | 随机种子 |
| AI 增强提示词 | `promptExtend` | boolean | false | 启用编辑 Prompt 优化 |

### 3.2 后端服务: `ImageEditOptions`

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `n` | int | 1 | 生成数量 |
| `negative_prompt` | Optional[str] | None | 负向提示词 |
| `size` | Optional[str] | None | 输出尺寸 |
| `watermark` | bool | False | 是否添加水印 |
| `seed` | Optional[int] | None | 随机种子 |
| `prompt_extend` | bool | True | API 级别的 prompt 扩展 |
| `enable_prompt_optimize` | bool | False | 启用编辑 Prompt 智能优化 |

### 3.3 完整对照表

| 前端参数 | kwargs 键名 | 后端字段 | 状态 |
|---------|------------|---------|------|
| `aspectRatio` | `aspectRatio` | `size` (转换) | ✅ 已对接 |
| `resolution` | `resolution` | `size` (转换) | ✅ 已对接 |
| `negativePrompt` | `negativePrompt` / `negative_prompt` | `negative_prompt` | ✅ 已对接 |
| `seed` | `seed` | `seed` | ✅ 已对接 |
| `promptExtend` | `promptExtend` / `prompt_extend` | `enable_prompt_optimize` | ✅ 已对接 |

---

## 四、常量定义

### 4.1 默认值

> 注意：文档原引用的 `controls/constants/` 子目录不存在。以下常量定义内联在各控件组件中。

```typescript
export const DEFAULT_CONTROLS = {
  aspectRatio: "1:1",
  resolution: "1K",
  numberOfImages: 1,
  style: "None",
  seed: -1,
  negativePrompt: "",
  outputMimeType: "image/png",
  outputCompressionQuality: 80,
  enhancePrompt: false,
};
```

### 4.2 通义专用比例

```typescript
// 文生图比例
export const TONGYI_GEN_ASPECT_RATIOS = [
  { value: "1:1", label: "1:1" },
  { value: "16:9", label: "16:9" },
  { value: "9:16", label: "9:16" },
  { value: "4:3", label: "4:3" },
  { value: "3:4", label: "3:4" },
  // ... 更多比例
];

// 图像编辑比例
export const TONGYI_EDIT_ASPECT_RATIOS = [...];
```

### 4.3 分辨率档位

```typescript
export const TONGYI_GEN_RESOLUTION_TIERS = [
  { value: "1K", label: "1K" },
  { value: "1.25K", label: "1.25K" },
  { value: "1.5K", label: "1.5K" },
];

// z-image-turbo 额外支持 2K
export const Z_IMAGE_RESOLUTION_TIERS = [
  ...TONGYI_GEN_RESOLUTION_TIERS,
  { value: "2K", label: "2K" },
];
```

---

## 五、模型特殊限制

### 5.1 图片数量限制

| 模型 | 最大图片数 | 前端处理 |
|-----|----------|---------|
| z-image-turbo | 1 | `maxImageCount = 1`，隐藏数量选择器 |
| z-image | 4 | 显示 1-4 选择器 |
| qwen-image-plus | 4 | 显示 1-4 选择器 |
| wan2.x-t2i 系列 | 4 | 显示 1-4 选择器 |

### 5.2 分辨率档位支持

| 模型 | 支持档位 | 前端处理 |
|-----|---------|---------|
| wan2.x-t2i | 1K, 1.25K, 1.5K | 显示 3 档选择器 |
| z-image-turbo | 1K, 1.25K, 1.5K, 2K | 显示 4 档选择器 |
| wan2.6-image | 单档位 | 隐藏分辨率选择器 |

### 5.3 动态参数验证

前端通过 `useEffect` 动态验证参数有效性：

```typescript
// 当模型变化时，验证当前比例是否有效
useEffect(() => {
  const validRatios = availableAspectRatios.map(r => r.value);
  if (!validRatios.includes(aspectRatio)) {
    setAspectRatio(validRatios[0] || '1:1');
  }
}, [modelId, availableAspectRatios, aspectRatio, setAspectRatio]);
```

---

## 六、已修复问题 ✅

### 6.1 问题: `promptExtend` 参数未传递 (已修复)

**修复内容:**
- ✅ `generate_image()` 现已传递 `enable_prompt_optimize` 和 `add_magic_suffix` 参数
- ✅ `edit_image()` 现已传递 `enable_prompt_optimize` 参数
- ✅ 前端新增 "魔法词组" 开关 (`addMagicSuffix`)

**修复代码 (`tongyi_service.py`):**

```python
# generate_image()
enable_prompt_optimize = kwargs.get("promptExtend") or kwargs.get("enable_prompt_optimize", False)
add_magic_suffix = kwargs.get("addMagicSuffix") if kwargs.get("addMagicSuffix") is not None else kwargs.get("add_magic_suffix", True)

request = ImageGenerationRequest(
    # ... 现有参数 ...
    enable_prompt_optimize=enable_prompt_optimize,
    add_magic_suffix=add_magic_suffix,
)

# edit_image()
enable_prompt_optimize = kwargs.get("promptExtend") or kwargs.get("enable_prompt_optimize", False)

options = ImageEditOptions(
    # ... 现有参数 ...
    enable_prompt_optimize=enable_prompt_optimize,
)
```

---

## 七、数据流图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端 (React)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ModeControlsCoordinator                                                     │
│  └── getProviderControls('tongyi')                                          │
│      └── TongYiControls.ImageGenControls                                    │
│          ├── style, numberOfImages, aspectRatio, resolution                 │
│          ├── seed, negativePrompt                                           │
│          └── promptExtend (AI 增强提示词)                                    │
│                                                                              │
│  ControlsState (useControlsState hook)                                       │
│  └── 统一管理所有控件状态                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ HTTP POST /api/generate
┌─────────────────────────────────────────────────────────────────────────────┐
│                              后端 API 层                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  kwargs = {                                                                  │
│    "aspectRatio", "imageResolution", "numberOfImages",                      │
│    "negativePrompt", "seed", "imageStyle", "promptExtend"                   │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TongyiService.generate_image()                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ImageGenerationRequest(                                                     │
│    model_id, prompt, aspect_ratio, resolution, num_images,                  │
│    negative_prompt, seed, style,                                             │
│    enable_prompt_optimize,  ← 从 promptExtend 获取                           │
│    add_magic_suffix         ← 默认 True                                      │
│  )                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ImageGenerationService.generate()                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  if enable_prompt_optimize:                                                  │
│      └── GenerationPromptOptimizer.optimize()                                │
│          ├── detect_language() → 中文/英文                                   │
│          ├── _rewrite_with_llm() → Qwen-Plus 改写                            │
│          └── add_magic_suffix → "超清，4K，电影级构图"                         │
│                                                                              │
│  └── DashScope API 调用                                                      │
│      └── _generate_z_image() / _generate_qwen_image() / _generate_wan_v2()  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 八、Prompt 优化功能

### 8.1 文生图 Prompt 优化

使用 **Qwen-Plus** 模型进行智能改写：

| 功能 | 说明 |
|-----|------|
| 语言检测 | 自动识别中文/英文 |
| 场景分类 | 人像 / 含文字 / 通用图像 |
| 智能改写 | 根据场景优化描述 |
| 魔法词组 | 可选追加质量增强词 |

**中文魔法词组:** `超清，4K，电影级构图`
**英文魔法词组:** `Ultra HD, 4K, cinematic composition`

### 8.2 图像编辑 Prompt 优化

使用 **Qwen-VL-Max** 视觉模型：

| 任务类型 | 处理规则 |
|---------|---------|
| 添加/删除/替换 | 保持原意，补充细节 |
| 文字编辑 | 文字内容用双引号包含 |
| 人像编辑 | 保持视觉一致性 |
| 风格转换 | 描述关键视觉特征 |
| 内容填充 | Inpainting/Outpainting 专用格式 |

---

## 九、修改记录

| 日期 | 修改项 | 文件 | 状态 |
|------|-------|------|------|
| 2026-01-26 | 传递 `promptExtend` → `enable_prompt_optimize` | `tongyi_service.py` | ✅ 完成 |
| 2026-01-26 | 传递 `add_magic_suffix` 参数 | `tongyi_service.py` | ✅ 完成 |
| 2026-01-26 | 前端添加魔法词组开关 (`addMagicSuffix`) | `ImageGenControls.tsx` | ✅ 完成 |
| 2026-01-26 | 新增 `addMagicSuffix` 状态 | `useControlsState.ts`, `types.ts` | ✅ 完成 |

---

## 更新日志

| 日期 | 版本 | 变更内容 |
|-----|------|---------|
| 2026-01-26 | v2.0 | 重写文档，基于新的模块化前端架构 |
| 2026-01-26 | v1.0 | 初始版本 |
