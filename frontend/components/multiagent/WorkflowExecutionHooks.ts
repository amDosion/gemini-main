/**
 * Workflow Execution Hooks
 * 
 * Custom hooks for managing workflow execution state and API calls:
 * - useWorkflowExecution: Main execution hook
 * - useExecutionPolling: Poll for status updates
 * - useExecutionLogs: Manage execution logs
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';
import { LogEntry, LogLevel } from './ExecutionLogPanel';

export interface WorkflowExecutionRequest {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  startNodeId?: string;
}

export interface WorkflowExecutionResponse {
  executionId: string;
  status: 'running' | 'completed' | 'failed';
  nodeStatuses: Record<string, {
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    result?: any;
    error?: string;
    startTime?: number;
    endTime?: number;
  }>;
  nodeErrors?: Record<string, string>;
  logs?: Array<{
    timestamp: number;
    nodeId: string;
    level: string;
    message: string;
  }>;
}

export interface UseWorkflowExecutionResult {
  isExecuting: boolean;
  executionId: string | null;
  executeWorkflow: (request: WorkflowExecutionRequest) => Promise<void>;
  cancelExecution: () => void;
  retryNode: (nodeId: string) => Promise<void>;
  error: string | null;
}

/**
 * Main workflow execution hook
 */
export const useWorkflowExecution = (
  onStatusUpdate?: (nodeStatuses: WorkflowExecutionResponse['nodeStatuses']) => void
): UseWorkflowExecutionResult => {
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const executeWorkflow = useCallback(async (request: WorkflowExecutionRequest) => {
    setIsExecuting(true);
    setError(null);

    try {
      const response = await fetch('/api/multi-agent/orchestrate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          workflow: {
            nodes: request.nodes.map(node => ({
              id: node.id,
              type: node.data.type,
              label: node.data.label,
              description: node.data.description,
              agentId: node.data.agentId,
              position: node.position
            })),
            edges: request.edges.map(edge => ({
              id: edge.id,
              source: edge.source,
              target: edge.target
            }))
          },
          startNodeId: request.startNodeId
        })
      });

      if (!response.ok) {
        throw new Error(`Execution failed: ${response.statusText}`);
      }

      const result: WorkflowExecutionResponse = await response.json();
      setExecutionId(result.executionId);

      // Update node statuses
      if (onStatusUpdate && result.nodeStatuses) {
        onStatusUpdate(result.nodeStatuses);
      }

      // Start polling for updates if execution is running
      if (result.status === 'running') {
        startPolling(result.executionId);
      } else {
        setIsExecuting(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setIsExecuting(false);
    }
  }, [onStatusUpdate]);

  const startPolling = useCallback((execId: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`/api/multi-agent/orchestrate/${execId}/status`);
        if (!response.ok) {
          throw new Error('Failed to fetch status');
        }

        const result: WorkflowExecutionResponse = await response.json();

        // Update node statuses
        if (onStatusUpdate && result.nodeStatuses) {
          onStatusUpdate(result.nodeStatuses);
        }

        // Stop polling if execution is complete
        if (result.status === 'completed' || result.status === 'failed') {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          setIsExecuting(false);
        }
      } catch (err) {
        console.error('Polling error:', err);
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        setIsExecuting(false);
      }
    }, 1000); // Poll every second
  }, [onStatusUpdate]);

  const cancelExecution = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsExecuting(false);
    setExecutionId(null);
  }, []);

  const retryNode = useCallback(async (nodeId: string) => {
    if (!executionId) {
      return;
    }

    try {
      const response = await fetch(`/api/multi-agent/orchestrate/${executionId}/retry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ nodeId })
      });

      if (!response.ok) {
        throw new Error('Retry failed');
      }

      const result: WorkflowExecutionResponse = await response.json();

      // Update node statuses
      if (onStatusUpdate && result.nodeStatuses) {
        onStatusUpdate(result.nodeStatuses);
      }

      // Resume polling if needed
      if (result.status === 'running') {
        setIsExecuting(true);
        startPolling(executionId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed');
    }
  }, [executionId, onStatusUpdate, startPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  return {
    isExecuting,
    executionId,
    executeWorkflow,
    cancelExecution,
    retryNode,
    error
  };
};

/**
 * Execution logs management hook
 */
export const useExecutionLogs = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const addLog = useCallback((
    nodeId: string,
    nodeName: string,
    level: LogLevel,
    message: string
  ) => {
    const newLog: LogEntry = {
      id: `${Date.now()}-${Math.random()}`,
      timestamp: Date.now(),
      nodeId,
      nodeName,
      level,
      message
    };
    setLogs(prev => [...prev, newLog]);
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const importLogs = useCallback((serverLogs: Array<{
    timestamp: number;
    nodeId: string;
    level: string;
    message: string;
  }>, nodesMap: Map<string, Node<CustomNodeData>>) => {
    const newLogs: LogEntry[] = serverLogs.map((log, index) => ({
      id: `${log.timestamp}-${index}`,
      timestamp: log.timestamp,
      nodeId: log.nodeId,
      nodeName: nodesMap.get(log.nodeId)?.data.label || log.nodeId,
      level: (log.level as LogLevel) || 'info',
      message: log.message
    }));
    setLogs(prev => [...prev, ...newLogs]);
  }, []);

  return {
    logs,
    addLog,
    clearLogs,
    importLogs
  };
};
