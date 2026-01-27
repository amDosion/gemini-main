# 前端 Controls/Modes 目录重构设计文档

## 1. 背景与目标

### 1.1 当前问题

当前 `frontend/controls/modes/` 采用扁平结构，存在以下问题：

1. **内部判断过多** - 单个文件内使用 `if (isGoogle) ... else if (isTongYi) ...` 判断
2. **耦合度高** - 修改一个提供商的逻辑可能影响其他提供商
3. **扩展困难** - 新增提供商需要修改多个现有文件
4. **与后端不一致** - 后端 `backend/app/services/` 已按提供商分目录

### 1.2 目标

- 按提供商分离控件，提高代码隔离性
- 与后端架构保持一致，降低认知负担
- 便于未来扩展新提供商
- 保持 `ModeControlsCoordinator` 的分发职责不变

---

## 2. 现有目录结构

### 2.1 共享 UI 组件（已存在）

`frontend/controls/shared/` - 存放可复用的原子 UI 组件：

```
frontend/controls/shared/
├── ToggleButton.tsx        # 通用开关按钮
├── DropdownSelector.tsx    # 通用下拉选择器
├── SliderControl.tsx       # 通用滑块控制
├── AdvancedToggle.tsx      # 高级设置开关
├── index.ts
└── README.md
```

### 2.2 常量配置（已存在）

`frontend/controls/constants/` - 存放参数常量。

---

## 3. 新目录结构设计

### 3.1 modes 目录重构

```
frontend/controls/modes/
│
├── google/                         # Google 提供商专用
│   ├── ImageGenControls.tsx        # 图片生成 ★ 主实现
│   ├── ImageEditControls.tsx       # 图片编辑 ★ 主实现
│   ├── ImageOutpaintControls.tsx   # 图片扩展 ★ 主实现
│   ├── VideoGenControls.tsx        # 视频生成 ★ 主实现
│   ├── VirtualTryOnControls.tsx    # 虚拟试穿 ★ 主实现
│   ├── ChatControls.tsx            # Chat 模式 ★ 主实现
│   ├── AudioGenControls.tsx        # 音频生成 ★ 主实现
│   ├── PdfExtractControls.tsx      # PDF 提取 ★ 主实现
│   ├── DeepResearchControls.tsx    # 深度研究 ★ 主实现
│   ├── MultiAgentControls.tsx      # 多 Agent ★ 主实现
│   └── index.ts
│
├── tongyi/                         # 阿里通义专用
│   ├── ImageGenControls.tsx        # 图片生成 ★ 专有实现
│   ├── ImageEditControls.tsx       # 图片编辑 ★ 专有实现（后端有 image_edit.py）
│   ├── ImageOutpaintControls.tsx   # 图片扩展 ★ 专有实现（后端有 image_expand.py）
│   ├── VideoGenControls.tsx        # → 导出 google/VideoGenControls（占位）
│   ├── VirtualTryOnControls.tsx    # → 导出 google/VirtualTryOnControls（占位）
│   ├── ChatControls.tsx            # → 导出 google/ChatControls（通用）
│   ├── AudioGenControls.tsx        # → 导出 google/AudioGenControls（占位）
│   ├── PdfExtractControls.tsx      # → 导出 google/PdfExtractControls（占位）
│   ├── DeepResearchControls.tsx    # → 导出 google/DeepResearchControls（占位）
│   ├── MultiAgentControls.tsx      # → 导出 google/MultiAgentControls（占位）
│   └── index.ts
│
├── openai/                         # OpenAI 专用
│   ├── ImageGenControls.tsx        # 图片生成 ★ 专有实现（DALL-E）
│   ├── ImageEditControls.tsx       # → 导出 google/ImageEditControls（占位）
│   ├── ImageOutpaintControls.tsx   # → 导出 google/ImageOutpaintControls（占位）
│   ├── VideoGenControls.tsx        # → 导出 google/VideoGenControls（占位）
│   ├── VirtualTryOnControls.tsx    # → 导出 google/VirtualTryOnControls（占位）
│   ├── ChatControls.tsx            # → 导出 google/ChatControls（通用）
│   ├── AudioGenControls.tsx        # → 导出 google/AudioGenControls（占位）
│   ├── PdfExtractControls.tsx      # → 导出 google/PdfExtractControls（占位）
│   ├── DeepResearchControls.tsx    # → 导出 google/DeepResearchControls（占位）
│   ├── MultiAgentControls.tsx      # → 导出 google/MultiAgentControls（占位）
│   └── index.ts
│
├── README.md                       # 目录说明
└── index.ts                        # 统一导出
```

### 3.2 占位文件示例

对于未实现的功能，使用 re-export 方式：

```typescript
// tongyi/ImageEditControls.tsx
export { ImageEditControls } from '../google/ImageEditControls';
```

### 3.3 与后端目录对照

| 后端 (`backend/app/services/`) | 前端 (`frontend/controls/modes/`) |
|-------------------------------|-----------------------------------|
| `gemini/`                     | `google/`                         |
| `tongyi/`                     | `tongyi/`                         |
| `openai/`                     | `openai/`                         |

---

## 4. 文件迁移计划

### 4.1 迁移映射表

| 原文件 | 目标位置 | 类型 |
|--------|---------|------|
| `ImageGenControls.tsx` | `google/ImageGenControls.tsx` | 主实现 |
| `TongYiImageGenControls.tsx` | `tongyi/ImageGenControls.tsx` | 专有实现 |
| `ImageEditControls.tsx` | `google/ImageEditControls.tsx` | 主实现 |
| `ImageOutpaintControls.tsx` | `google/ImageOutpaintControls.tsx` | 主实现 |
| `VideoGenControls.tsx` | `google/VideoGenControls.tsx` | 主实现 |
| `VirtualTryOnControls.tsx` | `google/VirtualTryOnControls.tsx` | 主实现 |
| `ChatControls.tsx` | `google/ChatControls.tsx` | 主实现 |
| `AudioGenControls.tsx` | `google/AudioGenControls.tsx` | 主实现 |
| `PdfExtractControls.tsx` | `google/PdfExtractControls.tsx` | 主实现 |
| `DeepResearchControls.tsx` | `google/DeepResearchControls.tsx` | 主实现 |
| `MultiAgentControls.tsx` | `google/MultiAgentControls.tsx` | 主实现 |

### 4.2 各提供商实现状态

| 控件 | Google | TongYi | OpenAI | 说明 |
|------|--------|--------|--------|------|
| ImageGenControls | ★ 主实现 | ★ 专有 | ★ 专有 | 各有不同参数 |
| ImageEditControls | ★ 主实现 | ★ 专有 | 占位 | TongYi 有 image_edit.py |
| ImageOutpaintControls | ★ 主实现 | ★ 专有 | 占位 | TongYi 有 image_expand.py |
| VideoGenControls | ★ 主实现 | 占位 | 占位 | 仅 Google 支持 |
| VirtualTryOnControls | ★ 主实现 | 占位 | 占位 | 仅 Google 支持 |
| ChatControls | ★ 主实现 | 通用 | 通用 | 所有提供商通用 |
| AudioGenControls | ★ 主实现 | 占位 | 占位 | 仅 Google TTS |
| PdfExtractControls | ★ 主实现 | 占位 | 占位 | 通用功能 |
| DeepResearchControls | ★ 主实现 | 占位 | 占位 | 仅 Google 支持 |
| MultiAgentControls | ★ 主实现 | 占位 | 占位 | 通用功能 |

---

## 5. ModeControlsCoordinator 分发逻辑

### 5.1 重构后分发方式

```tsx
import * as GoogleControls from '../controls/modes/google';
import * as TongYiControls from '../controls/modes/tongyi';
import * as OpenAIControls from '../controls/modes/openai';

// 获取对应提供商的控件集
const getProviderControls = (providerId: string) => {
  switch (providerId) {
    case 'tongyi': return TongYiControls;
    case 'openai': return OpenAIControls;
    case 'google':
    case 'google-custom':
    default: return GoogleControls;
  }
};

// 分发逻辑
const Controls = getProviderControls(providerId);

switch (mode) {
  case 'chat':
    return <Controls.ChatControls currentModel={currentModel} {...controlProps} />;
  
  case 'image-gen':
    return <Controls.ImageGenControls currentModel={currentModel} controls={controls} />;
  
  case 'image-chat-edit':
  case 'image-mask-edit':
  case 'image-inpainting':
  case 'image-background-edit':
  case 'image-recontext':
    return <Controls.ImageEditControls controls={controls} />;
  
  case 'image-outpainting':
    return <Controls.ImageOutpaintControls controls={controls} />;
  
  case 'video-gen':
    return <Controls.VideoGenControls controls={controls} />;
  
  case 'audio-gen':
    return <Controls.AudioGenControls controls={controls} />;
  
  case 'pdf-extract':
    return <Controls.PdfExtractControls {...controlProps} />;
  
  case 'virtual-try-on':
    return <Controls.VirtualTryOnControls controls={controls} />;
  
  case 'deep-research':
    return <Controls.DeepResearchControls currentModel={currentModel} {...controlProps} />;
  
  case 'multi-agent':
    return <Controls.MultiAgentControls currentModel={currentModel} {...controlProps} />;
  
  default:
    return null;
}
```

---

## 6. 索引文件设计

### 6.1 `google/index.ts`

```typescript
// Google 提供商 - 所有主实现
export { ImageGenControls } from './ImageGenControls';
export { ImageEditControls } from './ImageEditControls';
export { ImageOutpaintControls } from './ImageOutpaintControls';
export { VideoGenControls } from './VideoGenControls';
export { VirtualTryOnControls } from './VirtualTryOnControls';
export { ChatControls } from './ChatControls';
export { AudioGenControls } from './AudioGenControls';
export { PdfExtractControls } from './PdfExtractControls';
export { DeepResearchControls } from './DeepResearchControls';
export { MultiAgentControls } from './MultiAgentControls';
```

### 6.2 `tongyi/index.ts`

```typescript
// TongYi 提供商 - 专有实现 + 占位
export { ImageGenControls } from './ImageGenControls';  // ★ 专有实现
export { ImageEditControls } from './ImageEditControls';  // ★ 专有实现（n, negative_prompt, size, seed, prompt_extend）
export { ImageOutpaintControls } from './ImageOutpaintControls';  // ★ 专有实现
export { VideoGenControls } from './VideoGenControls';  // 占位
export { VirtualTryOnControls } from './VirtualTryOnControls';  // 占位
export { ChatControls } from './ChatControls';  // 通用
export { AudioGenControls } from './AudioGenControls';  // 占位
export { PdfExtractControls } from './PdfExtractControls';  // 占位
export { DeepResearchControls } from './DeepResearchControls';  // 占位
export { MultiAgentControls } from './MultiAgentControls';  // 占位
```

### 6.3 `openai/index.ts`

```typescript
// OpenAI 提供商 - 专有实现 + 占位
export { ImageGenControls } from './ImageGenControls';  // 专有实现
export { ImageEditControls } from './ImageEditControls';  // 占位
// ... 同上
```

### 6.4 根 `modes/index.ts`

```typescript
// 按提供商导出
export * as GoogleControls from './google';
export * as TongYiControls from './tongyi';
export * as OpenAIControls from './openai';
```

---

## 7. 迁移步骤

### Phase 1: 创建目录结构
1. 创建 `modes/google/`、`modes/tongyi/`、`modes/openai/` 目录
2. 创建各目录的 `index.ts`

### Phase 2: 迁移 Google 主实现
1. 移动所有现有控件到 `google/` 目录
2. 从 `ImageGenControls.tsx` 中移除 TongYi/OpenAI 的判断逻辑

### Phase 3: 创建 TongYi 专有实现 + 占位
1. 移动 `TongYiImageGenControls.tsx` → `tongyi/ImageGenControls.tsx`
2. 创建其他占位文件（re-export Google）

### Phase 4: 创建 OpenAI 专有实现 + 占位
1. 从原 `ImageGenControls.tsx` 提取 OpenAI 逻辑到 `openai/ImageGenControls.tsx`
2. 创建其他占位文件（re-export Google）

### Phase 5: 更新 ModeControlsCoordinator
1. 更新导入路径
2. 使用新的分发逻辑

### Phase 6: 清理
1. 删除原目录下的旧文件
2. 更新文档

---

## 8. 优缺点分析

### 8.1 优点

| 优点 | 说明 |
|------|------|
| **隔离性强** | 修改 Google 控件不影响 TongYi |
| **易于扩展** | 新增 Anthropic 只需创建 `anthropic/` 目录 |
| **职责清晰** | 每个文件只负责一个提供商 |
| **前后端一致** | 与 `backend/app/services/` 结构对称 |
| **统一入口** | 每个提供商都有完整的控件导出 |
| **占位机制** | 未实现的功能自动使用 Google 默认 |

### 8.2 缺点

| 缺点 | 缓解措施 |
|------|---------|
| **占位文件较多** | 单行 re-export，维护成本低 |
| **文件数量增加** | 但每个文件更小更专注 |
| **重构工作量** | 分步迁移，保持向后兼容 |

---

## 9. 结论

采用此重构方案，主要收益：
- Google 作为主实现，其他提供商按需覆盖
- 占位机制确保所有提供商有统一的控件入口
- ModeControlsCoordinator 分发逻辑更简洁
- 便于团队协作和代码审查
