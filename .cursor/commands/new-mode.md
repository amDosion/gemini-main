# 创建新的应用模式 (AppMode)

为项目添加一个新的应用模式，包括前后端完整实现。

## 执行步骤

### 1. 后端实现

#### 1.1 添加模式映射
```python
# backend/app/core/mode_method_mapper.py
MODE_METHOD_MAP = {
    # ... 现有映射
    "[new-mode]": "[new_mode]_handler"
}
```

#### 1.2 在服务中实现处理方法
```python
# backend/app/services/gemini/google_service.py (或其他提供商)
async def [new_mode]_handler(
    self,
    request: dict,
    user_id: str
) -> dict:
    """[新模式]处理"""
    prompt = request.get("prompt", "")
    options = request.get("options", {})

    # 实现处理逻辑
    result = await self._call_api(prompt, options)

    return {
        "content": result.get("content"),
        "data": result.get("data")
    }
```

### 2. 前端实现

#### 2.1 添加类型定义
```typescript
// frontend/types/types.ts
export type AppMode =
  | 'chat'
  | 'image-gen'
  // ... 现有模式
  | '[new-mode]'  // 添加新模式
```

#### 2.2 创建视图组件
```typescript
// frontend/components/views/[NewMode]View.tsx
import React, { useState, useCallback } from 'react';
import { useChat } from '../../hooks/useChat';
import { GenViewLayout } from '../common/GenViewLayout';
import type { Message, AppMode } from '../../types/types';

interface [NewMode]ViewProps {
  sessionId: string | null;
  onSessionUpdate: (id: string, messages: Message[]) => void;
}

export const [NewMode]View: React.FC<[NewMode]ViewProps> = ({
  sessionId,
  onSessionUpdate
}) => {
  const { messages, sendMessage, loadingState } = useChat({
    sessionId,
    onSessionUpdate
  });

  const handleSubmit = useCallback(async (
    prompt: string,
    attachments: Attachment[]
  ) => {
    await sendMessage(prompt, attachments);
  }, [sendMessage]);

  return (
    <GenViewLayout
      mode="[new-mode]" as AppMode
      messages={messages}
      loading={loadingState === 'loading'}
      onSubmit={handleSubmit}
    />
  );
};

export default [NewMode]View;
```

#### 2.3 创建控制组件
```typescript
// frontend/controls/modes/[NewMode]Controls.tsx
import React from 'react';
import type { ControlsProps } from '../types';

export const [NewMode]Controls: React.FC<ControlsProps> = ({
  values,
  onChange
}) => {
  return (
    <div className="flex flex-col gap-4">
      {/* 控制选项 */}
    </div>
  );
};

export default [NewMode]Controls;
```

#### 2.4 创建处理器类
```typescript
// frontend/hooks/handlers/[NewMode]HandlerClass.ts
import { BaseHandler } from './BaseHandler';
import type { ExecutionContext, HandlerResult } from './types';

export class [NewMode]HandlerClass extends BaseHandler {
  constructor() {
    super('[new-mode]');
  }

  canHandle(mode: string): boolean {
    return mode === '[new-mode]';
  }

  async process(context: ExecutionContext): Promise<HandlerResult> {
    const { message, attachments, options } = context;

    const response = await fetch('/api/modes/gemini/[new-mode]', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        attachments,
        options
      }),
      signal: context.signal
    });

    return response.json();
  }
}
```

#### 2.5 注册处理器
```typescript
// frontend/hooks/handlers/StrategyRegistry.ts
import { [NewMode]HandlerClass } from './[NewMode]HandlerClass';

registry.register('[new-mode]', new [NewMode]HandlerClass());
```

#### 2.6 添加路由
```typescript
// frontend/App.tsx
<Route path="/[new-mode]" element={<[NewMode]View ... />} />
```

### 3. 添加到模式选择器

更新模式选择器组件，添加新模式的图标和标签。

## 检查清单

- [ ] 后端：mode_method_mapper.py 添加映射
- [ ] 后端：服务类实现处理方法
- [ ] 前端：types.ts 添加 AppMode
- [ ] 前端：创建 View 组件
- [ ] 前端：创建 Controls 组件
- [ ] 前端：创建 Handler 类
- [ ] 前端：注册 Handler
- [ ] 前端：添加路由
- [ ] 前端：更新模式选择器

## 使用示例

```
/new-mode 创建一个代码生成模式，支持根据描述生成代码，包含语言选择和代码风格选项
```
