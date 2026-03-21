import React from 'react';
import {
  AlertTriangle,
  Download,
  Eye,
  FolderOpen,
  LayoutGrid,
  Maximize2,
  MessageSquare,
  Minimize2,
  Redo2,
  Save,
  Trash2,
  Undo2,
  X,
} from 'lucide-react';

interface WorkflowEditorTopBarProps {
  nodesCount: number;
  edgesCount: number;
  selectedNodeLabel: string | null;
  activeTemplateName?: string | null;
  templateSaveLabel?: string;
  templateSaveTitle?: string;
  onOpenTemplateSelector: () => void;
  onOpenTemplateSave: () => void;
  canSaveTemplate: boolean;
  onClearCanvas: () => void;
  canClearCanvas: boolean;
  onUndo: () => void;
  canUndo: boolean;
  onRedo: () => void;
  canRedo: boolean;
  onDeleteSelectedNode: () => void;
  canDeleteSelectedNode: boolean;
  onAutoLayout: () => void;
  canAutoLayout: boolean;
  onToggleResultPanel: () => void;
  canToggleResultPanel: boolean;
  showResultPanel: boolean;
  onExportImage: () => void | Promise<void>;
  canExportImage: boolean;
  isExportingImage: boolean;
  onToggleFullscreen: () => void;
  isFullscreen: boolean;
  onExit?: () => void;
  executeErrorBanner: string | null;
  onDismissExecuteErrorBanner: () => void;
}

export const WorkflowEditorTopBar: React.FC<WorkflowEditorTopBarProps> = ({
  nodesCount,
  edgesCount,
  selectedNodeLabel,
  activeTemplateName,
  templateSaveLabel = '保存',
  templateSaveTitle,
  onOpenTemplateSelector,
  onOpenTemplateSave,
  canSaveTemplate,
  onClearCanvas,
  canClearCanvas,
  onUndo,
  canUndo,
  onRedo,
  canRedo,
  onDeleteSelectedNode,
  canDeleteSelectedNode,
  onAutoLayout,
  canAutoLayout,
  onToggleResultPanel,
  canToggleResultPanel,
  showResultPanel,
  onExportImage,
  canExportImage,
  isExportingImage,
  onToggleFullscreen,
  isFullscreen,
  onExit,
  executeErrorBanner,
  onDismissExecuteErrorBanner,
}) => {
  const groupedButtonClass =
    'h-8 px-2.5 text-xs text-slate-300 hover:bg-slate-800/80 transition-colors flex items-center gap-1 border-r border-slate-700/80 last:border-r-0 disabled:opacity-40 disabled:hover:bg-transparent';
  const groupedIconButtonClass =
    'h-8 w-8 text-xs text-slate-400 hover:bg-slate-800/80 transition-colors flex items-center justify-center border-r border-slate-700/80 last:border-r-0 disabled:opacity-40 disabled:hover:bg-transparent';

  return (
    <>
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-slate-400">
            {nodesCount} 节点 · {edgesCount} 连接
          </span>
          <span className="text-[11px] text-slate-500">
            右键节点圆点可断开端口连接
          </span>
          {selectedNodeLabel && (
            <span className="text-[11px] px-2 py-0.5 rounded-md border border-teal-500/30 bg-teal-500/10 text-teal-300">
              已选节点：{selectedNodeLabel}
            </span>
          )}
          {activeTemplateName && (
            <span className="text-[11px] px-2 py-0.5 rounded-md border border-amber-500/30 bg-amber-500/10 text-amber-200">
              编辑模板：{activeTemplateName}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border border-slate-700/80 bg-slate-900/70 overflow-hidden">
            <button
              onClick={onOpenTemplateSelector}
              className={groupedButtonClass}
            >
              <FolderOpen size={13} /> 模板
            </button>
            <button
              onClick={onOpenTemplateSave}
              disabled={!canSaveTemplate}
              className={groupedButtonClass}
              title={templateSaveTitle}
            >
              <Save size={13} /> {templateSaveLabel}
            </button>
            <button
              onClick={onClearCanvas}
              disabled={!canClearCanvas}
              className={groupedButtonClass}
              title="清除当前画布内容"
            >
              <Trash2 size={13} /> 清空
            </button>
          </div>

          <div className="flex items-center rounded-lg border border-slate-700/80 bg-slate-900/70 overflow-hidden">
            <button
              onClick={onUndo}
              disabled={!canUndo}
              className={groupedIconButtonClass}
              title="撤销"
            >
              <Undo2 size={13} />
            </button>
            <button
              onClick={onRedo}
              disabled={!canRedo}
              className={groupedIconButtonClass}
              title="重做"
            >
              <Redo2 size={13} />
            </button>
            <button
              onClick={onDeleteSelectedNode}
              disabled={!canDeleteSelectedNode}
              className={groupedIconButtonClass}
              title="删除选中节点"
            >
              <Trash2 size={13} />
            </button>
          </div>

          <div className="flex items-center rounded-lg border border-slate-700/80 bg-slate-900/70 overflow-hidden">
            <button
              onClick={onAutoLayout}
              disabled={!canAutoLayout}
              className={groupedButtonClass}
              title="自动排版工作流"
            >
              <LayoutGrid size={13} /> 自动排版
            </button>
            <button
              onClick={onToggleResultPanel}
              disabled={!canToggleResultPanel}
              className={`${groupedButtonClass} ${
                showResultPanel
                  ? 'bg-indigo-600/20 text-indigo-300'
                  : 'text-slate-400'
              }`}
              title="查看最终结果"
            >
              <Eye size={13} /> 结果
            </button>
            <button
              onClick={onExportImage}
              disabled={!canExportImage || isExportingImage}
              className={groupedButtonClass}
              title="下载工作流图片"
            >
              <Download size={13} /> {isExportingImage ? '下载中' : '下载'}
            </button>
          </div>

          <div className="flex items-center rounded-lg border border-slate-700/80 bg-slate-900/70 overflow-hidden">
            <button
              onClick={onToggleFullscreen}
              className={`${groupedButtonClass} ${
                isFullscreen
                  ? 'bg-emerald-600/20 text-emerald-300'
                  : 'text-slate-400'
              }`}
              title={isFullscreen ? '退出全屏' : '全屏编辑区'}
            >
              {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              {isFullscreen ? '退出全屏' : '全屏'}
            </button>
            {onExit && (
              <button
                onClick={onExit}
                className={groupedIconButtonClass}
                title="返回聊天界面"
              >
                <MessageSquare size={13} />
              </button>
            )}
          </div>
        </div>
      </div>
      {executeErrorBanner && (
        <div className="px-4 py-2 border-b border-rose-500/30 bg-rose-500/10 text-rose-200 text-xs flex items-start justify-between gap-2">
          <div className="flex items-start gap-2 min-w-0">
            <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
            <span className="break-words">{executeErrorBanner}</span>
          </div>
          <button
            onClick={onDismissExecuteErrorBanner}
            className="p-0.5 rounded hover:bg-rose-500/20 text-rose-200/80 hover:text-rose-100 transition-colors"
            title="关闭错误提示"
          >
            <X size={12} />
          </button>
        </div>
      )}
    </>
  );
};
