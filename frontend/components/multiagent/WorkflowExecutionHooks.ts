/**
 * Workflow Execution Hooks
 * 
 * Custom hooks for managing workflow execution state and API calls:
 * - useExecutionLogs: Manage execution logs
 */

import { useState, useCallback } from 'react';
import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';
import { LogEntry, LogLevel } from './ExecutionLogPanel';

/**
 * Execution logs management hook
 */
export const useExecutionLogs = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const addLog = useCallback((
    nodeId: string,
    nodeName: string,
    level: LogLevel,
    message: string,
    timestamp?: number
  ) => {
    const newLog: LogEntry = {
      id: `${Date.now()}-${Math.random()}`,
      timestamp: timestamp ?? Date.now(),
      nodeId,
      nodeName,
      level,
      message
    };
    setLogs(prev => {
      const updated = [...prev, newLog];
      // Cap at 2000 entries to prevent memory leak
      return updated.length > 2000 ? updated.slice(-1500) : updated;
    });
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
