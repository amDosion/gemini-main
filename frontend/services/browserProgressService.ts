/**
 * Browser Progress Service
 * 
 * Handles real-time progress updates for browser operations using Server-Sent Events (SSE).
 */

export interface BrowseProgressUpdate {
  operation_id: string;
  step: string;
  status: 'in_progress' | 'completed' | 'error';
  details: string | null;
  progress: number | null;
  timestamp: string;
}

export type ProgressCallback = (update: BrowseProgressUpdate) => void;

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
    const eventSource = new EventSource(
      `http://localhost:8000/api/browse/progress/${operationId}`
    );

    eventSource.onmessage = (event) => {
      try {
        const update: BrowseProgressUpdate = JSON.parse(event.data);
        
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
      } catch (error) {
        console.error('Error parsing SSE message:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
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
