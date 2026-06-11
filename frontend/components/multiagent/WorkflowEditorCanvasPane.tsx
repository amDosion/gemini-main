import React from 'react';
import ReactFlow, {
  Background,
  Connection,
  Controls,
  Edge,
  EdgeChange,
  MiniMap,
  Node,
  NodeChange,
  ReactFlowInstance,
} from 'reactflow';
import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import type { WorkflowNodeData } from './types';
import { ComponentLibrary } from './ComponentLibrary';
import { PropertiesPanel } from './PropertiesPanel';
import { FLOW_NODE_TYPES, type WorkflowNodeFieldFocusRequest } from './workflowEditorUtils';
import { DEFAULT_WORKFLOW_EDGE_TYPE, FLOW_EDGE_TYPES } from './workflowEdgeTypes';
import { resolveNodeMiniMapColor } from './workflowNodeAppearance';

const FLOW_DEFAULT_EDGE_OPTIONS = {
  type: DEFAULT_WORKFLOW_EDGE_TYPE,
  animated: true,
  style: { stroke: '#14b8a6', strokeWidth: 2 },
} as const;

// Module-level so MiniMap receives a stable reference across renders.
const resolveMiniMapNodeColor = (node: Node): string => {
  const data = node.data as WorkflowNodeData;
  const config = nodeTypeConfigs[data.type as NodeType] || nodeTypeConfigs.agent;
  return resolveNodeMiniMapColor(data, config);
};

interface WorkflowEditorCanvasPaneProps {
  reactFlowWrapperRef: React.RefObject<HTMLDivElement | null>;
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
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
  // 不要用 useMemo 包装——这些已经是 module-level 常量，直接传引用最稳定。
  //
  // 然而 ReactFlow 11.11.4 的 useNodeOrEdgeTypes 内部有个反向 bug:
  //   if (shallow(typesKeysRef.current, typeKeys)) { onError?.('002', ...) }
  // 这意味着 keys 集合**相等**时才报警（应该是 !shallow 表示 keys 变化时报警）。
  // 在 React 19 dev StrictMode 双 mount 下，第二次 mount 见到同样的 keys
  // → shallow=true → 触发 002 警告。这是上游 bug，不是我们的问题。
  //
  // 修法：通过 onError 拦截 002 错误码，让 ReactFlow 沉默这条误报，
  // 其他错误（001 / 003+）按默认行为打印。
  const handleReactFlowError = React.useCallback((id: string, message: string) => {
    if (id === '002') return; // 上游 bug 误报，已确认我们传的是 module-level 常量
    console.warn(`[React Flow ${id}] ${message}`);
  }, []);

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
          nodeTypes={FLOW_NODE_TYPES}
          edgeTypes={FLOW_EDGE_TYPES}
          onError={handleReactFlowError}
          isValidConnection={isValidConnection}
          fitView
          deleteKeyCode={null}
          attributionPosition="bottom-left"
          defaultEdgeOptions={FLOW_DEFAULT_EDGE_OPTIONS}
          style={{ backgroundColor: '#0f172a' }}
        >
          <Background color="#1e293b" gap={20} size={1} />
          <Controls className="!bg-slate-800 !border-slate-700 !rounded-lg [&>button]:!bg-slate-800 [&>button]:!border-slate-700 [&>button]:!text-slate-400 [&>button:hover]:!bg-slate-700" />
          <MiniMap
            style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            maskColor="rgba(0, 0, 0, 0.3)"
            nodeColor={resolveMiniMapNodeColor}
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
