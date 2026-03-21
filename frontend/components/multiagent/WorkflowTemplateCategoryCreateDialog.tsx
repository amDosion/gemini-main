import React, { useEffect, useRef } from 'react';
import { Loader2, Plus, X } from 'lucide-react';

interface WorkflowTemplateCategoryCreateDialogProps {
  isOpen: boolean;
  title?: string;
  confirmLabel?: string;
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  onConfirm: () => void;
  loading?: boolean;
  error?: string | null;
}

export const WorkflowTemplateCategoryCreateDialog: React.FC<WorkflowTemplateCategoryCreateDialogProps> = ({
  isOpen,
  title = '新增分类',
  confirmLabel = '创建',
  value,
  onChange,
  onClose,
  onConfirm,
  loading = false,
  error = null,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!loading) {
          onClose();
        }
      } else if (event.key === 'Enter') {
        event.preventDefault();
        if (!loading) {
          onConfirm();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, loading, onClose, onConfirm]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm">
      <div className="w-[420px] max-w-[90vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
        <div className="flex items-center justify-between gap-2 mb-3">
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Plus size={16} className="text-teal-300" />
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="关闭"
          >
            <X size={16} />
          </button>
        </div>

        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="输入分类名称"
          disabled={loading}
          className="w-full px-3 py-2 text-sm border border-slate-700 rounded-lg bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
        />

        {error && (
          <div className="mt-2 text-xs text-rose-300">
            {error}
          </div>
        )}

        <div className="mt-4 inline-flex items-stretch rounded-lg border border-slate-700 overflow-hidden bg-slate-900 float-right">
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="px-3 py-1.5 text-xs text-emerald-100 bg-emerald-700/40 hover:bg-emerald-600/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            {confirmLabel}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-3 py-1.5 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            取消
          </button>
        </div>
        <div className="clear-both" />
      </div>
    </div>
  );
};
