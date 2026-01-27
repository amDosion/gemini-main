# Coordinators 协调者目录

本目录存放协调者组件，负责根据应用状态分发渲染对应的子组件。

## 文件说明

| 文件 | 职责 |
|------|------|
| `ModeControlsCoordinator.tsx` | 根据 AppMode 和 providerId 分发渲染对应的模式控制组件 |

## 设计原则

- 协调者只负责分发逻辑，不包含业务逻辑
- 协调者通过 switch/case 或映射表实现分发
- 新增模式时只需添加对应的 case 分支

## ModeControlsCoordinator 分发逻辑

```tsx
// 按提供商获取控件集
const getProviderControls = (providerId: string) => {
  switch (providerId) {
    case 'tongyi': return TongYiControls;
    case 'openai': return OpenAIControls;
    default: return GoogleControls;
  }
};

// 使用对应提供商的控件
const Controls = getProviderControls(providerId);
return <Controls.ImageGenControls {...props} />;
```

## 新增提供商

1. 在 `controls/modes/{provider}/` 创建控件目录
2. 更新 `getProviderControls` 函数添加新 case
