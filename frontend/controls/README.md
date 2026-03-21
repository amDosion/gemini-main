# Controls 模式参数控制目录

本目录存放各模式的参数控制 UI 组件。

## 目录结构

| 子目录/文件 | 职责 |
|------------|------|
| `modes/` | 各模式专用的控制组件（通用 + 差异覆盖） |
| `modes/google/` | 通用主实现 |
| `modes/tongyi/` | TongYi 差异实现 |
| `modes/openai/` | OpenAI 差异实现 |
| `modes/registry.ts` | `providerId + mode` 分发注册表 |
| `types.ts` | 类型定义 |
| `modes/index.ts` | 控件统一导出（含向后兼容导出） |

## 架构说明

控件按“通用实现 + provider 差异覆盖”组织：
- **通用实现**：集中维护在 `modes/google/`
- **差异实现**：仅在 provider 目录保留差异控件
- **分发注册**：在 `modes/registry.ts` 中定义覆盖关系

参数数据源：
- **唯一数据源**：后端 `mode_controls_catalog.json`
- **读取方式**：控件中使用 `useModeControlsSchema(providerId, mode, modelId)`
- **策略**：前端不再维护模式参数常量，不做兜底兼容

```
modes/
├── google/         # 主实现（所有控件）
├── tongyi/         # 专有: ImageGen, ImageEdit（其余按需复用）
└── openai/         # 专有: ImageGen (DALL-E)
```

后端 schema 接口：
`GET /api/modes/{provider}/{mode}/controls?model_id=...`

## 使用方式

默认通过 `ModeControlsCoordinator` 使用（各 View 右侧参数面板）。  
`chat` 输入区是例外：`ChatInputArea` 直接使用 `ChatControls`。

```tsx
// 向后兼容：默认使用 Google 实现
import { ImageGenControls } from './controls/modes';

// 推荐：统一通过 providerId 获取控件集
import { getProviderControls } from './controls/modes';
const Controls = getProviderControls(providerId);
```

## 新增/调整比例与分辨率

目标：尽量只改一个文件。

1. 修改 `backend/app/config/mode_controls_catalog.json`
2. 按 `provider -> modes -> {mode}` 补充/调整 `aspect_ratios`、`resolution_tiers`、`resolution_map`
3. 如需模型差异，用 `model_variants` 覆盖
4. 前端控件无需改代码（只要该控件已接入 `useModeControlsSchema`）
