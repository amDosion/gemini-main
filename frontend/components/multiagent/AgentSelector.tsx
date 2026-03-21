/**
 * AgentSelector - Agent 节点配置中的 Agent 选择器
 */

import React, { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import type { AgentDef } from './types';
import { useAgentRegistry } from './useAgentRegistry';

interface AgentSelectorProps {
  value: string;
  agentName?: string;
  onChange: (agentId: string, agentName: string, agent?: AgentDef) => void;
  onResolvedAgent?: (agent: AgentDef | null) => void;
}

const normalizeName = (value: string) => value.trim().toLowerCase();

export const AgentSelector: React.FC<AgentSelectorProps> = ({ value, agentName = '', onChange, onResolvedAgent }) => {
  const { agents, loading, error } = useAgentRegistry();
  const normalizedValue = String(value || '').trim();
  const selected = agents.find((agent) => agent.id === normalizedValue);
  const hasInvalidBinding = !error && normalizedValue.length > 0 && !selected;
  const fallbackName = String(agentName || '').trim();
  const selectValue = selected ? selected.id : '';

  useEffect(() => {
    if (loading) return;
    if (error) return;
    if (value) return;
    if (!fallbackName) return;
    if (agents.length === 0) return;

    const matched = agents.find((agent) => normalizeName(String(agent?.name || '')) === normalizeName(fallbackName));
    if (!matched) return;

    onChange(matched.id, matched.name, matched);
  }, [loading, error, value, agentName, agents, onChange]);

  useEffect(() => {
    if (loading) return;
    onResolvedAgent?.(selected || null);
  }, [loading, onResolvedAgent, selected]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-slate-500">
        <Loader2 size={14} className="animate-spin" /> 加载 Agent 列表...
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <select
        value={selectValue}
        onChange={(e) => {
          const nextId = e.target.value;
          const agent = agents.find((item) => item.id === nextId);
          onChange(nextId, agent?.name || '', agent);
        }}
        className="w-full px-3 py-2 border border-slate-700 bg-slate-800 rounded-lg text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
      >
        <option value="">请选择 Agent</option>
        {agents.map(agent => (
          <option key={agent.id} value={agent.id}>
            {agent.icon} {agent.name} ({agent.providerId}/{agent.modelId})
          </option>
        ))}
      </select>
      {error && (
        <p className="text-xs text-rose-300">
          Agent 列表加载失败：{error}
        </p>
      )}
      {!error && agents.length === 0 && (
        <p className="text-xs text-amber-400">
          还没有创建 Agent，请先在 Agent 管理面板中创建。
        </p>
      )}
      {hasInvalidBinding && (
        <div className="p-2 bg-amber-500/10 rounded text-xs text-amber-200 border border-amber-500/30 space-y-1">
          <div className="font-medium text-amber-100">当前绑定的 Agent 已失效或被删除</div>
          <div className="text-[11px] text-amber-300/90 break-all">
            ID: {normalizedValue}
            {fallbackName ? ` · 名称: ${fallbackName}` : ''}
          </div>
          <button
            type="button"
            onClick={() => onChange('', '', undefined)}
            className="px-2 py-1 rounded border border-amber-500/40 bg-amber-500/20 hover:bg-amber-500/30 transition-colors text-[11px]"
          >
            清理失效绑定
          </button>
        </div>
      )}
      {selected && (
        <div className="p-2 bg-teal-500/10 rounded text-xs text-slate-300 border border-teal-500/30">
          <div className="font-medium text-teal-300">{selected.icon} {selected.name}</div>
          <div className="text-slate-500 mt-0.5">{selected.providerId} / {selected.modelId}</div>
          {selected.description && <div className="mt-0.5">{selected.description}</div>}
        </div>
      )}
      {!selected && !normalizedValue && fallbackName && !error && (
        <div className="p-2 bg-amber-500/10 rounded text-xs text-amber-200 border border-amber-500/30">
          模板绑定智能体：{agentName}（当前未匹配到同名 Agent）
        </div>
      )}
    </div>
  );
};
