import React, { useState } from 'react';
import { Copy, Check, Download, Table, Code, FileText, Globe } from 'lucide-react';
import { PdfExtractionResult } from '../../../types/types';

export type ViewMode = 'table' | 'json' | 'markdown' | 'html';

interface PdfResultToolbarProps {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  result: PdfExtractionResult;
}

export const PdfResultToolbar: React.FC<PdfResultToolbarProps> = ({ 
  viewMode, 
  setViewMode, 
  result 
}) => {
  const [copied, setCopied] = useState(false);

  const downloadAsJson = () => {
    if (!result.data) return;
    const dataStr = JSON.stringify(result.data, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `extracted-${result.templateType || 'data'}-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const copyJson = () => {
    if (!result.data) return;
    navigator.clipboard.writeText(JSON.stringify(result.data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!result.success) return null;

  const tabs: { mode: ViewMode; icon: React.ReactNode; label: string }[] = [
    { mode: 'table', icon: <Table size={14} />, label: '表格' },
    { mode: 'json', icon: <Code size={14} />, label: 'JSON' },
    { mode: 'markdown', icon: <FileText size={14} />, label: 'Markdown' },
    { mode: 'html', icon: <Globe size={14} />, label: 'HTML' },
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 p-2 px-4 bg-slate-900/30">
      {/* View Mode Tabs */}
      <div className="flex bg-slate-800/50 rounded-lg p-1">
        {tabs.map(({ mode, icon, label }) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              viewMode === mode 
                ? 'bg-indigo-600 text-white shadow-sm' 
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
          >
            {icon}
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={downloadAsJson}
          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs text-slate-200 transition-all"
          title="下载 JSON"
        >
          <Download size={14} />
          <span className="hidden sm:inline">下载</span>
        </button>

        <button
          onClick={copyJson}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 rounded-lg text-sm text-indigo-300 hover:text-indigo-200 transition-all"
          title="复制 JSON"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span className="hidden sm:inline">{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
    </div>
  );
};
