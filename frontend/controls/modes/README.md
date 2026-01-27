# 模式控件目录

按提供商分组的控件实现。

## 目录结构

```
modes/
├── google/                   # Google 提供商 - 主实现
│   ├── ImageGenControls.tsx  # ★ 主实现
│   ├── ImageEditControls.tsx # ★ 主实现
│   ├── ImageOutpaintControls.tsx
│   ├── VideoGenControls.tsx
│   ├── AudioGenControls.tsx
│   ├── VirtualTryOnControls.tsx
│   ├── ChatControls.tsx
│   ├── PdfExtractControls.tsx
│   ├── DeepResearchControls.tsx
│   ├── MultiAgentControls.tsx
│   └── index.ts
│
├── tongyi/                   # 阿里通义 - 专有实现 + 占位
│   ├── ImageGenControls.tsx  # ★ 专有实现
│   ├── ImageEditControls.tsx # ★ 专有实现
│   ├── ImageOutpaintControls.tsx # ★ 专有实现
│   ├── VideoGenControls.tsx  # → re-export Google
│   ├── ...                   # → re-export Google
│   └── index.ts
│
├── openai/                   # OpenAI - 专有实现 + 占位
│   ├── ImageGenControls.tsx  # ★ 专有实现 (DALL-E)
│   ├── ImageEditControls.tsx # → re-export Google
│   ├── ...                   # → re-export Google
│   └── index.ts
│
├── index.ts                  # 统一导出
└── README.md
```

## 使用方式

### 新架构（推荐）

```tsx
import * as GoogleControls from './modes/google';
import * as TongYiControls from './modes/tongyi';
import * as OpenAIControls from './modes/openai';

// 根据 providerId 选择控件集
const Controls = providerId === 'tongyi' ? TongYiControls : GoogleControls;

// 使用
<Controls.ImageGenControls {...props} />
```

### 向后兼容

```tsx
import { ImageGenControls } from './modes';  // 默认 Google 实现
```

## 添加新提供商

1. 创建 `modes/{provider}/` 目录
2. 实现专有控件或 re-export Google
3. 创建 `index.ts` 导出所有控件
4. 更新 `ModeControlsCoordinator` 的 `getProviderControls`

## 占位文件示例

```typescript
// tongyi/VideoGenControls.tsx
export { VideoGenControls } from '../google/VideoGenControls';
```
