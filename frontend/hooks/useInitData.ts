import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { InitData } from '../types/types';
import { apiClient } from '../services/apiClient';
import { LLMFactory } from '../services/LLMFactory';
import { reportError } from '../utils/globalErrorHandler';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';

/**
 * Return interface for the useInitData hook.
 */
interface UseInitDataReturn {
  initData: InitData | null;
  // ✅ B-2: 暴露独立 critical / non-critical 切片,下游 hook 可仅订阅关心的部分,
  // 避免合并 memo 引用变化触发整条 useSettings/usePersonas/useStorageConfigs effect 链。
  criticalData: Partial<InitData> | null;
  nonCriticalData: Partial<InitData> | null;
  isLoading: boolean;
  error: Error | null;
  isConfigReady: boolean; // true when data is loaded (even if empty or failed)
  retry: () => void;
}

const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // 1 second

/**
 * Custom React Hook to fetch initial application data from the /api/init endpoint.
 * It handles loading states, error handling with automatic exponential backoff,
 * and provides a manual retry mechanism.
 *
 * @param shouldLoad - Boolean indicating if the data should be loaded. Only loads when true (优化：减少不必要的请求).
 * @returns An object containing the initial data, loading and error states, and a retry function.
 */
export const useInitData = (shouldLoad: boolean): UseInitDataReturn => {
  const [criticalData, setCriticalData] = useState<Partial<InitData> | null>(null);
  const [nonCriticalData, setNonCriticalData] = useState<Partial<InitData> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [isConfigReady, setIsConfigReady] = useState<boolean>(false);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const scopeVersion = usePrivateCacheScopeRevision();

  // Use ref to track if component is mounted
  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);
  const requestRunRef = useRef(0);

  const retry = useCallback(() => {
    setRetryTrigger((count) => count + 1);
  }, []);

  useEffect(() => {
    const runId = requestRunRef.current + 1;
    requestRunRef.current = runId;
    const isCurrentRun = () => isMountedRef.current && requestRunRef.current === runId;

    // Reset mounted flag on mount
    isMountedRef.current = true;

    // ✅ 条件加载：只有在 shouldLoad 为 true 时才加载数据
    if (!shouldLoad) {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      // 不需要加载数据，重置状态
      setCriticalData(null);
      setNonCriticalData(null);
      setIsLoading(false);
      setError(null);
      setIsConfigReady(true); // ✅ 标记为已就绪（即使没有加载数据）
      return;
    }

    const fetchData = async () => {
      // Cancel previous request if exists
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      setCriticalData(null);
      setNonCriticalData(null);
      setIsConfigReady(false);
      setIsLoading(true);
      setError(null); // Clear previous error

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        // Create new AbortController for this attempt
        abortControllerRef.current = new AbortController();
        const requestSignal = abortControllerRef.current.signal;

        try {
          // ✅ 步骤 1：先加载关键数据（阻塞渲染）
          const critical = await apiClient.get<Partial<InitData>>('/api/init/critical', {
            signal: requestSignal,
          });

          // Check if component is still mounted before updating state
          if (!isCurrentRun()) {
            return;
          }

          setCriticalData(critical);
          setError(null);
          setIsConfigReady(true); // ✅ 移到这里：关键数据加载成功后立即设置

          // ✅ 步骤 2：关键数据加载完成后，立即渲染
          // Header 可以显示提供商和模型选择器
          // chat 模式可以正常工作

          // ✅ 步骤 3：后台加载非关键数据（不阻塞渲染）
          // C-2 + B-6: 传递 abort signal,组件卸载后取消;失败 reportError 而非静默吞
          apiClient
            .get<Partial<InitData>>('/api/init/non-critical', {
              signal: requestSignal,
            })
            .then((nonCritical) => {
              if (isCurrentRun()) {
                setNonCriticalData(nonCritical);
              }
            })
            .catch((err) => {
              // AbortError 和组件卸载后的请求都正常忽略
              if (err?.name === 'AbortError' || !isCurrentRun()) {
                return;
              }
              reportError('useInitData.non-critical', err);
            });

          // ✅ 步骤 4：后台异步初始化 LLMFactory（不阻塞渲染）
          LLMFactory.initialize();

          // Data successfully fetched, exit the retry loop.
          return;
        } catch (e) {
          // Check if component is still mounted
          if (!isCurrentRun()) {
            return;
          }

          // 修 ts-reviewer MEDIUM：catch 入参是 unknown，用 instanceof guard 替代 `as` cast
          const error = e instanceof Error ? e : new Error(String(e));

          // ✅ C-7: 中止/取消错误直接退出,不进重试 loop
          if (
            error?.name === 'AbortError' ||
            error?.message === 'Request cancelled by user' ||
            error?.message === 'The operation was aborted.'
          ) {
            return;
          }

          // Don't retry on authentication errors (401)
          if (error.message === 'Unauthorized') {
            setError(error);
            setIsConfigReady(true); // ✅ 错误情况下也设置为 true，让 UI 显示错误
            return; // Exit without retry
          }

          // Retry on other errors
          if (attempt < MAX_RETRIES) {
            const delay = BASE_RETRY_DELAY * Math.pow(2, attempt);
            await new Promise((resolve) => setTimeout(resolve, delay));
            if (!isCurrentRun()) {
              return;
            }
          } else {
            setError(error);
            setIsConfigReady(true); // ✅ 重试耗尽后设置为 true，让 UI 显示错误
          }
        }
      }
    };

    fetchData().finally(() => {
      if (isCurrentRun()) {
        setIsLoading(false);
        // ✅ 不在这里设置 isConfigReady，因为此时 criticalData 可能还没更新
        // isConfigReady 已在 setCriticalData 之后设置
      }
    });

    // Cleanup function
    return () => {
      isMountedRef.current = false;
      if (requestRunRef.current === runId) {
        requestRunRef.current += 1;
      }
      // 不 abort fetch：React StrictMode 双 mount 触发 cleanup → abort → re-mount
      // 重 fetch，在 Network tab 看到 (canceled)。fetch 内部已用 isMountedRef
      // guard 防 setState-after-unmount；abortControllerRef 仅用于 retry 时 cancel 前一次。
    };
  }, [shouldLoad, retryTrigger, scopeVersion]); // scopeVersion 保证跨用户切换时重载 init data

  // ✅ 合并关键数据和非关键数据
  const initData = useMemo(() => {
    if (!criticalData) return null;
    return {
      ...criticalData,
      ...nonCriticalData,
      // 如果非关键数据还未加载，使用空数组作为默认值
      sessions: nonCriticalData?.sessions || [],
      sessionsMode: nonCriticalData?.sessionsMode,
      personas: nonCriticalData?.personas || [],
      storageConfigs: nonCriticalData?.storageConfigs || [],
      activeStorageId: nonCriticalData?.activeStorageId || null,
      imagenConfig: nonCriticalData?.imagenConfig || null,
      sessionsTotal: nonCriticalData?.sessionsTotal || 0,
      sessionsHasMore: nonCriticalData?.sessionsHasMore || false,
    } as InitData;
  }, [criticalData, nonCriticalData]);

  return { initData, criticalData, nonCriticalData, isLoading, error, isConfigReady, retry };
};
