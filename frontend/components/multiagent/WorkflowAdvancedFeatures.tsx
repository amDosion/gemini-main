/**
 * Workflow Advanced Features
 * 
 * Provides advanced workflow management features:
 * - Import/Export workflows
 * - Undo/Redo functionality
 * - Keyboard shortcuts
 * - Workflow validation
 */

import React, { useCallback, useEffect, useRef } from 'react';
import { Node, Edge } from 'reactflow';
import { Download, Upload, Undo, Redo, Keyboard } from 'lucide-react';
import { CustomNodeData } from './CustomNode';
import { exportWorkflow, importWorkflow, validateWorkflow } from './workflowUtils';
import { useToastContext } from '../../contexts/ToastContext';

interface WorkflowAdvancedFeaturesProps {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  onNodesChange: (nodes: Node<CustomNodeData>[]) => void;
  onEdgesChange: (edges: Edge[]) => void;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
}

export const WorkflowAdvancedFeatures: React.FC<WorkflowAdvancedFeaturesProps> = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
}) => {
  const { showSuccess, showError } = useToastContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showShortcuts, setShowShortcuts] = React.useState(false);

  // Export workflow to JSON file
  const handleExport = useCallback(() => {
    try {
      const json = exportWorkflow(nodes, edges);
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `workflow-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      showError('导出失败：' + (error as Error).message);
    }
  }, [nodes, edges]);

  // Import workflow from JSON file
  const handleImport = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const json = e.target?.result as string;
        const { nodes: importedNodes, edges: importedEdges } = importWorkflow(json);
        
        // Validate imported workflow
        const validation = validateWorkflow(importedNodes, importedEdges);
        if (!validation.isValid) {
          const allErrors = [
            ...validation.globalErrors,
            ...validation.edgeErrors,
            ...Object.values(validation.nodeErrors).flat(),
          ];
          const proceed = confirm(
            `工作流存在问题：\n${allErrors.join('\n')}\n\n是否继续导入？`
          );
          if (!proceed) return;
        }

        onNodesChange(importedNodes);
        onEdgesChange(importedEdges);
        showSuccess('工作流导入成功！');
      } catch (error) {
        showError('导入失败：' + (error as Error).message);
      }
    };
    reader.readAsText(file);

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [onNodesChange, onEdgesChange]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ctrl/Cmd + Z: Undo
      if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        onUndo?.();
      }
      
      // Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y: Redo
      if (
        ((event.ctrlKey || event.metaKey) && event.key === 'z' && event.shiftKey) ||
        ((event.ctrlKey || event.metaKey) && event.key === 'y')
      ) {
        event.preventDefault();
        onRedo?.();
      }

      // Ctrl/Cmd + E: Export
      if ((event.ctrlKey || event.metaKey) && event.key === 'e') {
        event.preventDefault();
        handleExport();
      }

      // Ctrl/Cmd + I: Import
      if ((event.ctrlKey || event.metaKey) && event.key === 'i') {
        event.preventDefault();
        fileInputRef.current?.click();
      }

      // Ctrl/Cmd + /: Show shortcuts
      if ((event.ctrlKey || event.metaKey) && event.key === '/') {
        event.preventDefault();
        setShowShortcuts((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onUndo, onRedo, handleExport]);

  return (
    <>
      {/* Toolbar Buttons */}
      <div className="flex items-center gap-2">
        {/* Undo */}
        <button
          onClick={onUndo}
          disabled={!canUndo}
          title="撤销 (Ctrl+Z)"
          className="
            px-3 py-1.5 text-xs font-medium 
            bg-white hover:bg-gray-50 
            border border-gray-300 text-gray-700 
            rounded transition-colors 
            flex items-center gap-1
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          <Undo size={14} />
          撤销
        </button>

        {/* Redo */}
        <button
          onClick={onRedo}
          disabled={!canRedo}
          title="重做 (Ctrl+Shift+Z)"
          className="
            px-3 py-1.5 text-xs font-medium 
            bg-white hover:bg-gray-50 
            border border-gray-300 text-gray-700 
            rounded transition-colors 
            flex items-center gap-1
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          <Redo size={14} />
          重做
        </button>

        {/* Export */}
        <button
          onClick={handleExport}
          disabled={nodes.length === 0}
          title="导出工作流 (Ctrl+E)"
          className="
            px-3 py-1.5 text-xs font-medium 
            bg-white hover:bg-gray-50 
            border border-gray-300 text-gray-700 
            rounded transition-colors 
            flex items-center gap-1
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          <Download size={14} />
          导出
        </button>

        {/* Import */}
        <button
          onClick={() => fileInputRef.current?.click()}
          title="导入工作流 (Ctrl+I)"
          className="
            px-3 py-1.5 text-xs font-medium 
            bg-white hover:bg-gray-50 
            border border-gray-300 text-gray-700 
            rounded transition-colors 
            flex items-center gap-1
          "
        >
          <Upload size={14} />
          导入
        </button>

        {/* Shortcuts Help */}
        <button
          onClick={() => setShowShortcuts(!showShortcuts)}
          title="快捷键 (Ctrl+/)"
          className="
            px-3 py-1.5 text-xs font-medium 
            bg-white hover:bg-gray-50 
            border border-gray-300 text-gray-700 
            rounded transition-colors 
            flex items-center gap-1
          "
        >
          <Keyboard size={14} />
          快捷键
        </button>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        onChange={handleImport}
        className="hidden"
      />

      {/* Shortcuts Modal */}
      {showShortcuts && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={() => setShowShortcuts(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-800">键盘快捷键</h3>
              <button
                onClick={() => setShowShortcuts(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <ShortcutItem keys={['Ctrl', 'Z']} description="撤销上一步操作" />
              <ShortcutItem keys={['Ctrl', 'Shift', 'Z']} description="重做" />
              <ShortcutItem keys={['Ctrl', 'Y']} description="重做（备选）" />
              <ShortcutItem keys={['Ctrl', 'E']} description="导出工作流" />
              <ShortcutItem keys={['Ctrl', 'I']} description="导入工作流" />
              <ShortcutItem keys={['Ctrl', '/']} description="显示/隐藏快捷键" />
              <ShortcutItem keys={['Delete']} description="删除选中节点" />
              <ShortcutItem keys={['Ctrl', 'A']} description="全选节点" />
            </div>

            <div className="mt-4 pt-4 border-t border-gray-200">
              <p className="text-xs text-gray-500">
                💡 提示：在 Mac 上使用 Cmd 代替 Ctrl
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

// Shortcut item component
const ShortcutItem: React.FC<{ keys: string[]; description: string }> = ({
  keys,
  description,
}) => (
  <div className="flex items-center justify-between">
    <span className="text-sm text-gray-700">{description}</span>
    <div className="flex items-center gap-1">
      {keys.map((key, index) => (
        <React.Fragment key={index}>
          {index > 0 && <span className="text-gray-400 text-xs">+</span>}
          <kbd className="px-2 py-1 text-xs font-mono bg-gray-100 border border-gray-300 rounded">
            {key}
          </kbd>
        </React.Fragment>
      ))}
    </div>
  </div>
);

export default WorkflowAdvancedFeatures;
