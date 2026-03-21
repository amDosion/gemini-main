import React from 'react';
import ReactFlow, {
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  ReactFlowInstance,
} from 'reactflow';
import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import type { WorkflowNodeData } from './types';
import { ComponentLibrary } from './ComponentLibrary';
import { PropertiesPanel } from './PropertiesPanel';
import { FLOW_NODE_TYPES, type WorkflowNodeFieldFocusRequest } from './workflowEditorUtils';
import { DEFAULT_WORKFLOW_EDGE_TYPE, FLOW_EDGE_TYPES } from './workflowEdgeTypes';

const FLOW_DEFAULT_EDGE_OPTIONS = {
  type: DEFAULT_WORKFLOW_EDGE_TYPE,
  animated: true,
  style: { stroke: '#14b8a6', strokeWidth: 2 },
} as const;

interface WorkflowEditorCanvasPaneProps {
  reactFlowWrapperRef: React.RefObject<HTMLDivElement | null>;
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  onNodesChange: (changes: import("reactflow").NodeChange[]) => void;
  onEdgesChange: (changes: import("reactflow").EdgeChange[]) => void;
  onConnect: (params: Connection) => void;
  onNodeClick: (_event: React.MouseEvent, node: Node) => void;
  onEdgeClick: (_event: React.MouseEvent, edge: Edge) => void;
  onPaneClick: () => void;
  onInit: (instance: ReactFlowInstance) => void;
  onDrop: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  isValidConnection: (connection: Connection) => boolean;
  selectedNode: Node<WorkflowNodeData> | null;
  onCloseSelectedNode: () => void;
  onUpdateNode: (nodeId: string, updates: Partial<WorkflowNodeData>) => void;
  onDeleteNode: (nodeId: string) => void;
  focusRequest: WorkflowNodeFieldFocusRequest | null;
  onConsumeFocusRequest?: (token: string) => void;
}

export const WorkflowEditorCanvasPane: React.FC<WorkflowEditorCanvasPaneProps> = ({
  reactFlowWrapperRef,
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onEdgeClick,
  onPaneClick,
  onInit,
  onDrop,
  onDragOver,
  isValidConnection,
  selectedNode,
  onCloseSelectedNode,
  onUpdateNode,
  onDeleteNode,
  focusRequest,
  onConsumeFocusRequest,
}) => {
  const stableNodeTypes = React.useMemo(() => FLOW_NODE_TYPES, []);
  const stableEdgeTypes = React.useMemo(() => FLOW_EDGE_TYPES, []);
  const stableDefaultEdgeOptions = React.useMemo(() => FLOW_DEFAULT_EDGE_OPTIONS, []);

  return (
    <div className="flex flex-1 overflow-hidden relative">
      <ComponentLibrary />

      <div ref={reactFlowWrapperRef} className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={onPaneClick}
          onInit={onInit}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={stableNodeTypes}
          edgeTypes={stableEdgeTypes}
          isValidConnection={isValidConnection}
          fitView
          deleteKeyCode={null}
          attributionPosition="bottom-left"
          defaultEdgeOptions={stableDefaultEdgeOptions}
          style={{ backgroundColor: '#0f172a' }}
        >
          <Background color="#1e293b" gap={20} size={1} />
          <Controls className="!bg-slate-800 !border-slate-700 !rounded-lg [&>button]:!bg-slate-800 [&>button]:!border-slate-700 [&>button]:!text-slate-400 [&>button:hover]:!bg-slate-700" />
          <MiniMap
            style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            maskColor="rgba(0, 0, 0, 0.3)"
            nodeColor={(node) => {
              const data = node.data as WorkflowNodeData;
              const config = nodeTypeConfigs[data.type as NodeType] || nodeTypeConfigs.agent;
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
                'bg-cyan-500': '#06b6d4',
                'bg-amber-500': '#f59e0b',
                'bg-violet-500': '#8b5cf6',
              };
              return colorMap[config?.iconColor] || '#475569';
            }}
          />
        </ReactFlow>

        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center">
              <div className="text-4xl mb-3 opacity-30">🔗</div>
              <p className="text-sm text-slate-500">从左侧拖拽节点到画布</p>
              <p className="text-xs mt-1.5 text-slate-600">连接节点构建工作流</p>
            </div>
          </div>
        )}
      </div>

      {selectedNode && (
        <PropertiesPanel
          selectedNode={selectedNode}
          onClose={onCloseSelectedNode}
          onUpdateNode={onUpdateNode}
          onDeleteNode={onDeleteNode}
          focusRequest={focusRequest}
          onConsumeFocusRequest={onConsumeFocusRequest}
        />
      )}
    </div>
  );
};
