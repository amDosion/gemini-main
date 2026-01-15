/**
 * React Flow Test Component
 * 
 * Comprehensive test component demonstrating all node types and statuses
 */

import React, { useEffect } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { CustomNode, CustomNodeData } from './CustomNode';
import { nodeTypeConfigs } from './nodeTypeConfigs';

// Test nodes with different types and statuses
const initialNodes: Node<CustomNodeData>[] = [
  // Row 1: Basic nodes
  {
    id: '1',
    type: 'start',
    position: { x: 50, y: 50 },
    data: {
      label: '开始节点',
      description: '工作流入口',
      icon: nodeTypeConfigs.start.icon,
      iconColor: nodeTypeConfigs.start.iconColor,
      type: 'start',
      status: 'completed',
    },
  },
  {
    id: '2',
    type: 'llm',
    position: { x: 320, y: 50 },
    data: {
      label: 'LLM 节点',
      description: '调用大语言模型',
      icon: nodeTypeConfigs.llm.icon,
      iconColor: nodeTypeConfigs.llm.iconColor,
      type: 'llm',
      status: 'running',
      progress: 65,
      agentName: 'GPT-4',
    },
  },
  {
    id: '3',
    type: 'knowledge',
    position: { x: 590, y: 50 },
    data: {
      label: '知识库节点',
      description: '检索知识库',
      icon: nodeTypeConfigs.knowledge.icon,
      iconColor: nodeTypeConfigs.knowledge.iconColor,
      type: 'knowledge',
      status: 'pending',
    },
  },
  {
    id: '4',
    type: 'agent',
    position: { x: 860, y: 50 },
    data: {
      label: '智能体节点',
      description: '调用子智能体',
      icon: nodeTypeConfigs.agent.icon,
      iconColor: nodeTypeConfigs.agent.iconColor,
      type: 'agent',
      status: 'failed',
      error: 'Connection timeout: Failed to connect to agent service',
      agentName: 'Research Agent',
    },
  },

  // Row 2: Control flow nodes
  {
    id: '5',
    type: 'condition',
    position: { x: 50, y: 250 },
    data: {
      label: '条件分支',
      description: '根据条件分支',
      icon: nodeTypeConfigs.condition.icon,
      iconColor: nodeTypeConfigs.condition.iconColor,
      type: 'condition',
      status: 'completed',
    },
  },
  {
    id: '6',
    type: 'merge',
    position: { x: 320, y: 250 },
    data: {
      label: '合并节点',
      description: '合并多个分支',
      icon: nodeTypeConfigs.merge.icon,
      iconColor: nodeTypeConfigs.merge.iconColor,
      type: 'merge',
      status: 'running',
      progress: 30,
    },
  },
  {
    id: '7',
    type: 'code',
    position: { x: 590, y: 250 },
    data: {
      label: '代码执行',
      description: '执行 Python 代码',
      icon: nodeTypeConfigs.code.icon,
      iconColor: nodeTypeConfigs.code.iconColor,
      type: 'code',
      status: 'completed',
      progress: 100,
    },
  },
  {
    id: '8',
    type: 'api',
    position: { x: 860, y: 250 },
    data: {
      label: 'API 调用',
      description: '调用外部 API',
      icon: nodeTypeConfigs.api.icon,
      iconColor: nodeTypeConfigs.api.iconColor,
      type: 'api',
      status: 'pending',
    },
  },

  // Row 3: End node
  {
    id: '9',
    type: 'end',
    position: { x: 450, y: 450 },
    data: {
      label: '结束节点',
      description: '工作流出口',
      icon: nodeTypeConfigs.end.icon,
      iconColor: nodeTypeConfigs.end.iconColor,
      type: 'end',
      status: 'pending',
    },
  },
];

// Test edges connecting nodes
const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3' },
  { id: 'e3-4', source: '3', target: '4' },
  { id: 'e5-6', source: '5', target: '6', animated: true },
  { id: 'e6-7', source: '6', target: '7' },
  { id: 'e7-8', source: '7', target: '8' },
  { id: 'e4-9', source: '4', target: '9' },
  { id: 'e8-9', source: '8', target: '9' },
];

const nodeTypes = {
  start: CustomNode,
  end: CustomNode,
  llm: CustomNode,
  knowledge: CustomNode,
  agent: CustomNode,
  condition: CustomNode,
  merge: CustomNode,
  code: CustomNode,
  api: CustomNode,
};

const ReactFlowTestInner: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState<CustomNodeData>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Simulate progress updates for running nodes
  useEffect(() => {
    const interval = setInterval(() => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.data.status === 'running' && node.data.progress !== undefined) {
            const newProgress = Math.min((node.data.progress || 0) + 5, 100);
            return {
              ...node,
              data: {
                ...node.data,
                progress: newProgress,
                status: newProgress === 100 ? 'completed' : 'running',
              },
            };
          }
          return node;
        })
      );
    }, 500);

    return () => clearInterval(interval);
  }, [setNodes]);

  return (
    <div className="w-full h-screen flex flex-col">
      {/* Header */}
      <div className="p-4 bg-white border-b border-gray-200">
        <h1 className="text-2xl font-bold text-gray-800">React Flow 节点测试</h1>
        <p className="text-sm text-gray-600 mt-1">
          展示所有节点类型和状态（pending、running、completed、failed）
        </p>
      </div>

      {/* React Flow Canvas */}
      <div className="flex-1 bg-gray-50">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-left"
        >
          <Background color="#e5e7eb" gap={16} />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              const data = node.data as CustomNodeData;
              const config = nodeTypeConfigs[data.type];
              const colorMap: Record<string, string> = {
                'bg-blue-500': '#3b82f6',
                'bg-green-500': '#22c55e',
                'bg-purple-500': '#a855f7',
                'bg-teal-500': '#14b8a6',
                'bg-yellow-500': '#eab308',
                'bg-orange-500': '#f97316',
                'bg-indigo-500': '#6366f1',
                'bg-pink-500': '#ec4899',
                'bg-red-500': '#ef4444',
              };
              return colorMap[config?.iconColor] || '#9ca3af';
            }}
          />
        </ReactFlow>
      </div>

      {/* Legend */}
      <div className="p-4 bg-white border-t border-gray-200">
        <div className="flex items-center gap-6 text-xs text-gray-600">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-gray-400"></div>
            <span>Pending</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span>Running</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span>Completed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span>Failed</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export const ReactFlowTest: React.FC = () => {
  return (
    <ReactFlowProvider>
      <ReactFlowTestInner />
    </ReactFlowProvider>
  );
};

export default ReactFlowTest;
