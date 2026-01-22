---
name: frontend-hook
description: |
  创建和修改 React 自定义 Hook。适用于：
  - 创建新的自定义 Hook
  - 添加新的请求处理器类
  - 修改状态管理逻辑
  - 实现业务逻辑封装
---

# React Hook 开发技能

## 适用场景

当用户请求以下任务时，使用此技能：
- 创建新的自定义 Hook
- 添加新的请求处理器（Handler）
- 修改状态管理逻辑
- 封装可复用的业务逻辑

## 项目结构

```
frontend/hooks/
├── handlers/           # 请求处理器类
│   ├── BaseHandler.ts
│   ├── ChatHandlerClass.ts
│   ├── ImageGenHandlerClass.ts
│   ├── StrategyRegistry.ts
│   ├── attachmentUtils.ts
│   └── types.ts
├── useChat.ts          # 聊天核心逻辑
├── useSettings.ts      # 设置管理
├── useSessions.ts      # 会话管理
├── useModels.ts        # 模型管理
├── useAuth.ts          # 认证状态
├── useImageHandlers.ts # 图像处理
├── useDeepResearch.ts  # 深度研究
└── useToast.ts         # 通知提示
```

## Hook 模板

### 标准自定义 Hook

```tsx
import { useState, useCallback, useEffect, useRef } from 'react';

// 配置选项接口
export interface UseXxxOptions {
  enabled?: boolean;
  onSuccess?: (data: DataType) => void;
  onError?: (error: Error) => void;
}

// 返回值接口
export interface UseXxxReturn {
  data: DataType | null;
  loading: boolean;
  error: Error | null;
  execute: (params: ParamsType) => Promise<void>;
  reset: () => void;
}

export const useXxx = (options: UseXxxOptions = {}): UseXxxReturn => {
  const { enabled = true, onSuccess, onError } = options;

  // 状态
  const [data, setData] = useState<DataType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Refs（不触发重渲染）
  const abortControllerRef = useRef<AbortController | null>(null);

  // 执行函数
  const execute = useCallback(async (params: ParamsType) => {
    if (!enabled) return;

    setLoading(true);
    setError(null);
    abortControllerRef.current = new AbortController();

    try {
      const result = await fetchData(params, {
        signal: abortControllerRef.current.signal
      });
      setData(result);
      onSuccess?.(result);
    } catch (err) {
      if (err.name !== 'AbortError') {
        const error = err as Error;
        setError(error);
        onError?.(error);
      }
    } finally {
      setLoading(false);
    }
  }, [enabled, onSuccess, onError]);

  // 重置函数
  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  // 清理
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  return { data, loading, error, execute, reset };
};
```

### 处理器类模板 (handlers/)

```tsx
// handlers/XxxHandlerClass.ts
import { BaseHandler } from './BaseHandler';
import type { ExecutionContext, HandlerResult } from './types';
import { apiClient } from '../../services/apiClient';

export class XxxHandlerClass extends BaseHandler {
  constructor() {
    super('xxx'); // 处理器名称
  }

  // 验证是否可处理
  canHandle(mode: string): boolean {
    return mode === 'xxx' || mode.startsWith('xxx-');
  }

  // 主处理方法
  async process(context: ExecutionContext): Promise<HandlerResult> {
    const { message, attachments, options, signal } = context;

    // 1. 验证输入
    this.validateInput(context);

    // 2. 准备请求
    const request = this.prepareRequest(context);

    // 3. 发送请求
    const response = await apiClient.post('/api/modes/gemini/xxx', request, {
      signal
    });

    // 4. 处理响应
    return this.processResponse(response);
  }

  // 流式处理
  async *processStream(context: ExecutionContext): AsyncGenerator<Chunk> {
    const { message, options } = context;

    const response = await fetch('/api/modes/gemini/xxx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, options, stream: true }),
      signal: context.signal
    });

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') return;
          yield JSON.parse(data);
        }
      }
    }
  }

  // 输入验证
  private validateInput(context: ExecutionContext): void {
    if (!context.message?.trim()) {
      throw new Error('Message is required');
    }
  }

  // 准备请求
  private prepareRequest(context: ExecutionContext): RequestBody {
    return {
      message: context.message,
      attachments: context.attachments,
      modelId: context.options.model,
      options: context.options
    };
  }

  // 处理响应
  private processResponse(response: any): HandlerResult {
    return {
      content: response.content,
      attachments: response.attachments,
      metadata: response.metadata
    };
  }
}
```

### 在 StrategyRegistry 中注册

```tsx
// handlers/StrategyRegistry.ts
import { XxxHandlerClass } from './XxxHandlerClass';

// 注册处理器
registry.register('xxx', new XxxHandlerClass());
```

## 常用 Hook 模式

### 数据获取 Hook

```tsx
export const useData = <T>(url: string) => {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const response = await apiClient.get<T>(url);
        if (!cancelled) setData(response);
      } catch (err) {
        if (!cancelled) setError(err as Error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchData();
    return () => { cancelled = true; };
  }, [url]);

  return { data, loading, error };
};
```

### 表单状态 Hook

```tsx
export const useForm = <T extends Record<string, any>>(initial: T) => {
  const [values, setValues] = useState<T>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});

  const handleChange = useCallback((key: keyof T, value: any) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
  }, []);

  const reset = useCallback(() => {
    setValues(initial);
    setErrors({});
  }, [initial]);

  return { values, errors, handleChange, setErrors, reset };
};
```

### 防抖 Hook

```tsx
export const useDebounce = <T>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
};
```

## 开发步骤

1. **确定 Hook 类型**：数据获取、状态管理、副作用处理
2. **定义接口**：Options 和 Return 类型
3. **实现核心逻辑**：状态管理、副作用
4. **添加清理逻辑**：防止内存泄漏
5. **导出类型**：确保类型可用

## 注意事项

- Hook 名称以 `use` 开头
- 返回稳定的引用（useCallback、useMemo）
- 处理组件卸载时的清理
- 避免在条件语句中调用 Hook
- 处理器类继承 `BaseHandler`
