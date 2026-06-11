/**
 * Workflow JSON 序列化/反序列化工具。
 *
 * 1:1 抽离自 `workflowUtils.ts` L354-429
 * （主组件瘦身 — 单文件 <800 行目标）。
 */

import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';

/** 将工作流（节点 + 边 + metadata）序列化为格式化 JSON 字符串。剥离运行时执行状态。 */
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
    nodes: nodes.map((node) => ({
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
    edges: edges.map((edge) => ({
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

/** 最小结构校验：节点必须有 string `id` 和数值 `position.x/y`，否则视为非法导入。 */
const isValidWorkflowNode = (node: unknown): boolean => {
  if (typeof node !== 'object' || node === null) {
    return false;
  }
  const candidate = node as { id?: unknown; position?: unknown };
  if (typeof candidate.id !== 'string') {
    return false;
  }
  const position = candidate.position;
  if (typeof position !== 'object' || position === null) {
    return false;
  }
  const coords = position as { x?: unknown; y?: unknown };
  return typeof coords.x === 'number' && typeof coords.y === 'number';
};

/** 从 JSON 字符串反序列化工作流。失败返回 null（不抛异常）。 */
export const importWorkflow = (
  jsonString: string
): {
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

    if (!Array.isArray(workflow.nodes) || !Array.isArray(workflow.edges)) {
      throw new Error('Invalid workflow format');
    }
    if (!(workflow.nodes as unknown[]).every(isValidWorkflowNode)) {
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
  } catch {
    return null;
  }
};
