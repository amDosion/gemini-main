import { useState, useCallback, useRef, useEffect } from 'react';
import apiClient from '../services/apiClient';

/**
 * Defines the shape of the research status object.
 */
export interface ResearchStatus {
  status: 'idle' | 'starting' | 'in_progress' | 'completed' | 'failed';
  interactionId?: string;
  progress?: string;
  result?: string;
  error?: string;
  elapsedTime?: number;
  estimatedTime?: number;
}

/**
 * Defines the options available for starting a research task.
 */
export interface ResearchOptions {
  format?: 'technical report' | 'market analysis' | 'literature review' | string;
  includePrivateData?: boolean;
  fileSearchStoreNames?: string[];
  language?: string;
  tone?: 'professional' | 'casual' | 'technical';
}

/**
 * Defines the return value of the useDeepResearch hook.
 */
export interface UseDeepResearchReturn {
  researchStatus: ResearchStatus;
  startResearch: (prompt: string, options?: ResearchOptions) => Promise<void>;
  cancelResearch: () => Promise<void>;
}

// --- Constants ---
const POLLING_INTERVAL = 10000; // 10 seconds
const MAX_POLLS = 360; // 60 minutes
const MAX_PROMPT_LENGTH = 10000;
const DANGEROUS_KEYWORDS = ['ignore previous', 'system:', 'admin:', 'root:'];
const MAX_RETRIES = 3;
const RETRY_DELAYS = [2000, 4000, 8000]; // milliseconds

// --- Helper Functions ---

/**
 * Constructs the full prompt with specified formatting and style options.
 * @param prompt - The base user prompt.
 * @param options - Research options including format, language, and tone.
 * @returns The constructed prompt string.
 */
const buildPrompt = (prompt: string, options: ResearchOptions = {}): string => {
  let fullPrompt = prompt;
  const additions: string[] = [];

  if (options.format) {
    switch (options.format) {
      case 'technical report':
        additions.push('Please format the output as a technical report with an introduction, methodology, findings, and conclusion.');
        break;
      case 'market analysis':
        additions.push('Please format the output as a market analysis, including market size, trends, competition, and opportunities.');
        break;
      case 'literature review':
        additions.push('Please format the output as a literature review, summarizing key themes and identifying gaps in the current research.');
        break;
      default:
        additions.push(`Please format the report as ${options.format}.`);
        break;
    }
  }
  if (options.language) {
    additions.push(`Please write the report in ${options.language}.`);
  }
  if (options.tone) {
    additions.push(`Please use a ${options.tone} tone.`);
  }

  if (additions.length > 0) {
    fullPrompt += '\n\n' + additions.join('\n');
  }

  return fullPrompt;
};


/**
 * Estimates the remaining time based on progress keywords.
 * @param progress - The progress description string.
 * @returns Estimated time in seconds.
 */
const estimateRemainingTime = (progress: string): number => {
  if (!progress) return 180; // Default 3 mins if no progress string
  const lowerCaseProgress = progress.toLowerCase();
  if (lowerCaseProgress.includes('gathering')) return 600; // 10 mins
  if (lowerCaseProgress.includes('analyzing')) return 480; // 8 mins
  if (lowerCaseProgress.includes('generating')) return 300; // 5 mins
  if (lowerCaseProgress.includes('refining')) return 120; // 2 mins
  if (lowerCaseProgress.includes('initiated')) return 900; // 15 mins
  return 180; // Default 3 mins
};

/**
 * Formats time in seconds to a MM:SS string.
 * @param totalSeconds - The total seconds to format.
 * @returns The formatted time string "MM:SS".
 */
export const formatTime = (totalSeconds: number): string => {
  if (isNaN(totalSeconds) || totalSeconds < 0) {
    return '00:00';
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

/**
 * A custom React hook to manage long-running deep research tasks.
 */
export const useDeepResearch = (): UseDeepResearchReturn => {
  const [researchStatus, setResearchStatus] = useState<ResearchStatus>({ status: 'idle' });
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollCountRef = useRef<number>(0);
  const startTimeRef = useRef<number | null>(null);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Stops all asynchronous activities (polling, retries).
   */
  const stopAsyncActivities = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    pollCountRef.current = 0;
    startTimeRef.current = null;
  }, []);

  /**
   * Polls the backend for the status of an in-progress research task.
   * @param interactionId - The ID of the research task to poll.
   * @param retryCount - The current retry attempt count.
   */
  const pollResearchStatus = useCallback(async (interactionId: string, retryCount = 0) => {
    if (!interactionId || interactionId.trim() === '') {
        setResearchStatus(prev => ({
          ...prev,
          status: 'failed',
          error: 'Invalid interaction ID.',
        }));
        stopAsyncActivities();
        return;
    }

    if (pollCountRef.current >= MAX_POLLS) {
      setResearchStatus(prev => ({
        ...prev,
        status: 'failed',
        error: 'Research timed out after 60 minutes.',
      }));
      stopAsyncActivities();
      return;
    }

    pollCountRef.current += 1;

    try {
      const response = await apiClient.get<{
        status: 'in_progress' | 'completed' | 'failed';
        progress?: string;
        result?: string;
        error?: string;
      }>(`/api/research/status/${interactionId}`);

      const { status, progress, result, error } = response;
      const elapsedTime = startTimeRef.current ? (Date.now() - startTimeRef.current) / 1000 : 0;

      setResearchStatus(prev => ({
        ...prev,
        status,
        progress: progress || prev.progress,
        result: status === 'completed' ? result : prev.result,
        error: status === 'failed' ? error : prev.error,
        elapsedTime,
        estimatedTime: estimateRemainingTime(progress || ''),
      }));

      if (status === 'completed' || status === 'failed') {
        stopAsyncActivities();
      }
    } catch (err: any) {
        const isTemporaryError = err.response?.status === 503 || err.code === 'ECONNREFUSED';
        if (isTemporaryError && retryCount < MAX_RETRIES) {
          const delay = RETRY_DELAYS[retryCount];
          retryTimeoutRef.current = setTimeout(() => {
            pollResearchStatus(interactionId, retryCount + 1);
          }, delay);
          return;
        }

        let errorMessage = 'An unknown error occurred while polling for status.';
        if (err.response) {
            errorMessage = `API Error: ${err.response.data?.message || err.response.statusText}`;
        } else if (err.request) {
            errorMessage = 'Network Error: Could not connect to the server. Please check your connection.';
        } else {
            errorMessage = `Error: ${err.message}`;
        }

        setResearchStatus(prev => ({
            ...prev,
            status: 'failed',
            error: errorMessage,
        }));
        stopAsyncActivities();
    }
  }, [stopAsyncActivities]);

  /**
   * Starts a new research task.
   * @param prompt - The main prompt for the research.
   * @param options - Optional parameters for the research.
   */
  const startResearch = useCallback(async (prompt: string, options: ResearchOptions = {}) => {
    if (prompt.length > MAX_PROMPT_LENGTH) {
        setResearchStatus({ 
          status: 'failed', 
          error: `Prompt exceeds maximum length of ${MAX_PROMPT_LENGTH} characters.` 
        });
        return;
    }
    
    const lowerPrompt = prompt.toLowerCase();
    const foundDangerous = DANGEROUS_KEYWORDS.find(kw => lowerPrompt.includes(kw));
    if (foundDangerous) {
        setResearchStatus({ 
          status: 'failed', 
          error: `Prompt contains potentially dangerous content: "${foundDangerous}"` 
        });
        return;
    }

    stopAsyncActivities();
    setResearchStatus({ status: 'starting', progress: 'Preparing research...' });

    const fullPrompt = buildPrompt(prompt, options);

    try {
      const response = await apiClient.post<{ interactionId: string }>('/api/research/start', {
        prompt: fullPrompt,
        includePrivateData: options.includePrivateData,
        fileSearchStoreNames: options.fileSearchStoreNames,
      });

      const { interactionId } = response;
      if (!interactionId) {
        throw new Error('Backend did not return an interactionId.');
      }
      
      startTimeRef.current = Date.now();
      setResearchStatus({
        status: 'in_progress',
        interactionId,
        progress: 'Research initiated...',
        elapsedTime: 0,
        estimatedTime: estimateRemainingTime('initiated'),
      });

      pollingRef.current = setInterval(() => {
        pollResearchStatus(interactionId);
      }, POLLING_INTERVAL);

    } catch (err: any) {
        let errorMessage = 'An unknown error occurred while starting the research.';
        if (err.response) {
            errorMessage = `API Error: ${err.response.data?.message || err.response.statusText}`;
        } else if (err.request) {
            errorMessage = 'Network Error: Could not connect to the server to start the research.';
        } else {
            errorMessage = `Error: ${err.message}`;
        }
        setResearchStatus({
            status: 'failed',
            error: errorMessage,
        });
        stopAsyncActivities();
    }
  }, [pollResearchStatus, stopAsyncActivities]);

  /**
   * Cancels the currently active research task.
   */
  const cancelResearch = useCallback(async () => {
    const { interactionId, status } = researchStatus;

    if (status !== 'starting' && status !== 'in_progress') {
        return;
    }
    
    if (!interactionId) {
        setResearchStatus({ status: 'idle' });
        return;
    }

    stopAsyncActivities();

    try {
      await apiClient.post(`/api/research/cancel/${interactionId}`);
      setResearchStatus({ status: 'idle' });
    } catch (err: any) {
      setResearchStatus({
        status: 'idle',
        error: `Failed to cancel research: ${err.response?.data?.message || err.message}`
      });
    }
  }, [researchStatus, stopAsyncActivities]);

  // Effect to clean up polling on component unmount
  useEffect(() => {
    return () => {
      stopAsyncActivities();
    };
  }, [stopAsyncActivities]);

  return { researchStatus, startResearch, cancelResearch };
};
