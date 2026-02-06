import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { InitData } from '../types/types';
import { apiClient } from '../services/apiClient';
import { LLMFactory } from '../services/LLMFactory';

/**
 * Return interface for the useInitData hook.
 */
interface UseInitDataReturn {
  initData: InitData | null;
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

  // Use ref to track if component is mounted
  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  const retry = useCallback(() => {
    setRetryTrigger(count => count + 1);
  }, []);

  useEffect(() => {
    // Reset mounted flag on mount
    isMountedRef.current = true;

    // ✅ 条件加载：只有在 shouldLoad 为 true 时才加载数据
    if (!shouldLoad) {
      // 不需要加载数据，重置状态
      setCriticalData(null);
      setNonCriticalData(null);
      setIsLoading(false);
      setError(null);
      setIsConfigReady(true);  // ✅ 标记为已就绪（即使没有加载数据）
      return;
    }

    const fetchData = async () => {
      // Cancel previous request if exists
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      setIsLoading(true);
      setError(null); // Clear previous error

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        // Create new AbortController for this attempt
        abortControllerRef.current = new AbortController();

        try {
          // ✅ 步骤 1：先加载关键数据（阻塞渲染）
          const critical = await apiClient.get<Partial<InitData>>('/api/init/critical');
          
          // Check if component is still mounted before updating state
          if (!isMountedRef.current) {
            return;
          }

          setCriticalData(critical);
          setError(null);
          setIsConfigReady(true);  // ✅ 移到这里：关键数据加载成功后立即设置
          
          // ✅ 步骤 2：关键数据加载完成后，立即渲染
          // Header 可以显示提供商和模型选择器
          // chat 模式可以正常工作
          
          // ✅ 步骤 3：后台加载非关键数据（不阻塞渲染）
          apiClient.get<Partial<InitData>>('/api/init/non-critical')
            .then(nonCritical => {
              if (isMountedRef.current) {
                setNonCriticalData(nonCritical);
              }
            })
            .catch(err => {
              console.warn('[useInitData] 非关键数据加载失败:', err);
              // 非关键数据失败不影响主流程
            });
          
          // ✅ 步骤 4：后台异步初始化 LLMFactory（不阻塞渲染）
          LLMFactory.initialize().catch(err => {
            console.warn('[useInitData] LLMFactory 初始化失败:', err);
          });
          
          // Data successfully fetched, exit the retry loop.
          return; 
        } catch (e) {
          // Check if component is still mounted
          if (!isMountedRef.current) {
            return;
          }

          const error = e as Error;

          // Don't retry on authentication errors (401)
          if (error.message === 'Unauthorized') {
            console.error('Authentication failed. Please log in again.');
            setError(error);
            setIsConfigReady(true);  // ✅ 错误情况下也设置为 true，让 UI 显示错误
            return; // Exit without retry
          }

          // Retry on other errors
          if (attempt < MAX_RETRIES) {
            const delay = BASE_RETRY_DELAY * Math.pow(2, attempt);
            console.warn(`Attempt ${attempt + 1} failed. Retrying in ${delay}ms...`);
            await new Promise(resolve => setTimeout(resolve, delay));
          } else {
            console.error('Failed to fetch init data after multiple retries.', e);
            setError(error);
            setIsConfigReady(true);  // ✅ 重试耗尽后设置为 true，让 UI 显示错误
          }
        }
      }
    };

    fetchData().finally(() => {
      if (isMountedRef.current) {
        setIsLoading(false);
        // ✅ 不在这里设置 isConfigReady，因为此时 criticalData 可能还没更新
        // isConfigReady 已在 setCriticalData 之后设置
      }
    });

    // Cleanup function
    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [shouldLoad, retryTrigger]);  // ✅ 修改依赖：shouldLoad 替代 isAuthenticated

  // ✅ 合并关键数据和非关键数据
  const initData = useMemo(() => {
    if (!criticalData) return null;
    return {
      ...criticalData,
      ...nonCriticalData,
      // 如果非关键数据还未加载，使用空数组作为默认值
      sessions: nonCriticalData?.sessions || [],
      personas: nonCriticalData?.personas || [],
      storageConfigs: nonCriticalData?.storageConfigs || [],
      activeStorageId: nonCriticalData?.activeStorageId || null,
      imagenConfig: nonCriticalData?.imagenConfig || null,
      sessionsTotal: nonCriticalData?.sessionsTotal || 0,
      sessionsHasMore: nonCriticalData?.sessionsHasMore || false
    } as InitData;
  }, [criticalData, nonCriticalData]);

  return { initData, isLoading, error, isConfigReady, retry };
};
