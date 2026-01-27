# Controls 模式参数控制目录

本目录存放各模式的参数控制 UI 组件。

## 目录结构

| 子目录/文件 | 职责 |
|------------|------|
| `modes/` | 各模式专用的控制组件（按提供商分组） |
| `modes/google/` | Google 主实现 |
| `modes/tongyi/` | TongYi 专有实现 + 占位 |
| `modes/openai/` | OpenAI 专有实现 + 占位 |
| `shared/` | 可复用的原子 UI 组件 |
| `constants/` | 常量定义（比例、风格、分辨率等） |
| `types.ts` | 类型定义 |
| `index.ts` | 统一导出 |

## 架构说明

控件按提供商分组，每个提供商目录包含完整的控件集：
- **专有实现**：该提供商特有的参数和 UI
- **占位文件**：re-export Google 主实现

```
modes/
├── google/         # 主实现（所有控件）
├── tongyi/         # 专有: ImageGen, ImageEdit, ImageOutpaint
└── openai/         # 专有: ImageGen (DALL-E)
```

## 使用方式

通过 `ModeControlsCoordinator` 协调者使用，不直接在业务组件中导入。

```tsx
// 向后兼容：默认使用 Google 实现
import { ImageGenControls } from './controls/modes';

// 新架构：按提供商导入
import * as GoogleControls from './controls/modes/google';
import * as TongYiControls from './controls/modes/tongyi';
```
