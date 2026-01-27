# Controls 常量模块化结构

## 概述

`constants.ts` 已重构为模块化结构，所有常量按功能拆分到独立文件中，便于维护和扩展。

## 文件结构

```
constants/
├── types.ts          # 类型定义（AspectRatioOption, ResolutionTierOption）
├── aspectRatios.ts   # 比例选项常量
├── resolutions.ts    # 分辨率映射和档位常量
├── styles.ts         # 风格选项常量
├── voices.ts         # 语音选项常量
├── defaults.ts       # 默认值常量（IMAGE_COUNTS, OUTPUT_MIME_OPTIONS, DEFAULT_CONTROLS）
├── tryon.ts          # 虚拟试衣专用（BASE_STEPS_OPTIONS, TRYON_DEFAULTS）
├── utils.ts          # 工具函数（getPixelResolution, getAvailableAspectRatios 等）
├── index.ts          # 统一导出
└── README.md         # 本文档
```

## 模块说明

### types.ts
- `AspectRatioOption` - 比例选项接口
- `ResolutionTierOption` - 分辨率档位选项接口

### aspectRatios.ts
包含所有比例选项常量：
- `GEN_ASPECT_RATIOS` - 通用比例
- `GOOGLE_EDIT_ASPECT_RATIOS` - Google 图像编辑比例
- `OPENAI_ASPECT_RATIOS` - OpenAI 比例
- `TONGYI_EDIT_ASPECT_RATIOS` - 通义图像编辑比例
- `TONGYI_GEN_ASPECT_RATIOS` - 通义文生图比例
- `Z_IMAGE_ASPECT_RATIOS` - z-image-turbo 专用比例
- `WAN26_IMAGE_ASPECT_RATIOS` - wan2.6-image 专用比例
- `GOOGLE_GEN_ASPECT_RATIOS` - Google 图片生成比例
- `VIDEO_ASPECT_RATIOS` - 视频比例

### resolutions.ts
包含所有分辨率映射和档位常量：
- 图像编辑分辨率映射（`QWEN_EDIT_RESOLUTIONS`, `WAN_EDIT_RESOLUTIONS`）
- 文生图分辨率映射（`WAN_T2I_*_RESOLUTIONS`, `Z_IMAGE_*_RESOLUTIONS`）
- Google 分辨率映射（`GOOGLE_GEN_*_RESOLUTIONS`）
- 分辨率档位选项（`TONGYI_GEN_RESOLUTION_TIERS`, `Z_IMAGE_RESOLUTION_TIERS`, `GOOGLE_GEN_RESOLUTION_TIERS`）
- 通用分辨率选项（`RESOLUTIONS`, `VIDEO_RESOLUTIONS`）

### styles.ts
- `STYLES` - 风格选项数组

### voices.ts
- `VOICES` - 语音选项数组（音频生成）

### defaults.ts
- `IMAGE_COUNTS` - 图片数量选项（试衣、文生图等共用）
- `OUTPUT_MIME_OPTIONS` - 输出格式选项（试衣、Imagen 等共用：PNG/JPEG）
- `DEFAULT_CONTROLS` - 默认控件值对象

### tryon.ts
官方支持的 Virtual Try-On 参数（来源: docs/virtual_try_on_sdk_usage_zh.md）：
- `BASE_STEPS_OPTIONS` - 质量步数选项（8/16/32/48）
- `TRYON_DEFAULTS` - 试衣默认值（baseSteps=32, outputMimeType=image/jpeg, outputCompressionQuality=100）

注意：服装类型（上装/下装/全身）不是官方 API 支持的参数，已移除

### utils.ts
工具函数：
- `getPixelResolution()` - 获取像素分辨率
- `getAspectRatioLabel()` - 获取带像素分辨率的比例标签
- `getAvailableAspectRatios()` - 获取可用比例列表
- `getAvailableResolutionTiers()` - 获取可用分辨率档位列表

## 使用方式

### 标准导入方式
从 `controls/constants` 导入（自动解析到 `constants/index.ts`）：
```typescript
import { DEFAULT_CONTROLS, STYLES, VOICES } from '../controls/constants';
```

### 按需导入（推荐）
可以直接从子模块导入，减少打包体积：
```typescript
// 只导入需要的常量
import { STYLES } from '../controls/constants/styles';
import { DEFAULT_CONTROLS } from '../controls/constants/defaults';
import { getPixelResolution } from '../controls/constants/utils';
```

### 统一导出
通过 `constants/index.ts` 统一导出所有内容：
```typescript
import * from '../controls/constants';
```

## 优势

1. **模块化**：按功能拆分，便于维护
2. **按需导入**：可以只导入需要的常量，减少打包体积
3. **向后兼容**：原有的 `constants.ts` 文件保留，重新导出所有内容
4. **清晰结构**：每个文件职责单一，易于理解
5. **易于扩展**：添加新常量时，只需修改对应的模块文件

## 迁移指南

无需迁移！所有现有的导入语句都可以继续使用，因为 `constants.ts` 文件会重新导出所有模块化内容。

如果需要优化打包体积，可以逐步将导入改为从子模块导入。
