# Image Outpainting 功能设计文档

## 1. 概述

本文档描述 Image Outpainting（画布扩展）功能的技术设计方案。该功能基于 Vertex AI Imagen 3 的图像编辑能力，实现图像边界的扩展和内容生成。

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  App.tsx                                                                     │
│  └─ handleModeSwitch('image-outpainting')                                   │
│     └─ setAppMode('image-outpainting')                                      │
│                                                                              │
│  StudioView.tsx                                                              │
│  └─ switch(mode)                                                             │
│     └─ case 'image-outpainting': return <ImageExpandView {...props} />      │
│                                                                              │
│  ImageExpandView.tsx                                                         │
│  └─ 用户上传图片 → 选择方向 → 设置像素数 → 输入描述 → 点击生成              │
│  └─ onSend(prompt, options, attachments, 'image-outpainting')               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据处理层                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  useChat.ts                                                                  │
│  └─ sendMessage()                                                            │
│     └─ if (mode === 'image-outpainting')                                    │
│        └─ const result = await handleImageExpand(attachments, context)      │
│        └─ 更新 UI 显示                                                       │
│        └─ 提交上传任务到 Redis 队列                                          │
│                                                                              │
│  handlers/imageExpandHandler.ts                                              │
│  └─ handleImageExpand(text, attachments, context)                           │
│     └─ 调用 imageExpandService                                              │
│     └─ 下载结果图创建 Blob URL                                               │
│     └─ 返回 HandlerResult                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              服务层                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  services/providers/google/media/image-expand.ts                             │
│  └─ imageExpand(referenceImage, options)                                    │
│     ├─ Step 1: 计算新画布尺寸                                                │
│     │          └─ 根据方向和像素数计算                                        │
│     │                                                                        │
│     ├─ Step 2: 生成扩展掩码                                                  │
│     │          └─ 创建扩展区域的掩码                                          │
│     │                                                                        │
│     └─ Step 3: 调用后端 /api/image/outpaint                                 │
│                └─ 发送 image + mask + prompt + direction                    │
│                └─ 返回扩展后的图片                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              后端层                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  backend/app/routers/image.py                                                │
│  └─ POST /api/image/outpaint                                                 │
│     └─ 接收 image, direction, expand_pixels, prompt                         │
│     └─ 生成扩展掩码                                                          │
│     └─ 调用 Imagen 3 outpainting 模式                                       │
│     └─ 返回扩展后的图片                                                      │
│                                                                              │
│  backend/app/services/image_service.py                                       │
│  └─ outpaint_image(image, direction, expand_pixels, prompt)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. 组件与接口

### 3.1 类型定义扩展

**文件路径**：`types.ts`

```typescript
// 1. AppMode 已包含 'image-outpainting'
export type AppMode = 
  | 'chat' 
  | 'image-gen' 
  | 'image-edit' 
  | 'video-gen' 
  | 'audio-gen' 
  | 'image-outpainting'  // 已存在
  | 'pdf-extract'
  | 'virtual-try-on';

// 2. 新增 ImageOutpaintingOptions
export interface ImageOutpaintingOptions {
  direction: 'bottom' | 'top' | 'left' | 'right' | 'all';
  expandPixels?: number;  // 扩展像素数，默认 256
  expandRatio?: number;   // 扩展比例（相对于原图尺寸）
  prompt?: string;        // 内容描述（可选）
  dilation?: number;      // 掩码膨胀系数，默认 0.03
}

// 3. 扩展 ChatOptions
export interface ChatOptions {
  // ... 现有字段 ...
  imageOutpaintingOptions?: ImageOutpaintingOptions;
}
```

### 3.2 Handler 接口

**文件路径**：`frontend/hooks/handlers/imageExpandHandler.ts`

```typescript
import { HandlerContext, HandlerResult } from './types';
import { Attachment } from '../../../types';

export interface ImageExpandHandlerResult extends HandlerResult {
  uploadTask?: Promise<{ 
    dbAttachments: Attachment[]; 
    dbUserAttachments: Attachment[] 
  }>;
}

/**
 * 处理 Image Outpainting 模式
 * 
 * @param text - 内容描述文本（可选）
 * @param attachments - 附件列表（需包含原图）
 * @param context - 处理器上下文
 * @returns 生成结果
 */
export async function handleImageExpand(
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<ImageExpandHandlerResult>;
```

### 3.3 前端服务接口

**文件路径**：`frontend/services/providers/google/media/image-expand.ts`

```typescript
import { Attachment, ChatOptions } from "../../../../../types";
import { ImageGenerationResult } from "../../interfaces";

// ========== 类型定义 ==========

export interface ImageExpandOptions {
  direction: 'bottom' | 'top' | 'left' | 'right' | 'all';
  expandPixels?: number;  // 扩展像素数
  expandRatio?: number;   // 扩展比例
  prompt?: string;        // 内容描述
  dilation?: number;      // 掩码膨胀系数
}

// ========== 主函数 ==========

/**
 * Image Outpainting 主函数
 * 扩展图像边界并生成内容
 */
export async function imageExpand(
  referenceImage: Attachment,
  options: ImageExpandOptions
): Promise<ImageGenerationResult>;

// ========== 辅助函数 ==========

/**
 * 计算扩展后的画布尺寸
 */
export function calculateExpandedSize(
  originalWidth: number,
  originalHeight: number,
  direction: string,
  expandPixels: number
): { width: number; height: number };

/**
 * 生成扩展掩码
 * 返回 Base64 编码的掩码图像
 */
export function generateExpansionMask(
  originalWidth: number,
  originalHeight: number,
  direction: string,
  expandPixels: number
): string;

/**
 * 调用后端 Outpainting API
 */
export async function outpaintImage(
  imageBase64: string,
  direction: 'bottom' | 'top' | 'left' | 'right' | 'all',
  expandPixels: number,
  prompt?: string,
  dilation?: number
): Promise<ImageGenerationResult>;
```

### 3.4 后端 API 接口

**文件路径**：`backend/app/routers/image.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

router = APIRouter(prefix="/api/image", tags=["image"])

# ========== Outpainting 接口 ==========

class OutpaintRequest(BaseModel):
    image: str  # Base64 编码的原图
    direction: Literal['bottom', 'top', 'left', 'right', 'all']  # 扩展方向
    expand_pixels: int  # 扩展像素数
    prompt: Optional[str] = None  # 扩展内容描述
    dilation: float = 0.03  # 膨胀系数

class OutpaintResponse(BaseModel):
    success: bool
    image: Optional[str] = None  # Base64 编码的扩展后图像
    mimeType: str = "image/png"
    new_width: int  # 新图像宽度
    new_height: int  # 新图像高度
    error: Optional[str] = None

@router.post("/outpaint", response_model=OutpaintResponse)
async def outpaint_image(request: OutpaintRequest) -> OutpaintResponse:
    """使用 Imagen 3 进行画布扩展"""
    pass
```

### 3.5 UI 组件接口

**文件路径**：`frontend/components/views/ImageExpandView.tsx`

```typescript
interface ImageExpandViewProps {
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

## 4. 数据模型

### 4.1 Outpainting 掩码生成

```python
def create_outpainting_mask(
    original_size: tuple,
    direction: str,
    expand_pixels: int
) -> tuple[np.ndarray, tuple]:
    """
    创建 Outpainting 掩码
    
    Args:
        original_size: (width, height) 原始图像尺寸
        direction: 'bottom', 'top', 'left', 'right', 'all'
        expand_pixels: 扩展的像素数
    
    Returns:
        (mask, new_size)
    """
    width, height = original_size
    
    if direction == 'bottom':
        new_size = (width, height + expand_pixels)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[height:, :] = 255  # 底部扩展区域
    
    elif direction == 'top':
        new_size = (width, height + expand_pixels)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:expand_pixels, :] = 255  # 顶部扩展区域
    
    elif direction == 'left':
        new_size = (width + expand_pixels, height)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:, :expand_pixels] = 255  # 左侧扩展区域
    
    elif direction == 'right':
        new_size = (width + expand_pixels, height)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:, width:] = 255  # 右侧扩展区域
    
    elif direction == 'all':
        new_size = (width + 2 * expand_pixels, height + 2 * expand_pixels)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        # 中心区域为原图（黑色），四周为扩展区域（白色）
        mask[:expand_pixels, :] = 255  # 顶部
        mask[-expand_pixels:, :] = 255  # 底部
        mask[:, :expand_pixels] = 255  # 左侧
        mask[:, -expand_pixels:] = 255  # 右侧
    
    return mask, new_size
```

### 4.2 画布尺寸计算

```typescript
function calculateExpandedSize(
  originalWidth: number,
  originalHeight: number,
  direction: string,
  expandPixels: number
): { width: number; height: number } {
  switch (direction) {
    case 'bottom':
    case 'top':
      return { width: originalWidth, height: originalHeight + expandPixels };
    
    case 'left':
    case 'right':
      return { width: originalWidth + expandPixels, height: originalHeight };
    
    case 'all':
      return { 
        width: originalWidth + 2 * expandPixels, 
        height: originalHeight + 2 * expandPixels 
      };
    
    default:
      return { width: originalWidth, height: originalHeight };
  }
}
```

## 5. 正确性属性

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 画布尺寸正确性
*For any* 扩展操作，扩展后的画布尺寸应等于原图尺寸加上指定的扩展像素数。
**Validates: Requirements 3.3.1**

### Property 2: 掩码区域正确性
*For any* 扩展方向，生成的掩码应正确标识扩展区域（白色）和原图区域（黑色）。
**Validates: Requirements 3.4.1**

### Property 3: 扩展内容连贯性
*For any* 画布扩展操作，扩展区域的内容应与原图在风格、光照、色调上保持一致。
**Validates: Requirements 3.4.2**

### Property 4: 边缘融合自然性
*For any* 扩展操作，扩展内容与原图边缘应自然融合，无明显接缝。
**Validates: Requirements 3.4.3**

### Property 5: 错误处理完整性
*For any* API 调用失败，系统应返回明确的错误信息，不应抛出未捕获的异常。
**Validates: Requirements 3.7.1, 3.7.2, 3.7.3, 3.7.4**

## 6. 错误处理

### 6.1 Outpainting 错误

| 错误类型 | 错误码 | 处理方式 |
|---------|--------|---------|
| 扩展比例过大 | `EXPAND_TOO_LARGE` | 提示用户减小扩展像素数 |
| 掩码生成失败 | `MASK_GENERATION_ERROR` | 记录错误并提示用户 |
| 画布创建失败 | `CANVAS_ERROR` | 提示用户检查图像格式 |
| Vertex AI 认证失败 | `AUTH_ERROR` | 提示用户检查 GCP 配置 |
| 安全过滤触发 | `SAFETY_FILTER` | 提示用户修改 prompt |
| API 配额超限 | `QUOTA_EXCEEDED` | 提示用户稍后重试 |

## 7. 测试策略

### 7.1 单元测试

- 测试 `calculateExpandedSize` 函数的尺寸计算
- 测试 `generateExpansionMask` 函数的掩码生成
- 测试 `create_outpainting_mask` 函数的各个方向
- 测试错误处理分支

### 7.2 属性测试

- **Property 1 测试**：生成随机的图像尺寸和扩展像素数，验证画布尺寸计算正确性
- **Property 2 测试**：生成随机的扩展参数，验证掩码区域标识正确性
- **Property 5 测试**：模拟各种 API 错误，验证错误处理逻辑

### 7.3 集成测试

- 测试完整的扩展流程（上传 → 选择方向 → 生成）
- 测试各个方向的扩展效果
- 测试边界情况（最小/最大扩展像素数）
- 测试有/无内容描述的扩展

### 7.4 UI 测试

- 测试方向选择控件
- 测试像素数输入验证
- 测试结果展示
- 测试下载功能
- 测试错误提示显示

## 8. 实现注意事项

### 8.1 Imagen 3 Outpainting 参数

```python
# Outpainting
edit_model.edit_image(
    prompt=prompt or "Extend the image naturally",
    edit_mode='outpainting',
    reference_images=[
        RawReferenceImage(image=expanded_canvas, reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=expand_mask,
            mask_mode='background',  # 注意：outpainting 使用 background
            dilation=0.03
        )
    ],
    number_of_images=1,
    person_generation="allow_adult"
)
```

### 8.2 认证配置

由于 Vertex AI 需要 GCP 项目认证（OAuth），不能仅使用 API Key，因此：

1. **后端代理**：所有 Imagen 3 调用必须通过后端代理
2. **环境变量**：后端需配置 `GCP_PROJECT_ID` 和服务账号凭证

### 8.3 与现有代码的集成点

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `types.ts` | 修改 | 添加 `ImageOutpaintingOptions` |
| `useChat.ts` | 修改 | 添加 `else if (mode === 'image-outpainting')` 分支 |
| `StudioView.tsx` | 修改 | 添加 `case 'image-outpainting': return <ImageExpandView />` |
| `handlers/imageExpandHandler.ts` | 新增/修改 | 实现 Handler 逻辑 |
| `backend/app/routers/image.py` | 修改 | 添加 `/outpaint` 端点 |
| `backend/app/services/image_service.py` | 修改 | 添加 `outpaint_image` 函数 |

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

### 9.2 扩展参数验证

```typescript
// 验证扩展参数是否合理
function validateExpandParams(
  originalWidth: number,
  originalHeight: number,
  expandPixels: number
): { valid: boolean; error?: string } {
  const MAX_EXPAND_RATIO = 2.0;  // 最大扩展比例
  
  const expandRatio = expandPixels / Math.min(originalWidth, originalHeight);
  
  if (expandRatio > MAX_EXPAND_RATIO) {
    return {
      valid: false,
      error: `扩展比例过大（${expandRatio.toFixed(2)}），建议不超过 ${MAX_EXPAND_RATIO}`
    };
  }
  
  return { valid: true };
}
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
// 所有 Imagen 3 调用必须通过后端代理

// ✅ 正确：通过后端调用
const result = await fetch('/api/image/outpaint', {
  method: 'POST',
  body: JSON.stringify({ image, direction, expand_pixels, prompt })
});

// ❌ 错误：前端直接调用 Vertex AI
// const result = await vertexai.edit_image(...);  // 不要这样做！
```

## 11. 扩展性设计

### 11.1 支持更多扩展模式

```typescript
// 未来可扩展的扩展模式
type ExpansionMode = 
  | 'outpainting'         // 当前：画布扩展
  | 'smart-crop'          // 未来：智能裁剪
  | 'auto-complete'       // 未来：自动补全
  | 'perspective-extend'; // 未来：透视扩展
```

### 11.2 支持更多 AI 模型

```typescript
// 模型选择接口
interface ModelConfig {
  expandModel: 'imagen-3.0-capability-001' | 'imagen-3.0-fast-001';  // 未来可能有更多
}
```
