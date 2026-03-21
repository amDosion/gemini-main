/**
 * AgentManagerPanel - Agent 管理面板
 *
 * 创建、编辑、恢复、删除 Agent（动态获取用户已配置的 LLM 提供商和模型）
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Ban, Loader2, RotateCcw, Trash2 } from 'lucide-react';
import { getAuthHeaders } from '../../services/apiClient';
import type { AgentDef } from './types';
import {
  createDefaultAgentCard,
  emitAgentRegistryUpdated,
  fetchAgentList,
} from './agentRegistryService';
import {
  AgentTaskType,
  ProviderModels,
  modelSupportsTask,
  normalizeProviderModels,
  pickProviderDefaultModel,
} from './providerModelUtils';
import { AgentManagerEditorForm } from './agentManager/AgentManagerEditorForm';
import { AgentManagerListView } from './agentManager/AgentManagerListView';
import { AgentRuntimeSessionPanel } from './AgentRuntimeSessionPanel';

interface AgentManagerPanelProps {
  onAgentCountChange?: (count: number) => void;
  preferredProviderId?: string;
  preferredModelId?: string;
}

export const AGENT_MANAGER_REFRESH_EVENT = 'multiagent:agent-manager-refresh';
export const AGENT_MANAGER_CREATE_EVENT = 'multiagent:agent-manager-create';

export const AgentManagerPanel: React.FC<AgentManagerPanelProps> = ({
  onAgentCountChange,
  preferredProviderId,
  preferredModelId,
}) => {
  const [agents, setAgents] = useState<AgentDef[]>([]);
  const [providers, setProviders] = useState<ProviderModels[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<AgentDef | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<'active' | 'inactive'>('active');
  const [activeCount, setActiveCount] = useState(0);
  const [inactiveCount, setInactiveCount] = useState(0);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pendingDeleteAction, setPendingDeleteAction] = useState<{
    id: string;
    name: string;
    hardDelete: boolean;
  } | null>(null);
  const [deletingAction, setDeletingAction] = useState(false);
  const [pendingRestoreAction, setPendingRestoreAction] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [restoringAction, setRestoringAction] = useState(false);
  const [activeRuntimeAgent, setActiveRuntimeAgent] = useState<AgentDef | null>(null);
  const latestFetchRequestIdRef = useRef(0);
  const fetchAbortControllerRef = useRef<AbortController | null>(null);

  const getHeaders = useCallback((): HeadersInit => ({
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
  }), []);

  const getErrorMessage = useCallback(async (response: Response, fallback: string) => {
    try {
      const payload = await response.json();
      return payload?.detail || payload?.message || fallback;
    } catch {
      return fallback;
    }
  }, []);

  const fetchProviders = useCallback(async () => {
    await fetch('/api/agents/available-models', {
      headers: getHeaders(),
      credentials: 'include',
    }).then(res => {
      if (res.ok) return res.json().then(data => setProviders(normalizeProviderModels(data)));
    });
  }, [getHeaders]);

  const fetchAgents = useCallback(async () => {
    const requestId = latestFetchRequestIdRef.current + 1;
    latestFetchRequestIdRef.current = requestId;
    fetchAbortControllerRef.current?.abort();
    const controller = new AbortController();
    fetchAbortControllerRef.current = controller;
    setLoading(true);
    try {
      const includeInactive = selectedStatus === 'inactive';
      const result = await fetchAgentList({
        includeInactive,
        search: searchKeyword.trim(),
        status: selectedStatus,
        signal: controller.signal,
      });
      if (controller.signal.aborted || requestId !== latestFetchRequestIdRef.current) {
        return;
      }
      setAgents(result.agents);
      setActiveCount(result.activeCount);
      setInactiveCount(result.inactiveCount);
    } catch (error) {
      if (controller.signal.aborted || requestId !== latestFetchRequestIdRef.current) {
        return;
      }
    } finally {
      if (requestId === latestFetchRequestIdRef.current) {
        fetchAbortControllerRef.current = null;
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }
  }, [searchKeyword, selectedStatus]);

  useEffect(() => {
    return () => {
      fetchAbortControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchAgents();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [fetchAgents]);

  const handleNew = useCallback(() => {
    const baseCard = createDefaultAgentCard();
    const defaultTaskType = (baseCard.defaults.defaultTaskType || 'chat') as AgentTaskType;
    const normalizedPreferredProviderId = String(preferredProviderId || '').trim();
    const normalizedPreferredModelId = String(preferredModelId || '').trim();
    const preferredProvider = normalizedPreferredProviderId
      ? providers.find((provider) => provider.providerId === normalizedPreferredProviderId)
      : undefined;
    const preferredProviderModel = normalizedPreferredModelId && preferredProvider
      ? (preferredProvider.allModels.find((model) => model.id === normalizedPreferredModelId)
        || preferredProvider.models.find((model) => model.id === normalizedPreferredModelId))
      : undefined;
    const preferredProviderSupportsTask = modelSupportsTask(preferredProviderModel, defaultTaskType);
    const fallbackProvider =
      providers.find((provider) => pickProviderDefaultModel(provider, defaultTaskType))
      || providers[0];
    const targetProvider =
      preferredProvider && (preferredProviderSupportsTask || pickProviderDefaultModel(preferredProvider, defaultTaskType))
        ? preferredProvider
        : fallbackProvider;
    const targetModel =
      preferredProvider && preferredProviderSupportsTask && preferredProviderModel
        ? preferredProviderModel
        : pickProviderDefaultModel(targetProvider, defaultTaskType);
    setEditing({
      id: '',
      name: '',
      description: '',
      agentType: 'custom',
      providerId: targetProvider?.providerId || '',
      modelId: targetModel?.id || '',
      systemPrompt: '',
      temperature: 0.7,
      maxTokens: 4096,
      icon: '🤖',
      color: '#14b8a6',
      status: 'active',
      agentCard: {
        ...baseCard,
        defaults: {
          ...baseCard.defaults,
          defaultTaskType,
        },
      },
    });
    setIsNew(true);
  }, [preferredModelId, preferredProviderId, providers]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handleRefreshEvent = () => {
      void fetchAgents();
    };
    const handleCreateEvent = () => {
      handleNew();
    };
    window.addEventListener(AGENT_MANAGER_REFRESH_EVENT, handleRefreshEvent as EventListener);
    window.addEventListener(AGENT_MANAGER_CREATE_EVENT, handleCreateEvent as EventListener);
    return () => {
      window.removeEventListener(AGENT_MANAGER_REFRESH_EVENT, handleRefreshEvent as EventListener);
      window.removeEventListener(AGENT_MANAGER_CREATE_EVENT, handleCreateEvent as EventListener);
    };
  }, [fetchAgents, handleNew]);

  useEffect(() => {
    onAgentCountChange?.(activeCount + inactiveCount);
  }, [activeCount, inactiveCount, onAgentCountChange]);

  const handleSave = async () => {
    if (!editing || !editing.name.trim() || !editing.providerId || !editing.modelId) return;
    const defaultTaskType = (editing.agentCard?.defaults?.defaultTaskType || 'chat') as AgentTaskType;
    const currentProvider = providers.find((provider) => provider.providerId === editing.providerId);
    const currentModel = currentProvider?.allModels.find((model) => model.id === editing.modelId)
      || currentProvider?.models.find((model) => model.id === editing.modelId);
    if (!modelSupportsTask(currentModel, defaultTaskType)) {
      setNotice({ type: 'error', text: `当前模型不支持 ${defaultTaskType}，请重新选择兼容模型` });
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      const url = isNew ? '/api/agents' : `/api/agents/${editing.id}`;
      const method = isNew ? 'POST' : 'PUT';
      const res = await fetch(url, {
        method,
        headers: getHeaders(),
        credentials: 'include',
        body: JSON.stringify({
          name: editing.name,
          description: editing.description,
          agentType: String(editing.agentType || 'custom').trim().toLowerCase() || 'custom',
          providerId: editing.providerId,
          modelId: editing.modelId,
          systemPrompt: editing.systemPrompt,
          temperature: editing.temperature,
          maxTokens: editing.maxTokens,
          icon: editing.icon,
          color: editing.color,
          agentCard: editing.agentCard || createDefaultAgentCard(),
        }),
      });
      if (res.ok) {
        setEditing(null);
        setIsNew(false);
        await fetchAgents();
        emitAgentRegistryUpdated();
        setNotice({ type: 'success', text: isNew ? 'Agent 创建成功' : 'Agent 更新成功' });
      } else {
        setNotice({ type: 'error', text: await getErrorMessage(res, '保存 Agent 失败') });
      }
    } catch (error) {
      setNotice({ type: 'error', text: '保存 Agent 失败，请稍后重试' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string, hardDelete: boolean = false) => {
    setNotice(null);
    setDeletingAction(true);
    try {
      const path = hardDelete ? `/api/agents/${id}?hard_delete=true` : `/api/agents/${id}`;
      const res = await fetch(path, {
        method: 'DELETE',
        headers: getHeaders(),
        credentials: 'include',
      });
      if (!res.ok) {
        setNotice({ type: 'error', text: await getErrorMessage(res, hardDelete ? '永久删除失败' : '停用失败') });
        return;
      }
      await fetchAgents();
      emitAgentRegistryUpdated();
      setPendingDeleteAction(null);
      if (hardDelete) {
        setNotice({ type: 'success', text: 'Agent 已永久删除' });
      }
    } catch (error) {
      setNotice({ type: 'error', text: hardDelete ? '永久删除失败，请稍后重试' : '停用失败，请稍后重试' });
    } finally {
      setDeletingAction(false);
    }
  };

  const handleRestore = async (id: string) => {
    setNotice(null);
    setRestoringAction(true);
    try {
      const res = await fetch(`/api/agents/${id}/restore?rename_on_conflict=true`, {
        method: 'POST',
        headers: getHeaders(),
        credentials: 'include',
      });
      if (!res.ok) {
        setNotice({ type: 'error', text: await getErrorMessage(res, '恢复 Agent 失败') });
        return;
      }
      await fetchAgents();
      emitAgentRegistryUpdated();
      setPendingRestoreAction(null);
    } catch (error) {
      setNotice({ type: 'error', text: '恢复 Agent 失败，请稍后重试' });
    } finally {
      setRestoringAction(false);
    }
  };

  if (editing) {
    return (
      <AgentManagerEditorForm
        editing={editing}
        isNew={isNew}
        saving={saving}
        providers={providers}
        onCancel={() => {
          setEditing(null);
          setIsNew(false);
        }}
        onSave={handleSave}
        onChange={setEditing}
      />
    );
  }

  return (
    <div className="relative h-full">
      <AgentManagerListView
        activeCount={activeCount}
        inactiveCount={inactiveCount}
        searchKeyword={searchKeyword}
        selectedStatus={selectedStatus}
        notice={notice}
        loading={loading}
        agents={agents}
        onSearchKeywordChange={setSearchKeyword}
        onSelectStatus={setSelectedStatus}
        onCreate={handleNew}
        onEdit={(agent) => {
          setEditing(agent);
          setIsNew(false);
        }}
        onDisable={(agent) => {
          setPendingRestoreAction(null);
          setPendingDeleteAction({
            id: agent.id,
            name: agent.name,
            hardDelete: false,
          });
        }}
        onRestore={(agent) => {
          setPendingDeleteAction(null);
          setPendingRestoreAction({
            id: agent.id,
            name: agent.name,
          });
        }}
        onHardDelete={(agent) => {
          setPendingRestoreAction(null);
          setPendingDeleteAction({
            id: agent.id,
            name: agent.name,
            hardDelete: true,
          });
        }}
        onOpenRuntimeSessions={(agent) => {
          setActiveRuntimeAgent(agent);
        }}
      />

      {pendingDeleteAction && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm">
          <div className="w-[430px] max-w-[92vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
            <h3 className="text-base font-semibold text-slate-100 mb-2">
              {pendingDeleteAction.hardDelete ? '确认永久删除 Agent' : '确认停用 Agent'}
            </h3>
            <p className="text-sm text-slate-300">
              {pendingDeleteAction.hardDelete ? (
                <>
                  将永久删除「<span className="text-rose-200">{pendingDeleteAction.name}</span>」，此操作不可恢复。
                </>
              ) : (
                <>
                  将停用「<span className="text-amber-200">{pendingDeleteAction.name}</span>」，该操作不会删除数据，可稍后恢复。
                </>
              )}
            </p>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setPendingDeleteAction(null)}
                disabled={deletingAction}
                className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                取消
              </button>
              <button
                onClick={() => {
                  void handleDelete(pendingDeleteAction.id, pendingDeleteAction.hardDelete);
                }}
                disabled={deletingAction}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 ${
                  pendingDeleteAction.hardDelete
                    ? 'border border-rose-700/70 bg-rose-900/30 text-rose-200 hover:bg-rose-800/40'
                    : 'border border-amber-700/60 bg-amber-900/30 text-amber-100 hover:bg-amber-800/40'
                }`}
              >
                {deletingAction ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : pendingDeleteAction.hardDelete ? (
                  <Trash2 size={13} />
                ) : (
                  <Ban size={13} />
                )}
                {pendingDeleteAction.hardDelete ? '确认永久删除' : '确认停用'}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeRuntimeAgent && (
        <AgentRuntimeSessionPanel
          agent={activeRuntimeAgent}
          onClose={() => setActiveRuntimeAgent(null)}
        />
      )}

      {pendingRestoreAction && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm">
          <div className="w-[430px] max-w-[92vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
            <h3 className="text-base font-semibold text-slate-100 mb-2">确认恢复 Agent</h3>
            <p className="text-sm text-slate-300">
              将恢复「<span className="text-emerald-200">{pendingRestoreAction.name}</span>」，并重新出现在 Active 列表中。
            </p>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setPendingRestoreAction(null)}
                disabled={restoringAction}
                className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                取消
              </button>
              <button
                onClick={() => {
                  void handleRestore(pendingRestoreAction.id);
                }}
                disabled={restoringAction}
                className="px-3 py-1.5 text-sm rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 border border-emerald-700/60 bg-emerald-900/30 text-emerald-100 hover:bg-emerald-800/40"
              >
                {restoringAction ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
                确认恢复
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
