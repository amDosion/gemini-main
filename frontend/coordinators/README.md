# Coordinators 协调者目录

本目录存放协调者组件，负责根据应用状态分发渲染对应的子组件。

## 文件说明

| 文件 | 职责 |
|------|------|
| `ModeControlsCoordinator.tsx` | 根据 `AppMode` 和 `providerId` 分发渲染对应的模式控制组件 |

## 设计原则

- 协调者只负责分发逻辑，不包含业务逻辑
- 协调者使用 provider 分发 + mode 分发两层路由
- 新增模式时只需添加对应 `case` 分支
- provider 差异注册在 `controls/modes/registry.ts`
- 参数选项数据源不在协调者：由各控件通过后端 schema 拉取（单一源）

## ModeControlsCoordinator 分发逻辑

```tsx
// 1) 按 provider 选择控件集（通用 + override）
const Controls = getProviderControls(providerId);

// 2) 按 mode 渲染具体控件
switch (mode) {
  case 'image-gen':
    return <Controls.ImageGenControls {...props} />;
  case 'image-outpainting':
    return <Controls.ImageOutpaintControls {...props} />;
  // ...
}
```

## 新增提供商

1. 在 `controls/modes/{provider}/` 增加差异控件实现
2. 在 `controls/modes/registry.ts` 的 `providerOverrides` 添加覆盖项
3. 如需别名，在 `providerAliases` 添加映射

## 与单一源的关系

- `ModeControlsCoordinator` 只决定“渲染哪个控件组件”
- 每个控件组件内部通过 `useModeControlsSchema(providerId, mode, modelId)` 请求：
  - `GET /api/modes/{provider}/{mode}/controls`
- 后端从 `backend/app/config/mode_controls_catalog.json` 按 `provider + mode (+ model variant)` 返回 schema
- 前端图片控件不再使用本地比例/分辨率兜底；schema 缺失时视为配置错误
