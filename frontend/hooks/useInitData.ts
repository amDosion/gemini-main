import { useState, useEffect, useCallback, useRef } from 'react';
import { InitData } from '../types/types';
import { apiClient } from '../services/apiClient';

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
 * @param isAuthenticated - Boolean indicating if the user is authenticated. The API call is only made if true.
 * @returns An object containing the initial data, loading and error states, and a retry function.
 */
export const useInitData = (isAuthenticated: boolean): UseInitDataReturn => {
  const [initData, setInitData] = useState<InitData | null>(null);
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

    if (!isAuthenticated) {
      // If the user is not authenticated, do nothing.
      // Reset state in case of logout.
      setInitData(null);
      setIsLoading(false);
      setError(null);
      setIsConfigReady(false);
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
          const data = await apiClient.get<InitData>('/api/init');

          // Check if component is still mounted before updating state
          if (!isMountedRef.current) {
            return;
          }

          if (data?._metadata?.partialFailures?.length) {
            console.warn(
              'Partial failures encountered during init:',
              data._metadata.partialFailures
            );
          }
          
          setInitData(data);
          setError(null); // Clear error on success
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
          }
        }
      }
    };

    fetchData().finally(() => {
      if (isMountedRef.current) {
        setIsLoading(false);
        setIsConfigReady(true);
      }
    });

    // Cleanup function
    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isAuthenticated, retryTrigger]);

  return { initData, isLoading, error, isConfigReady, retry };
};
