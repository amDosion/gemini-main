/**
 * Multi-Agent Workflow Editor - Enhanced Version
 * 
 * Complete workflow editor with all advanced features:
 * - Search and filter in component library
 * - Undo/Redo functionality
 * - Import/Export workflows
 * - Keyboard shortcuts
 * - Performance optimization
 * - Interactive tutorial
 * - Workflow validation
 */

import React, { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import ReactFlow, {
  Node,
  Edge,
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
import { Play, HelpCircle } from 'lucide-react';

import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import { CustomNode, CustomNodeData } from './CustomNode';
import { ComponentLibrary } from './ComponentLibrary';
import { PropertiesPanel } from './PropertiesPanel';
import { ExecutionLogPanel } from './ExecutionLogPanel';
import { WorkflowTemplateSelector } from './WorkflowTemplateSelector';
import { WorkflowTemplateSaveDialog } from './WorkflowTemplateSaveDialog';
import { WorkflowAdvancedFeatures } from './WorkflowAdvancedFeatures';
import { WorkflowTutorial, TutorialButton } from './WorkflowTutorial';
import { useWorkflowExecution, useExecutionLogs } from './WorkflowExecutionHooks';
import { useUndoRedo } from './useUndoRedo';
import { usePerformanceOptimization } from './usePerformanceOptimization';
import { validateWorkflow } from './workflowUtils';

type WorkflowNode = Node<CustomNodeData>;

interface MultiAgentWorkflowEditorEnhancedProps {
  onExecute?: (workflow: { nodes: WorkflowNode[]; edges: Edge[] }) => void;
  onSave?: (workflow: { nodes: WorkflowNode[]; edges: Edge[] }) => void;
  isLoading?: boolean;
}

const MultiAgentWorkflowEditorEnhancedInner: React.FC<MultiAgentWorkflowEditorEnhancedProps> = ({
  onExecute,
  onSave,
  isLoading = false,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<CustomNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);
  
  // UI state
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [showTemplateSave, setShowTemplateSave] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);

  // Undo/Redo
  const { undo, redo, canUndo, canRedo, takeSnapshot } = useUndoRedo({
    maxHistorySize: 50,
  });

  // Performance optimization
  const { metrics, isLargeWorkflow, measurePerformance } = usePerformanceOptimization(
    nodes,
    edges,
    {
      enableMetrics: true,
      largeWorkflowThreshold: 50,
    }
  );

  // Workflow execution hooks
  const { executeWorkflow, retryNode, isExecuting } = useWorkflowExecution(
    (nodeStatuses) => {
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

  const { logs, addLog } = useExecutionLogs();

  // Register custom node types
  const nodeTypes = useMemo(() => ({
    start: CustomNode,
    end: CustomNode,
    llm: CustomNode,
    knowledge: CustomNode,
    agent: CustomNode,
    condition: CustomNode,
    merge: CustomNode,
    code: CustomNode,
    api: CustomNode,
  }), []);

  // Take snapshot on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (nodes.length > 0 || edges.length > 0) {
        takeSnapshot(nodes, edges);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [nodes, edges, takeSnapshot]);

  // Show tutorial on first visit
  useEffect(() => {
    const hasSeenTutorial = localStorage.getItem('workflow-tutorial-completed');
    if (!hasSeenTutorial) {
      setShowTutorial(true);
    }
  }, []);

  // Handle node connection
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Handle node click
  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      setSelectedNode(node as WorkflowNode);
    },
    []
  );

  // Handle node update
  const handleUpdateNode = useCallback(
    (nodeId: string, updates: Partial<CustomNodeData>) => {
      setNodes((nds) =>
        nds.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, ...updates } }
            : node
        )
      );
      
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
    // Validate workflow first
    const validation = validateWorkflow(nodes, edges);
    if (!validation.isValid) {
      const allErrors = [
        ...validation.globalErrors,
        ...validation.edgeErrors,
        ...Object.values(validation.nodeErrors).flat(),
      ];
      const proceed = confirm(
        `工作流存在以下问题：\n${allErrors.join('\n')}\n\n是否继续执行？`
      );
      if (!proceed) return;
    }

    addLog('system', '系统', 'info', '开始执行工作流...');

    try {
      await executeWorkflow({ nodes, edges });
      addLog('system', '系统', 'info', '工作流执行完成');
    } catch (error) {
      addLog('system', '系统', 'error', `工作流执行失败: ${error}`);
    }
  }, [nodes, edges, executeWorkflow, addLog]);

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

  // Handle template save
  const handleTemplateSaved = useCallback(
    (template: any) => {
      setShowTemplateSave(false);
      addLog('system', '系统', 'info', `已保存模板: ${template.name}`);
    },
    [addLog]
  );

  // Handle undo
  const handleUndo = useCallback(() => {
    const previous = undo();
    if (previous && 'nodes' in previous && 'edges' in previous) {
      setNodes(previous.nodes);
      setEdges(previous.edges);
    }
  }, [undo, setNodes, setEdges]);

  // Handle redo
  const handleRedo = useCallback(() => {
    const next = redo();
    if (next && 'nodes' in next && 'edges' in next) {
      setNodes(next.nodes);
      setEdges(next.edges);
    }
  }, [redo, setNodes, setEdges]);

  // Handle drag over
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // Handle drop
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
      const newNode: WorkflowNode = {
        id: `node-${Date.now()}`,
        type: config.type,
        position,
        data: {
          label: config.label,
          description: config.description,
          icon: config.icon,
          iconColor: config.iconColor,
          type: config.type,
        },
      };

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
          {isLargeWorkflow && (
            <span className="text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded">
              ⚡ 大型工作流
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {/* Advanced Features */}
          <WorkflowAdvancedFeatures
            nodes={nodes}
            edges={edges}
            onNodesChange={setNodes}
            onEdgesChange={setEdges}
            onUndo={handleUndo}
            onRedo={handleRedo}
            canUndo={canUndo}
            canRedo={canRedo}
          />

          {/* Tutorial Button */}
          <TutorialButton onClick={() => setShowTutorial(true)} />

          {/* Execute Button */}
          <button
            onClick={handleExecute}
            disabled={isExecuting || nodes.length === 0}
            className="
              px-3 py-1.5 text-xs font-medium 
              bg-blue-600 hover:bg-blue-700 
              disabled:bg-gray-300 disabled:text-gray-500 
              disabled:cursor-not-allowed 
              text-white rounded transition-colors 
              flex items-center gap-1
            "
          >
            <Play size={14} />
            {isExecuting ? '执行中...' : '执行工作流'}
          </button>
        </div>
      </div>

      {/* Performance Metrics (dev mode) */}
      {process.env.NODE_ENV === 'development' && (
        <div className="px-3 py-1 bg-gray-100 border-b border-gray-200 text-xs text-gray-600 flex items-center gap-4">
          <span>FPS: {metrics.fps}</span>
          <span>节点: {metrics.nodeCount}</span>
          <span>边: {metrics.edgeCount}</span>
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Component Library with Search */}
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

          {/* Empty state */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center text-gray-500">
                <p className="text-sm">从左侧组件库拖拽节点到画布</p>
                <p className="text-xs mt-2 text-gray-400">或点击"帮助"查看教程</p>
              </div>
            </div>
          )}
        </div>

        {/* Properties Panel */}
        {selectedNode && (
          <PropertiesPanel
            selectedNode={selectedNode}
            onClose={() => setSelectedNode(null)}
            onUpdateNode={handleUpdateNode}
            onRetry={(nodeId) => retryNode(nodeId)}
          />
        )}
      </div>

      {/* Execution Log Panel */}
      {showLogs && (
        <ExecutionLogPanel
          logs={logs}
          isOpen={showLogs}
          onClose={() => setShowLogs(false)}
        />
      )}

      {/* Template Selector */}
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

      {/* Tutorial */}
      <WorkflowTutorial
        isOpen={showTutorial}
        onClose={() => setShowTutorial(false)}
        onComplete={() => {
          addLog('system', '系统', 'info', '教程已完成！');
        }}
      />
    </div>
  );
};

// Wrap with ReactFlowProvider
export const MultiAgentWorkflowEditorEnhanced: React.FC<MultiAgentWorkflowEditorEnhancedProps> = (props) => {
  return (
    <ReactFlowProvider>
      <MultiAgentWorkflowEditorEnhancedInner {...props} />
    </ReactFlowProvider>
  );
};

export default MultiAgentWorkflowEditorEnhanced;
