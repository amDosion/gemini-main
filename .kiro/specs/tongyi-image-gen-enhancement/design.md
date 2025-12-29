# Design Document

## Overview

本设计文档描述了图片生成功能的增强实现，主要涉及：
1. 通义提供商多图片生成支持（`n` 参数）
2. 比例与分辨率联动显示（通义和谷歌提供商）
3. 配置集中化与可扩展性设计

核心设计原则：
- **单一数据源**：所有比例和分辨率配置集中在 `constants.ts`
- **动态适配**：UI 组件根据提供商和模型动态显示选项
- **易于扩展**：新增比例或分辨率只需修改配置文件

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        UI Layer                                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐   │
│  │ TongYiImageGenControls │  │ ImageGenControls (Google)     │   │
│  └──────────┬──────────┘  └──────────────┬──────────────────┘   │
│             │                             │                      │
│             └──────────────┬──────────────┘                      │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    constants.ts                              ││
│  │  - Resolution Mappings (per provider, per model, per tier)   ││
│  │  - Aspect Ratio Options (per provider, per model)            ││
│  │  - Helper Functions (getPixelResolution, getAspectRatioLabel)││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                 tongyi/image-gen.ts                          ││
│  │  - generateWanV2Image() - 支持 n 参数                        ││
│  │  - generateZImage() - 支持 n 参数                            ││
│  │  - 多图片响应解析                                             ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Constants 配置模块 (`frontend/controls/constants.ts`)

#### 1.1 分辨率映射数据结构

```typescript
/**
 * 分辨率映射表类型
 * key: 比例值 (如 "1:1", "16:9")
 * value: 像素分辨率 (如 "1280*1280")
 */
type ResolutionMap = Record<string, string>;

/**
 * 分辨率档位配置
 * key: 档位名称 (如 "1K", "1.25K", "1.5K", "2K")
 * value: 该档位的分辨率映射表
 */
type ResolutionTierConfig = Record<string, ResolutionMap>;
```

#### 1.2 通义提供商配置

```typescript
// wan2.x-t2i 系列模型分辨率配置
export const WAN_T2I_RESOLUTIONS: ResolutionTierConfig = {
  '1K': WAN_T2I_1K_RESOLUTIONS,
  '1.25K': WAN_T2I_1280_RESOLUTIONS,
  '1.5K': WAN_T2I_1536_RESOLUTIONS,
};

// z-image-turbo 模型分辨率配置
export const Z_IMAGE_TURBO_RESOLUTIONS: ResolutionTierConfig = {
  '1K': Z_IMAGE_1K_RESOLUTIONS,
  '1.25K': Z_IMAGE_1280_RESOLUTIONS,
  '1.5K': Z_IMAGE_1536_RESOLUTIONS,
  '2K': Z_IMAGE_2K_RESOLUTIONS,
};

// wan2.6-image 模型分辨率配置（单档位）
export const WAN26_IMAGE_RESOLUTIONS: ResolutionTierConfig = {
  'default': WAN26_IMAGE_DEFAULT_RESOLUTIONS,
};
```

#### 1.3 谷歌提供商配置

```typescript
// Google 图片生成分辨率配置
export const GOOGLE_GEN_RESOLUTIONS: ResolutionTierConfig = {
  '1K': GOOGLE_GEN_1K_RESOLUTIONS,
  '2K': GOOGLE_GEN_2K_RESOLUTIONS,
  '4K': GOOGLE_GEN_4K_RESOLUTIONS,
};
```

#### 1.4 辅助函数

```typescript
/**
 * 获取像素分辨率
 * @param aspectRatio 比例值，如 "1:1"
 * @param tier 分辨率档位，如 "1K"
 * @param provider 提供商，如 "tongyi" | "google"
 * @param modelId 模型ID（可选，用于通义提供商区分模型）
 * @returns 像素分辨率，如 "1280*1280"
 */
export function getPixelResolution(
  aspectRatio: string,
  tier: string,
  provider: 'tongyi' | 'google',
  modelId?: string
): string;

/**
 * 获取带像素分辨率的比例标签
 * @param aspectRatio 比例值，如 "1:1"
 * @param tier 分辨率档位，如 "1K"
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 标签，如 "1:1 (1280×1280)"
 */
export function getAspectRatioLabel(
  aspectRatio: string,
  tier: string,
  provider: 'tongyi' | 'google',
  modelId?: string
): string;

/**
 * 获取指定提供商和模型的可用比例列表
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 比例选项数组
 */
export function getAvailableAspectRatios(
  provider: 'tongyi' | 'google',
  modelId?: string
): AspectRatioOption[];

/**
 * 获取指定提供商和模型的可用分辨率档位列表
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 分辨率档位选项数组
 */
export function getAvailableResolutionTiers(
  provider: 'tongyi' | 'google',
  modelId?: string
): ResolutionTierOption[];
```

### 2. UI 组件更新

#### 2.1 TongYiImageGenControls 组件

```typescript
interface TongYiImageGenControlsProps {
  currentModel?: { id: string; name?: string };
  // ... 其他 props
}

// 组件内部逻辑：
// 1. 根据 currentModel.id 判断模型类型
// 2. 调用 getAvailableAspectRatios() 获取可用比例
// 3. 调用 getAvailableResolutionTiers() 获取可用分辨率档位
// 4. 比例选择器显示 getAspectRatioLabel() 返回的标签
```

#### 2.2 ImageGenControls 组件（Google）

```typescript
// 组件内部逻辑：
// 1. 调用 getAvailableAspectRatios('google') 获取可用比例
// 2. 调用 getAvailableResolutionTiers('google') 获取可用分辨率档位
// 3. 比例选择器显示 getAspectRatioLabel() 返回的标签
```

### 3. 服务层更新

#### 3.1 多图片生成支持

```typescript
// tongyi/image-gen.ts

async function generateWanV2Image(
  modelId: string,
  prompt: string,
  options: ChatOptions,
  apiKey: string,
  baseUrl?: string
): Promise<ImageGenerationResult[]> {
  // 1. 构建请求 payload，包含 n 参数
  const n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);
  
  const payload = {
    model: modelId,
    input: { messages: [{ role: "user", content: [{ text: prompt }] }] },
    parameters: {
      size: getPixelResolution(options.imageAspectRatio, options.imageResolution, 'tongyi', modelId),
      n: n,  // 图片数量
      prompt_extend: true,
      watermark: false
    }
  };
  
  // 2. 发送请求
  const response = await fetch(url, { ... });
  const data = await response.json();
  
  // 3. 解析多图片响应
  return parseMultipleImages(data);
}

function parseMultipleImages(data: any): ImageGenerationResult[] {
  const results: ImageGenerationResult[] = [];
  
  if (data.output?.choices) {
    for (const choice of data.output.choices) {
      const content = choice?.message?.content;
      if (Array.isArray(content)) {
        for (const item of content) {
          if (item.image) {
            results.push({
              url: item.image,
              mimeType: 'image/png'
            });
          }
        }
      }
    }
  }
  
  return results;
}
```

## Data Models

### 1. 比例选项接口

```typescript
interface AspectRatioOption {
  label: string;      // 显示标签，如 "1:1 Square"
  value: string;      // 比例值，如 "1:1"
  description?: string; // 可选描述
}
```

### 2. 分辨率档位选项接口

```typescript
interface ResolutionTierOption {
  label: string;      // 显示标签，如 "1K (1280×1280 base)"
  value: string;      // 档位值，如 "1K"
  baseResolution: string; // 基准分辨率，如 "1280×1280"
}
```

### 3. 图片生成结果接口

```typescript
interface ImageGenerationResult {
  url: string;        // 图片 URL
  mimeType: string;   // MIME 类型
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 分辨率映射完整性

*For any* valid aspect ratio and resolution tier combination supported by a provider/model, the `getPixelResolution()` function SHALL return a non-empty pixel resolution string in the format "width*height".

**Validates: Requirements 2.2, 2.3, 3.2**

### Property 2: 比例标签格式一致性

*For any* valid aspect ratio and resolution tier combination, the `getAspectRatioLabel()` function SHALL return a string containing both the ratio (e.g., "1:1") and the pixel resolution (e.g., "1280×1280") in parentheses.

**Validates: Requirements 2.5, 3.5**

### Property 3: 多图片请求参数正确性

*For any* numberOfImages value between 1 and 4 (inclusive), when generating images with wan2.x-t2i models, the API request payload SHALL contain an `n` parameter equal to the numberOfImages value.

**Validates: Requirements 1.1**

### Property 4: 多图片响应解析完整性

*For any* API response containing N images in `output.choices`, the `parseMultipleImages()` function SHALL return an array of exactly N `ImageGenerationResult` objects.

**Validates: Requirements 1.2, 5.1, 5.2, 5.3**

### Property 5: 模型特定比例可用性

*For any* model ID, the `getAvailableAspectRatios()` function SHALL return only the aspect ratios supported by that specific model (e.g., z-image-turbo includes 7:9, 9:7, 9:21 while wan2.x-t2i does not).

**Validates: Requirements 2.7**

### Property 6: 分辨率档位可用性

*For any* model ID, the `getAvailableResolutionTiers()` function SHALL return only the resolution tiers supported by that specific model (e.g., z-image-turbo supports 4 tiers including 2K, while wan2.x-t2i supports 3 tiers).

**Validates: Requirements 4.1, 4.2, 4.3**

## Error Handling

### 1. 无效比例处理

当用户选择的比例不在当前模型支持的列表中时：
- 自动回退到默认比例 `1:1`
- 记录警告日志

### 2. 无效分辨率档位处理

当用户选择的分辨率档位不在当前模型支持的列表中时：
- 自动回退到默认档位（通常是 `1K`）
- 记录警告日志

### 3. API 响应解析错误

当 API 响应格式不符合预期时：
- 尝试备用解析路径
- 如果仍然失败，抛出描述性错误
- 记录完整响应用于调试

### 4. 图片数量限制

- `z-image-turbo` 模型：强制限制为 1 张
- 其他模型：限制在 1-4 张范围内
- 超出范围时自动调整到最近的有效值

## Testing Strategy

### 1. 单元测试

- 测试 `getPixelResolution()` 函数的各种输入组合
- 测试 `getAspectRatioLabel()` 函数的格式正确性
- 测试 `parseMultipleImages()` 函数的响应解析
- 测试边界条件和错误处理

### 2. 属性测试

使用 `fast-check` 库进行属性测试：

```typescript
import fc from 'fast-check';

// Property 1: 分辨率映射完整性
fc.assert(
  fc.property(
    fc.constantFrom(...validAspectRatios),
    fc.constantFrom(...validTiers),
    (aspectRatio, tier) => {
      const result = getPixelResolution(aspectRatio, tier, 'tongyi', 'wan2.6-t2i');
      return result.match(/^\d+\*\d+$/) !== null;
    }
  ),
  { numRuns: 100 }
);

// Property 4: 多图片响应解析完整性
fc.assert(
  fc.property(
    fc.integer({ min: 1, max: 4 }),
    (n) => {
      const mockResponse = generateMockResponse(n);
      const results = parseMultipleImages(mockResponse);
      return results.length === n;
    }
  ),
  { numRuns: 100 }
);
```

### 3. 集成测试

- 测试 UI 组件与 constants 配置的集成
- 测试服务层与 API 的集成
- 测试端到端的图片生成流程
