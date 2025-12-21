# Design Document

## Overview

本设计文档描述模式参数控制组件的重构方案。核心目标是将臃肿的 `GenerationControls.tsx` 拆分为独立的模式控制组件，引入协调者模式统一管理，并将状态逻辑抽离到专用 Hook 中。

## Architecture

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              InputArea.tsx                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  useControlsState()  →  返回所有控制参数状态                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  ModeControlsCoordinator                                                 ││
│  │  └─ switch(mode)                                                         ││
│  │     ├─ 'chat'             → <ChatControls />                             ││
│  │     ├─ 'image-gen'        → <ImageGenControls />                         ││
│  │     ├─ 'image-edit'       → <ImageEditControls />                        ││
│  │     ├─ 'image-outpainting'→ <ImageOutpaintControls />                    ││
│  │     ├─ 'video-gen'        → <VideoGenControls />                         ││
│  │     ├─ 'audio-gen'        → <AudioGenControls />                         ││
│  │     ├─ 'pdf-extract'      → <PdfExtractControls />                       ││
│  │     └─ 'virtual-try-on'   → <VirtualTryOnControls />                     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
frontend/
├── hooks/
│   ├── useControlsState.ts          // 控制参数状态管理 Hook
│   └── ...
│
├── coordinators/                     // 协调者目录
│   ├── README.md                     // 目录说明文档
│   ├── index.ts                      // 统一导出
│   └── ModeControlsCoordinator.tsx   // 模式参数控制协调者
│
└── controls/                         // 模式参数控制 UI
    ├── README.md                     // 目录说明文档
    ├── index.ts                      // 统一导出
    ├── types.ts                      // 类型定义
    ├── constants.ts                  // 常量（比例、风格等）
    │
    ├── modes/                        // 各模式控制组件
    │   ├── README.md                 // 目录说明文档
    │   ├── ChatControls.tsx
    │   ├── ImageGenControls.tsx
    │   ├── ImageEditControls.tsx
    │   ├── ImageOutpaintControls.tsx
    │   ├── VideoGenControls.tsx
    │   ├── AudioGenControls.tsx
    │   ├── VirtualTryOnControls.tsx
    │   └── PdfExtractControls.tsx
    │
    └── shared/                       // 可复用原子组件
        ├── README.md                 // 目录说明文档
        ├── ToggleButton.tsx
        ├── DropdownSelector.tsx
        ├── SliderControl.tsx
        └── AdvancedToggle.tsx
```

### 目录说明文档

#### `frontend/coordinators/README.md`

```markdown
# Coordinators 协调者目录

本目录存放协调者组件，负责根据应用状态分发渲染对应的子组件。

## 文件说明

| 文件 | 职责 |
|------|------|
| `ModeControlsCoordinator.tsx` | 根据 AppMode 分发渲染对应的模式控制组件 |

## 设计原则

- 协调者只负责分发逻辑，不包含业务逻辑
- 协调者通过 switch/case 或映射表实现分发
- 新增模式时只需添加对应的 case 分支
```

#### `frontend/controls/README.md`

```markdown
# Controls 模式参数控制目录

本目录存放各模式的参数控制 UI 组件。

## 目录结构

| 子目录/文件 | 职责 |
|------------|------|
| `modes/` | 各模式专用的控制组件 |
| `shared/` | 可复用的原子 UI 组件 |
| `types.ts` | 类型定义 |
| `constants.ts` | 常量定义（比例、风格等） |
| `index.ts` | 统一导出 |

## 使用方式

通过 ModeControlsCoordinator 协调者使用，不直接在业务组件中导入。
```

#### `frontend/controls/modes/README.md`

```markdown
# Modes 模式控制组件目录

本目录存放各 AppMode 对应的控制组件。

## 文件说明

| 文件 | 对应模式 | 控制项 |
|------|---------|--------|
| `ChatControls.tsx` | chat | Search, Browse, RAG, Cache, Reasoning, URL Context, Code |
| `ImageGenControls.tsx` | image-gen | Style, Count, Aspect Ratio, Resolution, Advanced |
| `ImageEditControls.tsx` | image-edit | Try-On, Aspect Ratio, Resolution, Advanced |
| `ImageOutpaintControls.tsx` | image-outpainting | Scale/Offset Mode, Parameters |
| `VideoGenControls.tsx` | video-gen | Aspect Ratio, Resolution |
| `AudioGenControls.tsx` | audio-gen | Voice |
| `VirtualTryOnControls.tsx` | virtual-try-on | Clothing Type, Mask Preview |
| `PdfExtractControls.tsx` | pdf-extract | Template, Advanced |

## 新增模式

1. 在本目录创建 `XxxControls.tsx`
2. 在 `../index.ts` 中导出
3. 在 `ModeControlsCoordinator` 中添加 case 分支
```

#### `frontend/controls/shared/README.md`

```markdown
# Shared 共享组件目录

本目录存放可复用的原子 UI 组件。

## 文件说明

| 文件 | 职责 |
|------|------|
| `ToggleButton.tsx` | 通用开关按钮（如 Search、Thinking 等） |
| `DropdownSelector.tsx` | 通用下拉选择器（如 Style、Aspect Ratio 等） |
| `SliderControl.tsx` | 通用滑块控制（如 Scale Factor 等） |
| `AdvancedToggle.tsx` | 高级设置开关按钮 |

## 设计原则

- 组件应保持通用性，不包含模式特定逻辑
- 通过 props 控制样式和行为
- 保持一致的视觉风格
```

## Components and Interfaces

### ModeControlsCoordinator

**文件路径**：`frontend/coordinators/ModeControlsCoordinator.tsx`

```typescript
import React from 'react';
import { AppMode, ModelConfig } from '../../types';
import { 
  ChatControls,
  ImageGenControls,
  ImageEditControls,
  ImageOutpaintControls,
  VideoGenControls,
  AudioGenControls,
  VirtualTryOnControls,
  PdfExtractControls
} from '../controls';

interface ModeControlsCoordinatorProps {
  mode: AppMode;
  providerId: string;
  currentModel?: ModelConfig;
  // 其余控制参数通过 rest props 传递
  [key: string]: any;
}

/**
 * 模式控制协调者
 * 根据当前 mode 分发渲染对应的控制组件
 */
export const ModeControlsCoordinator: React.FC<ModeControlsCoordinatorProps> = ({ 
  mode, 
  providerId,
  currentModel,
  ...controlProps 
}) => {
  switch (mode) {
    case 'chat':
      return <ChatControls currentModel={currentModel} {...controlProps} />;
    case 'image-gen':
      return <ImageGenControls providerId={providerId} {...controlProps} />;
    case 'image-edit':
      return <ImageEditControls providerId={providerId} {...controlProps} />;
    case 'image-outpainting':
      return <ImageOutpaintControls {...controlProps} />;
    case 'video-gen':
      return <VideoGenControls providerId={providerId} {...controlProps} />;
    case 'audio-gen':
      return <AudioGenControls {...controlProps} />;
    case 'virtual-try-on':
      return <VirtualTryOnControls {...controlProps} />;
    case 'pdf-extract':
      return <PdfExtractControls {...controlProps} />;
    default:
      return null;
  }
};
```

### useControlsState Hook

**文件路径**：`frontend/hooks/useControlsState.ts`

```typescript
export interface ControlsState {
  // Chat Controls
  enableSearch: boolean;
  setEnableSearch: (v: boolean) => void;
  enableThinking: boolean;
  setEnableThinking: (v: boolean) => void;
  enableCodeExecution: boolean;
  setEnableCodeExecution: (v: boolean) => void;
  enableUrlContext: boolean;
  setEnableUrlContext: (v: boolean) => void;
  enableBrowser: boolean;
  setEnableBrowser: (v: boolean) => void;
  enableRAG: boolean;
  setEnableRAG: (v: boolean) => void;
  googleCacheMode: 'none' | 'exact' | 'semantic';
  setGoogleCacheMode: (v: 'none' | 'exact' | 'semantic') => void;

  // Generation Controls
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  numberOfImages: number;
  setNumberOfImages: (v: number) => void;
  style: string;
  setStyle: (v: string) => void;
  
  // Advanced Settings
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  negativePrompt: string;
  setNegativePrompt: (v: string) => void;
  seed: number;
  setSeed: (v: number) => void;
  loraConfig: LoraConfig;
  setLoraConfig: (v: LoraConfig) => void;

  // Out-Painting
  outPaintingMode: 'scale' | 'offset';
  setOutPaintingMode: (v: 'scale' | 'offset') => void;
  scaleFactor: number;
  setScaleFactor: (v: number) => void;
  offsetPixels: { left: number; right: number; top: number; bottom: number };
  setOffsetPixels: (v: typeof offsetPixels) => void;

  // Audio
  voice: string;
  setVoice: (v: string) => void;

  // PDF
  pdfTemplate: string;
  setPdfTemplate: (v: string) => void;
  pdfAdditionalInstructions: string;
  setPdfAdditionalInstructions: (v: string) => void;

  // Virtual Try-On
  showTryOn: boolean;
  setShowTryOn: (v: boolean) => void;
  tryOnTarget: string;
  setTryOnTarget: (v: string) => void;
}

export function useControlsState(mode: AppMode): ControlsState;
```

### Mode Control Components

每个模式控制组件接收 `ControlsState` 的子集作为 props：

```typescript
// ChatControls
interface ChatControlsProps {
  currentModel?: ModelConfig;
  enableSearch: boolean;
  setEnableSearch: (v: boolean) => void;
  // ... 其他 chat 相关状态
}

// ImageGenControls
interface ImageGenControlsProps {
  providerId: string;
  style: string;
  setStyle: (v: string) => void;
  numberOfImages: number;
  setNumberOfImages: (v: number) => void;
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}
```

### Shared Components

```typescript
// ToggleButton
interface ToggleButtonProps {
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
  icon: React.ReactNode;
  label: string;
  activeColor?: string;
  title?: string;
}

// DropdownSelector
interface DropdownSelectorProps<T> {
  value: T;
  onChange: (v: T) => void;
  options: { label: string; value: T }[];
  icon?: React.ReactNode;
  iconColor?: string;
  placeholder?: string;
}

// SliderControl
interface SliderControlProps {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
  formatValue?: (v: number) => string;
}
```

## Data Models

### 常量定义

**文件路径**：`frontend/controls/constants.ts`

```typescript
export const ASPECT_RATIOS = {
  GEN: [
    { label: "1:1 Square", value: "1:1" },
    { label: "3:4 Portrait", value: "3:4" },
    { label: "4:3 Landscape", value: "4:3" },
    { label: "9:16 Portrait", value: "9:16" },
    { label: "16:9 Landscape", value: "16:9" },
  ],
  GOOGLE_EDIT: [
    // 扩展的比例选项
  ],
  OPENAI: [
    { label: "1:1 Square", value: "1:1" },
    { label: "Portrait (1024x1792)", value: "9:16" },
    { label: "Landscape (1792x1024)", value: "16:9" },
  ],
  VIDEO: [
    { label: "16:9 Landscape", value: "16:9" },
    { label: "9:16 Portrait", value: "9:16" },
  ],
};

export const STYLES = [
  { label: "No Style", value: "None" },
  { label: "Photorealistic", value: "Photorealistic" },
  { label: "Anime", value: "Anime" },
  // ...
];

export const VOICES = [
  { label: "Puck", value: "Puck" },
  // ...
];
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Mode-to-Component Mapping Correctness

*For any* valid AppMode value, the ModeControlsCoordinator shall render exactly one corresponding control component, and the component type shall match the mode.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**

### Property 2: State Update Consistency

*For any* control parameter setter function call with a valid value, the corresponding state value shall be updated to the new value immediately.

**Validates: Requirements 2.2**

### Property 3: Mode Change Reset Behavior

*For any* mode change from mode A to mode B, the mode-specific parameters for mode B shall be reset to their default values.

**Validates: Requirements 2.3**

## Error Handling

| 错误场景 | 处理方式 |
|---------|---------|
| 未知的 AppMode 值 | ModeControlsCoordinator 返回 null，不渲染任何控件 |
| 无效的参数值 | 各控件组件内部校验，使用默认值替代 |
| 缺少必要的 props | TypeScript 编译时检查，运行时使用可选链保护 |

## Testing Strategy

### 单元测试

- 测试 `useControlsState` Hook 的状态初始化和更新逻辑
- 测试各模式控件组件的渲染和交互
- 测试共享组件的行为

### 属性测试

使用 `fast-check` 库进行属性测试：

- **Property 1 测试**：生成随机 AppMode 值，验证协调者渲染正确的组件
- **Property 2 测试**：生成随机状态值，验证 setter 正确更新状态
- **Property 3 测试**：生成随机模式切换序列，验证参数重置行为

### 集成测试

- 测试 InputArea 与 ModeControlsCoordinator 的集成
- 测试模式切换时的状态同步
- 测试各模式控件的完整交互流程
