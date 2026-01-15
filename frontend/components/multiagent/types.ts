/**
 * Type Definitions for Multi-Agent Workflow Editor
 * 
 * Shared types used across all workflow components
 */

import type { Node, Edge } from 'reactflow';

// Node execution status
export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed';

// Edge animation types
export type EdgeAnimationType = 'none' | 'pulse' | 'flow';

// Custom node data interface
export interface WorkflowNodeData {
  label: string;
  description: string;
  icon: string;
  iconColor: string;
  type?: string;
  agentId?: string;
  agentName?: string;
  tools?: string[];
  status?: NodeStatus;
  progress?: number;
  result?: any;
  error?: string;
  startTime?: number;
  endTime?: number;
}

// Workflow Node type (compatible with React Flow)
export type WorkflowNode = Node<WorkflowNodeData>;

// Workflow Edge type (compatible with React Flow)
export type WorkflowEdge = Edge;

// Execution Status for workflow execution tracking
export interface ExecutionStatus {
  nodeStatuses: Record<string, NodeStatus>;
  nodeProgress: Record<string, number>;
  nodeResults: Record<string, any>;
  nodeErrors: Record<string, string>;
  logs: Array<{
    timestamp: number;
    nodeId: string;
    message: string;
    level: 'info' | 'warn' | 'error';
  }>;
}

// Workflow execution state
export interface WorkflowExecutionState {
  isExecuting: boolean;
  executionId: string | null;
  startTime: number | null;
  endTime: number | null;
}

// Node validation result
export interface NodeValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

// Workflow validation result
export interface WorkflowValidationResult {
  isValid: boolean;
  nodeErrors: Record<string, string[]>;
  edgeErrors: string[];
  globalErrors: string[];
}

// Workflow statistics
export interface WorkflowStatistics {
  totalNodes: number;
  totalEdges: number;
  nodesByType: Record<string, number>;
  executionTime?: number;
  successRate?: number;
}
