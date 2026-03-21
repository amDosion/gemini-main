import React from 'react';
import { Ban, Bot, Edit3, Loader2, RotateCcw, Search, Trash2, Workflow } from 'lucide-react';
import type { AgentDef } from '../types';
import {
  AGENT_TASK_FILTER_LABELS,
} from '../agentRegistryService';

const getAgentSourceBadgeClassName = (sourceKind: string): string => {
  if (sourceKind === 'seed') {
    return 'text-amber-200 border border-amber-500/30 bg-amber-500/10';
  }
  if (sourceKind === 'google-runtime') {
    return 'text-cyan-300 border border-cyan-500/30 bg-cyan-500/10';
  }
  if (sourceKind === 'vertex-interactions') {
    return 'text-violet-300 border border-violet-500/30 bg-violet-500/10';
  }
  return 'text-slate-300 border border-slate-600 bg-slate-800/80';
};

interface AgentManagerListViewProps {
  activeCount: number;
  inactiveCount: number;
  searchKeyword: string;
  selectedStatus: 'active' | 'inactive';
  notice: { type: 'success' | 'error'; text: string } | null;
  loading: boolean;
  agents: AgentDef[];
  onSearchKeywordChange: (keyword: string) => void;
  onSelectStatus: (status: 'active' | 'inactive') => void;
  onCreate: () => void;
  onEdit: (agent: AgentDef) => void;
  onDisable: (agent: AgentDef) => void;
  onRestore: (agent: AgentDef) => void;
  onHardDelete: (agent: AgentDef) => void;
  onOpenRuntimeSessions: (agent: AgentDef) => void;
}

export const AgentManagerListView: React.FC<AgentManagerListViewProps> = ({
  activeCount,
  inactiveCount,
  searchKeyword,
  selectedStatus,
  notice,
  loading,
  agents,
  onSearchKeywordChange,
  onSelectStatus,
  onCreate,
  onEdit,
  onDisable,
  onRestore,
  onHardDelete,
  onOpenRuntimeSessions,
}) => (
  <div className="flex flex-col h-full bg-slate-900 text-slate-200">
    <div className="px-3 pt-3 space-y-2">
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <button
          type="button"
          onClick={() => onSelectStatus('active')}
          className={`px-2.5 py-1.5 rounded border text-left transition-colors ${
            selectedStatus === 'active'
              ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
              : 'border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          Active: {activeCount}
        </button>
        <button
          type="button"
          onClick={() => onSelectStatus('inactive')}
          className={`px-2.5 py-1.5 rounded border text-left transition-colors ${
            selectedStatus === 'inactive'
              ? 'border-teal-500/40 bg-teal-500/15 text-teal-200'
              : 'border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          Inactive: {inactiveCount}
        </button>
      </div>
      <div className="relative">
        <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
        <input
          value={searchKeyword}
          onChange={(event) => onSearchKeywordChange(event.target.value)}
          placeholder="搜索名称 / 提供商 / 模型"
          className="w-full pl-8 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
        />
      </div>
    </div>

    {notice && (
      <div
        className={`mx-3 mt-3 px-3 py-2 rounded-lg border text-xs ${
          notice.type === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-red-500/10 border-red-500/30 text-red-300'
        }`}
      >
        {notice.text}
      </div>
    )}

    <div className="flex-1 overflow-y-auto p-3 space-y-2">
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-slate-500" />
        </div>
      ) : agents.length === 0 ? (
        <div className="text-center py-8">
          <Bot size={32} className="mx-auto mb-3 text-slate-600" />
          <p className="text-sm text-slate-500">
            {searchKeyword
              ? '没有匹配的 Agent'
              : (selectedStatus === 'inactive' ? '暂无停用 Agent' : '还没有 Agent')}
          </p>
          {!searchKeyword && selectedStatus === 'active' && (
            <button
              onClick={onCreate}
              className="mt-3 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs font-medium transition-colors"
            >
              创建第一个 Agent
            </button>
          )}
        </div>
      ) : (
        agents.map((agent) => {
          const isActive = agent.status === 'active';
          const supportsRuntimeSessions = Boolean(
            agent.runtime?.supportsSessions
            ?? agent.supportsRuntimeSessions
          );
          const runtimeLabel = String(agent.runtime?.label || '').trim();
          const supportsOfficialOrchestration = Boolean(
            agent.runtime?.supportsOfficialOrchestration
            ?? agent.supportsOfficialOrchestration
          );
          const defaultTaskType = agent.agentCard?.defaults?.defaultTaskType || 'chat';
          const defaultTaskLabel = AGENT_TASK_FILTER_LABELS[defaultTaskType as keyof typeof AGENT_TASK_FILTER_LABELS] || defaultTaskType;
          const sourceLabel = String(agent.source?.label || '').trim();
          const sourceKind = String(agent.source?.kind || '').trim();
          return (
            <div
              key={agent.id}
              className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-teal-500/30 transition-colors group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="text-xl flex-shrink-0">{agent.icon}</span>
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{agent.name}</div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">{agent.providerId}/{agent.modelId}</div>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] border ${
                      isActive
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                        : 'bg-slate-700/70 border-slate-600 text-slate-300'
                    }`}
                  >
                    {isActive ? 'active' : 'inactive'}
                  </span>
                  {isActive ? (
                    <>
                      {supportsRuntimeSessions && (
                        <button
                          onClick={() => onOpenRuntimeSessions(agent)}
                          className="p-1.5 inline-flex items-center justify-center rounded border border-indigo-500/20 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 transition-colors"
                          title="管理运行时会话"
                        >
                          <Workflow size={12} />
                        </button>
                      )}
                      <button
                        onClick={() => onEdit(agent)}
                        className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
                        title="编辑"
                      >
                        <Edit3 size={13} />
                      </button>
                      <button
                        onClick={() => onDisable(agent)}
                        className="p-1.5 inline-flex items-center justify-center rounded border border-amber-500/20 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 transition-colors"
                        title="停用"
                      >
                        <Ban size={12} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => onRestore(agent)}
                        className="px-2 py-1 inline-flex items-center gap-1 rounded border border-emerald-500/20 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 transition-colors"
                        title="恢复"
                      >
                        <RotateCcw size={12} />
                        <span className="text-[10px] leading-none">恢复</span>
                      </button>
                      <button
                        onClick={() => onHardDelete(agent)}
                        className="px-2 py-1 inline-flex items-center gap-1 rounded border border-red-500/20 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                        title="永久删除"
                      >
                        <Trash2 size={12} />
                        <span className="text-[10px] leading-none">永久删除</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
              {agent.description && <p className="text-[11px] text-slate-500 mt-1.5 line-clamp-2">{agent.description}</p>}
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
                <div className="text-indigo-300 border border-indigo-500/30 bg-indigo-500/10 inline-flex px-1.5 py-0.5 rounded">
                  默认任务: {defaultTaskLabel}
                </div>
                {sourceLabel && (
                  <div className={`inline-flex px-1.5 py-0.5 rounded ${getAgentSourceBadgeClassName(sourceKind)}`}>
                    来源: {sourceLabel}
                  </div>
                )}
                {runtimeLabel && (
                  <div className="text-cyan-300 border border-cyan-500/30 bg-cyan-500/10 inline-flex px-1.5 py-0.5 rounded">
                    Runtime: {runtimeLabel}
                  </div>
                )}
                {supportsOfficialOrchestration && (
                  <div className="text-emerald-300 border border-emerald-500/30 bg-emerald-500/10 inline-flex px-1.5 py-0.5 rounded">
                    官方编排
                  </div>
                )}
              </div>
            </div>
          );
        })
      )}
    </div>
  </div>
);
