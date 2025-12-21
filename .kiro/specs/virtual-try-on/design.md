# Virtual Try-On 功能设计文档

## 1. 概述

本文档描述 Virtual Try-On 功能的技术设计方案。该功能基于 Gemini 2.5 的图像分割能力、Vertex AI Imagen 3 的图像编辑能力和 Imagen 4 的超分辨率能力，实现服装的虚拟替换、画布扩展和图像质量提升。

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  App.tsx                                                                     │
│  └─ handleModeSwitch('virtual-try-on')                                      │
│     └─ setAppMode('virtual-try-on')                                         │
│     └─ 自动选择支持 vision 的模型                                            │
│                                                                              │
│  StudioView.tsx                                                              │
│  └─ switch(mode)                                                             │
│     └─ case 'virtual-try-on': return <VirtualTryOnView {...props} />        │
│                                                                              │
│  VirtualTryOnView.tsx                                                        │
│  └─ 用户上传图片 → 选择服装类型 → 预览掩码 → 输入描述 → 点击生成            │
│  └─ onSend(prompt, options, attachments, 'virtual-try-on')                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据处理层                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  useChat.ts                                                                  │
│  └─ sendMessage()                                                            │
│     └─ if (mode === 'virtual-try-on')                                       │
│        └─ const result = await handleVirtualTryOn(attachments, context)     │
│        └─ 更新 UI 显示                                                       │
│        └─ 提交上传任务到 Redis 队列                                          │
│                                                                              │
│  handlers/virtualTryOnHandler.ts                                             │
│  └─ handleVirtualTryOn(text, attachments, context)                          │
│     └─ 调用 virtualTryOnService                                             │
│     └─ 下载结果图创建 Blob URL                                               │
│     └─ 返回 HandlerResult                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              服务层                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  services/providers/google/media/virtual-tryon.ts                            │
│  └─ virtualTryOn(ai, referenceImage, options)                               │
│     ├─ Step 1: segmentClothing(ai, image, target)                           │
│     │          └─ 调用 Gemini API 进行服装分割                               │
│     │          └─ 返回 SegmentationResult[]                                 │
│     │                                                                        │
│     ├─ Step 2: generateMask(segmentationResults, imageSize)                 │
│     │          └─ 合并分割结果生成完整掩码                                    │
│     │                                                                        │
│     ├─ Step 3: 调用后端 /api/tryon/edit                                     │
│     │          └─ 发送 image + mask + prompt                                │
│     │          └─ 返回编辑后的图片                                           │
│     │                                                                        │
│     └─ Step 4 (可选): upscaleImage()                                        │
│                └─ 调用后端 /api/tryon/upscale                               │
│                └─ 提高图像分辨率                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              后端层                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  backend/app/routers/tryon.py                                                │
│  ├─ POST /api/tryon/edit                                                     │
│  │  └─ 接收 image, mask, prompt, edit_mode                                  │
│  │  └─ 调用 Vertex AI Imagen 3 API                                          │
│  │  └─ 返回编辑后的图片                                                      │
│  │                                                                           │
│  └─ POST /api/tryon/upscale                                                  │
│     └─ 接收 image, upscale_factor                                           │
│     └─ 检查分辨率限制（17MP）                                                │
│     └─ 调用 Imagen 4 upscale 模型                                           │
│     └─ 返回高分辨率图片                                                      │
│                                                                              │
│  backend/app/services/tryon_service.py                                       │
│  ├─ edit_with_mask(image, mask, prompt, edit_mode)                          │
│  └─ upscale_image(image, upscale_factor, add_watermark)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流对比（参考 image-outpainting 模式）

| 层级 | image-outpainting | virtual-try-on |
|------|-------------------|----------------|
| 类型定义 | `AppMode` 包含 `'image-outpainting'` | 需新增 `'virtual-try-on'` |
| UI 组件 | `ImageExpandView.tsx` | 需新增 `VirtualTryOnView.tsx` |
| Handler | `imageExpandHandler.ts` | 需新增 `virtualTryOnHandler.ts` |
| useChat 分支 | `else if (mode === 'image-outpainting')` | 需新增 `else if (mode === 'virtual-try-on')` |
| 服务 | `tongyi/image-expand.ts` | 需新增 `google/media/virtual-tryon.ts` |
| 后端 API | `/api/image/out-painting` | 需新增 `/api/tryon/edit`, `/api/tryon/upscale` |

## 3. 组件与接口

### 3.1 类型定义扩展

**文件路径**：`types.ts`

```typescript
// 1. 扩展 AppMode
export type AppMode = 
  | 'chat' 
  | 'image-gen' 
  | 'image-edit' 
  | 'video-gen' 
  | 'audio-gen' 
  | 'image-outpainting' 
  | 'pdf-extract'
  | 'virtual-try-on';  // 新增

// 2. 新增 VirtualTryOnOptions
export interface VirtualTryOnOptions {
  targetClothing: 'top' | 'bottom' | 'full' | 'custom';
  customTarget?: string;  // 当 targetClothing 为 'custom' 时使用
  editMode: 'inpainting-insert' | 'inpainting-remove';
  dilation?: number;  // 掩码膨胀系数，默认 0.02
  showMaskPreview?: boolean;  // 是否显示掩码预览
  
  // Upscale 选项
  enableUpscale?: boolean;
  upscaleFactor?: 2 | 4;  // 放大倍数
  addWatermark?: boolean;  // 是否添加水印
}

// 3. 扩展 ChatOptions
export interface ChatOptions {
  // ... 现有字段 ...
  virtualTryOnTarget?: string;  // 保留兼容性
  virtualTryOnOptions?: VirtualTryOnOptions;  // 新增详细选项
}
```

### 3.2 Handler 接口

**文件路径**：`frontend/hooks/handlers/virtualTryOnHandler.ts`

```typescript
import { HandlerContext, HandlerResult } from './types';
import { Attachment } from '../../../types';

export interface VirtualTryOnHandlerResult extends HandlerResult {
  segmentationPreview?: string;  // 分割预览图 URL（可选）
  uploadTask?: Promise<{ 
    dbAttachments: Attachment[]; 
    dbUserAttachments: Attachment[] 
  }>;
}

/**
 * 处理 Virtual Try-On 模式
 * 
 * @param text - 服装描述文本
 * @param attachments - 附件列表（需包含人物图片）
 * @param context - 处理器上下文
 * @returns 生成结果
 */
export async function handleVirtualTryOn(
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<VirtualTryOnHandlerResult>;
```

### 3.3 前端服务接口

**文件路径**：`frontend/services/providers/google/media/virtual-tryon.ts`

```typescript
import { GoogleGenAI } from "@google/genai";
import { Attachment, ChatOptions } from "../../../../../types";
import { ImageGenerationResult } from "../../interfaces";

// ========== 类型定义 ==========

export interface SegmentationResult {
  mask: string;           // Base64 编码的掩码图像 "data:image/png;base64,..."
  box_2d: number[];       // 边界框坐标 [y0, x0, y1, x1]（归一化到 1000）
  label: string;          // 物体标签
}

export interface TryOnOptions {
  targetClothing: string;       // 要分割的服装类型（如 "hoodie", "jacket"）
  prompt: string;               // 服装描述
  editMode?: 'inpainting-insert' | 'inpainting-remove';
  dilation?: number;            // 掩码膨胀系数（默认 0.02）
  modelId?: string;             // Gemini 模型 ID（用于分割）
  
  // Upscale 选项
  enableUpscale?: boolean;
  upscaleFactor?: 2 | 4;
  addWatermark?: boolean;
}

// ========== 主函数 ==========

/**
 * Virtual Try-On 主函数
 * 整合分割、编辑、扩展和超分辨率流程
 */
export async function virtualTryOn(
  ai: GoogleGenAI,
  referenceImage: Attachment,
  options: TryOnOptions,
  apiKey: string
): Promise<ImageGenerationResult>;

// ========== 辅助函数 ==========

/**
 * 服装分割
 * 调用 Gemini API 进行服装区域分割
 */
export async function segmentClothing(
  ai: GoogleGenAI,
  image: Attachment,
  targetClothing: string,
  modelId?: string
): Promise<SegmentationResult[]>;

/**
 * 生成完整掩码
 * 将分割结果合并为完整的二值掩码
 */
export function generateMask(
  segmentationResults: SegmentationResult[],
  imageWidth: number,
  imageHeight: number
): string;  // 返回 Base64 编码的掩码图像

/**
 * 生成掩码预览（用于 UI 显示）
 * 返回半透明红色叠加的预览图
 */
export async function generateMaskPreview(
  imageBase64: string,
  targetClothing: string,
  apiKey: string
): Promise<string>;  // 返回 data:image/png;base64,...

/**
 * 调用后端编辑 API
 */
export async function editWithMask(
  imageBase64: string,
  maskBase64: string,
  prompt: string,
  editMode: 'inpainting-insert' | 'inpainting-remove',
  dilation?: number
): Promise<ImageGenerationResult>;

/**
 * 调用后端 Upscale API
 */
export async function upscaleImage(
  imageBase64: string,
  upscaleFactor: 2 | 4,
  addWatermark?: boolean
): Promise<ImageGenerationResult>;
```

### 3.4 后端 API 接口

**文件路径**：`backend/app/routers/tryon.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

router = APIRouter(prefix="/api/tryon", tags=["tryon"])

# ========== 编辑接口 ==========

class TryOnEditRequest(BaseModel):
    image: str  # Base64 编码的原图
    mask: str   # Base64 编码的掩码
    prompt: str  # 服装描述
    edit_mode: str = "inpainting-insert"  # 编辑模式
    mask_mode: str = "foreground"  # 掩码模式
    dilation: float = 0.02  # 膨胀系数

class TryOnEditResponse(BaseModel):
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mimeType: str = "image/png"
    error: Optional[str] = None

@router.post("/edit", response_model=TryOnEditResponse)
async def edit_image(request: TryOnEditRequest) -> TryOnEditResponse:
    """使用 Vertex AI Imagen 3 进行图像编辑"""
    pass

# ========== Upscale 接口 ==========

class UpscaleRequest(BaseModel):
    image: str  # Base64 编码的原图
    upscale_factor: Literal[2, 4]  # 放大倍数
    add_watermark: bool = False  # 是否添加水印

class UpscaleResponse(BaseModel):
    success: bool
    image: Optional[str] = None  # Base64 编码的高分辨率图像
    mimeType: str = "image/png"
    original_resolution: str  # 原始分辨率（如 "1024x1024"）
    upscaled_resolution: str  # 放大后分辨率（如 "4096x4096"）
    error: Optional[str] = None

@router.post("/upscale", response_model=UpscaleResponse)
async def upscale_image(request: UpscaleRequest) -> UpscaleResponse:
    """使用 Imagen 4 进行图像超分辨率"""
    pass

# ========== 分割接口（调试用）==========

class SegmentRequest(BaseModel):
    image: str  # Base64 编码的图片
    target: str = "clothing"  # 分割目标
    api_key: str  # Gemini API Key

class SegmentationResult(BaseModel):
    box_2d: list[float]  # 边界框
    mask: str  # Base64 编码的掩码
    label: str  # 标签

class SegmentResponse(BaseModel):
    success: bool
    segments: Optional[list[SegmentationResult]] = None
    error: Optional[str] = None

@router.post("/segment", response_model=SegmentResponse)
async def segment_clothing(request: SegmentRequest) -> SegmentResponse:
    """使用 Gemini API 进行服装分割（主要用于调试）"""
    pass
```

### 3.5 UI 组件接口

**文件路径**：`frontend/components/views/VirtualTryOnView.tsx`

```typescript
interface VirtualTryOnViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  initialAttachments?: Attachment[];
  providerId?: string;
  sessionId?: string | null;
}
```

**组件结构**：

```
┌─────────────────────────────────────────────────────────────┐
│                    VirtualTryOnView                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   侧边栏         │    │         主画布区域              │ │
│  │  - 历史记录      │    │  - 原图/结果图显示              │ │
│  │  - 掩码预览      │    │  - 掩码叠加预览（半透明红色）   │ │
│  │  - 对比滑块      │    │  - 缩放/平移控制                │ │
│  │                 │    │  - 对比视图（左右滑动）         │ │
│  └─────────────────┘    └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    底部控制区                            │ │
│  │  - 服装类型选择（上衣/下装/全身/自定义）                  │ │
│  │  - 生成掩码预览按钮                                      │ │
│  │  - 服装描述输入框                                        │ │
│  │  - Upscale 控件（2x/4x）                                 │ │
│  │  - 生成按钮                                              │ │
│  │  - 下载按钮（原图/结果图/掩码）                          │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 4. 数据模型

### 4.1 分割掩码数据结构

```typescript
// Gemini API 返回的原始 JSON 格式
interface GeminiSegmentationResponse {
  box_2d: [number, number, number, number];  // [y0, x0, y1, x1] 归一化到 1000
  mask: string;  // "data:image/png;base64,..."
  label: string;  // 物体标签
}
```

### 4.2 掩码处理流程

```
1. Gemini 返回 JSON 数据（可能包含多个分割结果）
   ↓
2. 解析 box_2d 坐标（归一化到 1000）
   ↓
3. 解码 Base64 掩码图像
   ↓
4. 将归一化坐标转换为绝对像素坐标
   box_2d_abs = [
     y0 * imageHeight / 1000,
     x0 * imageWidth / 1000,
     y1 * imageHeight / 1000,
     x1 * imageWidth / 1000
   ]
   ↓
5. 调整掩码大小以匹配边界框
   ↓
6. 将掩码放置到完整图像的正确位置
   ↓
7. 合并多个分割结果（如果有）
   ↓
8. 生成最终的二值掩码（白色=服装区域，黑色=其他区域）
```

### 4.4 Upscale 分辨率检查

```python
def check_upscale_resolution(
    width: int,
    height: int,
    upscale_factor: int
) -> tuple[bool, str]:
    """
    检查超分辨率后的分辨率是否超过限制
    
    Args:
        width: 原始宽度
        height: 原始高度
        upscale_factor: 放大倍数
    
    Returns:
        (is_valid, error_message)
    """
    MAX_MEGAPIXELS = 17
    
    new_width = width * upscale_factor
    new_height = height * upscale_factor
    new_megapixels = (new_width * new_height) / 1_000_000
    
    if new_megapixels > MAX_MEGAPIXELS:
        return False, f"输出分辨率 {new_megapixels:.2f}MP 超过限制 {MAX_MEGAPIXELS}MP"
    
    return True, ""
```

## 5. 正确性属性

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 分割掩码覆盖完整性
*For any* 包含目标服装的人物图像，分割函数返回的掩码应完全覆盖目标服装区域，不遗漏任何部分。
**Validates: Requirements 3.1.2**

### Property 2: 掩码坐标转换正确性
*For any* Gemini 返回的归一化坐标 `box_2d`，转换后的绝对像素坐标应满足：
- `0 <= x0_abs < x1_abs <= imageWidth`
- `0 <= y0_abs < y1_abs <= imageHeight`
**Validates: Requirements 3.1.3**

### Property 3: 编辑区域隔离性
*For any* 编辑操作，非掩码区域的像素值应保持不变（允许边缘融合区域的微小变化）。
**Validates: Requirements 3.2.2**

### Property 4: 服装描述一致性
*For any* 服装描述 prompt，生成的服装应与描述的颜色、款式、材质等特征一致。
**Validates: Requirements 3.2.1**

### Property 5: Upscale 分辨率限制
*For any* 超分辨率操作，输出分辨率（输入分辨率 × 放大倍数）不应超过 17 megapixels。
**Validates: Requirements 3.4.4**

### Property 6: 错误处理完整性
*For any* API 调用失败，系统应返回明确的错误信息，不应抛出未捕获的异常。
**Validates: Requirements 3.8.1, 3.8.2, 3.8.3, 3.8.4**

### Property 7: 掩码预览可见性
*For any* 生成的掩码预览，用户应能清晰看到半透明红色叠加区域，且该区域应与实际编辑区域一致。
**Validates: Requirements 3.5.4**

## 6. 错误处理

### 6.1 分割阶段错误

| 错误类型 | 错误码 | 处理方式 |
|---------|--------|---------|
| JSON 解析失败 | `SEGMENT_PARSE_ERROR` | 返回空数组，提示用户重试 |
| 掩码解码失败 | `MASK_DECODE_ERROR` | 跳过该项，继续处理其他结果 |
| 边界框无效 | `INVALID_BBOX` | 跳过该项，记录警告日志 |
| 未检测到目标 | `NO_TARGET_FOUND` | 提示用户检查图像或调整目标类型 |

### 6.2 编辑阶段错误

| 错误类型 | 错误码 | 处理方式 |
|---------|--------|---------|
| Vertex AI 认证失败 | `AUTH_ERROR` | 提示用户检查 GCP 配置 |
| 安全过滤触发 | `SAFETY_FILTER` | 提示用户修改 prompt |
| API 配额超限 | `QUOTA_EXCEEDED` | 提示用户稍后重试 |
| 图像尺寸超限 | `IMAGE_TOO_LARGE` | 自动缩放或提示用户 |

### 6.3 Upscale 错误

| 错误类型 | 错误码 | 处理方式 |
|---------|--------|---------|
| 分辨率超限 | `RESOLUTION_EXCEEDED` | 提示用户当前分辨率和限制 |
| 模型不可用 | `MODEL_UNAVAILABLE` | 提示用户稍后重试 |
| 内存不足 | `OUT_OF_MEMORY` | 建议用户使用较小的放大倍数 |

## 7. 测试策略

### 7.1 单元测试

- 测试 `segmentClothing` 函数的 JSON 解析逻辑
- 测试 `generateMask` 函数的坐标转换正确性
- 测试 `check_upscale_resolution` 函数的分辨率检查
- 测试错误处理分支

### 7.2 属性测试

- **Property 2 测试**：生成随机的归一化坐标，验证转换后的绝对坐标在有效范围内
- **Property 5 测试**：生成随机的图像尺寸和放大倍数，验证分辨率检查逻辑
- **Property 6 测试**：模拟各种 API 错误，验证错误处理逻辑

### 7.3 集成测试

- 测试完整的分割 → 编辑流程
- 测试虚拟试衣 → Upscale 组合流程
- 测试完整工作流：试衣 → 超分辨率
- 测试不同服装类型的分割效果
- 测试边界情况（无服装、多件服装等）

### 7.4 UI 测试

- 测试掩码预览显示
- 测试对比滑块功能
- 测试下载功能
- 测试图片上传验证
- 测试错误提示显示

## 8. 实现注意事项

### 8.1 Gemini 分割 Prompt

```python
prompt = f"""
Give the segmentation masks for {object_to_segment}. 
Output a JSON list of segmentation masks where each entry contains:
- the 2D bounding box in the key 'box_2d'
- the segmentation mask in key 'mask'
- the text label in the key 'label'
"""
```

### 8.2 Imagen 3 编辑参数

```python
# Inpainting
edit_model.edit_image(
    prompt=prompt,
    edit_mode='inpainting-insert',
    reference_images=[
        RawReferenceImage(image=base_img, reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=mask_img,
            mask_mode='foreground',
            dilation=0.02
        )
    ],
    number_of_images=1,
    safety_filter_level="block_some",
    person_generation="allow_adult"
)
```

### 8.3 Imagen 4 Upscale 参数

```python
upscale_model = ImageGenerationModel.from_pretrained("imagen-4.0-upscale-preview")

upscaled_images = upscale_model.upscale_image(
    image=input_image,
    upscale_factor=2,  # 或 4
    add_watermark=False
)
```

### 8.4 认证配置

由于 Vertex AI 需要 GCP 项目认证（OAuth），不能仅使用 API Key，因此：

1. **后端代理**：所有 Imagen 3/4 调用必须通过后端代理
2. **环境变量**：后端需配置 `GCP_PROJECT_ID` 和服务账号凭证
3. **前端**：Gemini 分割可直接使用 API Key 调用

### 8.5 与现有代码的集成点

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `types.ts` | 修改 | 添加 `'virtual-try-on'` 到 `AppMode`，添加 `VirtualTryOnOptions` |
| `useChat.ts` | 修改 | 添加 `else if (mode === 'virtual-try-on')` 分支 |
| `StudioView.tsx` | 修改 | 添加 `case 'virtual-try-on': return <VirtualTryOnView />` |
| `App.tsx` | 修改 | `handleModeSwitch` 添加 `virtual-try-on` 模型选择逻辑 |
| `handlers/index.ts` | 修改 | 导出 `handleVirtualTryOn` |
| `backend/app/routers/tryon.py` | 新增 | 添加 `/upscale` 端点 |
| `backend/app/services/tryon_service.py` | 修改 | 添加 `upscale_image` 函数 |

### 8.6 UI 组件实现要点

#### 掩码预览叠加

```tsx
// 半透明红色掩码叠加
{showMaskPreview && maskPreviewUrl && (
  <div className="absolute inset-0 pointer-events-none">
    <img 
      src={maskPreviewUrl}
      className="opacity-50 mix-blend-multiply"
      style={{ filter: 'hue-rotate(330deg)' }}  // 红色/粉色
      alt="Mask Preview"
    />
    <div className="absolute top-4 left-4 bg-black/60 text-white px-3 py-1 rounded-full text-xs">
      红色区域将被替换
    </div>
  </div>
)}
```

#### 对比滑块

```tsx
// 左右对比视图
<div className="relative w-full h-full overflow-hidden">
  <img src={originalImageUrl} className="absolute inset-0 w-full h-full object-contain" />
  <div 
    className="absolute inset-0 overflow-hidden"
    style={{ clipPath: `inset(0 ${100 - comparePosition}% 0 0)` }}
  >
    <img src={resultImageUrl} className="absolute inset-0 w-full h-full object-contain" />
  </div>
  <input
    type="range"
    min="0"
    max="100"
    value={comparePosition}
    onChange={(e) => setComparePosition(Number(e.target.value))}
    className="absolute bottom-4 left-1/2 -translate-x-1/2 w-64"
  />
</div>
```

#### 下载功能

```tsx
const handleDownload = (imageUrl: string, filename: string) => {
  const link = document.createElement('a');
  link.href = imageUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// 下载按钮
<button onClick={() => handleDownload(resultImageUrl, 'virtual-tryon-result.png')}>
  下载结果图
</button>
<button onClick={() => handleDownload(originalImageUrl, 'original.png')}>
  下载原图
</button>
<button onClick={() => handleDownload(maskPreviewUrl, 'mask.png')}>
  下载掩码
</button>
```

## 9. 性能优化

### 9.1 图像尺寸优化

```typescript
// 自动调整过大的图像
const MAX_SIZE = 1024;

function resizeImageIfNeeded(image: HTMLImageElement): HTMLCanvasElement {
  if (Math.max(image.width, image.height) <= MAX_SIZE) {
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(image, 0, 0);
    return canvas;
  }
  
  const ratio = MAX_SIZE / Math.max(image.width, image.height);
  const newWidth = Math.floor(image.width * ratio);
  const newHeight = Math.floor(image.height * ratio);
  
  const canvas = document.createElement('canvas');
  canvas.width = newWidth;
  canvas.height = newHeight;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(image, 0, 0, newWidth, newHeight);
  
  return canvas;
}
```

### 9.2 掩码缓存

```typescript
// 缓存生成的掩码，避免重复生成
const maskCache = new Map<string, string>();

async function getCachedMask(
  imageUrl: string,
  targetClothing: string
): Promise<string> {
  const cacheKey = `${imageUrl}-${targetClothing}`;
  
  if (maskCache.has(cacheKey)) {
    return maskCache.get(cacheKey)!;
  }
  
  const maskUrl = await generateMaskPreview(imageUrl, targetClothing, apiKey);
  maskCache.set(cacheKey, maskUrl);
  
  return maskUrl;
}
```

### 9.3 批处理优化

```python
# 后端批处理多个请求
async def batch_edit_images(requests: list[TryOnEditRequest]) -> list[TryOnEditResponse]:
    """批量处理编辑请求"""
    tasks = [edit_image(req) for req in requests]
    return await asyncio.gather(*tasks)
```

## 10. 安全考虑

### 10.1 输入验证

```python
# 验证图像格式和大小
def validate_image(image_base64: str) -> tuple[bool, str]:
    try:
        # 解码 Base64
        image_bytes = base64.b64decode(image_base64)
        
        # 检查文件大小（10MB）
        if len(image_bytes) > 10 * 1024 * 1024:
            return False, "图像文件超过 10MB 限制"
        
        # 检查图像格式
        img = PILImage.open(io.BytesIO(image_bytes))
        if img.format not in ['PNG', 'JPEG']:
            return False, "仅支持 PNG 和 JPEG 格式"
        
        return True, ""
    except Exception as e:
        return False, f"图像验证失败: {str(e)}"
```

### 10.2 API Key 保护

```typescript
// 前端不应暴露 Vertex AI 凭证
// 所有 Imagen 3/4 调用必须通过后端代理

// ✅ 正确：通过后端调用
const result = await fetch('/api/tryon/edit', {
  method: 'POST',
  body: JSON.stringify({ image, mask, prompt })
});

// ❌ 错误：前端直接调用 Vertex AI
// const result = await vertexai.edit_image(...);  // 不要这样做！
```

### 10.3 内容安全过滤

```python
# 后端检测安全过滤错误
try:
    result = edit_model.edit_image(...)
except Exception as e:
    error_msg = str(e)
    if "SAFETY" in error_msg.upper():
        return TryOnEditResponse(
            success=False,
            error="内容被安全过滤器拦截，请修改描述"
        )
```

## 11. 扩展性设计

### 11.1 支持更多编辑模式

```typescript
// 未来可扩展的编辑模式
type EditMode = 
  | 'inpainting-insert'
  | 'inpainting-remove'
  | 'outpainting'
  | 'style-transfer'      // 未来：风格迁移
  | 'color-adjustment'    // 未来：颜色调整
  | 'texture-synthesis';  // 未来：纹理合成
```

### 11.2 支持更多 AI 模型

```typescript
// 模型选择接口
interface ModelConfig {
  segmentationModel: 'gemini-2.5-flash' | 'gemini-2.5-pro' | 'gemini-3-flash-preview';
  editModel: 'imagen-3.0-capability-001' | 'imagen-3.0-fast-001';  // 未来可能有更多
  upscaleModel: 'imagen-4.0-upscale-preview' | 'imagen-4.0-upscale-001';
}
```

### 11.3 工作流编排

```typescript
// 支持自定义工作流
interface Workflow {
  steps: WorkflowStep[];
}

type WorkflowStep = 
  | { type: 'segment'; target: string }
  | { type: 'edit'; prompt: string }
  | { type: 'outpaint'; direction: string; pixels: number }
  | { type: 'upscale'; factor: 2 | 4 };

// 示例：完整工作流
const fullWorkflow: Workflow = {
  steps: [
    { type: 'segment', target: 'upper body clothing' },
    { type: 'edit', prompt: 'A dark green jacket' },
    { type: 'outpaint', direction: 'bottom', pixels: 256 },
    { type: 'upscale', factor: 2 }
  ]
};
```
### Property 5: Upscale 分辨率限制
*For any* 超分辨率操作，输出分辨率（输入分辨率 × 放大倍数）不应超过 17 megapixels。
**Validates: Requirements 3.4.4**

### Property 6: 错误处理完整性
*For any* API 调用失败，系统应返回明确的错误信息，不应抛出未捕获的异常。
**Validates: Requirements 3.8.1, 3.8.2, 3.8.3, 3.8.4**

### Property 8: 掩码预览可见性
*For any* 生成的掩码预览，用户应能清晰看到半透明红色叠加区域，且该区域应与实际编辑区域一致。
**Validates: Requirements 3.5.4**

### Property 9: 掩码预览参数动态调整
*For any* 透明度值 alpha ∈ [0.3, 1.0] 和阈值 threshold ∈ [10, 200]，调整参数后重新生成的掩码预览应反映新的参数设置。
**Validates: Requirements 3.7.3, 3.7.4**

### Property 10: 参数防抖优化
*For any* 连续的参数调整操作，系统应在用户停止调整后的 300ms 内只触发一次掩码重新生成。
**Validates: Requirements 3.7.6**
