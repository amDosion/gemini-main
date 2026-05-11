import { useCallback, useEffect, useRef, useState } from 'react';

import { getErrorMessage } from '../utils/errorMessage';

/**
 * 通用 async state 容器 hook。
 *
 * 替代 4+ 处 `useState(loading)`+`useState(error)`+`finally setLoading(false)` 三件套
 * （见 JIRA-frontend-hook-utility-extraction.md A.1.3）。
 *
 * 行为：
 * - execute(...args) → 调 asyncFn；自动管理 loading / error / data
 * - error 经 getErrorMessage 归一化为 string
 * - isMountedRef 防卸载后 setState（避免 React warning）
 * - sequenceRef 丢弃 stale execute（连续触发只采纳最后一次结果）
 * - reset() 清空 data/error，loading=false；同步 bump sequence 避免 in-flight 覆盖
 */

export interface UseAsyncStateOptions<T> {
  initialData?: T | null;
  onSuccess?: (data: T) => void;
  onError?: (err: unknown) => void;
}

export interface UseAsyncStateResult<T, Args extends unknown[]> {
  data: T | null;
  loading: boolean;
  error: string | null;
  execute: (...args: Args) => Promise<T | null>;
  reset: () => void;
}

export function useAsyncState<T, Args extends unknown[] = []>(
  asyncFn: (...args: Args) => Promise<T>,
  options?: UseAsyncStateOptions<T>
): UseAsyncStateResult<T, Args> {
  const initialData = options?.initialData ?? null;
  const onSuccess = options?.onSuccess;
  const onError = options?.onError;

  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  const sequenceRef = useRef(0);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (...args: Args): Promise<T | null> => {
      const mySequence = ++sequenceRef.current;
      setLoading(true);
      setError(null);
      try {
        const result = await asyncFn(...args);
        if (!isMountedRef.current || mySequence !== sequenceRef.current) {
          return null;
        }
        setData(result);
        setLoading(false);
        onSuccess?.(result);
        return result;
      } catch (err) {
        if (!isMountedRef.current || mySequence !== sequenceRef.current) {
          return null;
        }
        const errMsg = getErrorMessage(err);
        setError(errMsg);
        setLoading(false);
        onError?.(err);
        return null;
      }
    },
    [asyncFn, onSuccess, onError]
  );

  const reset = useCallback(() => {
    sequenceRef.current++;
    setData(initialData);
    setLoading(false);
    setError(null);
  }, [initialData]);

  return { data, loading, error, execute, reset };
}
