# 模式控件目录

按“通用实现 + provider 差异覆盖”组织。

## 目录结构

```text
modes/
├── google/                   # 通用实现（当前主实现）
├── openai/                   # 仅放 OpenAI 差异实现
│   ├── ImageGenControls.tsx
│   └── index.ts              # 其余直接导出通用实现
├── tongyi/                   # 仅放 TongYi 差异实现
│   ├── ImageGenControls.tsx
│   ├── ImageEditControls.tsx
│   └── index.ts              # 其余直接导出通用实现
├── registry.ts               # providerId + mode 分发注册表
├── index.ts                  # 统一导出
└── README.md
```

## 分发方式

```tsx
import { getProviderControls } from './modes/registry';

const Controls = getProviderControls(providerId);
<Controls.ImageGenControls {...props} />;
```

`registry.ts` 负责：
- providerId 归一化（例如 `google-custom -> google`）
- 合并通用控件与 provider override
- 按 mode 查找对应控件键

## 添加新提供商

1. 在 `modes/{provider}/` 只实现差异控件
2. 在 `registry.ts` 的 `providerOverrides` 增加覆盖项
3. 若有 provider 别名，在 `providerAliases` 增加映射
