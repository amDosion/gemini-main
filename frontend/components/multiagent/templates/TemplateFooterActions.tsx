/**
 * Template Footer Actions bar
 *
 * 1:1 抽离自 `WorkflowTemplateSelector.tsx` L1192-1261
 * （< 800 行合规拆分）。
 *
 * 包含底部按钮组：复制模板 / 编辑模板 / 删除模板 / 加载到画布 / 取消。
 * disabled 状态严格匹配原 inline JSX 中的 `canManageTemplate` 与
 * `copyingTemplateId / deletingTemplateId` 联动。
 */

import React from 'react';
import { Copy, Loader2, Pencil, Trash2 } from 'lucide-react';
import { type WorkflowTemplate } from '../workflowTemplateTypes';

interface TemplateFooterActionsProps {
  selectedTemplate: WorkflowTemplate | null;
  copyingTemplateId: string | null;
  deletingTemplateId: string | null;
  canManageTemplate: (template: WorkflowTemplate | null) => boolean;
  handleCopyTemplate: () => void;
  handleEditTemplate: () => void;
  handleRequestDeleteTemplate: () => void;
  handleLoadTemplate: () => void;
  onClose: () => void;
}

export const TemplateFooterActions: React.FC<TemplateFooterActionsProps> = ({
  selectedTemplate,
  copyingTemplateId,
  deletingTemplateId,
  canManageTemplate,
  handleCopyTemplate,
  handleEditTemplate,
  handleRequestDeleteTemplate,
  handleLoadTemplate,
  onClose,
}) => {
  return (
    <div className="flex items-center justify-end p-4 border-t border-slate-700 bg-slate-900/80">
      <div className="inline-flex items-stretch rounded-lg border border-slate-700 overflow-hidden bg-slate-900">
        <button
          onClick={handleCopyTemplate}
          disabled={
            !selectedTemplate || Boolean(copyingTemplateId) || Boolean(deletingTemplateId)
          }
          className="px-3.5 py-1.5 text-xs text-slate-200 bg-slate-800 hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          {copyingTemplateId ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Copy size={13} />
          )}
          复制模板
        </button>
        <button
          onClick={handleEditTemplate}
          disabled={
            !selectedTemplate ||
            Boolean(copyingTemplateId) ||
            Boolean(deletingTemplateId) ||
            !canManageTemplate(selectedTemplate)
          }
          className="px-3.5 py-1.5 text-xs text-amber-100 bg-amber-900/30 hover:bg-amber-800/40 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          title={
            selectedTemplate && !canManageTemplate(selectedTemplate)
              ? '只读模板不可直接编辑'
              : '加载到画布并进入编辑'
          }
        >
          <Pencil size={13} />
          编辑模板
        </button>
        <button
          onClick={handleRequestDeleteTemplate}
          disabled={
            !selectedTemplate ||
            Boolean(deletingTemplateId) ||
            !canManageTemplate(selectedTemplate)
          }
          className="px-3.5 py-1.5 text-xs text-rose-200 bg-rose-900/30 hover:bg-rose-800/40 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          title={
            selectedTemplate && !canManageTemplate(selectedTemplate)
              ? '只读模板不可删除'
              : '删除模板'
          }
        >
          {deletingTemplateId ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Trash2 size={13} />
          )}
          删除模板
        </button>
        <button
          onClick={handleLoadTemplate}
          disabled={!selectedTemplate}
          className="px-3.5 py-1.5 text-xs text-white bg-teal-600 hover:bg-teal-500 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          加载到画布
        </button>
        <button
          onClick={onClose}
          className="px-3.5 py-1.5 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 border-l border-slate-700 transition-colors"
        >
          取消
        </button>
      </div>
    </div>
  );
};
