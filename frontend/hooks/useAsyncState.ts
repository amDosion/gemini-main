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

  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  const sequenceRef = useRef(0);

  // 用 ref 镜像最新 asyncFn/onSuccess/onError，使 execute 的 identity 永久稳定。
  // 这样调用方把 execute 放进 useEffect deps 数组不会触发重复执行（即使 asyncFn 是内联函数）。
  const asyncFnRef = useRef(asyncFn);
  const onSuccessRef = useRef(options?.onSuccess);
  const onErrorRef = useRef(options?.onError);
  // intentional: no deps — 每次渲染都把最新回调写入 ref，保证 execute 闭包看到最新版本
  useEffect(() => {
    asyncFnRef.current = asyncFn;
    onSuccessRef.current = options?.onSuccess;
    onErrorRef.current = options?.onError;
  });

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const execute = useCallback(async (...args: Args): Promise<T | null> => {
    const mySequence = ++sequenceRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await asyncFnRef.current(...args);
      // isMounted=false 或 stale sequence：两种情况均跳过 setState + onSuccess/onError 回调
      if (!isMountedRef.current || mySequence !== sequenceRef.current) {
        return null;
      }
      setData(result);
      setLoading(false);
      onSuccessRef.current?.(result);
      return result;
    } catch (err) {
      // isMounted=false 或 stale sequence：同样跳过 setState + 回调
      if (!isMountedRef.current || mySequence !== sequenceRef.current) {
        return null;
      }
      const errMsg = getErrorMessage(err);
      setError(errMsg);
      setLoading(false);
      onErrorRef.current?.(err);
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    sequenceRef.current++;
    setData(initialData);
    setLoading(false);
    setError(null);
  }, [initialData]);

  return { data, loading, error, execute, reset };
}
