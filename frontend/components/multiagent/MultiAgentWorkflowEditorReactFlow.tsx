/**
 * Multi-Agent Workflow Editor - React Flow Implementation
 * 
 * A complete visual workflow editor built with React Flow featuring:
 * - Drag-and-drop node composition from component library
 * - Node connection with visible blue handles
 * - Properties panel for node editing
 * - Execution log panel
 * - Template management (load/save)
 * - Real-time execution status updates
 */

import React, { useState, useCallback, useRef, useMemo } from 'react';
import ReactFlow, {
  Node,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  ReactFlowInstance,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Play, Save, FolderOpen, FileText, Undo2, Redo2, StopCircle, Trash2 } from 'lucide-react';

import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import { CustomNode } from './CustomNode';
import { ComponentLibrary } from './ComponentLibrary';
import { PropertiesPanel } from './PropertiesPanel';
import { ExecutionLogPanel } from './ExecutionLogPanel';
import { WorkflowTemplateSelector } from './WorkflowTemplateSelector';
import { WorkflowTemplateSaveDialog } from './WorkflowTemplateSaveDialog';
import { useWorkflowExecution, useExecutionLogs } from './WorkflowExecutionHooks';
import { useUndoRedo } from './useUndoRedo';
import type { ExecutionStatus, WorkflowNode, WorkflowEdge, WorkflowNodeData } from './types';

interface MultiAgentWorkflowEditorReactFlowProps {
  onExecute?: (workflow: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }) => void;
  onSave?: (workflow: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }) => void;
  executionStatus?: ExecutionStatus;
}

const MultiAgentWorkflowEditorReactFlowInner: React.FC<MultiAgentWorkflowEditorReactFlowProps> = ({
  onExecute,
  onSave,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);
  
  // UI state
  const [selectedNode, setSelectedNode] = useState<Node<WorkflowNodeData> | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [showTemplateSave, setShowTemplateSave] = useState(false);

  // Workflow execution hooks
  const { executeWorkflow, retryNode, isExecuting, cancelExecution } = useWorkflowExecution(
    (nodeStatuses) => {
      // Update nodes with execution status
      setNodes((nds) =>
        nds.map((node) => {
          const status = nodeStatuses[node.id];
          if (status) {
            return {
              ...node,
              data: {
                ...node.data,
                ...status,
              },
            };
          }
          return node;
        })
      );
    }
  );

  const { logs, addLog, clearLogs } = useExecutionLogs();

  // Undo/Redo functionality
  const { undo, redo, canUndo, canRedo, takeSnapshot } = useUndoRedo();

  // Handle undo
  const handleUndo = useCallback(() => {
    const state = undo();
    if (state) {
      setNodes(state.nodes);
      setEdges(state.edges);
    }
  }, [undo, setNodes, setEdges]);

  // Handle redo
  const handleRedo = useCallback(() => {
    const state = redo();
    if (state) {
      setNodes(state.nodes);
      setEdges(state.edges);
    }
  }, [redo, setNodes, setEdges]);

  // Register custom node types
  const nodeTypes = useMemo(() => ({
    start: CustomNode,
    end: CustomNode,
    agent: CustomNode,
    tool: CustomNode,
    human: CustomNode,
    router: CustomNode,
    parallel: CustomNode,
    condition: CustomNode,
    merge: CustomNode,
    loop: CustomNode,
  }), []);

  // Connection validation - prevent invalid connections
  const isValidConnection = useCallback(
    (connection: Connection) => {
      const { source, target } = connection;
      if (!source || !target) return false;
      
      // Prevent self-connections
      if (source === target) return false;
      
      // Find source and target nodes
      const sourceNode = nodes.find(n => n.id === source);
      const targetNode = nodes.find(n => n.id === target);
      if (!sourceNode || !targetNode) return false;
      
      // Prevent connecting to start node (no inputs)
      if (targetNode.data.type === 'start') return false;
      
      // Prevent connecting from end node (no outputs)
      if (sourceNode.data.type === 'end') return false;
      
      // Prevent duplicate connections
      const existingConnection = edges.find(
        e => e.source === source && e.target === target
      );
      if (existingConnection) return false;
      
      return true;
    },
    [nodes, edges]
  );

  // Handle node connection
  const onConnect = useCallback(
    (params: Connection) => {
      takeSnapshot(nodes, edges);
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges, takeSnapshot, nodes, edges]
  );

  // Handle node click to show properties panel
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNode(node as Node<WorkflowNodeData>);
    },
    []
  );

  // Handle node update from properties panel
  const handleUpdateNode = useCallback(
    (nodeId: string, updates: Partial<WorkflowNodeData>) => {
      setNodes((nds) =>
        nds.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, ...updates } }
            : node
        )
      );
      
      // Update selected node state
      setSelectedNode((prev) =>
        prev && prev.id === nodeId
          ? { ...prev, data: { ...prev.data, ...updates } }
          : prev
      );
    },
    [setNodes]
  );

  // Handle workflow execution
  const handleExecute = useCallback(async () => {
    addLog('system', '系统', 'info', '开始执行工作流...');
    onExecute?.({ nodes: nodes as WorkflowNode[], edges: edges as WorkflowEdge[] });

    try {
      await executeWorkflow({ nodes, edges });
      addLog('system', '系统', 'info', '工作流执行完成');
    } catch (error) {
      addLog('system', '系统', 'error', `工作流执行失败: ${error}`);
    }
  }, [nodes, edges, executeWorkflow, addLog, onExecute]);

  // Handle cancel execution
  const handleCancelExecution = useCallback(() => {
    cancelExecution();
    addLog('system', '系统', 'info', '工作流执行已取消');
  }, [cancelExecution, addLog]);

  // Handle clear logs
  const handleClearLogs = useCallback(() => {
    clearLogs();
  }, [clearLogs]);

  // Handle template load
  const handleLoadTemplate = useCallback(
    (template: any) => {
      setNodes(template.config.nodes || []);
      setEdges(template.config.edges || []);
      setShowTemplateSelector(false);
      addLog('system', '系统', 'info', `已加载模板: ${template.name}`);
    },
    [setNodes, setEdges, addLog]
  );

  // Handle template save success
  const handleTemplateSaved = useCallback(
    (template: any) => {
      setShowTemplateSave(false);
      addLog('system', '系统', 'info', `已保存模板: ${template.name}`);
      onSave?.({ nodes: nodes as WorkflowNode[], edges: edges as WorkflowEdge[] });
    },
    [addLog, onSave, nodes, edges]
  );

  // Handle drag over for drop functionality
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // Handle drop to create new node
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow') as NodeType;
      if (!type || !reactFlowInstance) return;

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const config = nodeTypeConfigs[type];
      const newNode: Node<WorkflowNodeData> = {
        id: `node-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        type: config.type, // Use the node type from config
        position,
        data: {
          label: config.label,
          description: config.description,
          icon: config.icon,
          iconColor: config.iconColor,
          type: config.type,
        },
      };

      takeSnapshot(nodes, edges);
      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance, setNodes]
  );

  return (
    <div className="flex flex-col h-full bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
      {/* Top Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-800">多智能体工作流编排</span>
          <span className="text-xs text-gray-500">
            {nodes.length} 个节点, {edges.length} 个连接
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTemplateSelector(true)}
            className="px-3 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded transition-colors flex items-center gap-1"
          >
            <FolderOpen size={14} />
            加载模板
          </button>
          <button
            onClick={() => setShowTemplateSave(true)}
            disabled={nodes.length === 0}
            className="px-3 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save size={14} />
            保存模板
          </button>
          <button
            onClick={handleUndo}
            disabled={!canUndo}
            className="px-2 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="撤销 (Ctrl+Z)"
          >
            <Undo2 size={14} />
          </button>
          <button
            onClick={handleRedo}
            disabled={!canRedo}
            className="px-2 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="重做 (Ctrl+Y)"
          >
            <Redo2 size={14} />
          </button>
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="px-3 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded transition-colors flex items-center gap-1"
          >
            <FileText size={14} />
            {showLogs ? '隐藏日志' : '显示日志'}
          </button>
          {showLogs && (
            <button
              onClick={handleClearLogs}
              className="px-2 py-1.5 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 rounded transition-colors"
              title="清除日志"
            >
              <Trash2 size={14} />
            </button>
          )}
          {isExecuting ? (
            <button
              onClick={handleCancelExecution}
              className="px-3 py-1.5 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded transition-colors flex items-center gap-1"
            >
              <StopCircle size={14} />
              取消执行
            </button>
          ) : (
            <button
              onClick={handleExecute}
              disabled={nodes.length === 0}
              className="px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed text-white rounded transition-colors flex items-center gap-1"
            >
              <Play size={14} />
              执行工作流
            </button>
          )}
        </div>
      </div>

      {/* Main Content: Component Library + Canvas + Properties Panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Component Library Panel */}
        <ComponentLibrary />

        {/* React Flow Canvas */}
        <div ref={reactFlowWrapper} className="flex-1 bg-gray-50 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onInit={setReactFlowInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            isValidConnection={isValidConnection}
            fitView
            attributionPosition="bottom-left"
          >
            <Background color="#e5e7eb" gap={16} />
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                const data = node.data as WorkflowNodeData;
                const config = nodeTypeConfigs[data.type];
                // Convert Tailwind class to hex color
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
                return colorMap[config?.iconColor] || '#9ca3af';
              }}
            />
          </ReactFlow>

          {/* Empty state message */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center text-gray-500">
                <p className="text-sm">从左侧组件库拖拽节点到画布</p>
                <p className="text-xs mt-2 text-gray-400">连接节点创建工作流</p>
              </div>
            </div>
          )}
        </div>

        {/* Properties Panel (shown when node is selected) */}
        {selectedNode && (
          <PropertiesPanel
            selectedNode={selectedNode}
            onClose={() => setSelectedNode(null)}
            onUpdateNode={handleUpdateNode}
            onRetry={(nodeId) => retryNode(nodeId)}
          />
        )}
      </div>

      {/* Execution Log Panel (bottom, toggleable) */}
      {showLogs && (
        <ExecutionLogPanel
          logs={logs}
          isOpen={showLogs}
          onClose={() => setShowLogs(false)}
        />
      )}

      {/* Template Selector Dialog */}
      <WorkflowTemplateSelector
        isOpen={showTemplateSelector}
        onClose={() => setShowTemplateSelector(false)}
        onLoadTemplate={handleLoadTemplate}
      />

      {/* Template Save Dialog */}
      <WorkflowTemplateSaveDialog
        isOpen={showTemplateSave}
        onClose={() => setShowTemplateSave(false)}
        nodes={nodes}
        edges={edges}
        onSaveSuccess={handleTemplateSaved}
      />
    </div>
  );
};

// Wrap with ReactFlowProvider
export const MultiAgentWorkflowEditorReactFlow: React.FC<MultiAgentWorkflowEditorReactFlowProps> = (props) => {
  return (
    <ReactFlowProvider>
      <MultiAgentWorkflowEditorReactFlowInner {...props} />
    </ReactFlowProvider>
  );
};

export default MultiAgentWorkflowEditorReactFlow;
