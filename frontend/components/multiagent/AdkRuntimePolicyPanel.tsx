import React from 'react';
import type { AdkRuntimePolicyState } from './adkSessionService';

interface AdkRuntimePolicyPanelProps {
  policy: AdkRuntimePolicyState;
  onChange: (next: { strategy: string; strictMode: boolean }) => void;
}

export const AdkRuntimePolicyPanel: React.FC<AdkRuntimePolicyPanelProps> = ({ policy, onChange }) => {
  const hasDraftChange = (
    policy.selectedStrategy !== policy.effectiveStrategy
    || policy.selectedStrictMode !== policy.effectiveStrictMode
  );

  return (
    <div className="p-3 rounded border border-slate-800 bg-slate-900/40 space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-xs text-slate-300 font-medium">Runtime Policy</div>
        <div className="text-[10px] text-slate-500 font-mono">{policy.sourcePath}</div>
      </div>
      <div className="text-[11px] text-slate-400">
        当前生效: strategy={policy.effectiveStrategy} · strict_mode={policy.effectiveStrictMode ? 'true' : 'false'}
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <select
          aria-label="runtime_strategy 选择"
          value={policy.selectedStrategy}
          onChange={(event) => onChange({ strategy: event.target.value, strictMode: policy.selectedStrictMode })}
          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200"
        >
          {policy.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.value} · {option.label}
            </option>
          ))}
        </select>
        <label className="inline-flex items-center gap-2 px-2 py-1.5 rounded border border-slate-700 text-xs text-slate-300">
          <input
            aria-label="strict_mode 切换"
            type="checkbox"
            checked={policy.selectedStrictMode}
            onChange={(event) => onChange({ strategy: policy.selectedStrategy, strictMode: event.target.checked })}
            className="accent-indigo-500"
          />
          strict_mode
        </label>
      </div>
      {hasDraftChange && (
        <div className="text-[11px] text-amber-200 border border-amber-500/30 bg-amber-500/10 rounded px-2 py-1.5">
          已选择草案: strategy={policy.selectedStrategy} · strict_mode={policy.selectedStrictMode ? 'true' : 'false'}（仅前端展示，尚未提交后端）
        </div>
      )}
    </div>
  );
};

export default AdkRuntimePolicyPanel;
