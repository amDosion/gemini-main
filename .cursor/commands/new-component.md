# 创建新的 React 组件

根据用户描述创建一个新的 React 组件。

## 执行步骤

1. **确定组件类型和位置**
   - 视图组件 → `frontend/components/views/`
   - 布局组件 → `frontend/components/layout/`
   - 聊天组件 → `frontend/components/chat/`
   - 模态框 → `frontend/components/modals/`
   - 通用组件 → `frontend/components/common/`

2. **创建组件文件**
   使用以下模板：

```tsx
import React, { useState, useCallback, useMemo } from 'react';

interface [ComponentName]Props {
  // 定义 props
  className?: string;
}

export const [ComponentName]: React.FC<[ComponentName]Props> = ({
  className = ''
}) => {
  // 状态
  const [loading, setLoading] = useState(false);

  // 事件处理
  const handleAction = useCallback(() => {
    // 处理逻辑
  }, []);

  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      {/* 组件内容 */}
    </div>
  );
};

export default React.memo([ComponentName]);
```

3. **在 index.ts 中导出**
   ```typescript
   export { [ComponentName] } from './[ComponentName]';
   ```

4. **添加必要的样式**（使用 Tailwind CSS）

## 规范要求

- 使用函数式组件 + Hooks
- Props 接口命名：`[ComponentName]Props`
- 事件处理函数使用 `handle` 前缀
- 使用 `useCallback` 包装事件处理函数
- 使用 `React.memo` 优化纯展示组件
- 使用 Tailwind CSS 原子类

## 使用示例

```
/new-component 创建一个图片对比滑块组件，支持左右拖动对比两张图片
```
