/**
 * Workflow Utility Functions
 * 
 * Helper functions for workflow operations:
 * - Validation
 * - Node/Edge manipulation
 * - Export/Import
 * - Statistics calculation
 */

import { Node, Edge, Position } from 'reactflow';
import dagre from '@dagrejs/dagre';
import { CustomNodeData } from './CustomNode';
import { WorkflowValidationResult, WorkflowStatistics } from './types';
import { buildNodeParamChips } from './nodeParamSummaryUtils';
import {
  extractAudioUrls,
  extractImageUrls,
  extractTextContent,
  extractVideoUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
} from './workflowResultUtils';

const ACTIVE_INLINE_PROVIDER_TOKENS = new Set([
  '__active__',
  '__current__',
  'active',
  'current',
  'active-profile',
  'current-profile',
]);

const AUTO_INLINE_MODEL_TOKENS = new Set([
  '',
  '__auto__',
  '__active__',
  'auto',
  'active',
  'current',
  'active-profile',
  'current-profile',
]);

const isActiveInlineProviderToken = (value: unknown): boolean => (
  ACTIVE_INLINE_PROVIDER_TOKENS.has(String(value || '').trim().toLowerCase())
);

const isAutoInlineModelToken = (value: unknown): boolean => (
  AUTO_INLINE_MODEL_TOKENS.has(String(value || '').trim().toLowerCase())
);

const toBooleanFlag = (value: unknown): boolean => {
  if (typeof value === 'boolean') {
    return value;
  }
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase());
};

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
  const nodeIdSet = new Set(nodes.map((node) => node.id));
  const incomingByNode = new Map<string, Edge[]>();
  const outgoingByNode = new Map<string, Edge[]>();

  nodes.forEach((node) => {
    incomingByNode.set(node.id, []);
    outgoingByNode.set(node.id, []);
  });

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
    globalErrors.push('工作流必须包含一个结束节点');
  } else if (endNodes.length > 1) {
    globalErrors.push('工作流只能包含一个结束节点');
  }

  // Validate each node
  nodes.forEach(node => {
    const errors: string[] = [];
    const nodeType = node.data.type;

    // Check required fields
    if (!node.data.label || node.data.label.trim() === '') {
      errors.push('节点名称不能为空');
    }

    // Agent 节点必须绑定用户 Agent，或使用内联运行时配置
    if (nodeType === 'agent') {
      const hasAgentId = typeof node.data.agentId === 'string' && node.data.agentId.trim().length > 0;
      const hasAgentName = typeof node.data.agentName === 'string' && node.data.agentName.trim().length > 0;
      const inlineProviderId = String(node.data.inlineProviderId || '').trim();
      const inlineModelId = String(node.data.inlineModelId || '').trim();
      const hasExplicitInlineBinding = inlineProviderId.length > 0 && inlineModelId.length > 0;
      const hasActiveInlineBinding = isActiveInlineProviderToken(inlineProviderId) && isAutoInlineModelToken(inlineModelId);
      const useActiveProfileInline = toBooleanFlag(node.data.inlineUseActiveProfile);

      if (!hasAgentId && !hasAgentName && !hasExplicitInlineBinding && !hasActiveInlineBinding && !useActiveProfileInline) {
        errors.push('智能体节点必须配置智能体（agentId / agentName），或配置 inlineProviderId + inlineModelId，或启用 inlineUseActiveProfile');
      }

      const normalizedTaskType = String(node.data.agentTaskType || 'chat').trim().toLowerCase().replace(/_/g, '-');
      const hasReferenceImage = typeof node.data.agentReferenceImageUrl === 'string'
        && node.data.agentReferenceImageUrl.trim().length > 0;
      if (
        hasReferenceImage
        && !['vision-understand', 'image-understand', 'vision-analyze', 'image-analyze', 'image-edit'].includes(normalizedTaskType)
      ) {
        errors.push('节点配置了参考图时，任务类型必须是 vision-understand 或 image-edit');
      }
    }

    if (nodeType === 'condition' && !node.data.expression?.trim()) {
      errors.push('条件节点必须配置条件表达式');
    }

    if (nodeType === 'router' && !node.data.routerPrompt?.trim()) {
      errors.push('路由节点必须配置路由提示词');
    }

    if (nodeType === 'loop' && (node.data.maxIterations ?? 0) < 1) {
      errors.push('循环节点的最大迭代次数必须大于 0');
    }

    if (nodeType === 'tool' && !node.data.toolName?.trim()) {
      errors.push('工具节点必须配置工具名称');
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

    if (!sourceNode || !targetNode) {
      return;
    }
    outgoingByNode.get(edge.source)?.push(edge);
    incomingByNode.get(edge.target)?.push(edge);
  });

  nodes.forEach(node => {
    if (node.data.type === 'condition') {
      const outgoingCount = edges.filter(e => e.source === node.id).length;
      if (outgoingCount < 2) {
        if (!nodeErrors[node.id]) {
          nodeErrors[node.id] = [];
        }
        nodeErrors[node.id].push('条件节点应至少有 2 条输出连接');
      }
    }
  });

  const appendNodeError = (nodeId: string, message: string) => {
    if (!nodeErrors[nodeId]) {
      nodeErrors[nodeId] = [];
    }
    if (!nodeErrors[nodeId].includes(message)) {
      nodeErrors[nodeId].push(message);
    }
  };

  const startNode = startNodes.length === 1 ? startNodes[0] : null;
  const endNode = endNodes.length === 1 ? endNodes[0] : null;

  if (startNode) {
    if ((incomingByNode.get(startNode.id) || []).length > 0) {
      appendNodeError(startNode.id, '开始节点不能有输入连接');
    }
    if ((outgoingByNode.get(startNode.id) || []).length === 0) {
      appendNodeError(startNode.id, '开始节点至少需要一条输出连接');
    }
  }

  if (endNode) {
    if ((incomingByNode.get(endNode.id) || []).length === 0) {
      appendNodeError(endNode.id, '结束节点至少需要一条输入连接');
    }
    if ((outgoingByNode.get(endNode.id) || []).length > 0) {
      appendNodeError(endNode.id, '结束节点不能有输出连接');
    }
  }

  const bfsReachable = (seeds: string[], direction: 'forward' | 'reverse'): Set<string> => {
    const visited = new Set<string>();
    const queue: string[] = [...seeds];
    while (queue.length > 0) {
      const current = queue.shift();
      if (!current || visited.has(current) || !nodeIdSet.has(current)) {
        continue;
      }
      visited.add(current);
      const linkedEdges = direction === 'forward'
        ? (outgoingByNode.get(current) || [])
        : (incomingByNode.get(current) || []);
      linkedEdges.forEach((edge) => {
        const next = direction === 'forward' ? edge.target : edge.source;
        if (!visited.has(next)) {
          queue.push(next);
        }
      });
    }
    return visited;
  };

  if (startNode && endNode) {
    const reachableFromStart = bfsReachable([startNode.id], 'forward');
    if (!reachableFromStart.has(endNode.id)) {
      globalErrors.push('工作流必须存在从开始节点到结束节点的执行路径');
    }

    nodes.forEach((node) => {
      if (!reachableFromStart.has(node.id)) {
        appendNodeError(node.id, '节点不可从开始节点到达');
      }
    });

    const canReachEnd = bfsReachable([endNode.id], 'reverse');
    nodes.forEach((node) => {
      if (!canReachEnd.has(node.id)) {
        appendNodeError(node.id, '节点无法流向结束节点');
      }
    });
  }

  // Keep isolated-node detection to surface obvious wiring misses.
  nodes.forEach(node => {
    if (node.data.type === 'start' || node.data.type === 'end') {
      return;
    }
    const hasIncoming = (incomingByNode.get(node.id) || []).length > 0;
    const hasOutgoing = (outgoingByNode.get(node.id) || []).length > 0;
    if (!hasIncoming && !hasOutgoing) {
      appendNodeError(node.id, '节点未连接到工作流');
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

interface AutoLayoutOptions {
  startX?: number;
  startY?: number;
  columnGap?: number;
  rowGap?: number;
  direction?: 'TB' | 'LR';
}

const DEFAULT_NODE_MIN_WIDTH = 135;
const DEFAULT_NODE_MAX_WIDTH = 195;
const DEFAULT_MANUAL_NODE_MAX_WIDTH = 360;
const DEFAULT_MANUAL_NODE_MAX_HEIGHT = 960;
// Dagre graph created per-call to avoid shared mutable state
const AUTO_LAYOUT_RESET_WIDTH = DEFAULT_MANUAL_NODE_MAX_WIDTH;

const estimateNodeHeight = (node: Node<CustomNodeData>): number => {
  const data = node.data || ({} as CustomNodeData);
  const runtimeNodeHeight = Number((node as any)?.height);
  if (Number.isFinite(runtimeNodeHeight)) {
    return Math.max(120, Math.min(DEFAULT_MANUAL_NODE_MAX_HEIGHT, runtimeNodeHeight));
  }

  const dataHeight = Number((data as any).nodeHeight);
  if (Number.isFinite(dataHeight)) {
    return Math.max(120, Math.min(DEFAULT_MANUAL_NODE_MAX_HEIGHT, dataHeight));
  }

  const styleHeight = (node as any)?.style?.height;
  const parsedStyleHeight = typeof styleHeight === 'string' ? Number.parseFloat(styleHeight) : Number(styleHeight);
  if (Number.isFinite(parsedStyleHeight)) {
    return Math.max(120, Math.min(DEFAULT_MANUAL_NODE_MAX_HEIGHT, parsedStyleHeight));
  }

  let height = 84;

  if (data.runtime) {
    height += 22;
  }
  if (data.status === 'failed' && data.error) {
    height += 30;
  }
  if (data.instructions) {
    height += 20;
  }

  const chips = buildNodeParamChips(data).length;
  if (chips > 0) {
    const rows = Math.ceil(chips / 2);
    height += rows * 24 + 8;
  }

  const hasInputPreview = Boolean(
    data.startImageUrl ||
    (Array.isArray((data as any).startImageUrls) && (data as any).startImageUrls.length > 0) ||
    data.agentReferenceImageUrl ||
    data.toolReferenceImageUrl
  );
  if (hasInputPreview) {
    height += 108;
  }

  const resultText = extractTextContent(data.result).trim();
  const resultImages = extractImageUrls(data.result)
    .filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl))
    .slice(0, 6);
  const resultAudio = extractAudioUrls(data.result)
    .filter((audioUrl) => isDirectlyRenderableAudioUrl(audioUrl))
    .slice(0, 4);
  const resultVideo = extractVideoUrls(data.result)
    .filter((videoUrl) => isDirectlyRenderableVideoUrl(videoUrl))
    .slice(0, 3);
  if (resultImages.length > 0 || resultAudio.length > 0 || resultVideo.length > 0 || resultText.length > 0) {
    let resultPreviewHeight = 28; // preview card title + paddings
    if (resultImages.length > 0) {
      const visibleRows = resultImages.length > 1
        ? Math.min(2, Math.ceil(resultImages.length / 2))
        : 1;
      resultPreviewHeight += visibleRows * 68;
    }
    if (resultVideo.length > 0) {
      resultPreviewHeight += Math.min(2, resultVideo.length) * 92;
    }
    if (resultAudio.length > 0) {
      resultPreviewHeight += Math.min(3, resultAudio.length) * 42;
    }
    if (resultText.length > 0) {
      resultPreviewHeight += 30;
    }
    height += Math.min(320, Math.max(108, resultPreviewHeight));
  }

  if (data.type === 'start' || data.type === 'end') {
    height += 26;
  }

  return Math.max(120, height);
};

const estimateNodeWidth = (node: Node<CustomNodeData>): number => {
  const data = node.data || ({} as CustomNodeData);
  const runtimeNodeWidth = Number((node as any)?.width);
  if (Number.isFinite(runtimeNodeWidth)) {
    return Math.max(DEFAULT_NODE_MIN_WIDTH, Math.min(DEFAULT_MANUAL_NODE_MAX_WIDTH, runtimeNodeWidth));
  }

  const dataWidth = Number((data as any).nodeWidth);
  if (Number.isFinite(dataWidth)) {
    return Math.max(DEFAULT_NODE_MIN_WIDTH, Math.min(DEFAULT_MANUAL_NODE_MAX_WIDTH, dataWidth));
  }

  const styleWidth = (node as any)?.style?.width;
  const parsedStyleWidth = typeof styleWidth === 'string' ? Number.parseFloat(styleWidth) : Number(styleWidth);
  if (Number.isFinite(parsedStyleWidth)) {
    return Math.max(DEFAULT_NODE_MIN_WIDTH, Math.min(DEFAULT_MANUAL_NODE_MAX_WIDTH, parsedStyleWidth));
  }

  const chips = buildNodeParamChips(data);
  const longestChipText = chips.reduce((longest, chip) => Math.max(longest, String(chip || '').length), 0);
  const titleLength = String(data.label || '').length;
  const descriptionLength = String(data.description || '').length;
  const longest = Math.max(titleLength, descriptionLength, longestChipText);
  const extraWidth = Math.min(120, Math.max(0, longest - 12) * 4);
  const estimatedWidth = DEFAULT_NODE_MIN_WIDTH + extraWidth;
  return Math.max(DEFAULT_NODE_MIN_WIDTH, Math.min(DEFAULT_NODE_MAX_WIDTH, estimatedWidth));
};

export const estimateWorkflowNodeSize = (node: Node<CustomNodeData>) => ({
  width: estimateNodeWidth(node),
  height: estimateNodeHeight(node),
});

const normalizeNodeForAutoLayout = (node: Node<CustomNodeData>): Node<CustomNodeData> => {
  const nextData = {
    ...(node.data || ({} as CustomNodeData)),
    nodeWidth: AUTO_LAYOUT_RESET_WIDTH,
  } as CustomNodeData;

  return {
    ...(node as any),
    // Ignore runtime measured width so auto-layout always re-bases to 360.
    width: undefined,
    data: nextData,
    style: {
      ...((node as any)?.style || {}),
      width: AUTO_LAYOUT_RESET_WIDTH,
    },
  } as Node<CustomNodeData>;
};

const getLayoutedElements = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
  options: AutoLayoutOptions = {},
): { nodes: Node<CustomNodeData>[]; edges: Edge[] } => {
  const {
    startX = 80,
    startY = 80,
    columnGap = 120,
    rowGap = 36,
    direction = 'LR',
  } = options;
  const isHorizontal = direction === 'LR';
  const normalizedNodes = nodes.map((node) => normalizeNodeForAutoLayout(node));

  const dagreGraph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: direction,
    align: 'UL',
    ranksep: Math.max(120, columnGap),
    nodesep: Math.max(72, rowGap),
    edgesep: Math.max(24, Math.floor(rowGap * 0.8)),
    marginx: 0,
    marginy: 0,
  });

  normalizedNodes.forEach((node) => {
    const { width, height } = estimateWorkflowNodeSize(node);
    dagreGraph.setNode(String(node.id), { width, height });
  });

  edges.forEach((edge) => {
    const sourceId = String(edge.source || '').trim();
    const targetId = String(edge.target || '').trim();
    if (!sourceId || !targetId || sourceId === targetId) {
      return;
    }
    dagreGraph.setEdge(sourceId, targetId);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = normalizedNodes.map((node) => {
    const nodeId = String(node.id);
    const nodeWithPosition = dagreGraph.node(nodeId);
    if (!nodeWithPosition || !Number.isFinite(nodeWithPosition.x) || !Number.isFinite(nodeWithPosition.y)) {
      return node;
    }

    const { width, height } = estimateWorkflowNodeSize(node);
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      position: {
        // Dagre anchor is center; React Flow node anchor is top-left.
        x: nodeWithPosition.x - width / 2 + startX,
        y: nodeWithPosition.y - height / 2 + startY,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

/**
 * Auto layout workflow nodes by graph levels
 */
export const autoLayoutWorkflow = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
  options: AutoLayoutOptions = {}
): Node<CustomNodeData>[] => {
  if (nodes.length === 0) {
    return nodes;
  }

  const { nodes: layoutedNodes } = getLayoutedElements(nodes, edges, {
    ...options,
    direction: options.direction || 'LR',
  });
  return layoutedNodes;
};
