---
name: frontend-component
description: |
  创建和修改 React 前端组件。适用于：
  - 创建新的 React 组件
  - 添加新的应用模式视图
  - 修改现有组件功能
  - 添加 UI 交互功能
---

# React 组件开发技能

## 适用场景

当用户请求以下任务时，使用此技能：
- 创建新的 React 组件
- 添加新的应用模式（AppMode）视图
- 修改现有组件的功能或样式
- 添加用户界面交互

## 项目结构

```
frontend/components/
├── auth/           # 认证相关组件
├── layout/         # 布局组件 (AppLayout, Header, Sidebar)
├── chat/           # 聊天相关组件 (InputArea, MessageItem)
├── views/          # 视图组件（各模式页面）
├── modals/         # 模态框组件
├── message/        # 消息展示组件
├── multiagent/     # 多代理工作流组件
├── common/         # 通用组件 (LoadingSpinner, Toast)
└── index.ts        # Barrel export
```

## 组件模板

### 标准函数组件

```tsx
import React, { useState, useCallback, useMemo } from 'react';
import type { ComponentProps } from '../types/types';

interface XxxProps {
  // 必需属性
  data: DataType;
  // 可选属性
  className?: string;
  onAction?: (value: string) => void;
}

export const Xxx: React.FC<XxxProps> = ({
  data,
  className = '',
  onAction
}) => {
  // 1. 状态声明
  const [loading, setLoading] = useState(false);

  // 2. 计算属性
  const processedData = useMemo(() => {
    return data.map(item => transform(item));
  }, [data]);

  // 3. 事件处理
  const handleClick = useCallback(() => {
    onAction?.(data.id);
  }, [onAction, data.id]);

  // 4. 条件渲染
  if (loading) {
    return <LoadingSpinner />;
  }

  // 5. 主渲染
  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      {/* 内容 */}
    </div>
  );
};

export default React.memo(Xxx);
```

### 视图组件模板 (views/)

```tsx
import React, { useState, useCallback } from 'react';
import { useChat } from '../../hooks/useChat';
import { useSettings } from '../../hooks/useSettings';
import { GenViewLayout } from '../common/GenViewLayout';
import type { AppMode, Message } from '../../types/types';

interface XxxViewProps {
  sessionId: string | null;
  onSessionUpdate: (id: string, messages: Message[]) => void;
}

export const XxxView: React.FC<XxxViewProps> = ({
  sessionId,
  onSessionUpdate
}) => {
  const { settings } = useSettings();
  const { messages, sendMessage, loadingState } = useChat({
    sessionId,
    onSessionUpdate
  });

  const handleSubmit = useCallback(async (prompt: string, attachments: Attachment[]) => {
    await sendMessage(prompt, attachments);
  }, [sendMessage]);

  return (
    <GenViewLayout
      mode="xxx" as AppMode
      messages={messages}
      loading={loadingState === 'loading'}
      onSubmit={handleSubmit}
    />
  );
};

export default XxxView;
```

## 样式规范

### Tailwind CSS 常用类

```tsx
// 容器
<div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">

// 按钮
<button className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors disabled:opacity-50">

// 输入框
<input className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500">

// 弹性布局
<div className="flex items-center justify-between gap-4">

// 响应式
<div className="w-full md:w-1/2 lg:w-1/3">
```

## 开发步骤

1. **确定组件位置**：根据功能选择合适的目录
2. **定义 Props 接口**：使用 TypeScript 接口定义属性
3. **实现组件逻辑**：按照模板结构编写代码
4. **添加样式**：使用 Tailwind CSS 原子类
5. **导出组件**：在 index.ts 中添加导出
6. **测试组件**：确保功能正常

## 注意事项

- 使用 `useCallback` 包装事件处理函数
- 使用 `useMemo` 缓存计算结果
- 使用 `React.memo` 优化纯展示组件
- Props 使用 `XxxProps` 命名约定
- 事件处理函数使用 `handle` 前缀
