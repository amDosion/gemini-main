# 创建新的 React Hook

根据用户描述创建一个新的自定义 React Hook。

## 执行步骤

1. **确定 Hook 类型**
   - 数据获取 Hook → `frontend/hooks/`
   - 状态管理 Hook → `frontend/hooks/`
   - 请求处理器 → `frontend/hooks/handlers/`

2. **创建 Hook 文件**
   使用以下模板：

```typescript
import { useState, useCallback, useEffect, useRef } from 'react';

// 配置选项接口
export interface Use[HookName]Options {
  enabled?: boolean;
  onSuccess?: (data: any) => void;
  onError?: (error: Error) => void;
}

// 返回值接口
export interface Use[HookName]Return {
  data: any;
  loading: boolean;
  error: Error | null;
  execute: () => Promise<void>;
  reset: () => void;
}

export const use[HookName] = (
  options: Use[HookName]Options = {}
): Use[HookName]Return => {
  const { enabled = true, onSuccess, onError } = options;

  // 状态
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Refs
  const abortControllerRef = useRef<AbortController | null>(null);

  // 执行方法
  const execute = useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError(null);
    abortControllerRef.current = new AbortController();

    try {
      // 实现逻辑
      const result = await fetchData({
        signal: abortControllerRef.current.signal
      });
      setData(result);
      onSuccess?.(result);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        const error = err as Error;
        setError(error);
        onError?.(error);
      }
    } finally {
      setLoading(false);
    }
  }, [enabled, onSuccess, onError]);

  // 重置方法
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

3. **如果是处理器类，使用此模板**：

```typescript
// frontend/hooks/handlers/[Name]HandlerClass.ts
import { BaseHandler } from './BaseHandler';
import type { ExecutionContext, HandlerResult } from './types';

export class [Name]HandlerClass extends BaseHandler {
  constructor() {
    super('[name]');
  }

  canHandle(mode: string): boolean {
    return mode === '[mode-name]';
  }

  async process(context: ExecutionContext): Promise<HandlerResult> {
    // 实现处理逻辑
  }
}
```

4. **注册处理器**（如果是 Handler）
   在 `StrategyRegistry.ts` 中添加注册

## 规范要求

- Hook 名称以 `use` 开头
- 导出 Options 和 Return 接口
- 返回稳定的引用（useCallback）
- 处理组件卸载时的清理
- 处理器类继承 `BaseHandler`

## 使用示例

```
/new-hook 创建一个 useWebSocket hook，支持自动重连和心跳检测
```
