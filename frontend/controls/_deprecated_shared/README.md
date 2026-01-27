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
