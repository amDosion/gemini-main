/**
 * MCP Server 创建/编辑 Dialog。
 *
 * 1:1 抽离自 `McpTab.tsx` L950-1030（< 800 行合规拆分）。
 */

import React from 'react';
import { X, Save, AlertTriangle } from 'lucide-react';

export interface McpServerDialogProps {
  isOpen: boolean;
  mode: 'create' | 'edit';
  jsonText: string;
  onJsonTextChange: (value: string) => void;
  introUrl: string;
  onIntroUrlChange: (value: string) => void;
  introUrlError: string | null;
  dialogError: string | null;
  isSaving: boolean;
  onSave: () => void;
  onCancel: () => void;
}

export const McpServerDialog: React.FC<McpServerDialogProps> = ({
  isOpen,
  mode,
  jsonText,
  onJsonTextChange,
  introUrl,
  onIntroUrlChange,
  introUrlError,
  dialogError,
  isSaving,
  onSave,
  onCancel,
}) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[160] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-3xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <h3 className="text-base md:text-lg font-semibold text-white">
            {mode === 'edit' ? 'Edit MCP Server' : 'New MCP Server'}
          </h3>
          <button
            type="button"
            onClick={onCancel}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <p className="text-xs text-slate-500">
            Paste server JSON. Supported formats:{' '}
            <code className="font-mono">{'{ name, ...config }'}</code> or{' '}
            <code className="font-mono">{'{ mcpServers: { ... } }'}</code>.
          </p>
          <div className="space-y-1.5">
            <label className="block text-xs text-slate-400">
              MCP Intro Website URL (optional)
            </label>
            <input
              type="text"
              value={introUrl}
              onChange={(e) => onIntroUrlChange(e.target.value)}
              placeholder="https://example.com/mcp-intro"
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
              disabled={isSaving}
            />
            {introUrlError && (
              <div className="rounded-lg border border-red-800/60 bg-red-900/20 px-3 py-2 text-xs text-red-200 flex items-center gap-2">
                <AlertTriangle size={14} />
                <span>{introUrlError}</span>
              </div>
            )}
          </div>

          <textarea
            value={jsonText}
            onChange={(e) => onJsonTextChange(e.target.value)}
            spellCheck={false}
            className="w-full h-72 md:h-80 resize-y rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-xs md:text-sm font-mono text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
            disabled={isSaving}
          />

          {dialogError && (
            <div className="rounded-lg border border-red-800/60 bg-red-900/20 px-3 py-2 text-xs text-red-200 flex items-center gap-2">
              <AlertTriangle size={14} />
              <span>{dialogError}</span>
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors text-sm"
            disabled={isSaving}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={isSaving}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium inline-flex items-center gap-2 transition-colors"
          >
            <Save size={14} />
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
};
