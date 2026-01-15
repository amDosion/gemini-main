/**
 * Workflow Utility Functions
 * 
 * Helper functions for workflow operations:
 * - Validation
 * - Node/Edge manipulation
 * - Export/Import
 * - Statistics calculation
 */

import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';
import { WorkflowValidationResult, WorkflowStatistics } from './types';

/**
 * Validate workflow structure
 */
export const validateWorkflow = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[]
): WorkflowValidationResult => {
  const nodeErrors: Record<string, string[]> = {};
  const edgeErrors: string[] = [];
  const globalErrors: string[] = [];

  // Check for start node
  const startNodes = nodes.filter(n => n.data.type === 'start');
  if (startNodes.length === 0) {
    globalErrors.push('工作流必须包含一个开始节点');
  } else if (startNodes.length > 1) {
    globalErrors.push('工作流只能包含一个开始节点');
  }

  // Check for end node
  const endNodes = nodes.filter(n => n.data.type === 'end');
  if (endNodes.length === 0) {
    globalErrors.push('工作流必须包含至少一个结束节点');
  }

  // Validate each node
  nodes.forEach(node => {
    const errors: string[] = [];

    // Check required fields
    if (!node.data.label || node.data.label.trim() === '') {
      errors.push('节点名称不能为空');
    }

    // Check agent nodes have agent selected
    if (node.data.type === 'agent' && !node.data.agentId) {
      errors.push('智能体节点必须选择一个智能体');
    }

    if (errors.length > 0) {
      nodeErrors[node.id] = errors;
    }
  });

  // Validate edges
  edges.forEach(edge => {
    const sourceNode = nodes.find(n => n.id === edge.source);
    const targetNode = nodes.find(n => n.id === edge.target);

    if (!sourceNode) {
      edgeErrors.push(`连接 ${edge.id} 的源节点不存在`);
    }
    if (!targetNode) {
      edgeErrors.push(`连接 ${edge.id} 的目标节点不存在`);
    }
  });

  // Check for disconnected nodes (except start and end)
  nodes.forEach(node => {
    if (node.data.type === 'start' || node.data.type === 'end') {
      return;
    }

    const hasIncoming = edges.some(e => e.target === node.id);
    const hasOutgoing = edges.some(e => e.source === node.id);

    if (!hasIncoming && !hasOutgoing) {
      if (!nodeErrors[node.id]) {
        nodeErrors[node.id] = [];
      }
      nodeErrors[node.id].push('节点未连接到工作流');
    }
  });

  const isValid = 
    globalErrors.length === 0 &&
    Object.keys(nodeErrors).length === 0 &&
    edgeErrors.length === 0;

  return {
    isValid,
    nodeErrors,
    edgeErrors,
    globalErrors,
  };
};

/**
 * Calculate workflow statistics
 */
export const calculateWorkflowStatistics = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[]
): WorkflowStatistics => {
  const nodesByType: Record<string, number> = {};

  nodes.forEach(node => {
    const type = node.data.type;
    nodesByType[type] = (nodesByType[type] || 0) + 1;
  });

  // Calculate execution time if available
  let executionTime: number | undefined;
  const executedNodes = nodes.filter(n => n.data.startTime && n.data.endTime);
  if (executedNodes.length > 0) {
    const times = executedNodes.map(n => 
      (n.data.endTime! - n.data.startTime!) / 1000
    );
    executionTime = times.reduce((sum, time) => sum + time, 0);
  }

  // Calculate success rate
  let successRate: number | undefined;
  const completedNodes = nodes.filter(n => 
    n.data.status === 'completed' || n.data.status === 'failed'
  );
  if (completedNodes.length > 0) {
    const successfulNodes = completedNodes.filter(n => n.data.status === 'completed');
    successRate = (successfulNodes.length / completedNodes.length) * 100;
  }

  return {
    totalNodes: nodes.length,
    totalEdges: edges.length,
    nodesByType,
    executionTime,
    successRate,
  };
};

/**
 * Export workflow to JSON
 */
export const exportWorkflow = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
  metadata?: {
    name?: string;
    description?: string;
    version?: string;
  }
) => {
  const workflow = {
    version: metadata?.version || '1.0.0',
    name: metadata?.name || 'Untitled Workflow',
    description: metadata?.description || '',
    createdAt: Date.now(),
    nodes: nodes.map(node => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: {
        ...node.data,
        // Remove execution state
        status: undefined,
        progress: undefined,
        result: undefined,
        error: undefined,
        startTime: undefined,
        endTime: undefined,
      },
    })),
    edges: edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      type: edge.type,
    })),
  };

  return JSON.stringify(workflow, null, 2);
};

/**
 * Import workflow from JSON
 */
export const importWorkflow = (jsonString: string): {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  metadata: {
    name: string;
    description: string;
    version: string;
  };
} | null => {
  try {
    const workflow = JSON.parse(jsonString);

    if (!workflow.nodes || !workflow.edges) {
      throw new Error('Invalid workflow format');
    }

    return {
      nodes: workflow.nodes,
      edges: workflow.edges,
      metadata: {
        name: workflow.name || 'Imported Workflow',
        description: workflow.description || '',
        version: workflow.version || '1.0.0',
      },
    };
  } catch (error) {
    console.error('Failed to import workflow:', error);
    return null;
  }
};

/**
 * Find path between two nodes
 */
export const findPath = (
  startNodeId: string,
  endNodeId: string,
  edges: Edge[]
): string[] | null => {
  const visited = new Set<string>();
  const queue: string[][] = [[startNodeId]];

  while (queue.length > 0) {
    const path = queue.shift()!;
    const currentNode = path[path.length - 1];

    if (currentNode === endNodeId) {
      return path;
    }

    if (visited.has(currentNode)) {
      continue;
    }

    visited.add(currentNode);

    const outgoingEdges = edges.filter(e => e.source === currentNode);
    outgoingEdges.forEach(edge => {
      queue.push([...path, edge.target]);
    });
  }

  return null;
};

/**
 * Detect cycles in workflow
 */
export const detectCycles = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[]
): string[][] => {
  const cycles: string[][] = [];
  const visited = new Set<string>();
  const recursionStack = new Set<string>();

  const dfs = (nodeId: string, path: string[]): void => {
    visited.add(nodeId);
    recursionStack.add(nodeId);
    path.push(nodeId);

    const outgoingEdges = edges.filter(e => e.source === nodeId);
    
    for (const edge of outgoingEdges) {
      const targetId = edge.target;
      
      if (!visited.has(targetId)) {
        dfs(targetId, [...path]);
      } else if (recursionStack.has(targetId)) {
        // Found a cycle
        const cycleStart = path.indexOf(targetId);
        cycles.push([...path.slice(cycleStart), targetId]);
      }
    }

    recursionStack.delete(nodeId);
  };

  nodes.forEach(node => {
    if (!visited.has(node.id)) {
      dfs(node.id, []);
    }
  });

  return cycles;
};

/**
 * Get execution order (topological sort)
 */
export const getExecutionOrder = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[]
): string[] | null => {
  const inDegree = new Map<string, number>();
  const adjList = new Map<string, string[]>();

  // Initialize
  nodes.forEach(node => {
    inDegree.set(node.id, 0);
    adjList.set(node.id, []);
  });

  // Build graph
  edges.forEach(edge => {
    adjList.get(edge.source)?.push(edge.target);
    inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
  });

  // Find nodes with no incoming edges
  const queue: string[] = [];
  inDegree.forEach((degree, nodeId) => {
    if (degree === 0) {
      queue.push(nodeId);
    }
  });

  const result: string[] = [];

  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    result.push(nodeId);

    adjList.get(nodeId)?.forEach(neighbor => {
      const newDegree = (inDegree.get(neighbor) || 0) - 1;
      inDegree.set(neighbor, newDegree);
      
      if (newDegree === 0) {
        queue.push(neighbor);
      }
    });
  }

  // Check if all nodes are included (no cycles)
  if (result.length !== nodes.length) {
    return null; // Cycle detected
  }

  return result;
};
