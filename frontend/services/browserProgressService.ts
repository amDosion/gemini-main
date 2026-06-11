/**
 * Browser Progress Service
 *
 * Handles real-time progress updates for browser operations using Server-Sent Events (SSE).
 */

import { safeJsonParse } from '../utils/safeOps';

export interface BrowseProgressUpdate {
  operationId: string;
  step: string;
  status: 'in_progress' | 'completed' | 'error';
  details: string | null;
  progress: number | null;
  timestamp: string;
}

export type ProgressCallback = (update: BrowseProgressUpdate) => void;

// 配合 safeJsonParse 重载 1 强制类型 guard（type-design-analyzer NEEDS-IMPROVEMENT 修复）
const isBrowseProgressUpdate = (v: unknown): v is BrowseProgressUpdate => {
  if (!v || typeof v !== 'object') return false;
  const r = v as Record<string, unknown>;
  return (
    typeof r.operationId === 'string' &&
    typeof r.step === 'string' &&
    (r.status === 'in_progress' || r.status === 'completed' || r.status === 'error') &&
    typeof r.timestamp === 'string'
  );
};

export class BrowserProgressService {
  private eventSources: Map<string, EventSource> = new Map();

  /**
   * Subscribe to progress updates for a browse operation
   *
   * @param operationId - Unique identifier for the operation
   * @param onProgress - Callback function for progress updates
   * @param onComplete - Optional callback when operation completes
   * @param onError - Optional callback for errors
   * @returns Function to unsubscribe
   */
  subscribe(
    operationId: string,
    onProgress: ProgressCallback,
    onComplete?: () => void,
    onError?: (error: string) => void
  ): () => void {
    // Close existing connection if any
    this.unsubscribe(operationId);

    // Create new EventSource
    // 通过 Vite 代理访问后端 SSE 端点
    const eventSource = new EventSource(`/api/browse/progress/${operationId}`);

    eventSource.onmessage = (event) => {
      // safeJsonParse 重载 1：guard 强制运行时类型验证（避免类型逃逸）
      // 用 BrowseProgressUpdate | null union 让 fallback null 合规
      const update = safeJsonParse<BrowseProgressUpdate | null>(
        event.data,
        null,
        (v): v is BrowseProgressUpdate | null => v === null || isBrowseProgressUpdate(v)
      );
      if (!update) return;

      // Call progress callback
      onProgress(update);

      // Handle completion
      if (update.status === 'completed') {
        onComplete?.();
        this.unsubscribe(operationId);
      }

      // Handle errors
      if (update.status === 'error') {
        onError?.(update.details || 'Unknown error');
        this.unsubscribe(operationId);
      }
    };

    eventSource.onerror = () => {
      // 浏览器自动重连（readyState 为 CONNECTING）时也会触发 onerror，
      // 只有连接被永久关闭（CLOSED）才视为致命错误，否则交给浏览器内置重试
      if (eventSource.readyState !== EventSource.CLOSED) {
        return;
      }
      onError?.('Connection error');
      this.unsubscribe(operationId);
    };

    this.eventSources.set(operationId, eventSource);

    // Return unsubscribe function
    return () => this.unsubscribe(operationId);
  }

  /**
   * Unsubscribe from progress updates
   *
   * @param operationId - Operation identifier
   */
  unsubscribe(operationId: string): void {
    const eventSource = this.eventSources.get(operationId);
    if (eventSource) {
      eventSource.close();
      this.eventSources.delete(operationId);
    }
  }

  /**
   * Unsubscribe from all progress updates
   */
  unsubscribeAll(): void {
    this.eventSources.forEach((eventSource) => eventSource.close());
    this.eventSources.clear();
  }
}

// Export singleton instance
export const browserProgressService = new BrowserProgressService();
