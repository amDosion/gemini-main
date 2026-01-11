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
