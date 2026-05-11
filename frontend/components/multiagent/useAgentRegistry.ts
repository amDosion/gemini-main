import React from 'react';
import type { AgentDef } from './types';
import { fetchAgentList, subscribeAgentRegistryUpdated } from './agentRegistryService';

interface UseAgentRegistryOptions {
  includeInactive?: boolean;
  search?: string;
  autoLoad?: boolean;
}

interface UseAgentRegistryResult {
  agents: AgentDef[];
  loading: boolean;
  error: string | null;
  refreshAgents: () => Promise<AgentDef[]>;
}

// 模块级 cache + in-flight dedupe（修复用户反馈：/api/agents 多 AgentSelector 实例并发重复 fetch）
// cacheKey = includeInactive::search
const agentsCache = new Map<string, AgentDef[]>();
const inFlightAgents = new Map<string, Promise<AgentDef[]>>();
// 订阅刷新事件清空 cache（agent 增删改后触发）
let cacheInvalidationSubscribed = false;
const ensureCacheInvalidation = () => {
  if (cacheInvalidationSubscribed) return;
  cacheInvalidationSubscribed = true;
  subscribeAgentRegistryUpdated(() => {
    agentsCache.clear();
    inFlightAgents.clear();
  });
};

const buildCacheKey = (includeInactive: boolean, search: string) =>
  `${includeInactive ? '1' : '0'}::${search}`;

/**
 * 测试-only：清空模块级 cache + in-flight Map，让单测之间隔离。
 * 生产代码不应调用（cache 失效统一走 subscribeAgentRegistryUpdated）。
 */
export const __resetAgentRegistryCacheForTesting = (): void => {
  agentsCache.clear();
  inFlightAgents.clear();
};

export const useAgentRegistry = (options: UseAgentRegistryOptions = {}): UseAgentRegistryResult => {
  const { includeInactive = false, search = '', autoLoad = true } = options;
  const cacheKey = buildCacheKey(includeInactive, search);
  const [agents, setAgents] = React.useState<AgentDef[]>(() => agentsCache.get(cacheKey) ?? []);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // sequence-based stale-result discard（保留原 hook 的语义）
  const latestRequestIdRef = React.useRef(0);

  ensureCacheInvalidation();

  // refreshAgents：user-action，**force** fire 新 fetch；写入 cache 让其他实例可复用
  const refreshAgents = React.useCallback(async (): Promise<AgentDef[]> => {
    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAgentList({ includeInactive, search });
      // stale 结果丢弃（后发起的 refresh 先返回时旧响应不能覆盖新状态）
      if (requestId !== latestRequestIdRef.current) return result.agents;
      agentsCache.set(cacheKey, result.agents);
      setAgents(result.agents);
      setError(null);
      return result.agents;
    } catch (e) {
      if (requestId !== latestRequestIdRef.current) return [];
      const message = e instanceof Error ? e.message : 'Failed to fetch agents';
      setError(message);
      return [];
    } finally {
      if (requestId === latestRequestIdRef.current) setLoading(false);
    }
  }, [cacheKey, includeInactive, search]);

  // mount 自动 fetch：cache hit → 不 fetch；cache miss + in-flight hit → 复用 Promise；
  // cache miss + 无 in-flight → 新 fetch（写入 in-flight 让多实例同 mount 共享）
  // sequence guard：mount fetch 与 user refreshAgents 共享 latestRequestIdRef，确保 stale
  // mount result 不覆盖 user refresh 后的最新 state
  React.useEffect(() => {
    if (!autoLoad) return;
    const cached = agentsCache.get(cacheKey);
    if (cached) {
      setAgents(cached);
      return;
    }
    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    let active = true;
    let fetchPromise = inFlightAgents.get(cacheKey);
    if (!fetchPromise) {
      fetchPromise = fetchAgentList({ includeInactive, search })
        .then((result) => {
          agentsCache.set(cacheKey, result.agents);
          return result.agents;
        })
        .finally(() => inFlightAgents.delete(cacheKey));
      inFlightAgents.set(cacheKey, fetchPromise);
    }
    setLoading(true);
    fetchPromise
      .then((list) => {
        if (!active || requestId !== latestRequestIdRef.current) return;
        setAgents(list);
        setError(null);
      })
      .catch((e) => {
        if (!active || requestId !== latestRequestIdRef.current) return;
        const message = e instanceof Error ? e.message : 'Failed to fetch agents';
        setError(message);
      })
      .finally(() => {
        if (active && requestId === latestRequestIdRef.current) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [autoLoad, cacheKey, includeInactive, search]);

  React.useEffect(() => {
    if (!autoLoad) return;
    return subscribeAgentRegistryUpdated(() => {
      void refreshAgents();
    });
  }, [autoLoad, refreshAgents]);

  return {
    agents,
    loading,
    error,
    refreshAgents,
  };
};
