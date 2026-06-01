import React from 'react';
import { cacheManager, CACHE_DOMAINS } from '../../services/CacheManager';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
  registerPrivateCacheResetHandler,
} from '../../services/privateCacheInvalidation';
import {
  scopedPrivateCacheKey,
} from '../../services/privateCacheScope';
import { usePrivateCacheLifecycleRevision } from '../../hooks/usePrivateCacheScopeRevision';
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

const AGENT_REGISTRY_CACHE_TTL_MS = 5 * 60 * 1000;
cacheManager.setTTL(CACHE_DOMAINS.AGENT_REGISTRY, AGENT_REGISTRY_CACHE_TTL_MS);

// 数据缓存统一走 CacheManager + private user scope；in-flight Map 只负责同 key 请求去重。
const inFlightAgents = new Map<string, Promise<AgentDef[]>>();
let agentRegistryCacheGeneration = 0;

const clearAgentRegistryCache = (): void => {
  agentRegistryCacheGeneration += 1;
  cacheManager.clearDomain(CACHE_DOMAINS.AGENT_REGISTRY);
  inFlightAgents.clear();
};

registerPrivateCacheResetHandler(clearAgentRegistryCache);

// 订阅刷新事件清空 cache（agent 增删改后触发）
let cacheInvalidationSubscribed = false;
const ensureCacheInvalidation = () => {
  if (cacheInvalidationSubscribed) return;
  cacheInvalidationSubscribed = true;
  subscribeAgentRegistryUpdated(() => {
    clearAgentRegistryCache();
  });
};

const buildCacheKey = (includeInactive: boolean, search: string) =>
  scopedPrivateCacheKey(
    CACHE_DOMAINS.AGENT_REGISTRY,
    `${includeInactive ? '1' : '0'}::${search}`
  );

/**
 * 测试-only：清空 user-scope cache + in-flight Map，让单测之间隔离。
 * 生产代码不应调用（cache 失效统一走 subscribeAgentRegistryUpdated）。
 */
export const __resetAgentRegistryCacheForTesting = (): void => {
  clearAgentRegistryCache();
};

export const useAgentRegistry = (options: UseAgentRegistryOptions = {}): UseAgentRegistryResult => {
  const { includeInactive = false, search = '', autoLoad = true } = options;
  const cacheKey = buildCacheKey(includeInactive, search);
  const [agents, setAgents] = React.useState<AgentDef[]>(
    () => cacheManager.get<AgentDef[]>(cacheKey) ?? []
  );
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  // sequence-based stale-result discard（保留原 hook 的语义）
  const latestRequestIdRef = React.useRef(0);

  ensureCacheInvalidation();

  usePrivateCacheLifecycleRevision(() => {
    latestRequestIdRef.current += 1;
    setAgents([]);
    setLoading(false);
    setError(null);
  }, { includeCacheReset: true });

  // refreshAgents：user-action，**force** fire 新 fetch；写入 cache 让其他实例可复用
  const refreshAgents = React.useCallback(async (): Promise<AgentDef[]> => {
    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    setLoading(true);
    setError(null);
    const generationAtStart = agentRegistryCacheGeneration;
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
    try {
      const result = await fetchAgentList({ includeInactive, search });
      // stale 结果丢弃（后发起的 refresh 先返回时旧响应不能覆盖新状态）
      if (requestId !== latestRequestIdRef.current) return [];
      if (!isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) return [];
      if (generationAtStart === agentRegistryCacheGeneration) {
        cacheManager.set(cacheKey, result.agents);
      }
      setAgents(result.agents);
      setError(null);
      return result.agents;
    } catch (e) {
      if (requestId !== latestRequestIdRef.current) return [];
      if (!isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) return [];
      const message = e instanceof Error ? e.message : 'Failed to fetch agents';
      setError(message);
      return [];
    } finally {
      if (
        requestId === latestRequestIdRef.current &&
        isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
      ) {
        setLoading(false);
      }
    }
  }, [cacheKey, includeInactive, search]);

  // mount 自动 fetch：cache hit → 不 fetch；cache miss + in-flight hit → 复用 Promise；
  // cache miss + 无 in-flight → 新 fetch（写入 in-flight 让多实例同 mount 共享）
  // sequence guard：mount fetch 与 user refreshAgents 共享 latestRequestIdRef，确保 stale
  // mount result 不覆盖 user refresh 后的最新 state
  React.useEffect(() => {
    if (!autoLoad) return;
    const cached = cacheManager.get<AgentDef[]>(cacheKey);
    if (cached !== null) {
      setAgents(cached);
      return;
    }
    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    let active = true;
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
    let fetchPromise = inFlightAgents.get(cacheKey);
    if (!fetchPromise) {
      const generationAtStart = agentRegistryCacheGeneration;
      fetchPromise = fetchAgentList({ includeInactive, search })
        .then((result) => {
          if (
            generationAtStart === agentRegistryCacheGeneration &&
            isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
          ) {
            cacheManager.set(cacheKey, result.agents);
          }
          return result.agents;
        })
        .finally(() => {
          if (inFlightAgents.get(cacheKey) === fetchPromise) {
            inFlightAgents.delete(cacheKey);
          }
        });
      inFlightAgents.set(cacheKey, fetchPromise);
    }
    setLoading(true);
    fetchPromise
      .then((list) => {
        if (
          !active ||
          requestId !== latestRequestIdRef.current ||
          !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
        ) {
          return;
        }
        setAgents(list);
        setError(null);
      })
      .catch((e) => {
        if (
          !active ||
          requestId !== latestRequestIdRef.current ||
          !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
        ) {
          return;
        }
        const message = e instanceof Error ? e.message : 'Failed to fetch agents';
        setError(message);
      })
      .finally(() => {
        if (
          active &&
          requestId === latestRequestIdRef.current &&
          isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
        ) {
          setLoading(false);
        }
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
